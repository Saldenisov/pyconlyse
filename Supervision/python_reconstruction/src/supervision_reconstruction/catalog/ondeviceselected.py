"""Non-executable reconstruction stub for OnDeviceSelected.vi."""

from __future__ import annotations

from .runtime import unverified_behavior

IDENTITY = 'supervision-vi:0ffae304aaad2bf3'
SOURCE_SHA256 = '0FFAE304AAAD2BF3B72C34389E75F7C2F70E2E1929447F6B96B35C8DD853E012'
CONVERSION_STATE = 'open'
DOMAIN_MODEL = None

def reconstruct(*args: object, **kwargs: object) -> None:
    """Block execution until this VI has a reviewed, safe reconstruction."""
    del args, kwargs
    unverified_behavior(IDENTITY, CONVERSION_STATE)
