"""Implementation for find_device and related operations."""


def _bind_laser_pointing_methods_find_device(api):
    """Bind implementation to the owning module and its runtime state."""

    def find_device(self):
        argreturn = self.server_id, self.device_id
        self._device_id_internal, self._uri = argreturn

    def turn_on_local(self) -> api.Union[int, str]:
        self.set_state(api.DevState.ON)
        return 0

    def turn_off_local(self) -> api.Union[int, str]:
        self._restore_on_cancel = False
        self._search_stop.set()
        self.set_state(api.DevState.OFF)
        return 0

    def write_automatic_search_config(self, value):
        if self._search_is_running():
            raise RuntimeError("automatic search configuration is locked while running")
        self._search_config = self._normalise_search_config(value)

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
                    override = api.json.loads(str(configuration))
                    if not isinstance(override, dict):
                        raise ValueError("search command input must be a JSON object")
                    config.update(override)
                config = self._normalise_search_config(config)
            except (TypeError, ValueError, api.json.JSONDecodeError) as error:
                self._search_status = f"error: {error}"
                self.error(self._search_status)
                return -1

            self._search_stop.clear()
            self._search_pause.clear()
            self.cgc = True
            self._search_status = "running"
            self._search_history = []
            self._search_started_at = api.monotonic()
            self._search_session_id = str(api.uuid4())
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
            self._search_thread = api.Thread(
                target=self._automatic_search_worker,
                args=(config,),
                name=f"{self.device_name}-automatic-search",
                daemon=True,
            )
            self._record_alignment_event("search_start_requested")
            self._search_thread.start()
        return 0

    def _accept_pending_alignment_reference(self, details=None):
        """Persist a verified candidate, including from the completing worker."""

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
        return self._persist_alignment_reference(candidate, details)

    def _persist_alignment_reference(self, candidate: api.Dict, details=None):
        """Append one already-captured alignment to durable reference history."""

        details = dict(details or {})
        reference = {
            **candidate,
            "accepted_at_utc": self._utc_now(),
            "acceptance": details,
            "revision": len(self._alignment_reference_history) + 1,
        }
        encoded = api.json.dumps(reference, separators=(",", ":"), sort_keys=True)
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

    def _point_application_worker(self, point_name: str, config: api.Dict):
        try:
            self._apply_point(point_name, config)
        except api.SearchCancelled:
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
            group_index = api.optical_point_group(self._active_point)
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

    def move_active_actuator(self, request):
        """Move one mount axis only when its optical point owns the pair.

        This is the authoritative interlock used by the web client.  A manual
        move is refused until a numbered point has been applied successfully,
        and roles from the inactive X/Y pair are never accepted.
        """

        try:
            payload = api.json.loads(str(request))
        except (TypeError, ValueError, api.json.JSONDecodeError) as error:
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
            active_group = api.optical_point_group(self._active_point)
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

    def _search_is_running(self) -> bool:
        return self._search_thread is not None and self._search_thread.is_alive()

    def _point_application_is_running(self) -> bool:
        thread = getattr(self, "_point_application_thread", None)
        return (
            thread is not None
            and thread.is_alive()
        )

    def _utc_now() -> str:
        return api.datetime.now(api.timezone.utc).isoformat(timespec="milliseconds")

    def _json_object(value) -> api.Dict:
        try:
            parsed = api.json.loads(str(value or "{}"))
        except (TypeError, ValueError, api.json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

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
            "adaptive_search_model_json",
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
        api.Database().put_device_property(get_name(), properties)

    def _record_alignment_event(self, event_type: str, **details):
        event = {
            "event_type": str(event_type),
            "session_id": getattr(self, "_search_session_id", ""),
            "status": getattr(self, "_search_status", "idle"),
            "recorded_at_utc": self._utc_now(),
            **details,
        }
        encoded = api.json.dumps(event, separators=(",", ":"), sort_keys=True)
        lock = getattr(self, "_alignment_event_lock", None)
        if lock is None:
            lock = api.Lock()
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

    def _capture_alignment_state(self) -> api.Dict:
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

    def _alignment_state_mismatches(self, reference: api.Dict, current: api.Dict):
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

    def _restore_alignment_state(self, state: api.Dict, config: api.Dict):
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

    return {
        "find_device": find_device,
        "turn_on_local": turn_on_local,
        "turn_off_local": turn_off_local,
        "write_automatic_search_config": write_automatic_search_config,
        "start_automatic_search": start_automatic_search,
        "_accept_pending_alignment_reference": _accept_pending_alignment_reference,
        "_persist_alignment_reference": _persist_alignment_reference,
        "_point_application_worker": _point_application_worker,
        "initialize_active_pair": initialize_active_pair,
        "move_active_actuator": move_active_actuator,
        "_search_is_running": _search_is_running,
        "_point_application_is_running": _point_application_is_running,
        "_utc_now": _utc_now,
        "_json_object": _json_object,
        "_string_list": _string_list,
        "_configure_alignment_events": _configure_alignment_events,
        "_push_alignment_value": _push_alignment_value,
        "_persist_alignment_properties": _persist_alignment_properties,
        "_record_alignment_event": _record_alignment_event,
        "_alignment_role_specs": _alignment_role_specs,
        "_capture_alignment_state": _capture_alignment_state,
        "_alignment_state_mismatches": _alignment_state_mismatches,
        "_restore_alignment_state": _restore_alignment_state,
    }
