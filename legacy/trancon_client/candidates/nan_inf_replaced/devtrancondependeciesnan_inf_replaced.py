from __future__ import annotations
from typing import Any, NamedTuple
from .openg.devtrancon_analysisnonfinite_2026_10_03openg_sourcesearch_array__ogtk import search_array__ogtk

class NanInfReplacedResult(NamedTuple):
    out_with_nan_and_inf_replaced: list[float]

def nan_inf_replaced(in_with_inf_and_nan: list[float] | None=None, value: float=2.0) -> NanInfReplacedResult:
    in_with_inf_and_nan = in_with_inf_and_nan or []
    search_array__ogtk_result = search_array__ogtk(array=in_with_inf_and_nan, element_data=float('nan'))
    search_array__ogtk_result_99 = search_array__ogtk(array=in_with_inf_and_nan, element_data=float('inf'))
    search_array__ogtk_result_132 = search_array__ogtk(array=in_with_inf_and_nan, element_data=float('-inf'))
    in_with_inf_and_nan_2 = in_with_inf_and_nan
    search_array__ogtk_resultindices_of_elements = search_array__ogtk_result.indices_of_elements
    for i, search_array__ogtk_resultindices_of_element in enumerate(search_array__ogtk_resultindices_of_elements):
        _n = max(0, min(len([value]), len(in_with_inf_and_nan_2) - search_array__ogtk_resultindices_of_element))
        output_array = in_with_inf_and_nan_2[:search_array__ogtk_resultindices_of_element] + [value][:_n] + in_with_inf_and_nan_2[search_array__ogtk_resultindices_of_element + _n:]
        in_with_inf_and_nan_2_updated = output_array
        in_with_inf_and_nan_2 = in_with_inf_and_nan_2_updated
    state = in_with_inf_and_nan_2
    search_array__ogtk_result_99indices_of_elements = search_array__ogtk_result_99.indices_of_elements
    for i, search_array__ogtk_result_99indices_of_element in enumerate(search_array__ogtk_result_99indices_of_elements):
        _n = max(0, min(len([value]), len(state) - search_array__ogtk_result_99indices_of_element))
        output_array_1136 = state[:search_array__ogtk_result_99indices_of_element] + [value][:_n] + state[search_array__ogtk_result_99indices_of_element + _n:]
        state_updated = output_array_1136
        state = state_updated
    state_2 = state
    search_array__ogtk_result_132indices_of_elements = search_array__ogtk_result_132.indices_of_elements
    for i, search_array__ogtk_result_132indices_of_element in enumerate(search_array__ogtk_result_132indices_of_elements):
        product = value * -1.0
        _n = max(0, min(len([product]), len(state_2) - search_array__ogtk_result_132indices_of_element))
        out_with_nan_and_inf_replaced = state_2[:search_array__ogtk_result_132indices_of_element] + [product][:_n] + state_2[search_array__ogtk_result_132indices_of_element + _n:]
        state_2_updated = out_with_nan_and_inf_replaced
        state_2 = state_2_updated
    return NanInfReplacedResult(out_with_nan_and_inf_replaced=state_2)