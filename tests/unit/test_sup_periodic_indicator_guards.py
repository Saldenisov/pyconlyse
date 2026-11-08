"""Offline source mutations and pure, non-actuating indicator projections."""

import copy
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_periodic_indicator_guards as trace


@pytest.fixture(scope="module")
def sources():
    return trace.original()


@pytest.fixture(scope="module")
def report(sources):
    return trace.verify(*sources)


def test_report_reproduces_without_network(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network in local source analysis")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = trace.verify(*sources)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert not any(
        result[k]
        for k in (
            "complete_business_logic_coverage",
            "fresh_native_source_qualification",
            "screen_used",
            "vi_run_or_save",
            "hardware_io",
            "network_io",
            "runtime_or_web_changes",
        )
    )


def test_saved_literal_selection_not_displayed_true_arm_determines_reachability(report):
    orange = report["observations"]["orange_gate"]
    fault = report["observations"]["computed_fault_gate"]
    assert orange["value"] is True
    assert fault["value"] is False
    assert len(orange["calls_enabled_when_sequence_is_entered"]) == 2
    assert fault["calls_enabled_when_sequence_is_entered"] == []
    assert fault["calls_in_True_arm"] == [
        {
            "uid": "55320",
            "callee": "3_SUP_en_défaut_alims.vi",
        }
    ]
    assert not fault["False_arm_has_effects"]
    assert not fault["source_is_shift_register_or_sequence_local"]
    assert report["observations"]["only_main_fault_helper_call_uid"] == "55320"


def test_h2_runtime_candidate_route_is_separate_from_dormant_miswire(report):
    obs = report["observations"]
    assert obs["H2_running_prior_route"]["source"]["raw_index"] == 39
    assert obs["H2_raw_fault_route"]["source"]["field"]["raw_index"] == 40
    assert obs["H2_raw_fault_route"]["destination"]["raw_index"] == 64
    assert obs["H2_raw_fault_route"]["destination"]["label_path"] == [
        "Correcteur H2",
        "en défaut",
    ]


def test_all_19_fault_projection_leaves_and_both_boolean_values(report):
    routes = report["observations"]["raw_fault_routes"]
    assert len(routes) == 19
    assert sum(r["source"]["kind"] == "C3_IN_DIO96" for r in routes) == 18
    for route in routes:
        for value in (False, True):
            direct = {i: not value for i in range(60)}
            deviated = {i: not value for i in range(60)}
            if route["source"]["kind"] == "C3_IN_DIO96":
                bits = direct if route["line"] == "Voie directe" else deviated
                bits[route["source"]["field"]["raw_index"]] = value
                expected = value
            else:
                expected = False
            updates = trace.project_raw_fault_leaf_updates(direct, deviated, report)
            assert (
                updates[route["line"]][route["destination"]["label_path"][0]]
                is expected
            )
    assert [len(updates[line]) for line in ("Voie directe", "Voie déviée")] == [10, 9]
    assert "Phase HF / Laser" not in updates["Voie directe"]


def test_h5_false_is_not_inferred_from_reserved_input_or_command(report):
    for reserved_value in (False, True):
        direct, deviated = ({i: True for i in range(60)} for _ in range(2))
        deviated[52] = reserved_value
        updates = trace.project_raw_fault_leaf_updates(direct, deviated, report)
        assert updates["Voie déviée"]["Correcteur H5"] is False
    # Four input banks can be read at different times. No atomic state is assumed.
    direct = {i: False for i in range(60)}
    deviated = {i: True for i in range(60)}
    updates = trace.project_raw_fault_leaf_updates(direct, deviated, report)
    assert updates["Voie directe"]["Correcteur H2"] is False
    assert updates["Voie déviée"]["Correcteur H4"] is True


@pytest.mark.parametrize("invalid", [None, 0, 1, "False"])
def test_diagnostic_projection_does_not_coerce_unknown_to_safe(invalid, report):
    direct = {i: False for i in range(60)}
    deviated = dict(direct)
    direct[40] = invalid
    with pytest.raises(
        ValueError, match="Explicit Boolean C3 snapshot field required: 40"
    ):
        trace.project_raw_fault_leaf_updates(direct, deviated, report)


@pytest.mark.parametrize("port,value", [("24051", "00"), ("50022", "01")])
def test_rejects_changed_enabling_constant(sources, port, value):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(f".//*[@class='term'][@uid='{port}']/dco/ConstValue").text = value
    with pytest.raises(AssertionError, match="gate literal owner/value changed"):
        trace.verify(receipt, roots)


def test_rejects_cross_coupling_two_gate_sources(sources):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(
        ".//*[@class='signal'][@uid='50037']/termList/*[@uid='50022']"
    ).set("uid", "24051")
    with pytest.raises(
        AssertionError, match="gate constant gained another wire/driver"
    ):
        trace.verify(receipt, roots)


def test_rejects_gate_signal_retarget(sources):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(
        ".//*[@class='signal'][@uid='50037']/termList/*[@uid='50022']"
    ).set("uid", "NOT_THE_SAVED_CONSTANT")
    with pytest.raises(AssertionError, match="gate direct constant wire changed"):
        trace.verify(receipt, roots)


def test_rejects_operations_added_to_inactive_helpers_false_arm(sources):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    node = ET.Element("SL__arrayElement", {"class": "gRef", "uid": "TEST_WRITE"})
    roots["bd"].find(".//*[@class='diag'][@uid='13105']/zPlaneList").append(node)
    with pytest.raises(AssertionError, match="False arm gained an operation"):
        trace.verify(receipt, roots)


def test_rejects_h2_raw_fault_write_changed_to_running(sources):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='term'][@uid='61432']/dco/i").text = "62"
    with pytest.raises(AssertionError, match="raw fault destination changed"):
        trace.verify(receipt, roots)


def test_rejects_h5_false_replaced_by_true(sources):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='term'][@uid='49833']/dco/ConstValue").text = "01"
    with pytest.raises(AssertionError, match="H5 forced-False source changed"):
        trace.verify(receipt, roots)


def test_rejects_changed_native_image_identity(sources, monkeypatch):
    monkeypatch.setattr(trace, "IMAGES", {"0__SUP__ELYSEd119.png": "0" * 64})
    with pytest.raises(AssertionError, match="saved native image changed"):
        trace.verify(*sources)
