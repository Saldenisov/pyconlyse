"""Implementation for update_convergence_plot and related operations."""


def _bind_laser_pointing_widget_methods_update_convergence_plot(api):
    """Bind implementation to the owning module and its runtime state."""

    def update_convergence_plot(self, history, progress=None):
        """Render roundness error and a non-controlling centroid diagnostic."""

        valid = []
        for observation in history if isinstance(history, list) else []:
            try:
                elapsed = float(observation["elapsed_s"])
                error = float(
                    observation.get(
                        "roundness_error_pct", observation["error_px"]
                    )
                )
                group = int(observation.get("actuator_group", 0))
                delta_x, delta_y = (
                    float(value) for value in observation["delta_px"][:2]
                )
            except (KeyError, TypeError, ValueError):
                continue
            valid.append((elapsed, error, group, delta_x, delta_y))

        if not valid and isinstance(progress, dict):
            try:
                delta_x, delta_y = (
                    float(value) for value in progress["delta_px"][:2]
                )
                error = float(
                    progress.get(
                        "roundness_error_pct",
                        progress.get("error_px", api.math.hypot(delta_x, delta_y)),
                    )
                )
                group_name = str(progress.get("group", ""))
                group = 0
                for index, name in enumerate(getattr(self, "pid_groups", ()), start=1):
                    if str(name) == group_name:
                        group = index
                        break
                valid.append((0.0, error, group, delta_x, delta_y))
            except (KeyError, TypeError, ValueError):
                pass

        times = [item[0] for item in valid]
        errors = [item[1] for item in valid]
        self.convergence_line.setData(times, errors)
        for group_index, curve in (
            (1, self.convergence_group1),
            (2, self.convergence_group2),
        ):
            points = [item for item in valid if item[2] == group_index]
            curve.setData(
                [item[0] for item in points], [item[1] for item in points]
            )
        self.convergence_tolerance.setPos(self.search_tolerance.value())

        if not hasattr(self, "delta_plot"):
            return

        deltas_x = [item[3] for item in valid]
        deltas_y = [item[4] for item in valid]
        self.delta_trajectory.setData(deltas_x, deltas_y)
        for group_index, curve in (
            (1, self.delta_group1),
            (2, self.delta_group2),
        ):
            points = [item for item in valid if item[2] == group_index]
            curve.setData(
                [item[3] for item in points], [item[4] for item in points]
            )

        # This circle is only a visual centroid-displacement guide. The search
        # tolerance above is a percentage shape error and must not control it.
        tolerance = 2.0
        angles = [2 * api.math.pi * index / 100 for index in range(101)]
        self.delta_tolerance_curve.setData(
            [tolerance * api.math.cos(angle) for angle in angles],
            [tolerance * api.math.sin(angle) for angle in angles],
        )
        limit = max(
            5.0,
            tolerance * 1.25,
            *(abs(value) * 1.15 for value in deltas_x + deltas_y),
        )
        self.delta_plot.setXRange(-limit, limit, padding=0)
        self.delta_plot.setYRange(-limit, limit, padding=0)

        if valid:
            delta_x, delta_y = valid[-1][3], valid[-1][4]
            error = api.math.hypot(delta_x, delta_y)
            self.delta_x_value.setText(f"ΔX  {delta_x:+.2f} px")
            self.delta_y_value.setText(f"ΔY  {delta_y:+.2f} px")
            self.delta_norm_value.setText(f"|Δ|  {error:.2f} px")
            self.delta_current_vector.setData([0.0, delta_x], [0.0, delta_y])
            self.delta_current_point.setData([delta_x], [delta_y])
        else:
            self.delta_x_value.setText("ΔX  — px")
            self.delta_y_value.setText("ΔY  — px")
            self.delta_norm_value.setText("|Δ|  — px")
            self.delta_current_vector.setData([], [])
            self.delta_current_point.setData([], [])

    def rb_clicked(self, parameters: api.OrderedDict):
        for ds_role, state in parameters.items():
            ds_widget: api.DS_General_Widget = self.widgets[ds_role]
            if ds_widget and not isinstance(ds_widget, api.QtWidgets.QLabel):
                ds_widget.set_the_control_value(state)

    def set_the_control_value(self, value):
        pass

    def mouseDoubleClickEvent(self, event: api.QMouseEvent):
        self.parent.active_widget = self.dev_name
        self.parent.update_active_widget()

    return {
        "update_convergence_plot": update_convergence_plot,
        "rb_clicked": rb_clicked,
        "set_the_control_value": set_the_control_value,
        "mouseDoubleClickEvent": mouseDoubleClickEvent,
    }
