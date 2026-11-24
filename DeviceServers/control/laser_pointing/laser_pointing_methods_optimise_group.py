"""Implementation for _optimise_group and related operations."""


def _bind_laser_pointing_methods_optimise_group(api):
    """Bind implementation to the owning module and its runtime state."""

    def _optimise_group(
        self,
        group_name: str,
        point_pair: api.Tuple[str, str],
        stage_name: str,
        cycle: int,
        motor_step: float,
        config: api.Dict,
        search_origins: api.Dict,
    ) -> api.Dict:
        if config.get("alignment_objective") == "centering":
            return self._optimise_centering_group(group_name, point_pair, stage_name, cycle,
                                                  motor_step, config, search_origins)
        actuator_roles = self._actuator_roles_for_group(group_name)
        actuator_devices = [self._device_for_role(role) for role in actuator_roles]
        start = tuple(
            self._fresh_position_and_state(device)[0]
            for device in actuator_devices
        )
        origin = search_origins.setdefault(group_name, start)
        bounds = self._search_bounds(actuator_devices, origin, config["radius"])
        target_point = point_pair[-1]
        requested_motor_step = float(motor_step)
        motor_step = self._adaptive_step_limit(
            group_name, target_point, requested_motor_step, config
        )
        parameters = api.SearchParameters(
            initial_step=motor_step,
            minimum_step=motor_step,
            tolerance_px=config["roundness_tolerance_pct"],
            max_evaluations=config["max_evaluations"],
            minimum_improvement_px=config["minimum_improvement_px"],
            step_schedule=(motor_step,),
            probe_repetitions=self._adaptive_probe_repetitions(
                target_point, config
            ),
            unchanged_response_tolerance_px=config[
                "unchanged_response_tolerance_px"
            ],
            plateau_evaluations=int(config.get(
                "group_plateau_probe_limit", 5
            )),
            plateau_min_improvement=float(config.get(
                "group_plateau_min_improvement_pct", 5.0
            )),
        )
        last_optical_signature = ()
        best_visible_position = start
        best_visible_score = float("inf")
        best_visible_shape = None
        baseline_centre = None
        baseline_shape = None

        def objective(position):
            nonlocal last_optical_signature, best_visible_position
            nonlocal best_visible_score, best_visible_shape
            nonlocal baseline_centre, baseline_shape
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
                "requested_motor_step": requested_motor_step,
                "points": list(point_pair),
                "measured_point": target_point,
                "actuator_roles": list(actuator_roles),
                "previous_actuator_position": list(previous_position),
                "actuator_position": list(position),
                "move_delta": move_delta,
                "message": (
                    f"Moving {group_name}: "
                    + ", ".join(
                        f"{role} to {target:.3f} ({delta:+.3f})"
                        for role, target, delta in zip(
                            actuator_roles, position, move_delta
                        )
                    )
                ),
            }
            if last_beam_shape:
                self._search_progress["beam_shape"] = last_beam_shape
            self._move_pair(actuator_devices, position, config)
            try:
                test = self._measure_aperture_cycle(point_pair, config)
                test_shape = self._read_beam_shape()
            except api.LaserNotVisible as error:
                # The baseline must be visible, but a directional probe is
                # allowed to leave the usable camera/beam path. Score that
                # candidate as rejected, restore the last measured-good
                # position, and let the bounded search try another direction.
                if baseline_centre is None:
                    raise
                self._learn_from_probe(
                    group_name,
                    target_point,
                    actuator_roles,
                    previous_position,
                    position,
                    best_visible_score if api.np.isfinite(best_visible_score) else None,
                    None,
                    best_visible_shape,
                    None,
                    False,
                    requested_motor_step,
                    config,
                    error=error,
                )
                last_optical_signature = (
                    1.0e9,
                    *tuple(float(value) for value in position),
                )
                elapsed_s = (
                    api.monotonic() - self._search_started_at
                    if self._search_started_at is not None
                    else 0.0
                )
                next_maximum_step = self._adaptive_step_limit(
                    group_name, target_point, requested_motor_step, config
                )
                observation = {
                    "index": len(self._search_history) + 1,
                    "elapsed_s": elapsed_s,
                    "group": group_name,
                    "stage": stage_name,
                    "motor_step": motor_step,
                    "requested_motor_step": requested_motor_step,
                    "points": list(point_pair),
                    "measured_point": target_point,
                    "actuator_position": list(position),
                    "roundness_error_pct": 100.0,
                    "score_metric": "contour_symmetry_error_pct",
                    "error_px": 100.0,
                    "message": (
                        "Beam disappeared; rejecting probe and returning to "
                        f"{best_visible_position}. Next maximum step: "
                        f"{next_maximum_step:.3f}"
                    ),
                }
                self._search_history.append(observation)
                self._search_progress = {
                    **observation,
                    "phase": "probe_rejected",
                    "observation_index": observation["index"],
                }
                if tuple(position) != best_visible_position:
                    self._search_progress.update({
                        "phase": "restoring_last_visible_position",
                        "message": observation["message"],
                    })
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
            self._learn_from_probe(
                group_name,
                target_point,
                actuator_roles,
                previous_position,
                position,
                best_visible_score if api.np.isfinite(best_visible_score) else None,
                score,
                best_visible_shape,
                test_shape,
                True,
                requested_motor_step,
                config,
            )
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
                best_visible_shape = test_shape
            self._search_progress = {
                "phase": "measuring",
                "cycle": cycle,
                "stage": stage_name,
                "group": group_name,
                "motor_step": motor_step,
                "requested_motor_step": requested_motor_step,
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
                api.monotonic() - self._search_started_at
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
                "requested_motor_step": requested_motor_step,
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
            result = api.bounded_pattern_search(
                objective,
                start=start,
                bounds=bounds,
                parameters=parameters,
                cancelled=self._search_stop.is_set,
                response_signature=lambda: last_optical_signature,
                step_limit=lambda: self._adaptive_step_limit(
                    group_name, target_point, requested_motor_step, config
                ),
                direction_order=self._adaptive_direction_order(
                    group_name, target_point, actuator_roles
                ),
            )
        except (api.SearchCancelled, api.AxisStopUnconfirmed):
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
            raise api.SearchCancelled()

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
            "requested_motor_step": requested_motor_step,
            "points": list(point_pair),
            "start_position": list(start),
            "search_origin": list(origin),
            "best_position": list(retained_position),
            "best_roundness_error_pct": retained_score,
            "best_error_px": retained_score,
            "evaluations": result.evaluations,
            "reason": result.reason,
        }

    def _actuator_roles_for_group(self, group_name: str) -> api.Tuple[str, str]:
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

    def _actuator_group_entry(self, group_index: int) -> api.Tuple[str, api.Tuple[str, str]]:
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
            self.devices[device_name] = api.Device(device_name)
        return self.devices[device_name]

    def _actuator_lifecycle(device) -> api.Dict:
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

    def _search_bounds(devices, start: api.Sequence[float], radius: float):
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

    def _command_error(result):
        if result is None:
            return ""
        if isinstance(result, bool):
            return "" if result else "command returned False"
        if isinstance(result, (int, float)):
            return "" if float(result) == 0.0 else str(result)
        text = str(result).strip()
        return "" if text in ("", "0", "0.0") else text

    def _is_command_timeout(error) -> bool:
        normalized = str(error).lower().replace("_", "")
        return "timeout" in normalized or "timedout" in normalized

    def _move_pair(self, devices, positions, config):
        errors = []

        def move(device, position):
            try:
                self._move_single_axis(device, float(position), config)
            except Exception as error:
                errors.append(error)

        threads = [
            api.Thread(target=move, args=(device, position), daemon=True)
            for device, position in zip(devices, positions)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors:
            if any(isinstance(error, api.SearchCancelled) for error in errors):
                raise api.SearchCancelled()
            raise RuntimeError(
                "actuator movement failed: "
                + "; ".join(str(error) for error in errors)
            )

    def _move_single_axis(self, device, target: float, config):
        self._raise_if_cancelled()
        if self._calibrate_full_open_endpoint(device, target, config):
            return
        endpoint_required = (float(target) == 100.0
                             and self._full_open_endpoint_definition(
                                 device, working=config.get("_working_point", False)
                             ) is not None)
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
        deadline = api.monotonic() + config["motion_timeout_s"]
        last_actual = None
        while api.monotonic() < deadline:
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
                if endpoint_required and not self._calibrate_full_open_endpoint(device, target, config):
                    raise RuntimeError("Configured full-open endpoint is not confirmed")
                return
            # Mono-axis move_axis_abs returns only after the child command has
            # stopped.  Waiting for the full automatic-search timeout after a
            # stopped readback mismatch hides the real failure and blocks the
            # controller's Tango monitor for minutes.
            if "MOVING" not in state:
                if endpoint_required and self._calibrate_full_open_endpoint(device, target, config):
                    return
                raise RuntimeError(
                    f"motor stopped at {last_actual}, expected {target}"
                )
            self._interruptible_sleep(config["motion_poll_s"])
        raise RuntimeError(
            f"motor did not reach {target} within {config['motion_timeout_s']} s; "
            f"last readback was {last_actual}"
        )

    def _fresh_position_and_state(device) -> api.Tuple[float, str]:
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
        self._raise_if_cancelled()
        self._require_confirmed_axis_stop()
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
            if command_error and not self._is_command_timeout(command_error):
                raise RuntimeError(command_error)

        try:
            self._wait_for_axis_target(device, axis, target, config)
        except Exception:
            # The move has been submitted. Finish stopping this axis before
            # releasing the preset/search worker or starting a restore.
            self._stop_and_verify_axis(device, axis)
            raise

    def _state_is_moving(state) -> bool:
        try:
            return int(state) == int(api.DevState.MOVING)
        except (TypeError, ValueError):
            return "MOVING" in str(state).upper()

    def _is_flipper_role(role) -> bool:
        normalized_role = str(role).lower()
        return "shutter" in normalized_role or "flipper" in normalized_role

    def _full_open_endpoint_definition(self, device, *, working=False):
        definitions = api.json.loads(getattr(self, 'full_open_endpoint_calibrations', '{}') or '{}')
        if not isinstance(definitions, dict):
            raise ValueError('full_open_endpoint_calibrations must be a JSON object')
        if working:
            # These V0 irises use the RIGHT limit switch at full opening.
            # The same physical iris has different roles in Cam1 and Cam2.
            full_open_devices = {
                "elyse/motorized_devices/de1", "manip/v0/dv01",
                "manip/v0/dv02", "manip/v0/dv03",
            }
            for role, name in getattr(self, "ds_dict", {}).items():
                if isinstance(name, str) and name.lower() in full_open_devices:
                    definitions.setdefault(role, {"endpoint": "RIGHT"})
        for role, definition in definitions.items():
            if 'diaphragm' not in str(role).lower() or role not in self.ds_dict:
                continue
            if self._device_for_role(role) is not device:
                continue
            if not isinstance(definition, dict) or definition.get('endpoint') not in ('RIGHT','LEFT'):
                raise ValueError(f'Invalid full-open endpoint definition for {role}')
            nominal = float(definition.get('position', 100.))
            window = float(definition.get('max_counter_error', 5.))
            if nominal != 100. or not api.isfinite(window) or not 0 < window <= 5.:
                raise ValueError(f'Invalid full-open counter calibration window for {role}')
            return {'role': role, 'position': nominal, 'endpoint': definition['endpoint'],
                    'max_counter_error': window}
        return None

    def _fresh_endpoint_state(device):
        # Standa updates its endpoint attribute from the native status sample.
        # Refresh that sample before bypassing the Taurus polling cache.
        result = device.get_controller_status()
        error = api.DS_LaserPointing._command_error(result)
        if error:
            raise RuntimeError(f'Could not refresh physical endpoint: {error}')
        try:
            proxy = device.getDeviceProxy()
        except AttributeError:
            return str(device.endpoint_state).upper()
        original = proxy.get_source()
        direct = getattr(type(original), 'DEV', None)
        if direct is None:
            raise RuntimeError('Endpoint proxy does not expose a direct-read source')
        try:
            proxy.set_source(direct)
            return str(proxy.read_attribute('endpoint_state').value).upper()
        finally:
            proxy.set_source(original)

    def _calibrate_full_open_endpoint(self, device, target, config):
        if float(target) != 100.:
            return False
        definition = self._full_open_endpoint_definition(
            device, working=config.get("_working_point", False)
        )
        if definition is None:
            return False
        actual, state = self._fresh_position_and_state(device)
        if state != 'ON':
            return False
        endpoint = self._fresh_endpoint_state(device)
        actual, state = self._fresh_position_and_state(device)
        if state != 'ON' or endpoint != definition['endpoint']:
            return False
        nominal = definition['position']
        if not api.isfinite(actual) or abs(actual-nominal) > definition['max_counter_error']:
            raise RuntimeError(f"Full-open endpoint counter {actual} is outside its calibration window")
        if actual != nominal:
            self._raise_if_cancelled()
            result = device.define_position(nominal)  # Counter definition only; no movement/homing.
            error = self._command_error(result)
            if error:
                raise RuntimeError(f'Full-open counter definition failed: {error}')
            after, after_state = self._fresh_position_and_state(device)
            if (after_state != 'ON' or abs(after-nominal) > .01
                    or self._fresh_endpoint_state(device) != endpoint):
                raise RuntimeError('Full-open counter definition could not be verified')
            record = dict(role=definition['role'], endpoint=endpoint,
                          raw_position_before=actual, position_after=after,
                          physical_motion_commanded=False)
            self._search_progress['full_open_endpoint_calibration'] = record
            self._record_alignment_event('full_open_endpoint_calibrated', **record)
        return True

    def _wait_for_axis_target(self, device, axis, target, config):
        deadline = api.monotonic() + config["motion_timeout_s"]
        stable = 0
        last_actual = None
        last_read_error = ""
        while api.monotonic() < deadline:
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

    def _stop_and_verify_axis(self, device, axis):
        self._unconfirmed_axis_stop = (device, axis)
        try:
            command_error = self._command_error(device.stop_axis(axis))
            if command_error:
                raise RuntimeError(command_error)

            # PS90 can report ON during motion. Require fresh, stable positions
            # after the acknowledged stop, even when the status is already ON.
            previous = None
            stable = 0
            deadline = api.monotonic() + 3.0
            while api.monotonic() < deadline:
                state = device.get_status_axis(axis)
                position = float(device.read_position_axis(axis))
                if (state in (api.DevState.ON, api.DevState.STANDBY, api.DevState.OFF)
                        and api.isfinite(position) and previous is not None
                        and abs(position - previous) <= 0.002):
                    stable += 1
                    if stable >= 2:
                        self._unconfirmed_axis_stop = None
                        return
                else:
                    stable = 0
                previous = position
                api.sleep(0.2)
            raise RuntimeError("position did not settle after Stop")
        except Exception as error:
            raise api.AxisStopUnconfirmed(
                f"OWIS axis {axis} stop could not be confirmed: {error}"
            ) from error

    def _require_confirmed_axis_stop(self):
        if getattr(self, "_unconfirmed_axis_stop", None):
            raise api.AxisStopUnconfirmed("Confirm the OWIS stop before starting another optical move")

    def _publish_axis_stop_error(self, error):
        self._active_point = ""
        self._search_status = "axis stop unconfirmed"
        self._search_progress = {
            "phase": "axis_stop_unconfirmed", "message": str(error),
        }
        self._actuator_initialization_status = {
            "phase": "axis_stop_unconfirmed", "group": 0, "message": str(error),
        }
        self.error(str(error))

    def _retry_axis_stop(self):
        try:
            self._stop_and_verify_axis(*self._unconfirmed_axis_stop)
        except api.AxisStopUnconfirmed as error:
            self._publish_axis_stop_error(error)
        else:
            self._search_status = "cancelled; current alignment kept"
            self._search_progress = {
                "phase": "cancelled_keep_current", "message": "OWIS axis stopped",
            }
            self._actuator_initialization_status = {
                "phase": "point_application_cancelled", "group": 0,
                "message": "OWIS axis stopped; select an optical point to use the mounts",
            }


    return {
        "_full_open_endpoint_definition": _full_open_endpoint_definition,
        "_fresh_endpoint_state": _fresh_endpoint_state,
        "_calibrate_full_open_endpoint": _calibrate_full_open_endpoint,
        "_wait_for_axis_target": _wait_for_axis_target,
        "_stop_and_verify_axis": _stop_and_verify_axis,
        "_require_confirmed_axis_stop": _require_confirmed_axis_stop,
        "_publish_axis_stop_error": _publish_axis_stop_error,
        "_retry_axis_stop": _retry_axis_stop,
        "_optimise_group": _optimise_group,
        "_actuator_roles_for_group": _actuator_roles_for_group,
        "_actuator_group_entry": _actuator_group_entry,
        "_device_for_role": _device_for_role,
        "_actuator_lifecycle": _actuator_lifecycle,
        "_search_bounds": _search_bounds,
        "_command_error": _command_error,
        "_is_command_timeout": _is_command_timeout,
        "_move_pair": _move_pair,
        "_move_single_axis": _move_single_axis,
        "_fresh_position_and_state": _fresh_position_and_state,
        "_move_multi_axis": _move_multi_axis,
        "_state_is_moving": _state_is_moving,
        "_is_flipper_role": _is_flipper_role,
    }
