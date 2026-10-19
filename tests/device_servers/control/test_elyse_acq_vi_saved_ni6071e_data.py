"""Explicit source snapshots and returning pilot/initialization composition."""

from dataclasses import FrozenInstanceError, replace
from itertools import product

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    UNASSIGNED,
    CallKey,
    ErrorCluster,
    SampleMatrix,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.init_ni6071e import initialize
from DeviceServers.control.elyse_acq.vi_simulation.initialization_caller import (
    STAGES,
    InitializerFixture,
    project_initializer_frame,
)
from DeviceServers.control.elyse_acq.vi_simulation.read_ni6071e import SOURCE
from DeviceServers.control.elyse_acq.vi_simulation.saved_ni6071e_data import (
    record_pilot_test,
    saved_source_ni6071e_snapshot,
)
from DeviceServers.control.elyse_acq.vi_simulation.startup_integration import (
    record_returning_startup_suffix,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import StopMemory

FAULT = ErrorCluster(True, -987, "supplied read fault")
TASKS = (TaskReference("C1 fixture"), TaskReference("C2 fixture"))
KEYS = tuple(CallKey(SOURCE.name, uid) for uid in ("1269", "269"))


def test_saved_snapshot_distinguishes_reader_count_and_initializer_clock():
    saved = saved_source_ni6071e_snapshot()
    assert saved.reader_samples_per_channel == 1000
    assert saved.initializer_clock.samples_per_channel == 10
    assert saved.initializer_clock.rate_hz == 5000.0
    assert (saved.trigger_c1, saved.trigger_c2) == ("/1/PFI0", "/2/PFI0")
    assert saved.initializer_public_error_out == NO_ERROR
    with pytest.raises(FrozenInstanceError):
        saved.reader_samples_per_channel = 10


def test_pilot_requests_1000_samples_but_does_not_reset_supplied_incoming_error():
    incoming = ErrorCluster(False, 987, "supplied initializer warning")
    result = record_pilot_test(
        ScriptedBoundary(),
        saved=saved_source_ni6071e_snapshot(),
        tasks=TASKS,
        initializer_error=incoming,
    )
    assert len(result.read.calls) == 2
    assert result.fallback.steps == ()
    for call in result.read.calls:
        assert call.error_in is incoming
        assert call.args["samples_per_channel"] == 1000
        assert call.args["timeout_seconds"] == 1.0
    assert result.fallback.original_read_error == incoming


def test_returned_pilot_data_is_projected_but_adds_no_root_readback_write():
    boundary = ScriptedBoundary(
        data={KEYS[0]: SampleMatrix(((1.0, 1.0),)), KEYS[1]: SampleMatrix(((2.0,),))}
    )
    result = record_pilot_test(
        boundary,
        saved=saved_source_ni6071e_snapshot(),
        tasks=TASKS,
        initializer_error=NO_ERROR,
    )
    boundary.assert_all_fixtures_used()
    assert result.read.banks == ((15.0,), (2.74,))
    assert not result.fallback.steps
    assert not hasattr(result.read, "local_assignments")


@pytest.mark.parametrize("statuses", tuple(product((False, True), repeat=2)))
def test_actual_supplied_read_errors_select_fallback_not_saved_error_out(statuses):
    saved = saved_source_ni6071e_snapshot()
    errors = {key: FAULT if status else NO_ERROR for key, status in zip(KEYS, statuses)}
    boundary = ScriptedBoundary(errors=errors)
    fallback = {}
    if any(statuses):
        fallback = dict(
            fallback_result=InitializerFixture(TASKS, NO_ERROR),
            clear_returns={uid: NO_ERROR for uid in ("2134", "4034", "7931")},
        )
    result = record_pilot_test(
        boundary, saved=saved, tasks=TASKS, initializer_error=NO_ERROR, **fallback
    )
    boundary.assert_all_fixtures_used()
    assert result.fallback.original_read_error.status is any(statuses)
    assert bool(result.fallback.steps) is any(statuses)
    assert result.fallback.sequence_local_306 == NO_ERROR
    assert saved.reader_error_out is NO_ERROR


def test_persisted_unwritten_initializer_output_is_only_an_explicit_seed():
    saved = saved_source_ni6071e_snapshot()
    args = dict(
        clock=saved.initializer_clock,
        trigger_c1=saved.trigger_c1,
        trigger_c2=saved.trigger_c2,
        error_in=saved.initializer_error_in,
    )
    unseeded = initialize(ScriptedBoundary(), **args)
    assert (
        unseeded.error_out is UNASSIGNED
    )  # merely importing snapshot does not seed it
    boundary = ScriptedBoundary(errors={unseeded.calls[-2].key: FAULT})
    seeded = initialize(
        boundary, **args, public_error_out_seed=saved.initializer_public_error_out
    )
    boundary.assert_all_fixtures_used()
    assert seeded.internal_error is FAULT
    assert seeded.error_out is NO_ERROR
    assert len(seeded.calls) == 137


def test_returning_pilot_and_startup_use_separate_phase_recorders_and_raw_error():
    saved = saved_source_ni6071e_snapshot()
    fixtures = tuple(
        InitializerFixture(
            tuple(TaskReference(f"{uid}:{i}") for i in range(sum(n for _, n in banks))),
            NO_ERROR,
        )
        for uid, _, _, _, banks in STAGES
    )
    caller = project_initializer_frame(fixtures, clear_returns={})
    banks = dict(item for step in caller.steps for item in step.local_assignments)
    replacement = InitializerFixture(
        (TaskReference("retry C1"), TaskReference("retry C2")), NO_ERROR
    )
    clears = {uid: NO_ERROR for uid in ("2134", "4034", "7931")}
    pilot_boundary = ScriptedBoundary(errors={KEYS[1]: FAULT})
    pilot = record_pilot_test(
        pilot_boundary,
        saved=saved,
        tasks=(banks[23], banks[24]),
        initializer_error=caller.next_read_error,
        fallback_result=replacement,
        clear_returns=clears,
    )
    suffix_boundary = ScriptedBoundary()
    suffix = record_returning_startup_suffix(
        suffix_boundary,
        initializer_fixtures=fixtures,
        initializer_clear_returns={},
        pilot_read_error=pilot.read.error_out,
        fallback_result=replacement,
        fallback_clear_returns=clears,
        discovery_error=NO_ERROR,
        discovery_children=(),
        clock=saved.initializer_clock,
        vdm_before=(False,) * 80,
        stop_before=StopMemory(False, False, False, False),
    )
    assert suffix.pilot == pilot.fallback
    assert tuple(c.task_in for c in suffix.initial_io.analog.calls) == replacement.tasks
    assert dict(suffix.status_publication.local_assignments)[7][0] is False
    assert suffix.initial_io.output.requested_voltages[3][0] == 3.25
    assert len(pilot_boundary.calls) == 2
    assert len(suffix_boundary.calls) == 49


@pytest.mark.parametrize("saved", [None, object()])
def test_untyped_source_snapshots_rejected_before_read(saved):
    boundary = ScriptedBoundary()
    with pytest.raises(TypeError, match="Snapshot"):
        record_pilot_test(
            boundary, saved=saved, tasks=TASKS, initializer_error=NO_ERROR
        )
    assert not boundary.calls


@pytest.mark.parametrize(
    "field,value",
    [
        ("reader_samples_per_channel", True),
        ("initializer_clock", None),
        ("trigger_c1", None),
        ("reader_error_out", None),
    ],
)
def test_snapshot_representation_guards_are_not_labview_fault_claims(field, value):
    with pytest.raises(TypeError):
        replace(saved_source_ni6071e_snapshot(), **{field: value})


def test_real_boundary_rejected_without_instantiating_driver():
    with pytest.raises(TypeError):
        record_pilot_test(
            object(),
            saved=saved_source_ni6071e_snapshot(),
            tasks=TASKS,
            initializer_error=NO_ERROR,
        )
