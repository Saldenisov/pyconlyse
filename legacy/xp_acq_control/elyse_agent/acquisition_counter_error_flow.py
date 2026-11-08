"""Supplied-return NI6602 error-cluster replay, never a native adapter.

The saved helper reuses its original task/error at every PulseDone poll. Only
the final poll's returned task/error feed Stop -> Clear Errors -> timing
properties -> Start. Returned error status does not itself terminate polling.
Every native boundary requires an explicit return; no driver behavior is
inferred from incoming error status. A Python callback exception propagates
unchanged and is never converted into a cleared LabVIEW error cluster.

Caller reset/publication is separate: it requires a supplied normal handler
return. An absent response suspends the caller. A supplied top-level abort
does not run ordinary continuation or invent resource cleanup. In particular,
an unwired Simple Error Handler mode does NOT establish a Continue/Stop dialog:
the inspected local LabVIEW 2020 wrapper defaults to OK-message mode 1, and the
deployed XP library identity remains unqualified. No dialog or Stop primitive,
clock, driver, process, transport, or hardware operation is executed here.

Callback exceptions provide no evidence about partially applied effects. A
caller that ever uses an effectful adapter must latch uncertainty before each
effectful callback; this supplied-return proof model implements no such adapter
and grants no physical operating permission or ownership-release permission.
"""

from collections import namedtuple
from enum import Enum
from math import isfinite

from .acquisition_counter_timing import (
    BANK_NAME,
    CALLER_FRAME_UIDS,
    CALLER_UIDS,
    POLL_LIMIT_INDEX,
    PROPERTY_CODES,
    SOURCE_HELPER_SHA256,
    SOURCE_VI_SHA256,
    labview_i32_to_u32_ticks,
    validate_counter_bank,
)


class MissingValue(Enum):
    UNWIRED = "unwired"
    UNASSIGNED = "unassigned"
    UNSUPPLIED = "unsupplied_external_return"


UNWIRED = MissingValue.UNWIRED
UNASSIGNED = MissingValue.UNASSIGNED
UNSUPPLIED = MissingValue.UNSUPPLIED
NO_RESPONSE = "NO_RESPONSE"
RETURNED = "RETURNED"
ABORT_TOP_LEVEL = "ABORT_TOP_LEVEL"


class NativeErrorCluster(namedtuple("NativeErrorClusterBase", "status code source")):
    __slots__ = ()

    def __new__(cls, status, code, source=""):
        if type(status) is not bool or type(code) is not int:
            raise TypeError("Native error status/code require exact bool/I32")
        if not -2147483648 <= code <= 2147483647:
            raise ValueError("Native error code must fit signed I32")
        if type(source) is not str:
            raise TypeError("Native error source requires exact str")
        return tuple.__new__(cls, (status, code, source))


NO_ERROR = NativeErrorCluster(False, 0, "")


def clear_all_errors(error_in):
    """Documented Clear Errors profile with unwired specific-error-code input.

    NI help documents default code 0 as clearing every error to False/0/empty.
    This value transform clears no driver/task state and catches no Python
    exception. Selecting this documented profile does not qualify the deployed
    XP library binary; the replay callback must choose it explicitly.
    """
    if type(error_in) is not NativeErrorCluster:
        raise TypeError("Clear Errors requires exact NativeErrorCluster")
    NativeErrorCluster(error_in.status, error_in.code, error_in.source)
    return NO_ERROR


class TaskReference(namedtuple("TaskReferenceBase", "token")):
    __slots__ = ()

    def __new__(cls, token):
        if type(token) is not str or not token:
            raise ValueError("Opaque task token requires nonempty exact str")
        return tuple.__new__(cls, (token,))


class NativeReturn(namedtuple("NativeReturnBase", "task error data")):
    __slots__ = ()

    def __new__(cls, task, error, data=UNSUPPLIED):
        if type(task) is not TaskReference and task is not UNWIRED:
            raise TypeError("Native return task requires opaque token or UNWIRED")
        if type(error) is not NativeErrorCluster:
            raise TypeError("Native return error requires NativeErrorCluster")
        NativeErrorCluster(error.status, error.code, error.source)
        if data is not UNSUPPLIED and not (
            type(data) is tuple
            and all(
                type(value) in (bool, int, float, str)
                and (type(value) is not float or isfinite(value))
                for value in data
            )
        ):
            raise TypeError("Native return data requires immutable scalar tuple")
        return tuple.__new__(cls, (task, error, data))


class NativeCall(
    namedtuple("NativeCallBase", "stage node_uid iteration task_in error_in arguments")
):
    __slots__ = ()


class NativeCallResult(namedtuple("NativeCallResultBase", "call returned")):
    __slots__ = ()


