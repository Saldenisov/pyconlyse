"""Pure predicates transcribed from saved Acquisition controller wiring."""

from __future__ import annotations

from typing import Sequence


def cooling_flow_trip(c4_in: Sequence[bool], c3_in: Sequence[bool]) -> bool:
    """Evaluate saved Timeout/subframe-3 Boolean guard on raw logical bits.

    Field names do not establish electrical active-high/low polarity. This
    predicate is not a complete radioprotection or hardware safety model.
    """
    if len(c4_in) != 64 or any(type(bit) is not bool for bit in c4_in):
        raise ValueError("C4_IN_DIO96 must contain exactly 64 Boolean fields")
    if len(c3_in) != 56 or any(type(bit) is not bool for bit in c3_in):
        raise ValueError("C3_IN_DIO96 must contain exactly 56 Boolean fields")
    return (c4_in[19] or c4_in[38]) and (
        not c3_in[0] or not c3_in[6]
    )
