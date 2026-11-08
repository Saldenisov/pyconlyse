"""Implementation for _normalise_working_rule and related operations."""


def _bind_laser_pointing_methods_normalise_working_rule(api):
    """Bind implementation to the owning module and its runtime state."""

    def _normalise_working_rule(self):
        """Expose the effective Working preset to every client.

        Old Tango database registrations may contain a camera-observation
        flipper route in the Working rule. Working always means an open beam:
        all diaphragms are fully open and all configured shutters are down.
        The registered wave-plate and translation targets remain authoritative.
        """

        rules = getattr(self, "controller_rules", None) or {}
        working_rule = rules.get("working")
        if not isinstance(working_rule, dict):
            return
        for role in (getattr(self, "ds_dict", None) or {}):
            normalized_role = str(role).lower()
            if "diaphragm" in normalized_role:
                working_rule[role] = 100.0
            elif self._is_flipper_role(role):
                working_rule[role] = 1.0

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

    def _command_route_flippers(self, point_name, force_down=False):
        point_rule = self.controller_rules.get(point_name, {})
        device_map = getattr(self, "ds_dict", None) or {}
        if force_down:
            targets = [
                (role, 1.0)
                for role in device_map
                if self._is_flipper_role(role)
            ]
        else:
            targets = [
                (role, float(target))
                for role, target in point_rule.items()
                if self._is_flipper_role(role) and role in device_map
            ]
        for role, target in targets:
            expected = "UP_BLOCKED" if target == -1.0 else "DOWN_CLEAR"
            self._raise_if_cancelled()
            progress = getattr(self, "_search_progress", None)
            if (getattr(self, "cgc", False) or force_down) and isinstance(
                progress, dict
            ):
                progress.update({
                    "phase": "applying_point",
                    "point": point_name,
                    "optical_role": role,
                    "optical_target": target,
                    "message": (
                        f"Lowering {role} for Working; verifying {expected}"
                        if force_down else
                        f"Routing {role} for {point_name}; verifying {expected}"
                    ),
                })
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

    def _apply_point(self, point_name: str, config: api.Dict):
        self._raise_if_cancelled()
        working_point = str(point_name).strip().lower() == "working"
        # Route the selected camera before changing apertures or propagation
        # plane. Each controller's registered rules specify the exact flipper
        # combination; the topology cannot be derived from point number.
        # Working is sequenced differently: wave plate first, remaining optics
        # second, and shutters down only after every optical readback succeeds.
        if not working_point:
            self._command_route_flippers(point_name)
        # Optical presets commonly contain several Standa-backed devices on
        # the same host. Apply them deterministically so their Tango/libximc
        # transactions cannot contend and leave a partial preset behind.
        targets = [
            (role, value)
            for role, value in self.controller_rules[point_name].items()
            if not self._is_flipper_role(role)
        ]
        if working_point:
            # Working is the safe open-beam preset. Enforce 100% for every
            # configured diaphragm even if an older database rule is stale or
            # omits one. The priority function below puts the registered
            # wave-plate target first, then every remaining Working optic.
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
            configured_wave_plates = [
                role for role in configured_roles
                if "halfwave" in str(role).lower()
            ]
            target_roles = {role for role, _value in targets}
            missing_wave_plates = [
                role for role in configured_wave_plates
                if role not in target_roles
            ]
            if missing_wave_plates:
                raise RuntimeError(
                    "could not apply Working: no registered working target for "
                    + ", ".join(missing_wave_plates)
                )
        # Numbered points set apertures before their translation plane.
        # Working sets λ/2 first, all remaining optics second, and flippers
        # separately at the end because their numeric position always reads zero.
        def target_priority(item):
            normalized_role = str(item[0]).lower()
            if working_point and "halfwave" in normalized_role:
                return 0
            if "diaphragm" in normalized_role:
                return 1 if working_point else 0
            if "translation" in normalized_role:
                return 2 if working_point else 1
            return 3 if working_point else 2

        targets.sort(key=target_priority)

        deferred_errors = []
        for role, value in targets:
            self._raise_if_cancelled()
            progress = getattr(self, "_search_progress", None)
            if (getattr(self, "cgc", False) or working_point) and isinstance(
                progress, dict
            ):
                progress.update({
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
        if working_point:
            # The flipper server publishes DOWN_CLEAR only after the physical
            # movement has completed. _command_route_flippers reads it back
            # directly and refuses to publish Working on any mismatch.
            self._command_route_flippers(point_name, force_down=True)
        # Publish the point only after every child has reached its readback.
        # Both clients use this as the source of truth for the mount interlock.
        self._publish_active_point(point_name)

    def _publish_active_point(self, point_name: str):
        self._active_point = point_name
        group_index = api.optical_point_group(point_name)
        self._actuator_initialization_status = {
            "phase": "ready_to_initialize" if group_index else "idle",
            "group": group_index,
            "message": (
                f"Point selected; initialise Standa pair {group_index}"
                if group_index
                else "Select a numbered optical point before initialising a pair"
            ),
        }

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

    def _fresh_camera_image(camera):
        """Take a direct image snapshot, bypassing any Taurus polling cache."""

        value = api.DS_LaserPointing._fresh_camera_values(camera, "image")["image"]
        return api.np.array(value, copy=True)

    def _read_beam_shape(self):
        """Return the contour score calculated for the latest point sample."""

        shape = getattr(self, "_last_beam_shape", None)
        if shape is None:
            raise api.LaserNotVisible("no recent beam-contour measurement is available")
        return shape

    def _measure_point(self, point_name: str, config: api.Dict):
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
        contour_profile = api.camera_contour_profile(
            self.ds_dict["Camera"], profile["center_gravity_threshold"]
        )
        profile_arguments = {
            **contour_profile,
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
                    if config.get("alignment_objective") == "centering":
                        hashes = getattr(self, "_alignment_frame_hashes", None)
                        if hashes is None:
                            hashes = self._alignment_frame_hashes = api.deque(maxlen=64)
                        digest = api.hashlib.blake2b(frame.tobytes(), digest_size=16).digest()
                        if digest in hashes:
                            raise ValueError("duplicate camera frame cannot confirm independent measurements")
                    # A valid camera transfer can still contain no usable
                    # beam after an optical or actuator move. Do not let that
                    # frame poison the median profile; consume the existing
                    # invalid-frame retry budget and wait for another frame.
                    api.beam_contour_symmetry([frame], **profile_arguments)
                    if config.get("alignment_objective") == "centering":
                        hashes.append(digest)
                    frames.append(frame)
                    break
                except Exception as error:
                    if retries_remaining <= 0:
                        raise api.LaserNotVisible(
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
                "frame_shapes": [list(api.np.asarray(frame).shape) for frame in frames],
                "frame_peaks": [float(api.np.max(frame)) for frame in frames],
            }
            shape = api.beam_contour_symmetry(
                frames,
                include_preview=True,
                **profile_arguments,
            )
        except Exception as error:
            raise api.LaserNotVisible(
                f"Basler beam contours are invalid at {point_name}: {error}; "
                f"profile input={profile_diagnostics}"
            ) from error
        self._last_beam_shape = shape
        return tuple(shape["alignment_centroid"] if config.get("alignment_objective") == "centering"
                     else shape["shape_centroid"])

    def _interruptible_sleep(self, duration: float):
        if duration > 0 and self._search_stop.wait(duration):
            raise api.SearchCancelled()
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
                raise api.SearchCancelled()
        if self._search_stop.is_set():
            raise api.SearchCancelled()
        self._search_status = "running"
        self._search_progress = {
            **self._progress_before_pause,
            "resumed_at_utc": self._utc_now(),
        }
        self._pause_active = False
        self._record_alignment_event("resumed")

    def _raise_if_cancelled(self):
        if self._search_stop.is_set():
            raise api.SearchCancelled()
        self._wait_if_paused()
        if self._search_stop.is_set():
            raise api.SearchCancelled()

    def execute_action(self, action: float, device: api.Device, relative=False, threaded=False):
        """Compatibility helper retained for external scripts."""
        if threaded:
            api.Thread(
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

    return {
        "_normalise_working_rule": _normalise_working_rule,
        "_fresh_flipper_command_state": _fresh_flipper_command_state,
        "_command_route_flippers": _command_route_flippers,
        "_apply_point": _apply_point,
        "_publish_active_point": _publish_active_point,
        "_fresh_camera_values": _fresh_camera_values,
        "_fresh_camera_image": _fresh_camera_image,
        "_read_beam_shape": _read_beam_shape,
        "_measure_point": _measure_point,
        "_interruptible_sleep": _interruptible_sleep,
        "_wait_if_paused": _wait_if_paused,
        "_raise_if_cancelled": _raise_if_cancelled,
        "execute_action": execute_action,
        "stop_opts": stop_opts,
    }
