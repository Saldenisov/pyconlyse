from __future__ import annotations
from typing import Any, NamedTuple
from . import _runtime as _lv

class BgCorrsdResult(NamedTuple):
    data_corrected: list[list[float]]

def bg_corrsd(lower_pixel: float=0.0, upper_pixel: float=0.0, data: list[list[float]] | None=None, baseline_mode: int=0) -> BgCorrsdResult:
    data = data or []
    transposed_array = [list(r) for r in zip(*data)]
    size = _lv.array_size(transposed_array, 2)
    case_output = 0.0
    if upper_pixel == lower_pixel:
        case_output = lower_pixel + 1
    else:
        case_output = lower_pixel
    element = _lv.index_array_nd(size, [0], 0)
    values = []
    for i in range(element):
        values.append(i)
    case_output_1135 = 0.0
    case_output_1273 = 0.0
    if case_output > upper_pixel:
        case_output_1135 = case_output
        case_output_1273 = upper_pixel
    else:
        case_output_1135 = upper_pixel
        case_output_1273 = case_output
    x1 = case_output_1135 - case_output_1273 + 1
    subarray = _lv.array_subset_nd(transposed_array, [(0, None), (case_output_1273, x1)])
    values_2 = []
    for i, subarray_item in enumerate(subarray):
        sum_ = sum(subarray_item)
        quotient = _lv.real64_divide(sum_, x1)
        values_2.append(quotient)
    data_corrected = None
    if not baseline_mode:
        data_correcteds = []
        for i in range(min(len(data), len(values_2))):
            difference = _lv.sub(data[i], values_2[i])
            data_correcteds.append(difference)
        values_valueses = [(values, values_2)]
        data_corrected = data_correcteds
        case_output_39 = values_valueses
    return BgCorrsdResult(data_corrected=data_corrected)