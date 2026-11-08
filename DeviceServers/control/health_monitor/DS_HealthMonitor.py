"""Change-driven health monitor for ELYSE Tango Device Servers.

The monitor polls only to discover changes.  Its archive-enabled attributes are
updated and pushed only for a state, reachability, process-start, or error
transition; the scan timestamp is intentionally not configured for events.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

from tango import AttrWriteType, DevState, DeviceProxy, DispLevel
from tango.server import Device, attribute, command, device_property


DEFAULT_MONITORED_DEVICES = (
    "sys/database/2",
    "tango/admin/everest",
    "tango/admin/elysium2",
    "tango/admin/elysevm",
    "manip/V0/PDU_VO",
    "manip/VD2/PDU_VD2",
    "manip/SD1/PDU_SD1",
    "manip/SD2/PDU_SD2",
    "manip/ELYSE/PDU_ELYSE",
    "ELYSE/pdu/iTest",
    "control/DAQ/TRANCON-DAQ",
    "manip/general/PSP",
    "manip/sync/DG645",
    "manip/awg/keysight33509b_laser",
    "manip/V0/LaserPointing-Cam1",
    "manip/V0/LaserPointing-Cam2",
    "manip/V0/Cam1_V0",
    "manip/V0/Cam2_V0",
    "manip/V0/Cam3_V0",
    "manip/general/DS_OWIS_Aggregator",
    "manip/general/DS_OWIS_PS90",
    "manip/general/DS_OWIS_PS90_IP",
    "ELYSE/motorized_devices/DE1",
    "ELYSE/motorized_devices/DE2",
    "ELYSE/motorized_devices/MM1_X",
    "ELYSE/motorized_devices/MM1_Y",
    "ELYSE/motorized_devices/MM2_X",
    "ELYSE/motorized_devices/MM2_Y",
    "ELYSE/motorized_devices/MME_X",
    "ELYSE/motorized_devices/MME_Y",
    "manip/V0/DV01",
    "manip/V0/DV02",
    "manip/V0/DV03",
    "manip/V0/DV04",
    "manip/V0/F1",
    "manip/V0/L-2_1",
    "manip/V0/MM3_X",
    "manip/V0/MM3_Y",
    "manip/V0/MM4_X",
    "manip/V0/MM4_Y",
    "manip/V0/OPA_X",
    "manip/V0/OPA_Y",
    "manip/V0/S1",
    "manip/V0/S2",
    "manip/V0/S3",
    "manip/V0/TS_OPA_m",
    "manip/V0/TS_SC_m",
    "manip/camera/hamamatsu_streak_main",
    "manip/CR/ANDOR_CCD1",
    "manip/CR/ANDOR_SHAMROCK1",
    "manip/CR/ANDOR_KYMERA1",
    "ml/analysis/ML_UV1",
)

CRITICAL_STATES = {"ALARM", "DISABLE", "FAULT", "UNKNOWN", "UNREACHABLE"}
OPTIONAL_TRACKING_ATTRIBUTES = (
    "process_started_at_utc",
    "last_error_at_utc",
    "error_count",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_name(value: Any) -> str:
    """Convert DevState and compatible values to a stable uppercase name."""

    name = getattr(value, "name", None)
    if name:
        return str(name).upper()
    text = str(value).rsplit(".", 1)[-1]
    return text.upper()


def is_critical_state(value: Any) -> bool:
    return state_name(value) in CRITICAL_STATES


def normalized_device_names(values) -> list[str]:
    """Return unique, non-dserver Tango names while preserving order."""

    result: list[str] = []
    seen: set[str] = set()
    for raw in values or ():
        name = str(raw).strip()
        key = name.lower()
        if not name or key.startswith("dserver/") or key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


class DS_HealthMonitor(Device):
    """Read-only observer that emits events only when device health changes."""

    monitored_devices = device_property(dtype=(str,), default_value=[])
    poll_period_ms = device_property(dtype=int, default_value=2000)
    device_timeout_ms = device_property(dtype=int, default_value=700)

    @attribute(dtype=str, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def last_transition_json(self):
        with self._lock:
            return self._last_transition_json

    @attribute(dtype=str, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def last_critical_event_json(self):
        with self._lock:
            return self._last_critical_event_json

    @attribute(dtype=str, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def unreachable_devices_json(self):
        with self._lock:
            return self._unreachable_devices_json

    @attribute(dtype=int, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def transition_count(self):
        with self._lock:
            return self._transition_count

    @attribute(dtype=int, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def critical_event_count(self):
        with self._lock:
            return self._critical_event_count

    @attribute(dtype=int, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def monitored_device_count(self):
        return len(self._device_names)

    @attribute(dtype=str, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def monitored_devices_json(self):
        return json.dumps(self._device_names, separators=(",", ":"))

    @attribute(dtype=str, access=AttrWriteType.READ, display_level=DispLevel.OPERATOR)
    def last_scan_completed_at_utc(self):
        """UI diagnostic only; deliberately has no change/archive event."""

        with self._lock:
            return self._last_scan_completed_at_utc

    def init_device(self):
        Device.init_device(self)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._proxies: dict[str, Any] = {}
        self._last_transition_json = "{}"
        self._last_critical_event_json = "{}"
        self._unreachable_devices_json = "[]"
        self._transition_count = 0
        self._critical_event_count = 0
        self._last_scan_completed_at_utc = ""
        configured = normalized_device_names(self.monitored_devices)
        self._device_names = configured or list(DEFAULT_MONITORED_DEVICES)
        self._configure_transition_events()
        self.set_state(DevState.INIT)
        self.set_status("Establishing passive device-health baseline")
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="elyse-device-health-monitor",
            daemon=True,
        )
        self._thread.start()

    def delete_device(self):
        stop_event = getattr(self, "_stop_event", None)
        if stop_event is not None:
            stop_event.set()
        thread = getattr(self, "_thread", None)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        super().delete_device()

    def _configure_transition_events(self):
        names = (
            "last_transition_json",
            "last_critical_event_json",
            "unreachable_devices_json",
            "transition_count",
            "critical_event_count",
        )
        for name in names:
            self.set_change_event(name, True, False)
            self.set_archive_event(name, True, False)

    def _push_transition_attribute(self, name: str, value: Any):
        try:
            self.push_change_event(name, value)
        except Exception as exc:
            self.warn_stream(f"Cannot push change event for {name}: {exc}")
        try:
            self.push_archive_event(name, value)
        except Exception as exc:
            self.warn_stream(f"Cannot push archive event for {name}: {exc}")

    def _proxy_for(self, name: str):
        proxy = self._proxies.get(name)
        if proxy is None:
            proxy = DeviceProxy(name)
            proxy.set_timeout_millis(max(100, int(self.device_timeout_ms)))
            self._proxies[name] = proxy
        return proxy

    @staticmethod
    def _attribute_value(proxy, name: str, default=None):
        try:
            return proxy.read_attribute(name).value
        except Exception:
            return default

    def _observe_device(self, name: str) -> dict[str, Any]:
        try:
            proxy = self._proxy_for(name)
            current_state = state_name(proxy.state())
            snapshot: dict[str, Any] = {"state": current_state, "error": ""}
            for attribute_name in OPTIONAL_TRACKING_ATTRIBUTES:
                snapshot[attribute_name] = self._attribute_value(
                    proxy, attribute_name, None
                )
            return snapshot
        except Exception as exc:
            self._proxies.pop(name, None)
            return {
                "state": "UNREACHABLE",
                "error": str(exc)[:1000],
                "process_started_at_utc": None,
                "last_error_at_utc": None,
                "error_count": None,
            }

    @staticmethod
    def _event_type(previous: dict[str, Any], current: dict[str, Any]) -> str | None:
        if previous.get("state") != current.get("state"):
            return "reachability" if "UNREACHABLE" in {
                previous.get("state"), current.get("state")
            } else "state"
        old_start = previous.get("process_started_at_utc")
        new_start = current.get("process_started_at_utc")
        if old_start and new_start and old_start != new_start:
            return "process_restart"
        old_error_at = previous.get("last_error_at_utc")
        new_error_at = current.get("last_error_at_utc")
        if new_error_at and new_error_at != old_error_at:
            return "device_error"
        old_count = previous.get("error_count")
        new_count = current.get("error_count")
        if old_count is not None and new_count is not None and new_count != old_count:
            return "device_error"
        return None

    def _record_event(
        self,
        name: str,
        previous: dict[str, Any] | None,
        current: dict[str, Any],
        event_type: str,
    ):
        event = {
            "device": name,
            "event_type": event_type,
            "previous_state": previous.get("state") if previous else None,
            "new_state": current.get("state"),
            "process_started_at_utc": current.get("process_started_at_utc"),
            "last_error_at_utc": current.get("last_error_at_utc"),
            "error_count": current.get("error_count"),
            "observed_at_utc": utc_now_iso(),
            "error": current.get("error", ""),
        }
        encoded = json.dumps(event, separators=(",", ":"), ensure_ascii=True)
        with self._lock:
            self._last_transition_json = encoded
            self._transition_count += 1
            transition_count = self._transition_count
        self._push_transition_attribute("last_transition_json", encoded)
        self._push_transition_attribute("transition_count", transition_count)

        critical = is_critical_state(current.get("state")) or event_type == "device_error"
        if critical:
            with self._lock:
                self._last_critical_event_json = encoded
                self._critical_event_count += 1
                critical_count = self._critical_event_count
            self._push_transition_attribute("last_critical_event_json", encoded)
            self._push_transition_attribute("critical_event_count", critical_count)

    def _update_unreachable(self):
        unreachable = sorted(
            name
            for name, snapshot in self._snapshots.items()
            if snapshot.get("state") == "UNREACHABLE"
        )
        encoded = json.dumps(unreachable, separators=(",", ":"))
        with self._lock:
            if encoded == self._unreachable_devices_json:
                return
            self._unreachable_devices_json = encoded
        self._push_transition_attribute("unreachable_devices_json", encoded)

    @command(dtype_out=int)
    def scan_once(self):
        """Perform one immediate passive scan and return transition count."""

        for name in self._device_names:
            current = self._observe_device(name)
            previous = self._snapshots.get(name)
            if previous is None:
                self._snapshots[name] = current
                if current.get("state") == "UNREACHABLE":
                    self._record_event(name, None, current, "initial_unreachable")
                continue
            event_type = self._event_type(previous, current)
            self._snapshots[name] = current
            if event_type:
                self._record_event(name, previous, current, event_type)

        self._update_unreachable()
        now = utc_now_iso()
        with self._lock:
            self._last_scan_completed_at_utc = now
            unreachable_count = sum(
                snapshot.get("state") == "UNREACHABLE"
                for snapshot in self._snapshots.values()
            )
            transition_count = self._transition_count
        if unreachable_count:
            self.set_state(DevState.ALARM)
            self.set_status(
                f"Passive monitoring active: {unreachable_count} of "
                f"{len(self._device_names)} devices unreachable"
            )
        else:
            self.set_state(DevState.ON)
            self.set_status(
                f"Passive monitoring active: {len(self._device_names)} devices reachable"
            )
        return transition_count

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                self.scan_once()
            except Exception as exc:
                self.error_stream(f"Health scan failed: {exc}")
                self.set_state(DevState.FAULT)
                self.set_status(f"Health scan failed: {exc}")
            elapsed = time.monotonic() - started
            delay = max(0.1, (max(100, int(self.poll_period_ms)) / 1000.0) - elapsed)
            self._stop_event.wait(delay)


if __name__ == "__main__":
    DS_HealthMonitor.run_server()
