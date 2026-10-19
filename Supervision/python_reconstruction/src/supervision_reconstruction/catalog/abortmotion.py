"""Non-executable reconstruction stub for AbortMotion.vi."""

from __future__ import annotations

from .runtime import unverified_behavior

IDENTITY = 'supervision-vi:63cfbd2708d6f680'
SOURCE_SHA256 = '63CFBD2708D6F6801E7A37191336D68C9512A8B2A08D3C48D997E046853B311C'
CONVERSION_STATE = 'open'
DOMAIN_MODEL = None

def reconstruct(*args: object, **kwargs: object) -> None:
    """Block execution until this VI has a reviewed, safe reconstruction."""
    del args, kwargs
    unverified_behavior(IDENTITY, CONVERSION_STATE)
