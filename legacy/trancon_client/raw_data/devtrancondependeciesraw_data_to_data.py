from __future__ import annotations
from typing import Any, NamedTuple
from .devtrancondependeciesaverage_array_poly import average_array_poly
from .. import _lv_runtime as _lv

class RawDataToDataResult(NamedTuple):
    exp_data: list[list[float]]

def raw_data_to_data(raw_data: list[list[list[list[int]]]] | None=None, trabs_precalc: list[list[float]] | None=None) -> RawDataToDataResult:
    raw_data = raw_data or []
    trabs_precalc = trabs_precalc or []
    size = _lv.array_size(trabs_precalc, 2)
    element = _lv.index_array_nd(size, [0], 0)
    exp_data = None
    if element != 0:
        exp_data = trabs_precalc
    else:
        out_arrays = []
        for i, raw_data_item in enumerate(raw_data):
            size_1171 = _lv.array_size(raw_data_item, 3)
            element_1219 = _lv.index_array_nd(size_1171, [1], 0)
            var_2d_array_s = []
            for j in range(element_1219):
                element_1358 = _lv.index_array_nd(raw_data_item, [0, j, None], [])
                element_1422 = _lv.index_array_nd(raw_data_item, [1, j, None], [])
                element_1437 = _lv.index_array_nd(raw_data_item, [2, j, None], [])
                element_1449 = _lv.index_array_nd(raw_data_item, [3, j, None], [])
                element_1461 = _lv.index_array_nd(raw_data_item, [4, j, None], [])
                element_1473 = _lv.index_array_nd(raw_data_item, [5, j, None], [])
                difference = _lv.sub(element_1461, element_1358)
                difference_1962 = _lv.sub(element_1437, element_1358)
                difference_1980 = _lv.sub(element_1449, element_1422)
                difference_1998 = _lv.sub(element_1473, element_1422)
                quotient = _lv.real64_divide(difference, difference_1962)
                quotient_326 = _lv.real64_divide(difference_1998, difference_1980)
                quotient_366 = _lv.real64_divide(quotient, quotient_326)
                logx = _lv.log10(quotient_366)
                var_2d_array_s.append(logx)
            average_array_poly_result = average_array_poly(var_2d_array_=var_2d_array_s)
            out_arrays.append(average_array_poly_result.out_array)
        exp_data = out_arrays
    return RawDataToDataResult(exp_data=exp_data)