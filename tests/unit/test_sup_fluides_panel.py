"""Pinned native display evidence; no VI execution or hardware access."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_fluides_panel as exporter


def test_saved_fluides_palette_and_both_valve_cases_match_frontend():
    panel = exporter.build_panel()
    assert panel == json.loads(exporter.OUTPUT.read_text("utf-8"))
    assert panel["fields"]["14"]["true_color"] == "#00C82D"
    assert panel["fields"]["15"]["true_color"] == "#FF3333"
    assert panel["fields"]["12"]["false_color"] == "#00C82D"
    assert panel["fields"]["11"]["true_text"] == "CANON\nAUCUN DEFAUT"
    assert panel["unavailable_live_fields"] == [4, 16, 21]
    assert not panel["hardware_commands"]
    for name, indices in (("CANON", [2, 3]), ("SECTION", [8, 9])):
        assert panel["valves"][name]["indices"] == indices
        assert [s["text"] for s in panel["valves"][name]["states"]] == [
            f"VANNE {name}\n{value}"
            for value in ("REGULATION", "FERMEE", "OUVERTE", "EN DEFAUT")
        ]
