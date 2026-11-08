"""AST-extracted lvkit helpers; native cleaning qualification pending."""
from __future__ import annotations
import math as _math
import operator as _op
from collections.abc import Callable

def _binop(a, b, f: Callable):
    a_arr, b_arr = (isinstance(a, list), isinstance(b, list))
    if a_arr and b_arr:
        return [_binop(x, y, f) for x, y in zip(a, b)]
    if a_arr:
        return [_binop(x, b, f) for x in a]
    if b_arr:
        return [_binop(a, y, f) for y in b]
    return f(a, b)

def add(a, b):
    return _binop(a, b, _op.add)

def _real64_divide_scalar(a, b):
    a, b = (float(a), float(b))
    if b == 0.0:
        if a == 0.0 or _math.isnan(a):
            return _math.nan
        sign = _math.copysign(1.0, a) * _math.copysign(1.0, b)
        return _math.copysign(_math.inf, sign)
    return a / b

def real64_divide(a, b):
    """DBL division; list broadcasting follows existing runtime convention.

    Nonzero/zero -> signed Inf; zero/zero and NaN/zero -> NaN. This does
    not model LabVIEW floating-point status flags or other representations.
    """
    return _binop(a, b, _real64_divide_scalar)

def index_array_nd(arr, indices, default):
    """Select enabled axes; None preserves a disabled axis. Never mutate input."""
    indices = list(indices)
    sizes = array_size(arr, len(indices))
    sizes = [sizes] if isinstance(sizes, int) else sizes
    if any((index is not None and (not 0 <= int(index) < size) for index, size in zip(indices, sizes))):
        return default

    def select(value, remaining):
        if not remaining:
            return value
        if not isinstance(value, (list, tuple)):
            raise ValueError('Index Array input is not rectangular at declared rank')
        index, *tail = remaining
        if index is None:
            return [select(item, tail) for item in value]
        index = int(index)
        if not 0 <= index < len(value):
            raise ValueError('Index Array input is not rectangular at declared rank')
        return select(value[index], tail)
    return select(arr, indices)

def array_subset_nd(arr, bounds):
    """Nested list subset with independent (index, length) for each axis.

    Qualified domain: rectangular arrays, integral nonnegative boundaries
    whose requested subset fits each axis. Unwired lengths retain that axis.
    Native behavior outside this domain has not been qualified here.
    """
    if not bounds:
        return arr
    index, length = bounds[0]
    start = int(index)
    end = None if length is None else start + int(length)
    selected = arr[start:end]
    return [array_subset_nd(value, bounds[1:]) for value in selected] if len(bounds) > 1 else selected

def array_size(a, ndims: int):
    """LabVIEW Array Size for an ``ndims``-dimensional array. A 1-D array yields
    a scalar element count; a 2-D+ array yields a 1-D list of per-dimension sizes
    ``[d0, d1, ...]`` (LabVIEW's multi-dimensional Array Size returns the size
    vector, not a scalar). Dimension sizes are read down the first element of
    each axis, matching LabVIEW's rectangular arrays; an empty axis is size 0."""
    if ndims <= 1:
        return len(a)
    sizes = []
    cur = a
    for _ in range(ndims):
        sizes.append(len(cur) if isinstance(cur, (list, tuple)) else 0)
        cur = cur[0] if isinstance(cur, (list, tuple)) and cur else []
    return sizes
