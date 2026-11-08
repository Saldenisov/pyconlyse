"""Implementation for _adaptive_direction_order and related operations."""


def _bind_laser_pointing_methods_adaptive_direction_order(api):
    """Bind implementation to the owning module and its runtime state."""

    def _adaptive_direction_order(
        self, group_name: str, point_name: str, actuator_roles
    ):
        directions = [
            (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)
        ]
        if not getattr(self, "_adaptive_search_model", None):
            return directions
        model = self._adaptive_search_model.get(
            self._adaptive_model_key(group_name, point_name), {}
        )
        axes = model.get("axes", {})

        def learned_value(direction):
            axis = 0 if direction[0] else 1
            sign = "positive" if direction[axis] > 0 else "negative"
            statistics = axes.get(str(actuator_roles[axis]), {}).get(sign, {})
            return float(statistics.get("mean_improvement_per_step", 0.0))

        return sorted(directions, key=learned_value, reverse=True)

    def _update_running_mean(statistics: api.Dict, name: str, value: float) -> None:
        count_name = f"{name}_samples"
        count = int(statistics.get(count_name, 0)) + 1
        old_mean = float(statistics.get(name, 0.0))
        statistics[name] = old_mean + (float(value) - old_mean) / count
        statistics[count_name] = count

    def _persist_adaptive_search_model(self) -> None:
        encoded = api.json.dumps(
            getattr(self, "_adaptive_search_model", {}),
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            self._persist_alignment_properties({
                "adaptive_search_model_property": encoded,
            })
        except Exception as error:
            warning = getattr(self, "warn_stream", None)
            if warning is not None:
                warning(f"Could not persist adaptive search model: {error}")
        self._push_alignment_value("adaptive_search_model_json", encoded)

    def _learn_from_probe(
        self,
        group_name: str,
        point_name: str,
        actuator_roles,
        previous_position,
        target_position,
        score_before,
        score_after,
        shape_before,
        shape_after,
        visible: bool,
        requested_step: float,
        config: api.Dict,
        error="",
    ) -> None:
        if not config.get("adaptive_learning", True):
            return
        deltas = [
            float(target) - float(previous)
            for target, previous in zip(target_position, previous_position)
        ]
        displacement = max(abs(delta) for delta in deltas)
        if displacement <= 1.0e-12:
            return

        key = self._adaptive_model_key(group_name, point_name)
        models = getattr(self, "_adaptive_search_model", None)
        if models is None:
            models = {}
            self._adaptive_search_model = models
        model = models.setdefault(key, {
            "camera": str(
                (getattr(self, "ds_dict", None) or {}).get("Camera", "")
            ),
            "point": str(point_name),
            "group": str(group_name),
            "axes": {},
            "successful_probes": 0,
            "failed_visibility_probes": 0,
        })

        hardware_limit = self._hardware_probe_step_limit(point_name)
        configured_limit = config.get("point_step_limits", {}).get(
            str(point_name).strip().lower(), float(requested_step)
        )
        maximum_step = min(float(requested_step), float(configured_limit))
        if hardware_limit is not None:
            maximum_step = min(maximum_step, hardware_limit)
        minimum_step = float(config.get("adaptive_min_step", 0.125))
        safe_step = min(
            maximum_step,
            float(model.get("safe_step", maximum_step)),
        )
        improvement = None
        if score_before is not None and score_after is not None:
            improvement = float(score_before) - float(score_after)

        for role, delta in zip(actuator_roles, deltas):
            if abs(delta) <= 1.0e-12:
                continue
            direction = "positive" if delta > 0 else "negative"
            statistics = model["axes"].setdefault(str(role), {}).setdefault(
                direction,
                {"probes": 0, "visible_probes": 0, "lost_beam_probes": 0},
            )
            statistics["probes"] += 1
            if visible:
                statistics["visible_probes"] += 1
            else:
                statistics["lost_beam_probes"] += 1
            if improvement is not None:
                self._update_running_mean(
                    statistics,
                    "mean_improvement_per_step",
                    improvement / abs(delta),
                )

        if not visible:
            model["failed_visibility_probes"] = int(
                model.get("failed_visibility_probes", 0)
            ) + 1
            safe_step = max(
                minimum_step,
                min(safe_step, displacement)
                * float(config.get("adaptive_backoff", 0.5)),
            )
        else:
            model["successful_probes"] = int(
                model.get("successful_probes", 0)
            ) + 1
            threshold = float(config.get("minimum_improvement_px", 0.1))
            # A visible but worse directional probe is an ordinary optimizer
            # rejection, not evidence that the travel was unsafe. Halving the
            # persistent limit here made cardinal probes collapse every later
            # coarse pass to the minimum step. Only visibility loss backs off;
            # the bounded search already rejects worse optical scores.
            if improvement is not None and improvement >= threshold:
                safe_step = min(
                    maximum_step,
                    max(safe_step, displacement)
                    * float(config.get("adaptive_growth", 1.15)),
                )

        before_centre = (shape_before or {}).get("shape_centroid")
        after_centre = (shape_after or {}).get("shape_centroid")
        model["safe_step"] = min(maximum_step, safe_step)
        model["maximum_step"] = maximum_step
        model["last_probe"] = {
            "recorded_at_utc": self._utc_now(),
            "roles": list(actuator_roles),
            "from": [float(value) for value in previous_position],
            "to": [float(value) for value in target_position],
            "delta": deltas,
            "visible": bool(visible),
            "roundness_error_before": score_before,
            "roundness_error_after": score_after,
            "roundness_improvement": improvement,
            "contour_centre_before": before_centre,
            "contour_centre_after": after_centre,
            "error": str(error),
        }
        self._persist_adaptive_search_model()

    def _aperture_sweep_spec(self, point_pair):
        """Find the one diaphragm changed between an open/closed point pair."""

        rules = getattr(self, "controller_rules", None) or {}
        open_point, closed_point = tuple(point_pair)
        open_rule = rules.get(open_point, {})
        closed_rule = rules.get(closed_point, {})
        candidates = []
        for role in set(open_rule).intersection(closed_rule):
            if "diaphragm" not in str(role).lower():
                continue
            try:
                open_value = float(open_rule[role])
                closed_value = float(closed_rule[role])
            except (TypeError, ValueError):
                continue
            if open_value > closed_value:
                candidates.append((role, closed_value, open_value))
        if not candidates:
            return None
        if len(candidates) > 1:
            raise ValueError(
                f"{open_point}/{closed_point} changes more than one diaphragm"
            )
        return candidates[0]

    def _measure_aperture_cycle(self, point_pair, config: api.Dict):
        """Measure ring symmetry while opening and repeatedly cycling an iris."""

        target_point = point_pair[-1]
        centering_mode = config.get("alignment_objective") == "centering"
        check_pair = centering_mode and config.get("centering_check_aperture_pair", True)
        sweep_enabled = config.get("aperture_sweep_enabled", True)
        if not sweep_enabled and not check_pair:
            centroid = self._measure_point(target_point, config)
            return centroid
        specification = self._aperture_sweep_spec(point_pair)
        if specification is None:
            centroid = self._measure_point(target_point, config)
            return centroid

        role, closed_value, open_value = specification
        device = self._device_for_role(role)
        sample_config = {
            **config,
            "samples": int(config["samples"] if centering_mode else config.get("aperture_samples", 1)),
        }
        positions = api.np.linspace(
            closed_value,
            open_value,
            int(config.get("aperture_sweep_positions", 4)),
        )
        records = []
        current_value = closed_value

        def capture(value, phase, cycle=0, move=True):
            nonlocal current_value
            self._raise_if_cancelled()
            if move:
                self._search_progress.update({
                    "phase": "cycling_aperture",
                    "point": target_point,
                    "aperture_role": role,
                    "aperture_position": float(value),
                    "aperture_cycle": int(cycle),
                    "message": (
                        f"{phase}: moving {role} to {float(value):.3f}%"
                    ),
                })
                self._move_single_axis(device, float(value), config)
                current_value = float(value)
            centroid = self._measure_point(target_point, sample_config)
            shape = self._read_beam_shape()
            records.append({
                "phase": phase,
                "cycle": int(cycle),
                "aperture_position": float(value),
                "centroid": [float(centroid[0]), float(centroid[1])],
                "shape": shape,
            })

        try:
            capture(closed_value, "Closed reference", move=False)
            if sweep_enabled:
                for index, value in enumerate(positions[1:], start=2):
                    capture(value, f"Opening aperture {index}/{len(positions)}")
                for cycle in range(1, int(config.get("aperture_cycle_count", 2)) + 1):
                    capture(closed_value, "Closing aperture", cycle=cycle)
                    capture(open_value, "Opening aperture", cycle=cycle)
            else:
                capture(open_value, "Open aperture endpoint")
            capture(
                closed_value,
                "Final closed measurement",
                cycle=int(config.get("aperture_cycle_count", 2)),
            )
        finally:
            # Never leave the iris at an intermediate/open sweep position.
            # Clear cancellation only around this one bounded safety move.
            if abs(float(current_value) - closed_value) > 1.0e-9:
                cancelled = self._search_stop.is_set()
                if cancelled:
                    self._search_stop.clear()
                try:
                    self._move_single_axis(device, closed_value, config)
                    current_value = closed_value
                finally:
                    if cancelled:
                        self._search_stop.set()
            self._active_point = target_point

        centres = api.np.asarray(
            [record["centroid"] for record in records], dtype=float
        )
        common_centre = api.np.median(centres, axis=0)
        centre_drift_px = float(api.np.sqrt(api.np.mean(api.np.sum(
            (centres - common_centre) ** 2, axis=1
        ))))
        contour_errors = [
            float(record["shape"]["roundness_error_pct"])
            for record in records
        ]
        contour_error = float(api.np.median(contour_errors))
        radii = [
            float(record["shape"].get("sigma_major_px", 0.0))
            for record in records
            if float(record["shape"].get("sigma_major_px", 0.0)) > 0
        ]
        reference_radius = float(api.np.median(radii)) if radii else 1.0
        centre_drift_pct = 100.0 * centre_drift_px / reference_radius
        combined_error = min(
            100.0,
            contour_error
            + float(config.get("aperture_drift_weight", 0.5))
            * centre_drift_pct,
        )
        final_shape = dict(records[-1]["shape"])
        final_shape.update({
            "roundness_error_pct": combined_error,
            "roundness_pct": 100.0 - combined_error,
            "shape_centroid": [
                float(common_centre[0]), float(common_centre[1])
            ],
            "contour_roundness_error_pct": contour_error,
            "aperture_centre_drift_px": centre_drift_px,
            "aperture_centre_drift_pct": centre_drift_pct,
            "aperture_role": role,
            "aperture_closed_position": closed_value,
            "aperture_open_position": open_value,
            "aperture_measurement_count": len(records),
            "aperture_trace": [
                {
                    "phase": record["phase"],
                    "cycle": record["cycle"],
                    "position": record["aperture_position"],
                    "centroid": record["centroid"],
                    "roundness_error_pct": float(
                        record["shape"]["roundness_error_pct"]
                    ),
                }
                for record in records
            ],
        })
        if centering_mode:
            internal = max(api.finite_nonnegative(r["shape"]["centering_error_px"], "internal centering error") for r in records)
            if not api.np.isfinite(centres).all():
                raise ValueError("aperture centers must be finite")
            closed_centres = api.np.asarray([r["centroid"] for r in records
                                        if r["aperture_position"] == closed_value], dtype=float)
            closed_centre = api.np.median(closed_centres, axis=0)
            aperture_offset = float(api.np.max(api.np.linalg.norm(centres - closed_centre, axis=1)))
            final_shape.update({
                "centering_internal_error_px": internal,
                "centering_aperture_error_px": aperture_offset,
                "centering_error_px": max(internal, aperture_offset),
                "alignment_centroid": closed_centre.tolist(),
                "aperture_pair_checked": True,
                "centering_method": "ellipse_centres_and_aperture_endpoints",
            })
        self._last_beam_shape = final_shape
        self._search_progress.update({
            "phase": "aperture_cycle_measured",
            "point": target_point,
            "aperture_role": role,
            "aperture_centre_drift_px": centre_drift_px,
            "roundness_error_pct": combined_error,
            "beam_shape": final_shape,
            "message": (
                f"{role} cycle complete: centre drift "
                f"{centre_drift_px:.3f} px, contour error "
                f"{contour_error:.2f}%"
            ),
        })
        return tuple(final_shape["alignment_centroid"] if centering_mode else final_shape["shape_centroid"])

    def _verify_centering_pair(self, point_pair, config):
        measurements = []
        for _ in range(config["measurement_repetitions"]):
            self._raise_if_cancelled()
            self._measure_aperture_cycle(point_pair, config)
            shape = dict(self._read_beam_shape())
            if (point_pair[0] != point_pair[-1] and config["centering_check_aperture_pair"]
                    and not shape.get("aperture_pair_checked")):
                raise RuntimeError("centering verification requires the open/closed aperture pair")
            measurements.append(shape)
        quality = api.centering_verification(measurements, config["centering_tolerance_px"],
                                         config["ellipticity_tolerance_pct"])
        quality["roundness_error_pct"] = float(api.np.median([m["roundness_error_pct"] for m in measurements]))
        return quality

    def _optimise_centering_group(self, group_name, point_pair, stage_name, cycle,
                                  motor_step, config, search_origins):
        roles = self._actuator_roles_for_group(group_name)
        devices = [self._device_for_role(role) for role in roles]
        start = tuple(self._fresh_position_and_state(d)[0] for d in devices)
        origin = search_origins.setdefault(group_name, start)
        bounds = self._search_bounds(devices, origin, config["radius"])
        target_point = point_pair[-1]
        step = self._adaptive_step_limit(group_name, target_point, float(motor_step), config)
        retained = start

        def move(position):
            self._raise_if_cancelled()
            readings = [self._fresh_position_and_state(d) for d in devices]
            if any("ON" not in state or "MOVING" in state for _, state in readings):
                raise RuntimeError("centering measurement requires stationary ON actuators")
            current = tuple(value for value, _ in readings)
            if any(abs(a - b) > config["position_tolerance"] for a, b in zip(current, position)):
                self._move_pair(devices, position, config)

        def measure(position):
            move(position)
            self._search_progress = {"phase": "confirming_centering", "group": group_name,
                                     "point": target_point, "score_metric": "centering_error_px",
                                     "message": "Measuring independent centering repeats; ellipticity is diagnostic"}
            self._measure_aperture_cycle(point_pair, config)
            shape = dict(self._read_beam_shape())
            if (point_pair[0] != point_pair[-1] and config["centering_check_aperture_pair"]
                    and not shape.get("aperture_pair_checked")):
                raise RuntimeError("centering search requires the open/closed aperture pair")
            return shape

        def observe(record):
            nonlocal retained
            if record["confirmed"]:
                retained = tuple(record["position"])
            shapes = record["measurements"]
            observation = {
                "index": len(self._search_history) + 1,
                "elapsed_s": api.monotonic() - self._search_started_at if self._search_started_at else 0.0,
                "group": group_name, "actuator_group": list(self.pid_groups).index(group_name) + 1,
                "stage": stage_name, "cycle": cycle, "motor_step": step,
                "points": list(point_pair), "measured_point": target_point,
                "actuator_position": list(record["position"]),
                "centering_error_px": record["quality"]["median"],
                "ellipticity_error_pct": float(api.np.median([s["ellipticity_error_pct"] for s in shapes])),
                "roundness_error_pct": float(api.np.median([s["roundness_error_pct"] for s in shapes])),
                "score_metric": "centering_error_px", "confirmed": record["confirmed"],
                "confirmation": {k: v for k, v in record.items() if k not in ("measurements", "position")},
            }
            self._search_history.append(observation)
            self._search_progress = {**observation, "phase": "centering_confirmed" if record["confirmed"]
                                     else "centering_probe_rejected", "beam_shape": shapes[-1]}

        parameters = api.SearchParameters(
            initial_step=step, minimum_step=step, step_schedule=(step,),
            tolerance_px=config["centering_tolerance_px"], max_evaluations=config["max_evaluations"],
            minimum_improvement_px=config["centering_minimum_improvement_px"],
            probe_repetitions=self._adaptive_probe_repetitions(target_point, config),
        )
        try:
            result, evidence = api.confirmed_centering_search(
                measure, move, start, bounds, parameters,
                repetitions=config["measurement_repetitions"],
                noise_multiplier=config["confirmation_noise_multiplier"],
                cancelled=self._search_stop.is_set, on_observation=observe,
                step_limit=lambda: self._adaptive_step_limit(group_name, target_point, float(motor_step), config),
            )
        except (api.SearchCancelled, api.CenteringSearchCancelled):
            if not getattr(self, "_restore_on_cancel", True):
                self._search_stop.clear()
                try:
                    move(retained)
                finally:
                    self._search_stop.set()
            raise api.SearchCancelled()
        except Exception:
            move(retained)
            raise
        quality = api.centering_verification(evidence["measurements"], config["centering_tolerance_px"],
                                         config["ellipticity_tolerance_pct"])
        return {"group": group_name, "stage": stage_name, "cycle": cycle,
                "points": list(point_pair), "start_position": list(start),
                "best_position": list(result.best_position), "search_origin": list(origin),
                "best_centering_error_px": result.best_score, "score_metric": "centering_error_px",
                "evaluations": result.evaluations, "reason": result.reason,
                "measurement_count": evidence["measurement_count"], "quality": quality}

    return {
        "_adaptive_direction_order": _adaptive_direction_order,
        "_update_running_mean": _update_running_mean,
        "_persist_adaptive_search_model": _persist_adaptive_search_model,
        "_learn_from_probe": _learn_from_probe,
        "_aperture_sweep_spec": _aperture_sweep_spec,
        "_measure_aperture_cycle": _measure_aperture_cycle,
        "_verify_centering_pair": _verify_centering_pair,
        "_optimise_centering_group": _optimise_centering_group,
    }