class HandlerOutcome(namedtuple("HandlerOutcomeBase", "disposition error_out")):
    """Explicit handler completion, not an inferred physical dialog response."""

    __slots__ = ()

    def __new__(cls, disposition, error_out=UNASSIGNED):
        if disposition not in (NO_RESPONSE, RETURNED, ABORT_TOP_LEVEL):
            raise ValueError("Unrecognized supplied handler disposition")
        if disposition == RETURNED:
            if type(error_out) is not NativeErrorCluster:
                raise TypeError("Normal handler return requires supplied error cluster")
            NativeErrorCluster(error_out.status, error_out.code, error_out.source)
        elif error_out is not UNASSIGNED:
            raise ValueError("Unreturned handler has no supplied output cluster")
        return tuple.__new__(cls, (disposition, error_out))


def _json_value(value):
    if isinstance(value, MissingValue):
        return {"connection": value.value}
    if type(value) is NativeErrorCluster:
        return {"status": value.status, "code": value.code, "source": value.source}
    if type(value) is TaskReference:
        return {"opaque_task_token": value.token}
    if type(value) is NativeCall:
        return {
            "stage": value.stage,
            "node_uid": value.node_uid,
            "iteration": value.iteration,
            "task_in": _json_value(value.task_in),
            "error_in": _json_value(value.error_in),
            "arguments": {name: _json_value(item) for name, item in value.arguments},
        }
    if type(value) is NativeReturn:
        return {
            "task": _json_value(value.task),
            "error": _json_value(value.error),
            "data": _json_value(value.data),
        }
    if type(value) is NativeCallResult:
        return {
            "call": _json_value(value.call),
            "returned": _json_value(value.returned),
        }
    if type(value) is HandlerOutcome:
        return {
            "disposition": value.disposition,
            "error_out": _json_value(value.error_out),
        }
    if type(value) is tuple:
        return [_json_value(item) for item in value]
    return value


class CounterErrorFlowResult(
    namedtuple(
        "CounterErrorFlowResultBase",
        "delay_ticks high_ticks poll_iterations exit_reason final_pulse_done "
        "task_out error_out calls completed suspended_at",
    )
):
    __slots__ = ()

    def to_dict(self):
        result = {name: _json_value(getattr(self, name)) for name in self._fields}
        result.update(
            {
                "operation": "counter_timing.native_error_flow_preview",
                "mode": "supplied-return-only",
                "source_vi_sha256": SOURCE_VI_SHA256,
                "source_helper_sha256": SOURCE_HELPER_SHA256,
                "driver_semantics_inferred": False,
                "hardware_acknowledged": False,
                "native_timing_equivalence": False,
                "automatic_retry": False,
                "resource_release_requested": False,
            }
        )
        return result


class CounterCallerResult(
    namedtuple(
        "CounterCallerResultBase",
        "helper handler reset_snapshot requested_reset_snapshot "
        "publication_snapshot completed_frames completed suspended_at",
    )
):
    __slots__ = ()

    def to_dict(self):
        result = {
            name: _json_value(getattr(self, name))
            for name in self._fields
            if name != "helper"
        }
        result["helper"] = self.helper.to_dict()
        result.update(
            {
                "operation": "counter_timing.native_caller_preview",
                "mode": "supplied-return-only",
                "bank": BANK_NAME,
                "caller_frame_uids": list(CALLER_FRAME_UIDS),
                "handler_uid": CALLER_UIDS["simple_error_handler_boundary"],
                "source_dialog_mode_input_wired": False,
                "saved_connector_default": 1,
                "deployed_xp_handler_binary_qualified": False,
                "supplied_handler_disposition_hypothetical": True,
                "source_vi_sha256": SOURCE_VI_SHA256,
                "hardware_acknowledged": False,
                "resource_release_requested": False,
                "automatic_retry": False,
                "atomic_snapshot": False,
            }
        )
        return result


