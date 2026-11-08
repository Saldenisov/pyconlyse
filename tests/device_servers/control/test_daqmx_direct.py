import configparser
from pathlib import Path
from types import SimpleNamespace

from tests.device_servers.base._driver_stubs import daqmx_imports

with daqmx_imports():
    from DeviceServers.control.daqmx import DS_DAQmx as daqmx_module


DAQMX_DIR = Path(__file__).resolve().parents[3] / "DeviceServers" / "control" / "daqmx"


def test_transcon_channel_map_matches_physical_card_contract():
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(DAQMX_DIR / "daqmx_transcon.ini", encoding="utf-8")

    assert parser.sections() == [
        "Laser_SC Shutter",
        "Motor",
        "Accelerator Shutter",
        "Relay Key Heater",
        "Faraday Cup Status",
        "Faraday Cup",
        "Pump Start_Stop",
        "Laser_Pump Shutter",
        "Power Status",
        "Pump Speed",
        "ELYSE Pulse Counter",
    ]
    assert parser["Power Status"]["unit"] == "uA"
    assert parser["Power Status"].getfloat("multiplier") == 1_000_000
    assert parser["ELYSE Pulse Counter"]["counter"] == "TRANCON-DAQ/ctr0"
    assert {parser[name]["type"] for name in parser.sections()} <= daqmx_module.SUPPORTED_TYPES


def test_digital_output_read_uses_command_cache_without_reconfiguring_as_input(monkeypatch):
    task_calls = []
    monkeypatch.setattr(daqmx_module.nidaqmx, "Task", lambda: task_calls.append(True))
    output = daqmx_module.DaqmxChannel(
        name="Laser_SC Shutter",
        channel="TRANCON-DAQ/port0/line0",
        kind="DigitalOut",
    )
    server = SimpleNamespace(_digital_output_values={output.name: None})

    assert daqmx_module.DS_DAQmx._read_digital(server, output) == -1
    server._digital_output_values[output.name] = 1
    assert daqmx_module.DS_DAQmx._read_digital(server, output) == 1
    assert task_calls == []


def test_alarm_limits_apply_after_engineering_scaling():
    channel = daqmx_module.DaqmxChannel(
        name="Power Status",
        channel="TRANCON-DAQ/ai0",
        kind="AIcurrent",
        multiplier=1_000_000,
        unit="uA",
        limit_alarm_min=100,
        limit_alarm_max=1000,
    )

    assert daqmx_module.DS_DAQmx._is_alarm(channel, 99.9) is True
    assert daqmx_module.DS_DAQmx._is_alarm(channel, 500) is False
    assert daqmx_module.DS_DAQmx._is_alarm(channel, 1000.1) is True
