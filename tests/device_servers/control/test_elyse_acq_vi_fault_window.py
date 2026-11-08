"""Finite scheduling proof; no NI/PSP/VI execution, real scheduler or delays."""

from math import factorial

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.fault_window import (
    exhaustive_fault_window,
)
from DeviceServers.control.elyse_acq.vi_simulation.final_cleanup import (
    CleanupFrameReturned,
    CleanupHandler,
    CleanupStopReset,
    PspClose,
    TpgClose,
    replay_cleanup,
)
from DeviceServers.control.elyse_acq.vi_simulation.outer_stop_schedule import (
    FinalCleanupEntry,
    replay_outer_stop,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    project_stop_reset,
    replay_runtime,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_schedule import (
    ERROR_SITES,
    RUNTIME_LOOPS,
    BodyCompleted,
    ErrorArmEntry,
    LocalAssignment,
    OuterTcpRead,
    StopLocalRead,
)


@pytest.fixture(scope="module")
def outcomes():
    return exhaustive_fault_window(stop_before=False, tcp_before=False)


def replay_witness(witness, stop=False, tcp=False):
    """Independent literal-site replay, not the DP implementation."""
    literals = {
        "43027": (30, True),
        "43040": (45, True),
        "50011": (30, True),
        "50019": (45, True),
        "85095": (30, False),
        "68231": (45, False),
    }
    captured = {}
    assert len(witness) == len(set(witness)) == 11
    for action in witness:
        kind, uid = action.split(":")
        if kind == "write":
            bank, value = literals[uid]
            if bank == 30:
                stop = value
            else:
                tcp = value
        else:
            assert kind == "read" and uid in RUNTIME_LOOPS
            captured[uid] = stop
    return stop, tcp, tuple(uid for uid in RUNTIME_LOOPS if captured[uid])


def test_all_eleven_factorial_orders_accounted_for(outcomes):
    assert sum(row.order_count for row in outcomes) == factorial(11) == 39916800
    assert len({(r.stop_after, r.tcp_after, r.exited_loops) for r in outcomes}) == len(
        outcomes
    )


def test_every_witness_replays_to_its_claimed_joint_outcome(outcomes):
    for row in outcomes:
        assert replay_witness(row.witness) == (
            row.stop_after,
            row.tcp_after,
            row.exited_loops,
        )
        assert row.entered_outer_frame == (row.exited_loops == RUNTIME_LOOPS)
        assert row.outer_tcp_selector == (
            row.tcp_after if row.entered_outer_frame else None
        )


def checked_runtime_witness(row):
    """Submit the witness to the existing source-qualified partial-order model."""
    tokens = [ErrorArmEntry(selector) for selector in ERROR_SITES]
    for action in row.witness:
        kind, uid = action.split(":")
        tokens.append(LocalAssignment(uid) if kind == "write" else StopLocalRead(uid))
    # These tokens explicitly assert returning body work; no native call occurs.
    tokens.extend(BodyCompleted(loop) for loop in RUNTIME_LOOPS)
    if row.entered_outer_frame:
        tokens.append(OuterTcpRead())
    return replay_runtime(tokens, stop_before=False, tcp_before=False)


def test_all_128_witnesses_obey_existing_body_and_error_arm_dependencies(outcomes):
    for row in outcomes:
        runtime = checked_runtime_witness(row)
        assert (runtime.stop_after, runtime.tcp_after, runtime.exited_loops) == (
            row.stop_after,
            row.tcp_after,
            row.exited_loops,
        )
        assert runtime.outer_tcp_snapshot is row.outer_tcp_selector


def test_fault_window_can_reach_resource_cleanup_without_staged_card_stop(outcomes):
    row = next(
        row
        for row in outcomes
        if row.entered_outer_frame and not row.stop_after and not row.tcp_after
    )
    outer = replay_outer_stop(
        (FinalCleanupEntry(),),
        runtime=checked_runtime_witness(row),
        emergency_stop=False,
        general_stop=True,
    )
    assert outer.cleanup_entered
    assert outer.choices == outer.final_frame_entries == ()
    cleanup = replay_cleanup(
        tuple(PspClose(index) for index in range(27))
        + (
            CleanupHandler("88"),
            TpgClose(51),
            CleanupHandler("68680"),
            TpgClose(52),
            CleanupHandler("67965"),
            CleanupStopReset(),
            CleanupFrameReturned(),
        ),
        outer=outer,
        boundary=ScriptedBoundary(),
        psp_error_seed=NO_ERROR,
        tpg_sessions=(TaskReference("supplied51"), TaskReference("supplied52")),
    )
    assert cleanup.frame_returned
    assert len(cleanup.calls) == 32
    assert {call.operation for call in cleanup.calls} == {
        "close_variable_reference",
        "tpg300_close",
        "simple_error_handler",
    }
    assert cleanup.memory_after.general_stop is True
    # A completed later initializer reset is not a native restart simulation.
    post_init = project_stop_reset("post_init", cleanup.memory_after)
    assert post_init.independent_assignments == ((45, False), (46, False))
    assert post_init.after.general_stop is True


def test_all_five_can_exit_with_tcp_false(outcomes):
    matches = [r for r in outcomes if r.entered_outer_frame and not r.tcp_after]
    assert matches
    # A runtime publication fault is not a guaranteed staged-stop request.
    assert all(r.outer_tcp_selector is False for r in matches)


def test_stop_can_be_false_after_all_conditions_captured_true(outcomes):
    assert any(r.entered_outer_frame and not r.stop_after for r in outcomes)


def test_mixed_loop_exits_are_reachable(outcomes):
    assert any(0 < len(r.exited_loops) < 5 for r in outcomes)


@pytest.mark.parametrize("stop,tcp", [(False, True), (True, False), (True, True)])
def test_other_explicit_seeds_keep_exact_order_total(stop, tcp):
    result = exhaustive_fault_window(stop_before=stop, tcp_before=tcp)
    assert sum(row.order_count for row in result) == factorial(11)
    assert all(
        replay_witness(row.witness, stop, tcp)
        == (row.stop_after, row.tcp_after, row.exited_loops)
        for row in result
    )


def test_no_implicit_or_numeric_seeds():
    with pytest.raises(TypeError):
        exhaustive_fault_window(stop_before=0, tcp_before=False)
