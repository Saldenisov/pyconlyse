from DeviceServers.control.health_monitor.DS_HealthMonitor import (
    DS_HealthMonitor,
    is_critical_state,
    normalized_device_names,
    state_name,
)


def test_normalized_device_names_excludes_duplicates_and_dserver():
    assert normalized_device_names(
        [" A/B/C ", "a/b/c", "dserver/Server/one", "X/Y/Z"]
    ) == ["A/B/C", "X/Y/Z"]


def test_state_helpers_accept_enum_style_and_strings():
    class State:
        name = "fault"

    assert state_name(State()) == "FAULT"
    assert state_name("DevState.ON") == "ON"
    assert is_critical_state(State())
    assert not is_critical_state("ON")


def test_event_type_detects_only_meaningful_transitions():
    baseline = {
        "state": "ON",
        "process_started_at_utc": "2026-01-01T00:00:00+00:00",
        "last_error_at_utc": "",
        "error_count": 0,
    }
    assert DS_HealthMonitor._event_type(baseline, dict(baseline)) is None

    state_changed = dict(baseline, state="FAULT")
    assert DS_HealthMonitor._event_type(baseline, state_changed) == "state"

    unreachable = dict(baseline, state="UNREACHABLE")
    assert DS_HealthMonitor._event_type(baseline, unreachable) == "reachability"

    restarted = dict(
        baseline, process_started_at_utc="2026-01-02T00:00:00+00:00"
    )
    assert DS_HealthMonitor._event_type(baseline, restarted) == "process_restart"

    errored = dict(
        baseline,
        last_error_at_utc="2026-01-01T00:01:00+00:00",
        error_count=1,
    )
    assert DS_HealthMonitor._event_type(baseline, errored) == "device_error"
