"""Clean-checkout parity against retained inert source contracts, never NI."""
import random

import pytest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    CallKey, NO_ERROR, ScriptedBoundary, TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.timeout_dispatch import (
    counter_intent, counter_publication_frame, counter_reset_frame,
)
from DeviceServers.control.elyse_acq.vi_simulation.write_ni6602 import (
    SOURCE, POLL_UID, labview_i32_to_u32_ticks as reviewed_ticks, write,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_counter_timing import (
    HELPER_UIDS, SOURCE_HELPER_SHA256, decode_counter_bank,
    labview_i32_to_u32_ticks as executable_ticks,
)
from legacy.xp_acq_agent.tests.test_acquisition_counter_timing import Harness, bank


def test_finite_conversion_matches_reviewed_i32_to_u32_contract():
    rng = random.Random(0x6602)
    values = [rng.uniform(-3e8, 3e8) for _ in range(4096)]
    values += [i / 40.0 for i in range(-100, 101)]
    values += [-1e300, 1e300, -2147483648 / 20.0, 2147483647 / 20.0]
    for value in values:
        assert executable_ticks(value) == reviewed_ticks(value)
    assert executable_ticks(-1.0) == 0xFFFFFFEC
    assert executable_ticks(.125) == 2
    assert executable_ticks(.175) == 4
    assert executable_ticks(-1e300) == 0x80000000
    assert executable_ticks(1e300) == 0x7FFFFFFF


@pytest.mark.parametrize("selector", range(1, 17))
def test_all_integer_requests_match_source_pair_and_task_mapping(selector):
    snapshot = bank(float(selector))
    tasks = tuple(TaskReference("ctr" + str(i)) for i in range(8))
    reviewed = counter_intent(snapshot, tasks)
    decoded = decode_counter_bank(snapshot)
    assert decoded["counter"] == reviewed.task_index
    assert decoded["delay_index"] == reviewed.delay_index
    assert decoded["width_index"] == reviewed.width_index
    assert decoded["delay_microseconds"] == reviewed.delay
    assert decoded["width_microseconds"] == reviewed.width


@pytest.mark.parametrize("done", [(True,), (False, False, True), (False,) * 22])
def test_helper_trace_equals_reviewed_nominal_poll_stop_properties_start(done):
    boundary = ScriptedBoundary(data={
        CallKey(SOURCE.name, POLL_UID, i): (value,) for i, value in enumerate(done)
    })
    source = write(boundary, task=TaskReference("counter"),
                   delay_microseconds=10.0, width_microseconds=25.0, error_in=NO_ERROR)
    harness = Harness()
    harness.image = (10.0, 25.0) + bank()[2:]
    harness.done_values = list(done)
    result = harness.execute()
    assert result["poll_iterations"] == source.poll_iterations
    assert result["poll_exit_reason"] == source.exit_reason
    assert result["decoded"]["delay_ticks"] == source.delay_ticks
    assert result["decoded"]["high_ticks"] == source.high_ticks
    observed = [uid for _, uid in harness.observations if uid in HELPER_UIDS]
    assert observed == [call.key.node_uid for call in source.calls]
    assert SOURCE_HELPER_SHA256 == SOURCE.sha256


def test_reset_and_publication_match_their_independent_source_reads():
    dispatch = bank(3.0)
    reset = tuple(float(i + 100) for i in range(32)) + (16.0,)
    publication = tuple(float(i + 200) for i in range(32)) + (7.0,)
    harness = Harness()
    harness.read_images = [dispatch, reset, publication]
    result = harness.execute()
    expected_reset = counter_reset_frame(reset, helper_returned_error=NO_ERROR)
    expected_publication = counter_publication_frame(publication)
    assert result["requested_reset_snapshot"] == expected_reset
    assert result["publication_snapshot"] == expected_publication.data
    assert result["atomic_snapshot"] is False
    assert result["source_error_semantics_reproduced"] is False
