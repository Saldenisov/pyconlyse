"""Regression and mutation tests for the saved error-1100 native repair."""

import sys
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import validate_acq_legacy_hook_retirement as retirement  # noqa: E402
from validate_acq_shared_state_helpers import node  # noqa: E402

pytestmark = pytest.mark.skipif(
    not retirement.SOURCE.exists(), reason="native evidence required"
)


@pytest.fixture
def exports():
    before = retirement.NativeExport(
        retirement.EVIDENCE / "startup_error1100_static" / retirement.NAME
    )
    after = retirement.NativeExport(
        retirement.EVIDENCE / "startup_error1100_fixed_static" / retirement.NAME
    )
    return before, after


def test_only_obsolete_helper_changed():
    report = retirement.audit()
    assert report["compared_files"] == 58
    assert report["changed_files"] == ["ACQ_Telemetry_Publish.vi"]


@pytest.mark.parametrize(
    "field,value",
    [("activeDiag", "00"), ("defaultDiag", "00"), ("commentMode", "False")],
)
def test_reenabled_legacy_queue_rejected(exports, field, value):
    before, after = exports
    node(after.bd, "commentNode", "212").find(field).text = value
    with pytest.raises(AssertionError, match="must remain disabled"):
        retirement.validate(before, after)


def test_false_successful_enqueue_claim_rejected(exports):
    before, after = exports
    node(after.bd, "bDConstDCO", "650").find("ConstValue").text = "00"
    with pytest.raises(AssertionError, match="not enqueued=True"):
        retirement.validate(before, after)


def test_nonzero_telemetry_error_rejected(exports):
    before, after = exports
    node(after.bd, "bDConstDCO", "613").find("ConstValue").text = "010000044C0000000000"
    with pytest.raises(AssertionError, match="must be no error"):
        retirement.validate(before, after)


def test_active_queue_call_rejected(exports):
    before, after = exports
    active = node(after.bd, "diag", "364")
    active.find("zPlaneList").append(deepcopy(node(before.bd, "prim", "43")))
    with pytest.raises(AssertionError, match="outside retired body"):
        retirement.validate(before, after)


def test_disconnected_output_rejected(exports):
    before, after = exports
    node(after.bd, "diag", "364").find("signalList/*/termList/*").set("uid", "999")
    with pytest.raises(AssertionError, match="outputs disconnected"):
        retirement.validate(before, after)


def test_changed_connector_rejected(exports):
    before, after = exports
    node(after.fp, "fPDCO", "592").find("conNum").text = "12"
    with pytest.raises(AssertionError, match="connector"):
        retirement.validate(before, after)


def test_extra_psp_write_rejected(exports):
    before, after = exports
    ET.SubElement(
        node(after.bd, "diag", "364").find("zPlaneList"),
        "SL__arrayElement",
        {"class": "sharedVariableDynamicWrite", "uid": "999"},
    )
    with pytest.raises(AssertionError, match="dynamic operation"):
        retirement.validate(before, after)


def test_run_on_open_rejected(exports):
    before, after = exports
    after.metadata.find("LVSR/Section/Execution").set("RunOnOpen", "1")
    with pytest.raises(AssertionError, match="RunOnOpen"):
        retirement.validate(before, after)


def test_legacy_outputs_do_not_control_main():
    main = retirement.Export(retirement.GOOD / "export" / "0_ACQ_ELYSE")
    retirement.validate_caller_outputs_unused(main)


def test_using_legacy_output_for_control_rejected():
    main = retirement.Export(retirement.GOOD / "export" / "0_ACQ_ELYSE")
    # An output connected anywhere in the diagram must invalidate retirement.
    signal = next(n for n in main.bd.iter() if n.get("class") == "signal")
    ET.SubElement(signal.find("termList"), "SL__arrayElement", {"uid": "46120"})
    with pytest.raises(AssertionError, match="affects caller control flow"):
        retirement.validate_caller_outputs_unused(main)
