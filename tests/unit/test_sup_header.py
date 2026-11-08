"""Native frequency UI choices, not equipment execution or frequency metrology."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_header as exporter


def test_native_frequency_choices_match_committed_projection():
    result = exporter.build_header()
    assert result == json.loads(exporter.HEADER_OUTPUT.read_text("utf-8"))
    assert [choice["label"] for choice in result["choices"]] == [
        "0,2 Hz",
        "0,5 Hz",
        "1 Hz",
        "2 Hz",
        "5 Hz",
        "10 Hz",
        "25 Hz",
        "50 Hz",
    ]
    assert [choice["value"] for choice in result["choices"]] == [
        4981000,
        1981000,
        981000,
        481000,
        181000,
        81000,
        21000,
        1000,
    ]
    assert result["selection_scope"] == "local_draft_only"
    assert not result["hardware_writes"]


def test_refuses_changed_native_sparse_ring():
    receipt, roots = copy.deepcopy(exporter.original())
    ring = roots["fp"].find(".//*[@class='stdRing'][@uid='53463']")
    ring.find("ringSparseValues/*").text = "00000001"
    with pytest.raises(AssertionError, match="choices changed"):
        exporter.build_header(receipt, roots)
