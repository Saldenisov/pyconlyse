"""Static display provenance only. No runtime, PSP, Tango, or hardware calls."""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import export_sup_live_display_map as exporter


@pytest.fixture(scope="module")
def original_roots():
    return exporter.original()


def test_generated_map_matches_original_wires_and_does_not_claim_full_parity(
    original_roots, monkeypatch
):
    monkeypatch.setattr(exporter, "original", lambda: original_roots)
    actual = exporter.build_map()
    assert actual == json.loads(exporter.OUTPUT.read_text("utf-8"))
    assert len(actual["rules"]) == 94
    assert not actual["hardware_writes"]
    assert not actual["whole_runtime_equivalence"]
    assert not actual["color_polarity_qualified"]
    rows = {row["id"]: row for row in actual["rules"]}
    assert (
        rows["fluides:22"]["index"] == 8
    )  # native flattened target ordinal29, not29th UI field
    assert rows["modulateur:42"]["scale"] == 3
    assert rows["modulateur:43"]["scale"] == 4.11
    assert rows["vide:12"]["native_filter_samples"] == 30
    assert not rows["vide:12"]["temporal_equivalence"]
    assert rows["vide:3"]["offset"] == 0.0026
    assert rows["vide:3"]["scale"] == -4e-6
    assert rows["hf:0"]["index"] == 44
    assert rows["hf:0"]["transform"] == "attenuator_formula"


@pytest.mark.parametrize("terminal", ["136502", "130869", "216586", "161658"])
def test_refuses_changed_calibration_or_native_filter(
    original_roots, monkeypatch, terminal
):
    receipt, roots = copy.deepcopy(original_roots)
    term = next(
        n
        for n in roots["bd"].iter()
        if n.get("class") == "term" and n.get("uid") == terminal
    )
    term.find("dco/ConstValue").text = "00000000"
    monkeypatch.setattr(exporter, "original", lambda: (receipt, roots))
    with pytest.raises((AssertionError, ValueError, __import__("struct").error)):
        exporter.build_map()
