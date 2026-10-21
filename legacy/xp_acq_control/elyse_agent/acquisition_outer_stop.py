"""Original seven-phase ACQ outer stop through Python 3.4 callbacks.

No devices, files, processes, network or sleeps are opened by this module.
This is NOT event6 General Arrêt, deinitialization, an electrical emergency
controller, or the separate zero/8 kV shutdown policy. The source tests the
C9 command against strict 6.6, not an HT measurement. Local final flags and
successful callbacks are not physical-OFF acknowledgements.

Same-frame independent native nodes are deliberately serialized as writes,
loops/counters/nested frames, then waits. The 200-decrement bound, cancellation
and fail-closed cleanup are Python policies, not recovered native semantics.
After failure/cancellation only not-yet-attempted counter stops and the HT
supply stop/release may run; cooling-off and final flags are not completed.
An attempted counter stop or HT pulse is never replayed. Unfinished digital
pulses are restored to their preprocedure commanded baseline where possible;
unresolved restoration remains explicit and must retain acquisition ownership.
"""
import math


SOURCE_VI_SHA256 = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
# External review evidence, NOT a bundled clean-checkout dependency. Clean
# tests compare the committed inert plan; native reproduction needs this file.
SOURCE_ARCHIVE = "C:/dev/pyconlyse/legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
SOURCE_ARCHIVE_SHA256 = "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527"
BANK_SHAPES = {9: (10, float), 10: (10, float), 12: (10, float),
               15: (32, bool), 17: (40, bool), 36: (29, bool), 44: (77, bool)}
PULSE_FIELDS = {15: (1, 4, 6, 8, 17, 19), 17: (1, 4)}


def _write(bank, fields):
    return ("write", bank, tuple(sorted(fields)))


def _bools(bank, false=(), true=()):
    return _write(bank, [(i, False) for i in false] + [(i, True) for i in true])


def _phase(uid, *effects):
    return (uid, tuple(sorted(effects, key=repr)))


CONTROLLED_STOP = (
    _phase("60323", ("ht_ramp", "18613", "42212")),
    _phase("51962", _bools(35, true=(-1,)), ("subsequence", (
        _phase("47671", ("counter_poll_stop_clear", 21, 3, "47770", 40, 1),
               _write(50, [(-1, 5.0)])),
        _phase("47989", ("counter_poll_stop_clear", 21, 4, "48062", 40, 1)),
        _phase("48537", ("wait", 1000)),))),
    _phase("43360", ("subsequence", (
        _phase("49114", ("wait", 150), _bools(15, false=(19,)),
               _write(50, [(-1, 4.0)])),
        _phase("49284", _bools(15, true=(19,))),
        _phase("49853", ("wait", 1000)),))),
    _phase("129793", ("subsequence", (
        _phase("128452", _write(50, [(-1, 3.0)]),
               _write(9, [(i, 0.0) for i in (0, 1, 2, 3, 4, 5, 6, 7, 9)]),
               _write(10, [(i, 0.0) for i in (0, 1, 3, 4, 5, 6, 7, 8, 9)])),
        _phase("128743", ("wait", 1000)),
        _phase("128773", _bools(17, false=(9, 11, 15, 17, 21, 23, 25, 27,
                                         29, 31, 32, 33, 34, 35, 36, 37, 38, 39))),
        _phase("129221", ("wait", 1000)),))),
    _phase("1722", ("subsequence", (
        _phase("42424", ("wait", 150), _bools(15, false=(8,)),
               _write(50, [(-1, 2.0)])),
        _phase("42549", _bools(15, true=(8,))),
        _phase("42712", ("wait", 1000)),
        _phase("42763", ("wait", 150), _bools(15, false=(17,))),
        _phase("42895", _bools(15, true=(17,))),
        _phase("43136", ("wait", 1000)),
        _phase("43197", ("wait", 150), _bools(15, false=(6,))),
        _phase("43264", _bools(15, true=(6,))),
        _phase("43315", ("wait", 1000)),
        _phase("43345", ("wait", 150), _bools(15, false=(4,))),
        _phase("43418", _bools(15, true=(4,))),
        _phase("43468", ("wait", 2000)),
        _phase("43520", ("wait", 150), _bools(15, false=(1,))),
        _phase("43589", _bools(15, true=(1,))),
        _phase("43933", ("wait", 1000)),))),
    _phase("52159", ("subsequence", (
        _phase("54293", ("wait", 150), _bools(17, false=(1,)),
               _write(50, [(-1, 1.0)])),
        _phase("54391", _bools(17, true=(1,))),
        _phase("54440", ("wait", 400)),
        _phase("54470", ("wait", 150), _bools(17, false=(4,))),
        _phase("54530", ("wait", 150), _bools(17, true=(4,))),
        _phase("54590", _bools(36, false=(1,)),
               _bools(44, false=(1, 2, 3), true=(5,))),
        _phase("58827", _bools(36, false=(1,)),
               _bools(44, false=(1, 2, 3), true=(5,))),
        _phase("54731", ("wait", 100)),))),
    _phase("64826", ("wait", 1000), _bools(46, true=(-1,)),
           _bools(47, false=(-1,)), _write(50, [(-1, 0.0)])),
)


