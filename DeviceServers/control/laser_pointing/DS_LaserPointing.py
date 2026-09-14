import ast
import json
import sys
from math import hypot
from pathlib import Path
from statistics import median
from threading import Event, Lock, Thread
from time import monotonic
from typing import Dict, Optional, Sequence, Tuple, Union

from tango import AttrWriteType, DevState, DispLevel
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
except ModuleNotFoundError:
    from automatic_search import (
        SearchParameters,
        bounded_pattern_search,
        optical_point_group,
    )


DEFAULT_SEARCH_CONFIG = {
    "mode": "sensitive",
    "initial_step": 10.0,
    "minimum_step": 2.0,
    "step_schedule": [10.0, 6.0, 2.0],
    "radius": 30.0,
    "tolerance_px": 2.0,
    "minimum_improvement_px": 0.1,
    "unchanged_response_tolerance_px": 0.25,
    "probe_repetitions": 3,
    "max_evaluations": 16,
    "max_cycles": 2,
    "samples": 3,
    "sample_interval_s": 0.2,
    "camera_frame_wait_s": 0.25,
    "motion_timeout_s": 180.0,
    "motion_poll_s": 0.2,
    "position_tolerance": 0.05,
    "position_stable_reads": 2,
    "groups": [],
    "point_pairs": {},
    "restore_point": "",
}


class SearchCancelled(RuntimeError):
    """Raised internally when cancellation occurs during a measurement."""


class LaserNotVisible(RuntimeError):
    """Raised when Basler has no valid laser centroid."""


