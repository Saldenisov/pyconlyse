from sys import modules as _refactor_modules

import json
import hashlib
import sys
from datetime import datetime, timezone
from math import hypot as hypot
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from typing import Dict, Optional, Sequence, Tuple, Union
from uuid import uuid4
from collections import deque

import numpy as np
from tango import AttrWriteType, Database, DevState, DispLevel
from tango.server import attribute, command, device_property
from taurus import Device

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from DeviceServers.control.laser_pointing.laser_pointing_methods_find_device import _bind_laser_pointing_methods_find_device
from DeviceServers.control.laser_pointing.laser_pointing_methods_store_pending_reference import _bind_laser_pointing_methods_store_pending_reference
from DeviceServers.control.laser_pointing.laser_pointing_methods_adaptive_direction_order import _bind_laser_pointing_methods_adaptive_direction_order
from DeviceServers.control.laser_pointing.laser_pointing_methods_optimise_group import _bind_laser_pointing_methods_optimise_group
from DeviceServers.control.laser_pointing.laser_pointing_methods_normalise_working_rule import _bind_laser_pointing_methods_normalise_working_rule

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
    from DeviceServers.control.laser_pointing.beam_metrics import (
        beam_contour_symmetry,
        camera_contour_profile,
    )
    from DeviceServers.control.laser_pointing.alignment_quality import (
        centering_verification, finite_nonnegative,
    )
    from DeviceServers.control.laser_pointing.confirmed_search import (
        confirmed_centering_search, CenteringSearchCancelled,
    )
except ModuleNotFoundError:
    from automatic_search import (
        SearchParameters,
        bounded_pattern_search,
        optical_point_group,
    )
    from beam_metrics import beam_contour_symmetry, camera_contour_profile
    from DeviceServers.control.laser_pointing.alignment_quality import centering_verification, finite_nonnegative
    from DeviceServers.control.laser_pointing.confirmed_search import confirmed_centering_search, CenteringSearchCancelled


