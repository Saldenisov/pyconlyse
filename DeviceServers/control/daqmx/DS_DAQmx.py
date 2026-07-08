#!/usr/bin/env python
"""
Direct NI-DAQmx Tango device server for a locally installed DAQ card.

This server is intentionally separate from DS_DAQmx_ZMQ, which remains the
remote-card reader path.
"""

from __future__ import annotations

import configparser
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Union

_PYCONLYSE_ROOT = Path(__file__).resolve().parents[3]
if str(_PYCONLYSE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYCONLYSE_ROOT))

import nidaqmx
from nidaqmx.constants import Edge, TerminalConfiguration
from nidaqmx.system import Device as NIDAQmxDevice
from nidaqmx.system import System
from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, command, device_property

try:
    from DeviceServers.base.DS_general import DS_General
except ModuleNotFoundError:
    from DeviceServers.base.general import DS_General


SUPPORTED_TYPES = {
    "DigitalIn",
    "DigitalOut",
    "AIcurrent",
    "AIVoltage",
    "DigitalCounter",
}


@dataclass
class DaqmxChannel:
    name: str
    channel: str
    kind: str
    counter: str = ""
    multiplier: float = 1.0
    alarm_path: str = ""
    limit_alarm_min: Optional[float] = None
    limit_alarm_max: Optional[float] = None

    @property
    def is_digital(self) -> bool:
        return self.kind in {"DigitalIn", "DigitalOut"}

    @property
    def is_analog(self) -> bool:
        return self.kind in {"AIcurrent", "AIVoltage"}

    @property
    def is_counter(self) -> bool:
        return self.kind == "DigitalCounter"


