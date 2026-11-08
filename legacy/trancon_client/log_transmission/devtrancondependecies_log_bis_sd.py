from __future__ import annotations
from typing import Any, NamedTuple
from .. import _lv_runtime as _lv

class LogBisSdResult(NamedTuple):
    output_logxlog1x: list[float]

def _log_bis_sd(transmission: list[float] | None=None) -> LogBisSdResult:
    transmission = transmission or []
    quotient = _lv.real64_divide(1.0, transmission)
    logx = _lv.log10(quotient)
    return LogBisSdResult(output_logxlog1x=logx)