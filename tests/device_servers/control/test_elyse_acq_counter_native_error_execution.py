"""Differential NI6602 supplied-return traces; no native or hardware calls.

The frozen modern model and Python 3.4 replay receive independently translated
fixtures. Default fixture pass-through describes this test only, not DAQmx
error-in behavior. Clear-all is selected explicitly when comparing its
documented profile; arbitrary other supplied returns test wires, not a claim
about the deployed XP Clear Errors body.
"""

import pytest
from DeviceServers.control.elyse_acq.vi_simulation import boundary as source_boundary
from DeviceServers.control.elyse_acq.vi_simulation import write_ni6602 as source_writer
from legacy.xp_acq_agent.elyse_agent import acquisition_counter_error_flow as replay

TASK = source_boundary.TaskReference("original-task")
NO_ERROR = source_boundary.NO_ERROR
INPUT_ERROR = source_boundary.ErrorCluster(True, -10, "input")
POLL_ERROR = source_boundary.ErrorCluster(True, -20, "poll")
STOP_ERROR = source_boundary.ErrorCluster(True, -30, "stop")
PROPERTY_ERROR = source_boundary.ErrorCluster(True, -40, "properties")
START_ERROR = source_boundary.ErrorCluster(True, -50, "start")


def _key(uid, iteration=None):
    return source_boundary.CallKey(source_writer.SOURCE.name, uid, iteration)


def _replay_error(value):
    return replay.NativeErrorCluster(value.status, value.code, value.source)


def _normalized(value):
    if type(value) in (source_boundary.ErrorCluster, replay.NativeErrorCluster):
        return {"status": value.status, "code": value.code, "source": value.source}
    if type(value) in (source_boundary.TaskReference, replay.TaskReference):
        return {"task": value.token}
    if type(value) in (source_boundary.MissingValue, replay.MissingValue):
        return {"connection": value.value}
    if type(value) is tuple:
        return tuple(_normalized(item) for item in value)
    return value


def _source_call(call):
    return {
        "uid": call.key.node_uid,
        "iteration": call.key.iteration,
        "operation": call.operation,
        "task_in": _normalized(call.task_in),
        "error_in": _normalized(call.error_in),
        "arguments": {name: _normalized(value) for name, value in call.arguments},
        "task_out": _normalized(call.returned.task),
        "error_out": _normalized(call.returned.error),
        "data_out": _normalized(call.returned.data),
    }


def _replayed_call(record):
    call, returned = record
    # The replay records additive documented-default provenance; the frozen
    # source contract previously recorded only the wired input/output slots.
    additive_clear_metadata = {
        "specific_error_code",
        "specific_error_code_input_wired",
        "specific_error_code_provenance",
    }
    return {
        "uid": call.node_uid,
        "iteration": call.iteration,
        "operation": call.stage,
        "task_in": _normalized(call.task_in),
        "error_in": _normalized(call.error_in),
        "arguments": {
            name: _normalized(value)
            for name, value in call.arguments
            if name not in additive_clear_metadata
        },
        "task_out": _normalized(returned.task),
        "error_out": _normalized(returned.error),
        "data_out": _normalized(returned.data),
    }


def _run_pair(
    done=(True,), errors=None, tasks=None, error_in=NO_ERROR, documented_clear_all=False
):
    supplied_errors = dict(errors or {})
    supplied_tasks = dict(tasks or {})
    supplied_data = {
        _key("3202", index): (value,)
        for index, value in enumerate(done)
        if value is not None
    }
    if documented_clear_all:
        assert _key("309") not in supplied_errors
        # The modern oracle requires this explicit Clear Errors fixture too;
        # it does not otherwise implement Clear Errors semantics.
        supplied_errors[_key("309")] = NO_ERROR
    boundary = source_boundary.ScriptedBoundary(
        errors=supplied_errors, tasks=supplied_tasks, data=supplied_data
    )
    source = source_writer.write(
        boundary,
        task=TASK,
        error_in=error_in,
        delay_microseconds=0.125,
        width_microseconds=-0.075,
    )

    requests = []

    def supplied_return(call):
        requests.append(call)
        key = _key(call.node_uid, call.iteration)
        returned_task = supplied_tasks.get(key)
        task_out = (
            replay.TaskReference(returned_task.token)
            if returned_task is not None
            else call.task_in
        )
        if documented_clear_all and call.node_uid == "309":
            error_out = replay.clear_all_errors(call.error_in)
        elif key in supplied_errors:
            error_out = _replay_error(supplied_errors[key])
        else:
            error_out = (
                replay.NO_ERROR if call.error_in is replay.UNWIRED else call.error_in
            )
        data_out = supplied_data.get(key, replay.UNSUPPLIED)
        return replay.NativeReturn(task_out, error_out, data_out)

    reproduced = replay.execute_counter_error_flow(
        supplied_return,
        replay.TaskReference(TASK.token),
        0.125,
        -0.075,
        _replay_error(error_in),
    )
    assert [_source_call(call) for call in source.calls] == [
        _replayed_call(record) for record in reproduced.calls
    ]
    assert (
        source.delay_ticks,
        source.high_ticks,
        source.poll_iterations,
        source.exit_reason,
        _normalized(source.final_pulse_done),
        _normalized(source.error_out),
    ) == (
        reproduced.delay_ticks,
        reproduced.high_ticks,
        reproduced.poll_iterations,
        reproduced.exit_reason,
        _normalized(reproduced.final_pulse_done),
        _normalized(reproduced.error_out),
    )
    assert source.source.sha256 == replay.SOURCE_HELPER_SHA256
    boundary.assert_all_fixtures_used()
    return source, reproduced, requests


