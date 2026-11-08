import copy
import json
from types import SimpleNamespace

import pytest

from tools.acq_psp_telemetry_check import (
    BANKS, PSP_DEVICE, TELEMETRY_DEVICE, capture_live, compare_snapshots, main,
)


def bank(value=3.5, label="raw field", kind="DBL"):
    return dict(data=[value], lv_type=dict(type="LvVariant", contained_type=dict(
        type="Cluster", fields=[dict(name=label, type=kind)])),
        error=dict(status=False, code=0, source=""), age_seconds=0.1, stale=False,
        producer_kind="copied_acquisition", session_id="producer", sequence=1)


def snapshot(**banks):
    return dict(source="copied_labview_telemetry", hardware_writes=False,
                storage_mode="ram_latest", receiver_session="receiver",
                received_this_process=10, publications=banks or {BANKS[0]: bank()})


def receipt(value=3.5, label="raw field", stamp=99.5, **extra):
    return dict(raw_channel=label, recv_ts=stamp, value=value, **extra)


def check(before=None, receipts=None, after=None):
    before = before if before is not None else snapshot()
    return compare_snapshots(before, [receipt()] if receipts is None else receipts,
                             copy.deepcopy(before) if after is None else after, now=100.0)


def test_equal_values_are_only_partial_consistency_not_full_parity():
    result = check()
    assert result["counts"] == {"consistent_stationary_endpoints": 1}
    assert result["verdict"] == "PARTIAL_CONSISTENCY"
    assert result["full_parity_verified"] is False
    assert result["hardware_sample_identity_verified"] is False
    assert len(result["missing_banks_after"]) == 26
    assert result["values_in_report"] is False
    assert '"value"' not in json.dumps(result)


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_boolean_psp_encoding_is_exact_zero_or_one(value):
    result = check(snapshot(**{BANKS[0]: bank(bool(value), kind="Boolean")}), [receipt(value)])
    assert result["counts"] == {"consistent_stationary_endpoints": 1}


@pytest.mark.parametrize("value", [2.0, -1.0, "1", True, None, float("nan")])
def test_boolean_does_not_accept_truthiness(value):
    result = check(snapshot(**{BANKS[0]: bank(True, kind="Boolean")}), [receipt(value)])
    assert result["counts"] == {"invalid_numeric_value": 1}


def test_duplicate_raw_label_never_guesses_bank_from_value():
    result = check(snapshot(**{BANKS[0]: bank(), BANKS[1]: bank(8)}))
    assert result["counts"] == {"ambiguous_raw_label": 2}


@pytest.mark.parametrize("field,value,status", [
    ("stale", True, "telemetry_stale"),
    ("age_seconds", 50.0, "telemetry_stale"),
    ("age_seconds", float("nan"), "telemetry_stale"),
    ("error", dict(status=True, code=1), "telemetry_read_error"),
    ("error", {}, "telemetry_read_error"),
    ("producer_kind", "fixture", "not_copied_acquisition"),
])
def test_bad_telemetry_cannot_be_accepted(field, value, status):
    before = snapshot()
    before["publications"][BANKS[0]][field] = value
    assert check(before)["counts"] == {status: 1}


def test_psp_receipt_age_not_global_receiver_state():
    assert check(receipts=[receipt(stamp=1)])["counts"] == {"psp_stale": 1}
    assert check(receipts=[])["counts"] == {"no_recent_psp_receipt": 1}


def test_rejects_future_and_nonfinite_receipt_timestamps():
    result = check(receipts=[receipt(stamp=101), receipt(stamp=float("nan"))])
    assert result["invalid_psp_receipts"] == 2
    assert result["counts"] == {"no_recent_psp_receipt": 1}


def test_chooses_latest_receipt_not_list_position():
    assert check(receipts=[receipt(stamp=99.9), receipt(1, stamp=99)])["counts"] == {
        "consistent_stationary_endpoints": 1}


def test_canonical_archive_path_not_substituted_for_raw_bank_field():
    assert check(receipts=[receipt(label="elyse/cooling/canon/temperature/measurement")])["counts"] == {
        "no_recent_psp_receipt": 1}


