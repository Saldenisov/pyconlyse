"""Injected Python 3.4 executor for saved ACQ impulse events 23 and 24.

No device, clock, thread or transport is opened here. Counter callbacks use
retained physical ctr3/ctr4 tasks. Pulse completion is source CO property 6414,
NOT Task.is_task_done and NOT proof of physical modulator operation.

The original Clear Errors boundaries continue the counter chain; Python
callback exceptions are retained instead of discarded. Publication DPS->EPS
preserves its source error wire. Other independent same-frame nodes are
serialized by this adapter. An aggregate exception does not suppress later
source frames except cancellation or observer failure.

Python failure policy (not a source guarantee): failed/cancelled starts stop
every counter whose start may have applied; cancelled stops attempt both
counter stops without consulting cancellation again. Failed cleanup remains
explicit in the report; ownership must stay with the caller until resolved.
No error path closes, drops or replaces the task owner's retained handles.
"""


SOURCE_VI_SHA256 = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
SOURCE_COUNTER_HELPER_SHA256 = "4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211"
SUPPORTED_OPERATIONS = ("modulator_impulse.start", "modulator_impulse.stop")
FRAME_UIDS = {
    "modulator_impulse.start": ("45203", "45276", "45385", "45576"),
    "modulator_impulse.stop": ("40802", "49141", "41162", "41284", "41447"),
}
POLL_BODY_UIDS = {3: "2745", 4: "49233"}
BANK_SIZES = {36: 29, 44: 77}


class ImpulsionExecutionError(RuntimeError):
    def __init__(self, report):
        self.report = report
        self.result = report
        RuntimeError.__init__(self, report["operation"] + ": " + report["status"])


class ImpulsionExecutionCancelled(ImpulsionExecutionError):
    pass


def _snapshot(bank, values):
    if (type(values) is not tuple or len(values) != BANK_SIZES[bank]
            or any(type(value) is not bool for value in values)):
        raise TypeError("Complete immutable Boolean tuple required for bank " + str(bank))
    return values


