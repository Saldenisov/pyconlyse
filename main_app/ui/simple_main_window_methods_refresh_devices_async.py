"""Implementation for refresh_devices_async and related operations."""


def _bind_simple_main_window_methods_refresh_devices_async(api):
    """Bind implementation to the owning module and its runtime state."""

    def refresh_devices_async(self):
        # Build device list from DB and place into grid; states updated separately
        if api.OFFLINE_MODE:
            self._rebuild_devices_grid([])
            return
        try:
            import concurrent.futures

            from tango import Database
        except Exception:
            self._rebuild_devices_grid([])
            return

        def _fetch():
            try:
                db = Database()
                names = []
                for prefix in ("ELYSE", "manip"):
                    try:
                        names.extend(list(db.get_device_exported(f"{prefix}*")))
                    except Exception:
                        continue
                # Unique and sorted
                return sorted(set(names))
            except Exception:
                return []

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_fetch)

        def _done(_f):
            try:
                names = _f.result(timeout=0) or []
            except Exception:
                names = []
            api.QTimer.singleShot(0, lambda lst=names: self._rebuild_devices_grid(lst))
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    def _rebuild_devices_grid(self, device_names: api.List[str]):
        # Clear grid
        try:
            while self.devices_grid.count() > 0:
                item = self.devices_grid.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass
        self.device_widgets.clear()

        # Rebuild
        row, col = 0, 0
        cols = 3
        for name in device_names:
            led = api.LedIndicator(10)
            lab = api.QLabel(name)
            lab.setStyleSheet("font-size: 11px")
            self.devices_grid.addWidget(led, row, col)
            self.devices_grid.addWidget(lab, row, col + 1)
            self.device_widgets[name] = (led, lab)
            col += 2
            if col >= cols * 2:
                col = 0
                row += 1
        self.statusBar().showMessage(f"Devices listed: {len(device_names)}")

    def update_device_states_async(self):
        if api.OFFLINE_MODE:
            return
        if not self.device_widgets:
            return
        try:
            import concurrent.futures

            from taurus import Device
        except Exception:
            return

        names = list(self.device_widgets.keys())

        def _read_all():
            res = {}
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:

                    def read_state(dev_name: str):
                        try:
                            dev = Device(dev_name)
                            st = str(dev.state()).upper()
                            return dev_name, st
                        except Exception:
                            return dev_name, "ERROR"

                    futs = [ex.submit(read_state, n) for n in names]
                    for fut in futs:
                        try:
                            dev, state = fut.result(timeout=2.0)
                        except Exception:
                            continue
                        res[dev] = state
            except Exception:
                pass
            return res

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_read_all)

        def _done(_f):
            try:
                results = _f.result(timeout=0) or {}
            except Exception:
                results = {}

            def apply():
                for dev, (led, lab) in self.device_widgets.items():
                    st = (results.get(dev) or "UNKNOWN").upper()
                    if st in ("ON", "RUNNING", "STANDBY", "MOVING"):
                        led.set_on()
                    elif st in ("OFF",):
                        led.set_off()
                    elif st in ("ERROR", "FAULT", "ALARM"):
                        led.set_error()
                    else:
                        led.set_off()
                    lab.setText(dev)

            api.QTimer.singleShot(0, apply)
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    def _resolve_itest_device(self, config_or_device: str) -> str:
        """Map selection to Tango device for iTest client.
        Accepts either a config name (e.g. 'ITestPSU/test') or a full device name.
        """
        mapping = {
            "ELYSE": "ELYSE/pdu/iTest",
            "ITestPSU/ELYSE": "ELYSE/pdu/iTest",
            "ITestPSU/test": "test/itest/psu01",
            "ITestPSU/main": "manip/power/itest_psu01",
            "ITestPSU/lab": "lab/itest/psu01",
            "ITestPSU/bilt": "bilt/power/itest_main",
            "test": "test/itest/psu01",
            "main": "manip/power/itest_psu01",
            "lab": "lab/itest/psu01",
            "bilt": "bilt/power/itest_main",
        }
        if "/" in config_or_device and config_or_device not in mapping:
            return config_or_device
        return mapping.get(config_or_device, config_or_device)

    def _launch_client(self, key: str):
        try:
            import subprocess
            import sys
            from pathlib import Path

            refs = self.client_rows.get(key) or {}
            combo: api.QComboBox = refs.get("combo")  # type: ignore
            if not combo or combo.count() == 0 or not combo.isEnabled():
                api.QMessageBox.information(
                    self, key, "Please configure selection list in Config menu."
                )
                return
            selection = (combo.currentText() or "").strip()
            vis = (
                self._client_vis.value if hasattr(self._client_vis, "value") else "FULL"
            )

            # All DS now use instance/config names, not device names
            if not selection or selection.startswith("("):
                api.QMessageBox.information(
                    self, key, "Please select an instance or configure list."
                )
                return

            # If this key is configured as a 'widget', prefer launching in-process widget
            kind = refs.get("kind") if isinstance(refs, dict) else None
            if key == "ITEST" and kind == "widget":
                try:
                    from main_app.ui.widget_launchers import start_itest_widget
                except Exception as e:
                    api.QMessageBox.critical(self, key, f"Cannot import iTest widget: {e}")
                    return
                device_name = self._resolve_itest_device(selection)
                panel = start_itest_widget(device_name, parent=self, vis=vis)
                if panel:
                    try:
                        self._launched_panels.append(panel)
                    except Exception:
                        pass
                    self.statusBar().showMessage(
                        f"Started iTest Tab client for {device_name} in this window"
                    )
                    return
                else:
                    api.QMessageBox.warning(self, key, f"Failed to start iTest widget for {device_name}")
                    return

            # Map device server keys to client script paths
            client_paths = {
                "NETIO": "DeviceServers\\power\\netio\\DS_NETIO_client.py",
                "OWIS": "DeviceServers\\motion\\owis\\DS_OWIS_client.py",
                "ZABER": "DeviceServers\\motion\\zaber\\DS_Zaber_client.py",
                "STANDA": "DeviceServers\\motion\\standa\\DS_STANDA_client.py",
                "TOPDIRECT": "DeviceServers\\motion\\topdirect\\DS_TOPDIRECT_client.py",
                "BASLER": "DeviceServers\\cameras\\basler\\DS_BASLER_client.py",
                "LASER_POINTING": (
                    "DeviceServers\\control\\laser_pointing\\"
                    "DS_LASER_POINTING_client.py"
                ),
                "KEYSIGHT": (
                    "DeviceServers\\instruments\\keysight\\"
                    "DS_KEYSIGHT_33509B_client.py"
                ),
                "ITEST": (
                    "DeviceServers\\power\\iTest\\"
                    "DS_iTest_client.py"
                ),
                "DAQMX": (
                    "DeviceServers\\control\\daqmx\\DS_DAQmx_client.py"
                ),
                "SPECTROSCOPY": (
                    "DeviceServers\\spectroscopy\\DS_SPECTROSCOPY_client.py"
                ),
                "ANDOR_CCD": "DeviceServers\\cameras\\andor\\DS_ANDOR_CCD_client.py",
                "ANDOR_SPECTROGRAPH": (
                    "DeviceServers\\spectrographs\\andor\\DS_ANDOR_SPECTROGRAPH_client.py"
                ),
                "AVANTES_CCD": (
                    "DeviceServers\\cameras\\avantes\\DS_AVANTES_CCD_client.py"
                ),
                "AVANTES_SPECTRO": (
                    "DeviceServers\\spectrographs\\avantes\\"
                    "DS_AVANTES_SPECTRO_client.py"
                ),
                "ARCHIVE": "DeviceServers\\data\\archive\\DS_ARCHIVE_client.py",
                "EXPERIMENT": (
                    "DeviceServers\\control\\experiment\\DS_Experiment_client.py"
                ),
                "DAQMX_ZMQ": (
                    "DeviceServers\\control\\daqmx\\DS_DAQmx_zmq_client.py"
                ),
            }

            if key not in client_paths:
                api.QMessageBox.warning(self, key, f"No client script configured for {key}")
                return

            # Build full path to client script
            pyconlyse_root = Path(
                api.main_app_path
            ).parent  # Go up from main_app to pyconlyse root
            client_script = pyconlyse_root / client_paths[key]

            if not client_script.exists():
                api.QMessageBox.warning(
                    self, key, f"Client script not found: {client_script}"
                )
                return

            # Determine python console executable (prefer CONDA env from PYCONLYSE_ENV)
            import os

            python_path: str | None = None
            env_name = os.environ.get("PYCONLYSE_ENV", "").strip()
            if env_name:
                try:
                    # Try to resolve conda environment path
                    # Method 1: Check if it's already a full path
                    if os.path.isabs(env_name) and os.path.exists(env_name):
                        env_dir = Path(env_name)
                    else:
                        # Method 2: Use conda info --envs to find the environment
                        result = subprocess.run(
                            ["conda", "info", "--envs"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        env_dir = None
                        if result.returncode == 0:
                            # Parse conda info output to find environment path
                            for line in result.stdout.splitlines():
                                if env_name in line and not line.startswith("#"):
                                    # Line format: "env_name    *    /path/to/env"
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[0] == env_name:
                                        env_path = parts[-1]  # Last part is the path
                                        if os.path.exists(env_path):
                                            env_dir = Path(env_path)
                                            break

                        # Method 3: Try common conda paths if not found
                        if not env_dir:
                            # Try user conda envs directory
                            user_envs = Path.home() / ".conda" / "envs" / env_name
                            if user_envs.exists():
                                env_dir = user_envs
                            else:
                                # Try system conda envs
                                conda_prefix = os.environ.get("CONDA_PREFIX")
                                if conda_prefix:
                                    system_envs = Path(conda_prefix).parent / "envs" / env_name
                                    if system_envs.exists():
                                        env_dir = system_envs

                    # Look for python.exe in the environment directory
                    if env_dir and env_dir.exists():
                        env_python = env_dir / "python.exe"
                        if not env_python.exists():
                            # Fallback: some env layouts might place python under Scripts
                            alt_python = env_dir / "Scripts" / "python.exe"
                            if alt_python.exists():
                                env_python = alt_python
                        if env_python.exists():
                            python_path = str(env_python)
                except Exception:
                    python_path = None

            if not python_path:
                # Fallback to interpreter next to current executable, else current executable
                pyexe = Path(sys.executable)
                py_console = pyexe.with_name("python.exe")
                python_path = str(py_console if py_console.exists() else pyexe)

            # Build arguments for the new console process
            args = [python_path, str(client_script), selection]
            if vis != "FULL":
                args.append(vis)

            # Launch in a brand-new console window (Windows-specific)
            creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(args, cwd=str(pyconlyse_root), creationflags=creationflags)

            self.statusBar().showMessage(
                f"Started {key} ({selection}) in separate window"
            )

        except Exception as e:
            api.QMessageBox.critical(self, key, f"Failed to start {key}: {e}")

    return {
        "refresh_devices_async": refresh_devices_async,
        "_rebuild_devices_grid": _rebuild_devices_grid,
        "update_device_states_async": update_device_states_async,
        "_resolve_itest_device": _resolve_itest_device,
        "_launch_client": _launch_client,
    }
