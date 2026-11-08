"""Callback-based execution of fourteen Acquisition procedures (Python 3.4).

No driver is imported here. Callers own local banks, output serialization and
authorization. The adapter serializes same-frame independent effects as local
writes, nested/helper effects, publications, then waits. This is NOT a claim
that LabVIEW's concurrent nodes, independent DAQ writer or PSP publication have
identical timing.

Each frame obtains independent full local snapshots before its effects. A
publication uses that frame-entry snapshot, never an invented post-write value.
Literal EPS assignments report software intent, not physical acknowledgement.
HT supply commands here are Boolean source pulses, not voltage ramps or proof
of physical high voltage. Their DPS -> EPS -> C4_OUT publications are source
error-wired: a failed publication short-circuits later publications in that
chain. A stop may then attempt its later frames under the Python policy below.
The Focales OFF container's nested 500 ms and independent outer 150 ms waits
are serialized (650 ms); this explicit Python schedule is not native timing
equivalence. Helper callbacks are required; normal return means only callback
completion, not inferred native or physical acknowledgement. Original error-
dialog Continue/Stop behavior is not reproduced by these Python policies.

Python failure policy (not a recovered VI property): a failed start/reset stops
immediately; stop procedures attempt all remaining literal source effects and
aggregate errors. Cancellation or a failed output write restores any in-flight
DO pulse to its preprocedure commanded baseline, including a write that may
have applied before raising. Successful completed pulses are not rolled back.
Neither error handling nor cancellation deinitializes resources.
"""
from .acquisition_stage_model import BANK_SHAPES, load_model


SUPPORTED_OPERATIONS = (
    "cooling.start", "cooling.stop", "chauffage.start", "chauffage.stop",
    "prema.start", "prema.stop", "relays_ht.start", "relays_ht.stop",
    "modulator.reset", "alimentation_ht.start", "alimentation_ht.stop",
    "alimentation_ht.reset",
    "focales.start", "focales.stop",
)
OUTPUT_BANKS = (15, 17)


class StageExecutionError(RuntimeError):
    def __init__(self, report):
        self.report = report
        RuntimeError.__init__(self, "{0}: {1}".format(
            report["operation"], report["status"]))


class StageExecutionCancelled(StageExecutionError):
    pass


def _snapshot(bank, value):
    if bank == 35:
        if type(value) is not bool:
            raise ValueError("Bank 35 requires a Boolean local snapshot")
        return value
    if (type(value) is not tuple or len(value) != BANK_SHAPES[bank]
            or any(type(item) is not bool for item in value)):
        raise ValueError("Complete Boolean tuple required for bank " + str(bank))
    return value


def _validate_plan(frames, operation):
    """Validate the entire plan before any callback can produce effects."""
    if not isinstance(frames, list) or not frames:
        raise ValueError("Nonempty ordered stage plan required")
    banks, uids, last_writes, helpers = set(), set(), {}, set()

    def validate_frames(sequence, depth=0):
        if not isinstance(sequence, list) or not sequence or depth > 16:
            raise ValueError("Nonempty bounded ordered source frames required")
        for frame in sequence:
            validate_frame(frame, depth)

    def validate_frame(frame, depth):
        if not isinstance(frame, (tuple, list)) or len(frame) != 2:
            raise ValueError("Invalid source frame")
        uid, effects = frame
        if (not isinstance(uid, str) or not uid.isdigit() or uid in uids
                or not isinstance(effects, list)):
            raise ValueError("Invalid source frame identity/effects")
        uids.add(uid)
        for effect_index, effect in enumerate(effects):
            if not isinstance(effect, (tuple, list)) or not effect:
                raise ValueError("Invalid source effect")
            kind = effect[0]
            if kind == "write":
                if len(effect) != 3:
                    raise ValueError("Invalid local write")
                _, bank, changes = effect
                if type(bank) is not int or bank not in (15, 17, 35, 36, 44):
                    raise ValueError("Unqualified local bank")
                if not isinstance(changes, (tuple, list)) or not changes:
                    raise ValueError("Explicit literal local changes required")
                seen = set()
                for pair in changes:
                    if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                        raise ValueError("Invalid literal local field")
                    index, value = pair
                    if (type(index) is not int or type(value) is not bool
                            or index in seen or (bank == 35 and
                            (index != -1 or value is not True)) or
                            (bank != 35 and not 0 <= index < BANK_SHAPES[bank])):
                        raise ValueError("Invalid local field/type")
                    seen.add(index)
                    if bank in OUTPUT_BANKS:
                        last_writes[(bank, index)] = (uid, effect_index)
                if bank != 35:
                    # ACTION is a literal scalar assignment, not a local
                    # read/merge. No source-qualified initial value is known.
                    banks.add(bank)
            elif kind == "wait":
                if (len(effect) != 2 or type(effect[1]) is not int
                        or not 0 < effect[1] <= 29000):
                    raise ValueError("Invalid source wait")
            elif kind == "publish":
                if len(effect) != 2 or not isinstance(effect[1], (list, tuple)):
                    raise ValueError("Invalid source publication")
                for pair in effect[1]:
                    if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                            or tuple(pair) not in (("DPS", 36), ("EPS", 44),
                                                   ("C4_OUT_DIO96", 15))):
                        raise ValueError("Unqualified source publication")
                    banks.add(pair[1])
            elif kind == "subsequence":
                if len(effect) != 2 or operation not in ("focales.start", "focales.stop"):
                    raise ValueError("Unqualified nested source frames")
                validate_frames(effect[1], depth + 1)
            elif kind == "call_handle_error":
                required = {"focales.start": "1_Focales ON.vi",
                            "focales.stop": "1_Focales OFF.vi"}.get(operation)
                if len(effect) != 2 or effect[1] != required or required is None:
                    raise ValueError("Unqualified source helper")
                helpers.add(required)
            else:
                # Focales/helper calls and nested procedures must never be
                # partly executed merely because their first frames look safe.
                raise ValueError("Unsupported stage effect: " + str(kind))

    validate_frames(frames)
    # Determine releases in the actual selected schedule, not arbitrary
    # same-frame source effect list order. Container writes precede children.
    last_writes.clear()
    def collect_releases(sequence):
        for uid, effects in sequence:
            for index, effect in enumerate(effects):
                if effect[0] == "write" and effect[1] in OUTPUT_BANKS:
                    for field, value in effect[2]:
                        last_writes[(effect[1], field)] = (uid, index)
            for effect in effects:
                if effect[0] == "subsequence":
                    collect_releases(effect[1])
    collect_releases(frames)
    return sorted(banks), last_writes, helpers


