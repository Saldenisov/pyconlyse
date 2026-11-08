from __future__ import annotations
from typing import Any, NamedTuple
from . import _runtime as _lv

class CleanKineticsSdResult(NamedTuple):
    timedelays_out: list[float]
    data_out: list[list[float]]

def clean_kinetics_sd(tdpixels: tuple=None, clean_mode: int=1, bounds: tuple=None, data: list[list[float]] | None=None, kinetics: list[float] | None=None, timedelays: list[float] | None=None) -> CleanKineticsSdResult:
    data = data or []
    kinetics = kinetics or []
    timedelays = timedelays or []
    subarray = _lv.array_subset_nd(data, [(0, None), (0, None)])
    size = len(kinetics)
    positions = []
    bounds0 = bounds[0]
    bounds1 = bounds[1]
    tdpixels1 = tdpixels[1]
    tdpixels0 = tdpixels[0]
    for i, kinetic in enumerate(kinetics):
        result = i <= tdpixels1 and i >= tdpixels0
        case_output_6664 = None
        if result:
            result_1137 = kinetic < bounds0 or kinetic > bounds1
            case_output = None
            if result_1137:
                output_array = positions[:len(positions)] + [i] + positions[len(positions):] if 0 <= len(positions) <= len(positions) else list(positions)
                case_output = output_array
            else:
                case_output = positions
            case_output_6664 = case_output
        else:
            case_output_6664 = positions
        positions_updated = case_output_6664
        positions = positions_updated
    timedelays_out = None
    data_out = None
    match clean_mode:
        case 0:
            state = subarray
            timedelays_2 = timedelays
            for i, position in enumerate(positions):
                difference = position - i
                output_array_570 = timedelays_2[:difference] + timedelays_2[difference + 1:]
                output_array_2284 = state[:difference] + state[difference + 1:]
                state_updated = output_array_2284
                timedelays_out = output_array_570
                state = state_updated
                timedelays_2 = timedelays_out
            data_out = [list(r) for r in zip(*state)]
            timedelays_out = timedelays_2
        case 1:
            transposed_array = [list(r) for r in zip(*subarray)]
            data_outs = []
            size___1 = size - 1
            for i, transposed_array_item in enumerate(transposed_array):
                state_2 = transposed_array_item
                for j, position_2 in enumerate(positions):
                    case_output_1850 = None
                    if 0 == position_2:
                        element = _lv.index_array_nd(state_2, [position_2 + 1], 0.0)
                        _n = max(0, min(len([element]), len(state_2) - position_2))
                        output_array_2571 = state_2[:position_2] + [element][:_n] + state_2[position_2 + _n:]
                        case_output_1850 = output_array_2571
                    else:
                        case_output_1799 = None
                        if size___1 == position_2:
                            element_2595 = _lv.index_array_nd(state_2, [position_2 - 1], 0.0)
                            _n = max(0, min(len([element_2595]), len(state_2) - position_2))
                            output_array_1761 = state_2[:position_2] + [element_2595][:_n] + state_2[position_2 + _n:]
                            case_output_1799 = output_array_1761
                        else:
                            element_1408 = _lv.index_array_nd(state_2, [position_2 + 1], 0.0)
                            element_1519 = _lv.index_array_nd(state_2, [position_2 - 1], 0.0)
                            quotient = _lv.real64_divide(element_1519 + element_1408, 2.0)
                            _n = max(0, min(len([quotient]), len(state_2) - position_2))
                            output_array_1149 = state_2[:position_2] + [quotient][:_n] + state_2[position_2 + _n:]
                            case_output_1799 = output_array_1149
                        case_output_1850 = case_output_1799
                    state_2_updated = case_output_1850
                    state_2 = state_2_updated
                data_outs.append(state_2)
            timedelays_out = timedelays
            data_out = data_outs
    return CleanKineticsSdResult(timedelays_out=timedelays_out, data_out=data_out)
