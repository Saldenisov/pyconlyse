"""Pure returned-error projection from TPG300 suppress warning.vi.

Source SHA256 1F2EF5A5BA6309D0077D9B7E944B4DA8C9F08DEE08D95B859D70FA91C4FC7FC9.
No assumption that a positive code is reachable with either status polarity.
"""

from .boundary import NO_ERROR, ErrorCluster

SUPPRESSED_CODE = 0x3FFF0006


def suppress_warning(error: ErrorCluster) -> ErrorCluster:
    if type(error) is not ErrorCluster:
        raise TypeError("explicit error-cluster snapshot required")
    return NO_ERROR if error.code == SUPPRESSED_CODE else error
