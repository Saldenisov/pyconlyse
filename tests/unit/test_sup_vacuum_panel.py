"""Native display correspondence only, no hardware/native runtime execution."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_vacuum_panel as exporter


def test_vacuum_source_identity_spatial_order_and_valve_cases():
    panel = exporter.build_panel()
    assert panel == json.loads(exporter.OUTPUT.read_text("utf-8"))
    assert not panel["hardware_commands"]
    assert not panel["layout_is_physical_length_scale"]
    assert not panel["pressure_alarm_inputs_qualified"]
    assert [p["field"] for p in panel["pressures"]] == [3, 5, 1, 14, 7, 12, 9, 17]
    assert [p["indices"] for p in panel["valves"]] == [[15, 14], [17, 16]]
    assert all(v["bank"] == "C5_IN_DIO96" for v in panel["valves"])
    assert all(v["states"][1]["color"] == "#00C82D" for v in panel["valves"])


def test_vacuum_proof_rejects_changed_valve_bit_order(monkeypatch):
    receipt, roots = copy.deepcopy(exporter.original())
    term = next(
        t
        for t in roots["bd"].iter()
        if t.get("uid") == "59020" and t.find("dco/i") is not None
    )
    term.find("dco/i").text = "14"
    monkeypatch.setattr(exporter, "original", lambda: (receipt, roots))
    with pytest.raises(AssertionError, match="bit ordinal"):
        exporter.build_panel()
