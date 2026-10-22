"""Python 3.4 callback executor for the seven saved cooling-trip frames.

Import performs no I/O. Callbacks are supplied by the single acquisition owner.
The default disabled gate is independent of the raw Boolean expression. The
nonempty Diagram Disable 14478 arm was seen enabled in the reviewed LabVIEW
20.0f1 import, NOT qualified in the deployed LabVIEW 2012 application.

Frame boundaries and separate local reads are preserved. Independent nodes in
one native frame have no ordering wire; this adapter deliberately uses reads,
writes, publication, then wait. Requested waits are not electrical pulse-width
or fault-response guarantees. Callback completion is not a hardware ACK.

Fail-fast cancellation/exception and restoration of an unfinished active-low
command are explicit Python failure policy, NOT proven native error semantics.
This branch does not stop Chauffage/PREMA/Focales, infer water polarity, latch a
trip, or automatically restart any stage.
"""


SOURCE_VI_SHA256 = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
DPS_URI = "ni.var.psp://10.20.30.2/SUPERVISION/DPS"
FRAME_UIDS = ("10221", "13119", "14187", "20056", "30644", "31857", "39347")
BANK_SIZES = {17: 40, 36: 29, 44: 77}


class CoolingTripError(RuntimeError):
    """Execution failed; result retains partial effects and cleanup failures."""

    def __init__(self, message, result, cause=None):
        RuntimeError.__init__(self, message)
        self.result = result
        self.cause = cause


class CoolingTripCancelled(CoolingTripError):
    """Owner cancellation interrupted the callback sequence."""


def _bool_snapshot(values, size, label):
    if (type(values) is not tuple or len(values) != size
            or any(type(value) is not bool for value in values)):
        raise TypeError(label + " requires a full immutable Boolean tuple")
    return values


def cooling_trip_predicate(c4_snapshot, c3_snapshot):
    """Raw source expression; this is not a heating or HT safety permission."""
    _bool_snapshot(c4_snapshot, 64, "C4_IN_DIO96")
    _bool_snapshot(c3_snapshot, 56, "C3_IN_DIO96")
    return ((c4_snapshot[19] or c4_snapshot[38])
            and (not c3_snapshot[0] or not c3_snapshot[6]))


def _source_intent():
    return {
        "source_vi_sha256": SOURCE_VI_SHA256,
        "frame_uids": list(FRAME_UIDS),
        "requested_wait_ms": [150, None, 400, 150, None, None, 100],
        "c3_output_assignments": [(0, 1, False), (1, 1, True),
                                  (3, 4, False), (4, 4, True)],
        "eps_assignments": [(1, True), (2, False), (3, False), (5, True)],
        "dps_assignments": [(1, False)],
        "publication_uri": DPS_URI,
        "false_arm_empty": True,
        "source_within_frame_unordered": True,
        "native_enabled_arm_seen": "LabVIEW 20.0f1 import only",
        "deployed_lv2012_arm_qualified": False,
    }


