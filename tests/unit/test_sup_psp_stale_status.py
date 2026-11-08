"""PSP source mutations and non-actuating stale-snapshot witnesses."""

import copy
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_psp_stale_status as stale


@pytest.fixture(scope="module")
def sources():
    return stale.original()


@pytest.fixture(scope="module")
def report(sources):
    return stale.verify(*sources)


def test_reproduces_without_network_native_or_production_changes(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden during static PSP analysis")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = stale.verify(*sources)
    assert result == json.loads(stale.OUTPUT.read_text("utf-8"))
    assert not any(
        result[key]
        for key in (
            "native_PSP_failure_policy_verified",
            "observed_live_race",
            "complete_Supervision_coverage",
            "screen_used",
            "vi_run_or_save",
            "hardware_io",
            "network_io",
            "production_changes",
        )
    )


def test_eleven_results_write_even_without_a_freshness_decision(report):
    rows = report["observations"]["periodic_PSP_read_chain"]
    assert len(rows) == 11
    assert all(
        not r["timestamp_connected"] and not r["result_write_error_gated"] for r in rows
    )
    assert all(r["previous_read_error_path"] for r in rows[1:])
    assert rows[0]["previous_read_error_path"] == []
    c3 = rows[3]
    assert c3["bank"] == "C3_IN_DIO96"
    assert c3["ports"]["timestamp"] == "15591"
    assert c3["result_local_writer"] == "15663"


def test_separate_c3_reads_are_not_invented_as_an_internal_bank_race(report):
    obs = report["observations"]
    assert obs["C3_local_writer_census"] == ["15663"]
    assert obs["C3_internal_writer_and_status_readers_share_one_ordered_loop"]
    assert [r["reference_uid"] for r in obs["C3_status_snapshots"]] == [
        "14210",
        "61458",
    ]
    assert obs["ingest_outer_frame"] < obs["indicator_outer_frame"]
    assert not obs["computed_fault_writer_enabled"]


def test_timeout_numeric_writers_retain_all_twenty_two_status_flags(report):
    rows = report["observations"]["Voie_directe_RMW_writers"][:2]
    statuses = {12 * row + offset for row in range(11) for offset in (2, 4)}
    assert [r["writer"] for r in rows] == ["7430", "7502"]
    assert all(len(r["changed_indices"]) == 11 for r in rows)
    assert all(statuses.isdisjoint(r["changed_indices"]) for r in rows)
    assert all(r["frame_uid"] == "7699" and r["loop"] == "6017" for r in rows)


def test_older_timeout_snapshot_restores_flags_after_periodic_status_refresh():
    # H2 indices from the audited type/wire map. These are fabricated test values.
    current = {62: False, 64: False, 66: 1.0, 67: 1.0}
    timeout_snapshot = current.copy()
    current = stale.copy_back(current.copy(), {62: True})  # frame0 running
    current = stale.copy_back(current.copy(), {64: True})  # frame1 raw fault
    assert current[62] is True and current[64] is True
    current = stale.copy_back(timeout_snapshot, {66: 2.0})  # later Timeout write
    assert current == {62: False, 64: False, 66: 2.0, 67: 1.0}
    assert timeout_snapshot == {62: False, 64: False, 66: 1.0, 67: 1.0}


def test_next_raw_pass_can_repair_but_not_guarantee_persistent_recovery():
    current = {62: False, 64: False, 66: 1.0, 67: 1.0}
    timeout_snapshot = current.copy()
    current = stale.copy_back(current, {62: True})
    current = stale.copy_back(current, {64: True})
    assert current[62] and current[64]
    current = stale.copy_back(timeout_snapshot, {67: 3.0})
    assert not current[62] and not current[64]
    current = stale.copy_back(current, {62: True})
    current = stale.copy_back(current, {64: True})
    assert current[62] and current[64]


def test_numeric_same_frame_rmw_can_lose_an_independent_numeric_change():
    current = {62: True, 64: False, 66: 1.0, 67: 1.0}
    command_snapshot, measured_snapshot = current.copy(), current.copy()
    current = stale.copy_back(command_snapshot, {66: 2.0})
    current = stale.copy_back(measured_snapshot, {67: 3.0})
    assert current[66] == 1.0 and current[67] == 3.0
    # No race is inevitable: a read after the first write retains both changes.
    current = stale.copy_back(current, {66: 2.0})
    assert current[66] == 2.0 and current[67] == 3.0


def test_phase_flags_are_retained_not_repaired_by_numeric_or_other_row_updates(report):
    current = {26: True, 28: True, 62: False, 64: False}
    current = stale.copy_back(current, {62: True, 64: True})
    assert current[26] and current[28]
    for r in report["observations"]["Voie_directe_RMW_writers"]:
        assert {26, 28}.isdisjoint(r["changed_indices"])


def test_native_psp_error_outputs_and_live_timing_are_not_synthesized(report):
    assert not report["native_PSP_failure_policy_verified"]
    assert not report["observed_live_race"]
    unknown = " ".join(report["requires_native_evidence_or_remains_unknown"])
    assert "No zero" in unknown and "blocking" in unknown and "latency" in unknown


def test_rejects_result_wire_detached_from_the_local(sources):
    r, x = sources
    x = copy.deepcopy(x)
    for signal in x["bd"].findall(".//*[@class='signal']"):
        if any(p.get("uid") == "15588" for p in signal.findall("termList/*")):
            signal.find("termList/*[@uid='15666']").set("uid", "NO_RESULT_LOCAL")
    with pytest.raises(AssertionError, match="gRef peer"):
        stale.verify(r, x)


def test_rejects_timestamp_consumer_added(sources):
    r, x = sources
    x = copy.deepcopy(x)
    signal = ET.SubElement(
        x["bd"].find("root/nodeList"),
        "SL__arrayElement",
        {
            "class": "signal",
            "uid": "NEW_TIMESTAMP_CONSUMER",
        },
    )
    ports = ET.SubElement(signal, "termList")
    ET.SubElement(ports, "SL__arrayElement", {"uid": "15591"})
    ET.SubElement(ports, "SL__arrayElement", {"uid": "TIME_AGE_CHECK"})
    with pytest.raises(AssertionError, match="freshness consumer"):
        stale.verify(r, x)


def test_rejects_broken_upstream_error_chain(sources):
    r, x = sources
    x = copy.deepcopy(x)
    for signal in x["bd"].findall(".//*[@class='signal']"):
        terminal = signal.find("termList/*[@uid='15579']")
        if terminal is not None:
            terminal.set("uid", "CLEARED_ERROR")
    with pytest.raises(AssertionError, match="saved wire path absent"):
        stale.verify(r, x)


def test_rejects_extra_c3_local_writer(sources):
    r, x = sources
    x = copy.deepcopy(x)
    node = copy.deepcopy(x["bd"].find(".//*[@class='gRef'][@uid='15663']"))
    node.set("uid", "ADDITIONAL_C3_WRITER")
    node.find("termList/*").set("uid", "NEW_WRITE_PORT")
    x["bd"].find("root/nodeList").append(node)
    with pytest.raises(AssertionError, match="C3 local writer census"):
        stale.verify(r, x)


def test_rejects_new_guard_on_c3_result_write(sources):
    r, x = sources
    x = copy.deepcopy(x)
    zplane = x["bd"].find(".//*[@class='diag'][@uid='18099']/zPlaneList")
    writer = zplane.find("*[@class='gRef'][@uid='15663']")
    zplane.remove(writer)
    guard = ET.SubElement(
        zplane, "SL__arrayElement", {"class": "select", "uid": "NEW_RESULT_GUARD"}
    )
    ET.SubElement(guard, "nodeList").append(writer)
    with pytest.raises(AssertionError, match="result gained an error guard"):
        stale.verify(r, x)


def test_rejects_numeric_bundle_changing_a_flag(sources):
    r, x = sources
    x = copy.deepcopy(x)
    x["bd"].find(".//*[@class='term'][@uid='14154']/dco/i").text = "2"
    with pytest.raises(AssertionError, match="RMW field schema"):
        stale.verify(r, x)


def test_rejects_sequence_misclassified_as_true_false_case(sources):
    r, x = sources
    x = copy.deepcopy(x)
    x["bd"].find(".//*[@class='sequence'][@uid='13595']").set("class", "select")
    with pytest.raises(AssertionError, match="Timeout sequence identity"):
        stale.verify(r, x)


def test_rejects_an_added_loop_data_dependency(sources):
    r, x = sources
    x = copy.deepcopy(x)
    loop = x["bd"].find(".//*[@class='whileLoop'][@uid='6017']")
    ET.SubElement(loop.find("termList"), "SL__arrayElement", {"uid": "NEW_LOOP_INPUT"})
    with pytest.raises(AssertionError, match="loop boundary gained a wire"):
        stale.verify(r, x)
