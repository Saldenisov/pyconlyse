"""Caller projection preserves error arms without assuming NI success."""

from itertools import product

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    UNWIRED,
    ErrorCluster,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.initialization_caller import (
    AI_ARGUMENTS,
    STAGES,
    InitializerFixture,
    project_ai_test_frame,
    project_initializer_frame,
)


def fixtures(statuses):
    return tuple(
        InitializerFixture(
            tuple(
                TaskReference(f"supplied:{uid}:{i}")
                for i in range(sum(n for _, n in banks))
            ),
            ErrorCluster(status, 100 + j, f"init:{uid}"),
        )
        for j, (status, (uid, _, _, _, banks)) in enumerate(zip(statuses, STAGES))
    )


def test_all_16_initializer_arm_patterns_and_all_selected_clear_statuses():
    count = 0
    for statuses in product((False, True), repeat=4):
        supplied = fixtures(statuses)
        clear_uids = [s[2] for status, s in zip(statuses, STAGES) if status]
        for returned_statuses in product((False, True), repeat=len(clear_uids)):
            clears = {
                uid: ErrorCluster(status, -200 + i, f"clear:{uid}")
                for i, (uid, status) in enumerate(zip(clear_uids, returned_statuses))
            }
            actual = project_initializer_frame(supplied, clear_returns=clears)
            position = 0
            prior = UNWIRED
            for fixture, (uid, name, clear_uid, _, banks) in zip(supplied, STAGES):
                stage = actual.steps[position]
                assert (
                    stage.node_uid,
                    stage.operation,
                    stage.error_in,
                    stage.error_out,
                ) == (uid, name, prior, fixture.error_out)
                assert stage.arguments == (AI_ARGUMENTS if uid == "262" else ())
                assert tuple(bank for bank, _ in stage.local_assignments) == tuple(
                    b for b, _ in banks
                )
                flattened = tuple(
                    t
                    for _, value in stage.local_assignments
                    for t in (value if type(value) is tuple else (value,))
                )
                assert flattened == fixture.tasks
                position += 1
                prior = fixture.error_out
                if prior.status:
                    clear = actual.steps[position]
                    assert (clear.node_uid, clear.error_in, clear.error_out) == (
                        clear_uid,
                        prior,
                        clears[clear_uid],
                    )
                    assert clear.local_assignments == ()
                    prior = clears[clear_uid]
                    position += 1
            assert position == len(actual.steps)
            assert actual.next_read_error == prior
            count += 1
    assert count == 81


def test_warning_codes_pass_unchanged_and_no_default_clear_success():
    supplied = fixtures((False,) * 4)
    actual = project_initializer_frame(supplied, clear_returns={})
    assert len(actual.steps) == 4
    assert actual.steps[2].error_in is supplied[1].error_out
    assert actual.steps[2].error_in.code == 101
    with pytest.raises(ValueError, match="exactly"):
        project_initializer_frame(
            fixtures((True, False, False, False)), clear_returns={}
        )


@pytest.mark.parametrize("bad", [None, (), [], (object(),) * 4])
def test_invalid_fixtures_rejected(bad):
    with pytest.raises(TypeError):
        project_initializer_frame(bad, clear_returns={})


def test_opaque_task_count_and_clear_fixture_types_rejected():
    good = fixtures((False,) * 4)
    bad = (InitializerFixture(good[0].tasks[:-1], good[0].error_out),) + good[1:]
    with pytest.raises(ValueError, match="cardinality"):
        project_initializer_frame(bad, clear_returns={})
    with pytest.raises(ValueError, match="exactly"):
        project_initializer_frame(good, clear_returns={"383": ErrorCluster(False, 0)})
    with pytest.raises(TypeError, match="ErrorCluster"):
        project_initializer_frame(
            fixtures((True, False, False, False)), clear_returns={"383": False}
        )
    with pytest.raises(TypeError):
        InitializerFixture((object(),), ErrorCluster(False, 0))
    with pytest.raises(TypeError):
        InitializerFixture((), None)


@pytest.mark.parametrize("code", [-200284, -999, 0, 99])
@pytest.mark.parametrize("retry_status", [False, True])
def test_any_error_status_runs_fallback_but_original_error_is_retained(
    code, retry_status
):
    raw = ErrorCluster(True, code, "original pilot read")
    retry = fixtures((False, retry_status, False, False))[1]
    clears = {
        uid: ErrorCluster(False, i, uid)
        for i, uid in enumerate(("2134", "4034", "7931"))
    }
    if retry_status:
        clears["2268"] = ErrorCluster(False, 0, "final cleared fixture")
    actual = project_ai_test_frame(
        read_error=raw, fallback_result=retry, clear_returns=clears
    )
    assert actual.original_read_error is raw
    assert actual.original_read_error.status
    assert actual.sequence_local_306 == (
        clears["2268"] if retry_status else retry.error_out
    )
    assert [s.node_uid for s in actual.steps] == ["2134", "4034", "7931", "1198"] + (
        ["2268"] if retry_status else []
    )
    assert actual.steps[3].error_in == clears["7931"]
    assert actual.steps[3].arguments[:2] == (
        ("trigger_c1", "/1/20MHzTimebase"),
        ("trigger_c2", "/2/20MHzTimebase"),
    )
    assert actual.steps[3].local_assignments == (
        (23, retry.tasks[0]),
        (24, retry.tasks[1]),
    )


def test_warning_is_not_fallback_and_missing_clear_results_are_rejected():
    warning = ErrorCluster(False, -200284)
    result = project_ai_test_frame(read_error=warning)
    assert result.steps == ()
    assert result.sequence_local_306 is warning
    with pytest.raises(ValueError):
        project_ai_test_frame(
            read_error=warning, fallback_result=fixtures((False,) * 4)[1]
        )
    with pytest.raises(ValueError):
        project_ai_test_frame(
            read_error=ErrorCluster(True, 1),
            fallback_result=fixtures((False,) * 4)[1],
            clear_returns={},
        )
