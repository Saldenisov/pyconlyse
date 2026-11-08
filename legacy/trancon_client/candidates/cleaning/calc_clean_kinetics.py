from __future__ import annotations
from typing import Any, NamedTuple
from . import _runtime as _lv

class CalcCleanKineticsResult(NamedTuple):
    kinetics: list[float]

def calc_clean_kinetics(data: list[list[float]] | None=None, wavelength_min: int=0, wavelength_max: int=0) -> CalcCleanKineticsResult:
    data = data or []
    element = _lv.index_array_nd(data, [None, 1], [])
    size = len(element)
    x1 = wavelength_max - wavelength_min + 1
    initialized_array = [0.0 for _ in range(size)]
    state = initialized_array
    for i in range(x1):
        element_96 = _lv.index_array_nd(data, [None, i + wavelength_min], [])
        sum_ = _lv.add(state, element_96)
        state_updated = sum_
        state = state_updated
    quotient = _lv.real64_divide(state, x1)
    return CalcCleanKineticsResult(kinetics=quotient)
