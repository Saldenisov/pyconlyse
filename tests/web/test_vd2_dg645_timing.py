"""Exact operator calibration and software-only VD2 timing integration."""

from decimal import Decimal
import json
from types import SimpleNamespace

from flask import Flask, jsonify
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from vd2_dg645_timing import CONFIG_PATH, apply_timing, timing_for_range, verify_timing
from vd2_measurement_protocol import Vd2MeasurementProtocol


CALIBRATION = [
    ("1 ns", "2.2077265"), ("2 ns", "2.2077259"), ("5 ns", "2.207714"),
    ("10 ns", "2.207696"), ("20 ns", "2.207683"), ("50 ns", "2.20759"),
    ("100 ns", "2.20752"), ("200 ns", "2.20749"), ("500 ns", "2.20715"),
    ("1 us", "2.2065"), ("2 us", "2.2054"), ("5 us", "2.202"),
    ("10 us", "2.197"), ("20 us", "2.185"), ("50 us", "2.15"),
    ("100 us", "2.05"), ("200 us", "1.85"), ("500 us", "1.4"),
    ("1 ms", "0.85"), ("2 ms", "0"),
]


def test_output_roles_preserve_operator_mapping_without_guessing_gate_parameters():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["output_roles"] == {
        "AB": "pre-pulse", "CD": "main flashlamp pulse",
        "EF": "streak-camera trigger", "GH": "gate; operator parameters pending",
    }
    assert config["timing_calibration"]["gates"] == "not supplied; preserve existing settings"


def test_saved_baseline_evidence_is_distinct_from_waveform_calibration():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    evidence = config["memory_programming"]
    assert evidence["memory_readback_verified"] is True
    assert evidence["physical_waveform_verified"] is False
    assert config["verified_on_hardware"] is False
    assert evidence["automatic_slot_save"] is False
    assert evidence["calibrated_ranges_read_back"] == len(CALIBRATION)
    before = json.loads((CONFIG_PATH.parent / evidence["backup_file"]).read_text(encoding="utf-8"))
    verified = json.loads((CONFIG_PATH.parent / evidence["verified_snapshot_file"]).read_text(encoding="utf-8"))
    assert verified["DLAY?2"] == "0,+0.002041700000"
    assert verified["DLAY?6"] == "0,+0.002206500000"
    assert verified["BURM?"] == "0"
    assert {key for key in before if before[key] != verified[key]} == {"DLAY?1", "DLAY?2", "DLAY?6"}
    assert verified["*IDN?"] == evidence["instrument_idn"]


class Generator:
    def __init__(self):
        self.commands = []
        self.delays = {2: (0, Decimal("0.0020417")), 6: (0, Decimal("0.0022065")),
                       3: (2, Decimal("0.00005")), 7: (6, Decimal("0.00001"))}
        self.fail_command = None
        self.readback_override = None
        self.burst = "0"

    def set_timeout_millis(self, _value):
        pass

    def command_inout(self, command, value=None):
        self.commands.append((command, value))
        if value == self.fail_command:
            raise TimeoutError("accepted write may have timed out")
        if command == "scpi_write":
            channel, reference, seconds = value.removeprefix("DLAY ").split(",")
            self.delays[int(channel)] = (int(reference), Decimal(seconds))
        elif value == "*OPC?":
            return "1"
        elif value == "BURM?":
            return self.burst
        elif command == "scpi_query":
            if self.readback_override is not None:
                return self.readback_override
            reference, seconds = self.delays[int(value.split()[1])]
            return f"{reference},{seconds}"


@pytest.mark.parametrize("label,expected_e", CALIBRATION)
def test_every_supplied_value_uses_ms_without_rounding_and_preserves_gates(label, expected_e):
    profile = timing_for_range(label)
    assert profile.delay_a_ms == Decimal("2.0417")
    assert profile.delay_e_ms == Decimal(expected_e)
    generator = Generator()
    gates = {channel: generator.delays[channel] for channel in (3, 7)}
    apply_timing(generator, profile)
    assert generator.delays[2] == (0, Decimal("0.0020417"))
    assert generator.delays[6] == (0, Decimal(expected_e) / 1000)
    assert {channel: generator.delays[channel] for channel in (3, 7)} == gates
    assert [value for command, value in generator.commands if command == "scpi_write"] == list(profile.commands)
    assert not any("*SAV" in str(value) or "BURM" in str(value) for _, value in generator.commands)


@pytest.mark.parametrize("alias,label", [("1ns", "1 ns"), ("1 µs", "1 us"), ("1 μs", "1 us"),
                                         ("1000 ns", "1 us"), ("0.5 us", "500 ns"), ("2.0 ms", "2 ms")])
