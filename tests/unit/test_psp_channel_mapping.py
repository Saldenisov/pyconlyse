import importlib
import sys
import threading
import types
from pathlib import Path


def _install_tango_stub():
    if "tango" in sys.modules and "tango.server" in sys.modules:
        return

    tango = types.ModuleType("tango")

    class AttrWriteType:
        READ = 0
        READ_WRITE = 1

    class DevState:
        ON = "ON"
        OFF = "OFF"
        FAULT = "FAULT"
        STANDBY = "STANDBY"
        INIT = "INIT"
        RUNNING = "RUNNING"
        MOVING = "MOVING"

    class DispLevel:
        OPERATOR = 0

    tango.AttrWriteType = AttrWriteType
    tango.DevState = DevState
    tango.DispLevel = DispLevel

    server = types.ModuleType("tango.server")

    def _decorator(*_args, **_kwargs):
        def wrap(func):
            return func

        return wrap

    class Device:
        pass

    def device_property(*_args, **_kwargs):
        return None

    server.Device = Device
    server.attribute = _decorator
    server.command = _decorator
    server.pipe = _decorator
    server.device_property = device_property

    sys.modules["tango"] = tango
    sys.modules["tango.server"] = server


_install_tango_stub()

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_supervision_channel_mapper_handles_mojibake():
    from DeviceServers.control.daqmx.supervision_channel_mapper import SupervisionChannelMapper

    mapper = SupervisionChannelMapper(ROOT / "DeviceServers" / "control" / "daqmx")

    normalized = mapper.resolve("00 OUT00 b05 C10 DÃ©lais")
    assert normalized["canonical_name"] == "elyse/sync/NI6071E/delay"
    assert normalized["match_type"] == "normalized"

    exact = mapper.resolve("00 OUT00 b01 Cmd alimentation HT")
    assert exact["canonical_name"] == "elyse/HT/voltage/set_value"
    assert exact["match_type"] == "exact"

    already = mapper.resolve("elyse/vacuum/HF/measurement")
    assert already["canonical_name"] == "elyse/vacuum/HF/measurement"
    assert already["match_type"] == "already_canonical"


def test_ds_psp_build_message_uses_canonical_channel():
    module = importlib.import_module("DeviceServers.control.psp.DS_PSP")
    DS_PSP = module.DS_PSP
    from DeviceServers.control.daqmx.supervision_channel_mapper import SupervisionChannelMapper

    device = object.__new__(DS_PSP)
    device._messages_received = 7
    device._channel_mapper = SupervisionChannelMapper(ROOT / "DeviceServers" / "control" / "daqmx")
    device._lock = threading.RLock()

    message = device._build_message("00 OUT00 b05 C10 DÃ©lais:12.5:100.0", 101.0)

    assert message["raw_channel"] == "00 OUT00 b05 C10 DÃ©lais"
    assert message["channel"] == "elyse/sync/NI6071E/delay"
    assert message["mapping_match_type"] == "normalized"
    assert message["value"] == 12.5
    assert message["source_ts"] == 100.0