def execute_impulsion(operation, start_counter, pulse_done, stop_counter,
                      read_local, write_local, publish, wait_seconds, cancelled,
                      observer=None, new_value=True, execution_wait=None):
    """Execute qualified frames with callbacks; no admission gate is implied.

    read_local(bank)->tuple, write_local(bank, ((index,bool),...)),
    publish(name,bank,snapshot), wait_seconds(seconds), cancelled()->exactbool,
    observer(frame_index,source_uid). Counter callbacks take physical number.
    Caller must own authorization/serialization, all retained tasks and gates.

    False NewVal is a callback-free no-op. Poll termination is Done OR i>40:
    at most 42 reads per counter, with requested 1ms wait on every iteration,
    including the final one. This is not a 42ms wall-clock deadline. No source
    physical ACK or native exception/dialog equivalence is claimed.
    """
    if type(operation) is not str or operation not in SUPPORTED_OPERATIONS:
        raise ValueError("Unsupported impulsion operation")
    if type(new_value) is not bool:
        raise TypeError("NewVal requires an exact Boolean")
    callbacks = (start_counter, pulse_done, stop_counter, read_local, write_local,
                 publish, wait_seconds, cancelled)
    if any(not callable(callback) for callback in callbacks):
        raise TypeError("All impulsion callbacks must be callable")
    if observer is not None and not callable(observer):
        raise TypeError("Observer must be callable or None")
    if execution_wait is not None and not callable(execution_wait):
        raise TypeError("Execution wait must be callable or None")
    frames = FRAME_UIDS[operation]
    report = {
        "operation": operation, "status": "NOOP" if not new_value else "EXECUTING",
        "source_vi_sha256": SOURCE_VI_SHA256,
        "source_counter_helper_sha256": SOURCE_COUNTER_HELPER_SHA256,
        "event": 23 if operation.endswith(".start") else 24,
        "source_frame_uids": list(frames), "started_frames": [],
        "completed_frames": [], "remaining_frames": list(frames) if new_value else [],
        "completed": not new_value, "hardware_acknowledged": False,
        "source_error_semantics_reproduced": False,
        "native_timing_equivalence": False, "ownership_retained_by_caller": True,
        "callback_intents": [], "counter_polls": [], "failures": [],
        "restoration_attempts": [], "restoration_failures": [],
        "pending_counter_stops": [], "commanded_running_counters": [],
        "counter_clear_error_boundaries": [],
    }
    if not new_value:
        return report
    current = [None]
    possibly_running = set()
    uncertain_stops = set()

    def failure(kind, exc, number=None):
        row = {"frame_uid": current[0], "operation": kind,
               "error": type(exc).__name__ + ": " + str(exc)}
        if number is not None:
            row["counter"] = number
        report["failures"].append(row)

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise TypeError("Cancellation callback requires an exact Boolean")
        if value:
            raise ImpulsionExecutionCancelled(report)

    def attempt(kind, callback, args, number=None):
        check_cancel()
        try:
            value = callback(*args)
        except Exception as exc:
            failure(kind, exc, number)
            return False, None
        # Record an effect before cancellation can hide its completion.
        report["callback_intents"].append((kind,) + tuple(args))
        check_cancel()
        return True, value

    def clear_boundary(number):
        # A Clear Errors VI is not an NI stop/reset. Do not erase Python errors.
        report["counter_clear_error_boundaries"].append((current[0], number))

    def stop(number):
        uncertain_stops.add(number)
        succeeded, _ = attempt("counter_stop", stop_counter, (number,), number)
        if succeeded:
            uncertain_stops.discard(number)
            possibly_running.discard(number)
        clear_boundary(number)

    def poll_then_stop(number):
        for iteration in range(42):
            ok, done = attempt("counter_pulse_done", pulse_done, (number,), number)
            if ok and type(done) is not bool:
                failure("counter_pulse_done", TypeError("Pulse-done must be an exact Boolean"), number)
                done = False
            if not ok:
                done = False
            report["counter_polls"].append((number, POLL_BODY_UIDS[number], iteration, done))
            attempt("wait_seconds", wait_seconds, (0.001,))
            if done or iteration > 40:
                break
        stop(number)

    def change(bank, changes):
        # The source has a separate local read for each bundle. Do not claim
        # atomicity across banks, or fabricate a snapshot after a failed read.
        ok, values = attempt("local_read", read_local, (bank,))
        if not ok:
            return
        try:
            _snapshot(bank, values)
        except Exception as exc:
            failure("local_read_shape", exc)
            return
        attempt("local_write", write_local, (bank, changes))

    def publish_status():
        # Separate fresh source reads; publication is error-wired DPS->EPS.
        values = {}
        valid = True
        for bank in (36, 44):
            ok, snapshot = attempt("local_read", read_local, (bank,))
            if ok:
                try:
                    values[bank] = _snapshot(bank, snapshot)
                except Exception as exc:
                    failure("publication_snapshot", exc)
                    valid = False
            else:
                valid = False
        if not valid:
            return
        ok, _ = attempt("publish", publish, ("DPS", 36, values[36]))
        if ok:
            attempt("publish", publish, ("EPS", 44, values[44]))

    def restore(numbers):
        for number in sorted(numbers):
            report["restoration_attempts"].append(number)
            uncertain_stops.add(number)
            try:
                stop_counter(number)
            except Exception as exc:
                report["restoration_failures"].append({
                    "counter": number, "error": type(exc).__name__ + ": " + str(exc)})
            else:
                uncertain_stops.discard(number)
                possibly_running.discard(number)

    def final_wait(seconds):
        # The source counter chain has finished. Never sample between polling,
        # stop, configuration or restart calls; uncertain stops remain unsafe.
        if execution_wait is None:
            return wait_seconds(seconds)
        return execution_wait(seconds, not uncertain_stops and not report["failures"],
                              dict(operation=operation, phase="final_status_wait",
                                   source_uid=current[0]))

    aborted = None
    try:
        for index, uid in enumerate(frames):
            current[0] = uid
            check_cancel()
            report["started_frames"].append(uid)
            if observer is not None:
                observer(index, uid)
                check_cancel()
            if operation.endswith(".start"):
                if index == 0:
                    # ACTION is independent of the ordered counter chain.
                    attempt("local_write", write_local, (35, ((-1, True),)))
                    for number in (3, 4):
                        # A raising callback might already have started a task.
                        possibly_running.add(number)
                        attempt("counter_start", start_counter, (number,), number)
                        clear_boundary(number)
                elif index == 1:
                    change(36, ((18, False),))
                    change(44, ((55, False), (52, True)))
                elif index == 2:
                    publish_status()
                else:
                    attempt("wait_seconds", final_wait, (0.1,))
            else:
                if index == 0:
                    attempt("local_write", write_local, (35, ((-1, True),)))
                    poll_then_stop(3)
                elif index == 1:
                    poll_then_stop(4)
                elif index == 2:
                    change(36, ((19, False),))
                    # Source really writes EPS42, not EPS55 (do not "repair").
                    change(44, ((52, False), (42, True)))
                elif index == 3:
                    publish_status()
                else:
                    attempt("wait_seconds", final_wait, (0.1,))
            report["completed_frames"].append(uid)
            report["remaining_frames"] = list(frames[index + 1:])
    except Exception as exc:
        aborted = exc
        if not isinstance(exc, ImpulsionExecutionCancelled):
            failure("execution_interrupted", exc)

    if aborted is not None or report["failures"]:
        if operation.endswith(".start"):
            restore(possibly_running | uncertain_stops)
        elif aborted is not None:
            restore(set((3, 4)))
        report["status"] = "CANCELLED" if isinstance(aborted, ImpulsionExecutionCancelled) else "FAILED"
    else:
        report["status"] = "COMPLETED"
        report["completed"] = True
    report["pending_counter_stops"] = sorted(uncertain_stops)
    report["commanded_running_counters"] = sorted(possibly_running)
    if report["status"] != "COMPLETED":
        error = ImpulsionExecutionCancelled if report["status"] == "CANCELLED" else ImpulsionExecutionError
        raise error(report)
    return report
