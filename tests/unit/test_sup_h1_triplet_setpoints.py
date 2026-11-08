"""No-actuation source proofs; screenshot provenance remains explicitly bounded."""

import copy
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import verify_sup_h1_triplet_setpoints as proof


@pytest.fixture(scope="module")
def sources():
    return proof.original()


def graph(sources):
    receipt, roots = sources
    table, _ = proof.components()
    return proof.SourceGraph(receipt, roots, table(roots["meta"]))


def test_reproduces_report_without_network(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network allowed")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = proof.verify(*sources)
    assert result == json.loads(proof.OUTPUT.read_text("utf-8"))
    assert result["explicit_NumFloat64_terminal_labels_checked"] == 302
    assert result["explicit_label_conflicts"] == 0
    assert not any(
        result[k]
        for k in (
            "screen_used",
            "vi_run_or_save",
            "hardware_io",
            "network_io",
            "deployment",
            "fresh_native_labview_verification",
            "physical_channel_or_pin_verified",
            "all_omitted_indices_qualified",
        )
    )
    assert result["image_capture_time_vi_sha256"] is None


def test_exact_two_named_routes_do_not_default_missing_indices(sources):
    result = proof.verify(*sources)
    assert [
        (r["name"], r["bank_input"]["name"], r["direct_wire"]["net"])
        for r in result["routes"]
    ] == [
        ("H1", "C6NI6703", "8488"),
        ("Triplet 1-1", "C7NI6703", "7998"),
    ]
    for route, expected in zip(result["routes"], proof.CASES):
        dest = route["destination"]
        assert dest["raw_index"] is None
        assert not dest["index_was_defaulted"]
        assert dest["matched_member"]["position_path"] == [0]
        assert dest["matched_member"]["label_path"] == [expected["label"]]
        assert route["source_level_named_route_resolved"]
        assert route["psp"]["uri"].endswith("/" + expected["bank"])
    # This separate connector-ABI gap is not silently closed by named-type proof.
    assert (
        result["routes"][0]["acquisition_writer_receipt"]["raw_connector_index"] is None
    )


@pytest.mark.parametrize(
    "port,net,replacement",
    [
        ("14331", "8488", "14587"),
        ("14067", "7998", "14077"),
    ],
)
def test_rejects_setpoint_wire_retarget(sources, port, net, replacement):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(
        f".//*[@class='signal'][@uid='{net}']/termList/*[@uid='{port}']"
    ).set("uid", replacement)
    with pytest.raises(AssertionError, match="setpoint direct wire changed"):
        proof.verify(receipt, roots)


@pytest.mark.parametrize(
    "port,other_type",
    [
        ("14331", "TypeID(7370)"),
        ("14067", "TypeID(7365)"),
    ],
)
def test_rejects_saved_type_retarget_even_without_index(sources, port, other_type):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(
        f".//*[@class='term'][@uid='{port}']/dco/typeDesc"
    ).text = other_type
    with pytest.raises(AssertionError, match="expected named destination changed"):
        proof.verify(receipt, roots)


def test_labelled_match_rejects_ambiguous_member_names(sources):
    g = graph(copy.deepcopy(sources))
    cluster = g.table.heap(g.aggregate("8553").findtext("dco/typeDesc"))
    cluster.append(copy.deepcopy(cluster[0]))
    with pytest.raises(AssertionError, match="missing or ambiguous"):
        proof.labelled_member(g, "14331")


def test_no_unlabelled_numeric_or_positional_fallback(sources):
    g = graph(copy.deepcopy(sources))
    desc = g.table.heap("TypeID(7369)")
    desc.attrib.pop("Label")
    with pytest.raises(AssertionError, match="labelled scalar type required"):
        proof.labelled_member(g, "14331")


def test_rejects_conflicting_explicit_index(sources):
    import xml.etree.ElementTree as ET

    g = graph(copy.deepcopy(sources))
    ET.SubElement(g.nodes["14331"].find("dco"), "i").text = "1"
    with pytest.raises(AssertionError, match="explicit index conflicts"):
        proof.labelled_member(g, "14331")


def test_rejects_explicit_sibling_label_conflict(sources):
    receipt, roots = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(
        ".//*[@class='term'][@uid='14587']/dco/typeDesc"
    ).text = "TypeID(7371)"
    with pytest.raises(
        AssertionError, match="explicit scalar terminal label conflicts"
    ):
        proof.verify(receipt, roots)


def test_rejects_changed_corroborating_image_pin(sources, monkeypatch):
    monkeypatch.setattr(proof, "IMAGES", {"0__SUP__ELYSEd347.png": "0" * 64})
    with pytest.raises(AssertionError, match="corroborating screenshot changed"):
        proof.verify(*sources)
