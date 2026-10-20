"""Injected Python 3.4 executor for the saved C10 NI6602 timing path.

No driver, process, clock or transport is opened. An explicit caller-owned
33-DBL image supplies the selector and timings. Only integer selectors 1..16
have a proved mapping: paired selectors select C10 ctr0..7, not C11. The
helper reads CO.PulseDone, requests 1ms per iteration (including final), and
exits Done OR i>20. It then stops, crosses Clear Errors, writes initial/low/
high ticks, and starts the same retained counter. DBL*20 -> saturating I32
(ties to even) -> U32 preserves the original conversion, not driver permits.

The caller subsequently resets selector32 on a NEW image and publishes yet
another NEW image. These are not an atomic transaction or a compare/exchange;
changes between the three reads are observable and the saved reset can consume
a newer selector. The caller must serialize competing Python modifications.

Python policy, not native error-cluster/dialog equivalence: callbacks must
complete normally. An exception/cancellation aborts later steps; no automatic
stop, start, property rewrite, selector consumption, publication or rollback is
replayed. A raising write may already have applied. Reports retain uncertainty
and ownership so the backend cannot silently close/reopen or authorize energy.
The original Clear Errors and Simple Error Handler boundaries are recorded,
not emulated by clearing Python exceptions or inventing a Continue response.
"""

import math


SOURCE_VI_SHA256 = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
SOURCE_HELPER_SHA256 = "4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211"
BANK_NAME = "C1011NI6602"
BANK_LOCAL = 39
BANK_SIZE = 33
SELECTOR_INDEX = 32
PUBLICATION_URI = "ni.var.psp://10.20.30.2/SUPERVISION/C1011NI6602"
POLL_LIMIT_INDEX = 20
POLL_UID = "3202"
WAIT_UID = "3194"
PROPERTY_CODES = (664, 4465, 4457)
HELPER_UIDS = ("3202", "3194", "2976", "309", "3083", "3032")
CALLER_FRAME_UIDS = ("23641", "22979", "1507")
CALLER_UIDS = {
    "dispatch_read": "44855", "guard_case": "23199",
    "helper": "23634", "simple_error_handler_boundary": "22439",
    "reset_read": "23233", "selector_reset": "23248",
    "publication_read": "5036", "publication": "21449",
}


class CounterTimingError(RuntimeError):
    def __init__(self, report):
        self.report = report
        self.result = report
        RuntimeError.__init__(self, report["operation"] + ": " + report["status"])


class CounterTimingCancelled(CounterTimingError):
    pass


class _CancelledSignal(Exception):
    pass


def validate_counter_bank(snapshot):
    """Require an explicit immutable finite 33-DBL image, without coercion.

    Rejection of nonfinite or non-DBL inputs is Python policy. It must not be
    described as a saved Acquisition interlock or native driver acceptance.
    """
    if (type(snapshot) is not tuple or len(snapshot) != BANK_SIZE
            or any(type(value) is not float or not math.isfinite(value)
                   for value in snapshot)):
        raise ValueError("Explicit immutable finite 33-float counter bank required")
    return snapshot


def labview_i32_to_u32_ticks(microseconds):
    """Saved finite DBL*20 -> saturating I32 -> low 32 bits at U32 input.

    Negative, zero and saturated bit patterns represent source data, not a
    hardware operating permission. Nonfinite results are deliberately rejected.
    """
    if type(microseconds) not in (int, float):
        raise ValueError("Finite numeric counter timing required")
    try:
        product = microseconds * 20.0
    except OverflowError:
        raise ValueError("Finite DBL counter timing product required")
    if not math.isfinite(product):
        raise ValueError("Finite DBL counter timing product required")
    signed = min(2147483647, max(-2147483648, round(product)))
    return signed & 0xFFFFFFFF


def decode_counter_bank(snapshot):
    """Return the proved C10 pair, or None for the source guard's false arm.

    Fractional selectors pass the original 0<n<17 guard but Index Array
    coercion is unproved. Reject them rather than truncating/rounding a task.
    Fields16..31 never select C11 in this Acquisition path.
    """
    values = validate_counter_bank(snapshot)
    selector = values[SELECTOR_INDEX]
    if not 0.0 < selector < 17.0:
        return None
    if not selector.is_integer():
        raise ValueError("Fractional Acquisition counter selector is unqualified")
    number = int(selector)
    counter = (number - 1) // 2
    delay_index = 2 * counter
    width_index = delay_index + 1
    delay, width = values[delay_index], values[width_index]
    return {
        "selector": number, "counter": counter,
        "delay_index": delay_index, "width_index": width_index,
        "delay_microseconds": delay, "width_microseconds": width,
        "delay_ticks": labview_i32_to_u32_ticks(delay),
        "high_ticks": labview_i32_to_u32_ticks(width),
    }