def test_only_exact_equivalent_time_ranges_are_normalized(alias, label):
    assert timing_for_range(alias) == timing_for_range(label)


@pytest.mark.parametrize("value", ["0.5 ns", "3 us", "1", "nan ms", "-1 us", "2 s", "1 us;*SAV 9"])
def test_missing_or_unsupported_calibration_is_rejected_without_interpolation(value):
    with pytest.raises(ValueError):
        timing_for_range(value)


@pytest.mark.parametrize("raw", ["2,0.0020417", "0,0.002041700010", "0,NaN", "0,Infinity", "", "0,0,0"])
def test_wrong_reference_precision_or_malformed_readback_is_not_verified(raw):
    generator = Generator()
    generator.readback_override = raw
    with pytest.raises(RuntimeError, match="timing unverified"):
        verify_timing(generator, timing_for_range("1 us"))
    assert all(command == "scpi_query" for command, _ in generator.commands)


@pytest.mark.parametrize("index", [0, 1])
def test_uncertain_timing_write_is_not_replayed_or_saved(index):
    generator = Generator()
    profile = timing_for_range("1 ns")
    generator.fail_command = profile.commands[index]
    with pytest.raises(TimeoutError):
        apply_timing(generator, profile)
    assert generator.commands == [("scpi_write", command) for command in profile.commands[:index + 1]]


@pytest.fixture
def timing_rig(monkeypatch):
    generator = Generator()
    events = []
    values = {"time_range": "1 us", "streak_mode": "Operate", "connected": True,
              "application_running": True, "remoteex_status": "idle"}
    range_override = {"value": None}

    class Streak:
        def set_timeout_millis(self, _value):
            pass

        def state(self):
            return "ON"

        def read_attribute(self, name):
            return SimpleNamespace(value=values.get(name))

        def write_attribute(self, name, value):
            events.append((name, value))
            values[name] = value

        def command_inout(self, command, arg=None):
            events.append((command, arg))
            if arg == "AcqStatus()":
                return "0,AcqStatus,idle"
            if arg == "DevParamGet(TD,Time Range)":
                return f"0,DevParamGet,{range_override['value'] or values['time_range']}"
            if arg == "DevParamGet(TD,Mode)":
                return f"0,DevParamGet,{values['streak_mode']}"

    streak = Streak()
    monkeypatch.setattr(api, "_proxy", lambda: streak)
    monkeypatch.setattr(api, "DeviceProxy", lambda device: generator if device == api.DG645_DEVICE else streak)
    monkeypatch.setattr(api, "_snapshot", lambda _: {"values": dict(values)})
    monkeypatch.setattr(api, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(api, "require_http_hardware", lambda **_: None)
    monkeypatch.delenv("PYCONLYSE_PRODUCTION", raising=False)
    monkeypatch.delenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", raising=False)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    return SimpleNamespace(client=app.test_client(), generator=generator, streak=streak,
                           values=values, events=events, range_override=range_override)


def test_time_range_change_applies_matching_a_e_after_native_readback(timing_rig):
    response = timing_rig.client.post("/api/pump-probe-vd2/parameter/time_range", json={"value": "1 µs"})
    assert response.status_code == 200
    assert ("time_range", "1 us") in timing_rig.events
    assert timing_rig.generator.delays[6] == (0, Decimal("0.0022065"))
    assert all(command not in {"StartApplication", "StartRemoteEx"} for command, _ in timing_rig.events)


def test_time_range_authorization_includes_exact_dg645_commands_before_any_write(timing_rig, monkeypatch):
    calls = []
    def deny(**kwargs):
        calls.append(kwargs)
        return jsonify({"success": False}), 428
    monkeypatch.setattr(api, "require_http_hardware", deny)
    response = timing_rig.client.post("/api/pump-probe-vd2/parameter/time_range", json={"value": "2 ms"})
    assert response.status_code == 428
    assert calls[0]["args"]["dg645_timing"]["commands"] == ["DLAY 2,0,0.0020417", "DLAY 6,0,0.000"]
    assert {"device": api.DG645_DEVICE, "command": "scpi_write"} in calls[0]["targets"]
    assert timing_rig.events == timing_rig.generator.commands == []


def test_uncalibrated_range_is_rejected_before_camera_or_generator_write(timing_rig):
    response = timing_rig.client.post("/api/pump-probe-vd2/parameter/time_range", json={"value": "0.5 ns"})
    assert response.status_code == 400
    assert timing_rig.events == timing_rig.generator.commands == []


