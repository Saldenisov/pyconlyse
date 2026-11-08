"""Isolated controller projections for two statically unreachable saved VIs.

No integration into root initialization or hardware adapters is permitted
by this module. Public error indicator defaults and standard DAQ/Mean
semantics are not inferred. External returns are supplied in-memory data.
"""

from dataclasses import dataclass

from .boundary import (
    UNASSIGNED,
    UNSUPPLIED,
    UNWIRED,
    BoundaryCall,
    ErrorCluster,
    InitializerResult,
    MissingValue,
    SampleClockInputs,
    SampleMatrix,
    ScriptedBoundary,
    SourceVi,
    TaskReference,
    require_boundary,
    require_error,
)
from .read_ni6071e import C1_OFFSETS, C1_SLOPES

INIT_SOURCE = SourceVi(
    "1_ACQ_INIT_NI6259.vi",
    "A8DE6D36566F3EF97F0B69B5C7E2AC6E8BCEAF8C48667D60A565DE05A09A323E",
)
READ_SOURCE = SourceVi(
    "1_ACQ_READ_NI6259.vi",
    "89BC9BE30E5F216474E25F47DF562316F970E0AF118AD5E24FC1E9E0956B7963",
)


def initialize(
    boundary: ScriptedBoundary,
    *,
    clock: SampleClockInputs,
    error_in: ErrorCluster,
    public_error_out_seed: ErrorCluster | MissingValue = UNASSIGNED,
) -> InitializerResult:
    require_boundary(boundary)
    require_error(error_in)  # Saved input has no outgoing wire.
    if type(clock) is not SampleClockInputs:
        raise TypeError("clock requires explicit SampleClockInputs")
    if (
        type(public_error_out_seed) is not ErrorCluster
        and public_error_out_seed is not UNASSIGNED
    ):
        raise TypeError("public_error_out_seed requires ErrorCluster or UNASSIGNED")
    offset = len(boundary.calls)
    created = boundary.invoke(
        INIT_SOURCE,
        "2629",
        "3",
        "create_task",
        error_in=UNWIRED,
        name="C1_NI6220",
        auto_cleanup=True,
    )
    for i in range(8):
        # No task/error shift registers: all iterations use Create returns.
        result = boundary.invoke(
            INIT_SOURCE,
            "2818",
            "2798",
            "create_ai_voltage_channel",
            iteration=i,
            task_in=created.task,
            error_in=created.error,
            physical_channel=f"11/ai{i}",
            minimum=-0.2,
            maximum=0.2,
            terminal_configuration_code=0x277A,
            units_code=0x286C,
            polymorphic_selector="02",
        )
    result = boundary.invoke(
        INIT_SOURCE,
        "2393",
        "3",
        "configure_sample_clock",
        task_in=result.task,
        error_in=result.error,
        source="OnboardClock",
        rate_hz=clock.rate_hz,
        samples_per_channel=clock.samples_per_channel,
        sample_mode_code=0x27C2,
        edge_code=0x2828,
        polymorphic_selector="02",
    )
    result = boundary.invoke(
        INIT_SOURCE,
        "2454",
        "3",
        "configure_start_trigger_none",
        task_in=result.task,
        error_in=result.error,
        polymorphic_selector="02",
    )
    result = boundary.invoke(
        INIT_SOURCE,
        "2561",
        "3",
        "set_read_properties",
        task_in=result.task,
        error_in=result.error,
        relative_to_code=0x28B9,
        auto_start=True,
        relative_to_property_code=6410,
        auto_start_property_code=6182,
    )
    return InitializerResult(
        INIT_SOURCE,
        (result.task,),
        public_error_out_seed,
        result.error,
        boundary.calls[offset:],
    )


def project_means(
    means: tuple[float, ...],
    *,
    calibrated: bool = False,
) -> tuple[float, ...]:
    """Saved False arm; True is an explicitly inactive test projection.

    Multiply then Add use elementwise common lengths, not scalar repair or
    padding. Inputs already represent at most eight supplied Mean results.
    NaN/Inf and signed zero are not made finite by a Python-only safety rule.
    """
    if (
        type(means) is not tuple
        or len(means) > 8
        or any(type(v) not in (int, float) for v in means)
    ):
        raise TypeError("at most eight supplied DBL Mean results required")
    if type(calibrated) is not bool:
        raise TypeError("calibration projection selector requires bool")
    values = tuple(float(v) for v in means)
    if not calibrated:
        return values
    products = tuple(v * s for v, s in zip(values, C1_SLOPES))
    return tuple(p + a for p, a in zip(products, C1_OFFSETS))


@dataclass(frozen=True)
class ReadResult:
    source: SourceVi
    bank: tuple[float, ...] | MissingValue
    mean_returns: tuple[float | MissingValue, ...] | MissingValue
    error_out: ErrorCluster
    calls: tuple[BoundaryCall, ...]


def read(
    boundary: ScriptedBoundary,
    *,
    task: TaskReference,
    samples_per_channel: int,
    error_in: ErrorCluster,
) -> ReadResult:
    """Record Read then up to eight Mean calls; neither error gates data.

    Mean input rows are not truncated by requested samples. Mean returns,
    including empty-row/NaN results, must be supplied separately. Missing
    Read data leaves loop count unknown; returned empty data yields zero
    iterations and an empty bank, not missing data or eight zero values.
    """
    require_boundary(boundary)
    require_error(error_in)
    if type(task) is not TaskReference:
        raise TypeError("simulation task reference required")
    if (
        type(samples_per_channel) is not int
        or not -(2**31) <= samples_per_channel < 2**31
    ):
        raise ValueError("Python-only guard: I32 sample count required")
    offset = len(boundary.calls)
    returned = boundary.invoke(
        READ_SOURCE,
        "1269",
        "3",
        "read_analog_2d_dbl_many_channels_many_samples",
        task_in=task,
        error_in=error_in,
        samples_per_channel=samples_per_channel,
        timeout_seconds=-1.0,
        polymorphic_selector="08",
    )
    if returned.data is UNSUPPLIED:
        return ReadResult(
            READ_SOURCE, UNSUPPLIED, UNSUPPLIED, returned.error, boundary.calls[offset:]
        )
    if type(returned.data) is not SampleMatrix:
        raise TypeError("NI6259 Read return requires SampleMatrix or UNSUPPLIED")
    means = []
    for i, row in enumerate(returned.data.rows[:8]):
        mean = boundary.invoke(
            READ_SOURCE,
            "359",
            "639",
            "mean_dbl",
            iteration=i,
            samples=row,
        )
        if mean.data is UNSUPPLIED:
            means.append(UNSUPPLIED)
        elif (
            type(mean.data) is tuple
            and len(mean.data) == 1
            and type(mean.data[0]) in (int, float)
        ):
            means.append(float(mean.data[0]))
        else:
            raise TypeError("Mean return requires one supplied DBL value or UNSUPPLIED")
    bank = UNSUPPLIED if UNSUPPLIED in means else project_means(tuple(means))
    return ReadResult(
        READ_SOURCE, bank, tuple(means), returned.error, boundary.calls[offset:]
    )
