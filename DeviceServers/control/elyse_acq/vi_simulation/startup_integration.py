"""Returning startup suffix from supplied prefix outcomes, never a launcher.

System Exec/time synchronization, native initializer calls, the pilot read and
discovery are NOT executed. Their returned values are explicit fixtures. The
saved empty Diagram Disable arm is assumed. All suffix boundary calls return;
independent branches use one allowed serial fixture order. No intervening
external/local mutation, native readiness, valid task or restart is inferred.
"""

from dataclasses import dataclass

from .boundary import (
    BoundaryCall,
    SampleClockInputs,
    ScriptedBoundary,
    TaskReference,
    require_boundary,
)
from .initialization_caller import (
    AiFallbackProjection,
    CallerProjection,
    project_ai_test_frame,
    project_initializer_frame,
)
from .psp_discovery import DiscoveryProjection, project_discovery_frame
from .runtime_io import RuntimeIoResult
from .rw_dio96 import DigitalOutputBanks
from .startup_io import record_initial_io
from .startup_postinit import PostInitResult, record_postinit
from .startup_publication import (
    StartupPublicationResult,
    publish_commands,
    publish_status,
)
from .stop_lifecycle import StopMemory, StopResetProjection, project_stop_reset
from .write_ni6703 import LogicalAoBanks


@dataclass(frozen=True)
class ReturningStartupResult:
    initializers: CallerProjection
    pilot: AiFallbackProjection
    discovery: DiscoveryProjection
    task_banks: tuple[tuple[int, object], ...]
    command_publication: StartupPublicationResult
    initial_io: RuntimeIoResult
    postinit: PostInitResult
    status_publication: StartupPublicationResult
    stop_reset: StopResetProjection
    local_assignments: tuple[tuple[int, object], ...]
    calls: tuple[BoundaryCall, ...]


def record_returning_startup_suffix(
    boundary: ScriptedBoundary,
    *,
    initializer_fixtures,
    initializer_clear_returns,
    pilot_read_error,
    discovery_error,
    discovery_children,
    clock: SampleClockInputs,
    vdm_before: tuple[bool, ...],
    stop_before: StopMemory,
    fallback_result=None,
    fallback_clear_returns=None,
) -> ReturningStartupResult:
    """Compose task ownership and separate error lanes across ordered frames.

    Initializer/fallback projections describe returning prefix calls only.
    Initial I/O receives the most recently assigned AI tokens, independent of
    their errors. Discovery's final error and the cleared pilot error are not
    startup abort conditions. Final VDM-A[0] uses the ORIGINAL pilot status.
    DPS/EPS zeros and TCP/Emergency resets are software assignments, not device
    acknowledgments. Stop30 and General47 are retained from supplied memory.

    Assignment listing is a fixture order/completed-frame postcondition, not
    an atomic commit or native within-frame schedule. The boundary records
    49 call sites, not 49 successful hardware or PSP operations. This function
    has no runtime entry, driver, transport, timer, callback or readiness gate.
    """
    require_boundary(boundary)
    if type(clock) is not SampleClockInputs:
        raise TypeError("explicit NI6220 clock snapshot required")
    if (
        type(vdm_before) is not tuple
        or len(vdm_before) != 80
        or any(type(v) is not bool for v in vdm_before)
    ):
        raise TypeError("explicit 80-Boolean VDM-A snapshot required")
    reset = project_stop_reset("post_init", stop_before)
    initializers = project_initializer_frame(
        initializer_fixtures, clear_returns=initializer_clear_returns
    )
    pilot = project_ai_test_frame(
        read_error=pilot_read_error,
        fallback_result=fallback_result,
        clear_returns=fallback_clear_returns,
    )
    discovery = project_discovery_frame(
        enumeration_error=discovery_error, children=discovery_children
    )
    prefix_assignments = tuple(
        item
        for step in initializers.steps + pilot.steps
        for item in step.local_assignments
    )
    tasks = dict(prefix_assignments)
    # These snapshots come from the checked projectors, not guessed bank order.
    analog_tasks: tuple[TaskReference, TaskReference] = (tasks[23], tasks[24])
    start = len(boundary.calls)
    commands = publish_commands(boundary)
    banks = dict(commands.local_assignments)
    io = record_initial_io(
        boundary,
        analog_tasks=analog_tasks,
        digital_tasks=tasks[22],
        output_tasks=tasks[25],
        digital_outputs=DigitalOutputBanks(tuple(banks[i] for i in (17, 15, 13))),
        analog_outputs=LogicalAoBanks(tuple(banks[i] for i in (9, 10, 11, 12))),
    )
    postinit = record_postinit(boundary, clock=clock)
    post_banks = dict(postinit.local_assignments)
    status = publish_status(
        boundary,
        raw_pilot_error=pilot.original_read_error,
        local_snapshots={36: post_banks[36], 44: post_banks[44], 7: vdm_before},
    )
    return ReturningStartupResult(
        initializers,
        pilot,
        discovery,
        tuple((i, tasks[i]) for i in (21, 23, 24, 22, 25)),
        commands,
        io,
        postinit,
        status,
        reset,
        prefix_assignments
        + ((61, discovery.local_61),)
        + commands.local_assignments
        + io.local_assignments
        + postinit.local_assignments
        + status.local_assignments,
        boundary.calls[start:],
    )
