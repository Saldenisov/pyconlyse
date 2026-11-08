"""Implementation for _active_pair_is_ready and related operations."""


def _bind_laser_pointing_widget_methods_active_pair_is_ready(api):
    """Bind implementation to the owning module and its runtime state."""

    def _active_pair_is_ready(self, group_index):
        if group_index not in (1, 2):
            return False
        role_groups = getattr(self, "_actuator_role_groups", ())
        if group_index > len(role_groups):
            return False
        for role in role_groups[group_index - 1]:
            widget = self.widgets.get(role)
            device = getattr(widget, "ds", None)
            if device is None:
                return False
            try:
                connection = str(device.hardware_connection_state).strip().upper()
                initialization = str(device.initialization_state).strip().upper()
                state = str(device.getDeviceProxy().state()).strip().upper()
                state = state.rsplit(".", 1)[-1]
            except Exception:
                return False
            if (
                connection != "READY"
                and initialization != "SUCCEEDED"
                and state not in {"ON", "MOVING", "RUNNING"}
            ):
                return False
        return True

    def _update_pair_initialization_controls(self, status=None):
        button = getattr(self, "initialize_pair_button", None)
        label = getattr(self, "initialize_pair_status", None)
        if button is None:
            return
        group_index = getattr(self, "_active_actuator_group", 0)
        ready = self._active_pair_is_ready(group_index)
        button.setText(
            f"Initialize Standa pair {group_index}"
            if group_index in (1, 2)
            else "Initialize active pair"
        )
        button.setEnabled(
            self._pair_initialization_supported
            and group_index in (1, 2)
            and not self._pair_initialization_busy
            and not self._point_apply_busy
            and not self._search_running
        )
        if label is not None:
            if status:
                label.setText(str(status))
            elif not self._pair_initialization_supported:
                label.setText("Restart DS_LaserPointing to enable this command")
            elif group_index not in (1, 2):
                label.setText("Select point 1–3 or 4–6 first")
            elif ready:
                label.setText(f"Pair {group_index} is initialised")
            elif not self._pair_initialization_busy:
                label.setText(
                    f"Pair {group_index} selected; axes will initialise X then Y"
                )

    def initialize_active_pair(self):
        group_index = self._active_actuator_group
        if group_index not in (1, 2) or self._pair_initialization_busy:
            return
        self._pair_initialization_busy = True
        self._set_point_buttons_enabled(False)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(False)
        self._update_pair_initialization_controls(
            f"Initialising pair {group_index} sequentially…"
        )
        self.set_active_actuator_group(
            group_index,
            f"Initialising Standa pair {group_index}; movement is locked",
        )

        def initialise():
            try:
                result = getattr(
                    self, f"ds_{self.dev_name}"
                ).initialize_active_pair()
                if result not in (None, 0):
                    raise RuntimeError(f"controller returned {result}")
                self.pair_initialization_finished.emit(True, "")
            except Exception as error:
                self.pair_initialization_finished.emit(False, str(error))

        api.Thread(
            target=initialise,
            name=f"{self.dev_name}-initialize-pair-{group_index}",
            daemon=True,
        ).start()

    def _finish_active_pair_initialization(self, success, message):
        self._pair_initialization_busy = False
        self._set_point_buttons_enabled(not self._search_running)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(not self._search_running)
        group_index = self._active_actuator_group
        if success:
            self._update_pair_initialization_controls(
                f"Standa pair {group_index} initialised"
            )
            self.set_active_actuator_group(group_index)
        else:
            self._update_pair_initialization_controls(
                f"Initialisation failed: {message}"
            )
            self.set_active_actuator_group(
                group_index,
                f"Standa pair {group_index} failed to initialise; movement remains locked",
            )

    def hide_update_param_buttons(self):
        for button in self.findChildren(api.QtWidgets.QAbstractButton):
            if button.text().strip().lower() == "update param":
                button.hide()

    def add_automatic_search_controls(self, layout, ds):
        """Add non-blocking controls for the controller-side search worker."""
        group = api.QtWidgets.QGroupBox("Automatic alignment")
        form = api.QtWidgets.QGridLayout(group)

        self.search_mode = api.QtWidgets.QComboBox()
        self.search_mode.addItem("Staged: 2/5 then 3/6", "staged")
        self.search_mode.addItem("Sensitive: 3/6", "sensitive")
        self.search_mode.addItem("Medium: 2/5", "medium")

        def double_spin(value, minimum, maximum, decimals=2):
            widget = api.QtWidgets.QDoubleSpinBox()
            widget.setRange(minimum, maximum)
            widget.setDecimals(decimals)
            widget.setValue(value)
            widget.setMaximumWidth(60)
            return widget

        defaults = {}
        try:
            defaults = api.json.loads(str(ds.automatic_search_config))
        except Exception:
            pass

        mode_index = self.search_mode.findData(defaults.get("mode", "sensitive"))
        self.search_mode.setCurrentIndex(max(0, mode_index))
        schedule = list(defaults.get("step_schedule", [10.0, 6.0, 2.0]))
        if len(schedule) != 3:
            schedule = [10.0, 6.0, 2.0]
        self.search_step_coarse = double_spin(schedule[0], 0.1, 50.0, 2)
        self.search_step_middle = double_spin(schedule[1], 0.1, 50.0, 2)
        self.search_step_fine = double_spin(schedule[2], 0.1, 50.0, 2)
        self.search_radius = double_spin(defaults.get("radius", 30.0), 0.1, 100.0, 2)
        self.search_tolerance = double_spin(
            defaults.get("roundness_tolerance_pct", 7.0), 0.0, 100.0, 2
        )

        self.search_evaluations = api.QtWidgets.QSpinBox()
        self.search_evaluations.setRange(1, 500)
        self.search_evaluations.setValue(defaults.get("max_evaluations", 16))
        self.search_samples = api.QtWidgets.QSpinBox()
        self.search_samples.setRange(1, 5)
        self.search_samples.setValue(defaults.get("samples", 3))
        self.search_max_cycles = max(1, int(defaults.get("max_cycles", 2)))

        self.search_evaluations.setMaximumWidth(60)
        self.search_samples.setMaximumWidth(60)

        form.addWidget(api.QtWidgets.QLabel("Sequence"), 0, 0)
        form.addWidget(self.search_mode, 0, 1, 1, 3)
        form.addWidget(api.QtWidgets.QLabel("Steps"), 1, 0)
        form.addWidget(self.search_step_coarse, 1, 1)
        form.addWidget(self.search_step_middle, 1, 2)
        form.addWidget(self.search_step_fine, 1, 3)
        form.addWidget(api.QtWidgets.QLabel("Radius"), 2, 0)
        form.addWidget(self.search_radius, 2, 1)
        form.addWidget(api.QtWidgets.QLabel("Round err. %"), 2, 2)
        form.addWidget(self.search_tolerance, 2, 3)
        form.addWidget(api.QtWidgets.QLabel("Evals"), 3, 0)
        form.addWidget(self.search_evaluations, 3, 1)
        form.addWidget(api.QtWidgets.QLabel("Frames"), 3, 2)
        form.addWidget(self.search_samples, 3, 3)

        self.search_start = api.QtWidgets.QPushButton("Start automatic search")
        self.search_pause = api.QtWidgets.QPushButton("Pause")
        self.search_resume = api.QtWidgets.QPushButton("Continue")
        self.search_cancel = api.QtWidgets.QPushButton("Cancel — keep current")
        self.search_stop = api.QtWidgets.QPushButton("Cancel + restore")
        self.search_cancel.setToolTip(
            "Stop at the latest measured-good alignment without restoring "
            "the pre-search state"
        )
        self.search_stop.setToolTip(
            "Stop and restore every actuator and optic captured before search"
        )
        self.search_accept = api.QtWidgets.QPushButton("Accept as next-day reference")
        self.search_pause.setEnabled(False)
        self.search_resume.setEnabled(False)
        self.search_cancel.setEnabled(False)
        self.search_stop.setEnabled(False)
        self.search_accept.setEnabled(False)
        self.search_status = api.QtWidgets.QLabel("idle")
        self.search_status.setWordWrap(True)
        form.addWidget(self.search_start, 4, 0, 1, 2)
        form.addWidget(self.search_pause, 4, 2)
        form.addWidget(self.search_resume, 4, 3)
        form.addWidget(self.search_cancel, 5, 0, 1, 2)
        form.addWidget(self.search_stop, 5, 2, 1, 2)
        form.addWidget(self.search_accept, 6, 0, 1, 4)
        form.addWidget(self.search_status, 7, 0, 1, 4)
        self.search_reference = api.QtWidgets.QLabel("Stored reference: none")
        self.search_reference.setWordWrap(True)
        self.search_reference.setStyleSheet(
            "color: #52657b; background: #f6f9fc; border: 1px solid #cbd7e5; "
            "border-radius: 4px; padding: 4px;"
        )
        form.addWidget(self.search_reference, 8, 0, 1, 4)

        self.convergence_plot = api.pg.PlotWidget()
        self.convergence_plot.setBackground("#ffffff")
        self.convergence_plot.setMinimumHeight(145)
        self.convergence_plot.setMaximumHeight(185)
        self.convergence_plot.setTitle(
            "Convergence over time", color="#24364b", size="10pt"
        )
        self.convergence_plot.setLabel("left", "Roundness error", units="%")
        self.convergence_plot.setLabel("bottom", "Elapsed time", units="s")
        self.convergence_plot.showGrid(x=True, y=True, alpha=0.2)
        self.convergence_plot.addLegend(offset=(8, 8), labelTextColor="#24364b")
        group1_label = (
            "Near plane · Standa 1"
            if getattr(self, "has_translation_planes", False)
            else "Diaphragm 1 · Standa 1"
        )
        group2_label = (
            "Far plane · Standa 2"
            if getattr(self, "has_translation_planes", False)
            else "Diaphragm 2 · Standa 2"
        )
        self.convergence_line = self.convergence_plot.plot(
            [], [], pen=api.pg.mkPen("#7b8794", width=1.5)
        )
        self.convergence_group1 = self.convergence_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#2378c3", symbolPen="#174f82",
            name=group1_label,
        )
        self.convergence_group2 = self.convergence_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#e38b2c", symbolPen="#985916",
            name=group2_label,
        )
        self.convergence_tolerance = api.pg.InfiniteLine(
            pos=self.search_tolerance.value(), angle=0,
            pen=api.pg.mkPen("#2f9e44", width=1, style=api.QtCore.Qt.DashLine),
        )
        self.convergence_plot.addItem(self.convergence_tolerance)
        form.addWidget(self.convergence_plot, 9, 0, 1, 4)

        self.search_start.clicked.connect(self.start_automatic_search)
        self.search_pause.clicked.connect(self.pause_automatic_search)
        self.search_resume.clicked.connect(self.resume_automatic_search)
        self.search_cancel.clicked.connect(self.cancel_automatic_search)
        self.search_stop.clicked.connect(self.stop_automatic_search)
        self.search_accept.clicked.connect(self.accept_alignment_reference)
        layout.addWidget(group)

        self.search_timer = api.Qt.QTimer(self)
        self.search_timer.timeout.connect(self.update_automatic_search_status)
        self.search_timer.start(500)

    def add_delta_coordinates_view(self, layout):
        """Place the directional centroid mismatch directly below the camera."""

        group = api.QtWidgets.QGroupBox("Centroid diagnostic")
        group.setObjectName("laserPointingCentroidDiagnostic")
        group.setToolTip(
            "ΔX and ΔY compare the current contour centre with the first "
            "measurement at this point. Automatic alignment optimizes "
            "concentric-contour symmetry, not this displacement."
        )
        group_layout = api.QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(6, 5, 6, 6)
        group_layout.setSpacing(4)

        metrics = api.QtWidgets.QHBoxLayout()
        metrics.setSpacing(6)
        self.delta_x_value = api.QtWidgets.QLabel("ΔX  — px")
        self.delta_y_value = api.QtWidgets.QLabel("ΔY  — px")
        self.delta_norm_value = api.QtWidgets.QLabel("|Δ|  — px")
        for label, colour in (
            (self.delta_x_value, "#1f6fb2"),
            (self.delta_y_value, "#c56f15"),
            (self.delta_norm_value, "#7a2e8e"),
        ):
            label.setAlignment(api.QtCore.Qt.AlignCenter)
            label.setStyleSheet(
                "background: #f4f7fa; border: 1px solid #d6dde6; "
                f"border-radius: 4px; color: {colour}; font-weight: 600; padding: 4px;"
            )
            metrics.addWidget(label)
        group_layout.addLayout(metrics)

        self.delta_plot = api.pg.PlotWidget()
        self.delta_plot.setBackground("#ffffff")
        self.delta_plot.setMinimumHeight(210)
        self.delta_plot.setMaximumHeight(280)
        self.delta_plot.setLabel("bottom", "ΔX", units="px")
        self.delta_plot.setLabel("left", "ΔY", units="px")
        self.delta_plot.showGrid(x=True, y=True, alpha=0.18)
        self.delta_plot.setAspectLocked(True, ratio=1)
        self.delta_plot.addLegend(offset=(8, 8), labelTextColor="#24364b")
        self.delta_plot.addItem(
            api.pg.InfiniteLine(
                pos=0, angle=90, pen=api.pg.mkPen("#aeb7c2", width=1)
            )
        )
        self.delta_plot.addItem(
            api.pg.InfiniteLine(
                pos=0, angle=0, pen=api.pg.mkPen("#aeb7c2", width=1)
            )
        )
        self.delta_tolerance_curve = self.delta_plot.plot(
            [], [], pen=api.pg.mkPen("#2f9e44", width=1.5, style=api.QtCore.Qt.DashLine),
            name="2 px display guide",
        )
        self.delta_trajectory = self.delta_plot.plot(
            [], [], pen=api.pg.mkPen("#7b8794", width=1.5)
        )
        self.delta_group1 = self.delta_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#2378c3", symbolPen="#174f82", name="Pair 1",
        )
        self.delta_group2 = self.delta_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#e38b2c", symbolPen="#985916", name="Pair 2",
        )
        self.delta_current_vector = self.delta_plot.plot(
            [], [], pen=api.pg.mkPen("#b3261e", width=2)
        )
        self.delta_current_point = self.delta_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=11,
            symbolBrush="#ffffff", symbolPen=api.pg.mkPen("#b3261e", width=2),
        )
        group_layout.addWidget(self.delta_plot)

        hint = api.QtWidgets.QLabel(
            "Display only · alignment minimizes beam roundness error"
        )
        hint.setAlignment(api.QtCore.Qt.AlignCenter)
        hint.setStyleSheet("color: #647386; font-size: 9px;")
        group_layout.addWidget(hint)
        layout.addWidget(group)
        self.update_convergence_plot([], {})

    def start_automatic_search(self):
        if self._point_apply_busy or self._pair_initialization_busy:
            self.search_status.setText("Wait until the optical point has finished applying")
            return
        step_schedule = [
            self.search_step_coarse.value(),
            self.search_step_middle.value(),
            self.search_step_fine.value(),
        ]
        if not step_schedule[0] > step_schedule[1] > step_schedule[2]:
            self.search_status.setText(
                "Coarse, middle, and fine steps must be strictly decreasing"
            )
            return
        config = {
            "mode": self.search_mode.currentData(),
            "initial_step": step_schedule[0],
            "minimum_step": step_schedule[-1],
            "step_schedule": step_schedule,
            "radius": self.search_radius.value(),
            "roundness_tolerance_pct": self.search_tolerance.value(),
            "max_evaluations": self.search_evaluations.value(),
            "samples": self.search_samples.value(),
            "max_cycles": self.search_max_cycles,
        }
        previous_group = self._active_actuator_group
        try:
            self._search_running = True
            self._set_automatic_contour_overlay(True)
            self.set_active_actuator_group(
                0, "Automatic search owns both mount pairs; manual movement is locked"
            )
            self._set_point_buttons_enabled(False)
            result = getattr(self, f"ds_{self.dev_name}").start_automatic_search(
                api.json.dumps(config)
            )
            if result not in (None, 0):
                self.search_status.setText("Search is already running or configuration is invalid")
                self._search_running = False
                self._set_automatic_contour_overlay(False)
                self.set_active_actuator_group(previous_group)
                self._set_point_buttons_enabled(True)
        except Exception as error:
            self._search_running = False
            self._set_automatic_contour_overlay(False)
            self.set_active_actuator_group(previous_group)
            self.search_status.setText(f"Could not start: {error}")
        self.update_automatic_search_status()

    def stop_automatic_search(self):
        try:
            getattr(self, f"ds_{self.dev_name}").stop_automatic_search()
        except Exception as error:
            self.search_status.setText(f"Could not cancel and restore: {error}")
        self.update_automatic_search_status()

    def cancel_automatic_search(self):
        try:
            getattr(self, f"ds_{self.dev_name}").cancel_automatic_search()
        except Exception as error:
            self.search_status.setText(f"Could not cancel: {error}")
        self.update_automatic_search_status()

    def pause_automatic_search(self):
        try:
            getattr(self, f"ds_{self.dev_name}").pause_automatic_search()
        except Exception as error:
            self.search_status.setText(f"Could not pause: {error}")
        self.update_automatic_search_status()

    def resume_automatic_search(self):
        try:
            getattr(self, f"ds_{self.dev_name}").resume_automatic_search()
        except Exception as error:
            self.search_status.setText(f"Could not continue: {error}")
        self.update_automatic_search_status()

    def accept_alignment_reference(self):
        try:
            ds = getattr(self, f"ds_{self.dev_name}")
            metadata = api.json.dumps({"client": "pyqt5"})
            if getattr(self, "_has_pending_reference", False):
                revision = ds.accept_alignment_reference(metadata)
                action = "Accepted"
            else:
                revision = ds.save_current_alignment_reference(metadata)
                action = "Saved current manual"
            self.search_status.setText(
                f"{action} alignment reference revision {revision}"
            )
        except Exception as error:
            self.search_status.setText(f"Could not save reference: {error}")
        self.update_automatic_search_status()

    def update_automatic_search_status(self):
        try:
            ds = getattr(self, f"ds_{self.dev_name}")
            if not self._pair_initialization_supported:
                self._refresh_pair_initialization_capability(ds)
            status = str(ds.automatic_search_status)
            progress = api.json.loads(str(ds.automatic_search_progress) or "{}")
            try:
                history = api.json.loads(str(ds.automatic_search_history) or "[]")
            except Exception:
                history = []
            try:
                pending_reference = api.json.loads(
                    str(ds.alignment_pending_reference_json) or "{}"
                )
            except Exception:
                pending_reference = {}
            try:
                reference = api.json.loads(str(ds.alignment_reference_json) or "{}")
                revision = int(ds.alignment_reference_revision)
            except Exception:
                reference = {}
                revision = 0
            try:
                active_point = str(ds.active_point)
            except Exception:
                active_point = ""
            self.update_convergence_plot(history, progress)
            detail = ""
            if progress.get("message"):
                detail = f" — {progress['message']}"
            elif progress.get("group"):
                detail = (
                    f" — {progress.get('stage')} {progress.get('group')}, "
                    f"step {progress.get('motor_step', '?')}, "
                    f"roundness error "
                    f"{progress.get('roundness_error_pct', progress.get('error_px', 0)):.2f}%"
                )
            self.search_status.setText(status + detail)
            running = status in (
                "running", "pausing", "paused", "cancelling", "restoring",
                "cancelling; keeping current",
            )
            paused = status in ("pausing", "paused")
            cancelling = status in (
                "cancelling", "restoring", "cancelling; keeping current"
            )
            self._set_automatic_contour_overlay(
                status in ("running", "pausing", "paused")
            )
            session_locked = running or bool(pending_reference)
            self._has_pending_reference = bool(pending_reference)
            self._search_running = session_locked
            self.search_start.setEnabled(
                not session_locked and not self._point_apply_busy
            )
            self.search_pause.setEnabled(running and not paused and not cancelling)
            self.search_resume.setEnabled(paused and not cancelling)
            self.search_cancel.setEnabled(
                (running or bool(pending_reference)) and not cancelling
            )
            self.search_stop.setEnabled(
                (running or bool(pending_reference)) and not cancelling
            )
            if pending_reference:
                self.search_accept.setText("Accept as next-day reference")
            else:
                self.search_accept.setText(
                    "Save current manual alignment as next-day reference"
                )
            self.search_accept.setEnabled(
                not running
                and not cancelling
                and not self._point_apply_busy
                and not self._pair_initialization_busy
            )
            if reference:
                positions = ", ".join(
                    f"{role} {float(axis.get('position', 0)):.3f}"
                    for role, axis in reference.get("actuators", {}).items()
                )
                self.search_reference.setText(
                    f"Stored reference r{revision} · "
                    f"{reference.get('accepted_at_utc', 'saved')} · {positions}"
                )
            else:
                self.search_reference.setText("Stored reference: none")
            self._set_point_buttons_enabled(
                not session_locked and not self._point_apply_busy
            )
            if running:
                self.set_active_actuator_group(
                    0,
                    "Automatic search owns both mount pairs; manual movement is locked",
                )
            elif pending_reference:
                self.set_active_actuator_group(
                    0,
                    "Accept, keep current, or restore the pre-search alignment",
                )
            elif not self._point_apply_busy:
                buttons = self._point_buttons(active_point)
                if buttons:
                    for button in buttons:
                        button.setChecked(True)
                else:
                    self._clear_point_selection()
                self.set_active_actuator_group(api.optical_point_group(active_point))
        except Exception:
            # The controller may be temporarily unavailable during server restart.
            pass

    def _set_automatic_contour_overlay(self, enabled):
        camera = self.widgets.get("Camera")
        if camera is not None and hasattr(
            camera, "set_automatic_contour_overlay"
        ):
            camera.set_automatic_contour_overlay(enabled)

    return {
        "_active_pair_is_ready": _active_pair_is_ready,
        "_update_pair_initialization_controls": _update_pair_initialization_controls,
        "initialize_active_pair": initialize_active_pair,
        "_finish_active_pair_initialization": _finish_active_pair_initialization,
        "hide_update_param_buttons": hide_update_param_buttons,
        "add_automatic_search_controls": add_automatic_search_controls,
        "add_delta_coordinates_view": add_delta_coordinates_view,
        "start_automatic_search": start_automatic_search,
        "stop_automatic_search": stop_automatic_search,
        "cancel_automatic_search": cancel_automatic_search,
        "pause_automatic_search": pause_automatic_search,
        "resume_automatic_search": resume_automatic_search,
        "accept_alignment_reference": accept_alignment_reference,
        "update_automatic_search_status": update_automatic_search_status,
        "_set_automatic_contour_overlay": _set_automatic_contour_overlay,
    }
