"""Implementation for _store_pending_reference and related operations."""


def _bind_laser_pointing_methods_store_pending_reference(api):
    """Bind implementation to the owning module and its runtime state."""

    def _store_pending_reference(self, candidate: api.Dict):
        encoded = api.json.dumps(candidate, separators=(",", ":"), sort_keys=True)
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

    def _restore_completed_alignment_worker(self, baseline: api.Dict, config: api.Dict):
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

    def _normalise_search_config(value) -> api.Dict:
        if isinstance(value, str):
            value = api.json.loads(value)
        if not isinstance(value, dict):
            raise ValueError("automatic search configuration must be a JSON object")
        config = dict(api.DEFAULT_SEARCH_CONFIG)
        config.update(value)

        config["alignment_objective"] = str(config["alignment_objective"]).strip().lower()
        if config["alignment_objective"] not in ("roundness", "centering"):
            raise ValueError("alignment_objective must be roundness or centering")
        for name in ("centering_tolerance_px", "centering_minimum_improvement_px",
                     "confirmation_noise_multiplier", "ellipticity_tolerance_pct"):
            config[name] = api.finite_nonnegative(config[name], name)
        repeats = config["measurement_repetitions"]
        if isinstance(repeats, bool) or int(repeats) != float(repeats) or not 3 <= int(repeats) <= 5:
            raise ValueError("measurement_repetitions must be an integer between 3 and 5")
        config["measurement_repetitions"] = int(repeats)
        if not isinstance(config["centering_check_aperture_pair"], bool):
            raise ValueError("centering_check_aperture_pair must be boolean")

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
            "adaptive_min_step",
            "adaptive_backoff",
            "adaptive_growth",
            "aperture_drift_weight",
            "group_plateau_min_improvement_pct",
            "stagnation_min_improvement_pct",
        ):
            config[name] = float(config[name])
        for name in (
            "probe_repetitions",
            "max_evaluations",
            "max_cycles",
            "samples",
            "invalid_frame_retries",
            "position_stable_reads",
            "aperture_sweep_positions",
            "aperture_cycle_count",
            "aperture_samples",
            "group_plateau_probe_limit",
            "stagnation_pass_limit",
        ):
            config[name] = int(config[name])

        if not isinstance(config["step_schedule"], (list, tuple)):
            raise ValueError("step_schedule must be a JSON list")
        config["step_schedule"] = [float(step) for step in config["step_schedule"]]
        if not config["step_schedule"]:
            raise ValueError("step_schedule cannot be empty")
        config["initial_step"] = config["step_schedule"][0]
        config["minimum_step"] = config["step_schedule"][-1]

        api.SearchParameters(
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
        config["adaptive_learning"] = bool(config["adaptive_learning"])
        config["aperture_sweep_enabled"] = bool(
            config["aperture_sweep_enabled"]
        )
        if config["adaptive_min_step"] <= 0:
            raise ValueError("adaptive_min_step must be positive")
        if not 0 < config["adaptive_backoff"] < 1:
            raise ValueError("adaptive_backoff must be between zero and one")
        if config["adaptive_growth"] < 1:
            raise ValueError("adaptive_growth must be at least one")
        if not isinstance(config["point_step_limits"], dict):
            raise ValueError("point_step_limits must be a JSON object")
        config["point_step_limits"] = {
            str(point).strip().lower(): float(limit)
            for point, limit in config["point_step_limits"].items()
        }
        if any(limit <= 0 for limit in config["point_step_limits"].values()):
            raise ValueError("point_step_limits values must be positive")
        if not isinstance(config["point_probe_repetitions"], dict):
            raise ValueError("point_probe_repetitions must be a JSON object")
        config["point_probe_repetitions"] = {
            str(point).strip().lower(): int(repetitions)
            for point, repetitions in config["point_probe_repetitions"].items()
        }
        if any(
            repetitions < 1
            for repetitions in config["point_probe_repetitions"].values()
        ):
            raise ValueError(
                "point_probe_repetitions values must be at least one"
            )
        if config["aperture_sweep_positions"] < 2:
            raise ValueError("aperture_sweep_positions must be at least two")
        if config["aperture_cycle_count"] < 1:
            raise ValueError("aperture_cycle_count must be at least one")
        if not 1 <= config["aperture_samples"] <= 3:
            raise ValueError("aperture_samples must be between one and three")
        if config["aperture_drift_weight"] < 0:
            raise ValueError("aperture_drift_weight cannot be negative")
        if config["group_plateau_probe_limit"] < 1:
            raise ValueError("group_plateau_probe_limit must be at least one")
        if config["group_plateau_min_improvement_pct"] < 0:
            raise ValueError(
                "group_plateau_min_improvement_pct cannot be negative"
            )
        if config["stagnation_pass_limit"] < 2:
            raise ValueError("stagnation_pass_limit must be at least two")
        if config["stagnation_min_improvement_pct"] < 0:
            raise ValueError(
                "stagnation_min_improvement_pct cannot be negative"
            )
        # Flippers are not part of optical-point application, so legacy
        # camera-verified flipper entries from the Tango database are ignored.
        config["camera_verified_roles"] = []
        config["restore_point"] = str(config["restore_point"]).strip()
        return config

    def _automatic_search_worker(self, config: api.Dict):
        results = []
        verification = []
        try:
            self._alignment_frame_hashes = api.deque(maxlen=64)
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
            stopped_for_stagnation = False
            completed_passes = 0
            stagnant_passes = 0
            best_verification_error = float("inf")
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
                        if config.get("alignment_objective") == "centering":
                            quality = self._verify_centering_pair(point_pair, config)
                            verification.append({"group": group_name, "point": point_name, **quality})
                        else:
                            self._measure_aperture_cycle(point_pair, config)
                            shape = self._read_beam_shape()
                            verification.append({
                                "group": group_name,
                                "point": point_name,
                                "roundness_error_pct": shape["roundness_error_pct"],
                                "contour_centre_drift_px": shape.get("contour_centre_drift_px"),
                            })
                    self._search_progress = {
                        "phase": "verifying",
                        "cycle": cycle,
                        "motor_step": motor_step,
                        "points": verification,
                        "results": results,
                    }
                    if verification and all(
                        (item["centering_passed"]
                         if config.get("alignment_objective") == "centering"
                         else item["roundness_error_pct"] <= config["roundness_tolerance_pct"])
                        for item in verification
                    ):
                        converged = True
                        break
                    if verification:
                        completed_passes += 1
                        verification_error = max(
                            float(item["centering_worst_px"] if config.get("alignment_objective") == "centering"
                                  else item["roundness_error_pct"])
                            for item in verification
                        )
                        minimum_improvement = float(
                            config["centering_minimum_improvement_px"]
                            if config.get("alignment_objective") == "centering"
                            else config.get("stagnation_min_improvement_pct", 5.0))
                        if (
                            verification_error
                            < best_verification_error - minimum_improvement
                        ):
                            best_verification_error = verification_error
                            # The improving pass begins a new plateau series.
                            stagnant_passes = 1
                        else:
                            stagnant_passes += 1
                        self._search_progress.update({
                            "completed_passes": completed_passes,
                            "stagnant_passes": stagnant_passes,
                            "stagnation_pass_limit": int(config.get(
                                "stagnation_pass_limit", 5
                            )),
                            "verification_error_pct": verification_error,
                            "best_verification_error_pct": (
                                best_verification_error
                            ),
                        })
                        if stagnant_passes >= int(config.get(
                            "stagnation_pass_limit", 5
                        )):
                            stopped_for_stagnation = True
                            break
                if converged or stopped_for_stagnation:
                    break

            if stopped_for_stagnation:
                self._search_status = ("finished; no centering improvement" if config.get("alignment_objective") == "centering"
                                       else "finished; no roundness improvement")
                self._search_progress = {
                    **self._search_progress,
                    "phase": "stopped_no_improvement",
                    "converged": False,
                    "verification": verification,
                    "results": results,
                    "session_id": self._search_session_id,
                    "acceptance_required": False,
                    "current_alignment_kept": True,
                    "message": (
                        "Stopped after "
                        f"{stagnant_passes} complete near/far passes without "
                        "meaningful roundness improvement; current best "
                        "alignment is kept"
                    ),
                }
                self._record_alignment_event(
                    "search_stopped_no_improvement",
                    converged=False,
                    completed_passes=completed_passes,
                    stagnant_passes=stagnant_passes,
                    best_verification_error_pct=best_verification_error,
                )
                return

            restore_point = config["restore_point"]
            if restore_point:
                if restore_point not in self.controller_rules:
                    raise ValueError(f"unknown restore_point {restore_point!r}")
                self._apply_point(restore_point, config)

            self._search_progress = {
                "phase": "finished" if converged else "not_converged",
                "alignment_objective": config.get("alignment_objective", "roundness"),
                "centering_converged": converged if config.get("alignment_objective") == "centering" else None,
                "ellipticity_passed": (all(v["ellipticity_passed"] for v in verification)
                                       if config.get("alignment_objective") == "centering" and verification else None),
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
            if converged:
                revision = self._accept_pending_alignment_reference({
                    "client": "automatic-search",
                    "automatic": True,
                })
                self._search_status = "finished"
                self._search_progress = {
                    **self._search_progress,
                    "phase": "finished",
                    "acceptance_required": False,
                    "accepted_reference_revision": revision,
                    "message": (
                        f"Reference r{revision} saved automatically"
                    ),
                }
                self._record_alignment_event(
                    "search_completed",
                    converged=True,
                    acceptance_required=False,
                    reference_revision=revision,
                )
            else:
                self._search_status = "not converged; awaiting operator decision"
                self._record_alignment_event(
                    "search_completed",
                    converged=False,
                    acceptance_required=True,
                )
        except api.SearchCancelled:
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
                    "phase": "cancelled_keep_current",
                    "results": results,
                    "session_id": self._search_session_id,
                    "message": (
                        "Automatic search stopped; latest measured-good "
                        "alignment is kept"
                    ),
                }
                self._search_status = "cancelled; current alignment kept"
                self._record_alignment_event("search_cancelled_keep_current")
        except api.LaserNotVisible as error:
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

    def _point_stages(self, config: api.Dict):
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

    def _validate_camera_verified_roles(self, config: api.Dict, stages) -> None:
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

    def _adaptive_model_key(self, group_name: str, point_name: str) -> str:
        camera = str(
            (getattr(self, "ds_dict", None) or {}).get(
                "Camera", "unknown-camera"
            )
        ).lower()
        return "|".join((
            camera,
            str(point_name).strip().lower(),
            str(group_name).strip().lower(),
        ))

    def _hardware_probe_step_limit(self, point_name: str) -> api.Optional[float]:
        """Return a non-overridable limit for a sensitive optical path."""

        camera = str(
            (getattr(self, "ds_dict", None) or {}).get("Camera", "")
        ).lower()
        point = str(point_name).strip().lower()
        if "cam2" in camera and point == "point6":
            return 0.5
        return None

    def _adaptive_step_limit(
        self,
        group_name: str,
        point_name: str,
        requested_step: float,
        config: api.Dict,
    ) -> float:
        upper_limit = float(requested_step)
        configured = config.get("point_step_limits", {}).get(
            str(point_name).strip().lower()
        )
        if configured is not None:
            upper_limit = min(upper_limit, float(configured))
        hardware_limit = self._hardware_probe_step_limit(point_name)
        if hardware_limit is not None:
            upper_limit = min(upper_limit, hardware_limit)
        limit = upper_limit
        if config.get("adaptive_learning", True):
            model = getattr(self, "_adaptive_search_model", {}).get(
                self._adaptive_model_key(group_name, point_name), {}
            )
            learned = model.get("safe_step")
            if learned is not None:
                limit = min(limit, float(learned))
        return min(
            upper_limit,
            max(float(config.get("adaptive_min_step", 0.125)), limit),
        )

    def _adaptive_probe_repetitions(
        self, point_name: str, config: api.Dict
    ) -> int:
        point = str(point_name).strip().lower()
        configured = config.get("point_probe_repetitions", {}).get(point)
        if configured is not None:
            return int(configured)
        # Repetition multiplies the displacement from the round centre. Never
        # do that on an explicitly hardware-limited long-path observation.
        if self._hardware_probe_step_limit(point_name) is not None:
            return 1
        return int(config["probe_repetitions"])

    return {
        "_store_pending_reference": _store_pending_reference,
        "_clear_pending_reference": _clear_pending_reference,
        "_restore_completed_alignment_worker": _restore_completed_alignment_worker,
        "_alignment_acceptance_is_pending": _alignment_acceptance_is_pending,
        "_normalise_search_config": _normalise_search_config,
        "_automatic_search_worker": _automatic_search_worker,
        "_point_stages": _point_stages,
        "_validate_camera_verified_roles": _validate_camera_verified_roles,
        "_less_sensitive_point": _less_sensitive_point,
        "_adaptive_model_key": _adaptive_model_key,
        "_hardware_probe_step_limit": _hardware_probe_step_limit,
        "_adaptive_step_limit": _adaptive_step_limit,
        "_adaptive_probe_repetitions": _adaptive_probe_repetitions,
    }