class OuterStopExecutionError(RuntimeError):
    def __init__(self, report):
        self.report = report
        RuntimeError.__init__(self, "outer controlled stop: " + report["status"])


class OuterStopExecutionCancelled(OuterStopExecutionError):
    pass


def _snapshot(bank, value):
    size, kind = BANK_SHAPES[bank]
    if (type(value) is not tuple or len(value) != size
            or any(type(item) is not kind for item in value)):
        raise ValueError("Complete immutable typed bank required: " + str(bank))
    if kind is float and not all(math.isfinite(item) for item in value):
        raise ValueError("Finite DBL bank required: " + str(bank))
    return value


def execute_outer_stop(read_local, write_local, pulse_done, stop_counter,
                       wait_seconds, cancelled, observer=None,
                       max_ramp_steps=200):
    """Execute one original outer sequence under the single NI/local owner.

    read_local(bank) -> fresh complete immutable tuple. write_local(bank,
    ((index,value),...)) patches only named fields; scalars use index -1.
    pulse_done(counter3_or4) -> exact bool reads CO.PulseDone. stop_counter(n)
    performs the owned task's StopTask, not release/recreate. Source error-clear
    is recorded conceptually, not a fabricated driver call or successful ACK.
    observer(frame_index, source_uid) runs on entry, in preorder. Completed
    frame UIDs are recorded in postorder. No callback is automatically retried.

    Failure/cancellation raises with .report after bounded cleanup attempts.
    The owner must retain NI tasks whenever effects/restorations are uncertain.
    """
    if any(not callable(fn) for fn in (read_local, write_local, pulse_done,
                                       stop_counter, wait_seconds, cancelled)):
        raise TypeError("All outer-stop callbacks must be callable")
    if observer is not None and not callable(observer):
        raise TypeError("observer must be callable or None")
    if type(max_ramp_steps) is not int or not 1 <= max_ramp_steps <= 100000:
        raise ValueError("Positive bounded max_ramp_steps required")
    report = dict(operation="outer.controlled_stop", status="EXECUTING",
                  source_vi_sha256=SOURCE_VI_SHA256,
                  source_archive=SOURCE_ARCHIVE,
                  source_archive_sha256=SOURCE_ARCHIVE_SHA256,
                  started_frames=[], completed_frames=[], phase_uid=None,
                  current_uid=None, failures=[], restoration_failures=[],
                  pending_output_restorations=[], restored_fields=[],
                  local_write_attempts=0, ramp_iterations=0,
                  ramp_decrements=0, counter_poll_counts={3: 0, 4: 0},
                  counter_stop_attempts=[], counter_stop_completed=[],
                  conceptual_error_clears=[], ht_supply_stop_complete=False,
                  ht_supply_assert_completed=False,
                  ht_supply_dwell_completed=False,
                  ht_supply_release_completed=False,
                  cancelled=False, hardware_acknowledged=False,
                  source_frame_effects_ordered=False,
                  adapter_schedule="writes_then_loops_counters_nested_then_waits",
                  failure_policy="abort_then_counter_and_ht_stop_then_restore",
                  ramp_bound_is_python_policy=True,
                  source_error_semantics_reproduced=False)
    pending, baseline, counter_attempted = {}, {}, set()
    frame_index = [0]
    ht_started, ht_release_attempted = [False], [False]

    def failure(kind, error, bank=None, cleanup=False):
        item = dict(kind=kind, source_uid=report["current_uid"],
                    phase_uid=report["phase_uid"], error_type=type(error).__name__,
                    error=str(error), cleanup=cleanup)
        if bank is not None:
            item["bank"] = bank
        report["failures"].append(item)

    def sync_pending():
        report["pending_output_restorations"] = [
            (bank, field, value) for (bank, field), value in sorted(pending.items())]

    def sync_ht_stop():
        report["ht_supply_stop_complete"] = all(report[key] for key in (
            "ht_supply_assert_completed", "ht_supply_dwell_completed",
            "ht_supply_release_completed"))

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise TypeError("Cancellation callback must return exact bool")
        if value:
            report["cancelled"] = True
            raise OuterStopExecutionCancelled(report)

    def call(fn, *args):
        check_cancel()
        value = fn(*args)
        check_cancel()
        return value

    def read(bank, cleanup=False):
        value = _snapshot(bank, read_local(bank) if cleanup else call(read_local, bank))
        if bank in PULSE_FIELDS and bank not in baseline:
            baseline[bank] = value
        return value

    def write(bank, fields, cleanup=False, already_read=False):
        fields = tuple(fields)
        if bank in BANK_SHAPES and not already_read:
            read(bank, cleanup)
        if bank in PULSE_FIELDS:
            for index, value in fields:
                if index in PULSE_FIELDS[bank] and value is False:
                    pending[(bank, index)] = baseline[bank][index]
        if bank == 15 and (19, False) in fields:
            ht_started[0] = True
        if bank == 15 and (19, True) in fields:
            ht_release_attempted[0] = True
        report["local_write_attempts"] += 1
        if cleanup:
            write_local(bank, fields)
        else:
            # Register uncertain writes before callback: it may apply then fail.
            check_cancel()
            write_local(bank, fields)
        if bank in PULSE_FIELDS:
            for index, value in fields:
                if index in PULSE_FIELDS[bank] and value is True:
                    pending.pop((bank, index), None)
        if bank == 15 and (19, False) in fields:
            report["ht_supply_assert_completed"] = True
        if bank == 15 and (19, True) in fields:
            report["ht_supply_release_completed"] = True
        sync_ht_stop()
        sync_pending()
        if not cleanup:
            check_cancel()

    def stop(number, cleanup=False):
        if number in counter_attempted:
            return
        # Mark before callback: neither uncertain nor failed stops are retried.
        counter_attempted.add(number)
        report["counter_stop_attempts"].append(number)
        if cleanup:
            stop_counter(number)
        else:
            check_cancel()
            stop_counter(number)
        report["counter_stop_completed"].append(number)
        report["conceptual_error_clears"].append(number)
        if not cleanup:
            check_cancel()

    def ramp():
        for iteration in range(max_ramp_steps + 1):
            check_cancel()
            checked = read(12)[0]
            report["ramp_iterations"] += 1
            write(50, ((-1, 6.0),))
            write(48, ((-1, checked),))
            if checked < 6.6:
                return
            if iteration == max_ramp_steps:
                raise RuntimeError("Python HT ramp decrement bound reached")
            # Separate fresh check and bundle reads, never substitute physical
            # voltage or reuse the initial bank. write patches only field0.
            read(12)
            write(12, ((0, checked - 0.1),), already_read=True)
            report["ramp_decrements"] += 1
            call(wait_seconds, 0.5)

    def counter(number):
        for iteration in range(42):
            done = call(pulse_done, number)
            if type(done) is not bool:
                raise TypeError("CO.PulseDone must return exact bool")
            report["counter_poll_counts"][number] += 1
            # The 1ms Wait executes even on the terminating iteration. It is
            # not a wall-clock bound on a property-node/driver call.
            call(wait_seconds, 0.001)
            if done or iteration > 40:
                break
        stop(number)

    def frames(sequence):
        for uid, effects in sequence:
            check_cancel()
            report["current_uid"] = uid
            report["started_frames"].append(uid)
            index = frame_index[0]
            frame_index[0] += 1
            if observer is not None:
                call(observer, index, uid)
            for kind in ("write", "ht_ramp", "counter_poll_stop_clear",
                         "subsequence", "wait"):
                for effect in effects:
                    if effect[0] != kind:
                        continue
                    check_cancel()
                    if kind == "write":
                        write(effect[1], effect[2])
                    elif kind == "ht_ramp":
                        ramp()
                    elif kind == "counter_poll_stop_clear":
                        counter(effect[2])
                    elif kind == "subsequence":
                        frames(effect[1])
                        report["current_uid"] = uid
                    else:
                        call(wait_seconds, effect[1] / 1000.0)
                        if uid == "49114":
                            report["ht_supply_dwell_completed"] = True
                            sync_ht_stop()
            report["completed_frames"].append(uid)

    def cleanup():
        for number in (3, 4):
            if number not in counter_attempted:
                try:
                    stop(number, True)
                except Exception as error:
                    failure("counter_stop", error, cleanup=True)
        if not report["ht_supply_stop_complete"]:
            # Complete an interrupted pulse only once; do not replay it.
            if not ht_started[0]:
                try:
                    write(15, ((19, False),), True)
                except Exception as error:
                    failure("ht_supply_assert", error, 15, True)
            if ht_started[0] and not ht_release_attempted[0]:
                try:
                    wait_seconds(0.150)
                    report["ht_supply_dwell_completed"] = True
                    sync_ht_stop()
                except Exception as error:
                    failure("ht_supply_dwell", error, cleanup=True)
                try:
                    write(15, ((19, True),), True)
                except Exception as error:
                    failure("ht_supply_release", error, 15, True)
        for bank in sorted(set(bank for bank, field in pending)):
            changes = tuple((field, value) for (b, field), value in
                            sorted(pending.items()) if b == bank)
            try:
                # Recovery patches the original commanded baseline, not a
                # second stop pulse or assertion of physical-OFF.
                write_local(bank, changes)
                report["restored_fields"].extend((bank, field) for field, value in changes)
                for field, value in changes:
                    pending.pop((bank, field), None)
            except Exception as error:
                report["restoration_failures"].append(dict(
                    bank=bank, changes=changes, error_type=type(error).__name__,
                    error=str(error)))
        sync_pending()

    try:
        # Validate typed source banks before ordinary effects. Every RMW is
        # still refreshed independently at its actual source effect.
        for bank in sorted(BANK_SHAPES):
            read(bank)
        for phase in CONTROLLED_STOP:
            report["phase_uid"] = phase[0]
            frames((phase,))
        check_cancel()
    except Exception as error:
        if isinstance(error, OuterStopExecutionCancelled):
            report["cancelled"] = True
        else:
            failure("execution", error)
        cleanup()
        report["status"] = "CANCELLED" if report["cancelled"] else "PARTIAL_FAILURE"
        exception = OuterStopExecutionCancelled if report["cancelled"] else OuterStopExecutionError
        raise exception(report)
    sync_pending()
    report["status"] = "COMPLETED"
    return report