class DS_LaserPointing(DS_ControlPosition):
    """Bounded automatic alignment through the configured diaphragm planes.

    The entry diaphragm and the two measurement planes remain encoded by the
    existing point rules.  Each search group compares a wider reference point
    with a more sensitive closed-diaphragm point and moves its associated X/Y
    actuator pair to minimise the centroid displacement.
    """

    RULES = {
        "start_cgc": [DevState.ON],
        "stop_cgc": [DevState.ON],
        "start_automatic_search": [DevState.ON],
        "stop_automatic_search": [DevState.ON],
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

    def init_device(self):
        old_stop = getattr(self, "_search_stop", None)
        if old_stop is not None:
            old_stop.set()

        self.sample_time = 1
        self.cgc = False
        self.deltas = [0.0, 0.0]
        self.current_pos = {"X": 0.0, "Y": 0.0}
        self.previos_pos = {"X": 0.0, "Y": 0.0}
        self.positions_before_pid = {}
        self._search_lock = Lock()
        self._search_stop = Event()
        self._search_thread: Optional[Thread] = None
        self._point_application_thread: Optional[Thread] = None
        self._search_status = "idle"
        self._search_progress: Dict = {}
        self._search_history = []
        self._search_started_at = None
        self._active_point = ""
        self._actuator_initialization_status = {
            "phase": "idle",
            "group": 0,
            "message": "Select an optical point before initialising a Standa pair",
        }

        super().init_device()
        camera_name = self.ds_dict["Camera"]
        self.devices[camera_name] = Device(camera_name)
        self._search_config = self._normalise_search_config(
            self.automatic_search_defaults
        )
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
        """Chronological centroid-error observations for time-based plots."""

        return json.dumps(list(self._search_history), sort_keys=True)

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
            self.cgc = True
            self._search_status = "running"
            self._search_history = []
            self._search_started_at = monotonic()
            self._search_progress = {"phase": "starting", "config": config}
            self._search_thread = Thread(
                target=self._automatic_search_worker,
                args=(config,),
                name=f"{self.device_name}-automatic-search",
                daemon=True,
            )
            self._search_thread.start()
        return 0

    @command(dtype_out=int)
    def stop_automatic_search(self):
        self._search_stop.set()
        self.cgc = False
        if self._search_is_running():
            self._search_status = "stopping"
        return 0

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
            tolerance_px=config["tolerance_px"],
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
        if config["samples"] < 1:
            raise ValueError("samples must be at least 1")
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
        config["restore_point"] = str(config["restore_point"]).strip()
        return config

    def _automatic_search_worker(self, config: Dict):
        results = []
        try:
            camera = self.devices[self.ds_dict["Camera"]]
            try:
                if not bool(camera.isgrabbing):
                    camera.start_grabbing()
            except Exception as error:
                raise RuntimeError(f"could not start camera acquisition: {error}")

            stages = self._point_stages(config)
            last_stage_group_count = len(stages[-1][1])
            converged = False
            search_origins = {}
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
                    if results and all(
                        result["best_error_px"] <= config["tolerance_px"]
                        for result in results[-last_stage_group_count:]
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

            self._search_progress = {"phase": "finished", "results": results}
            self._search_status = "completed"
        except SearchCancelled:
            self._search_progress = {"phase": "cancelled", "results": results}
            self._search_status = "cancelled"
        except LaserNotVisible as error:
            self._search_progress = {
                "phase": "laser_not_visible",
                "message": str(error),
                "results": results,
            }
            self._search_status = f"laser not visible: {error}"
            self.warn(f"Automatic laser-pointing search stopped: {error}", True)
        except Exception as error:
            self._search_progress = {
                "phase": "error",
                "message": str(error),
                "results": results,
            }
            self._search_status = f"error: {error}"
            self.error(f"Automatic laser-pointing search failed: {error}")
        finally:
            self.cgc = False

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
        start = tuple(float(device.position) for device in actuator_devices)
        origin = search_origins.setdefault(group_name, start)
        bounds = self._search_bounds(actuator_devices, origin, config["radius"])
        parameters = SearchParameters(
            initial_step=motor_step,
            minimum_step=motor_step,
            tolerance_px=config["tolerance_px"],
            max_evaluations=config["max_evaluations"],
            minimum_improvement_px=config["minimum_improvement_px"],
            step_schedule=(motor_step,),
            probe_repetitions=config["probe_repetitions"],
            unchanged_response_tolerance_px=config[
                "unchanged_response_tolerance_px"
            ],
        )
        last_optical_signature = ()

        def objective(position):
            nonlocal last_optical_signature
            self._raise_if_cancelled()
            self._move_pair(actuator_devices, position, config)
            reference = self._measure_point(point_pair[0], config)
            test = self._measure_point(point_pair[1], config)
            delta_x = reference[0] - test[0]
            delta_y = reference[1] - test[1]
            score = hypot(delta_x, delta_y)
            self.previos_pos = {"X": reference[0], "Y": reference[1]}
            self.current_pos = {"X": test[0], "Y": test[1]}
            self.deltas = [delta_x, delta_y]
            last_optical_signature = (
                reference[0],
                reference[1],
                test[0],
                test[1],
            )
            self._search_progress = {
                "phase": "measuring",
                "cycle": cycle,
                "stage": stage_name,
                "group": group_name,
                "motor_step": motor_step,
                "points": list(point_pair),
                "actuator_position": list(position),
                "reference_centroid": list(reference),
                "test_centroid": list(test),
                "delta_px": [delta_x, delta_y],
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
                "actuator_position": list(position),
                "delta_px": [delta_x, delta_y],
                "error_px": score,
            }
            self._search_history.append(observation)
            self._search_progress["observation_index"] = observation["index"]
            return score

        result = bounded_pattern_search(
            objective,
            start=start,
            bounds=bounds,
            parameters=parameters,
            cancelled=self._search_stop.is_set,
            response_signature=lambda: last_optical_signature,
        )
        if result.reason == "cancelled":
            raise SearchCancelled()
        self._move_pair(actuator_devices, result.best_position, config)

        return {
            "cycle": cycle,
            "stage": stage_name,
            "group": group_name,
            "motor_step": motor_step,
            "points": list(point_pair),
            "start_position": list(start),
            "search_origin": list(origin),
            "best_position": list(result.best_position),
            "best_error_px": result.best_score,
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
        result = device.move_axis_abs(float(target))
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
                last_actual = float(device.position)
                state = str(device.state).upper()
            except Exception as error:
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

    def _move_multi_axis(self, device, value, config):
        axis = int(value[0])
        target = float(value[1])
        result = device.move_axis_abs([axis, target])
        command_error = self._command_error(result)
        if command_error:
            raise RuntimeError(command_error)

        deadline = monotonic() + config["motion_timeout_s"]
        stable = 0
        last_actual = None
        while monotonic() < deadline:
            self._raise_if_cancelled()
            try:
                state = device.get_status_axis(axis)
                last_actual = float(device.read_position_axis(axis))
            except Exception as error:
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
            f"{config['motion_timeout_s']} s; last readback was {last_actual}"
        )

    @staticmethod
    def _state_is_moving(state) -> bool:
        try:
            return int(state) == int(DevState.MOVING)
        except (TypeError, ValueError):
            return "MOVING" in str(state).upper()

    def _apply_point(self, point_name: str, config: Dict):
        self._raise_if_cancelled()
        # Optical presets commonly contain several Standa-backed devices on
        # the same host. Apply them deterministically so their Tango/libximc
        # transactions cannot contend and leave a partial preset behind.
        for role, value in self.controller_rules[point_name].items():
            self._raise_if_cancelled()
            device = self._device_for_role(role)
            try:
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    self._move_multi_axis(device, value, config)
                else:
                    self._move_single_axis(device, float(value), config)
            except Exception as error:
                raise RuntimeError(
                    f"could not apply controller point {point_name}: {role}: {error}"
                ) from error
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

    def _measure_point(self, point_name: str, config: Dict):
        self._apply_point(point_name, config)
        # Motion completion is readback-driven. This short wait only ensures
        # Basler has published a frame acquired after the final movement.
        self._interruptible_sleep(config["camera_frame_wait_s"])
        camera = self.devices[self.ds_dict["Camera"]]
        x_values = []
        y_values = []
        for sample_index in range(config["samples"]):
            self._raise_if_cancelled()
            try:
                centroid = ast.literal_eval(str(camera.cg))
                x_value = float(centroid["X"])
                y_value = float(centroid["Y"])
            except Exception as error:
                raise RuntimeError(f"invalid camera centroid: {error}")
            try:
                centroid_valid = bool(camera.cg_valid)
            except Exception:
                # Compatibility with an older Basler server during rollout.
                centroid_valid = (x_value, y_value) not in (
                    (0.0, 0.0),
                    (1024.0, 1024.0),
                )
            if not centroid_valid:
                raise LaserNotVisible(
                    f"Basler camera did not detect the laser at {point_name}; "
                    "check that the laser is present before restarting"
                )
            x_values.append(x_value)
            y_values.append(y_value)
            if sample_index + 1 < config["samples"]:
                self._interruptible_sleep(config["sample_interval_s"])
        return median(x_values), median(y_values)

    def _interruptible_sleep(self, duration: float):
        if duration > 0 and self._search_stop.wait(duration):
            raise SearchCancelled()
        self._raise_if_cancelled()

    def _raise_if_cancelled(self):
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
