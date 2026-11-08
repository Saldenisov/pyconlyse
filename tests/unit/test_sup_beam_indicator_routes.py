"""Static caller joins, source anomalies and fail-closed mutation probes."""

import copy
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_beam_indicator_routes as audit


@pytest.fixture(scope="module")
def pinned_source():
    return audit.original()


def source_copy(pinned_source):
    return copy.deepcopy(pinned_source)


def test_report_reproduces_current_static_source_without_promoting_models():
    result = audit.build_routes()
    assert result == json.loads(audit.OUTPUT.read_text("utf-8"))
    observed = result["observations"]
    assert observed["running_route_count"] == observed["fault_route_count"] == 19
    assert observed["explicit_fault_source_indices"] == 17
    for key in (
        "hardware_writes",
        "network_io",
        "vi_run_or_save",
        "web_deployment",
        "commands_enabled",
    ):
        assert result[key] is False
    assert result["new_whole_vi_models"] == result["native_equivalence_claims"] == 0
    h2 = observed["h2_cross_lamp"]
    assert h2["source"]["label_path"] == ["H2"]
    assert h2["destination"]["label_path"] == ["Correcteur H2", "en marche"]
    assert h2["net"] == "40012"
    assert observed["earlier_h2_fault"]["destination"]["label_path"] == [
        "Correcteur H2",
        "en défaut",
    ]
    h2_running = next(
        r
        for r in observed["running_routes"]
        if r["destination"]["label_path"] == ["Correcteur H2", "en marche"]
    )
    assert h2_running["source"]["raw_index"] == 39
    assert (
        h2_running["frame"]
        == 0
        < observed["earlier_h2_fault"]["frame"]
        == 1
        < h2["frame"]
        == 3
    )
    h5 = next(
        r
        for r in observed["running_routes"]
        if r["destination"]["label_path"] == ["Correcteur H5", "en marche"]
    )
    assert h5["source"]["raw_index"] == 51


def test_missing_saved_indices_are_not_converted_to_zero():
    observed = audit.build_routes()["observations"]
    missing = [
        r["source"]
        for r in observed["fault_routes"]
        if r["source"]["raw_index"] is None
    ]
    assert len(missing) == 2
    assert all(
        f["label_path"] is None and f["addressing"] == "omitted-index-unqualified"
        for f in missing
    )
    assert observed["fault_helper"]["outputs"][1]["raw_param_index"] is None
    assert all(
        c["io"][0]["raw_param_index"] is None for c in observed["comparison_calls"]
    )


def test_rejects_silent_h2_repair_to_fault_lamp(pinned_source):
    receipt, roots = source_copy(pinned_source)
    roots["bd"].find(".//*[@class='term'][@uid='70594']/dco/i").text = "64"
    with pytest.raises(AssertionError, match="fault explicit field route changed"):
        audit.build_routes(receipt, roots)


def test_rejects_running_source_channel_change(pinned_source):
    receipt, roots = source_copy(pinned_source)
    roots["bd"].find(".//*[@class='term'][@uid='16092']/dco/i").text = "38"
    with pytest.raises(AssertionError, match="running explicit field route changed"):
        audit.build_routes(receipt, roots)


def test_rejects_running_not_replaced_with_other_primitive(pinned_source):
    receipt, roots = source_copy(pinned_source)
    roots["bd"].find(".//*[@class='prim'][@uid='29427']/primResID").text = "1061"
    with pytest.raises(AssertionError, match="running primitive changed"):
        audit.build_routes(receipt, roots)


def test_rejects_changed_sequence_order(pinned_source):
    receipt, roots = source_copy(pinned_source)
    frames = roots["bd"].find(".//*[@class='sequence'][@uid='32847']/diagramList")
    first = frames[0]
    frames.remove(first)
    frames.insert(1, first)
    with pytest.raises(AssertionError, match="monitor sequence frame order changed"):
        audit.build_routes(receipt, roots)


def test_rejects_fault_helper_true_false_case_swap(pinned_source):
    receipt, roots = source_copy(pinned_source)
    cases = roots["bd"].find(".//*[@class='select'][@uid='13076']/SelectRangeArray32")
    cases[1].find("diagramIdx").text = "0"
    with pytest.raises(AssertionError, match="Boolean guard case ranges changed"):
        audit.build_routes(receipt, roots)


def test_rejects_fabricated_zero_connector_index(pinned_source):
    receipt, roots = source_copy(pinned_source)
    dco = roots["bd"].find(".//*[@class='term'][@uid='55329']/dco")
    ET.SubElement(dco, "paramIdx").text = "0"
    with pytest.raises(AssertionError, match="fault output connector changed"):
        audit.build_routes(receipt, roots)


def test_rejects_changed_threshold_local_identity(pinned_source):
    receipt, roots = source_copy(pinned_source)
    row = next(r for r in receipt["locals"] if r["uid"] == "16157")
    row["name"] = "different threshold"
    with pytest.raises(AssertionError, match="call local source changed"):
        audit.build_routes(receipt, roots)


def test_rejects_changed_native_h2_lamp_identity(pinned_source):
    receipt, roots = source_copy(pinned_source)
    roots["fp"].find(
        ".//*[@class='stdBool'][@uid='39166']/partsList/*/textRec/text"
    ).text = '"en défaut"'
    with pytest.raises(AssertionError, match="native H2 lamp order changed"):
        audit.build_routes(receipt, roots)


def test_rejects_unreviewed_lvkit_component_update(monkeypatch):
    monkeypatch.setattr(audit, "TYPE_SHA", "0" * 64)
    with pytest.raises(AssertionError, match="current LVKit type component changed"):
        audit.components()


def test_rejects_changed_published_baseline(monkeypatch, pinned_source):
    monkeypatch.setattr(audit, "BASELINE_SHA", "0" * 64)
    with pytest.raises(AssertionError, match="published evidence baseline changed"):
        audit.build_routes(*pinned_source)
