"""Saved-wire regression checks; all state examples are nonactuating."""

import copy
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_wait_motor_stop as trace


@pytest.fixture(scope="module")
def sources():
    return trace.original()


@pytest.fixture(scope="module")
def motor_sources():
    return trace.motor_original()


@pytest.fixture(scope="module")
def report(sources, motor_sources):
    return trace.verify(*sources, motor_sources)


def find(roots, uid, key="bd"):
    return next(n for n in roots[key].iter() if n.get("uid") == uid and n.get("class"))


def test_saved_report_reproduces_without_network(sources, motor_sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden in static Wait/motor analysis")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = trace.verify(*sources, motor_sources)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert all(
        result[key] is False
        for key in (
            "screen_used",
            "VI_run_or_save",
            "network_io",
            "hardware_io",
            "production_changes",
            "full_Supervision_coverage",
            "guaranteed_normal_shutdown",
        )
    )


def test_nine_wait_writers_and_four_false_motor_resets(report):
    obs = report["observations"]
    assert len(obs["Wait_writers"]) == 9
    assert sum(row["value"] for row in obs["Wait_writers"]) == 4
    assert len(obs["Main_motor_False_writers"]) == 4
    assert not any(row["value"] for row in obs["Main_motor_False_writers"])
    assert obs["Main_motor_True_program_writers"] == []
    assert obs["autotune_finale_Wait_reset"] is False
    assert {row["bank"] for row in obs["controls"]} == {103, 234, 243}


def test_three_camera_error_arms_leave_wait_unchanged(report):
    guards = report["observations"]["conditional_Wait_clears"]
    assert {row["case"] for row in guards} == {"92709", "95344", "72028"}
    assert all(row["source_type"] == "error cluster" for row in guards)
    assert all(row["Error"]["Wait_written"] is False for row in guards)
    assert {row["No_Error"]["Wait_False_writer"] for row in guards} == {
        "58781",
        "95369",
        "72251",
    }


def test_separate_motor_scopes_and_all_eight_scalar_call_routes(report):
    obs = report["observations"]
    assert len(obs["Main_motor_loops"]) == 7
    assert len(obs["Main_to_motor_subVI"]) == 8
    assert len(obs["motor_subVI_loops"]) == 4
    assert len(obs["motor_subVI_resets"]) == 4
    for row in obs["motor_subVI_loops"]:
        predicate = row["exit_predicate"]
        assert len(predicate["OR_only_leaves"]) == 3
        assert set(predicate["OR_only_leaves"]) == {
            predicate["stop_motor"],
            predicate["error_status"],
            predicate["motion_done"],
        }
        assert predicate["formula"] == (
            "callee stop motor OR error.status OR motion done"
        )
    assert obs["motor_subVI_local_control"] == {
        "control": "402",
        "bank": 3,
        "connector": 6,
        "same_as_Main_bank243": False,
    }
    assert all(
        row["type"] == "Boolean value, not reference"
        and row["connector_index"] == 6
        and row["route"]
        for row in obs["Main_to_motor_subVI"]
    )


@pytest.mark.parametrize("stop", [False, True])
def test_latched_wait_blocks_camera_even_after_global_stop(stop):
    assert trace.camera_wait_witness(True, stop)["continue"] is True
    assert trace.camera_wait_witness(False, stop)["continue"] is False


@pytest.mark.parametrize("motor", [False, True])
@pytest.mark.parametrize("done", [False, True])
@pytest.mark.parametrize("error", [False, True])
def test_global_stop_does_not_change_manual_motion_exit(motor, done, error):
    expected = motor or done or error
    assert trace.motion_poll_witness(motor, done, error, False) is expected
    assert trace.motion_poll_witness(motor, done, error, True) is expected


def test_later_main_button_change_does_not_change_an_already_passed_boolean():
    passed_sample = False
    latest_main_value = True
    assert passed_sample is not latest_main_value
    assert trace.motion_poll_witness(passed_sample, False, False, True) is False
    # A future iteration can sample True; the existing call does not receive it.
    assert trace.motion_poll_witness(latest_main_value, False, False, True) is True


def test_failed_channel_setup_has_no_implicit_finally_clear():
    assert trace.camera_switch_witness(True, ordered_set=True) is True
    assert trace.camera_switch_witness(True, ordered_set=False) is True
    assert trace.camera_switch_witness(False, ordered_set=True) is False
    # Supplied ordering only, not a claim that this interleaving occurred.
    assert trace.camera_switch_witness(False, ordered_set=False) is True


@pytest.mark.parametrize("bad", [None, 0, 1, "True", [], {}])
def test_witnesses_do_not_coerce_unknown_states(bad):
    with pytest.raises(ValueError):
        trace.camera_wait_witness(bad, True)
    with pytest.raises(ValueError):
        trace.motion_poll_witness(False, False, bad, True)
    with pytest.raises(ValueError):
        trace.camera_switch_witness(bad)


@pytest.mark.parametrize(
    "uid,field,value",
    [
        ("61608", "dco/ConstValue", "0001"),
        ("96325", "dco/ConstValue", "0001"),
        ("16708", "termList/*/dco/paramIdx", "49"),
        ("96347", "termList/*/objFlags", "4096"),
        ("6584", "loopTestDCO/objFlags", "65537"),
        ("14274", "dco/ConstValue", "00000064"),
        ("92709", "SelectRangeArray32/*/diagramIdx", "1"),
        ("95344", "SelectRangeArray32/*/start", "1"),
        ("72028", "SelectRangeArray32/*/end", "1"),
        ("102481", "termList/*[@uid='102578']/dco/paramIdx", "7"),
    ],
)
def test_rejects_mutated_saved_control_guards_and_values(
    sources, motor_sources, uid, field, value
):
    receipt, roots = sources[0], copy.deepcopy(sources[1])
    target = find(roots, uid).find(field)
    assert target is not None and target.text != value
    target.text = value
    with pytest.raises(AssertionError):
        trace.verify(receipt, roots, motor_sources)


@pytest.mark.parametrize("sequence", ["14231", "11854", "35260"])
def test_rejects_reordered_reconfiguration_frames(sources, motor_sources, sequence):
    receipt, roots = sources[0], copy.deepcopy(sources[1])
    frames = find(roots, sequence).find("sequenceList")
    a, b = frames[0], frames[1]
    frames[0], frames[1] = b, a
    with pytest.raises(AssertionError):
        trace.verify(receipt, roots, motor_sources)


def test_rejects_broken_main_to_callee_stop_route(sources, motor_sources):
    receipt, roots = sources[0], copy.deepcopy(sources[1])
    wire = find(roots, "103220").find("termList")
    assert wire[-1].get("uid") == "102578"
    wire[-1].set("uid", "missing-stop-input")
    with pytest.raises(AssertionError):
        trace.verify(receipt, roots, motor_sources)


@pytest.mark.parametrize(
    "uid,field,value",
    [
        ("4534", "dco/ConstValue", "0001"),
        ("1620", "termList/*/dco/paramIdx", "243"),
        ("3937", "loopTestDCO/objFlags", "1"),
    ],
)
def test_rejects_callee_scope_or_predicate_mutations(
    sources, motor_sources, uid, field, value
):
    mr, mx = motor_sources[0], copy.deepcopy(motor_sources[1])
    target = find(mx, uid).find(field)
    assert target is not None and target.text != value
    target.text = value
    with pytest.raises(AssertionError):
        trace.verify(*sources, (mr, mx))
