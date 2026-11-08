"""Static saved-palette verification; never starts native software."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_modulator_panel as exporter


def test_saved_modulator_palette_and_formats_match_frontend():
    actual = exporter.build_panel()
    assert actual == json.loads(exporter.OUTPUT.read_text("utf-8"))
    assert len(actual["fields"]) == 48
    assert actual["fields"]["12"]["false_color"] == "#00C82D"
    assert actual["fields"]["12"]["true_color"] == "#FF3333"
    assert actual["fields"]["54"]["false_color"] == "#1E4B00"
    assert actual["fields"]["54"]["true_color"] == "#64FF00"
    assert actual["fields"]["34"]["saved_format"] == "%.2f"
    assert not actual["hardware_commands"]
    assert not actual["runtime_transitions_observed"]