class DS_DAQmx(DS_General):
    """Device Server (Tango) for direct control of a local NI-DAQmx card."""

    RULES = {
        "read_channel": [DevState.ON, DevState.STANDBY],
        "write_channel": [DevState.ON, DevState.STANDBY],
        "write_digital_output": [DevState.ON, DevState.STANDBY],
        "read_digital_input": [DevState.ON, DevState.STANDBY],
        "read_analog": [DevState.ON, DevState.STANDBY],
        "read_counter": [DevState.ON, DevState.STANDBY],
        "reset_counter": [DevState.ON, DevState.STANDBY],
        **DS_General.RULES,
    }

    _version_ = "0.1"
    _model_ = "NI-DAQmx direct local controller"
    polling = 500

    daq_device_name = device_property(dtype=str, default_value="TRANCON-DAQ")
    channel_config_path = device_property(dtype=str, default_value="")
    terminal_config = device_property(dtype=str, default_value="RSE")
    analog_min = device_property(dtype=float, default_value=-10.0)
    analog_max = device_property(dtype=float, default_value=10.0)
    digital_read_timeout_s = device_property(dtype=float, default_value=1.0)
    analog_read_timeout_s = device_property(dtype=float, default_value=2.0)
    counter_read_timeout_s = device_property(dtype=float, default_value=1.0)
    start_on_init = device_property(dtype=int, default_value=0)

    def init_device(self):
        self._lock = RLock()
        self._channels: List[DaqmxChannel] = []
        self._channels_by_name: Dict[str, DaqmxChannel] = {}
        self._counter_tasks: Dict[str, nidaqmx.Task] = {}
        self._states: List[int] = []
        self._analog_values: List[float] = []
        self._counter_values: List[int] = []
        self._ai_current_voltage_fallback = set()
        self._last_snapshot_json = "{}"
        self._last_read_json = "{}"
        self._device_info_json = "{}"
        super().init_device()
        self.register_variables_for_archive()
        if bool(int(self.start_on_init or 0)) and self._device_id_internal != -1:
            self.turn_on()

    def _default_config_path(self) -> Path:
        return Path(__file__).with_name("daqmx_transcon.ini")

    def _config_path(self) -> Path:
        if str(self.channel_config_path or "").strip():
            return Path(str(self.channel_config_path)).expanduser()
        return self._default_config_path()

    def _load_channels(self) -> None:
        parser = configparser.ConfigParser()
        parser.optionxform = str
        path = self._config_path()
        if not path.exists():
            raise FileNotFoundError(f"DAQmx channel config not found: {path}")
        parser.read(path, encoding="utf-8")

        channels: List[DaqmxChannel] = []
        for section in parser.sections():
            kind = parser.get(section, "type", fallback="").strip()
            if kind not in SUPPORTED_TYPES:
                raise ValueError(
                    f"Unsupported DAQmx channel type {kind!r} in [{section}]. "
                    f"Allowed: {sorted(SUPPORTED_TYPES)}"
                )
            channel = parser.get(section, "channel", fallback="").strip()
            if not channel:
                raise ValueError(f"Missing channel in [{section}]")
            counter = parser.get(section, "counter", fallback="").strip()
            if kind == "DigitalCounter" and not counter:
                raise ValueError(f"Missing counter in DigitalCounter [{section}]")

            limit_min = self._optional_float(
                parser.get(section, "limit_alarm_min", fallback="")
            )
            limit_max = self._optional_float(
                parser.get(section, "limit_alarm_max", fallback="")
            )
            channels.append(
                DaqmxChannel(
                    name=section,
                    channel=channel,
                    kind=kind,
                    counter=counter,
                    multiplier=parser.getfloat(section, "multiplier", fallback=1.0),
                    alarm_path=parser.get(section, "alarm_path", fallback=""),
                    limit_alarm_min=limit_min,
                    limit_alarm_max=limit_max,
                )
            )

        if not channels:
            raise ValueError(f"No DAQmx channels configured in {path}")

        self._channels = channels
        self._channels_by_name = {channel.name: channel for channel in channels}
        self._states = [-1 for channel in channels if channel.is_digital]
        self._analog_values = [0.0 for channel in channels if channel.is_analog]
        self._counter_values = [0 for channel in channels if channel.is_counter]

    @staticmethod
    def _optional_float(value: str) -> Optional[float]:
        value = str(value).strip()
        if not value:
            return None
        return float(value)

    def _get_terminal_config(self) -> TerminalConfiguration:
        name = str(self.terminal_config or "RSE").strip().upper()
        configs = {
            "RSE": TerminalConfiguration.RSE,
            "NRSE": TerminalConfiguration.NRSE,
            "DIFF": TerminalConfiguration.DIFF,
            "DIFFERENTIAL": TerminalConfiguration.DIFF,
        }
        pseudo_diff = getattr(TerminalConfiguration, "PSEUDODIFFERENTIAL", None)
        if pseudo_diff is not None:
            configs["PSEUDODIFFERENTIAL"] = pseudo_diff
        return configs.get(name, TerminalConfiguration.RSE)

    def _device(self) -> NIDAQmxDevice:
        return NIDAQmxDevice(str(self.daq_device_name))

    def find_device(self):
        self._device_id_internal, self._uri = -1, b""
        try:
            self._load_channels()
            system = System.local()
            for device in system.devices:
                if device.name == str(self.daq_device_name):
                    self._device_info_json = json.dumps(
                        {
                            "name": device.name,
                            "product_type": device.product_type,
                            "product_num": device.product_num,
                            "serial_num": device.serial_num,
                            "ai_channels": [c.name for c in device.ai_physical_chans],
                            "ao_channels": [c.name for c in device.ao_physical_chans],
                            "di_lines": [c.name for c in device.di_lines],
                            "do_lines": [c.name for c in device.do_lines],
                            "counters": [c.name for c in device.ci_physical_chans],
                            "config_path": str(self._config_path()),
                        },
                        indent=2,
                    )
                    self._device_id_internal = int(device.serial_num)
                    self._uri = device.name.encode("utf-8")
                    return
            self._device_info_json = json.dumps(
                {
                    "error": f"DAQmx device {self.daq_device_name!r} not found",
                    "available_devices": [device.name for device in system.devices],
                },
                indent=2,
            )
        except Exception as exc:
            self._device_info_json = json.dumps({"error": str(exc)}, indent=2)
            self.error(f"DAQmx discovery failed: {exc}")

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.find_device()
        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return self._device_info_json

        with self._lock:
            self._close_counter_tasks()
            for channel in self._channels:
                if channel.is_counter:
                    self._start_counter_task(channel)
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        with self._lock:
            self._close_counter_tasks()
        self.set_state(DevState.OFF)
        return 0

    def get_controller_status_local(self) -> Union[int, str]:
        try:
            _ = self._device().product_type
            if self.get_state() != DevState.ON:
                self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.set_state(DevState.FAULT)
            return f"DAQmx status check failed: {exc}"

    def _start_counter_task(self, channel: DaqmxChannel) -> None:
        task = nidaqmx.Task(new_task_name=f"{channel.name}_counter")
        counter_channel = task.ci_channels.add_ci_count_edges_chan(
            channel.counter,
            edge=Edge.RISING,
            initial_count=0,
        )
        counter_channel.ci_count_edges_term = channel.channel
        task.start()
        self._counter_tasks[channel.name] = task

    def _close_counter_tasks(self) -> None:
        for task in self._counter_tasks.values():
            try:
                task.stop()
            except Exception:
                pass
            try:
                task.close()
            except Exception:
                pass
        self._counter_tasks = {}

    def _channel(self, name: str) -> DaqmxChannel:
        try:
            return self._channels_by_name[str(name)]
        except KeyError as exc:
            raise ValueError(
                f"Unknown DAQmx channel {name!r}. Available: {list(self._channels_by_name)}"
            ) from exc

    def _read_digital(self, channel: DaqmxChannel) -> int:
        with nidaqmx.Task() as task:
            task.di_channels.add_di_chan(channel.channel)
            value = task.read(timeout=float(self.digital_read_timeout_s))
        return int(bool(value))

    def _write_digital(self, channel: DaqmxChannel, value: Union[str, int, bool]) -> int:
        if channel.kind != "DigitalOut":
            raise ValueError(f"{channel.name} is {channel.kind}, not DigitalOut")
        bool_value = self._coerce_bool(value)
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(channel.channel)
            task.write(bool_value, timeout=float(self.digital_read_timeout_s))
        return int(bool_value)

    @staticmethod
    def _coerce_bool(value: Union[str, int, bool]) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "on", "high"}

    def _read_analog_raw(self, channel: DaqmxChannel) -> float:
        if channel.kind == "AIcurrent" and channel.name not in self._ai_current_voltage_fallback:
            try:
                with nidaqmx.Task() as task:
                    task.ai_channels.add_ai_current_chan(
                        channel.channel,
                        min_val=float(self.analog_min),
                        max_val=float(self.analog_max),
                    )
                    return float(task.read(timeout=float(self.analog_read_timeout_s)))
            except Exception as exc:
                self.warn(
                    f"{channel.name}: AIcurrent task failed ({exc}); "
                    "falling back to voltage input.",
                    True,
                )
                self._ai_current_voltage_fallback.add(channel.name)

        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(
                channel.channel,
                terminal_config=self._get_terminal_config(),
                min_val=float(self.analog_min),
                max_val=float(self.analog_max),
            )
            return float(task.read(timeout=float(self.analog_read_timeout_s)))

    def _read_analog(self, channel: DaqmxChannel) -> float:
        return self._read_analog_raw(channel) * float(channel.multiplier)

    def _read_counter(self, channel: DaqmxChannel) -> int:
        if channel.name not in self._counter_tasks:
            self._start_counter_task(channel)
        return int(
            self._counter_tasks[channel.name].read(
                timeout=float(self.counter_read_timeout_s)
            )
        )

    def _read_channel_value(self, channel: DaqmxChannel):
        if channel.is_digital:
            return self._read_digital(channel)
        if channel.is_analog:
            return self._read_analog(channel)
        if channel.is_counter:
            return self._read_counter(channel)
        raise ValueError(f"Unsupported channel type: {channel.kind}")

    def _channel_payload(self, channel: DaqmxChannel) -> dict:
        raw_value = None
        if channel.is_analog:
            raw_value = self._read_analog_raw(channel)
            value = raw_value * float(channel.multiplier)
        else:
            value = self._read_channel_value(channel)

        payload = asdict(channel)
        payload["value"] = value
        payload["raw_value"] = raw_value
        payload["alarm"] = self._is_alarm(channel, value)
        return payload

    @staticmethod
    def _is_alarm(channel: DaqmxChannel, value) -> bool:
        try:
            numeric = float(value)
        except Exception:
            return False
        if channel.limit_alarm_min is not None and numeric < channel.limit_alarm_min:
            return True
        if channel.limit_alarm_max is not None and numeric > channel.limit_alarm_max:
            return True
        return False

    def _refresh_cached_values(self) -> None:
        states = []
        analog_values = []
        counter_values = []
        snapshot = {}
        for channel in self._channels:
            try:
                payload = self._channel_payload(channel)
                snapshot[channel.name] = payload
                if channel.is_digital:
                    states.append(int(payload["value"]))
                elif channel.is_analog:
                    analog_values.append(float(payload["value"]))
                elif channel.is_counter:
                    counter_values.append(int(payload["value"]))
            except Exception as exc:
                snapshot[channel.name] = {"error": str(exc), **asdict(channel)}
                if channel.is_digital:
                    states.append(-1)
                elif channel.is_analog:
                    analog_values.append(float("nan"))
                elif channel.is_counter:
                    counter_values.append(-1)
        self._states = states
        self._analog_values = analog_values
        self._counter_values = counter_values
        self._last_snapshot_json = json.dumps(snapshot, indent=2)

    @attribute(
        label="DAQmx channel names",
        dtype=[str],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def names(self):
        return [channel.name for channel in self._channels]

    @attribute(
        label="DAQmx physical channels",
        dtype=[str],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def channels(self):
        return [channel.channel for channel in self._channels]

    @attribute(
        label="DAQmx channel types",
        dtype=[str],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def channel_types(self):
        return [channel.kind for channel in self._channels]

    @attribute(
        label="Digital states",
        dtype=[int],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling,
    )
    def states(self):
        self._refresh_cached_values()
        return self._states

    @attribute(
        label="Analog values",
        dtype=[float],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling,
    )
    def analog_values(self):
        self._refresh_cached_values()
        return self._analog_values

    @attribute(
        label="Counter values",
        dtype=[int],
        max_dim_x=64,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=polling,
    )
    def counter_values(self):
        self._refresh_cached_values()
        return self._counter_values

    @attribute(label="Device info JSON", dtype=str, access=AttrWriteType.READ)
    def device_info_json(self):
        return self._device_info_json

    @attribute(label="Snapshot JSON", dtype=str, access=AttrWriteType.READ)
    def snapshot_json(self):
        self._refresh_cached_values()
        return self._last_snapshot_json

    @command(dtype_out=str)
    def list_channels_json(self) -> str:
        return json.dumps([asdict(channel) for channel in self._channels], indent=2)

    @command(dtype_out=str)
    def discover_hardware_json(self) -> str:
        system = System.local()
        return json.dumps(
            [
                {
                    "name": device.name,
                    "product_type": device.product_type,
                    "serial_num": device.serial_num,
                    "ai_channels": [c.name for c in device.ai_physical_chans],
                    "di_lines": [c.name for c in device.di_lines],
                    "do_lines": [c.name for c in device.do_lines],
                    "counters": [c.name for c in device.ci_physical_chans],
                }
                for device in system.devices
            ],
            indent=2,
        )

    @command(dtype_in=str, dtype_out=str)
    def read_channel(self, name: str) -> str:
        channel = self._channel(name)
        payload = self._channel_payload(channel)
        self._last_read_json = json.dumps(payload, indent=2)
        return self._last_read_json

    @command(
        dtype_in=[str],
        dtype_out=str,
        doc_in="[channel name, value]. Value accepts 0/1, true/false, on/off.",
    )
    def write_channel(self, name_value: List[str]) -> str:
        if len(name_value) < 2:
            return "ERROR: pass [channel name, value]"
        channel = self._channel(name_value[0])
        value = self._write_digital(channel, name_value[1])
        return json.dumps({"name": channel.name, "channel": channel.channel, "value": value})

    @command(
        dtype_in=[str],
        dtype_out=str,
        doc_in="[DigitalOut channel name, value]. Value accepts 0/1, true/false, on/off.",
    )
    def write_digital_output(self, name_value: List[str]) -> str:
        return self.write_channel(name_value)

    @command(dtype_in=str, dtype_out=int)
    def read_digital_input(self, name: str) -> int:
        channel = self._channel(name)
        if not channel.is_digital:
            raise ValueError(f"{name} is {channel.kind}, not DigitalIn/DigitalOut")
        return self._read_digital(channel)

    @command(dtype_in=str, dtype_out=float)
    def read_analog(self, name: str) -> float:
        channel = self._channel(name)
        if not channel.is_analog:
            raise ValueError(f"{name} is {channel.kind}, not AIcurrent/AIVoltage")
        return self._read_analog(channel)

    @command(dtype_in=str, dtype_out=int)
    def read_counter(self, name: str) -> int:
        channel = self._channel(name)
        if not channel.is_counter:
            raise ValueError(f"{name} is {channel.kind}, not DigitalCounter")
        return self._read_counter(channel)

    @command(dtype_in=str, dtype_out=str)
    def reset_counter(self, name: str) -> str:
        channel = self._channel(name)
        if not channel.is_counter:
            return f"ERROR: {name} is {channel.kind}, not DigitalCounter"
        with self._lock:
            task = self._counter_tasks.pop(channel.name, None)
            if task is not None:
                try:
                    task.stop()
                except Exception:
                    pass
                task.close()
            self._start_counter_task(channel)
        return f"OK: reset {channel.name}"

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        for channel in self._channels:
            if channel.kind == "DigitalIn":
                self.archive_state[channel.name] = (
                    lambda ch=channel: self._read_digital(ch),
                    "uint8",
                )
            elif channel.is_analog:
                self.archive_state[channel.name] = (
                    lambda ch=channel: self._read_analog(ch),
                    "float32",
                )
            elif channel.is_counter:
                self.archive_state[channel.name] = (
                    lambda ch=channel: self._read_counter(ch),
                    "uintc",
                )


if __name__ == "__main__":
    DS_DAQmx.run_server()
