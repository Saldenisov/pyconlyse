"""Source-checked stage transfer; all runs are offline and non-actuating."""
import copy
import hashlib
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from build_acq_modulator_catalog import build, OUTPUT
from legacy.xp_acq_agent.elyse_agent.acquisition_stage_model import CATALOG_SHA256, load_model
from legacy.xp_acq_agent.tests.test_acquisition_stage_model import StageModelTests as StageModelTests
import trace_acq_modulator_stage_safety as safety


def test_catalog_matches_complete_original_frame_graphs(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network in stage transfer")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert json.loads(OUTPUT.read_text("utf-8")) == build()
    assert hashlib.sha256(OUTPUT.read_bytes()).hexdigest() == CATALOG_SHA256
    assert load_model()._catalog["focal_helpers"]["reset"] is True


@pytest.fixture(scope="module")
def roots():
    return safety.original()[1]


def test_report_reproduces_with_no_live_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network in safety trace")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    report = safety.build()
    assert report == json.loads(safety.OUTPUT.read_text("utf-8"))
    assert report["complete_live_control"] is False
    assert report["hardware_commands_sent"] is False
    assert len(report["observations"]["water_display"]) == 6


def test_rejects_new_modulator_disabled_property(roots):
    roots = copy.deepcopy(roots)
    node = roots["bd"].find(".//*[@class='propNode'][@uid='67698']")
    node.find("ddo").set("uid", "56140")
    with pytest.raises(AssertionError, match="Modulateur gained"):
        safety.inspect_ui(roots)


def test_rejects_new_dynamic_disabled_property(roots):
    roots = copy.deepcopy(roots)
    node = ET.fromstring('<extra class="propNode" uid="TEST"><PropItemName>"DisabledEnum"</PropItemName></extra>')
    roots["bd"].append(node)
    with pytest.raises(AssertionError, match="DisabledEnum property target census"):
        safety.inspect_ui(roots)


def test_rejects_new_modulator_control_reference(roots):
    roots = copy.deepcopy(roots)
    node = roots["bd"].find(".//*[@class='ctlRefConst'][@uid='7979']")
    node.find("ddo").set("uid", "56140")
    with pytest.raises(AssertionError, match="Modulateur gained"):
        safety.inspect_ui(roots)


def test_rejects_removed_disabled_node(roots):
    roots = copy.deepcopy(roots)
    roots["bd"].find(".//*[@class='propNode'][@uid='67698']/.//PropItemName").text = '"Value"'
    with pytest.raises(AssertionError, match="DisabledEnum property target census"):
        safety.inspect_ui(roots)


@pytest.fixture(scope="module")
def acq_root():
    return safety.checked_root(safety.ACQ)


def test_c4_raw_input_consumers_are_not_klystron_water_permits(acq_root):
    result = safety.inspect_c4_consumers(acq_root)
    assert result["only_direct_local_unbundle_fields"] == [19, 38]
    assert len(result["references"]) == 6
    assert [r["peer_class"] for r in result["references"] if r["access"] == "read"] == [
        "sharedVariableDynamicOpen", "sharedVariableDynamicWrite", "nMux"]


def test_rejects_new_c4_read_or_extra_fanout(acq_root):
    root = copy.deepcopy(acq_root)
    root.find(".//*[@class='signal'][@uid='40077']/termList").append(ET.Element("t", uid="EXTRA_GUARD"))
    with pytest.raises(AssertionError, match="fanout"):
        safety.inspect_c4_consumers(root)


def test_rejects_c4_local_read_replaced_with_write(acq_root):
    root = copy.deepcopy(acq_root)
    root.find(".//*[@class='gRef'][@uid='10202']/termList/*/dco/objFlags").text = "0"
    with pytest.raises(AssertionError, match="direction"):
        safety.inspect_c4_consumers(root)
