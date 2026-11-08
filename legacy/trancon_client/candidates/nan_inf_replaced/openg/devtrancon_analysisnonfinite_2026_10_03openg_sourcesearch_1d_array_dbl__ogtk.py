from __future__ import annotations
from typing import Any, NamedTuple

class Search1dArrayDblOgtkResult(NamedTuple):
    indices_of_elements: list[int]

def search_1d_array_dbl__ogtk(array: list[float] | None=None, element_data: float=0.0, start_index_0: int=0) -> Search1dArrayDblOgtkResult:
    array = array or []
    start_index_0_2 = start_index_0
    initial_elements = []
    while True:
        index_of_element = next((i for i in range(int(start_index_0_2), len(array)) if array[i] == element_data), -1)
        case_output = None
        match index_of_element:
            case -1:
                case_output = initial_elements
            case _:
                items = initial_elements + [index_of_element]
                case_output = items
        start_index_0_2_updated = index_of_element + 1
        initial_elements_updated = case_output
        start_index_0_2 = start_index_0_2_updated
        initial_elements = initial_elements_updated
        if not index_of_element >= 0:
            break
    return Search1dArrayDblOgtkResult(indices_of_elements=initial_elements)