"""Data-only counter error/dialog inspection, with no native callback inputs.

This is a supplied-return replay, not an execution adapter. Task tokens and
error clusters are fixture data, never DAQmx handles. The only bank writes and
publications below append to bounded local lists. No actual dialog is opened.
The inspected LabVIEW 2020 dialog profile does not attest the XP 2012 library.
"""

from .acquisition_counter_error_flow import (
    NO_RESPONSE,
    RETURNED,
    UNASSIGNED,
    UNWIRED,
    HandlerOutcome,
    NativeErrorCluster,
    NativeReturn,
    TaskReference,
    continue_counter_caller,
    execute_counter_error_flow,
)
from .acquisition_counter_timing import decode_counter_bank, validate_counter_bank


def _error(value):
    if type(value) is not dict or set(value) != {"status", "code", "source"}:
        raise ValueError("Exact status/code/source fixture required")
    return NativeErrorCluster(value["status"], value["code"], value["source"])


def plan_simple_error_dialog(error, public_mode=1):
    """Inspect documented/local-2020 wrapper modes, not deployed XP behavior.

    Continue retains the incoming cluster and does not retry. A Stop option
    describes LabVIEW hierarchy abort, never orderly Python/NI shutdown. The
    source counter caller leaves the mode unwired (saved default 1).
    """
    incoming = _error(error)
    if type(public_mode) is not int or public_mode not in (0, 1, 2, 3, 4):
        raise ValueError("Public Simple Error Handler mode must be 0..4")
    shown = public_mode != 0 and (
        incoming.status or (public_mode in (3, 4) and incoming.code != 0)
    )
    buttons = (
        []
        if not shown
        else ["Continue", "Stop"]
        if public_mode in (2, 4)
        else ["Continue"]
    )
    return dict(
        public_mode=public_mode,
        core_mode=(0, 1, 2, 4, 5)[public_mode],
        dialog_required_by_profile=shown,
        buttons=buttons,
        continue_clears_error=False,
        continue_retries_operation=False,
        stop_effect="abort_calling_top_level" if "Stop" in buttons else None,
        orderly_cleanup_guaranteed=False,
        actual_dialog_opened=False,
        qualification="documented_and_inspected_local_LabVIEW_2020_profile",
        deployed_xp_handler_binary_qualified=False,
    )


def preview_counter_native_flow(
    snapshot,
    returns,
    handler,
    reset_snapshot=None,
    publication_snapshot=None,
    error_in=None,
):
    """Replay exact fixture data only; cannot invoke a supplied callback.

    Each return has stage/task_token/error and optional list data. A None task
    token denotes an unwired return, not a null native task handle. All fixtures
    are checked before replay. Extra/missing/out-of-order returns are errors.
    An exact error_in fixture is required, with no inferred success default.
    A RETURNED handler needs two independent bank fixtures; no physical bank is
    read. Other dispositions must not supply bank fixtures.
    Hypothetical hierarchy abort is available only in the lower-level model:
    this saved caller has no wired override to its one-button default profile.
    """
    request = decode_counter_bank(snapshot)
    if request is None:
        raise ValueError("Preview requires a routed source counter selector")
    incoming_error = _error(error_in)
    if type(returns) is not list or not 1 <= len(returns) <= 48:
        raise ValueError("Supply 1..48 explicit native boundary returns")
    scripted = []
    for value in returns:
        if (
            type(value) is not dict
            or not {"stage", "task_token", "error"} <= set(value)
            or set(value) - {"stage", "task_token", "error", "data"}
            or type(value["stage"]) is not str
        ):
            raise ValueError("Exact native boundary fixture required")
        token = value["task_token"]
        task = UNWIRED if token is None else TaskReference(token)
        if "data" in value:
            if type(value["data"]) is not list:
                raise ValueError("Fixture data must be a scalar list")
            returned = NativeReturn(task, _error(value["error"]), tuple(value["data"]))
        else:
            returned = NativeReturn(task, _error(value["error"]))
        scripted.append((value["stage"], returned))
    if (
        type(handler) is not dict
        or "disposition" not in handler
        or set(handler) - {"disposition", "error_out"}
    ):
        raise ValueError("Exact supplied handler disposition required")
    disposition = handler["disposition"]
    if type(disposition) is not str or disposition not in (NO_RESPONSE, RETURNED):
        raise ValueError("Unknown supplied handler disposition")
    outcome = HandlerOutcome(
        disposition,
        _error(handler["error_out"]) if "error_out" in handler else UNASSIGNED,
    )
    if disposition == RETURNED:
        reset = validate_counter_bank(reset_snapshot)
        publication = validate_counter_bank(publication_snapshot)
        banks = [reset, publication]
    elif reset_snapshot is not None or publication_snapshot is not None:
        raise ValueError("Unreturned handler cannot consume bank fixtures")
    else:
        banks = []
    consumed, effects = [], []

    def invoke(call):
        index = len(consumed)
        if index >= len(scripted) or scripted[index][0] != call.stage:
            raise ValueError("Missing or out-of-order native boundary fixture")
        consumed.append(call.stage)
        return scripted[index][1]

    helper = execute_counter_error_flow(
        invoke,
        TaskReference("fixture:C10/ctr" + str(request["counter"])),
        request["delay_microseconds"],
        request["width_microseconds"],
        incoming_error,
    )
    if len(consumed) != len(scripted):
        raise ValueError("Unused native boundary fixtures")
    dialog = (
        plan_simple_error_dialog(dict(helper.error_out._asdict()))
        if helper.completed
        else None
    )
    if (
        dialog is not None
        and disposition == NO_RESPONSE
        and not dialog["dialog_required_by_profile"]
    ):
        raise ValueError("Source default profile cannot wait for a nonexistent dialog")
    read_index = [0]

    def read_bank():
        image = banks[read_index[0]]
        read_index[0] += 1
        return image

    def write_bank(image):
        effects.append(dict(kind="fixture_reset", snapshot=list(image)))

    def publish(image):
        effects.append(dict(kind="fixture_publication", snapshot=list(image)))

    caller = continue_counter_caller(helper, outcome, read_bank, write_bank, publish)
    return dict(
        mode="STATIC_SUPPLIED_RETURN_PREVIEW",
        request=request,
        dialog=dialog,
        caller=caller.to_dict(),
        fixture_effects=effects,
        hardware_execution=False,
        native_execution=False,
        runtime_state_modified=False,
        resource_release_requested=False,
        automatic_continue=False,
        automatic_retry=False,
    )
