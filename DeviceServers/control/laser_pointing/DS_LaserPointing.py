import json
import sys
from datetime import datetime, timezone
from math import hypot
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from typing import Dict, Optional, Sequence, Tuple, Union
from uuid import uuid4

import numpy as np
from tango import AttrWriteType, Database, DevState, DispLevel
from tango.server import attribute, command, device_property
from taurus import Device

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

try:
    from DeviceServers.base.control import DS_ControlPosition
except ModuleNotFoundError:
    from base.control import DS_ControlPosition

try:
    from DeviceServers.control.laser_pointing.automatic_search import (
        SearchParameters,
        bounded_pattern_search,
        optical_point_group,
    )
    from DeviceServers.control.laser_pointing.beam_metrics import beam_contour_symmetry
except ModuleNotFoundError:
    from automatic_search import (
        SearchParameters,
        bounded_pattern_search,
        optical_point_group,
    )
    from beam_metrics import beam_contour_symmetry


DEFAULT_SEARCH_CONFIG = {
    "mode": "sensitive",
    "initial_step": 10.0,
    "minimum_step": 2.0,
    "step_schedule": [10.0, 6.0, 2.0],
    "radius": 30.0,
    "tolerance_px": 2.0,
    "roundness_tolerance_pct": 7.0,
    "minimum_improvement_px": 0.1,
    "unchanged_response_tolerance_px": 0.25,
    "probe_repetitions": 3,
    "max_evaluations": 16,
    "max_cycles": 2,
    "samples": 3,
    "invalid_frame_retries": 5,
    "sample_interval_s": 0.2,
    "camera_frame_wait_s": 0.25,
    "motion_timeout_s": 180.0,
    "motion_poll_s": 0.2,
    "position_tolerance": 0.05,
    "position_stable_reads": 2,
    "groups": [],
    "point_pairs": {},
    "camera_verified_roles": [],
    "restore_point": "",
}


class SearchCancelled(RuntimeError):
    """Raised internally when cancellation occurs during a measurement."""


class LaserNotVisible(RuntimeError):
    """Raised when Basler has no valid laser centroid."""


