"""Check copied controls, exact original PNG and direct source terminal wires."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_sup_workspace as exporter


def test_workspace_matches_original_source_and_retains_duplicate_native_read():
    result, png = exporter.build_workspace()
    assert result == json.loads(exporter.WORKSPACE_OUTPUT.read_text("utf-8"))
    assert hashlib.sha256(png).hexdigest() == result["synoptic"]["png_sha256"]
    assert png == exporter.IMAGE_OUTPUT.read_bytes()
    assert result["display_wire_count"] == 40
    assert [len(result["lines"][line]["rows"]) for line in ("direct", "deviated")] == [
        11,
        9,
    ]
    rows = result["lines"]["deviated"]["rows"]
    assert rows[7]["lecture"]["index"] == rows[8]["lecture"]["index"] == 34
    assert not result["hardware_writes"]
    assert not result["saved_values_used_as_telemetry"]
    direct = result["lines"]["direct"]["rows"]
    assert direct[3]["native_range_label"] == "-5A à 5A"
    assert direct[3]["native_range_uid"] == "29786"
    assert direct[3]["column"] == direct[4]["column"] == 1
    assert (direct[3]["row"], direct[4]["row"]) == (2, 3)
    assert direct[1]["native_formats"] == {"consigne": "%.1f", "lecture": "%.1f"}
    assert direct[2]["native_range_label"] == "0 à 360°"
    assert direct[7]["native_formats"]["lecture"] == "%.2g"


def test_refuses_changed_readback_source_index():
    receipt, roots = copy.deepcopy(exporter.original())
    node = roots["bd"].find(".//*[@class='nMux'][@uid='12095']")
    node.find("termList/*[@uid='12406']/dco/i").text = "29"
    with pytest.raises(AssertionError, match="line source field changed"):
        exporter.build_workspace(receipt, roots)


def test_refuses_changed_native_button_field_identity():
    receipt, roots = copy.deepcopy(exporter.original())
    node = roots["fp"].find(".//*[@class='stdBool'][@uid='15513']")
    node.find("partsList/*/textRec/text").text = '"different control"'
    with pytest.raises(AssertionError, match="native line control field order changed"):
        exporter.build_workspace(receipt, roots)


def test_refuses_changed_corrector_range_label():
    receipt, roots = copy.deepcopy(exporter.original())
    node = roots["fp"].find(".//*[@class='label'][@uid='29786']")
    node.find("textRec/text").text = '"-50A à 50A"'
    with pytest.raises(AssertionError, match="native line range label changed"):
        exporter.build_workspace(receipt, roots)


def test_button_controls_keep_original_six_roles_and_corrector_step_choices():
    result, _ = exporter.build_workspace()
    for line in result["lines"].values():
        for row in line["rows"]:
            controls = row["native_buttons"]
            assert [c["label"] for c in controls] == [
                "M/A",
                "X1/X10",
                "<<",
                "<",
                ">",
                ">>",
            ]
            assert [c["action_code"] for c in controls] == [1, 16, 128, 256, 512, 1024]
            assert [c["field_index"] for c in controls] == [0, 4, 7, 8, 9, 10]
            assert not any(c["commands_enabled"] for c in controls)
            if row["label"].startswith("Correcteur"):
                assert [c["step_choices"] for c in controls[2:]] == [
                    [0.1, 1.0],
                    [0.01, 0.1],
                    [0.01, 0.1],
                    [0.1, 1.0],
                ]
                assert not any(
                    c["boolean_to_step_polarity_qualified"] for c in controls[2:]
                )


def test_refuses_changed_native_corrector_button_label():
    receipt, roots = copy.deepcopy(exporter.original())
    roots["fp"].find(
        ".//*[@class='stdBool'][@uid='29827']/partsList/*/textRec/text"
    ).text = '"<"'
    with pytest.raises(AssertionError, match="native line control field order changed"):
        exporter.build_workspace(receipt, roots)


def test_refuses_changed_original_corrector_step_literal():
    receipt, roots = copy.deepcopy(exporter.original())
    roots["bd"].find(
        ".//*[@class='term'][@uid='17246']/dco/ConstValue"
    ).text = "3FF0000000000000"
    with pytest.raises(AssertionError, match="native corrector step choices changed"):
        exporter.build_workspace(receipt, roots)


def test_refuses_changed_original_corrector_arrow_direction():
    receipt, roots = copy.deepcopy(exporter.original())
    roots["bd"].find(".//*[@class='prim'][@uid='7706']/primResID").text = "1050"
    with pytest.raises(
        AssertionError, match="native arrow arithmetic primitive changed"
    ):
        exporter.build_workspace(receipt, roots)