def execute_cooling_trip(c4_snapshot, c3_snapshot, read_local, write_local,
                         publish, wait_seconds, cancelled,
                         frame_observer=None, enabled_arm=False, execution_wait=None):
    """Execute the qualified True arm synchronously using injected callbacks.

    read_local(bank) returns a full immutable Boolean tuple. write_local(bank,
    changes) receives tuple pairs; bank 35 is write-only ACTION, field -1.
    publish(name, bank, snapshot) receives frame 6's *fresh* DPS read. The owner
    provides cancellation and interruptible waits; this module opens no device.
    frame_observer(index, source_uid) is optional and called on frame entry.

    Every argument is validated before any callback. A disabled gate or false
    predicate invokes none, including cancellation/observer callbacks. Failures
    raise CoolingTripError (CoolingTripCancelled for cancellation); result is
    available on the exception and never claims physical shutdown completion.
    """
    if type(enabled_arm) is not bool:
        raise TypeError("enabled_arm requires an explicit Boolean qualification")
    predicate = cooling_trip_predicate(c4_snapshot, c3_snapshot)
    for name, callback in (("read_local", read_local), ("write_local", write_local),
                           ("publish", publish), ("wait_seconds", wait_seconds),
                           ("cancelled", cancelled)):
        if not callable(callback):
            raise TypeError(name + " callback required")
    if frame_observer is not None and not callable(frame_observer):
        raise TypeError("frame_observer requires a callable or None")
    if execution_wait is not None and not callable(execution_wait):
        raise TypeError("execution_wait requires a callable or None")

    result = {
        "enabled_arm": enabled_arm,
        "raw_predicate": predicate,
        "status": "disabled" if not enabled_arm else "false_arm",
        "completed": False,
        "callback_execution": False,
        "hardware_acknowledged": False,
        "source_error_semantics_reproduced": False,
        "adapter_order": "frame reads, writes, publication, wait",
        "source_intent": _source_intent(),
        "started_frame_uids": [],
        "completed_frame_uids": [],
        "remaining_frame_uids": list(FRAME_UIDS),
        "local_reads": [],
        "completed_callback_intents": [],
        "restoration_attempts": [],
        "cleanup_failures": [],
        "pending_output_restorations": [],
        "failure": None,
    }
    if not enabled_arm or not predicate:
        # No source frame was reached; this is not an evaluated successful trip.
        result["remaining_frame_uids"] = []
        return result

    pending = {}
    current_frame = [None]

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise TypeError("cancelled callback must return an explicit Boolean")
        if value:
            raise CoolingTripCancelled("Cooling-trip execution cancelled", result)

    def call(callback, *args):
        check_cancel()
        value = callback(*args)
        check_cancel()
        return value

    def read(bank, uid):
        values = call(read_local, bank)
        _bool_snapshot(values, BANK_SIZES[bank], "local bank " + str(bank))
        result["local_reads"].append((current_frame[0], uid, bank, values))
        return values

    def write(bank, changes):
        call(write_local, bank, changes)
        result["completed_callback_intents"].append(("write", bank, changes))

    def output(index, value, uid):
        snapshot = read(17, uid)
        if not value and index not in pending:
            # Register before callback: an exception may follow a partial write.
            pending[index] = snapshot[index]
        write(17, ((index, value),))
        if value:
            pending.pop(index, None)

    def wait(milliseconds):
        if execution_wait is None:
            call(wait_seconds, milliseconds / 1000.0)
        else:
            call(execution_wait, milliseconds / 1000.0, not pending,
                 dict(operation="cooling.trip", phase="source_wait",
                      frame=current_frame[0], source_uid=FRAME_UIDS[current_frame[0]]))
        result["completed_callback_intents"].append(("wait_ms", milliseconds))

    def cleanup():
        # Cancellation must not suppress restoration. Preserve every failure;
        # one failed restore must not hide the original cause or skip another.
        for index, baseline in sorted(list(pending.items())):
            attempt = {"bank": 17, "index": index, "baseline": baseline,
                       "read_succeeded": False, "write_succeeded": False}
            result["restoration_attempts"].append(attempt)
            try:
                values = read_local(17)
                _bool_snapshot(values, 40, "restore C3_OUT_DIO96")
                attempt["read_succeeded"] = True
            except Exception as exc:
                result["cleanup_failures"].append({
                    "operation": "restore_read", "bank": 17, "index": index,
                    "error": type(exc).__name__ + ": " + str(exc)})
            try:
                # Field-patch callback preserves unrelated fields even if the
                # diagnostic fresh read failed. Only a known baseline is sent.
                write_local(17, ((index, baseline),))
                attempt["write_succeeded"] = True
                pending.pop(index, None)
            except Exception as exc:
                result["cleanup_failures"].append({
                    "operation": "restore_write", "bank": 17, "index": index,
                    "error": type(exc).__name__ + ": " + str(exc)})
        result["pending_output_restorations"] = sorted(pending.items())

    result["callback_execution"] = True
    try:
        for index, uid in enumerate(FRAME_UIDS):
            current_frame[0] = index
            check_cancel()
            result["started_frame_uids"].append(uid)
            if frame_observer is not None:
                call(frame_observer, index, uid)
            if index == 0:
                output(1, False, "10431")
                write(35, ((-1, True),))
                wait(150)
            elif index == 1:
                output(1, True, "13466")
            elif index == 2:
                wait(400)
            elif index == 3:
                output(4, False, "22661")
                wait(150)
            elif index == 4:
                output(4, True, "30986")
            elif index == 5:
                # Separate read nodes in the same native frame; no atomicity.
                read(44, "39289")
                read(36, "39313")
                write(44, ((1, True), (2, False), (3, False), (5, True)))
                write(36, ((1, False),))
            else:
                snapshot = read(36, "39444")
                call(publish, "DPS", 36, snapshot)
                result["completed_callback_intents"].append(("publish", "DPS", 36, snapshot))
                wait(100)
            result["completed_frame_uids"].append(uid)
            result["remaining_frame_uids"] = list(FRAME_UIDS[index + 1:])
        result["status"] = "completed"
        result["completed"] = True
        return result
    except Exception as exc:
        was_cancelled = isinstance(exc, CoolingTripCancelled)
        result["status"] = "cancelled" if was_cancelled else "failed"
        result["failure"] = {"frame_index": current_frame[0],
                             "frame_uid": FRAME_UIDS[current_frame[0]],
                             "error": type(exc).__name__ + ": " + str(exc)}
        cleanup()
        error_type = CoolingTripCancelled if was_cancelled else CoolingTripError
        raise error_type("Cooling-trip " + result["status"], result, exc)
