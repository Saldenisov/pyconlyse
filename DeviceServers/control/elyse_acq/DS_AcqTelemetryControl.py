"""Separate opt-in Tango telemetry + named command facade for XP vNext.

Does not replace/restart the live LabVIEW telemetry receiver. No native/NI
imports; local XP window owns initialization, cleanup and process lifecycle.
"""
import json

import tango
from tango.server import Device, attribute, command, device_property, run

from DeviceServers.control.elyse_acq.control_client import ControlBridge, ControlClient
from legacy.xp_acq_control.elyse_agent.acquisition_remote import strict_json


class AcqTelemetryControl(Device):
    key_file = device_property(dtype=str)
    command_key_file = device_property(dtype=str, default_value="")
    xp_port = device_property(dtype=int, default_value=8772)
    commands_enabled = device_property(dtype=bool, default_value=False)

    def init_device(self):
        self._closing = True
        old = getattr(self, "_bridge", None)
        if old is not None and not old.stop(3):
            raise RuntimeError("Previous reader remains owned; replacement refused")
        super().init_device()
        self._bridge = self._client = None
        self._error = "Waiting for XP control runtime"
        try:
            with open(self.key_file, "rb") as stream:
                read_key = stream.read().strip()
            command_key = None
            if self.commands_enabled:
                with open(self.command_key_file, "rb") as stream:
                    command_key = stream.read().strip()
            self._client = ControlClient(read_key, command_key, enabled=bool(self.commands_enabled), port=int(self.xp_port))
            self._bridge = ControlBridge(self._client)
            self._bridge.start()
            self._closing = False
            self.set_state(tango.DevState.INIT)
        except Exception as error:
            self._error = str(error)
            self.set_state(tango.DevState.FAULT)
            self.set_status(self._error)

    def _view(self):
        if self._bridge is None:
            return dict(quality="UNAVAILABLE", bridge_error=self._error, runtime=None, commands_enabled=False)
        return self._bridge.snapshot()

    @attribute(dtype=str)
    def telemetry_json(self):
        return json.dumps(self._view(), allow_nan=False)

    @attribute(dtype=str)
    def runtime_json(self):
        return json.dumps(self._view(), allow_nan=False)

    @command(dtype_in=str, dtype_out=str)
    def ExecuteCommand(self, request):
        """Exact ID/session/revision/confirmation envelope; no implicit retry."""
        if self._client is None or not self.commands_enabled or getattr(self, "_closing", True):
            raise RuntimeError("TANGO_COMMANDS_DISABLED")
        # Tango access-control rules must separately restrict this command.
        # An operator_confirmed flag is explicit intent, not authentication.
        return json.dumps(self._client.submit(strict_json(request.encode("utf-8"))), allow_nan=False)

    def dev_state(self):
        view = self._view()
        value = view.get("runtime") or {}
        self.set_status("{0}; {1}; commands={2}".format(view["quality"], view.get("bridge_error", ""), view.get("commands_enabled", False)))
        if value.get("cooling_safety", {}).get("active") or view["quality"] in ("FAULT", "RECOVERY_REQUIRED"):
            return tango.DevState.FAULT
        return {"FRESH": tango.DevState.RUNNING, "EXECUTING": tango.DevState.MOVING,
                "IDLE": tango.DevState.STANDBY, "STOPPED": tango.DevState.STANDBY}.get(view["quality"], tango.DevState.UNKNOWN)

    def delete_device(self):
        self._closing = True
        if getattr(self, "_bridge", None) is not None and not self._bridge.stop(3):
            self.warn_stream("Control telemetry reader did not exit; retain owner, no automatic restart")


if __name__ == "__main__":
    run((AcqTelemetryControl,))