def execute_stage(operation, read_local, write_local, publish, wait_seconds,
                  cancelled, frame_observer=None, operator_confirmed=False,
                  new_value=True, focal_helper=None):
    """Execute one source path through injected local callbacks.

    read_local(bank) -> complete tuple of bool, or scalar bool for bank 35.
    write_local(bank, ((field, bool), ...)) must merge only the named fields.
    publish(name, bank, tuple_snapshot) observes an independent frame-entry read.
    wait_seconds(seconds), cancelled() -> bool, observer(frame_index, source_uid).
    focal_helper(helper_name) is mandatory only for a True Focales request.

    Confirmation is explicit even for a False NewVal no-op. Callback shapes,
    the complete pinned source plan and all initial bank snapshots are checked
    before any local write/publication/wait. A return never means hardware ACK.
    """
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError("Unsupported stage operation")
    if operator_confirmed is not True:
        raise ValueError("Explicit local stage confirmation required")
    if type(new_value) is not bool:
        raise ValueError("Explicit Boolean NewVal required")
    callbacks = (read_local, write_local, publish, wait_seconds, cancelled)
    if any(not callable(callback) for callback in callbacks):
        raise ValueError("All stage callbacks must be callable")
    if frame_observer is not None and not callable(frame_observer):
        raise ValueError("Frame observer must be callable or None")
    model = load_model()
    # Validate the True source plan even if this event is a False no-op.
    frames = model.plan(operation, True)
    banks, last_writes, required_helpers = _validate_plan(frames, operation)
    report = dict(operation=operation, status="NOOP" if not new_value else "EXECUTING",
                  completed_frames=[], failures=[], restoration_failures=[],
                  restored_fields=[], pending_output_restorations=[],
                  local_write_attempts=0,
                  helper_attempts=[], frame_observer_order="preorder",
                  completed_frames_order="completion_postorder",
                  hardware_acknowledged=False, source_frame_effects_ordered=False,
                  adapter_schedule=("writes_then_nested_or_helper_then_publish_then_wait"
                                    if required_helpers else "writes_then_publish_then_wait"),
                  failure_policy="best_effort_stop" if operation.endswith(".stop")
                  else "abort_start_or_reset", cancelled=False)
    if not new_value:
        return report
    if required_helpers and not callable(focal_helper):
        raise ValueError("Explicit Focales helper callback required before effects")
    baseline = {bank: _snapshot(bank, read_local(bank)) for bank in banks}
    pending = set()
    best_effort = operation.endswith(".stop")

    def sync_pending():
        # This is FINAL outstanding recovery state, unlike the historical
        # restoration_failures list. A later successful source release may
        # clear a pulse even after an earlier restoration attempt failed.
        report["pending_output_restorations"] = [
            (bank, index, baseline[bank][index]) for bank, index in sorted(pending)]

    def failure(phase, frame_index, uid, error, bank=None):
        item = dict(phase=phase, frame_index=frame_index, source_uid=uid,
                    error_type=type(error).__name__, error=str(error))
        if bank is not None:
            item["bank"] = bank
        report["failures"].append(item)

    def restore():
        # Track before callback invocation: an output adapter may apply a
        # partial write and only then raise. Restoration failure stays visible.
        for bank in sorted(set(bank for bank, index in pending)):
            changes = tuple((index, baseline[bank][index]) for b, index in
                            sorted(pending) if b == bank)
            try:
                write_local(bank, changes)
                report["restored_fields"].extend((bank, index) for index, value in changes)
                pending.difference_update((bank, index) for index, value in changes)
            except Exception as error:
                report["restoration_failures"].append(dict(
                    bank=bank, changes=changes, error_type=type(error).__name__,
                    error=str(error)))
        sync_pending()

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise ValueError("Cancellation callback must return Boolean")
        if value:
            report["cancelled"] = True
            report["status"] = "CANCELLED"
            restore()
            raise StageExecutionCancelled(report)

    next_frame = [0]
    def execute_frames(sequence):
        sequence_failed = False
        for uid, effects in sequence:
            frame_index = next_frame[0]
            next_frame[0] += 1
            check_cancel()
            frame_failed = False
            if frame_observer is not None:
                try:
                    frame_observer(frame_index, uid)
                except Exception as error:
                    failure("observer", frame_index, uid, error)
                    frame_failed = True
                    if not best_effort:
                        raise
            frame_banks = set()
            for effect in effects:
                if effect[0] == "write" and effect[1] != 35:
                    frame_banks.add(effect[1])
                elif effect[0] == "publish":
                    frame_banks.update(bank for name, bank in effect[1])
            entry = {}
            for bank in sorted(frame_banks):
                try:
                    entry[bank] = _snapshot(bank, read_local(bank))
                except Exception as error:
                    failure("read", frame_index, uid, error, bank)
                    frame_failed = True
                    if not best_effort:
                        raise
            # Frame list order is evidence for frames only; same-frame nodes
            # are independent. This deterministic schedule preserves a pulse
            # dwell and deliberately does not assert native concurrent timing.
            for kind in ("write", "subsequence", "call_handle_error", "publish", "wait"):
                for effect_index, effect in enumerate(effects):
                    if effect[0] != kind:
                        continue
                    check_cancel()
                    if kind == "subsequence":
                        child_failed = execute_frames(effect[1])
                        frame_failed = frame_failed or child_failed
                        continue
                    current_publication = None
                    helper_attempt = None
                    try:
                        if kind == "write":
                            _, bank, fields = effect
                            changes = tuple(tuple(pair) for pair in fields)
                            if bank in OUTPUT_BANKS:
                                pending.update((bank, index) for index, value in changes)
                            report["local_write_attempts"] += 1
                            write_local(bank, changes)
                            if bank in OUTPUT_BANKS:
                                for index, value in changes:
                                    if last_writes[(bank, index)] == (uid, effect_index):
                                        pending.discard((bank, index))
                        elif kind == "call_handle_error":
                            helper_attempt = dict(helper=effect[1], source_uid=uid,
                                                  source_error_policy=kind,
                                                  status="CALLBACK_STARTED")
                            report["helper_attempts"].append(helper_attempt)
                            focal_helper(effect[1])
                            helper_attempt["status"] = "CALLBACK_COMPLETED"
                            check_cancel()
                        elif kind == "publish":
                            for name, bank in effect[1]:
                                current_publication = (name, bank)
                                check_cancel()
                                if bank not in entry:
                                    raise ValueError("Publication frame-entry read unavailable")
                                publish(name, bank, entry[bank])
                        else:
                            wait_seconds(effect[1] / 1000.0)
                    except StageExecutionCancelled:
                        raise
                    except Exception as error:
                        failure(kind, frame_index, uid, error,
                                effect[1] if kind == "write" else
                                current_publication[1] if current_publication else None)
                        if current_publication is not None:
                            report["failures"][-1]["publication"] = current_publication[0]
                        if helper_attempt is not None:
                            helper_attempt["status"] = "FAILED"
                            helper_attempt["error_type"] = type(error).__name__
                            helper_attempt["error"] = str(error)
                            report["failures"][-1]["helper"] = effect[1]
                            # Cancellation takes precedence over best-effort
                            # OFF continuation when an unquiesced helper fails.
                            check_cancel()
                        frame_failed = True
                        if kind == "write" and effect[1] in OUTPUT_BANKS:
                            restore()
                        if not best_effort:
                            raise
            if not frame_failed:
                report["completed_frames"].append(uid)
            sequence_failed = sequence_failed or frame_failed
        return sequence_failed

    try:
        execute_frames(frames)
        check_cancel()
    except StageExecutionCancelled:
        raise
    except Exception as error:
        if not report["failures"]:
            failure("execution", None, None, error)
        restore()
        report["status"] = "PARTIAL_FAILURE"
        raise StageExecutionError(report)
    if report["failures"] or report["restoration_failures"]:
        restore()
        report["status"] = "PARTIAL_FAILURE"
        raise StageExecutionError(report)
    sync_pending()
    report["status"] = "COMPLETED"
    return report
