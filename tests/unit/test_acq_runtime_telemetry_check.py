"""Inert schema/comparison fixtures. No cards, device servers or live network."""
import copy

import pytest

from tools.acq_runtime_telemetry_check import INPUT_BANKS, compare_inputs, load_input_labels


def fixtures():
    labels = load_input_labels()
    runtime = dict(state="RUNNING", stale=False, error="", age_seconds=0.1,
                   storage_mode="ram_latest", sequence=1, resource_count=21,
                   latest=dict(source="python_daqmx_acquisition", simulated=False, banks={}))
    reference = dict(source="copied_labview_telemetry", storage_mode="ram_latest", publications={})
    for python_bank, group, kind, count in INPUT_BANKS:
        values = [False if kind == "digital_input" else 1.0] * count
        runtime["latest"]["banks"][python_bank] = dict(
            kind=kind, values=values[:], legacy_scaled_values=values[:])
        reference["publications"][group] = dict(
            producer_kind="copied_acquisition", stale=False, age_seconds=0.1,
            error=dict(status=False), data=values[:], lv_type=dict(contained_type=dict(
                type="Cluster", name=group, fields=[dict(
                    name=labels[(group, index)], type="Boolean" if kind == "digital_input" else "DBL")
                    for index in range(count)])))
    return runtime, reference, labels


def test_all_304_match_but_full_replacement_is_never_claimed():
    result = compare_inputs(*fixtures())
    assert result["counts"] == {"consistent_values": 304}
    assert result["full_parity_verified"] is False
    assert result["hardware_sample_identity_verified"] is False
    assert sum(bank["exact_native_labels"] for bank in result["per_bank"].values()) == 304


def test_stale_equal_values_are_not_matches():
    runtime, reference, labels = fixtures()
    for packet in reference["publications"].values():
        packet.update(stale=True, age_seconds=1200)
    result = compare_inputs(runtime, reference, labels)
    assert result["counts"] == {"reference_stale": 304}
    assert result["verdict"] == "INCONCLUSIVE"


@pytest.mark.parametrize("change", ["source", "simulated", "age", "fault"])
def test_synthetic_stale_or_fault_runtime_is_rejected(change):
    runtime, reference, labels = fixtures()
    if change == "source":
        runtime["latest"]["source"] = "python_acquisition_demo"
    elif change == "simulated":
        runtime["latest"]["simulated"] = True
    elif change == "age":
        runtime["age_seconds"] = 3
    else:
        runtime["state"] = "FAULT"
    assert compare_inputs(runtime, reference, labels)["counts"] == {"python_not_current_hardware_data": 304}


def test_schema_swapping_and_boolean_numeric_coercion_are_rejected():
    runtime, reference, labels = fixtures()
    fields = reference["publications"]["C1NI6071E"]["lv_type"]["contained_type"]["fields"]
    fields[0], fields[1] = fields[1], fields[0]
    reference["publications"]["C3_IN_DIO96"]["data"][0] = 0
    result = compare_inputs(runtime, reference, labels)
    assert result["counts"] == {"schema_mismatch": 2, "invalid_scalar": 1, "consistent_values": 301}


def test_analog_scaling_not_raw_volts_is_compared_and_inputs_unchanged():
    runtime, reference, labels = fixtures()
    runtime["latest"]["banks"]["C1_NI6071E_AI"]["values"] = [123.0] * 64
    before = copy.deepcopy((runtime, reference))
    assert compare_inputs(runtime, reference, labels)["counts"] == {"consistent_values": 304}
    assert (runtime, reference) == before


def test_read_error_and_nan_cannot_be_matches():
    runtime, reference, labels = fixtures()
    reference["publications"]["C1NI6071E"]["error"]["status"] = True
    runtime["latest"]["banks"]["C2_NI6071E_AI"]["legacy_scaled_values"][0] = float("nan")
    counts = compare_inputs(runtime, reference, labels)["counts"]
    assert counts == {"reference_read_error": 64, "invalid_scalar": 1, "consistent_values": 239}


def test_negative_or_nonfinite_tolerance_rejected():
    with pytest.raises(ValueError):
        compare_inputs(*fixtures(), atol=-1)
    with pytest.raises(ValueError):
        compare_inputs(*fixtures(), max_age=float("nan"))