def execute_counter_error_flow(
    invoke, task, delay_microseconds, width_microseconds, error_in
):
    """Replay proved task/error wires with explicitly supplied call returns.

    invoke(NativeCall)->NativeReturn is required even for Wait and ClearErrors.
    No pass-through, success, cleared cluster, native error-in short circuit, or
    successful task operation is invented. The Wait return is ignored because
    the source Wait has no task/error wire; its invocation records requested
    duration only. Poll-then-Wait is one admissible serialization of independent
    sibling nodes, not a claim of a hard native 22ms deadline.
    """
    if not callable(invoke):
        raise TypeError("Supplied native return callback must be callable")
    if type(task) is not TaskReference:
        raise TypeError("Helper task requires opaque TaskReference")
    if type(error_in) is not NativeErrorCluster:
        raise TypeError("Helper error requires NativeErrorCluster")
    NativeErrorCluster(error_in.status, error_in.code, error_in.source)
    delay = labview_i32_to_u32_ticks(delay_microseconds)
    high = labview_i32_to_u32_ticks(width_microseconds)
    calls = []

    def call(
        stage, uid, iteration=None, task_in=UNWIRED, incoming=UNWIRED, arguments=()
    ):
        requested = NativeCall(stage, uid, iteration, task_in, incoming, arguments)
        returned = invoke(requested)
        if type(returned) is not NativeReturn:
            raise TypeError("Every boundary requires explicit exact NativeReturn")
        # Revalidate even if a caller manually constructed a tuple subclass
        # through namedtuple._make rather than the public checked constructor.
        NativeReturn(returned.task, returned.error, returned.data)
        calls.append(NativeCallResult(requested, returned))
        return returned

    done = UNSUPPLIED
    for index in range(POLL_LIMIT_INDEX + 2):
        polled = call(
            "read_co_pulse_done",
            "3202",
            index,
            task,
            error_in,
            (("property_code", 6414), ("concurrent_wait_uid", "3194")),
        )
        call(
            "wait_ms",
            "3194",
            index,
            arguments=(("milliseconds", 1), ("concurrent_property_uid", "3202")),
        )
        if polled.data is UNSUPPLIED:
            done = UNSUPPLIED
        elif len(polled.data) == 1 and type(polled.data[0]) is bool:
            done = polled.data[0]
        else:
            raise ValueError("PulseDone supplied data requires one exact Boolean")
        if done is True or index > POLL_LIMIT_INDEX:
            reason = "pulse_done" if done is True else "iteration_limit"
            break
        if done is UNSUPPLIED:
            return CounterErrorFlowResult(
                delay,
                high,
                index + 1,
                "missing_poll_value",
                done,
                UNASSIGNED,
                UNASSIGNED,
                tuple(calls),
                False,
                "pulse_done_return",
            )
    if type(polled.task) is not TaskReference:
        raise TypeError("Final poll requires supplied opaque task return")
    stopped = call("stop_task", "2976", task_in=polled.task, incoming=polled.error)
    if type(stopped.task) is not TaskReference:
        raise TypeError("Stop requires supplied opaque task return")
    cleared = call(
        "clear_errors",
        "309",
        incoming=stopped.error,
        arguments=(
            ("connected_error_input_slot", 4),
            ("connected_error_output_slot", 0),
            ("specific_error_code", 0),
            ("specific_error_code_input_wired", False),
            (
                "specific_error_code_provenance",
                "unwired connector default 0 means all errors",
            ),
        ),
    )
    configured = call(
        "write_co_timing_properties",
        "3083",
        task_in=stopped.task,
        incoming=cleared.error,
        arguments=(
            ("property_codes", PROPERTY_CODES),
            ("initial_delay_ticks", delay),
            ("low_ticks", delay),
            ("high_ticks", high),
        ),
    )
    if type(configured.task) is not TaskReference:
        raise TypeError("Timing properties require supplied opaque task return")
    started = call(
        "start_task", "3032", task_in=configured.task, incoming=configured.error
    )
    return CounterErrorFlowResult(
        delay,
        high,
        index + 1,
        reason,
        done,
        started.task,
        started.error,
        tuple(calls),
        True,
        None,
    )


def continue_counter_caller(
    helper_result, handler_outcome, read_bank, write_bank, publish
):
    """Continue source reset/publication only after an explicit normal return.

    The handler's output error cluster is not a guard in the saved caller.
    Reset reads a new bank, changes only field32 to -1.0, then publication reads
    another bank. Neither action reuses the helper dispatch image. Supplied
    ABORT_TOP_LEVEL is a recorded abort boundary, not a Python Stop operation or
    a promise that NI resources have been cleared. Callback exceptions propagate
    unchanged; no successful reset/publication is fabricated or replayed. An
    effectful adapter would need a caller-owned uncertainty latch set BEFORE
    invoking each callback because a raising callback may already have applied
    its effect. This proof-only model neither supplies nor qualifies an adapter.
    """
    if type(helper_result) is not CounterErrorFlowResult:
        raise TypeError("Caller requires exact CounterErrorFlowResult")
    if type(handler_outcome) is not HandlerOutcome:
        raise TypeError("Caller requires explicit supplied HandlerOutcome")
    HandlerOutcome(handler_outcome.disposition, handler_outcome.error_out)
    if any(not callable(callback) for callback in (read_bank, write_bank, publish)):
        raise TypeError("Counter caller callbacks must all be callable")
    if not helper_result.completed:
        return CounterCallerResult(
            helper_result,
            handler_outcome,
            UNASSIGNED,
            UNASSIGNED,
            UNASSIGNED,
            (),
            False,
            "helper_not_completed",
        )
    if handler_outcome.disposition != RETURNED:
        pending = (
            "handler_response"
            if handler_outcome.disposition == NO_RESPONSE
            else "top_level_abort"
        )
        return CounterCallerResult(
            helper_result,
            handler_outcome,
            UNASSIGNED,
            UNASSIGNED,
            UNASSIGNED,
            (),
            False,
            pending,
        )
    reset = validate_counter_bank(read_bank())
    updated = reset[:32] + (-1.0,)
    write_bank(updated)
    publication = validate_counter_bank(read_bank())
    publish(publication)
    return CounterCallerResult(
        helper_result,
        handler_outcome,
        reset,
        updated,
        publication,
        (0, 1, 2),
        True,
        None,
    )
