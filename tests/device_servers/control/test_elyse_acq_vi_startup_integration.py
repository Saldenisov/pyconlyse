"""Cross-frame initialization contracts with supplied returns and no transport."""

from itertools import product

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    UNWIRED,
    CallKey,
    ErrorCluster,
    SampleClockInputs,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.initialization_caller import (
    STAGES,
    InitializerFixture,
)
from DeviceServers.control.elyse_acq.vi_simulation.psp_discovery import (
    DiscoveryChild,
    VariableToken,
)
from DeviceServers.control.elyse_acq.vi_simulation.startup_integration import (
    record_returning_startup_suffix,
)
from DeviceServers.control.elyse_acq.vi_simulation.startup_postinit import RESETS
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import StopMemory

FAULT = ErrorCluster(True, -901, "supplied failure")
VDM = tuple(i % 3 == 0 for i in range(80))


def inputs(statuses=(False,) * 4):
    fixtures = tuple(
        InitializerFixture(
            tuple(
                TaskReference(f"possibly-invalid:{uid}:{i}")
                for i in range(sum(count for _, count in banks))
            ),
            FAULT if status else NO_ERROR,
        )
        for status, (uid, _, _, _, banks) in zip(statuses, STAGES)
    )
    return dict(
        initializer_fixtures=fixtures,
        initializer_clear_returns={
            stage[2]: NO_ERROR for status, stage in zip(statuses, STAGES) if status
        },
        pilot_read_error=NO_ERROR,
        discovery_error=NO_ERROR,
        discovery_children=(),
        clock=SampleClockInputs(8123.5, 17),
        vdm_before=VDM,
        stop_before=StopMemory(True, True, True, True),
    )


def test_returning_frame_order_task_ownership_and_initial_ht_command():
    result = record_returning_startup_suffix(ScriptedBoundary(), **inputs())
    assert len(result.calls) == 49
    assert len({c.key for c in result.calls}) == 49
    assert result.calls == (
        result.command_publication.calls
        + result.initial_io.calls
        + result.postinit.calls
        + result.status_publication.calls
    )
    tasks = dict(result.task_banks)
    assert tuple(c.task_in for c in result.initial_io.analog.calls) == (
        tasks[23],
        tasks[24],
    )
    assert tuple(c.task_in for c in result.initial_io.digital.calls) == tasks[22]
    assert tuple(c.task_in for c in result.initial_io.output.calls) == tasks[25]
    assert len(tasks[21]) == 8  # counter task references retained, not readiness
    assert dict(result.command_publication.local_assignments)[12][0] == 6.5
    assert result.initial_io.output.requested_voltages[3][0] == 3.25
    assert result.status_publication.local_assignments == ((7, (True,) + VDM[1:]),)
    assert result.status_publication.calls[0].args["data"] == (False,) * 29
    assert result.status_publication.calls[1].args["data"] == (False,) * 77
    assert result.stop_reset.after == StopMemory(True, False, False, True)
    assert result.postinit.local_assignments[-4:] == RESETS
    assert result.status_publication.independent_wait_ms == 100


def test_all_81_initializer_clear_status_patterns_leave_suffix_present():
    count = 0
    for statuses in product((False, True), repeat=4):
        params = inputs(statuses)
        clear_keys = tuple(params["initializer_clear_returns"])
        for clear_statuses in product((False, True), repeat=len(clear_keys)):
            params["initializer_clear_returns"] = {
                key: FAULT if status else NO_ERROR
                for key, status in zip(clear_keys, clear_statuses)
            }
            result = record_returning_startup_suffix(ScriptedBoundary(), **params)
            assert len(result.calls) == 49
            assert result.pilot.original_read_error is NO_ERROR
            # Pilot returned error is independently supplied, not synthesized
            # from its incoming sequence-local 1063 cluster.
            final_init = FAULT if statuses[-1] else NO_ERROR
            if statuses[-1]:
                final_init = params["initializer_clear_returns"]["1843"]
            assert result.initializers.next_read_error == final_init
            assert dict(result.status_publication.local_assignments)[7][0] is True
            assert result.stop_reset.after.stop is True
            assert result.stop_reset.after.general_stop is True
            count += 1
    assert count == 81