@pytest.mark.parametrize("incoming", [NO_ERROR, INPUT_ERROR])
@pytest.mark.parametrize("done", [(True,), (False, False, True), (False,) * 22])
def test_original_task_and_error_reused_at_each_poll_and_full_trace_matches(
    incoming, done
):
    source, reproduced, requests = _run_pair(done=done, error_in=incoming)
    polls = [value for value in requests if value.node_uid == "3202"]
    assert len(polls) == source.poll_iterations
    assert all(value.task_in == replay.TaskReference(TASK.token) for value in polls)
    assert all(value.error_in == _replay_error(incoming) for value in polls)
    assert reproduced.completed is True
    assert len([value for value in requests if value.node_uid == "3194"]) == len(polls)


def test_intermediate_errors_and_task_returns_are_overwritten_not_shift_registered():
    _, reproduced, requests = _run_pair(
        done=(False, False, True),
        errors={_key("3202", 0): POLL_ERROR, _key("3202", 1): STOP_ERROR},
        tasks={
            _key("3202", 0): source_boundary.TaskReference("intermediate0"),
            _key("3202", 1): source_boundary.TaskReference("intermediate1"),
        },
    )
    stop = next(value for value in requests if value.node_uid == "2976")
    assert stop.task_in == replay.TaskReference(TASK.token)
    assert stop.error_in == replay.NO_ERROR
    assert reproduced.error_out == replay.NO_ERROR


def test_final_poll_return_feeds_stop_and_only_stop_return_task_feeds_properties():
    _, reproduced, requests = _run_pair(
        done=(False, True),
        errors={_key("3202", 1): POLL_ERROR},
        tasks={
            _key("3202", 1): source_boundary.TaskReference("final-poll"),
            _key("2976"): source_boundary.TaskReference("stop-returned"),
        },
    )
    by_uid = {value.node_uid: value for value in requests}
    assert by_uid["2976"].task_in == replay.TaskReference("final-poll")
    assert by_uid["2976"].error_in == _replay_error(POLL_ERROR)
    assert by_uid["3083"].task_in == replay.TaskReference("stop-returned")
    assert reproduced.error_out == _replay_error(POLL_ERROR)


def test_documented_clear_all_profile_explicitly_masks_stop_error_before_properties():
    _, reproduced, requests = _run_pair(
        errors={_key("2976"): STOP_ERROR}, documented_clear_all=True
    )
    by_uid = {value.node_uid: value for value in requests}
    assert by_uid["309"].error_in == _replay_error(STOP_ERROR)
    assert by_uid["3083"].error_in == replay.NO_ERROR
    assert by_uid["3032"].error_in == replay.NO_ERROR
    assert reproduced.error_out == replay.NO_ERROR
    assert dict(by_uid["309"].arguments) == {
        "connected_error_input_slot": 4,
        "connected_error_output_slot": 0,
        "specific_error_code": 0,
        "specific_error_code_input_wired": False,
        "specific_error_code_provenance": (
            "unwired connector default 0 means all errors"
        ),
    }


def test_supplied_noncleared_return_is_wire_fixture_not_default_clear_semantics():
    _, reproduced, requests = _run_pair(errors={_key("2976"): STOP_ERROR})
    by_uid = {value.node_uid: value for value in requests}
    assert by_uid["3083"].error_in == _replay_error(STOP_ERROR)
    assert by_uid["3032"].error_in == _replay_error(STOP_ERROR)
    assert reproduced.error_out == _replay_error(STOP_ERROR)


def test_property_and_start_return_errors_are_forwarded_without_invented_driver_gates():
    _, reproduced, requests = _run_pair(
        errors={
            _key("2976"): STOP_ERROR,
            _key("3083"): PROPERTY_ERROR,
            _key("3032"): START_ERROR,
        },
        tasks={
            _key("3083"): source_boundary.TaskReference("property-returned"),
            _key("3032"): source_boundary.TaskReference("start-returned"),
        },
        documented_clear_all=True,
    )
    start = next(value for value in requests if value.node_uid == "3032")
    assert start.task_in == replay.TaskReference("property-returned")
    assert start.error_in == _replay_error(PROPERTY_ERROR)
    assert reproduced.error_out == _replay_error(START_ERROR)
    assert reproduced.task_out == replay.TaskReference("start-returned")
    assert len(requests) == 6


@pytest.mark.parametrize(
    "done, expected_completed, expected_reason",
    [
        ((None,), False, "missing_poll_value"),
        ((False,) * 21 + (None,), True, "iteration_limit"),
    ],
)
def test_missing_pulse_data_suspension_or_limit_exit_matches_frozen_source(
    done, expected_completed, expected_reason
):
    _, reproduced, requests = _run_pair(done=done)
    assert reproduced.completed is expected_completed
    assert reproduced.exit_reason == expected_reason
    assert ("2976" in [value.node_uid for value in requests]) is expected_completed
    assert reproduced.final_pulse_done is replay.UNSUPPLIED


@pytest.mark.parametrize("error_uid", ["2976", "309", "3083", "3032"])
def test_each_post_poll_supplied_error_controls_its_outgoing_wire_without_retry(
    error_uid,
):
    _, reproduced, requests = _run_pair(errors={_key(error_uid): START_ERROR})
    expected = ["3202", "3194", "2976", "309", "3083", "3032"]
    assert [value.node_uid for value in requests] == expected
    assert reproduced.error_out == _replay_error(START_ERROR)
    at = expected.index(error_uid)
    assert all(
        value.error_in == _replay_error(START_ERROR) for value in requests[at + 1 :]
    )
