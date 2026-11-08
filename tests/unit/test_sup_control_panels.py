"""Pin the saved panel palettes, not hardware state or permission."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_control_panels as exporter


def test_four_panel_palettes_match_saved_source_without_default_telemetry():
    panel = exporter.build_panel()
    assert panel == json.loads(exporter.OUTPUT.read_text("utf-8"))
    assert not panel["hardware_commands"]
    assert not panel["saved_values_used_as_telemetry"]
    pages = panel["pages"]
    assert [len(pages[p]["fields"]) for p in pages] == [12, 28, 26, 14]
    assert (
        pages["radioprotection"]["fields"]["0"]["true_text"] == "PORTE LOURDE\nFERMEE"
    )
    assert pages["radioprotection"]["fields"]["4"]["true_color"] == "#FF3333"
    assert pages["ht"]["fields"]["27"]["false_color"] == "#00C82D"
    assert pages["ht"]["fields"]["27"]["true_color"] == "#B3B3B3"
    assert pages["hf"]["fields"]["0"]["saved_format"] == "%.2f"
    assert panel["power_state"]["inputs_inverted"]
    assert len(panel["power_state"]["indices"]) == 16
    assert panel["power_state"]["states"][0]["color"] == "#BCBCBC"
    assert panel["power_state"]["states"][3]["color"] == "#64FF00"
    assert not panel["power_state"]["permission_decision"]


def test_refuses_changed_control_identity(monkeypatch):
    receipt, roots = copy.deepcopy(exporter.original())
    child = next(
        n
        for n in roots["fp"].iter()
        if n.get("uid") == "67387" and n.get("class") == "stdBool"
    )
    child.find("partsList/*/textRec/text").text = '"different field"'
    monkeypatch.setattr(exporter, "original", lambda: (receipt, roots))
    with pytest.raises(AssertionError, match="identity"):
        exporter.build_panel()


def test_refuses_changed_power_input_inversion(monkeypatch):
    receipt, roots = copy.deepcopy(exporter.original())
    term = next(
        n
        for n in roots["bd"].iter()
        if n.get("uid") == "85348" and n.get("class") == "term"
    )
    flags = term.find("dco/objFlags")
    flags.text = str(int(flags.text) & ~0x10000)
    monkeypatch.setattr(exporter, "original", lambda: (receipt, roots))
    with pytest.raises(AssertionError, match="inversion"):
        exporter.build_panel()