@pytest.mark.parametrize("retry_status", [False, True])
@pytest.mark.parametrize("final_clear_status", [False, True])
def test_replacement_ai_tasks_do_not_replace_original_pilot_status(
    retry_status, final_clear_status
):
    params = inputs()
    replacement = InitializerFixture(
        (TaskReference("replacement C1"), TaskReference("replacement C2")),
        FAULT if retry_status else NO_ERROR,
    )
    clears = {uid: NO_ERROR for uid in ("2134", "4034", "7931")}
    if retry_status:
        clears["2268"] = FAULT if final_clear_status else NO_ERROR
    params.update(
        pilot_read_error=FAULT,
        fallback_result=replacement,
        fallback_clear_returns=clears,
    )
    result = record_returning_startup_suffix(ScriptedBoundary(), **params)
    assert tuple(c.task_in for c in result.initial_io.analog.calls) == replacement.tasks
    assert result.pilot.sequence_local_306 == (
        clears["2268"] if retry_status else replacement.error_out
    )
    assert dict(result.status_publication.local_assignments)[7] == (False,) + VDM[1:]
    assert result.initial_io.analog.calls[0].error_in is NO_ERROR
    assert result.initial_io.output.requested_voltages[3][0] == 3.25
    assert len(result.calls) == 49


def test_discovery_errors_and_returned_cardinality_are_not_startup_gates():
    params = inputs()
    child = DiscoveryChild(
        VariableToken("enumerated"),
        VariableToken("property"),
        "unknown supplied type",
        FAULT,
        VariableToken("failed-open-token"),
        FAULT,
    )
    params.update(discovery_error=FAULT, discovery_children=(child,))
    result = record_returning_startup_suffix(ScriptedBoundary(), **params)
    assert result.discovery.unused_final_error is FAULT
    assert dict(result.local_assignments)[61] == (child.opened_reference,)
    assert len(result.calls) == 49
    assert result.command_publication.calls[0].error_in is UNWIRED
    assert dict(result.status_publication.local_assignments)[7][0] is True


def test_all_8_fallback_clear_fault_patterns_retain_replacement_and_raw_error():
    for statuses in product((False, True), repeat=3):
        params = inputs()
        replacement = InitializerFixture(
            (TaskReference("retry C1"), TaskReference("retry C2")), NO_ERROR
        )
        clears = {
            uid: FAULT if status else NO_ERROR
            for uid, status in zip(("2134", "4034", "7931"), statuses)
        }
        params.update(
            pilot_read_error=FAULT,
            fallback_result=replacement,
            fallback_clear_returns=clears,
        )
        result = record_returning_startup_suffix(ScriptedBoundary(), **params)
        assert result.pilot.steps[3].error_in is clears["7931"]
        assert result.pilot.sequence_local_306 is NO_ERROR
        assert dict(result.task_banks)[23] == replacement.tasks[0]
        assert dict(result.status_publication.local_assignments)[7][0] is False
        assert len(result.calls) == 49


def test_every_suffix_call_fault_preserves_reset_and_raw_pilot_flag_contract():
    baseline = record_returning_startup_suffix(ScriptedBoundary(), **inputs())
    for call in baseline.calls:
        boundary = ScriptedBoundary(errors={call.key: FAULT})
        result = record_returning_startup_suffix(boundary, **inputs())
        boundary.assert_all_fixtures_used()
        assert tuple(c.key for c in result.calls) == tuple(
            c.key for c in baseline.calls
        )
        assert result.stop_reset.after == baseline.stop_reset.after
        assert result.postinit.local_assignments[-4:] == RESETS
        assert dict(result.status_publication.local_assignments)[7][0] is True
        assert result.command_publication.calls[0].error_in is UNWIRED
        assert result.initial_io.analog.calls[0].error_in is NO_ERROR
        assert result.status_publication.calls[0].error_in is UNWIRED
        assert result.initial_io.output.requested_voltages[3][0] == 3.25


def test_final_publication_failure_has_no_synthetic_handler_or_stop_assignment():
    key = CallKey("0_ACQ_ELYSE.vi", "27194")
    boundary = ScriptedBoundary(errors={key: FAULT})
    result = record_returning_startup_suffix(boundary, **inputs())
    boundary.assert_all_fixtures_used()
    assert result.status_publication.final_error is FAULT
    assert result.calls[-1].key == key
    assert not {30, 47}.intersection(i for i, _ in result.local_assignments)


@pytest.mark.parametrize(
    "name,bad",
    [
        ("clock", None),
        ("vdm_before", (False,) * 79),
        ("vdm_before", (0,) * 80),
        ("stop_before", None),
        ("initializer_fixtures", None),
        ("pilot_read_error", None),
        ("discovery_error", None),
        ("discovery_children", []),
    ],
)
def test_invalid_prefix_snapshots_rejected_before_boundary_requests(name, bad):
    params = inputs()
    params[name] = bad
    boundary = ScriptedBoundary()
    with pytest.raises((TypeError, ValueError)):
        record_returning_startup_suffix(boundary, **params)
    assert not boundary.calls


def test_no_real_boundary_and_no_implicit_fallback_results():
    with pytest.raises(TypeError):
        record_returning_startup_suffix(object(), **inputs())
    params = inputs()
    params["pilot_read_error"] = FAULT
    boundary = ScriptedBoundary()
    with pytest.raises(TypeError, match="replacement"):
        record_returning_startup_suffix(boundary, **params)
    assert not boundary.calls