def execute_counter_timing(read_bank, write_bank, publish, pulse_done,
                           stop_counter, write_timing_properties, start_counter,
                           wait_seconds, cancelled, observer=None):
    """Run the nominal source transfer with injected, synchronous callbacks.

    read_bank()->tuple33 is called independently for dispatch/reset/publication.
    write_bank(tuple33) replaces only selector32 on the freshly read reset
    image. publish(tuple33) receives the independently reread publication image;
    there is no built-in PSP/network operation. Counter callbacks take physical
    number0..7; write_timing_properties(number,initial,low,high) performs the
    source-ordered properties664/4465/4457. wait_seconds(0.001) must be injected;
    it does not create a hard 22ms deadline. cancelled()->exactbool and optional
    observer(stage,source_uid) run at callback boundaries, not inside a driver.

    The caller owns authorization, timing qualification, output serialization,
    retained NI handles and a separate property-write uncertainty latch BEFORE
    entering its driver callback. Successful start is only a software command
    acknowledgement. Poll failures are not silently converted to Done=False.
    """
    callbacks = (read_bank, write_bank, publish, pulse_done, stop_counter,
                 write_timing_properties, start_counter, wait_seconds, cancelled)
    if any(not callable(callback) for callback in callbacks):
        raise TypeError("Counter timing callbacks must all be callable")
    if observer is not None and not callable(observer):
        raise TypeError("Counter timing observer must be callable or None")
    report = {
        "operation": "counter_timing.update", "status": "EXECUTING",
        "source_vi_sha256": SOURCE_VI_SHA256,
        "source_helper_sha256": SOURCE_HELPER_SHA256,
        "bank": BANK_NAME, "local_bank": BANK_LOCAL,
        "helper_uids": list(HELPER_UIDS), "property_codes": list(PROPERTY_CODES),
        "caller_frame_uids": list(CALLER_FRAME_UIDS),
        "selector": None, "counter": None, "decoded": None,
        "dispatch_snapshot": None, "reset_snapshot": None,
        "requested_reset_snapshot": None, "publication_snapshot": None,
        "source_frames_completed": [], "steps_completed": [], "polls": [],
        "poll_iterations": 0, "poll_exit_reason": None,
        "final_pulse_done": None, "requested_wait_seconds": 0.0,
        "stop_attempted": False, "stop_completed": False,
        "clear_errors_boundary_reached": False,
        "configuration_attempted": False, "configuration_completed": False,
        "configuration_uncertain": False, "configured_counter": None,
        "start_attempted": False, "start_completed": False,
        "selector_reset_attempted": False, "selector_reset_completed": False,
        "selector_reset_uncertain": False, "publication_attempted": False,
        "publication_completed": False, "publication_uncertain": False,
        "pending_counter_stops": [], "commanded_running_counters": [],
        "failures": [], "completed": False, "hardware_acknowledged": False,
        "ownership_retained_by_caller": True,
        "source_error_semantics_reproduced": False,
        "native_timing_equivalence": False, "atomic_snapshot": False,
        "automatic_retry": False,
    }
    stage = ["before_dispatch"]
    effect = [None]

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise TypeError("Counter timing cancellation must return exact Boolean")
        if value:
            raise _CancelledSignal()

    def observe(name, uid):
        stage[0] = name
        check_cancel()
        if observer is not None:
            observer(name, uid)
        check_cancel()

    def call(name, uid, callback, args=()):
        observe(name, uid)
        result = callback(*args)
        report["steps_completed"].append(name)
        return result

    try:
        snapshot = validate_counter_bank(call("dispatch_read", CALLER_UIDS["dispatch_read"], read_bank))
        report["dispatch_snapshot"] = snapshot
        decoded = decode_counter_bank(snapshot)
        report["decoded"] = decoded
        check_cancel()
        if decoded is None:
            report["status"] = "NO_REQUEST"
            report["completed"] = True
            return report
        report["selector"] = decoded["selector"]
        number = decoded["counter"]
        report["counter"] = number
        for index in range(POLL_LIMIT_INDEX + 2):
            done = call("pulse_done", POLL_UID, pulse_done, (number,))
            if type(done) is not bool:
                raise TypeError("CO.PulseDone must return exact Boolean")
            report["polls"].append((index, done))
            report["poll_iterations"] = index + 1
            report["final_pulse_done"] = done
            # Wait is independent in the source; poll-then-wait is one
            # admissible serialization and includes the terminal iteration.
            call("poll_wait", WAIT_UID, wait_seconds, (0.001,))
            report["requested_wait_seconds"] += 0.001
            check_cancel()
            if done or index > POLL_LIMIT_INDEX:
                report["poll_exit_reason"] = "pulse_done" if done else "iteration_limit"
                break
        observe("counter_stop", "2976")
        report["stop_attempted"] = True
        report["pending_counter_stops"] = [number]
        effect[0] = "stop"
        stop_counter(number)
        report["stop_completed"] = True
        report["pending_counter_stops"] = []
        report["steps_completed"].append("counter_stop")
        effect[0] = None
        observe("clear_errors_boundary", "309")
        report["clear_errors_boundary_reached"] = True
        report["steps_completed"].append("clear_errors_boundary")
        observe("write_timing_properties", "3083")
        report["configuration_attempted"] = True
        report["configuration_uncertain"] = True
        effect[0] = "configuration"
        write_timing_properties(number, decoded["delay_ticks"],
                                decoded["delay_ticks"], decoded["high_ticks"])
        report["configuration_completed"] = True
        report["configuration_uncertain"] = False
        report["configured_counter"] = number
        report["steps_completed"].append("write_timing_properties")
        effect[0] = None
        observe("counter_start", "3032")
        report["start_attempted"] = True
        report["pending_counter_stops"] = [number]
        effect[0] = "start"
        start_counter(number)
        report["start_completed"] = True
        report["commanded_running_counters"] = [number]
        report["pending_counter_stops"] = []
        report["steps_completed"].append("counter_start")
        effect[0] = None
        # Source caller frame0 has helper -> Simple Error Handler. No modal
        # dialog or guessed Continue response exists in this Python adapter.
        observe("simple_error_handler_boundary", CALLER_UIDS["simple_error_handler_boundary"])
        report["source_frames_completed"].append(0)
        reset = validate_counter_bank(call("reset_read", CALLER_UIDS["reset_read"], read_bank))
        report["reset_snapshot"] = reset
        updated = reset[:SELECTOR_INDEX] + (-1.0,)
        report["requested_reset_snapshot"] = updated
        observe("selector_reset", CALLER_UIDS["selector_reset"])
        report["selector_reset_attempted"] = True
        report["selector_reset_uncertain"] = True
        effect[0] = "selector_reset"
        write_bank(updated)
        report["selector_reset_completed"] = True
        report["selector_reset_uncertain"] = False
        report["steps_completed"].append("selector_reset")
        effect[0] = None
        report["source_frames_completed"].append(1)
        publication = validate_counter_bank(call("publication_read", CALLER_UIDS["publication_read"], read_bank))
        report["publication_snapshot"] = publication
        observe("publication", CALLER_UIDS["publication"])
        report["publication_attempted"] = True
        report["publication_uncertain"] = True
        effect[0] = "publication"
        publish(publication)
        report["publication_completed"] = True
        report["publication_uncertain"] = False
        report["steps_completed"].append("publication")
        effect[0] = None
        report["source_frames_completed"].append(2)
        check_cancel()
        report["status"] = "COMPLETED"
        report["completed"] = True
        return report
    except _CancelledSignal:
        report["status"] = "CANCELLED"
        # Cancellation after a successful start leaves a running retained
        # task. It is not safe to release it just because reset/publication
        # was not reached; the caller needs an explicit confirmed stop.
        if report["start_completed"]:
            report["pending_counter_stops"] = [report["counter"]]
        raise CounterTimingCancelled(report)
    except Exception as error:
        report["status"] = "FAILED"
        report["failures"].append({"stage": stage[0],
                                   "error_type": type(error).__name__,
                                   "message": str(error),
                                   "possibly_applied_effect": effect[0]})
        if report["start_completed"]:
            report["pending_counter_stops"] = [report["counter"]]
        raise CounterTimingError(report)
