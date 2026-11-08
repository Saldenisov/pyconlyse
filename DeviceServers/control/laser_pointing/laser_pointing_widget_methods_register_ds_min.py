"""Implementation for register_DS_min and related operations."""


def _bind_laser_pointing_widget_methods_register_ds_min(api):
    """Bind implementation to the owning module and its runtime state."""

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def set_state_status(self, short=True):
        """Build a readable controller header for the composite client.

        The generic DS header is intentionally very compact.  In the two-column
        LaserPointing panel its Taurus labels could therefore shrink to their
        minimum size, leaving only the LED and an ellipsis.  The controller is
        the top-level safety boundary, so keep its identity and state visible.
        """
        dev_name = self.dev_name
        lo_status: api.Qt.QLayout = getattr(self, f"layout_status_{dev_name}")

        header = api.QtWidgets.QFrame()
        header.setObjectName("laserPointingControllerHeader")
        header.setSizePolicy(
            api.QtWidgets.QSizePolicy.Expanding, api.QtWidgets.QSizePolicy.Fixed
        )
        header.setMinimumHeight(54)
        header.setMaximumHeight(62)
        header.setStyleSheet(
            """
            QFrame#laserPointingControllerHeader {
                background-color: #F4F7FA;
                border: 1px solid #C7D1DC;
                border-radius: 5px;
            }
            QLabel#laserPointingPath {
                color: #5B6570;
                font-size: 10px;
                border: none;
                background: transparent;
            }
            QLabel#laserPointingStateCaption {
                color: #5B6570;
                border: none;
                background: transparent;
            }
            """
        )
        row = api.QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(8)

        name_label = api.TaurusLabel()
        state_led = api.TaurusLed()
        state_label = api.TaurusLabel()
        always_on = api.TaurusValueCheckBox()
        name_label.model = f"{dev_name}/device_friendly_name"
        state_led.model = f"{dev_name}/state"
        state_label.model = f"{dev_name}/state"
        always_on.model = f"{dev_name}/always_on_value"

        # Preserve the conventional attribute names used by DS widgets and by
        # recovery/test helpers.
        setattr(self, f"s1_{dev_name}", name_label)
        setattr(self, f"s2_{dev_name}", state_led)
        setattr(self, f"s3_{dev_name}", state_label)
        setattr(self, f"s4_{dev_name}", always_on)

        state_led.setMinimumSize(28, 28)
        state_led.setMaximumSize(28, 28)
        state_led.setSizePolicy(
            api.QtWidgets.QSizePolicy.Fixed, api.QtWidgets.QSizePolicy.Fixed
        )

        name_label.setWordWrap(False)
        name_label.bgRole = ""
        name_label.setAlignment(api.QtCore.Qt.AlignLeft | api.QtCore.Qt.AlignVCenter)
        name_label.setMinimumWidth(145)
        name_label.setSizePolicy(
            api.QtWidgets.QSizePolicy.Expanding, api.QtWidgets.QSizePolicy.Fixed
        )
        name_label.setToolTip(dev_name)

        path_label = api.QtWidgets.QLabel(dev_name)
        path_label.setObjectName("laserPointingPath")
        path_label.setTextInteractionFlags(api.QtCore.Qt.TextSelectableByMouse)
        identity = api.QtWidgets.QVBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(0)
        identity.addWidget(name_label)
        identity.addWidget(path_label)

        state_caption = api.QtWidgets.QLabel("State")
        state_caption.setObjectName("laserPointingStateCaption")
        state_label.setAlignment(api.QtCore.Qt.AlignCenter)
        state_label.setMinimumWidth(64)
        state_label.setMaximumWidth(90)
        state_label.setToolTip(f"{dev_name}/state")
        state_block = api.QtWidgets.QVBoxLayout()
        state_block.setContentsMargins(0, 0, 0, 0)
        state_block.setSpacing(0)
        state_block.addWidget(state_caption, 0, api.QtCore.Qt.AlignHCenter)
        state_block.addWidget(state_label)

        try:
            always_on.setChecked(bool(self.ds.always_on_value == 1))
        except (AttributeError, TypeError):
            always_on.setChecked(False)

        row.addWidget(state_led)
        row.addLayout(identity, 1)
        row.addLayout(state_block)
        row.addWidget(always_on)
        lo_status.setContentsMargins(0, 0, 0, 4)
        lo_status.addWidget(header)

        recovery = getattr(self, "_device_recovery", None)
        if recovery is not None:
            for recovery_target in (
                header,
                state_led,
                name_label,
                path_label,
                state_label,
            ):
                recovery.install_on(recovery_target)

        self.controller_header = header

    def set_states(self, mode=""):
        dev_name = self.dev_name
        ds: api.Device = getattr(self, f"ds_{dev_name}")

        self.rules: api.OrderedDict = eval(ds.get_rules)
        group = api.QtWidgets.QGroupBox("Optical points")
        mode_name = str(mode).strip()
        group.setObjectName(
            f"laserPointingOpticalPoints{mode_name}" if mode_name
            else "laserPointingOpticalPoints"
        )
        group.setSizePolicy(api.QtWidgets.QSizePolicy.Fixed, api.QtWidgets.QSizePolicy.Fixed)
        group.setMinimumWidth(300)
        group.setMaximumWidth(340)
        group.setMinimumHeight(82)
        group.setMaximumHeight(92)
        layout = api.QtWidgets.QGridLayout(group)
        layout.setContentsMargins(5, 3, 5, 4)
        layout.setHorizontalSpacing(3)
        layout.setVerticalSpacing(2)

        numbered = []
        working = []
        for state, parameters in self.rules.items():
            state_text = str(state)
            suffix = state_text.lower().replace("point", "")
            if suffix.isdigit():
                numbered.append((int(suffix), state_text, parameters))
            else:
                working.append((state_text, parameters))

        has_translation = any(
            "TranslationStage1" in parameters for _, _, parameters in numbered
        )
        self.has_translation_planes = has_translation
        planes = ((1, 2, 3), (4, 5, 6))
        button_group = api.QtWidgets.QButtonGroup(self)
        button_group.setExclusive(True)
        self.point_button_groups.append(button_group)

        for row, point_numbers in enumerate(planes):
            if has_translation:
                plane_label = "Near" if row == 0 else "Far"
            else:
                plane_label = "D1" if row == 0 else "D2"
            label = api.QtWidgets.QLabel(plane_label)
            label.setStyleSheet("font-size: 10px; font-weight: 600; color: #465568;")
            label.setToolTip(
                "Near plane · stage 0" if row == 0 and has_translation
                else (
                    "Far plane · stage −700" if has_translation
                    else f"Diaphragm {row + 1}"
                )
            )
            layout.addWidget(label, row, 0)

            for column, point_number in enumerate(point_numbers):
                entry = next((item for item in numbered if item[0] == point_number), None)
                if entry is None:
                    continue
                _, state, parameters = entry
                aperture = api.active_point_aperture(parameters)
                detail = (
                    f"{aperture:g}%" if aperture is not None else ""
                )
                button = api.QtWidgets.QPushButton(f"P{point_number} {detail}".rstrip())
                button.setCheckable(True)
                button.setFixedHeight(25)
                button.setMinimumWidth(54)
                button.setSizePolicy(
                    api.QtWidgets.QSizePolicy.Fixed, api.QtWidgets.QSizePolicy.Fixed
                )
                button.setToolTip(self._point_tooltip(state, parameters))
                button.clicked.connect(
                    api.partial(self.point_clicked, state, parameters, point_number)
                )
                button_group.addButton(button)
                self.point_buttons_by_state.setdefault(state, []).append(button)
                layout.addWidget(button, row, column + 1)

        if working:
            state, parameters = working[0]
            button = api.QtWidgets.QPushButton("Working")
            button.setCheckable(True)
            button.setFixedSize(68, 52)
            button.setToolTip(
                "Controller sequence: set λ/2 working target, apply all "
                "Working optics, then lower and verify all shutters"
            )
            button.clicked.connect(api.partial(self.point_clicked, state, parameters, 0))
            button_group.addButton(button)
            self.point_buttons_by_state.setdefault(state, []).append(button)
            layout.addWidget(button, 0, 4, 2, 1)

        return group

    def _component_device_path(specification):
        if isinstance(specification, (tuple, list)):
            return str(specification[0]) if specification else ""
        return str(specification or "")

    def _component_caption(role):
        text = str(role or "")
        lowered = text.lower()
        digits = "".join(character for character in text if character.isdigit())
        if "shutter" in lowered or "flipper" in lowered:
            return f"Flipper {digits}".rstrip()
        if "mainlaserdiaphragm" in lowered:
            return f"Main D{digits}".rstrip()
        if "crimpingdiaphragm" in lowered:
            return f"Diaphragm {digits}".rstrip()
        if "halfwaveplate" in lowered or "lambda" in lowered:
            return "λ/2"
        if "translation" in lowered:
            return "DL"
        return text

    def _status_value_card(self, role, device_name, attribute_name="position"):
        card = api.QtWidgets.QFrame()
        card.setObjectName("laserComponentStatusCard")
        card.setSizePolicy(
            api.QtWidgets.QSizePolicy.Expanding, api.QtWidgets.QSizePolicy.Fixed
        )
        card.setMinimumWidth(96)
        card.setFixedHeight(25)
        row = api.QtWidgets.QHBoxLayout(card)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(3)

        led = api.TaurusLed()
        led.model = f"{device_name}/state"
        led.setFixedSize(13, 13)
        led.setToolTip(device_name)
        caption = api.QtWidgets.QLabel(self._component_caption(role))
        caption.setObjectName("laserComponentStatusCaption")
        caption.setToolTip(device_name)
        is_flipper = "shutter" in role.lower() or "flipper" in role.lower()
        status_attribute = "commanded_flipper_state" if is_flipper else attribute_name
        value = api.OpticalStatusValue(role)
        value.model = f"{device_name}/{status_attribute}"
        value.bgRole = ""
        value.setObjectName("laserComponentStatusValue")
        value.setToolTip(
            f"{device_name}/{status_attribute}"
            + (
                " · last completed command: −1 = UP / blocked, +1 = DOWN / clear"
                if is_flipper
                else ""
            )
        )

        row.addWidget(led)
        row.addWidget(caption)
        row.addStretch(1)
        row.addWidget(value)
        return card

    def _status_state_card(self, caption_text, devices):
        card = api.QtWidgets.QFrame()
        card.setObjectName("laserComponentStatusCard")
        card.setSizePolicy(
            api.QtWidgets.QSizePolicy.Expanding, api.QtWidgets.QSizePolicy.Fixed
        )
        card.setMinimumWidth(96)
        card.setFixedHeight(25)
        row = api.QtWidgets.QHBoxLayout(card)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(3)
        caption = api.QtWidgets.QLabel(caption_text)
        caption.setObjectName("laserComponentStatusCaption")
        row.addWidget(caption)
        row.addStretch(1)
        for axis_name, device_name in devices:
            axis = api.QtWidgets.QLabel(axis_name)
            axis.setObjectName("laserComponentStatusAxis")
            led = api.TaurusLed()
            led.model = f"{device_name}/state"
            led.setFixedSize(13, 13)
            led.setToolTip(device_name)
            row.addWidget(axis)
            row.addWidget(led)
        return card

    def build_component_status_panel(self):
        """Create a compact, passive overview of LaserPointing hardware."""

        group = api.QtWidgets.QGroupBox("Main components · live status")
        group.setObjectName("laserPointingComponentStatus")
        group.setSizePolicy(
            api.QtWidgets.QSizePolicy.Expanding, api.QtWidgets.QSizePolicy.Fixed
        )
        group.setMinimumHeight(82)
        group.setMaximumHeight(92)
        grid = api.QtWidgets.QGridLayout(group)
        grid.setContentsMargins(5, 3, 5, 4)
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(2)

        cards = []
        camera_name = self._component_device_path(self.ds_dict.get("Camera", ""))
        if camera_name:
            cards.append(self._status_state_card("Camera", (("", camera_name),)))

        for index, roles in enumerate(self._actuator_role_groups, start=1):
            devices = []
            for role in roles:
                device_name = self._component_device_path(self.ds_dict.get(role, ""))
                if device_name:
                    axis = "X" if "x" in str(role).lower() else "Y"
                    devices.append((axis, device_name))
            if devices:
                cards.append(self._status_state_card(f"Standa {index}", devices))

        status_devices = dict(self.ds_dict)
        shutter1 = self._component_device_path(status_devices.get("Shutter1", ""))
        if (
            shutter1
            and "Shutter2" not in status_devices
            and shutter1.lower().endswith("/s1")
        ):
            status_devices["Shutter2"] = shutter1[:-1] + "2"

        optical_roles = []
        for role, specification in status_devices.items():
            lowered = str(role).lower()
            if any(
                marker in lowered
                for marker in (
                    "shutter",
                    "flipper",
                    "diaphragm",
                    "halfwaveplate",
                    "lambda",
                    "translation",
                )
            ):
                attribute_name = "position"
                if "translation" in lowered and isinstance(
                    specification, (tuple, list)
                ):
                    axes = specification[1] if len(specification) > 1 else ()
                    if not isinstance(axes, (tuple, list)):
                        axes = (axes,)
                    if axes:
                        attribute_name = f"pos{int(axes[0])}"
                optical_roles.append(
                    (
                        str(role),
                        self._component_device_path(specification),
                        attribute_name,
                    )
                )
        optical_roles.sort(
            key=lambda item: (
                0
                if "shutter" in item[0].lower()
                or "flipper" in item[0].lower()
                else 1,
                item[0].lower(),
            )
        )
        for role, device_name, attribute_name in optical_roles:
            if device_name:
                cards.append(
                    self._status_value_card(role, device_name, attribute_name)
                )

        columns = max(1, api.math.ceil(len(cards) / 2.0))
        for index, card in enumerate(cards):
            grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)

        group.setStyleSheet(
            """
            QGroupBox#laserPointingComponentStatus {
                font-weight: 600;
            }
            QFrame#laserComponentStatusCard {
                background: #f4f7fa;
                border: 1px solid #d5dde6;
                border-radius: 3px;
            }
            QLabel#laserComponentStatusCaption {
                color: #465568;
                font-size: 9px;
                border: none;
                background: transparent;
            }
            QLabel#laserComponentStatusAxis {
                color: #738092;
                font-size: 8px;
                border: none;
                background: transparent;
            }
            QLabel#laserComponentStatusValue {
                color: #172b44;
                font-size: 9px;
                font-weight: 700;
                border: none;
                background: transparent;
            }
            """
        )
        return group

    def _point_tooltip(state, parameters):
        settings = ", ".join(f"{role}={value}" for role, value in parameters.items())
        return f"Apply {state}: {settings}"

    def point_clicked(self, state, parameters, point_number, checked=False):
        """Apply a point through the controller, then unlock its mount pair."""

        if not checked or self._point_apply_busy or self._pair_initialization_busy:
            return
        self._point_apply_busy = True
        self._set_point_buttons_enabled(False)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(False)
        self.set_active_actuator_group(
            0, f"Applying {state}; alignment mounts are locked until readback completes"
        )
        if hasattr(self, "search_status"):
            self.search_status.setText(f"Applying {state}…")

        def apply():
            try:
                ds = getattr(self, f"ds_{self.dev_name}")
                result = ds.apply_controller_point(state)
                if result not in (None, 0):
                    raise RuntimeError(f"controller returned {result}")
                self.point_application_finished.emit(state, point_number, True, "")
            except Exception as error:
                self.point_application_finished.emit(
                    state, point_number, False, str(error)
                )

        api.Thread(target=apply, name=f"{self.dev_name}-apply-{state}", daemon=True).start()

    def _finish_point_application(self, state, point_number, success, message):
        self._point_apply_busy = False
        self._set_point_buttons_enabled(True)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(True)
        if success:
            group_index = api.optical_point_group(f"point{point_number}")
            for button in self._point_buttons(state):
                button.setChecked(True)
            self.set_active_actuator_group(group_index)
            if hasattr(self, "search_status"):
                self.search_status.setText(f"Applied {state}")
        else:
            self._clear_point_selection()
            self.set_active_actuator_group(
                0, f"Could not apply {state}; both mount pairs remain locked"
            )
            if hasattr(self, "search_status"):
                self.search_status.setText(f"Could not apply {state}: {message}")

    def _set_point_buttons_enabled(self, enabled):
        for group in getattr(self, "point_button_groups", ()):
            for button in group.buttons():
                button.setEnabled(bool(enabled))

    def _clear_point_selection(self):
        for group in getattr(self, "point_button_groups", ()):
            group.setExclusive(False)
            for button in group.buttons():
                button.setChecked(False)
            group.setExclusive(True)

    def _point_buttons(self, state):
        buttons = getattr(self, "point_buttons_by_state", {}).get(state, ())
        if isinstance(buttons, (list, tuple)):
            return list(buttons)
        return [buttons] if buttons is not None else []

    def set_active_actuator_group(self, group_index, reason=""):
        """Expose every ready manual axis unless the controller owns motion."""

        group_index = int(group_index or 0)
        self._active_actuator_group = group_index
        role_groups = tuple(getattr(self, "_actuator_role_groups", ()))
        ready_groups = {
            index: self._active_pair_is_ready(index)
            for index in range(1, len(role_groups) + 1)
        }
        controller_owns_motion = (
            self._point_apply_busy
            or self._pair_initialization_busy
            or self._search_running
        )
        if not reason:
            if group_index in (1, 2):
                optical_name = (
                    ("Near plane" if group_index == 1 else "Far plane")
                    if getattr(self, "has_translation_planes", False)
                    else f"Diaphragm {group_index}"
                )
                reason = (
                    f"{optical_name} selected — all initialized Standa "
                    "actuators remain available in Manual"
                )
            else:
                reason = (
                    "Manual mode — all initialized Standa actuators are available"
                )

        for index, roles in enumerate(
            role_groups, start=1
        ):
            pair_ready = ready_groups.get(index, False)
            enabled = api.manual_alignment_motion_enabled(
                pair_ready,
                point_application_busy=self._point_apply_busy,
                pair_initialization_busy=self._pair_initialization_busy,
                automatic_search_running=self._search_running,
            )
            for role in roles:
                widget = self.widgets.get(role)
                if widget is None:
                    continue
                lock_reason = (
                    "Manual alignment control is available"
                    if enabled
                    else (
                        reason
                        if controller_owns_motion
                        else f"Standa pair {index} is not initialized"
                    )
                )
                if hasattr(widget, "set_alignment_motion_enabled"):
                    widget.set_alignment_motion_enabled(enabled, lock_reason)
                else:
                    widget.setEnabled(enabled)

        label = getattr(self, "mount_interlock_status", None)
        if label is not None:
            label.setText(f"Mount interlock: {reason}")
            if ready_groups and all(ready_groups.values()) and not controller_owns_motion:
                label.setStyleSheet(
                    "background: #e4f4e8; color: #195c2b; "
                    "border: 1px solid #9bc9a6; border-radius: 4px; padding: 5px;"
                )
            else:
                label.setStyleSheet(
                    "background: #fff4d6; color: #775000; "
                    "border: 1px solid #e2bd68; border-radius: 4px; padding: 5px;"
                )
        self._update_pair_initialization_controls()

    def add_pair_initialization_controls(self, layout, ds):
        panel = api.QtWidgets.QWidget()
        panel_layout = api.QtWidgets.QHBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(5)
        self.initialize_pair_button = api.QtWidgets.QPushButton(
            "Initialize active pair"
        )
        self.initialize_pair_button.clicked.connect(self.initialize_active_pair)
        self.initialize_pair_status = api.QtWidgets.QLabel(
            "Select an optical point first"
        )
        self.initialize_pair_status.setWordWrap(True)
        self.initialize_pair_status.setStyleSheet(
            "color: #59687a; font-size: 9px;"
        )
        panel_layout.addWidget(self.initialize_pair_button)
        panel_layout.addWidget(self.initialize_pair_status, 1)
        layout.addWidget(panel)

        self._refresh_pair_initialization_capability(ds)
        self._update_pair_initialization_controls()

    def _refresh_pair_initialization_capability(self, ds):
        try:
            commands = {
                str(name).lower()
                for name in ds.getDeviceProxy().get_command_list()
            }
            self._pair_initialization_supported = (
                "initialize_active_pair" in commands
            )
        except Exception:
            self._pair_initialization_supported = False

    return {
        "register_DS_min": register_DS_min,
        "set_state_status": set_state_status,
        "set_states": set_states,
        "_component_device_path": _component_device_path,
        "_component_caption": _component_caption,
        "_status_value_card": _status_value_card,
        "_status_state_card": _status_state_card,
        "build_component_status_panel": build_component_status_panel,
        "_point_tooltip": _point_tooltip,
        "point_clicked": point_clicked,
        "_finish_point_application": _finish_point_application,
        "_set_point_buttons_enabled": _set_point_buttons_enabled,
        "_clear_point_selection": _clear_point_selection,
        "_point_buttons": _point_buttons,
        "set_active_actuator_group": set_active_actuator_group,
        "add_pair_initialization_controls": add_pair_initialization_controls,
        "_refresh_pair_initialization_capability": _refresh_pair_initialization_capability,
    }
