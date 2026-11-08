"""Only pinned static checks and fabricated button choices; no LabVIEW runtime."""

import copy
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_simple_error_handler as trace


@pytest.fixture(scope="module")
def sources():
    return trace.load_sources()


@pytest.fixture(scope="module")
def report(sources):
    return trace.verify(sources)


def changed(sources, key):
    # Copy only the mutated VI; Main is intentionally not copied for helper tests.
    result = dict(sources)
    result[key] = (sources[key][0], copy.deepcopy(sources[key][1]))
    return result


def node(sources, key, uid):
    return next(
        n
        for n in sources[key][1]["bd"].iter()
        if n.get("uid") == uid and n.get("class")
    )


def change_wire(sources, key, net_uid, index, replacement):
    net = node(sources, key, net_uid)
    net.findall("termList/*")[index].set("uid", replacement)


def test_report_reproduces_without_any_network(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Static handler audit must not use network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = trace.verify(sources)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert all(
        result[k] is False
        for k in (
            "screen_used",
            "vi_run_or_save",
            "network_io",
            "hardware_io",
            "production_changes",
            "deployed_library_equivalence",
            "full_Supervision_coverage",
        )
    )


def test_defaults_are_ok_not_continue_stop(report):
    obs = report["observations"]
    assert obs["Simple_dialog_default"] == obs["General_wrapper_default"] == 1
    assert obs["Simple_dialog_default_label"] == "OK message"
    assert obs["General_to_CORE_mode_remap"] == [[0, 0], [1, 1], [2, 2], [3, 4], [4, 5]]
    assert len(obs["Main_handler_calls"]) == 41
    assert all(
        not r["dialog_override"] and not r["output_consumed"]
        for r in obs["Main_handler_calls"]
    )
    assert obs["PSP_writes_using_default_Simple"] == 30


def test_null_bytes_are_not_normalized_to_unicode_replacement():
    assert trace.stored_bytes('"&#x00;&#x01;"') == b"\x00\x01"


@pytest.mark.parametrize("mode", [2, 3, 5])
@pytest.mark.parametrize("route", ["not_found", "details", "core_fallback"])
def test_continue_does_not_stop_clear_retry_or_clean_up(mode, route):
    result = trace.choice_projection(mode, "Continue", route)
    assert result["normal_return_expected_from_branch"]
    assert not any(
        v for k, v in result.items() if k != "normal_return_expected_from_branch"
    )


@pytest.mark.parametrize("mode", [2, 5])
@pytest.mark.parametrize("route", ["not_found", "details", "core_fallback"])
def test_regular_stop_is_abort_request_not_graceful_cleanup(mode, route):
    result = trace.choice_projection(mode, "Stop", route)
    assert result["requests_Stop_primitive"]
    assert not result["normal_return_expected_from_branch"]
    assert result["closes_dialog_FP_before_Stop"] == (route == "details")
    assert not result["effects_executed"]
    assert not result["sets_Main_stop_local"]
    assert not result["enters_Main_cleanup_by_itself"]
    assert not result["cleanup_guaranteed"]
    assert result["stop_event_value_if_returned"] == (route == "details")


@pytest.mark.parametrize("route", ["not_found", "details", "core_fallback"])
def test_auto_mode_propagates_stop_without_executing_stop_primitive(route):
    result = trace.choice_projection(3, "Stop", route)
    assert result["normal_return_expected_from_branch"]
    assert result["stop_event_value_if_returned"]
    assert not result["requests_Stop_primitive"]
    assert not result["cleanup_guaranteed"]


@pytest.mark.parametrize("mode", [0, 1, 4, -1, 6, True, None])
def test_unqualified_default_or_invalid_mode_is_not_simulated(mode):
    with pytest.raises(ValueError):
        trace.choice_projection(mode, "Stop", "not_found")


@pytest.mark.parametrize("choice, route", [("Help", "not_found"), ("Stop", "unknown")])
def test_unreviewed_choice_or_route_is_rejected(choice, route):
    with pytest.raises(ValueError):
        trace.choice_projection(2, choice, route)


@pytest.mark.parametrize(
    "key, wire, index, replacement",
    [
        ("simple", "220", 1, "275"),
        ("not_found", "447", 1, "496"),
        ("not_found", "425", 0, "399"),
        ("core", "3041", 1, "3080"),
        ("details", "1881", 1, "649"),
        ("details", "1914", 1, "1813"),
    ],
)
def test_changed_critical_wire_is_rejected(sources, key, wire, index, replacement):
    altered = changed(sources, key)
    change_wire(altered, key, wire, index, replacement)
    with pytest.raises(AssertionError):
        trace.verify(altered)


def test_changed_simple_default_is_rejected(sources):
    altered = changed(sources, "simple")
    fp = altered["simple"][1]["fp"]
    control = next(
        n
        for n in fp.iter()
        if n.get("class") == "fPDCO" and n.findtext("conNum") == "8"
    )
    control.find("DefaultData").text = '"&#x00;&#x02;"'
    with pytest.raises(AssertionError, match="default dialog mode changed"):
        trace.verify(altered)


def test_changed_auto_mode_exception_is_rejected(sources):
    altered = changed(sources, "not_found")
    node(altered, "not_found", "270").find("dco/DefaultData").text = '"&#x00;&#x02;"'
    with pytest.raises(AssertionError, match="constant 270 changed"):
        trace.verify(altered)


def test_changed_primitive_identity_is_rejected(sources):
    altered = changed(sources, "details")
    node(altered, "details", "403").find("primResID").text = "1352"
    with pytest.raises(AssertionError, match="primitive 403 changed"):
        trace.verify(altered)


def test_additional_main_dialog_override_is_rejected(sources):
    altered = changed(sources, "main")
    bd = altered["main"][1]["bd"]
    net = ET.SubElement(
        bd.find("root/nodeList"),
        "SL__arrayElement",
        {"class": "signal", "uid": "test-only-mode"},
    )
    ts = ET.SubElement(net, "termList")
    for port in ("12839", "14519"):
        ET.SubElement(ts, "SL__arrayElement", {"uid": port})
    with pytest.raises(AssertionError, match="override or consumed output"):
        trace.verify(altered)


def test_cleanup_is_later_frame_and_not_finally(report):
    cleanup = report["observations"]["cleanup"]
    assert cleanup["runtime_frame"] == "5902"
    assert cleanup["cleanup_frame"] == "14127"
    assert cleanup["PSP_connections"] == 13
    assert cleanup["image_buffers"] == 9
    assert not cleanup["is_finally_handler"]
    assert not cleanup["resource_groups_have_total_order"]


def test_library_and_screenshot_version_limits_are_retained(report):
    assert report["screenshots_are_not_capture_time_source_pins"]
    limits = report["unknown_or_requires_further_evidence"]
    assert any("deployed" in s and "not established" in s for s in limits)
    assert any("SelectRangeArray32" in s for s in limits)
    assert any("reclamation" in s for s in limits)
