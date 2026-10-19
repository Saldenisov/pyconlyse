"""Explicit persisted NI6071E fixtures, not native loading or live defaults.

The initializer stores ten samples; the reader stores one thousand. Neither
stored error indicator is a demonstrated external return. The initializer's
unwritten public output is seeded only when a caller explicitly supplies it.
"""

from dataclasses import dataclass

from .boundary import NO_ERROR, ErrorCluster, SampleClockInputs, require_error
from .initialization_caller import AiFallbackProjection, project_ai_test_frame
from .read_ni6071e import AnalogReadResult, read


@dataclass(frozen=True)
class SavedNi6071eSnapshot:
    reader_samples_per_channel: int
    reader_error_in: ErrorCluster
    reader_error_out: ErrorCluster
    initializer_clock: SampleClockInputs
    trigger_c1: str
    trigger_c2: str
    initializer_error_in: ErrorCluster
    initializer_public_error_out: ErrorCluster

    def __post_init__(self):
        if (
            type(self.reader_samples_per_channel) is not int
            or not -(2**31) <= self.reader_samples_per_channel < 2**31
        ):
            raise TypeError("explicit I32 saved reader sample count required")
        if type(self.initializer_clock) is not SampleClockInputs:
            raise TypeError("explicit saved initializer clock required")
        if type(self.trigger_c1) is not str or type(self.trigger_c2) is not str:
            raise TypeError("explicit saved trigger strings required")
        for value in (
            self.reader_error_in,
            self.reader_error_out,
            self.initializer_error_in,
            self.initializer_public_error_out,
        ):
            require_error(value)


def saved_source_ni6071e_snapshot() -> SavedNi6071eSnapshot:
    """Read-only source fixture; never automatically applied to other models."""
    return SavedNi6071eSnapshot(
        1000,
        NO_ERROR,
        NO_ERROR,
        SampleClockInputs(5000.0, 10),
        "/1/PFI0",
        "/2/PFI0",
        NO_ERROR,
        NO_ERROR,
    )


@dataclass(frozen=True)
class PilotTestResult:
    read: AnalogReadResult
    fallback: AiFallbackProjection


def record_pilot_test(
    boundary,
    *,
    saved: SavedNi6071eSnapshot,
    tasks,
    initializer_error: ErrorCluster,
    fallback_result=None,
    clear_returns=None,
) -> PilotTestResult:
    """Two returning Read call nodes, then the original error-dependent suffix.

    Explicit opt-in to the saved reader-count fixture. The incoming error is
    supplied from sequence local1063, not replaced by the saved reader input.
    Read errors come from ScriptedBoundary, NOT the persisted output indicator.
    No task clear/reinitialization is executed; that suffix is a pure projection.
    Pilot data is inspectable but has no new root bank19/20 assignment here.
    First I/O later needs a separate recorder to distinguish repeated helper
    call sites; this function does not execute an entire startup or scheduler.
    """
    if type(saved) is not SavedNi6071eSnapshot:
        raise TypeError("explicit SavedNi6071eSnapshot required")
    result = read(
        boundary,
        tasks=tasks,
        samples_per_channel=saved.reader_samples_per_channel,
        error_in=initializer_error,
    )
    fallback = project_ai_test_frame(
        read_error=result.error_out,
        fallback_result=fallback_result,
        clear_returns=clear_returns,
    )
    return PilotTestResult(result, fallback)