class DS_LaserPointing(DS_ControlPosition):
    """Alternate optical planes and minimise their beam-contour asymmetry."""

    RULES = {
        "start_cgc": [DevState.ON],
        "stop_cgc": [DevState.ON],
        "start_automatic_search": [DevState.ON],
        "pause_automatic_search": [DevState.ON],
        "resume_automatic_search": [DevState.ON],
        "stop_automatic_search": [DevState.ON],
        "accept_alignment_reference": [DevState.ON],
        "apply_controller_point": [DevState.ON],
        "select_manual_point": [DevState.ON],
        "initialize_active_pair": [DevState.ON],
        "move_active_actuator": [DevState.ON],
        **DS_ControlPosition.RULES,
    }
    _version_ = "0.2"
    _model_ = "LaserPointing Controller"
    polling = 500

    automatic_search_defaults = device_property(
        dtype=str, default_value=json.dumps(DEFAULT_SEARCH_CONFIG)
    )
    alignment_reference_property = device_property(dtype=str, default_value="{}")
    alignment_reference_history_property = device_property(dtype=(str,), default_value=[])
    alignment_pending_reference_property = device_property(dtype=str, default_value="{}")
    alignment_session_events_property = device_property(dtype=(str,), default_value=[])

    def init_device(self):
        old_stop = getattr(self, "_search_stop", None)
        if old_stop is not None:
            self._restore_on_cancel = False
            old_stop.set()
        old_pause = getattr(self, "_search_pause", None)
        if old_pause is not None:
            old_pause.clear()

        self.sample_time = 1
        self.cgc = False
        self.deltas = [0.0, 0.0]
        self.current_pos = {"X": 0.0, "Y": 0.0}
        self.previos_pos = {"X": 0.0, "Y": 0.0}
        self.positions_before_pid = {}
        self._search_lock = Lock()
        self._alignment_event_lock = Lock()
        self._search_stop = Event()
        self._search_pause = Event()
        self._search_thread: Optional[Thread] = None
        self._point_application_thread: Optional[Thread] = None
        self._search_status = "idle"
        self._search_progress: Dict = {}
        self._search_history = []
        self._search_started_at = None
        self._search_session_id = ""
        self._search_initial_state = {}
        self._restore_on_cancel = False
        self._pause_active = False
        self._progress_before_pause = {}
        self._last_beam_shape = None
        self._active_point = ""
        self._actuator_initialization_status = {
            "phase": "idle",
            "group": 0,
            "message": "Select an optical point before initialising a Standa pair",
        }

        super().init_device()
        # Flipper targets are camera-routing settings owned by the registered
        # controller rules. They are deliberately not inferred from camera
        # number: Cam1 uses S1=-1, while Cam2 uses S1=+1 and S2=-1.
        camera_name = self.ds_dict["Camera"]
        self.devices[camera_name] = Device(camera_name)
        self._search_config = self._normalise_search_config(
            self.automatic_search_defaults
        )
        self._alignment_reference = self._json_object(
            self.alignment_reference_property
        )
        self._alignment_pending_reference = self._json_object(
            self.alignment_pending_reference_property
        )
        self._alignment_reference_history = self._string_list(
            self.alignment_reference_history_property
        )
        self._alignment_session_events = self._string_list(
            self.alignment_session_events_property
        )
        self._alignment_event_count = len(self._alignment_session_events)
        self._alignment_event_json = (
            self._alignment_session_events[-1]
            if self._alignment_session_events else "{}"
        )
        self._configure_alignment_events()
        self.register_variables_for_archive()
        self.turn_on()

    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def find_device(self):
        argreturn = self.server_id, self.device_id
        self._device_id_internal, self._uri = argreturn

    def get_controller_status_local(self) -> Union[int, str]:
        return super().get_controller_status_local()

    def turn_on_local(self) -> Union[int, str]:
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self._restore_on_cancel = False
        self._search_stop.set()
        self.set_state(DevState.OFF)
        return 0

    @attribute(
        label="Automatic search status",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def automatic_search_status(self):
        return self._search_status

    @attribute(
        label="Automatic search progress",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def automatic_search_progress(self):
        return json.dumps(self._search_progress, sort_keys=True)

    @attribute(
        label="Automatic search convergence history",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def automatic_search_history(self):
        """Chronological beam-roundness observations for time-based plots."""

        return json.dumps(list(self._search_history), sort_keys=True)

    @attribute(
        label="Last alignment session event",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def alignment_session_event_json(self):
        return self._alignment_event_json

    @attribute(
        label="Alignment session event count",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def alignment_session_event_count(self):
        return int(self._alignment_event_count)

    @attribute(
        label="Accepted alignment reference",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def alignment_reference_json(self):
        return json.dumps(self._alignment_reference, sort_keys=True)

    @attribute(
        label="Accepted alignment reference revision",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def alignment_reference_revision(self):
        return len(self._alignment_reference_history)

    @attribute(
        label="Alignment awaiting operator acceptance",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def alignment_pending_reference_json(self):
        return json.dumps(self._alignment_pending_reference, sort_keys=True)

    @attribute(
        label="Active optical point",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def active_point(self):
        return self._active_point

    @attribute(
        label="Active actuator group",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def active_actuator_group(self):
        return optical_point_group(self._active_point)

    @attribute(
        label="Active actuator initialisation status",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def actuator_initialization_status(self):
        return json.dumps(self._actuator_initialization_status, sort_keys=True)

    @attribute(
        label="Automatic search configuration",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
    )
    def automatic_search_config(self):
        return json.dumps(self._search_config, sort_keys=True)

    def write_automatic_search_config(self, value):
        if self._search_is_running():
            raise RuntimeError("automatic search configuration is locked while running")
        self._search_config = self._normalise_search_config(value)

    @command(
        dtype_in=str,
        dtype_out=int,
        doc_in="Optional JSON object overriding automatic-search configuration.",
    )
    def start_automatic_search(self, configuration=""):
        """Start a serialized worker and return immediately."""
        with self._search_lock:
            if self._search_is_running():
                return -1
            if self._alignment_pending_reference:
                raise RuntimeError(
                    "accept the completed alignment or cancel and restore it "
                    "before starting another search"
                )
            if self._point_application_is_running():
                raise RuntimeError(
                    "cannot start automatic search while applying an optical point"
                )
            try:
                config = dict(self._search_config)
                if str(configuration).strip():
                    override = json.loads(str(configuration))
                    if not isinstance(override, dict):
                        raise ValueError("search command input must be a JSON object")
                    config.update(override)
                config = self._normalise_search_config(config)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self._search_status = f"error: {error}"
                self.error(self._search_status)
                return -1

            self._search_stop.clear()
            self._search_pause.clear()
            self.cgc = True
            self._search_status = "running"
            self._search_history = []
            self._search_started_at = monotonic()
            self._search_session_id = str(uuid4())
            self._search_initial_state = {}
            self._restore_on_cancel = True
            self._pause_active = False
            self._progress_before_pause = {}
            self._search_progress = {
                "phase": "starting",
                "config": config,
                "session_id": self._search_session_id,
                "accepted_reference_revision": len(
                    self._alignment_reference_history
                ),
            }
            self._search_thread = Thread(
                target=self._automatic_search_worker,
                args=(config,),
                name=f"{self.device_name}-automatic-search",
                daemon=True,
            )
            self._record_alignment_event("search_start_requested")
            self._search_thread.start()
        return 0

    @command(dtype_out=int)
    def pause_automatic_search(self):
        """Pause at the next safe checkpoint without losing search state."""

        if not self._search_is_running() or self._search_status != "running":
            return -1
        if self._search_pause.is_set():
            return 0
        self._search_pause.set()
        self._search_status = "pausing"
        self._record_alignment_event("pause_requested")
        return 0

    @command(dtype_out=int)
    def resume_automatic_search(self):
        """Continue the same worker, objective state, and convergence history."""

        if (
            not self._search_is_running()
            or self._search_status not in ("pausing", "paused")
            or not self._search_pause.is_set()
        ):
            return -1
        self._search_pause.clear()
        self._search_status = "running"
        self._record_alignment_event("resume_requested")
        return 0

    @command(dtype_out=int)
    def stop_automatic_search(self):
        """Cancel the search and asynchronously restore its captured baseline."""

        if self._search_status in ("cancelling", "restoring"):
            return -1
        self._restore_on_cancel = True
        if self._alignment_pending_reference:
            candidate = dict(self._alignment_pending_reference)
            baseline = candidate.get("initial_state") or self._search_initial_state
            restore_config = dict(
                candidate.get("search_config") or self._search_config
            )
            self._search_session_id = str(candidate.get("session_id", ""))
            self._search_stop.clear()
            self._search_pause.clear()
            self._search_status = "restoring"
            self._search_thread = Thread(
                target=self._restore_completed_alignment_worker,
                args=(baseline, restore_config),
                name=f"{self.device_name}-restore-alignment",
                daemon=True,
            )
            self._record_alignment_event("completed_alignment_rejected")
            self._search_thread.start()
            return 0
        self._search_stop.set()
        self._search_pause.clear()
        self.cgc = False
        if self._search_is_running():
            self._search_status = "cancelling"
            self._record_alignment_event("cancel_and_restore_requested")
        return 0

    @command(
        dtype_in=str,
        dtype_out=int,
        doc_in="Optional JSON metadata, for example an operator comment.",
    )
    def accept_alignment_reference(self, metadata=""):
        """Persist the completed state as a new, revisioned reference."""

        if self._search_is_running():
            raise RuntimeError("wait for automatic alignment to finish")
        candidate = dict(self._alignment_pending_reference)
        if not candidate:
            raise RuntimeError("there is no completed alignment awaiting acceptance")
        current_state = self._capture_alignment_state()
        mismatches = self._alignment_state_mismatches(candidate, current_state)
        if mismatches:
            raise RuntimeError(
                "alignment hardware changed after the search finished; "
                "discard and restore or run the alignment again: "
                + "; ".join(mismatches)
            )
        details = {}
        if str(metadata).strip():
            details = json.loads(str(metadata))
            if not isinstance(details, dict):
                raise ValueError("acceptance metadata must be a JSON object")
        reference = {
            **candidate,
            "accepted_at_utc": self._utc_now(),
            "acceptance": details,
            "revision": len(self._alignment_reference_history) + 1,
        }
        encoded = json.dumps(reference, separators=(",", ":"), sort_keys=True)
        history = [*self._alignment_reference_history, encoded]
        self._persist_alignment_properties({
            "alignment_reference_property": encoded,
            "alignment_reference_history_property": history,
            "alignment_pending_reference_property": "{}",
        })
        self._alignment_reference = reference
        self._alignment_reference_history = history
        self._alignment_pending_reference = {}
        self._search_status = "reference accepted"
        self._search_progress = {
            **self._search_progress,
            "acceptance_required": False,
            "accepted_reference_revision": reference["revision"],
            "accepted_at_utc": reference["accepted_at_utc"],
        }
        self._record_alignment_event(
            "reference_accepted", revision=reference["revision"]
        )
        self._push_alignment_value(
            "alignment_reference_json", self.alignment_reference_json()
        )
        self._push_alignment_value(
            "alignment_reference_revision", reference["revision"]
        )
        self._push_alignment_value("alignment_pending_reference_json", "{}")
        return reference["revision"]

    @command(
        dtype_in=str,
        dtype_out=int,
        doc_in="Controller point name, for example point3 or working.",
    )
    def apply_controller_point(self, point_name):
        """Start applying one complete optical preset through the controller.

        This is the browser-safe equivalent of clicking a point in the Qt
        composite widget: the controller owns all child-device coordination
        and publishes the point only after actual motor readback.  The Tango
        command returns immediately so long optical movements do not occupy
        the device serialization monitor and time out browser clients.
        """
        point_name = str(point_name).strip()
        if point_name not in self.controller_rules:
            raise ValueError(f"unknown controller point: {point_name}")

        with self._search_lock:
            if self._search_is_running():
                raise RuntimeError("cannot apply a point while automatic search is running")
            if self._alignment_acceptance_is_pending():
                raise RuntimeError(
                    "accept the completed alignment or cancel and restore it first"
                )
            if self._point_application_is_running():
                raise RuntimeError("another optical point is already being applied")
            self._search_stop.clear()
            # A partially applied preset must not leave either mount pair
            # unlocked under the previously selected point.
            self._active_point = ""
            self._actuator_initialization_status = {
                "phase": "point_applying",
                "group": 0,
                "message": f"Applying {point_name}; alignment mounts are locked",
            }
            self._search_progress = {
                "phase": "manual_point",
                "point": point_name,
                "message": f"Applying {point_name}",
            }
            self._point_application_thread = Thread(
                target=self._point_application_worker,
                args=(point_name, dict(self._search_config)),
                name=f"{self.device_name}-apply-{point_name}",
                daemon=True,
            )
            self._point_application_thread.start()
        return 0

    @command(
        dtype_in=str,
        dtype_out=int,
        doc_in="Point name used only to select the active manual Standa pair.",
    )
    def select_manual_point(self, point_name):
        """Select a manual mount pair without moving any laser-path hardware."""

        point_name = str(point_name).strip()
        if point_name not in self.controller_rules:
            raise ValueError(f"unknown controller point: {point_name}")
        if optical_point_group(point_name) == 0:
            raise ValueError("manual Standa control requires a numbered optical point")

        with self._search_lock:
            if self._search_is_running():
                raise RuntimeError(
                    "cannot select a manual point while automatic search is running"
                )
            if self._alignment_acceptance_is_pending():
                raise RuntimeError(
                    "accept the completed alignment or cancel and restore it first"
                )
            if self._point_application_is_running():
                raise RuntimeError(
                    "cannot select a manual point while an optical preset is applying"
                )
            self._publish_active_point(point_name)
            self._search_progress = {
                "phase": "manual_point_selected",
                "point": point_name,
                "message": (
                    f"Selected {point_name} for manual Standa control; "
                    "laser-path hardware was not moved"
                ),
            }
        return 0

    def _point_application_worker(self, point_name: str, config: Dict):
        try:
            self._apply_point(point_name, config)
        except SearchCancelled:
            self._search_progress = {
                "phase": "manual_point_cancelled",
                "point": point_name,
                "message": f"Applying {point_name} was cancelled",
            }
            self._actuator_initialization_status = {
                "phase": "point_application_cancelled",
                "group": 0,
                "message": f"Applying {point_name} was cancelled; mounts remain locked",
            }
        except Exception as error:
            self._search_progress = {
                "phase": "manual_point_error",
                "point": point_name,
                "message": f"Could not apply {point_name}: {error}",
            }
            self._actuator_initialization_status = {
                "phase": "point_application_error",
                "group": 0,
                "message": f"Could not apply {point_name}; mounts remain locked",
            }
            self.error(self._search_progress["message"])
        else:
            self._search_progress = {
                "phase": "manual_point_complete",
                "point": point_name,
                "message": f"Applied {point_name}",
            }

    @command(dtype_out=int)
    def initialize_active_pair(self):
        """Initialise the selected X/Y pair in deterministic sequence.

        Point selection is the safety interlock. The command never selects a
        point and never initialises axes from the inactive pair.
        """

        with self._search_lock:
            if self._search_is_running():
                raise RuntimeError(
                    "cannot initialise alignment mounts during automatic search"
                )
            if self._alignment_acceptance_is_pending():
                raise RuntimeError(
                    "accept the completed alignment or cancel and restore it first"
                )
            if self._point_application_is_running():
                raise RuntimeError(
                    "cannot initialise alignment mounts while applying an optical point"
                )
            group_index = optical_point_group(self._active_point)
            if group_index == 0:
                raise RuntimeError(
                    "select optical point 1-3 or 4-6 before initialising a Standa pair"
                )
            group_name, roles = self._actuator_group_entry(group_index)
            completed = []
            self._actuator_initialization_status = {
                "phase": "starting",
                "group": group_index,
                "group_name": group_name,
                "roles": list(roles),
                "completed": [],
                "message": f"Initialising Standa pair {group_index}",
            }
            try:
                for axis_index, role in enumerate(roles, start=1):
                    device = self._device_for_role(role)
                    self._actuator_initialization_status = {
                        "phase": "initializing_axis",
                        "group": group_index,
                        "group_name": group_name,
                        "role": role,
                        "axis_index": axis_index,
                        "axis_count": len(roles),
                        "completed": list(completed),
                        "message": (
                            f"Initialising {role} ({axis_index}/{len(roles)})"
                        ),
                    }
                    device.turn_on()
                    lifecycle = self._actuator_lifecycle(device)
                    if not lifecycle["ready"]:
                        detail = lifecycle["detail"] or lifecycle["state"]
                        raise RuntimeError(f"{role} did not initialise: {detail}")
                    completed.append(role)
            except Exception as error:
                self._actuator_initialization_status = {
                    "phase": "failed",
                    "group": group_index,
                    "group_name": group_name,
                    "completed": list(completed),
                    "message": str(error),
                }
                raise

            self._actuator_initialization_status = {
                "phase": "complete",
                "group": group_index,
                "group_name": group_name,
                "roles": list(roles),
                "completed": list(completed),
                "message": f"Standa pair {group_index} is initialised",
            }
        return 0

    @command(
        dtype_in=str,
        dtype_out=int,
        doc_in='JSON object with an actuator "role" and absolute "target".',
    )
    def move_active_actuator(self, request):
        """Move one mount axis only when its optical point owns the pair.

        This is the authoritative interlock used by the web client.  A manual
        move is refused until a numbered point has been applied successfully,
        and roles from the inactive X/Y pair are never accepted.
        """

        try:
            payload = json.loads(str(request))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("actuator move must be a JSON object") from error
        if not isinstance(payload, dict):
            raise ValueError("actuator move must be a JSON object")
        role = str(payload.get("role", "")).strip()
        try:
            target = float(payload["target"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("actuator move requires a numeric target") from error

        with self._search_lock:
            if self._search_is_running():
                raise RuntimeError("manual actuator movement is locked during automatic search")
            if self._alignment_acceptance_is_pending():
                raise RuntimeError(
                    "accept the completed alignment or cancel and restore it first"
                )
            if self._point_application_is_running():
                raise RuntimeError(
                    "manual actuator movement is locked while applying an optical point"
                )
            active_group = optical_point_group(self._active_point)
            if active_group == 0:
                raise RuntimeError(
                    "select optical point 1-3 or 4-6 before moving an alignment mount"
                )
            group_name, allowed_roles = self._actuator_group_entry(active_group)
            if role not in allowed_roles:
                raise RuntimeError(
                    f"{role or 'requested actuator'} is locked; {group_name} is active "
                    f"for {self._active_point}"
                )
            unavailable = []
            for allowed_role in allowed_roles:
                lifecycle = self._actuator_lifecycle(
                    self._device_for_role(allowed_role)
                )
                if not lifecycle["ready"]:
                    unavailable.append(allowed_role)
            if unavailable:
                raise RuntimeError(
                    f"Standa pair {active_group} is not initialised; unavailable axes: "
                    + ", ".join(unavailable)
                )
            config = dict(self._search_config)
            self._move_single_axis(self._device_for_role(role), target, config)
        return 0

    # Backward compatibility for existing clients and scripts.
    @command(dtype_in=str, dtype_out=int)
    def start_cgc(self, client_token=""):
        configuration = client_token if str(client_token).lstrip().startswith("{") else ""
        return self.start_automatic_search(configuration)

    @command(dtype_in=str, dtype_out=int)
    def stop_cgc(self, client_token=""):
        return self.stop_automatic_search()

    def _search_is_running(self) -> bool:
        return self._search_thread is not None and self._search_thread.is_alive()

    def _point_application_is_running(self) -> bool:
        thread = getattr(self, "_point_application_thread", None)
        return (
            thread is not None
            and thread.is_alive()
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    @staticmethod
    def _json_object(value) -> Dict:
        try:
            parsed = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _string_list(value):
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    def _configure_alignment_events(self):
        self._alignment_events_ready = False
        for name in (
            "alignment_session_event_json",
            "alignment_session_event_count",
            "alignment_reference_json",
            "alignment_reference_revision",
            "alignment_pending_reference_json",
        ):
            try:
                self.set_change_event(name, True, False)
                self.set_archive_event(name, True, False)
            except Exception as error:
                self.warn_stream(
                    f"Cannot configure LaserPointing session event {name}: {error}"
                )
        self._alignment_events_ready = True

    def _push_alignment_value(self, name, value):
        if not getattr(self, "_alignment_events_ready", False):
            return
        for event_kind in ("change", "archive"):
            try:
                getattr(self, f"push_{event_kind}_event")(name, value)
            except Exception as error:
                self.warn_stream(
                    f"Cannot push {event_kind} event for {name}: {error}"
                )

    def _persist_alignment_properties(self, properties):
        """Write durable session data to the Tango database.

        The Tango database is the authoritative persistent store available to
        the device today. HDB++ can additionally retain every pushed event
        after its Linux acceptance environment is activated.
        """

        get_name = getattr(self, "get_name", None)
        if get_name is None:
            # Unit-test instances are intentionally created without Tango's
            # DeviceImpl. They still exercise the in-memory lifecycle.
            return
        Database().put_device_property(get_name(), properties)

    def _record_alignment_event(self, event_type: str, **details):
        event = {
            "event_type": str(event_type),
            "session_id": getattr(self, "_search_session_id", ""),
            "status": getattr(self, "_search_status", "idle"),
            "recorded_at_utc": self._utc_now(),
            **details,
        }
        encoded = json.dumps(event, separators=(",", ":"), sort_keys=True)
        lock = getattr(self, "_alignment_event_lock", None)
        if lock is None:
            lock = Lock()
            self._alignment_event_lock = lock
        with lock:
            history = [*getattr(self, "_alignment_session_events", []), encoded]
            try:
                self._persist_alignment_properties({
                    "alignment_session_events_property": history,
                })
            except Exception as error:
                self.warn_stream(
                    f"Could not persist alignment session event: {error}"
                )
            self._alignment_session_events = history
            self._alignment_event_count = len(history)
            self._alignment_event_json = encoded
        self._push_alignment_value("alignment_session_event_json", encoded)
        self._push_alignment_value(
            "alignment_session_event_count", self._alignment_event_count
        )

    def _alignment_role_specs(self):
        specs = {}
        for rule in self.controller_rules.values():
            for role, value in rule.items():
                if role in self.ds_dict and role not in specs:
                    specs[role] = value
        return specs

    def _capture_alignment_state(self) -> Dict:
        state = {
            "captured_at_utc": self._utc_now(),
            "active_point": self._active_point,
            "actuators": {},
            "optics": {},
        }
        actuator_roles = []
        for group_index in range(1, len(self.pid_groups) + 1):
            _group_name, roles = self._actuator_group_entry(group_index)
            actuator_roles.extend(roles)
        for role in actuator_roles:
            position, motor_state = self._fresh_position_and_state(
                self._device_for_role(role)
            )
            state["actuators"][role] = {
                "position": position,
                "state": motor_state,
            }

        for role, specification in self._alignment_role_specs().items():
            device = self._device_for_role(role)
            if self._is_flipper_role(role):
                command_state = self._fresh_flipper_command_state(device)
                state["optics"][role] = {
                    "kind": "flipper",
                    "position": -1.0 if command_state == "UP_BLOCKED" else 1.0,
                    "commanded_state": command_state,
                }
            elif isinstance(specification, (list, tuple)) and len(specification) == 2:
                axis = int(specification[0])
                state["optics"][role] = {
                    "kind": "multi_axis",
                    "axis": axis,
                    "position": float(device.read_position_axis(axis)),
                    "state": str(device.get_status_axis(axis)),
                }
            else:
                position, motor_state = self._fresh_position_and_state(device)
                state["optics"][role] = {
                    "kind": "single_axis",
                    "position": position,
                    "state": motor_state,
                }
        return state

    def _alignment_state_mismatches(self, reference: Dict, current: Dict):
        tolerance = max(
            0.05,
            float(getattr(self, "_search_config", {}).get(
                "position_tolerance", 0.05
            )),
        )
        mismatches = []
        for section in ("actuators", "optics"):
            expected_items = reference.get(section, {})
            actual_items = current.get(section, {})
            for role, expected in expected_items.items():
                actual = actual_items.get(role)
                if actual is None:
                    mismatches.append(f"{role} readback is unavailable")
                    continue
                if expected.get("kind") == "flipper":
                    if actual.get("commanded_state") != expected.get("commanded_state"):
                        mismatches.append(
                            f"{role} is {actual.get('commanded_state')}, "
                            f"expected {expected.get('commanded_state')}"
                        )
                    continue
                try:
                    delta = abs(
                        float(actual["position"]) - float(expected["position"])
                    )
                except (KeyError, TypeError, ValueError):
                    mismatches.append(f"{role} position is unavailable")
                    continue
                if delta > tolerance:
                    mismatches.append(
                        f"{role} moved by {delta:.3f} (limit {tolerance:.3f})"
                    )
        return mismatches

    def _restore_alignment_state(self, state: Dict, config: Dict):
        if not state:
            raise RuntimeError("the automatic search baseline was not captured")
        self._search_status = "restoring"
        self._search_progress = {
            "phase": "restoring_initial_state",
            "session_id": self._search_session_id,
            "message": "Restoring pre-search Standa and optical readbacks",
        }
        self._record_alignment_event("restore_started")

        # Cancellation has reached the worker. Clear it only for the bounded
        # rollback operations; no search evaluation can resume from here.
        self._search_stop.clear()
        self._search_pause.clear()
        for role, snapshot in state.get("actuators", {}).items():
            self._search_progress.update({
                "restoring_role": role,
                "message": f"Restoring {role} to {snapshot['position']}",
            })
            self._move_single_axis(
                self._device_for_role(role), float(snapshot["position"]), config
            )

        # Restore apertures before translation/waveplate axes and flippers.
        optics = list(state.get("optics", {}).items())
        optics.sort(key=lambda item: (
            0 if "diaphragm" in item[0].lower() else
            1 if item[1].get("kind") == "multi_axis" else
            3 if item[1].get("kind") == "flipper" else 2
        ))
        for role, snapshot in optics:
            self._search_progress.update({
                "restoring_role": role,
                "message": f"Restoring {role} to {snapshot['position']}",
            })
            device = self._device_for_role(role)
            if snapshot.get("kind") == "multi_axis":
                self._move_multi_axis(
                    device,
                    [snapshot["axis"], snapshot["position"]],
                    config,
                )
            elif snapshot.get("kind") == "flipper":
                result = device.move_axis_abs(float(snapshot["position"]))
                command_error = self._command_error(result)
                if command_error:
                    raise RuntimeError(f"{role}: {command_error}")
                expected = str(snapshot.get("commanded_state", ""))
                actual = self._fresh_flipper_command_state(device)
                if expected and actual != expected:
                    raise RuntimeError(
                        f"{role} restored to {actual}, expected {expected}"
                    )
            else:
                self._move_single_axis(device, float(snapshot["position"]), config)
        self._active_point = str(state.get("active_point", ""))
        self._search_progress = {
            "phase": "restored_initial_state",
            "session_id": self._search_session_id,
            "message": "Cancelled alignment; restored the complete pre-search state",
            "restored_state": state,
        }
        self._search_status = "cancelled and restored"
        self._record_alignment_event("initial_state_restored")

    def _store_pending_reference(self, candidate: Dict):
        encoded = json.dumps(candidate, separators=(",", ":"), sort_keys=True)
        self._persist_alignment_properties({
            "alignment_pending_reference_property": encoded,
        })
        self._alignment_pending_reference = candidate
        self._push_alignment_value("alignment_pending_reference_json", encoded)

    def _clear_pending_reference(self):
        self._persist_alignment_properties({
            "alignment_pending_reference_property": "{}",
        })
        self._alignment_pending_reference = {}
        self._push_alignment_value("alignment_pending_reference_json", "{}")

    def _restore_completed_alignment_worker(self, baseline: Dict, config: Dict):
        try:
            self._restore_alignment_state(baseline, config)
            self._clear_pending_reference()
        except Exception as error:
            self._search_status = f"restore failed: {error}"
            self._search_progress = {
                "phase": "restore_failed",
                "session_id": self._search_session_id,
                "message": str(error),
            }
            self._record_alignment_event("restore_failed", error=str(error))
            self.error(
                f"Could not restore rejected LaserPointing alignment: {error}"
            )
        finally:
            self.cgc = False
            self._search_pause.clear()

    def _alignment_acceptance_is_pending(self) -> bool:
        return bool(getattr(self, "_alignment_pending_reference", {}))

    @staticmethod
    def _normalise_search_config(value) -> Dict:
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError("automatic search configuration must be a JSON object")
        config = dict(DEFAULT_SEARCH_CONFIG)
        config.update(value)

        mode = str(config["mode"]).lower().strip()
        if mode not in ("medium", "sensitive", "staged"):
            raise ValueError("mode must be medium, sensitive, or staged")
        config["mode"] = mode
        for name in (
            "initial_step",
            "minimum_step",
            "radius",
            "tolerance_px",
            "roundness_tolerance_pct",
            "minimum_improvement_px",
            "unchanged_response_tolerance_px",
            "sample_interval_s",
            "camera_frame_wait_s",
            "motion_timeout_s",
            "motion_poll_s",
            "position_tolerance",
        ):
            config[name] = float(config[name])
        for name in (
            "probe_repetitions",
            "max_evaluations",
            "max_cycles",
            "samples",
            "invalid_frame_retries",
            "position_stable_reads",
        ):
            config[name] = int(config[name])

        if not isinstance(config["step_schedule"], (list, tuple)):
            raise ValueError("step_schedule must be a JSON list")
        config["step_schedule"] = [float(step) for step in config["step_schedule"]]
        if not config["step_schedule"]:
            raise ValueError("step_schedule cannot be empty")
        config["initial_step"] = config["step_schedule"][0]
        config["minimum_step"] = config["step_schedule"][-1]

        SearchParameters(
            initial_step=config["initial_step"],
            minimum_step=config["minimum_step"],
            tolerance_px=config["roundness_tolerance_pct"],
            max_evaluations=config["max_evaluations"],
            minimum_improvement_px=config["minimum_improvement_px"],
            step_schedule=tuple(config["step_schedule"]),
            probe_repetitions=config["probe_repetitions"],
            unchanged_response_tolerance_px=config[
                "unchanged_response_tolerance_px"
            ],
        ).validate()
        if config["radius"] <= 0:
            raise ValueError("radius must be positive")
        if config["max_cycles"] < 1:
            raise ValueError("max_cycles must be at least 1")
        if config["samples"] < 1 or config["samples"] > 5:
            raise ValueError("samples must be between 1 and 5")
        if config["invalid_frame_retries"] < 0:
            raise ValueError("invalid_frame_retries cannot be negative")
        if config["sample_interval_s"] < 0 or config["camera_frame_wait_s"] < 0:
            raise ValueError("camera measurement times cannot be negative")
        if config["motion_timeout_s"] <= 0 or config["motion_poll_s"] <= 0:
            raise ValueError("motion timeout and poll interval must be positive")
        if config["position_tolerance"] < 0:
            raise ValueError("position_tolerance cannot be negative")
        if config["position_stable_reads"] < 1:
            raise ValueError("position_stable_reads must be at least 1")
        if not isinstance(config["groups"], list):
            raise ValueError("groups must be a JSON list")
        if not isinstance(config["point_pairs"], dict):
            raise ValueError("point_pairs must be a JSON object")
        # Flippers are not part of optical-point application, so legacy
        # camera-verified flipper entries from the Tango database are ignored.
        config["camera_verified_roles"] = []
        config["restore_point"] = str(config["restore_point"]).strip()
        return config

    def _automatic_search_worker(self, config: Dict):
        results = []
        verification = []
        try:
            self._search_initial_state = self._capture_alignment_state()
            self._search_progress = {
                **self._search_progress,
                "phase": "baseline_captured",
                "initial_state": self._search_initial_state,
                "message": "Captured pre-search state; starting alignment",
            }
            self._record_alignment_event(
                "search_started", initial_state=self._search_initial_state
            )
            camera = self.devices[self.ds_dict["Camera"]]
            try:
                if not bool(camera.isgrabbing):
                    camera.start_grabbing()
            except Exception as error:
                raise RuntimeError(f"could not start camera acquisition: {error}")

            stages = self._point_stages(config)
            self._validate_camera_verified_roles(config, stages)
            config["_camera_verified_roles_validated"] = True
            converged = False
            search_origins = {}
            # Keep the best measured position across motor-step passes. A
            # finer pass can be noisier than a coarse pass; it must not leave
            # the hardware at a demonstrably worse position merely because
            # each bounded search has its own local result object.
            self._search_stage_bests = {}
            for cycle in range(1, config["max_cycles"] + 1):
                for motor_step in config["step_schedule"]:
                    for stage_name, point_pairs in stages:
                        for group_name, point_pair in point_pairs:
                            self._raise_if_cancelled()
                            result = self._optimise_group(
                                group_name,
                                point_pair,
                                stage_name,
                                cycle,
                                float(motor_step),
                                config,
                                search_origins,
                            )
                            results.append(result)
                    # The second mount can affect the first optical plane.
                    # Revisit every sensitive point after the whole pass;
                    # previously good scores cannot prove convergence.
                    verification = []
                    for group_name, point_pair in stages[-1][1]:
                        self._raise_if_cancelled()
                        point_name = point_pair[-1]
                        self._measure_point(point_name, config)
                        shape = self._read_beam_shape()
                        verification.append({
                            "group": group_name,
                            "point": point_name,
                            "roundness_error_pct": shape["roundness_error_pct"],
                            "contour_centre_drift_px": shape.get(
                                "contour_centre_drift_px"
                            ),
                        })
                    self._search_progress = {
                        "phase": "verifying",
                        "cycle": cycle,
                        "motor_step": motor_step,
                        "points": verification,
                        "results": results,
                    }
                    if verification and all(
                        item["roundness_error_pct"]
                        <= config["roundness_tolerance_pct"]
                        for item in verification
                    ):
                        converged = True
                        break
                if converged:
                    break

            restore_point = config["restore_point"]
            if restore_point:
                if restore_point not in self.controller_rules:
                    raise ValueError(f"unknown restore_point {restore_point!r}")
                self._apply_point(restore_point, config)

            self._search_progress = {
                "phase": "finished" if converged else "not_converged",
                "converged": converged,
                "verification": verification,
                "results": results,
                "session_id": self._search_session_id,
                "acceptance_required": True,
            }
            self._raise_if_cancelled()
            candidate = self._capture_alignment_state()
            self._raise_if_cancelled()
            candidate.update({
                "session_id": self._search_session_id,
                "completed_at_utc": self._utc_now(),
                "converged": converged,
                "verification": verification,
                "initial_state": self._search_initial_state,
                "search_config": config,
            })
            self._store_pending_reference(candidate)
            self._search_status = "awaiting acceptance"
            self._record_alignment_event(
                "search_completed",
                converged=converged,
                acceptance_required=True,
            )
        except SearchCancelled:
            if self._restore_on_cancel:
                try:
                    self._restore_alignment_state(self._search_initial_state, config)
                except Exception as restore_error:
                    self._search_progress = {
                        "phase": "restore_failed",
                        "message": str(restore_error),
                        "results": results,
                        "session_id": self._search_session_id,
                    }
                    self._search_status = f"restore failed: {restore_error}"
                    self._record_alignment_event(
                        "restore_failed", error=str(restore_error)
                    )
                    self.error(
                        f"Automatic laser-pointing cancellation could not restore "
                        f"its initial state: {restore_error}"
                    )
            else:
                self._search_progress = {
                    "phase": "cancelled_without_restore",
                    "results": results,
                    "session_id": self._search_session_id,
                }
                self._search_status = "cancelled"
                self._record_alignment_event("search_cancelled_without_restore")
        except LaserNotVisible as error:
            self._search_progress = {
                "phase": "laser_not_visible",
                "message": str(error),
                "results": results,
            }
            self._search_status = f"laser not visible: {error}"
            self._record_alignment_event(
                "laser_not_visible", error=str(error)
            )
            self.warn(f"Automatic laser-pointing search stopped: {error}", True)
        except Exception as error:
            self._search_progress = {
                "phase": "error",
                "message": str(error),
                "results": results,
            }
            self._search_status = f"error: {error}"
            self._record_alignment_event("search_failed", error=str(error))
            self.error(f"Automatic laser-pointing search failed: {error}")
        finally:
            self.cgc = False
            self._search_pause.clear()
            self._pause_active = False

    def _point_stages(self, config: Dict):
        sensitive_pairs = []
        for group_name, pair in self.pid_groups.items():
            if len(pair) != 2:
                raise ValueError(f"{group_name} must contain exactly two points")
            sensitive_pairs.append((group_name, tuple(pair)))

        custom_pairs = config["point_pairs"]
        if custom_pairs:
            sensitive_pairs = []
            for group_name, pair in custom_pairs.items():
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError(f"point_pairs[{group_name!r}] must have two points")
                sensitive_pairs.append((group_name, tuple(pair)))

        selected = set(config["groups"])
        if selected:
            sensitive_pairs = [item for item in sensitive_pairs if item[0] in selected]
            missing = selected.difference(name for name, _pair in sensitive_pairs)
            if missing:
                raise ValueError(f"unknown search groups: {sorted(missing)}")
        if not sensitive_pairs:
            raise ValueError("no automatic-search groups are configured")

        if custom_pairs:
            for _group_name, pair in sensitive_pairs:
                for point in pair:
                    if point not in self.controller_rules:
                        raise ValueError(f"unknown controller point {point!r}")
            return [("custom", sensitive_pairs)]

        medium_pairs = [
            (group_name, (pair[0], self._less_sensitive_point(pair[1])))
            for group_name, pair in sensitive_pairs
        ]
        for _group_name, pair in medium_pairs + sensitive_pairs:
            for point in pair:
                if point not in self.controller_rules:
                    raise ValueError(f"unknown controller point {point!r}")

        if config["mode"] == "medium":
            return [("medium", medium_pairs)]
        if config["mode"] == "staged":
            return [("medium", medium_pairs), ("sensitive", sensitive_pairs)]
        return [("sensitive", sensitive_pairs)]

    def _validate_camera_verified_roles(self, config: Dict, stages) -> None:
        """Allow a visible beam to stand in for static shutter readback.

        This exception is deliberately narrow: the explicitly named role must
        be a shutter/flipper, must occur in every point used by the run, and
        must have one identical target throughout the sequence.  It therefore
        cannot bypass a shutter transition that selects another optical path.
        """

        roles = config.get("camera_verified_roles", [])
        if not roles:
            return

        points = []
        for _stage_name, point_pairs in stages:
            for _group_name, point_pair in point_pairs:
                for point_name in point_pair:
                    if point_name not in points:
                        points.append(point_name)
        restore_point = config.get("restore_point", "")
        if restore_point and restore_point not in points:
            points.append(restore_point)

        for role in roles:
            if role not in self.ds_dict:
                raise ValueError(f"unknown camera-verified role {role!r}")
            targets = []
            for point_name in points:
                point_rule = self.controller_rules.get(point_name, {})
                if role not in point_rule:
                    raise ValueError(
                        f"camera-verified role {role!r} is missing from {point_name}"
                    )
                targets.append(point_rule[role])
            if any(target != targets[0] for target in targets[1:]):
                raise ValueError(
                    f"camera-verified role {role!r} changes target during the run"
                )

    @staticmethod
    def _less_sensitive_point(point_name: str) -> str:
        prefix = str(point_name).rstrip("0123456789")
        suffix = str(point_name)[len(prefix):]
        if not suffix:
            raise ValueError(f"cannot infer medium point from {point_name!r}")
        point_number = int(suffix)
        if point_number not in (3, 6):
            raise ValueError(
                f"medium mode expects a point ending in 3 or 6, got {point_name!r}"
            )
        return f"{prefix}{point_number - 1}"

    def _optimise_group(
        self,
        group_name: str,
        point_pair: Tuple[str, str],
        stage_name: str,
        cycle: int,
        motor_step: float,
        config: Dict,
        search_origins: Dict,
    ) -> Dict:
        actuator_roles = self._actuator_roles_for_group(group_name)
        actuator_devices = [self._device_for_role(role) for role in actuator_roles]
        start = tuple(
            self._fresh_position_and_state(device)[0]
            for device in actuator_devices
        )
        origin = search_origins.setdefault(group_name, start)
        bounds = self._search_bounds(actuator_devices, origin, config["radius"])
        parameters = SearchParameters(
            initial_step=motor_step,
            minimum_step=motor_step,
            tolerance_px=config["roundness_tolerance_pct"],
            max_evaluations=config["max_evaluations"],
            minimum_improvement_px=config["minimum_improvement_px"],
            step_schedule=(motor_step,),
            probe_repetitions=config["probe_repetitions"],
            unchanged_response_tolerance_px=config[
                "unchanged_response_tolerance_px"
            ],
        )
        last_optical_signature = ()
        best_visible_position = start
        best_visible_score = float("inf")
        baseline_centre = None
        baseline_shape = None
        target_point = point_pair[-1]

        def objective(position):
            nonlocal last_optical_signature, best_visible_position
            nonlocal best_visible_score, baseline_centre, baseline_shape
            self._raise_if_cancelled()
            previous_position = tuple(
                self._fresh_position_and_state(device)[0]
                for device in actuator_devices
            )
            move_delta = [
                float(target) - float(current)
                for target, current in zip(position, previous_position)
            ]
            last_beam_shape = getattr(self, "_search_progress", {}).get("beam_shape")
            self._search_progress = {
                "phase": "moving_actuators",
                "cycle": cycle,
                "stage": stage_name,
                "group": group_name,
                "motor_step": motor_step,
                "points": list(point_pair),
                "measured_point": target_point,
                "actuator_roles": list(actuator_roles),
                "previous_actuator_position": list(previous_position),
                "actuator_position": list(position),
                "move_delta": move_delta,
                "message": (
                    f"Adjusting {group_name}: "
                    + ", ".join(
                        f"{role} {delta:+.3f}"
                        for role, delta in zip(actuator_roles, move_delta)
                    )
                ),
            }
            if last_beam_shape:
                self._search_progress["beam_shape"] = last_beam_shape
            self._move_pair(actuator_devices, position, config)
            try:
                test = self._measure_point(target_point, config)
                test_shape = self._read_beam_shape()
            except LaserNotVisible as error:
                # The baseline must be visible, but a directional probe is
                # allowed to leave the usable camera/beam path. Score that
                # candidate as rejected, restore the last measured-good
                # position, and let the bounded search try another direction.
                if baseline_centre is None:
                    raise
                last_optical_signature = (
                    1.0e9,
                    *tuple(float(value) for value in position),
                )
                elapsed_s = (
                    monotonic() - self._search_started_at
                    if self._search_started_at is not None
                    else 0.0
                )
                observation = {
                    "index": len(self._search_history) + 1,
                    "elapsed_s": elapsed_s,
                    "group": group_name,
                    "stage": stage_name,
                    "motor_step": motor_step,
                    "points": list(point_pair),
                    "measured_point": target_point,
                    "actuator_position": list(position),
                    "roundness_error_pct": 100.0,
                    "score_metric": "contour_symmetry_error_pct",
                    "error_px": 100.0,
                    "message": f"Rejected invisible probe: {error}",
                }
                self._search_history.append(observation)
                self._search_progress = {
                    **observation,
                    "phase": "probe_rejected",
                    "observation_index": observation["index"],
                }
                if tuple(position) != best_visible_position:
                    self._move_pair(
                        actuator_devices, best_visible_position, config
                    )
                return 100.0
            if baseline_centre is None:
                baseline_centre = test
                baseline_shape = test_shape
            reference = baseline_centre
            reference_shape = baseline_shape
            delta_x = reference[0] - test[0]
            delta_y = reference[1] - test[1]
            # Each threshold's border is fitted independently. A good beam
            # has circular borders with coincident centres at all heights.
            # Absolute camera position and baseline displacement are only
            # diagnostics, never part of the actuator objective.
            score = test_shape["roundness_error_pct"]
            self.previos_pos = {"X": reference[0], "Y": reference[1]}
            self.current_pos = {"X": test[0], "Y": test[1]}
            self.deltas = [delta_x, delta_y]
            last_optical_signature = (
                test[0],
                test[1],
                test_shape["roundness_pct"],
                test_shape.get("contour_centre_drift_px", 0.0),
            )
            improved = (
                score < best_visible_score - config["minimum_improvement_px"]
            )
            if improved:
                best_visible_score = score
                best_visible_position = tuple(position)
            self._search_progress = {
                "phase": "measuring",
                "cycle": cycle,
                "stage": stage_name,
                "group": group_name,
                "motor_step": motor_step,
                "points": list(point_pair),
                "measured_point": target_point,
                "actuator_position": list(position),
                "reference_centroid": list(reference),
                "test_centroid": list(test),
                "delta_px": [delta_x, delta_y],
                "reference_roundness_pct": reference_shape["roundness_pct"],
                "test_roundness_pct": test_shape["roundness_pct"],
                "roundness_error_pct": score,
                "beam_shape": test_shape,
                "score_metric": "contour_symmetry_error_pct",
                # Compatibility for older clients; this value is a percent,
                # not a centroid distance.
                "error_px": score,
            }
            group_index = list(self.pid_groups).index(group_name) + 1
            elapsed_s = (
                monotonic() - self._search_started_at
                if self._search_started_at is not None
                else 0.0
            )
            observation = {
                "index": len(self._search_history) + 1,
                "elapsed_s": elapsed_s,
                "diaphragm": group_index,
                "actuator_group": group_index,
                "group": group_name,
                "stage": stage_name,
                "motor_step": motor_step,
                "points": list(point_pair),
                "measured_point": target_point,
                "actuator_position": list(position),
                "delta_px": [delta_x, delta_y],
                "reference_roundness_pct": reference_shape["roundness_pct"],
                "test_roundness_pct": test_shape["roundness_pct"],
                "roundness_error_pct": score,
                "score_metric": "contour_symmetry_error_pct",
                "error_px": score,
            }
            self._search_history.append(observation)
            self._search_progress["observation_index"] = observation["index"]
            if not improved and tuple(position) != best_visible_position:
                # Return every rejected probe to the last measured-good
                # actuator position before trying another direction.
                self._raise_if_cancelled()
                self._move_pair(actuator_devices, best_visible_position, config)
            return score

        try:
            result = bounded_pattern_search(
                objective,
                start=start,
                bounds=bounds,
                parameters=parameters,
                cancelled=self._search_stop.is_set,
                response_signature=lambda: last_optical_signature,
            )
        except SearchCancelled:
            # Stop means stop: do not issue a rollback movement after the user
            # has cancelled the search.
            raise
        except Exception as search_error:
            # A probe can move the spot outside the usable optical path. Never
            # leave the mount at that failed candidate: return to the best
            # position for which both point centroids and the beam shape were
            # actually visible.
            try:
                self._move_pair(actuator_devices, best_visible_position, config)
            except Exception as restore_error:
                raise RuntimeError(
                    f"automatic probe failed ({search_error}); could not restore "
                    f"last visible position {best_visible_position}: {restore_error}"
                ) from search_error
            raise
        if result.reason == "cancelled":
            raise SearchCancelled()

        retained_position = tuple(result.best_position)
        retained_score = float(result.best_score)
        stage_bests = getattr(self, "_search_stage_bests", None)
        if stage_bests is not None:
            best_key = (stage_name, group_name)
            previous_best = stage_bests.get(best_key)
            if previous_best is None or retained_score < previous_best["score"]:
                stage_bests[best_key] = {
                    "position": retained_position,
                    "score": retained_score,
                }
            else:
                retained_position = tuple(previous_best["position"])
                retained_score = float(previous_best["score"])
        self._move_pair(actuator_devices, retained_position, config)

        return {
            "cycle": cycle,
            "stage": stage_name,
            "group": group_name,
            "motor_step": motor_step,
            "points": list(point_pair),
            "start_position": list(start),
            "search_origin": list(origin),
            "best_position": list(retained_position),
            "best_roundness_error_pct": retained_score,
            "best_error_px": retained_score,
            "evaluations": result.evaluations,
            "reason": result.reason,
        }

    def _actuator_roles_for_group(self, group_name: str) -> Tuple[str, str]:
        group_names = list(self.pid_groups)
        if group_name not in group_names:
            raise ValueError(f"unknown PID group {group_name!r}")
        actuator_groups = [
            roles
            for name, roles in self.groups.items()
            if str(name).lower().startswith("actuators")
        ]
        index = group_names.index(group_name)
        if index >= len(actuator_groups):
            raise ValueError(f"no actuator group corresponds to {group_name!r}")
        roles = actuator_groups[index]
        if isinstance(roles, str) or len(roles) != 2:
            raise ValueError(f"actuator group for {group_name!r} must contain X and Y")
        return tuple(roles)

    def _actuator_group_entry(self, group_index: int) -> Tuple[str, Tuple[str, str]]:
        actuator_groups = [
            (str(name), roles)
            for name, roles in self.groups.items()
            if str(name).lower().startswith("actuators")
        ]
        if group_index < 1 or group_index > len(actuator_groups):
            raise ValueError(f"actuator group {group_index} is not configured")
        group_name, roles = actuator_groups[group_index - 1]
        if isinstance(roles, str) or len(roles) != 2:
            raise ValueError(f"{group_name} must contain X and Y actuator roles")
        return group_name, tuple(roles)

    def _device_for_role(self, role: str):
        device_name = self.ds_dict[role]
        if isinstance(device_name, tuple):
            device_name = device_name[0]
        if device_name not in self.devices:
            self.devices[device_name] = Device(device_name)
        return self.devices[device_name]

    @staticmethod
    def _actuator_lifecycle(device) -> Dict:
        def value(name, default=""):
            try:
                proxy = device.getDeviceProxy()
                return str(proxy.read_attribute(name).value).strip().upper()
            except Exception:
                try:
                    return str(getattr(device, name)).strip().upper()
                except Exception:
                    return default

        try:
            state = str(device.getDeviceProxy().state()).strip().upper()
        except Exception:
            state = value("state", "UNKNOWN")
        state_name = state.rsplit(".", 1)[-1]
        connection = value("hardware_connection_state")
        initialization = value("initialization_state")
        detail = value("hardware_lifecycle_status")
        disconnected = connection in {
            "DISCONNECTED",
            "POWER_OFF",
            "POWER_STATUS_UNAVAILABLE",
        } or state_name in {"FAULT", "OFF", "UNKNOWN", "UNREACHABLE"}
        ready = not disconnected and (
            initialization == "SUCCEEDED"
            or connection == "READY"
            or state_name in {"ON", "MOVING", "RUNNING"}
        )
        return {
            "state": state,
            "connection": connection,
            "initialization": initialization,
            "detail": detail,
            "ready": ready,
        }

    @staticmethod
    def _search_bounds(devices, start: Sequence[float], radius: float):
        bounds = []
        for device, centre in zip(devices, start):
            lower = centre - radius
            upper = centre + radius
            try:
                important = list(device.important_parameters)
                lower = max(lower, float(important[0]))
                upper = min(upper, float(important[1]))
            except Exception:
                pass
            if lower > upper:
                raise ValueError("current actuator position is outside its limits")
            bounds.append((lower, upper))
        return bounds

    @staticmethod
    def _command_error(result):
        if result is None:
            return ""
        if isinstance(result, bool):
            return "" if result else "command returned False"
        if isinstance(result, (int, float)):
            return "" if float(result) == 0.0 else str(result)
        text = str(result).strip()
        return "" if text in ("", "0", "0.0") else text

    @staticmethod
    def _is_command_timeout(error) -> bool:
        normalized = str(error).lower().replace("_", "")
        return "timeout" in normalized or "timedout" in normalized

    def _move_pair(self, devices, positions, config):
        errors = []

        def move(device, position):
            try:
                self._move_single_axis(device, float(position), config)
            except Exception as error:
                errors.append(str(error))

        threads = [
            Thread(target=move, args=(device, position), daemon=True)
            for device, position in zip(devices, positions)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors:
            raise RuntimeError("actuator movement failed: " + "; ".join(errors))

    def _move_single_axis(self, device, target: float, config):
        command_timed_out = False
        try:
            result = device.move_axis_abs(float(target))
        except Exception as error:
            # Standa commands block until the physical move and final hardware
            # readback complete. A move longer than the Tango client's short
            # request timeout can therefore keep running successfully on the
            # server. Treat only that timeout as an unknown result and prove
            # completion from direct position/state reads below.
            if not self._is_command_timeout(error):
                raise
            command_timed_out = True
        else:
            command_error = self._command_error(result)
            if command_error:
                raise RuntimeError(command_error)

        # DS_Standa_Motor.move_axis_abs blocks on command_wait_for_stop and then
        # performs a hardware get_position read. Verify the published result as
        # well, allowing for the configured motor conversion/rounding.
        deadline = monotonic() + config["motion_timeout_s"]
        last_actual = None
        while monotonic() < deadline:
            self._raise_if_cancelled()
            try:
                last_actual, state = self._fresh_position_and_state(device)
            except Exception as error:
                if command_timed_out and self._is_command_timeout(error):
                    self._interruptible_sleep(config["motion_poll_s"])
                    continue
                raise RuntimeError(f"could not read motor position/state: {error}")
            if (
                abs(last_actual - target) <= config["position_tolerance"]
                and "MOVING" not in state
            ):
                return
            # Mono-axis move_axis_abs returns only after the child command has
            # stopped.  Waiting for the full automatic-search timeout after a
            # stopped readback mismatch hides the real failure and blocks the
            # controller's Tango monitor for minutes.
            if "MOVING" not in state:
                raise RuntimeError(
                    f"motor stopped at {last_actual}, expected {target}"
                )
            self._interruptible_sleep(config["motion_poll_s"])
        raise RuntimeError(
            f"motor did not reach {target} within {config['motion_timeout_s']} s; "
            f"last readback was {last_actual}"
        )

    @staticmethod
    def _fresh_position_and_state(device) -> Tuple[float, str]:
        """Read hardware-backed values instead of Taurus' polling cache."""

        try:
            proxy = device.getDeviceProxy()
        except AttributeError:
            return float(device.position), str(device.state).upper()

        original_source = proxy.get_source()
        direct_source = getattr(type(original_source), "DEV", None)
        if direct_source is None:
            raise RuntimeError("device proxy does not expose a direct-read source")
        try:
            proxy.set_source(direct_source)
            position = float(proxy.read_attribute("position").value)
            state = str(proxy.state()).upper()
        finally:
            proxy.set_source(original_source)
        return position, state

    def _move_multi_axis(self, device, value, config):
        axis = int(value[0])
        target = float(value[1])
        # Multi-axis OWIS servers expose move_axis as a DevVarDoubleArray.
        # The historical move_axis_abs alias used to be declared as a scalar
        # command and could not transport [axis, target] through Tango.
        try:
            result = device.move_axis([float(axis), target])
        except Exception as error:
            # A Tango request timeout is an unknown command result: the OWIS
            # server can keep executing the accepted move. Prove completion
            # from subsequent position/state reads instead of issuing the
            # command a second time while the stage may already be moving.
            if not self._is_command_timeout(error):
                raise
        else:
            command_error = self._command_error(result)
            if command_error:
                raise RuntimeError(command_error)

        deadline = monotonic() + config["motion_timeout_s"]
        stable = 0
        last_actual = None
        last_read_error = ""
        while monotonic() < deadline:
            self._raise_if_cancelled()
            try:
                state = device.get_status_axis(axis)
                last_actual = float(device.read_position_axis(axis))
            except Exception as error:
                # The OWIS aggregator may be serialization-busy for longer
                # than the client's 3 s timeout while a long axis move is in
                # progress. Retry only timeouts; other errors remain fatal.
                if self._is_command_timeout(error):
                    last_read_error = str(error)
                    self._interruptible_sleep(config["motion_poll_s"])
                    continue
                raise RuntimeError(
                    f"could not read OWIS axis {axis} position/state: {error}"
                )
            moving = self._state_is_moving(state)
            if (
                not moving
                and abs(last_actual - target) <= config["position_tolerance"]
            ):
                stable += 1
                if stable >= config["position_stable_reads"]:
                    return
            else:
                stable = 0
            self._interruptible_sleep(config["motion_poll_s"])
        raise RuntimeError(
            f"OWIS axis {axis} did not reach {target} within "
            f"{config['motion_timeout_s']} s; last readback was {last_actual}; "
            f"last transient read error was {last_read_error or 'none'}"
        )

    @staticmethod
    def _state_is_moving(state) -> bool:
        try:
            return int(state) == int(DevState.MOVING)
        except (TypeError, ValueError):
            return "MOVING" in str(state).upper()

    @staticmethod
    def _is_flipper_role(role) -> bool:
        normalized_role = str(role).lower()
        return "shutter" in normalized_role or "flipper" in normalized_role

    @staticmethod
    def _fresh_flipper_command_state(device):
        try:
            proxy = device.getDeviceProxy()
        except AttributeError:
            return str(device.commanded_flipper_state).strip().upper()
        original_source = proxy.get_source()
        direct_source = getattr(type(original_source), "DEV", None)
        try:
            if direct_source is not None:
                proxy.set_source(direct_source)
            return str(
                proxy.read_attribute("commanded_flipper_state").value
            ).strip().upper()
        finally:
            if direct_source is not None:
                proxy.set_source(original_source)

    def _command_route_flippers(self, point_name):
        point_rule = self.controller_rules.get(point_name, {})
        device_map = getattr(self, "ds_dict", None) or {}
        targets = [
            (role, float(target))
            for role, target in point_rule.items()
            if self._is_flipper_role(role) and role in device_map
        ]
        for role, target in targets:
            expected = "UP_BLOCKED" if target == -1.0 else "DOWN_CLEAR"
            self._raise_if_cancelled()
            device = self._device_for_role(role)
            try:
                if self._fresh_flipper_command_state(device) == expected:
                    continue
                result = device.move_axis_abs(target)
                error = self._command_error(result)
                if error:
                    raise RuntimeError(error)
                actual = self._fresh_flipper_command_state(device)
                if actual != expected:
                    raise RuntimeError(
                        f"commanded state is {actual}, expected {expected}"
                    )
            except Exception as error:
                raise RuntimeError(
                    f"could not apply controller point {point_name}: {role}: {error}"
                ) from error

    def _apply_point(self, point_name: str, config: Dict):
        self._raise_if_cancelled()
        # Route the selected camera before changing apertures or propagation
        # plane. Each controller's registered rules specify the exact flipper
        # combination; the topology cannot be derived from point number.
        self._command_route_flippers(point_name)
        # Optical presets commonly contain several Standa-backed devices on
        # the same host. Apply them deterministically so their Tango/libximc
        # transactions cannot contend and leave a partial preset behind.
        targets = [
            (role, value)
            for role, value in self.controller_rules[point_name].items()
            if not self._is_flipper_role(role)
        ]
        working_point = str(point_name).strip().lower() == "working"
        if working_point:
            # Working is the safe open-beam preset. Enforce 100% for every
            # configured diaphragm even if an older database rule is stale or
            # omits one. Put diaphragms first so a later wave-plate or
            # delay-line failure cannot leave an aperture closed.
            configured_roles = list(getattr(self, "ds_dict", {}))
            diaphragm_roles = []
            for role in configured_roles + [role for role, _value in targets]:
                if "diaphragm" in str(role).lower() and role not in diaphragm_roles:
                    diaphragm_roles.append(role)
            targets = (
                [(role, 100.0) for role in diaphragm_roles]
                + [
                    (role, value)
                    for role, value in targets
                    if "diaphragm" not in str(role).lower()
                ]
            )
        # Set apertures first, then the translation plane. The flipper is
        # handled separately because its numeric position always reads zero.
        def target_priority(item):
            normalized_role = str(item[0]).lower()
            if "diaphragm" in normalized_role:
                return 0
            if "translation" in normalized_role:
                return 1
            return 2

        targets.sort(key=target_priority)

        deferred_errors = []
        for role, value in targets:
            self._raise_if_cancelled()
            if getattr(self, "cgc", False):
                self._search_progress.update({
                    "phase": "applying_point",
                    "point": point_name,
                    "optical_role": role,
                    "optical_target": value,
                    "message": f"Moving optics to {point_name}: {role} -> {value}",
                })
            if (
                config.get("_camera_verified_roles_validated")
                and role in config.get("camera_verified_roles", [])
            ):
                self.info(
                    f"Keeping {role} in its current position for {point_name}; "
                    "the automatic measurement will verify the Basler centroid "
                    "after the complete optical preset is applied."
                )
                continue
            device = self._device_for_role(role)
            try:
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    self._move_multi_axis(device, value, config)
                else:
                    move_config = config
                    numeric_value = float(value)
                    if (
                        "diaphragm" in str(role).lower()
                        and numeric_value == 100.0
                    ):
                        # The percentage diaphragms mechanically stop just
                        # below the nominal 100% coordinate (typically
                        # 99.0-99.1%). Treat that readback as fully open while
                        # retaining the tight tolerance for every other point.
                        move_config = dict(config)
                        move_config["position_tolerance"] = max(
                            float(config.get("position_tolerance", 0.05)), 1.0
                        )
                    self._move_single_axis(device, numeric_value, move_config)
            except Exception as error:
                normalized_role = str(role).lower()
                if "diaphragm" in normalized_role:
                    deferred_errors.append(f"{role}: {error}")
                    continue
                raise RuntimeError(
                    f"could not apply controller point {point_name}: {role}: {error}"
                ) from error
        if deferred_errors:
            raise RuntimeError(
                f"could not fully apply {point_name} after attempting all diaphragms: "
                + "; ".join(deferred_errors)
            )
        # Publish the point only after every child has reached its readback.
        # Both clients use this as the source of truth for the mount interlock.
        self._publish_active_point(point_name)

    def _publish_active_point(self, point_name: str):
        self._active_point = point_name
        group_index = optical_point_group(point_name)
        self._actuator_initialization_status = {
            "phase": "ready_to_initialize" if group_index else "idle",
            "group": group_index,
            "message": (
                f"Point selected; initialise Standa pair {group_index}"
                if group_index
                else "Select a numbered optical point before initialising a pair"
            ),
        }

    @staticmethod
    def _fresh_camera_values(camera, *attribute_names):
        """Read camera attributes directly, bypassing the Taurus polling cache."""

        try:
            proxy = camera.getDeviceProxy()
        except AttributeError:
            return {
                attribute_name: getattr(camera, attribute_name)
                for attribute_name in attribute_names
            }
        original_source = proxy.get_source()
        direct_source = getattr(type(original_source), "DEV", None)
        if direct_source is None:
            raise RuntimeError("camera proxy does not expose a direct-read source")
        try:
            proxy.set_source(direct_source)
            return {
                attribute_name: proxy.read_attribute(attribute_name).value
                for attribute_name in attribute_names
            }
        finally:
            proxy.set_source(original_source)

    @staticmethod
    def _fresh_camera_image(camera):
        """Take a direct image snapshot, bypassing any Taurus polling cache."""

        value = DS_LaserPointing._fresh_camera_values(camera, "image")["image"]
        return np.array(value, copy=True)

    def _read_beam_shape(self):
        """Return the contour score calculated for the latest point sample."""

        shape = getattr(self, "_last_beam_shape", None)
        if shape is None:
            raise LaserNotVisible("no recent beam-contour measurement is available")
        return shape

    def _measure_point(self, point_name: str, config: Dict):
        if getattr(self, "_active_point", None) != point_name:
            if getattr(self, "cgc", False):
                self._search_progress.update({
                    "phase": "applying_point",
                    "point": point_name,
                    "message": f"Moving optics to {point_name}",
                })
            self._apply_point(point_name, config)
        # Motion completion is readback-driven. This short wait only ensures
        # Basler has published a frame acquired after the final movement.
        self._interruptible_sleep(config["camera_frame_wait_s"])
        camera = self.devices[self.ds_dict["Camera"]]
        self._last_beam_shape = None
        profile = self._fresh_camera_values(
            camera,
            "center_gravity_threshold",
            "width",
            "height",
        )
        profile_arguments = {
            "threshold": float(profile["center_gravity_threshold"]),
            "width": int(profile["width"]),
            "height": int(profile["height"]),
        }
        frames = []
        for sample_index in range(config["samples"]):
            if getattr(self, "cgc", False):
                self._search_progress.update({
                    "phase": "capturing_profiles",
                    "point": point_name,
                    "sample": sample_index + 1,
                    "samples": config["samples"],
                    "message": (
                        f"Capturing beam profile at {point_name}: "
                        f"frame {sample_index + 1}/{config['samples']}"
                    ),
                })
            retries_remaining = config["invalid_frame_retries"]
            while True:
                self._raise_if_cancelled()
                try:
                    acquisition = self._fresh_camera_values(
                        camera, "isgrabbing"
                    )
                    if not bool(acquisition["isgrabbing"]):
                        raise ValueError("camera acquisition is stopped")
                    frame = self._fresh_camera_image(camera)
                    if frame.size == 0 or frame.ndim < 2:
                        raise ValueError("camera returned an empty frame")
                    # A valid camera transfer can still contain no usable
                    # beam after an optical or actuator move. Do not let that
                    # frame poison the median profile; consume the existing
                    # invalid-frame retry budget and wait for another frame.
                    beam_contour_symmetry([frame], **profile_arguments)
                    frames.append(frame)
                    break
                except Exception as error:
                    if retries_remaining <= 0:
                        raise LaserNotVisible(
                            f"Basler frame is unavailable at {point_name}: {error}"
                        ) from error
                    retries_remaining -= 1
                    self._interruptible_sleep(max(
                        config["camera_frame_wait_s"],
                        config["sample_interval_s"],
                    ))
            if sample_index + 1 < config["samples"]:
                self._interruptible_sleep(config["sample_interval_s"])
        profile_diagnostics = {}
        try:
            if getattr(self, "cgc", False):
                self._search_progress.update({
                    "phase": "calculating_profiles",
                    "point": point_name,
                    "message": (
                        f"Calculating nine iso-intensity profiles at {point_name}"
                    ),
                })
            profile_diagnostics = {
                **profile_arguments,
                "frame_shapes": [list(np.asarray(frame).shape) for frame in frames],
                "frame_peaks": [float(np.max(frame)) for frame in frames],
            }
            shape = beam_contour_symmetry(
                frames,
                include_preview=True,
                **profile_arguments,
            )
        except Exception as error:
            raise LaserNotVisible(
                f"Basler beam contours are invalid at {point_name}: {error}; "
                f"profile input={profile_diagnostics}"
            ) from error
        self._last_beam_shape = shape
        return tuple(shape["shape_centroid"])

    def _interruptible_sleep(self, duration: float):
        if duration > 0 and self._search_stop.wait(duration):
            raise SearchCancelled()
        self._raise_if_cancelled()

    def _wait_if_paused(self):
        pause = getattr(self, "_search_pause", None)
        if pause is None or not pause.is_set():
            return
        if not getattr(self, "_pause_active", False):
            self._pause_active = True
            self._progress_before_pause = dict(self._search_progress)
            self._search_status = "paused"
            self._search_progress = {
                "phase": "paused",
                "session_id": self._search_session_id,
                "resume_phase": self._progress_before_pause.get("phase", ""),
                "message": (
                    "Paused at a safe checkpoint; Continue resumes this same search"
                ),
            }
            self._record_alignment_event(
                "paused",
                resume_phase=self._progress_before_pause.get("phase", ""),
            )
        while pause.is_set():
            if self._search_stop.wait(0.2):
                raise SearchCancelled()
        if self._search_stop.is_set():
            raise SearchCancelled()
        self._search_status = "running"
        self._search_progress = {
            **self._progress_before_pause,
            "resumed_at_utc": self._utc_now(),
        }
        self._pause_active = False
        self._record_alignment_event("resumed")

    def _raise_if_cancelled(self):
        if self._search_stop.is_set():
            raise SearchCancelled()
        self._wait_if_paused()
        if self._search_stop.is_set():
            raise SearchCancelled()

    def execute_action(self, action: float, device: Device, relative=False, threaded=False):
        """Compatibility helper retained for external scripts."""
        if threaded:
            Thread(
                target=self.execute_action,
                args=(action, device, relative, False),
                daemon=True,
            ).start()
        elif relative:
            device.move_axis_rel(action)
        else:
            device.move_axis_abs(action)

    def stop_opts(self):
        self.stop_automatic_search()


if __name__ == "__main__":
    DS_LaserPointing.run_server()
