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
        except api.SearchCancelled:
            # Cancel+restore is handled by the worker's complete baseline
            # restoration. Plain Cancel instead retains the latest position
            # with a valid beam measurement, never an interrupted probe.
            if getattr(self, "_restore_on_cancel", True) is False:
                self._search_stop.clear()
                try:
                    self._search_progress = {
                        **self._search_progress,
                        "phase": "retaining_last_measured_good_position",
                        "message": (
                            "Cancel requested; retaining latest measured-good "
                            f"{group_name} position {best_visible_position}"
                        ),
                    }
                    self._move_pair(
                        actuator_devices, best_visible_position, config
                    )
                finally:
                    self._search_stop.set()
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

    def _state_is_moving(state) -> bool:
        try:
            return int(state) == int(api.DevState.MOVING)
        except (TypeError, ValueError):
            return "MOVING" in str(state).upper()

    def _is_flipper_role(role) -> bool:
        normalized_role = str(role).lower()
        return "shutter" in normalized_role or "flipper" in normalized_role

    return {
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