def test_changed_endpoints_are_not_called_mismatch_or_parity():
    after = snapshot(**{BANKS[0]: bank(8)})
    assert check(after=after)["counts"] == {"source_changing_not_same_sample": 1}


def test_real_difference_is_reported_without_values():
    result = check(receipts=[receipt(1000)])
    assert result["counts"] == {"different_values": 1}
    assert result["verdict"] == "DIFFERENCES_OBSERVED"
    assert "1000" not in json.dumps(result)


@pytest.mark.parametrize("receiver_change", [True, False])
def test_session_change_invalidates_comparison(receiver_change):
    after = snapshot()
    if receiver_change:
        after["receiver_session"] = "new"
    else:
        after["publications"][BANKS[0]]["session_id"] = "new"
    assert check(after=after)["counts"] == {"session_changed": 1}


def test_arrays_and_invalid_cluster_shapes_remain_explicit_gaps():
    before = snapshot()
    before["publications"][BANKS[0]]["lv_type"]["contained_type"] = {"type": "Array"}
    before["publications"][BANKS[1]] = bank()
    before["publications"][BANKS[1]]["data"] = []
    result = check(before)
    assert result["unsupported_bank_types_after"] == {BANKS[0]: "Array"}
    assert result["invalid_schema_banks"] == [BANKS[1]]
    assert result["verdict"] == "INCONCLUSIVE"


def test_float_nonfinite_marker_is_not_fabricated_as_zero():
    result = check(snapshot(**{BANKS[0]: bank({"nonfinite": "NaN"})}), [receipt(0)])
    assert result["counts"] == {"invalid_numeric_value": 1}


def test_capture_only_uses_fixed_read_only_receivers_and_operations():
    calls = []
    class Proxy:
        def __init__(self, device):
            assert device in (PSP_DEVICE, TELEMETRY_DEVICE)
            self.device = device
            calls.append((device, "create"))
        def set_timeout_millis(self, timeout):
            assert timeout == 5000
        def read_attribute(self, attribute):
            assert self.device == TELEMETRY_DEVICE and attribute == "telemetry_json"
            calls.append((self.device, "read"))
            return SimpleNamespace(value=json.dumps(snapshot()))
        def command_inout(self, command, seconds):
            assert self.device == PSP_DEVICE and command == "get_history_json" and seconds == 2.0
            calls.append((self.device, command))
            return json.dumps([receipt()])
    result = capture_live(Proxy, wall_clock=lambda: 100.0, mono_clock=lambda: 1.0)
    assert result["counts"] == {"consistent_stationary_endpoints": 1}
    assert [operation for device, operation in calls] == ["create", "create", "read", "get_history_json", "read"]


def test_zero_reference_is_a_diagnostic_not_proof_of_zero_hardware():
    result = check(receipts=[receipt(0)])
    assert result["all_recent_numeric_psp_values_zero"] is True
    assert result["counts"] == {"different_values": 1}
    assert check(receipts=[])["all_recent_numeric_psp_values_zero"] is None


@pytest.mark.parametrize("max_age", [0, -1, float("nan"), 11, True])
def test_capture_rejects_bad_window_before_connecting(max_age):
    def forbidden_proxy(device):
        raise AssertionError("must validate before network access")
    with pytest.raises(ValueError):
        capture_live(forbidden_proxy, max_age=max_age)


def test_both_missing_sessions_do_not_count_as_same_valid_session():
    before = snapshot()
    del before["publications"][BANKS[0]]["session_id"]
    assert check(before)["counts"] == {"invalid_transport_contract": 1}


@pytest.mark.parametrize("kwargs", [dict(max_age=0), dict(atol=-1), dict(rtol=float("nan"))])
def test_invalid_tolerances_fail(kwargs):
    with pytest.raises(ValueError):
        compare_snapshots(snapshot(), [], snapshot(), now=100.0, **kwargs)


def test_cli_requires_explicit_live_switch_without_importing_tango():
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
