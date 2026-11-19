from __future__ import annotations
from typing import Any, NamedTuple
from .. import _lv_runtime as _lv

class Average2darraySdIntResult(NamedTuple):
    out_array: list[float]

def average_2darray_sd_int(var_2d_array_: list[list[int]] | None=None) -> Average2darraySdIntResult:
    var_2d_array_ = var_2d_array_ or []
    transposed_array = [list(r) for r in zip(*var_2d_array_)]
    out_arrays = []
    for i, transposed_array_item in enumerate(transposed_array):
        mean = _lv.mean_real64(transposed_array_item)
        out_arrays.append(mean)
    return Average2darraySdIntResult(out_array=out_arrays)