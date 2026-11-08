"""Three isolated APP-17 saved adapter bodies, shared with Python 3.4.

Constants are saved templates, not runtime defaults. No scheduler, clock,
period unit, late-cycle policy, intrinsic error or acquired-data binding is
implemented. Validation is replay policy, not LabVIEW failure semantics.
"""

from collections import namedtuple

from .saved_xnode import ErrorValue

SUPPORTED_UIDS = ("19070", "32991", "32954")
TIMING_FIELDS = (
    "expected_end_f_1", "actual_end_f_1", "finished_late_f_1",
    "expected_end_i_1", "actual_end_i_1", "finished_late_i_1",
    "expected_start_i", "actual_start_i", "expected_start_f", "actual_start_f",
    "source_name", "structure_name", "period", "deadline", "offset", "start",
    "priority", "timeout", "mode", "wakeup_reason", "error", "source_type",
    "secondary_source_type", "global_end_time", "global_start_time",
    "frame_duration", "iteration_duration", "assigned_cpu", "io_scan_engine_mode",
)
Timing = namedtuple("Timing", TIMING_FIELDS)
_CONFIG = Timing(
    0, 0, False, 0, 0, False, 0, 0, 0, 0, "1 kHz", "L88102460",
    1000, -1, 0, -1, 100, -1, 2, 0, ErrorValue(False, 0, ""), "1", "",
    0, 0, 0, 0, -2, 0,
)
_RIGHT = Timing(
    0, 0, False, 0, 0, False, 0, 0, 0, 0, "1 kHz", "L88102460",
    -1, -1, -1, -1, -1, 0, 0, 0, ErrorValue(False, 0, ""), "1", "",
    0, 0, 0, 0, -1, 0,
)


def evaluate_saved_timing(uid, timing=None):
    """Read the saved constant or direct field5, without consulting a runtime.

    Constant bodies ignore supplied input values: saved config Source Name
    and Period faces have no body wires. This does not model regeneration
    after wiring/editing those faces. Projection reads only Finished Late?
    [i-1]; an error elsewhere in Timing does not select a different branch.
    """
    if type(uid) is not str or uid not in SUPPORTED_UIDS:
        raise ValueError("unqualified APP-17 timing adapter UID")
    if uid == "19070":
        return _CONFIG
    if uid == "32991":
        return _RIGHT
    if type(timing) is not Timing or type(timing.finished_late_i_1) is not bool:
        raise TypeError("explicit Timing with bool Finished Late? [i-1] required")
    return timing.finished_late_i_1


def timing_from_json(value):
    """Strict storage types; enum numbers do not imply scheduling policies."""
    if type(value) is not dict or set(value) != set(TIMING_FIELDS):
        raise ValueError("all 29 explicit saved Timing fields required")
    for name in ("finished_late_f_1", "finished_late_i_1"):
        if type(value[name]) is not bool:
            raise TypeError("explicit Boolean Timing field required: " + name)
    for name in ("source_name", "structure_name", "source_type", "secondary_source_type"):
        if type(value[name]) is not str:
            raise TypeError("explicit String Timing field required: " + name)
    for index in (0, 1, 3, 4, 6, 7, 8, 9, 23, 24, 25, 26):
        _integer(value[TIMING_FIELDS[index]], 64, False)
    for index in (12, 13, 14, 15):
        _integer(value[TIMING_FIELDS[index]], 64, True)
    for index in (16, 17, 27):
        _integer(value[TIMING_FIELDS[index]], 32, True)
    for index in (18, 19, 28):
        _integer(value[TIMING_FIELDS[index]], 32, False)
    error = value["error"]
    if type(error) is not dict or set(error) != set(("status", "code", "source")):
        raise ValueError("explicit Timing error status/code/source required")
    if type(error["status"]) is not bool or type(error["source"]) is not str:
        raise TypeError("explicit Boolean/String Timing error fields required")
    _integer(error["code"], 32, True)
    copied = dict(value, error=ErrorValue(error["status"], error["code"], error["source"]))
    return Timing(*(copied[name] for name in TIMING_FIELDS))


def _integer(value, bits, signed):
    lower = -(2 ** (bits - 1)) if signed else 0
    upper = 2 ** (bits - 1) if signed else 2 ** bits
    if type(value) is not int or not lower <= value < upper:
        raise ValueError("explicit in-range Timing integer required")


def timing_to_json(value):
    result = value._asdict()
    result["error"] = dict(value.error._asdict())
    return dict(result)


def replay_saved_timing(payload):
    if type(payload) is not dict or set(payload) != set(("source_id", "uid", "inputs")):
        raise ValueError("saved timing replay requires source_id, uid, inputs")
    if type(payload["source_id"]) is not str or payload["source_id"] != "APP-17":
        raise ValueError("only qualified source APP-17 is supported")
    uid, inputs = payload["uid"], payload["inputs"]
    if type(uid) is not str or uid not in SUPPORTED_UIDS:
        raise ValueError("unqualified APP-17 timing adapter UID")
    if type(inputs) is not dict:
        raise TypeError("explicit saved timing input object required")
    if uid == "19070":
        if not set(inputs) <= set(("source_name", "period")):
            raise ValueError("only unused saved config faces may be supplied")
        result = dict(timing=timing_to_json(evaluate_saved_timing(uid)))
    elif uid == "32991":
        if inputs:
            raise ValueError("saved right constant body has no inputs")
        result = dict(timing=timing_to_json(evaluate_saved_timing(uid)))
    else:
        if set(inputs) != set(("timing",)):
            raise ValueError("explicit saved Timing input required")
        result = dict(finished_late_i_1=evaluate_saved_timing(uid, timing_from_json(inputs["timing"])))
    return dict(source_id="APP-17", uid=uid, outputs=result,
                input_origin="OPERATOR_SUPPLIED_REPLAY", saved_body_only=True,
                scheduler_execution_qualified=False, runtime_defaults_qualified=False,
                native_runtime_equivalence_qualified=False, acquired_data_bound=False)
