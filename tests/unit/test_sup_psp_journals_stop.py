"""Pinned source mutations and fabricated journal-loss/recovery witnesses."""

import copy
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_psp_journals_stop as trace


@pytest.fixture(scope="module")
def sources():
    receipt, roots = trace.original()
    return receipt, roots, trace.journal_sources()


@pytest.fixture(scope="module")
def report(sources):
    return trace.verify(*sources)


def signal(root, uid, *ports):
    node = ET.SubElement(
        root.find("root/nodeList"), "SL__arrayElement", {"class": "signal", "uid": uid}
    )
    ts = ET.SubElement(node, "termList")
    for port in ports:
        ET.SubElement(ts, "SL__arrayElement", {"uid": port})


def test_reproduces_with_network_forbidden_and_no_native_execution(
    sources, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network allowed in journal analysis")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = trace.verify(*sources)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert not any(
        result[key]
        for key in (
            "native_failure_or_recovery_executed",
            "complete_Supervision_coverage",
            "screen_used",
            "vi_run_or_save",
            "network_io",
            "hardware_io",
            "production_changes",
        )
    )


def test_all_runtime_psp_write_error_sites_are_classified(report):
    obs = report["observations"]
    assert len(obs["runtime_PSP_write_error_sinks"]) == 63
    assert obs["runtime_PSP_write_error_sink_counts"] == {
        "unwired error output": 5,
        "Simple Error Handler.vi": 30,
        "TER error case": 25,
        "TER via downstream error case": 1,
        "remote journal acknowledgement chain": 2,
    }
    assert report["paths_are_bindings_not_alternative_branch_execution"]


def test_read_errors_do_not_feed_main_journal_or_stop_writers(report):
    sinks = report["observations"]["read_error_sinks"]
    assert [r["error_out"] for r in sinks] == ["8626", "52012", "50631"]
    assert all(not r["journal_or_stop_writer_found"] for r in sinks)
    assert sinks[0]["error_cases"] == sinks[1]["error_cases"] == []
    assert len(sinks[2]["error_cases"]) == 5


def test_success_does_not_itself_clear_ter(report):
    rows = [
        r
        for r in report["observations"]["runtime_PSP_write_error_sinks"]
        if "TER" in r["sink"]["kind"]
    ]
    assert {r["event"] for r in rows} == {6, 14, 15, 16, 17, 18}
    assert all(not r["sink"]["No_Error_clears_TER"] for r in rows)
    assert (
        len(next(r for r in rows if r["event"] == 6)["sink"]["intervening_operations"])
        == 5
    )


def test_local_message_clear_is_not_confirmation_of_disk_persistence(report):
    assert trace.journal_returned_message("PSP error A") == ""
    obs = report["observations"]
    assert obs["journal_Message_OUTPUT"]["value"] == ""
    assert obs["journal_Message_OUTPUT"]["connector"] == 1
    assert not obs["journal_disk_call_has_consumed_output"]
    assert all(not r["clearing_depends_on_disk_success"] for r in obs["local_flush"])


def test_single_slot_overwrite_can_drop_an_error_before_flush():
    # Supplied Strings, not observed telemetry or a native scheduling assertion.
    ter = "error A"
    ter = "error B"
    delivered = ter
    ter = trace.journal_returned_message(delivered)
    assert delivered == "error B" and ter == ""


def test_late_flush_clear_can_erase_a_newer_event_error():
    ter = "error A"
    journal_snapshot = ter
    ter = "error B"
    ter = trace.journal_returned_message(journal_snapshot)
    assert ter == ""  # This interleaving loses B, not an inevitable outcome.


def test_event_after_clear_is_retained_for_next_flush():
    ter = "error A"
    ter = trace.journal_returned_message(ter)
    ter = "error B"
    assert ter == "error B"


def test_failed_remote_ack_can_duplicate_message_after_later_old_snapshot():
    remote_before = ("error A", "error B")
    first = trace.remote_head_intent(remote_before)
    assert first == {"message": "error A", "publish_tail": ("error B",)}
    local_after = first["publish_tail"]
    # Conditional witness: failed publication, then supplied old PSP data again.
    second = trace.remote_head_intent(remote_before)
    assert local_after == ("error B",)
    assert second["message"] == first["message"]


def test_confirmed_fresh_tail_moves_to_next_message_without_replaying_old_head():
    first = trace.remote_head_intent(("error A", "error B"))
    second = trace.remote_head_intent(first["publish_tail"])
    assert second == {"message": "error B", "publish_tail": ()}
    assert trace.remote_head_intent(("",)) is None


@pytest.mark.parametrize("invalid", [(), [], (False,), (None,)])
def test_remote_witness_never_invents_empty_array_or_type_defaults(invalid):
    with pytest.raises(ValueError):
        trace.remote_head_intent(invalid)


def test_ack_errors_can_precede_card_read_without_originating_at_card(report):
    obs = report["observations"]
    assert obs["acknowledgement_error_to_VTL"]
    assert obs["VTL_acknowledgement_error_to_first_card_read"]
    assert all(not r["local_tail_write_error_gated"] for r in obs["remote_flush"])


def test_global_stop_is_not_a_psp_fault_latch(report):
    obs = report["observations"]
    assert len(obs["global_stop_loop_consumers"]) == 4
    assert obs["global_stop_local_writers"] == ["12664"]
    assert obs["global_stop_reset"] == {
        "outer_frame": 3,
        "value": False,
        "wire": "12845",
    }
    assert not obs["polling_or_event_error_shift_register_found"]
    assert {r["event"] for r in obs["explicit_Clear_Errors_calls"]} == {25, 30, None}


