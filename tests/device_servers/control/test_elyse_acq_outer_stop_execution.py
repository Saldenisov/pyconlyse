"""Executable XP outer-stop plan cross-checked against reviewed inert VI plan."""
from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import (
    CONTROLLED_STOP as REVIEWED_PLAN, all_stop_phases, project_ht_ramp_iteration,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_outer_stop import (
    CONTROLLED_STOP as EXECUTABLE_PLAN,
)
from legacy.xp_acq_agent.tests.test_acquisition_outer_stop import Fixture, all_frames


def test_complete_original_outer_plan_equals_reviewed_40_frame_model():
    assert EXECUTABLE_PLAN == REVIEWED_PLAN
    assert all_frames() == list(all_stop_phases())


def test_execution_matches_independent_ramp_projection_without_zero_extension():
    for seed in (-2.0, 0.0, 6.599999999999999, 6.6, 7.0, 12.7):
        fixture = Fixture(seed)
        state = fixture.banks[12]
        decrements = 0
        while True:
            result = project_ht_ramp_iteration(state, state)
            if result.should_stop:
                break
            state = dict(result.local_writes)[12]
            decrements += 1
        executed = fixture.execute()
        assert fixture.banks[12] == state
        assert executed["ramp_decrements"] == decrements
