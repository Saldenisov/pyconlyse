"""One standard telemetry device; optional named commands to the Python owner.

LabVIEW remains receive-only. Python mode must be selected explicitly and
exclusively; neither telemetry nor commands ever fall back to another source.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tango import DevState
from tango.server import Device, attribute, command, device_property, run
from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkServer, TelemetrySinkStore
from legacy.xp_acq_agent.elyse_agent.cooling_safety import CoolingSafety


class DS_AcqTelemetry(Device):
    listen_host = device_property(dtype=str, default_value="10.20.30.202")
    listen_port = device_property(dtype=int, default_value=8767)
    key_file = device_property(dtype=str, default_value="")
    permitted_xp_host = device_property(dtype=str, default_value="10.20.30.10")
    producer_kind_filter = device_property(dtype=str, default_value="")
    cooling_journal_file = device_property(dtype=str, default_value="")
    xp_control_port = device_property(dtype=int, default_value=8772)
    command_key_file = device_property(dtype=str, default_value="")
    commands_enabled = device_property(dtype=bool, default_value=False)
    archive_config_file = device_property(dtype=str, default_value="")

    def init_device(self):
        self._closing = True
        if any(getattr(self, name, None) is not None for name in ('_server', '_bridge', '_archive')):
            self.delete_device()
            if any(getattr(self, name, None) is not None for name in ('_server', '_bridge', '_archive')):
                raise RuntimeError("Previous telemetry owner did not exit; replacement refused")
        self._server = self._store = self._thread = None
        self._bridge = self._client = None
        self._archive = None
        super().init_device()
        self._python_source = self.producer_kind_filter in ("python_acquisition", "unified_acquisition")
        if not self.key_file:
            self.set_state(DevState.FAULT)
            self.set_status("Not listening: configure key_file; RAM-only telemetry, no database.")
            return
        try:
            if self.listen_host not in ("10.20.30.202", "127.0.0.1"):
                raise ValueError("explicit Everest address required; wildcard disabled")
            key = Path(self.key_file).read_bytes().strip()
            if self.commands_enabled and not self._python_source:
                raise ValueError("Commands require exclusive Python telemetry source")
            journal_path = self.cooling_journal_file or (
                str(ROOT / "logs" / "elyse_cooling_alarms.sqlite3") if self.listen_host != "127.0.0.1" else "")
            cooling = (CoolingSafety.with_journal(journal_path, "labview_receiver")
                       if journal_path else CoolingSafety())
            if self.archive_config_file:
                from DeviceServers.control.elyse_acq.telemetry_archive import DurableArchive
                self._archive = DurableArchive(self.archive_config_file)
                self._archive.start()
            self._store = TelemetrySinkStore(key, permitted_producer_kind=self.producer_kind_filter or None,
                                             cooling=cooling, archive=self._archive)
            self._server = TelemetrySinkServer((self.listen_host, self.listen_port), self._store,
                                              permitted_peers=(self.permitted_xp_host,))
            self._thread = threading.Thread(target=self._server.serve_forever,
                                            kwargs={"poll_interval": 0.1}, daemon=True)
            self._thread.start()
            if self._python_source:
                from DeviceServers.control.elyse_acq.control_client import ControlClient, ControlBridge
                command_key = Path(self.command_key_file).read_bytes().strip() if self.commands_enabled else None
                self._client = ControlClient(key, command_key, enabled=bool(self.commands_enabled),
                                             port=int(self.xp_control_port))
                self._bridge = ControlBridge(self._client)
                self._bridge.start()
            self._closing = False
            self.set_state(DevState.ON)
            self.set_status("Standard 27-bank telemetry; exclusive source={0}; named commands={1}. "
                            "No NI/PSP tasks on Everest; no automatic command retries.".format(
                                self.producer_kind_filter or "legacy", bool(self.commands_enabled)))
        except Exception as error:
            self.delete_device()
            self.set_state(DevState.FAULT)
            self.set_status(str(error))

    @attribute(dtype=str)
    def telemetry_json(self):
        if self._store is None:
            return json.dumps(dict(available=False, hardware_writes=False))
        snapshot = self._store.snapshot()
        if getattr(self, "_python_source", False) and snapshot["source"] == "python_daqmx_acquisition":
            view = self._control_view()
            runtime = view.get("runtime") or {}
            age = view.get("bridge_age_seconds")
            matching_boot = bool(snapshot["publications"] and all(
                packet.get("session_id") == runtime.get("session_id")
                for packet in snapshot["publications"].values()))
            snapshot["cooling_safety"] = (runtime.get("cooling_safety") if matching_boot
                and not view.get("bridge_error") and type(age) in (int, float) and 0 <= age < 2 else None)
        return json.dumps(snapshot, allow_nan=False)

    @attribute(dtype=int)
    def received_messages(self):
        return 0 if self._store is None else self._store.snapshot()["received_this_process"]

    @attribute(dtype=str)
    def archive_status_json(self):
        archive = getattr(self, '_archive', None)
        return json.dumps(archive.status() if archive else dict(enabled=False), allow_nan=False)

    @command(dtype_in=str, dtype_out=str)
    def ReadHistory(self, request):
        archive = getattr(self, '_archive', None)
        if archive is None:
            raise RuntimeError('ARCHIVE_NOT_CONFIGURED')
        if len(request.encode('utf-8')) > 4096:
            raise ValueError('History request too large')
        return json.dumps(archive.store.read_history(json.loads(request)), allow_nan=False)

    @command(dtype_out=str)
    def ArchiveSummary(self):
        archive = getattr(self, '_archive', None)
        if archive is None:
            raise RuntimeError('ARCHIVE_NOT_CONFIGURED')
        return json.dumps(archive.store.summary(), allow_nan=False)

    def _control_view(self):
        bridge = getattr(self, "_bridge", None)
        if bridge is None:
            return dict(source="labview_receive_only", quality="UNAVAILABLE", runtime=None,
                        commands_enabled=False, bridge_error="Python command source not selected")
        view = bridge.snapshot()
        runtime = view.get("runtime") or {}
        packets = self._store.snapshot()["publications"] if self._store is not None else {}
        from legacy.xp_acq_control.elyse_agent.native_telemetry import INPUTS
        same_source = all(
            name in packets and packets[name].get("producer_kind") == "python_acquisition"
            and packets[name].get("session_id") == runtime.get("session_id")
            and packets[name].get("stale") is False
            and packets[name].get("error", {}).get("status") is False
            for name in INPUTS)
        view["telemetry_source_current"] = bool(same_source)
        source_mode = runtime.get("telemetry_delivery", {}).get("source_mode")
        if source_mode in ("LABVIEW_BRIDGE", "TRANSITION_OR_FAULT"):
            view["commands_enabled"] = False
        from legacy.xp_acq_control.elyse_agent.runtime_identity import valid_hex
        age = view.get("bridge_age_seconds")
        metadata_current = (valid_hex(runtime.get("session_id"), 32) and not view.get("bridge_error")
                            and type(age) in (int, float) and 0 <= age < 2)
        view["commands_enabled"] = bool(view.get("commands_enabled") and metadata_current and not self._closing)
        if not same_source:
            for name, capability in runtime.get("control", {}).get("capabilities", {}).items():
                if not name.endswith(".stop"):
                    capability.update(enabled=False, reason="STANDARD_TELEMETRY_NOT_CURRENT")
        return view

    @attribute(dtype=str)
    def runtime_json(self):
        return json.dumps(self._control_view(), allow_nan=False)

    @command(dtype_in=str, dtype_out=str)
    def ExecuteCommand(self, request):
        if (not getattr(self, "_python_source", False) or not self.commands_enabled
                or getattr(self, "_closing", True) or self._client is None
                or self._control_view().get("commands_enabled") is not True):
            raise RuntimeError("TANGO_COMMANDS_DISABLED_OR_TELEMETRY_SOURCE_NOT_CURRENT")
        from legacy.xp_acq_control.elyse_agent.acquisition_remote import strict_json, validate_request
        intent = validate_request(strict_json(request.encode("utf-8")))
        if not intent["operation"].endswith(".stop") and not self._control_view()["telemetry_source_current"]:
            raise RuntimeError("TANGO_COMMANDS_DISABLED_OR_TELEMETRY_SOURCE_NOT_CURRENT")
        # An explicitly requested stop is not hidden by a stale measurement
        # channel. XP still authenticates/fences the current boot and gates it.
        return json.dumps(self._client.submit(intent), allow_nan=False)

    def delete_device(self):
        self._closing = True
        bridge = getattr(self, "_bridge", None)
        if bridge is not None:
            if not bridge.stop(3):
                self.warn_stream("Python metadata reader still owned; replacement refused")
                return
            self._bridge = self._client = None
        if getattr(self, "_server", None) is not None:
            if self._thread is not None and self._thread.is_alive():
                self._server.shutdown()
                self._thread.join(3)
                if self._thread.is_alive():
                    self.warn_stream("Telemetry listener still owned; replacement refused")
                    return
            self._server.server_close()
            self._server = None
        if self._store is not None:
            self._store.close()
            self._store = None
        archive = getattr(self, '_archive', None)
        if archive is not None:
            if not archive.close(15):
                self.warn_stream('Archive worker still owned; replacement refused')
                return
            self._archive = None
        self._thread = None


if __name__ == "__main__":
    run((DS_AcqTelemetry,))
