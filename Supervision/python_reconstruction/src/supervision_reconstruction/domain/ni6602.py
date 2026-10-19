"""Pure NI-6602 timing plans reconstructed from two SuperVision VIs.

No function here imports nidaqmx or creates a task.  It records wired timing
constants and the visible stop/write/start ordering for later adapter work.
The PFI routing comes from the eight full-screen captures
``analysis/screenshots/1_SUP_INIT_NI6602_frame_{0..7}_ctr{0..7}_full.png``:
PFI10 is the 50 Hz gate/start-edge trigger and PFI11 the 20 MHz timebase.
The actual timebase frequency, reset policy, and hardware applicability remain
unresolved contracts and are therefore not hidden behind an adapter.
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple


I32_MIN = -(2**31)
I32_MAX = 2**31 - 1


@dataclass(frozen=True)
class CounterPulsePlan:
    """One of the eight initialization frames, expressed without driver calls."""

    label: str
    counter: str
    initial_delay_ticks: int
    low_ticks: int
    high_ticks: int
    # Full-screen INIT frames label PFI10 as ``Gate 50Hz`` on the DAQmx Start
    # Digital Edge trigger and PFI11 as ``Source 20MHz`` on the pulse-ticks
    # counter timebase property.
    trigger_source: Optional[str] = "/Dev1/PFI10"
    counter_timebase_source: Optional[str] = "/Dev1/PFI11"
    trigger_edge: Optional[str] = "rising"
    counter_timebase_rate_hz: Optional[float] = None
    counter_timebase_active_edge: Optional[str] = "rising"
    idle_state: Optional[str] = "low"
    retriggerable: bool = True
    finite_samples: int = 1


COUNTER_INITIALIZATION_PLAN: Tuple[CounterPulsePlan, ...] = (
    CounterPulsePlan("laser_hf", "Dev1/ctr0", 0, 7, 7),
    CounterPulsePlan("imac", "Dev1/ctr1", 0, 43520, 2000),
    CounterPulsePlan("laser", "Dev1/ctr2", 0, 40166, 200),
    CounterPulsePlan("oscilloscope_1", "Dev1/ctr3", 0, 43500, 200),
    CounterPulsePlan("oscilloscope_2", "Dev1/ctr4", 0, 43500, 2000),
    CounterPulsePlan("detection_1", "Dev1/ctr5", 0, 10000, 10000),
    CounterPulsePlan("detection_2", "Dev1/ctr6", 0, 6, 200),
    CounterPulsePlan("machine", "Dev1/ctr7", 0, 43500, 2000),
)


@dataclass(frozen=True)
class PulseUpdatePlan:
    """A driver-agnostic representation of the runtime update order."""

    initial_delay_ticks: int
    low_ticks: int
    high_ticks: int
    poll_interval_ms: int = 1
    ordering: Tuple[str, ...] = (
        "wait_until_pulse_done",
        "stop_task",
        "write_initial_delay",
        "write_low_ticks",
        "write_high_ticks",
        "start_task",
    )


def legacy_value_to_ticks(value: float) -> int:
    """Apply an explicit, deterministic evidence-model conversion policy.

    The diagram visibly multiplies a DBL input by 20 before an I32 conversion.
    It does not, by itself, prove a physical unit or the exact LabVIEW handling
    of ties/overflow.  This pure model therefore uses Python nearest-even
    rounding and saturation to signed-I32 bounds as an explicit policy, not a
    runtime-equivalence claim.  Non-finite values are rejected.
    """

    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("legacy timing value must be finite and non-boolean")
    ticks = int(round(value * 20.0))
    return max(I32_MIN, min(I32_MAX, ticks))


def microseconds_to_ticks(value_microseconds: float) -> int:
    """Deprecated compatibility alias; this name does not establish units."""

    return legacy_value_to_ticks(value_microseconds)


def make_pulse_update_plan(
    delay_value: float, width_value: float
) -> PulseUpdatePlan:
    """Make the runtime update plan without touching a DAQmx task.

    The VI visibly writes the converted delay to both ``InitialDelay`` and
    ``LowTicks``, and the converted width to ``HighTicks``.
    """

    delay_ticks = legacy_value_to_ticks(delay_value)
    return PulseUpdatePlan(
        initial_delay_ticks=delay_ticks,
        low_ticks=delay_ticks,
        high_ticks=legacy_value_to_ticks(width_value),
    )
