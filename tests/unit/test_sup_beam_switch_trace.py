"""Offline original switch routing and source-mutation checks."""

import copy
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_beam_switches as trace


@pytest.fixture(scope="module")
def sources():
    receipt, roots = trace.original()
    return receipt, roots, trace.checked_vam(trace.ACQ_ARCHIVE)


def test_static_trace_reproduces_without_network_or_hardware(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden in static switch trace")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = trace.build_trace(*sources)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert not any(
        result[k] for k in ("hardware_io", "network_io", "vi_run_or_save", "deployment")
    )
    assert not result["complete_controller_equivalence"]
    assert result["explicit_named_MA_read_ports"] == []
    assert result["acq_explicit_line_signaling_writers"] == []
    assert len(result["whole_cluster_helpers"]) == 2
    assert all(
        h["PSP_nodes"] == h["calls"] == 0 for h in result["whole_cluster_helpers"]
    )


def test_switch_only_cases_preserve_values_but_still_republish_analog_banks(sources):
    result = trace.build_trace(*sources)
    for line in result["lines"].values():
        assert [(p["action"], p["unchanged_fields"]) for p in line["pass_through"]] == [
            (1, 7),
            (16, 7),
        ]
        assert not line["switch_only_transfer"]
        assert line["unnamed_retained_boolean_active_consumers"] == []
        assert all(
            (mask & line["transfer_mask"]) < line["transfer_threshold"]
            for mask in (1, 16)
        )
        assert {p["bank"] for p in line["publications"]} == {
            f"C{i}NI6703" for i in range(6, 10)
        }
        assert line["publication_is_outside_transfer_guard"]
        assert all(
            "DPS" not in p["uri"] and "DIO96" not in p["uri"]
            for p in line["publications"]
        )


def test_all_24_selectors_and_both_line_correctors_have_proved_polarity(sources):
    result = trace.build_trace(*sources)
    assert [
        len(result["lines"][line]["step_paths"]) for line in ("direct", "deviated")
    ] == [16, 8]
    for line_name, line in result["lines"].items():
        corrector_rows = set(trace.GROUPS[line_name][-1])
        for rule in line["step_paths"]:
            assert rule["x1_path"]
            if set(rule["row_indices"]) == corrector_rows:
                assert (rule["false_step"], rule["true_step"]) == (
                    (0.1, 1.0) if rule["action"] in (128, 1024) else (0.01, 0.1)
                )
    # Native exception: Phase HF/Laser fine increment is x5, not x10.
    phase = next(
        r
        for r in result["lines"]["direct"]["step_paths"]
        if r["row_indices"] == [2] and r["action"] == 512
    )
    assert (phase["false_step"], phase["true_step"]) == (1.0, 5.0)


def test_acquisition_receives_four_numeric_banks_and_uses_separate_runtime_writer(
    sources,
):
    result = trace.build_trace(*sources)
    assert [r["local_bank"] for r in result["acq_receivers"]] == [9, 10, 11, 12]
    assert [r["reader_uid"] for r in result["acq_receivers"]] == [
        "10310",
        "10333",
        "10369",
        "10449",
    ]
    assert all(
        r["uri"].startswith("ni.var.psp://10.20.30.2/SUPERVISION/")
        for r in result["acq_receivers"]
    )
    assert all(r["call_uid"] == "278" for r in result["acq_runtime_writer"])
    # Raw missing connector index is preserved, never normalized to zero.
    assert result["acq_runtime_writer"][0]["raw_connector_index"] is None


def test_forward_routes_keep_omitted_indices_unknown_and_prove_h2_route(sources):
    result = trace.build_trace(*sources)
    routes = [
        r for line in result["lines"].values() for r in line["forward_setpoint_routes"]
    ]
    assert len(routes) == 20
    assert sum(r["target_field_qualified"] for r in routes) == 18
    assert all(
        r["destination"]["raw_index"] is None and r["destination"]["label_path"] is None
        for r in routes
        if not r["target_field_qualified"]
    )
    h2 = next(
        r for r in routes if r["source"]["label_path"] == ["Correcteur H2", "Consigne"]
    )
    assert h2["bank"] == "C6NI6703"
    assert h2["destination"]["raw_index"] == 2


def test_rejects_step_polarity_swap(sources):
    receipt, roots, acq = sources
    roots = copy.deepcopy(roots)
    low = roots["bd"].find(".//*[@class='term'][@uid='7837']/dco/ConstValue")
    high = roots["bd"].find(".//*[@class='term'][@uid='7817']/dco/ConstValue")
    low.text, high.text = high.text, low.text
    with pytest.raises(AssertionError, match="step values/polarity changed"):
        trace.build_trace(receipt, roots, acq)


def test_rejects_ma_pass_through_wire_change(sources):
    receipt, roots, acq = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='signal'][@uid='8545']/termList/*").set("uid", "8155")
    with pytest.raises(AssertionError, match="seven unchanged pass-through wires"):
        trace.build_trace(receipt, roots, acq)


def test_rejects_added_digital_command_publication(sources):
    receipt, roots, acq = sources
    roots = copy.deepcopy(roots)
    term = roots["bd"].find(".//*[@class='term'][@uid='11727']/dco/ConstValue")
    value = b"ni.var.psp://localhost/SUPERVISION/C3_OUT_DIO96"
    term.text = (len(value).to_bytes(4, "big") + value).hex().upper()
    with pytest.raises(AssertionError, match="publication bank/data identity changed"):
        trace.build_trace(receipt, roots, acq)


def test_rejects_lost_x1_field_to_selector_path(sources):
    receipt, roots, acq = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='signal'][@uid='7933']/termList/*[@uid='7700']").set(
        "uid", "7697"
    )
    with pytest.raises(AssertionError, match="saved wire path absent"):
        trace.build_trace(receipt, roots, acq)


def test_rejects_retained_boolean_becoming_adjustment_enable(sources):
    receipt, roots, acq = sources
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='signal'][@uid='11090']/termList/*[@uid='8265']").set(
        "uid", "7700"
    )
    with pytest.raises(AssertionError, match="retained Boolean gained a computation"):
        trace.build_trace(receipt, roots, acq)


def test_rejects_changed_acquisition_receive_destination(sources):
    receipt, roots, acq = sources
    bd, meta = copy.deepcopy(acq)
    bd.find(".//*[@class='gRef'][@uid='10392']/termList/*/dco/paramIdx").text = "17"
    with pytest.raises(
        AssertionError, match="runtime local identity/direction changed"
    ):
        trace.build_trace(receipt, roots, (bd, meta))


def test_rejects_changed_current_select_metadata(monkeypatch, sources):
    monkeypatch.setattr(trace, "COMPARISON_SHA", "0" * 64)
    with pytest.raises(AssertionError, match="current Select metadata hash changed"):
        trace.build_trace(*sources)
