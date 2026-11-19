from __future__ import annotations
from typing import Any, NamedTuple
from .devtrancondependeciesaverage_array_poly import average_array_poly
from .. import _lv_runtime as _lv

class RawBgCorrsdResult(NamedTuple):
    data_corrected: list[list[float]]

def raw_bg_corrsd(data_raw: list[list[list[list[int]]]] | None=None, raw_bg: list[int] | None=None) -> RawBgCorrsdResult:
    data_raw = data_raw or []
    raw_bg = raw_bg or []
    out_arrays = []
    for i, data_raw_item in enumerate(data_raw):
        size = _lv.array_size(data_raw_item, 3)
        element = _lv.index_array_nd(size, [1], 0)
        var_2d_array_s = []
        var_2d_array_s_2 = []
        var_2d_array_s_3 = []
        var_2d_array_s_4 = []
        var_2d_array_s_5 = []
        for j in range(element):
            element_840 = _lv.index_array_nd(raw_bg, [0], 0)
            element_868 = _lv.index_array_nd(raw_bg, [0 + 1], 0)
            element_561 = _lv.index_array_nd(data_raw_item, [0, j, None], [])
            element_573 = _lv.index_array_nd(data_raw_item, [1, j, None], [])
            element_585 = _lv.index_array_nd(data_raw_item, [2, j, None], [])
            element_597 = _lv.index_array_nd(data_raw_item, [3, j, None], [])
            element_609 = _lv.index_array_nd(data_raw_item, [4, j, None], [])
            element_621 = _lv.index_array_nd(data_raw_item, [5, j, None], [])
            difference = _lv.sub(element_609, element_561)
            difference_646 = _lv.sub(element_585, element_561)
            difference_658 = _lv.sub(element_597, element_573)
            difference_670 = _lv.sub(element_621, element_573)
            difference_1663 = _lv.sub(difference, element_840)
            difference_1776 = _lv.sub(difference_646, element_840)
            difference_1897 = _lv.sub(difference_658, element_868)
            difference_1834 = _lv.sub(difference_670, element_868)
            quotient = _lv.real64_divide(difference_1663, difference_1776)
            quotient_693 = _lv.real64_divide(difference_1834, difference_1897)
            quotient_704 = _lv.real64_divide(quotient, quotient_693)
            logx = _lv.log10(quotient_704)
            var_2d_array_s.append(logx)
            var_2d_array_s_2.append(difference_646)
            var_2d_array_s_3.append(difference)
            var_2d_array_s_4.append(difference_658)
            var_2d_array_s_5.append(difference_670)
        average_array_poly_result = average_array_poly(var_2d_array_=var_2d_array_s)
        average_array_poly_result_1428 = average_array_poly(var_2d_array_=var_2d_array_s_3)
        average_array_poly_result_1513 = average_array_poly(var_2d_array_=var_2d_array_s_2)
        average_array_poly_result_1553 = average_array_poly(var_2d_array_=var_2d_array_s_4)
        average_array_poly_result_1655 = average_array_poly(var_2d_array_=var_2d_array_s_5)
        items = average_array_poly_result_1513.out_array + average_array_poly_result_1553.out_array + average_array_poly_result_1428.out_array + average_array_poly_result_1655.out_array
        out_arrays.append(average_array_poly_result.out_array)
    return RawBgCorrsdResult(data_corrected=out_arrays)