"""Polymorphic VI module."""
from __future__ import annotations
from pathlib import Path
from typing import Any, NamedTuple
from .. import _lv_runtime as _lv


class Average2darraySdDoubleResult(NamedTuple):
    out_array: list[float]

def average_2darray_sd_double(var_2d_array_: list[list[float]] | None=None) -> Average2darraySdDoubleResult:
    var_2d_array_ = var_2d_array_ or []
    transposed_array = [list(r) for r in zip(*var_2d_array_)]
    out_arrays = []
    for i, transposed_array_item in enumerate(transposed_array):
        mean = _lv.mean_real64(transposed_array_item)
        out_arrays.append(mean)
    return Average2darraySdDoubleResult(out_array=out_arrays)

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

def average_1darray_sd(*args, **kwargs):
    raise NotImplementedError('Polymorphic variant was not loaded: average-1Darray-SD.vi')


def _lv_dispatch(_fn, /, *_vals):
    """Call a polymorphic variant, mapping the wrapper's values
    to the variant's parameters BY POSITION (variants share the
    input SLOT order but may name a slot differently — e.g. a
    scalar `string` vs an array `strings`)."""
    import inspect
    _p = list(inspect.signature(_fn).parameters)
    return _fn(**dict(zip(_p, _vals)))


def average_array_poly(*args, **kwargs) -> Average2darraySdDoubleResult:
    'Polymorphic wrapper for C:\\dev\\TRANCON\\dependecies\\average_array_poly.vi.'
    _vals = [*args, *kwargs.values()]
    return _lv_dispatch(average_2darray_sd_double, *_vals)
