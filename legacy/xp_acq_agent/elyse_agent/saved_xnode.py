"""Bounded saved Supervision XNode bodies shared with the modern host.

Python 3.4 stdlib only. Source APP-17 and exact borders are qualified in
xnode_followup_20261008/XNODE_CENSUS.json. These are isolated body replays;
50983/58520 belong to a saved Disabled frame and are never activated here.
No scheduler, telemetry, device, unit conversion or physical readback is inferred.
Validation refusals are Python policy, not simulated LabVIEW error codes.
"""

from __future__ import division

import math
from collections import namedtuple

ErrorValue = namedtuple("ErrorValue", "status code source")
XNodeResult = namedtuple("XNodeResult", "result error_out")
SUPPORTED_UIDS = ("50983", "58520", "37034", "36467", "47576")


def _error(value):
    if type(value.status) is not bool:
        raise TypeError("explicit error status must be bool")
    if type(value.code) is not int or not -(2**31) <= value.code < 2**31:
        raise ValueError("explicit I32 error code required")
    if type(value.source) is not str:
        raise TypeError("explicit error source must be str")


def evaluate_saved_xnode(uid, inputs, error_in):
    """Return Result and the original error value, using saved input order.

    Healthy domain: finite DBL tuples; exponential X1 in [-4, 8]; ratio inputs
    in [-19, 19], nonzero left-associated sum and finite result. No native
    NaN/Inf/singular/overflow equivalence is claimed. True status bypasses
    every input access and returns 0.0; nonzero code alone does not bypass.
    """
    if type(uid) is not str or uid not in SUPPORTED_UIDS:
        raise ValueError("unqualified APP-17 XNode UID")
    _error(error_in)
    if error_in.status:
        return XNodeResult(0.0, error_in)
    arity = 1 if uid in ("50983", "58520") else 4
    if type(inputs) is not tuple or len(inputs) != arity:
        raise TypeError("explicit full-size DBL tuple required")
    if any(type(value) is not float or not math.isfinite(value) for value in inputs):
        raise ValueError("finite DBL formula inputs required")
    if arity == 1:
        x1 = inputs[0]
        if not -4.0 <= x1 <= 8.0:
            raise ValueError("exponential input outside bounded replay domain [-4, 8]")
        if uid == "50983":
            result = 2.45 * math.exp(-11) * math.exp(0.85 * x1)
        else:
            result = 1.333 * math.exp(-11) * math.exp(1.2 * x1)
    else:
        if any(not -19.0 <= value <= 19.0 for value in inputs):
            raise ValueError("ratio input outside bounded replay domain [-19, 19]")
        x1, x2, x3, x4 = inputs
        denominator = x1 + x2 + x3 + x4
        if denominator == 0.0:
            raise ValueError("singular denominator has no qualified native equivalence")
        numerator = 40 * (x4 - x3) if uid == "37034" else 40 * (x2 - x1)
        result = numerator / denominator
    if not math.isfinite(result):
        raise ValueError("non-finite result has no qualified native equivalence")
    return XNodeResult(result, error_in)


def replay_saved_xnode(payload):
    """JSON adapter used by both web replay and signed acquisition RPC.

    Numeric JSON values are explicitly normalized to DBL for replay. This
    adapter policy does not qualify a native coercion or bind acquired data.
    No runtime state, revision, intent or output image is read or changed.
    """
    keys = ("source_id", "uid", "inputs", "error_in")
    if type(payload) is not dict or set(payload) != set(keys):
        raise ValueError("saved XNode replay requires source_id, uid, inputs, error_in")
    if payload["source_id"] != "APP-17" or type(payload["source_id"]) is not str:
        raise ValueError("only qualified source APP-17 is supported")
    error = payload["error_in"]
    if type(error) is not dict or set(error) != set(("status", "code", "source")):
        raise ValueError("explicit status/code/source error value required")
    error = ErrorValue(error["status"], error["code"], error["source"])
    _error(error)
    inputs = payload["inputs"]
    if not error.status:
        if type(inputs) is not list or any(type(v) not in (int, float) for v in inputs):
            raise TypeError("explicit JSON numeric input list required")
        try:
            inputs = tuple(float(value) for value in inputs)
        except OverflowError:
            raise ValueError("numeric input cannot be represented as a finite DBL")
    result = evaluate_saved_xnode(payload["uid"], inputs, error)
    return dict(
        source_id="APP-17",
        uid=payload["uid"],
        result=result.result,
        error_out=result.error_out._asdict(),
        input_origin="OPERATOR_SUPPLIED_REPLAY",
        inactive_saved_body=payload["uid"] in ("50983", "58520"),
        native_runtime_equivalence_qualified=False,
        acquired_data_bound=False,
    )