DEFAULT_SEARCH_CONFIG = {
    # Staged, explicit opt-in: existing deployed defaults remain unchanged.
    "alignment_objective": "roundness",
    "centering_tolerance_px": 1.0,
    "centering_minimum_improvement_px": 0.1,
    "measurement_repetitions": 3,
    "confirmation_noise_multiplier": 2.0,
    "ellipticity_tolerance_pct": 7.0,
    "centering_check_aperture_pair": True,
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
    "adaptive_learning": True,
    "adaptive_min_step": 0.125,
    "adaptive_backoff": 0.5,
    "adaptive_growth": 1.15,
    "point_step_limits": {},
    "point_probe_repetitions": {},
    "aperture_sweep_enabled": True,
    "aperture_sweep_positions": 4,
    "aperture_cycle_count": 2,
    "aperture_samples": 1,
    "aperture_drift_weight": 0.5,
    "group_plateau_probe_limit": 5,
    "group_plateau_min_improvement_pct": 5.0,
    "stagnation_pass_limit": 5,
    "stagnation_min_improvement_pct": 5.0,
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
        "cancel_automatic_search": [DevState.ON],
        "accept_alignment_reference": [DevState.ON],
        "save_current_alignment_reference": [DevState.ON],
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
    adaptive_search_model_property = device_property(dtype=str, default_value="{}")

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
        # Numbered points retain their camera-routing flipper states. Working
        # is different: it is the open-beam operating state, so every
        # configured diaphragm is open and every configured shutter is down.
        self._normalise_working_rule()
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
        self._adaptive_search_model = self._json_object(
            self.adaptive_search_model_property
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

    _laser_pointing_methods_find_device = _bind_laser_pointing_methods_find_device(_refactor_modules[__name__])
    find_device = _laser_pointing_methods_find_device["find_device"]

    def get_controller_status_local(self) -> Union[int, str]:
        return super().get_controller_status_local()

    turn_on_local = _laser_pointing_methods_find_device["turn_on_local"]

    turn_off_local = _laser_pointing_methods_find_device["turn_off_local"]

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

    write_automatic_search_config = _laser_pointing_methods_find_device["write_automatic_search_config"]

    @attribute(
        label="Learned automatic-search response model",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def adaptive_search_model_json(self):
        return json.dumps(
            getattr(self, "_adaptive_search_model", {}), sort_keys=True
        )

    start_automatic_search = (command(
        dtype_in=str,
        dtype_out=int,
        doc_in="Optional JSON object overriding automatic-search configuration.",
    ))(_laser_pointing_methods_find_device["start_automatic_search"])

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

    @command(dtype_out=int)
    def cancel_automatic_search(self):
        """Stop optimisation while retaining its latest measured-good state."""

        if self._search_status in (
            "cancelling",
            "restoring",
            "cancelling; keeping current",
        ):
            return -1
        self._restore_on_cancel = False
        if self._alignment_pending_reference:
            retained_point = str(
                self._alignment_pending_reference.get("active_point", "")
            )
            self._clear_pending_reference()
            if retained_point in self.controller_rules:
                self._active_point = retained_point
                self._actuator_initialization_status = {
                    "phase": "manual_point_selected",
                    "group": optical_point_group(retained_point),
                    "point": retained_point,
                    "message": (
                        f"Kept {retained_point} after cancelling without restore"
                    ),
                }
            self._search_status = "cancelled; current alignment kept"
            self._search_progress = {
                **self._search_progress,
                "phase": "cancelled_keep_current",
                "session_id": self._search_session_id,
                "message": (
                    "Stopped without restoring; current alignment is kept"
                ),
            }
            self._record_alignment_event(
                "completed_alignment_kept_without_reference"
            )
            return 0
        if not self._search_is_running():
            return -1
        self._search_stop.set()
        self._search_pause.clear()
        self.cgc = False
        self._search_status = "cancelling; keeping current"
        self._search_progress = {
            **self._search_progress,
            "phase": "cancelling_keep_current",
            "message": (
                "Stopping at the latest measured-good alignment; no restore"
            ),
        }
        self._record_alignment_event("cancel_keep_current_requested")
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
        details = {}
        if str(metadata).strip():
            details = json.loads(str(metadata))
            if not isinstance(details, dict):
                raise ValueError("acceptance metadata must be a JSON object")
        return self._accept_pending_alignment_reference(details)

    @command(
        dtype_in=str,
        dtype_out=int,
        doc_in="Optional JSON metadata for a manually aligned reference.",
    )
    def save_current_alignment_reference(self, metadata=""):
        """Save the current manual alignment without requiring an auto run."""

        if self._search_is_running():
            raise RuntimeError("wait for automatic alignment to finish")
        if self._point_application_is_running():
            raise RuntimeError("wait for the optical point to finish applying")
        if self._alignment_pending_reference:
            raise RuntimeError(
                "accept or cancel the pending automatic result first"
            )
        details = {}
        if str(metadata).strip():
            details = json.loads(str(metadata))
            if not isinstance(details, dict):
                raise ValueError("reference metadata must be a JSON object")
        self._search_session_id = str(uuid4())
        candidate = self._capture_alignment_state()
        candidate.update({
            "session_id": self._search_session_id,
            "completed_at_utc": self._utc_now(),
            "source": "manual",
            "manual_reference": True,
            "converged": None,
            "verification": [],
            "search_config": dict(self._search_config),
        })
        self._search_progress = {
            "phase": "saving_manual_reference",
            "session_id": self._search_session_id,
            "message": "Saving current manual alignment as next-day reference",
        }
        return self._persist_alignment_reference(candidate, {
            **details,
            "manual": True,
        })

    _accept_pending_alignment_reference = _laser_pointing_methods_find_device["_accept_pending_alignment_reference"]

    _persist_alignment_reference = _laser_pointing_methods_find_device["_persist_alignment_reference"]

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

    _point_application_worker = _laser_pointing_methods_find_device["_point_application_worker"]

    initialize_active_pair = (command(dtype_out=int))(_laser_pointing_methods_find_device["initialize_active_pair"])

    move_active_actuator = (command(
        dtype_in=str,
        dtype_out=int,
        doc_in='JSON object with an actuator "role" and absolute "target".',
    ))(_laser_pointing_methods_find_device["move_active_actuator"])

    # Backward compatibility for existing clients and scripts.
    @command(dtype_in=str, dtype_out=int)
    def start_cgc(self, client_token=""):
        configuration = client_token if str(client_token).lstrip().startswith("{") else ""
        return self.start_automatic_search(configuration)

    @command(dtype_in=str, dtype_out=int)
    def stop_cgc(self, client_token=""):
        return self.stop_automatic_search()

    _search_is_running = _laser_pointing_methods_find_device["_search_is_running"]

    _point_application_is_running = _laser_pointing_methods_find_device["_point_application_is_running"]

    _utc_now = (staticmethod)(_laser_pointing_methods_find_device["_utc_now"])

    _json_object = (staticmethod)(_laser_pointing_methods_find_device["_json_object"])

    _string_list = (staticmethod)(_laser_pointing_methods_find_device["_string_list"])

    _configure_alignment_events = _laser_pointing_methods_find_device["_configure_alignment_events"]

    _push_alignment_value = _laser_pointing_methods_find_device["_push_alignment_value"]

    _persist_alignment_properties = _laser_pointing_methods_find_device["_persist_alignment_properties"]

    _record_alignment_event = _laser_pointing_methods_find_device["_record_alignment_event"]

    _alignment_role_specs = _laser_pointing_methods_find_device["_alignment_role_specs"]

    _capture_alignment_state = _laser_pointing_methods_find_device["_capture_alignment_state"]

    _alignment_state_mismatches = _laser_pointing_methods_find_device["_alignment_state_mismatches"]

    _restore_alignment_state = _laser_pointing_methods_find_device["_restore_alignment_state"]
    del _laser_pointing_methods_find_device

    _laser_pointing_methods_store_pending_reference = _bind_laser_pointing_methods_store_pending_reference(_refactor_modules[__name__])
    _store_pending_reference = _laser_pointing_methods_store_pending_reference["_store_pending_reference"]

    _clear_pending_reference = _laser_pointing_methods_store_pending_reference["_clear_pending_reference"]

    _restore_completed_alignment_worker = _laser_pointing_methods_store_pending_reference["_restore_completed_alignment_worker"]

    _alignment_acceptance_is_pending = _laser_pointing_methods_store_pending_reference["_alignment_acceptance_is_pending"]

    _normalise_search_config = (staticmethod)(_laser_pointing_methods_store_pending_reference["_normalise_search_config"])

    _automatic_search_worker = _laser_pointing_methods_store_pending_reference["_automatic_search_worker"]

    _point_stages = _laser_pointing_methods_store_pending_reference["_point_stages"]

    _validate_camera_verified_roles = _laser_pointing_methods_store_pending_reference["_validate_camera_verified_roles"]

    _less_sensitive_point = (staticmethod)(_laser_pointing_methods_store_pending_reference["_less_sensitive_point"])

    _adaptive_model_key = _laser_pointing_methods_store_pending_reference["_adaptive_model_key"]

    _hardware_probe_step_limit = _laser_pointing_methods_store_pending_reference["_hardware_probe_step_limit"]

    _adaptive_step_limit = _laser_pointing_methods_store_pending_reference["_adaptive_step_limit"]

    _adaptive_probe_repetitions = _laser_pointing_methods_store_pending_reference["_adaptive_probe_repetitions"]
    del _laser_pointing_methods_store_pending_reference

    _laser_pointing_methods_adaptive_direction_order = _bind_laser_pointing_methods_adaptive_direction_order(_refactor_modules[__name__])
    _adaptive_direction_order = _laser_pointing_methods_adaptive_direction_order["_adaptive_direction_order"]

    _update_running_mean = (staticmethod)(_laser_pointing_methods_adaptive_direction_order["_update_running_mean"])

    _persist_adaptive_search_model = _laser_pointing_methods_adaptive_direction_order["_persist_adaptive_search_model"]

    _learn_from_probe = _laser_pointing_methods_adaptive_direction_order["_learn_from_probe"]

    _aperture_sweep_spec = _laser_pointing_methods_adaptive_direction_order["_aperture_sweep_spec"]

    _measure_aperture_cycle = _laser_pointing_methods_adaptive_direction_order["_measure_aperture_cycle"]

    _verify_centering_pair = _laser_pointing_methods_adaptive_direction_order["_verify_centering_pair"]

    _optimise_centering_group = _laser_pointing_methods_adaptive_direction_order["_optimise_centering_group"]
    del _laser_pointing_methods_adaptive_direction_order

    _laser_pointing_methods_optimise_group = _bind_laser_pointing_methods_optimise_group(_refactor_modules[__name__])
    _optimise_group = _laser_pointing_methods_optimise_group["_optimise_group"]

    _actuator_roles_for_group = _laser_pointing_methods_optimise_group["_actuator_roles_for_group"]

    _actuator_group_entry = _laser_pointing_methods_optimise_group["_actuator_group_entry"]

    _device_for_role = _laser_pointing_methods_optimise_group["_device_for_role"]

    _actuator_lifecycle = (staticmethod)(_laser_pointing_methods_optimise_group["_actuator_lifecycle"])

    _search_bounds = (staticmethod)(_laser_pointing_methods_optimise_group["_search_bounds"])

    _command_error = (staticmethod)(_laser_pointing_methods_optimise_group["_command_error"])

    _is_command_timeout = (staticmethod)(_laser_pointing_methods_optimise_group["_is_command_timeout"])

    _move_pair = _laser_pointing_methods_optimise_group["_move_pair"]

    _move_single_axis = _laser_pointing_methods_optimise_group["_move_single_axis"]

    _fresh_position_and_state = (staticmethod)(_laser_pointing_methods_optimise_group["_fresh_position_and_state"])

    _move_multi_axis = _laser_pointing_methods_optimise_group["_move_multi_axis"]

    _state_is_moving = (staticmethod)(_laser_pointing_methods_optimise_group["_state_is_moving"])

    _is_flipper_role = (staticmethod)(_laser_pointing_methods_optimise_group["_is_flipper_role"])
    del _laser_pointing_methods_optimise_group

    _laser_pointing_methods_normalise_working_rule = _bind_laser_pointing_methods_normalise_working_rule(_refactor_modules[__name__])
    _normalise_working_rule = _laser_pointing_methods_normalise_working_rule["_normalise_working_rule"]

    _fresh_flipper_command_state = (staticmethod)(_laser_pointing_methods_normalise_working_rule["_fresh_flipper_command_state"])

    _command_route_flippers = _laser_pointing_methods_normalise_working_rule["_command_route_flippers"]

    _apply_point = _laser_pointing_methods_normalise_working_rule["_apply_point"]

    _publish_active_point = _laser_pointing_methods_normalise_working_rule["_publish_active_point"]

    _fresh_camera_values = (staticmethod)(_laser_pointing_methods_normalise_working_rule["_fresh_camera_values"])

    _fresh_camera_image = (staticmethod)(_laser_pointing_methods_normalise_working_rule["_fresh_camera_image"])

    _read_beam_shape = _laser_pointing_methods_normalise_working_rule["_read_beam_shape"]

    _measure_point = _laser_pointing_methods_normalise_working_rule["_measure_point"]

    _interruptible_sleep = _laser_pointing_methods_normalise_working_rule["_interruptible_sleep"]

    _wait_if_paused = _laser_pointing_methods_normalise_working_rule["_wait_if_paused"]

    _raise_if_cancelled = _laser_pointing_methods_normalise_working_rule["_raise_if_cancelled"]

    execute_action = _laser_pointing_methods_normalise_working_rule["execute_action"]

    stop_opts = _laser_pointing_methods_normalise_working_rule["stop_opts"]
    del _laser_pointing_methods_normalise_working_rule


if __name__ == "__main__":
    DS_LaserPointing.run_server()
