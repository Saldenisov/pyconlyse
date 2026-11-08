"""Pinned-source Phase status retention, copy-back and mutation guards."""

import copy
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_phase_status as phase


@pytest.fixture(scope="module")
def sources():
    receipt, roots = phase.original()
    return receipt, roots, phase.helper_sources()


def test_reproduces_without_network_or_native_execution(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network allowed in Phase source analysis")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = phase.verify(*sources)
    assert result == json.loads(phase.OUTPUT.read_text("utf-8"))
    assert not any(
        result[key]
        for key in (
            "complete_Supervision_coverage",
            "native_defaults_verified",
            "screen_used",
            "vi_run_or_save",
            "hardware_io",
            "network_io",
            "production_changes",
        )
    )


def test_census_includes_whole_cluster_and_dynamic_row_writers(sources):
    result = phase.verify(*sources)
    obs = result["observations"]
    assert obs["direct_local_aliases"] == 15
    assert obs["direct_local_writers"] == 6
    assert {r["writer_uid"] for r in obs["whole_cluster_local_writers"]} == {
        "7430",
        "7502",
        "7649",
        "61451",
        "70618",
    }
    assert obs["comparison_whole_cluster_writer"]["uid"] == "16437"
    assert obs["row_Value_write"]["uid"] == "8025"
    assert len(obs["row_Value_write"]["branches"]) == 7
    assert (
        sum(len(r["updated_fields"]) for r in obs["whole_cluster_local_writers"]) == 52
    )
    assert obs["helper"]["Phase_orange"]["value"] is False
    assert all(f["label_path"][-1] == "orange" for f in obs["helper"]["fields_changed"])
    assert obs["static_reference_target_census"]["direct_bound_property_nodes"] == []


def test_corrects_old_auxiliary_aggregate_roles_without_changing_named_channels(
    sources,
):
    result = phase.verify(*sources)
    routes = result["correction_to_prior_auxiliary_role_labels"][
        "corrected_bank_local_directions"
    ]
    assert [(r["read"]["local"], r["write"]["local"]) for r in routes] == [
        ("15529", "6122"),
        ("9302", "8562"),
    ]


def test_rejects_new_phase_flag_producer_in_running_mux(sources):
    receipt, roots, helper = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='term'][@uid='16759']/dco/i").text = "26"
    with pytest.raises(AssertionError, match="now changes Phase flags"):
        phase.verify(receipt, roots, helper)


def test_rejects_unledgered_whole_cluster_writer(sources):
    receipt, roots, helper = sources
    roots = copy.deepcopy(roots)
    node = copy.deepcopy(roots["bd"].find(".//*[@class='gRef'][@uid='7430']"))
    node.set("uid", "UNREVIEWED_DIRECT_WRITER")
    roots["bd"].find("root/nodeList").append(node)
    with pytest.raises(AssertionError, match="direct local census changed"):
        phase.verify(receipt, roots, helper)


@pytest.mark.parametrize("net,port", [("8509", "8311"), ("11553", "7689")])
def test_rejects_status_passthrough_broken_in_any_audited_button_arm(
    sources, net, port
):
    receipt, roots, helper = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(
        f".//*[@class='signal'][@uid='{net}']/termList/*[@uid='{port}']"
    ).set("uid", "ALTERED_STATUS_SOURCE")
    with pytest.raises(AssertionError, match="source wire changed"):
        phase.verify(receipt, roots, helper)


def test_rejects_same_reference_row_read_write_separation(sources):
    receipt, roots, helper = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='signal'][@uid='11108']/termList/*[@uid='8027']").set(
        "uid", "ANOTHER_REFERENCE"
    )
    with pytest.raises(AssertionError, match="source wire changed: 11108"):
        phase.verify(receipt, roots, helper)


def test_rejects_new_static_property_binding_to_phase_lamp(sources):
    receipt, roots, helper = sources
    roots = copy.deepcopy(roots)
    prop = ET.Element(
        "SL__arrayElement", {"class": "propNode", "uid": "NEW_PHASE_PROPERTY"}
    )
    ET.SubElement(prop, "ddo", {"uid": "20261"})
    roots["bd"].find("root/nodeList").append(prop)
    with pytest.raises(
        AssertionError, match="static property/reference census changed"
    ):
        phase.verify(receipt, roots, helper)


def test_rejects_helper_changing_running_instead_of_orange(sources):
    receipt, roots, (hr, hx) = sources
    hx = copy.deepcopy(hx)
    hx["bd"].find(".//*[@class='term'][@uid='1586']/dco/i").text = "26"
    with pytest.raises(AssertionError, match="gained non-orange field write"):
        phase.verify(receipt, roots, (hr, hx))


def test_rejects_phase_orange_false_becoming_true(sources):
    receipt, roots, (hr, hx) = sources
    hx = copy.deepcopy(hx)
    hx["bd"].find(".//*[@class='term'][@uid='3056']/dco/ConstValue").text = "01"
    with pytest.raises(AssertionError, match="Phase orange False source changed"):
        phase.verify(receipt, roots, (hr, hx))


def test_rejects_helper_whole_input_copy_replaced(sources):
    receipt, roots, (hr, hx) = sources
    hx = copy.deepcopy(hx)
    hx["bd"].find(".//*[@class='signal'][@uid='5964']/termList/*[@uid='5920']").set(
        "uid", "ANOTHER_CLUSTER"
    )
    with pytest.raises(AssertionError, match="saved wire path absent"):
        phase.verify(receipt, roots, (hr, hx))


def test_rejects_relabelled_native_phase_flag(sources):
    receipt, roots, helper = sources
    roots = copy.deepcopy(roots)
    roots["fp"].find(
        ".//*[@class='stdBool'][@uid='20261']/partsList/*/textRec/text"
    ).text = '"not running"'
    with pytest.raises(AssertionError, match="Phase FP lamp identity changed"):
        phase.verify(receipt, roots, helper)
