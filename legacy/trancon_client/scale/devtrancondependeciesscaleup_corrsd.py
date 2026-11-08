from __future__ import annotations
from typing import Any, NamedTuple
from .. import _lv_runtime as _lv

class ScaleupCorrsdResult(NamedTuple):
    data_corrected: list[list[float]]

def scaleup_corrsd(scaleup: float=0.0, data: list[list[float]] | None=None) -> ScaleupCorrsdResult:
    data = data or []
    data_correcteds = []
    for i, datum in enumerate(data):
        data_corrected = _lv.mul(datum, scaleup)
        data_correcteds.append(data_corrected)
    return ScaleupCorrsdResult(data_corrected=data_correcteds)