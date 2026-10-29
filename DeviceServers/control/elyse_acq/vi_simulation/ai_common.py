"""Shared ordinary-tunnel AI configuration, not an accumulated error loop."""

from dataclasses import dataclass

from .boundary import (
    BoundaryReturn,
    ErrorCluster,
    MissingValue,
    SampleClockInputs,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
)


@dataclass(frozen=True)
class AiTaskSpec:
    device: int
    name: str
    frame_uid: str
    body_uid: str
    create_uid: str
    channel_uid: str
    timing_uid: str
    trigger_uid: str
    properties_uid: str
    maximums: tuple[float, ...]


def configure_task(
    boundary: ScriptedBoundary,
    source: SourceVi,
    spec: AiTaskSpec,
    *,
    clock: SampleClockInputs,
    trigger_source: str,
    create_error_in: ErrorCluster | MissingValue,
) -> BoundaryReturn:
    require_boundary(boundary)
    if type(clock) is not SampleClockInputs:
        raise TypeError("clock requires explicit SampleClockInputs")
    if type(trigger_source) is not str:
        raise TypeError("trigger_source requires str")
    created = boundary.invoke(
        source,
        spec.create_uid,
        spec.frame_uid,
        "create_task",
        error_in=create_error_in,
        name=spec.name,
        auto_cleanup=True,
    )
    for i, maximum in enumerate(spec.maximums):
        # Both task and error inputs are ordinary tunnels: every iteration uses
        # Create Task returns, not the preceding channel call's returns.
        result = boundary.invoke(
            source,
            spec.channel_uid,
            spec.body_uid,
            "create_ai_voltage_channel",
            iteration=i,
            task_in=created.task,
            error_in=created.error,
            physical_channel=f"{spec.device}/ai{i}",
            minimum=-maximum,
            maximum=maximum,
            terminal_configuration_code=0x2763,
            units_code=0x286C,
            polymorphic_selector="02",
        )
    result = boundary.invoke(
        source,
        spec.timing_uid,
        spec.frame_uid,
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
        source,
        spec.trigger_uid,
        spec.frame_uid,
        "configure_start_trigger",
        task_in=result.task,
        error_in=result.error,
        source=trigger_source,
        edge_code=0x2828,
        polymorphic_selector="03",
    )
    return boundary.invoke(
        source,
        spec.properties_uid,
        spec.frame_uid,
        "set_read_properties",
        task_in=result.task,
        error_in=result.error,
        relative_to_code=0x28B9,
        auto_start=True,
        relative_to_property_code=6410,
        auto_start_property_code=6182,
    )
