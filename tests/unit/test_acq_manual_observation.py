"""Synthetic snapshots only; never NI, PSP or remote commands."""
import pytest

from tools.acq_manual_observation import BANKS, InputObserver, diagnostic_summary


def sample(sequence=1):
    result = dict(state="RUNNING", stale=False, error="", resource_count=21, current_operation=None,
                  storage_mode="ram_latest", auto_initialize=False, remote_initialization_enabled=False,
                  remote_setpoints_enabled=False, sequence=sequence, age_seconds=.1,
                  latest=dict(source="python_daqmx_acquisition", simulated=False, banks={}))
    for bank, _group, kind, count in BANKS:
        result["latest"]["banks"][bank] = dict(kind=kind, values=[False if kind == "digital_input" else 1.] * count)
        if kind == "analog_input":
            result["latest"]["banks"][bank]["unit"] = "V"
    return result


def test_baseline_checks_all_320_inputs_and_never_calls_a_driver():
    observer = InputObserver()
    result = observer.observe(sample(), 0, .1)
    assert result["state"] == "BASELINE" and result["values_checked"] == 320
    assert result["physical_edge_times_known"] is False
    assert result["within_snapshot_order_known"] is False
    assert result["output_readback_available"] is False


def test_digital_changes_have_verified_names_and_no_inferred_physical_order():
    observer = InputObserver()
    observer.observe(sample(), 0, .1)
    current = sample(2)
    current["latest"]["banks"]["C4_DIO96_DI"]["values"][4] = True
    current["latest"]["banks"]["C4_DIO96_DI"]["values"][8] = True
    result = observer.observe(current, .3, .4)
    assert result["state"] == "CHANGES"
    assert [(r["index"], r["before"], r["after"]) for r in result["changes"]] == [(4, False, True), (8, False, True)]
    assert all(r["label"] for r in result["changes"])
    assert result["within_snapshot_order_known"] is False
    report = diagnostic_summary(result)
    assert report["changed_digital_count"] == 2 and not report["raw_values_printed"]
    assert not any("before" in row or "after" in row for row in report["changed_inputs"])


def test_analog_noise_threshold_uses_raw_volts_not_assumed_engineering_units():
    observer = InputObserver()
    observer.observe(sample(), 0, .1)
    current = sample(2)
    values = current["latest"]["banks"]["C11_NI6220_AI"]["values"]
    values[0], values[1] = 1.001, 1.1
    result = observer.observe(current, .3, .4)
    assert len(result["changes"]) == 1 and result["changes"][0]["index"] == 1
    assert result["changes"][0]["unit"] == "V"
    assert "purpose unverified" in result["changes"][0]["label"]


@pytest.mark.parametrize("failure", ["idle", "stale", "fault", "demo", "shape", "boolean", "nan", "operation", "age", "transit"])
def test_invalid_or_stale_inputs_reset_baseline_and_do_not_produce_off_transitions(failure):
    observer = InputObserver()
    observer.observe(sample(), 0, .1)
    invalid = sample(2)
    ended = .4
    if failure == "idle": invalid["state"] = "IDLE"
    if failure == "stale": invalid["stale"] = True
    if failure == "fault": invalid["error"] = "synthetic read failure"
    if failure == "demo": invalid["latest"]["simulated"] = True
    if failure == "shape": invalid["latest"]["banks"]["C3_DIO96_DI"]["values"].pop()
    if failure == "boolean": invalid["latest"]["banks"]["C3_DIO96_DI"]["values"][0] = 1
    if failure == "nan": invalid["latest"]["banks"]["C1_NI6071E_AI"]["values"][0] = float("nan")
    if failure == "operation": invalid["current_operation"] = "modulator.general.start"
    if failure == "age": invalid["age_seconds"] = 2
    if failure == "transit": ended = 2.5
    assert observer.observe(invalid, .3, ended)["state"] == "NOT_READY"
    assert observer.previous is None
    assert observer.observe(sample(3), 3, 3.1)["state"] == "BASELINE"


def test_duplicate_is_not_new_evidence_or_a_time_boundary():
    observer = InputObserver()
    observer.observe(sample(), 0, .1)
    assert observer.observe(sample(), .2, .3)["state"] == "DUPLICATE"
    assert observer.previous_interval == [0, .1]


def test_same_sequence_with_changed_values_breaks_continuity():
    observer = InputObserver()
    observer.observe(sample(), 0, .1)
    changed = sample()
    changed["latest"]["banks"]["C4_DIO96_DI"]["values"][0] = True
    assert observer.observe(changed, .2, .3)["state"] == "NOT_READY"


def test_sequence_gaps_are_explicit_and_rollback_starts_new_baseline():
    observer = InputObserver()
    observer.observe(sample(5), 0, .1)
    assert observer.observe(sample(9), .3, .4)["source_snapshots_skipped"] == 3
    assert observer.observe(sample(1), .5, .6)["baseline_reason"] == "sequence_rollback"


def test_command_echo_changes_are_not_mistaken_for_physical_output_changes():
    observer = InputObserver()
    observer.observe(sample(), 0, .1)
    current = sample(2)
    current["latest"]["commanded_digital"] = {"C4_DIO96_DO": [True] * 32}
    assert observer.observe(current, .3, .4)["changes"] == []


def test_baseline_does_not_alias_the_input_payload():
    observer = InputObserver()
    current = sample()
    observer.observe(current, 0, .1)
    current["latest"]["banks"]["C4_DIO96_DI"]["values"][0] = True
    assert observer.previous[("C4_DIO96_DI", 0)] is False