def test_mismatched_camera_range_does_not_apply_wrong_dg645_profile(timing_rig):
    timing_rig.range_override["value"] = "2 us"
    response = timing_rig.client.post("/api/pump-probe-vd2/parameter/time_range", json={"value": "1 ns"})
    assert response.status_code == 503
    assert "readback mismatch" in response.get_json()["error"]
    assert timing_rig.generator.commands == []


def test_acquisition_is_blocked_after_partial_failed_timing_change(timing_rig):
    timing_rig.generator.fail_command = timing_for_range("1 ns").commands[1]
    response = timing_rig.client.post("/api/pump-probe-vd2/parameter/time_range", json={"value": "1 ns"})
    assert response.status_code == 503
    timing_rig.events.clear()
    timing_rig.generator.commands.clear()
    response = timing_rig.client.post("/api/pump-probe-vd2/command/AcquireSingle")
    assert response.status_code == 503
    assert ("AcquireSingle", None) not in timing_rig.events
    assert all(command == "scpi_query" for command, _ in timing_rig.generator.commands)


def test_focus_live_does_not_require_sweep_calibration_or_touch_generator(timing_rig):
    timing_rig.values.update(streak_mode="Focus", time_range="0.5 ns")
    response = timing_rig.client.post("/api/pump-probe-vd2/command/StartLive")
    assert response.status_code == 200
    assert ("StartLive", None) in timing_rig.events
    assert timing_rig.generator.commands == []


@pytest.mark.parametrize("burst", ["1", "NaN"])
def test_operate_acquisition_is_blocked_if_burst_is_enabled_or_unknown(timing_rig, burst):
    timing_rig.generator.burst = burst
    response = timing_rig.client.post("/api/pump-probe-vd2/command/AcquireSingle")
    assert response.status_code == 503
    assert ("AcquireSingle", None) not in timing_rig.events


def test_timing_change_while_acquiring_is_rejected_before_any_write(timing_rig):
    timing_rig.values["remoteex_status"] = "busy"
    response = timing_rig.client.post("/api/pump-probe-vd2/parameter/time_range", json={"value": "2 us"})
    assert response.status_code == 503
    assert timing_rig.events == timing_rig.generator.commands == []


def test_startup_applies_calibration_after_application_recall_can_overwrite_delays(timing_rig, monkeypatch):
    original = timing_rig.streak.command_inout
    def start_application(command, arg=None):
        result = original(command, arg)
        if command == "StartApplication":
            timing_rig.generator.delays.update({2: (0, Decimal("0")), 6: (0, Decimal("0"))})
            timing_rig.values.update(time_range="1 us", streak_mode="Operate")
        return result
    monkeypatch.setattr(timing_rig.streak, "command_inout", start_application)
    monkeypatch.setattr(api, "_prepare_kymera_for_vd2", lambda *_: None)
    steps = []
    api._start_vd2_optics(timing_rig.streak, steps)
    assert timing_rig.generator.delays[2] == (0, Decimal("0.0020417"))
    assert timing_rig.generator.delays[6] == (0, Decimal("0.0022065"))
    assert any(step["step"] == "DG645 calibrated timing" for step in steps)


def test_startup_does_not_report_ready_with_unverified_timing(timing_rig, monkeypatch):
    monkeypatch.setattr(api, "_prepare_kymera_for_vd2", lambda *_: None)
    timing_rig.generator.fail_command = timing_for_range("1 us").commands[1]
    steps = []
    with pytest.raises(RuntimeError, match="timing unverified"):
        api._start_vd2_optics(timing_rig.streak, steps)
    assert not any(step["step"] == "VD2 optical profile" for step in steps)
    assert steps[-1]["status"] == "failed"


def test_his_protocol_worker_cannot_start_with_wrong_calibrated_timing(timing_rig, monkeypatch):
    protocol = Vd2MeasurementProtocol(lambda: timing_rig.streak)
    monkeypatch.setattr(protocol, "start", lambda **_: pytest.fail("No worker with unverified timing"))
    monkeypatch.setattr(api, "_measurement_protocol", protocol)
    timing_rig.generator.delays[6] = (0, Decimal("0.123"))
    response = timing_rig.client.post("/api/pump-probe-vd2/protocol/start", json={
        "phase": "BASE", "frames_per_his": 2, "output_root": "C:/test-data", "run_name": "calibration-test",
    })
    assert response.status_code == 503
    assert "timing unverified" in response.get_json()["error"]
    assert all(command == "scpi_query" for command, _ in timing_rig.generator.commands)