def test_dialog_abort_reconnect_and_disk_semantics_remain_unqualified(report):
    unknown = " ".join(report["unknown_or_requires_native_qualification"])
    assert all(
        s in unknown
        for s in ("Continue/Stop", "reconnect", "disk persistence", "startup")
    )
    assert not report["native_failure_or_recovery_executed"]


def test_main_ter_has_journal_literal_clear_and_fourteen_concat_writers(report):
    rows = report["observations"]["Main_TER_local_writers"]
    assert len(rows) == 15
    clears = [r for r in rows if r["kind"] == "journal Message OUTPUT empty String"]
    assert clears == [
        {"writer": "45305", "kind": "journal Message OUTPUT empty String"}
    ]
    assert sum(r["kind"] == "String concat formatter" for r in rows) == 14
    assert any(r.get("candidate_empty_literal_present") for r in rows)


def test_unwired_psp_input_flag_does_not_turn_error_input_into_output(sources):
    r, x, _ = sources
    T, _ = trace.components()
    g = trace.SourceGraph(r, x, T(x["meta"]))
    assert not g.is_input(g.nodes["49931"])
    assert g.nodes["49931"].findtext("dco/terminal_ID") == "08"
    assert trace.error_port(g, g.nodes["49916"], True) == "49931"
    assert trace.error_port(g, g.nodes["49916"], False) == "49934"


def test_rejects_added_journal_consumer_of_timeout_read_error(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    signal(x["bd"], "NEW_READ_ERROR_SINK", "8626", "45310")
    with pytest.raises(
        AssertionError, match="read error acquired a nontrivial consumer"
    ):
        trace.verify(r, x, h)


def test_rejects_additional_global_stop_writer(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    node = copy.deepcopy(x["bd"].find(".//*[@class='gRef'][@uid='12664']"))
    node.set("uid", "NEW_GLOBAL_STOP_WRITER")
    node.find("termList/*").set("uid", "NEW_GLOBAL_STOP_PORT")
    x["bd"].find("root/nodeList").append(node)
    with pytest.raises(AssertionError, match="global stop gained another local writer"):
        trace.verify(r, x, h)


def test_rejects_cleanup_stop_false_becoming_true(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    x["bd"].find(".//*[@class='term'][@uid='12839']/dco/ConstValue").text = "01"
    with pytest.raises(AssertionError, match="post-loop stop=False reset"):
        trace.verify(r, x, h)


def test_rejects_cross_iteration_state_added_to_polling_loop(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    ts = x["bd"].find(".//*[@class='whileLoop'][@uid='5846']/termList")
    ET.SubElement(ts, "SL__arrayElement", {"uid": "NEW_LATCH"})
    with pytest.raises(AssertionError, match="cross-iteration terminal"):
        trace.verify(r, x, h)


def test_rejects_helper_return_no_longer_empty(sources):
    r, x, (hr, hx) = sources
    hx = copy.deepcopy(hx)
    hx["bd"].find(".//*[@class='term'][@uid='455']/dco/ConstValue").text = "0000000141"
    with pytest.raises(AssertionError, match="empty String return"):
        trace.verify(r, x, (hr, hx))


def test_rejects_helper_message_output_connector_change(sources):
    r, x, (hr, hx) = sources
    hx = copy.deepcopy(hx)
    hx["fp"].find(".//*[@class='fPDCO'][@uid='45']/conNum").text = "2"
    with pytest.raises(AssertionError, match="Message OUTPUT connector"):
        trace.verify(r, x, (hr, hx))


def test_rejects_new_consumed_spreadsheet_result(sources):
    r, x, (hr, hx) = sources
    hx = copy.deepcopy(hx)
    signal(hx["bd"], "NEW_DISK_RESULT", "216", "UNQUALIFIED_DISK_GATE")
    with pytest.raises(AssertionError, match="disk result gained a consumer"):
        trace.verify(r, x, (hr, hx))


def test_rejects_success_case_gaining_a_ter_clear(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    node = copy.deepcopy(x["bd"].find(".//*[@class='gRef'][@uid='40558']"))
    node.set("uid", "NEW_SUCCESS_TER_CLEAR")
    node.find("termList/*").set("uid", "NEW_SUCCESS_TER_PORT")
    # Keep paramIdx identity in the existing name map for this isolated mutation.
    r = copy.deepcopy(r)
    r["locals"].append({"uid": "NEW_SUCCESS_TER_CLEAR", "name": "TER"})
    x["bd"].find(".//*[@class='diag'][@uid='36498']/nodeList").append(node)
    with pytest.raises(AssertionError, match="TER error/success branches"):
        trace.verify(r, x, h)


def test_rejects_standard_handler_gaining_a_wired_override_or_output(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    port = x["bd"].find(".//*[@class='iUse'][@uid='8654']/termList/*").get("uid")
    signal(x["bd"], "NEW_HANDLER_OUTPUT_USE", port, "ANOTHER_NODE")
    with pytest.raises(
        AssertionError, match="handler gained an override/output consumer"
    ):
        trace.verify(r, x, h)


def test_rejects_remote_head_deletion_count_change(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    x["bd"].find(".//*[@class='term'][@uid='18115']/dco/ConstValue").text = "00000002"
    with pytest.raises(AssertionError, match="one-head deletion"):
        trace.verify(r, x, h)


def test_rejects_acknowledgement_error_detached_from_first_card_read(sources):
    r, x, h = sources
    x = copy.deepcopy(x)
    x["bd"].find(".//*[@class='signal'][@uid='35138']/termList/*[@uid='12909']").set(
        "uid", "NO_ACK_CHAIN"
    )
    with pytest.raises(AssertionError, match="saved wire path absent"):
        trace.verify(r, x, h)
