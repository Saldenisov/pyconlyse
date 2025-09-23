# Import the fixes for safe device access
import sys
from pathlib import Path

import tango
from _functools import partial
from PyQt5 import QtWidgets
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.button import TaurusCommandButton

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType

fixes_path = Path(__file__).parents[3] / "fixes"
if str(fixes_path) not in sys.path:
    sys.path.append(str(fixes_path))
from taurus_warnings_fix import (
    check_device_connection,
    get_device_ids_safely,
    get_device_names_safely,
    get_device_states_safely,
    suppress_taurus_deprecation_warnings,
)


class Netio_pdu(DS_General_Widget):
    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        # Suppress Taurus deprecation warnings
        suppress_taurus_deprecation_warnings()
        super().__init__(device_name, parent, vis_type)

    def before_ds(self):
        """Initialize device-dependent data before UI is built."""
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")

        # Check device connection first
        if not check_device_connection(ds):
            print(f"Warning: Device {dev_name} is not properly connected")
            # Initialize with empty lists as fallback
            self.ids = []
            self.names = []
            self.states = []
        else:
            # Use safe accessors
            self.ids = get_device_ids_safely(ds)
            self.names = get_device_names_safely(ds)
            self.states = get_device_states_safely(ds)

        # Controls are not ready until set_states creates them
        self._controls_ready = False

    def register_DS_full(self, group_number=1):
        super(Netio_pdu, self).register_DS_full()
        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_buttons: Qt.QLayout = getattr(self, f"layout_buttons_{dev_name}")

        # State and status
        self.set_state_status(False)

        # state positions
        group = self.set_states()

        # Now that UI elements exist, subscribe to events (tolerate failures)
        for attr in ("states", "names", "ids"):
            try:
                getattr(self, f"ds_{dev_name}").subscribe_event(
                    attr, tango.EventType.CHANGE_EVENT, self.state_listener
                )
            except Exception as e:
                print(f"Info: couldn't subscribe to '{attr}' for {dev_name}: {e}")

        # Buttons and commands
        setattr(self, f"button_on_{dev_name}", TaurusCommandButton(command="turn_on"))
        button_on: TaurusCommandButton = getattr(self, f"button_on_{dev_name}")
        button_on.setModel(dev_name)

        setattr(self, f"button_off_{dev_name}", TaurusCommandButton(command="turn_off"))
        button_off: TaurusCommandButton = getattr(self, f"button_off_{dev_name}")
        button_off.setModel(dev_name)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)

        lo_device.addLayout(lo_status)
        lo_device.addWidget(group)
        lo_device.addLayout(lo_buttons)

        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        super(Netio_pdu, self).register_DS_min()
        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")

        # State and status
        self.set_state_status()

        # state positions
        group = self.set_states()

        # Now that UI elements exist, subscribe to events (tolerate failures)
        for attr in ("states", "names", "ids"):
            try:
                getattr(self, f"ds_{dev_name}").subscribe_event(
                    attr, tango.EventType.CHANGE_EVENT, self.state_listener
                )
            except Exception as e:
                print(f"Info: couldn't subscribe to '{attr}' for {dev_name}: {e}")

        lo_status.addWidget(group)
        lo_device.addLayout(lo_status)
        lo_group.addLayout(lo_device)

    def register_full_layouts(self):
        super(Netio_pdu, self).register_full_layouts()
        setattr(self, f"layout_state_{self.dev_name}", Qt.QHBoxLayout())

    def register_min_layouts(self):
        super(Netio_pdu, self).register_min_layouts()
        setattr(self, f"layout_state_{self.dev_name}", Qt.QHBoxLayout())

    def set_states(self):
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")

        lo_state: Qt.QLayout = getattr(self, f"layout_state_{dev_name}")
        setattr(self, f"checkbox_group_{dev_name}", Qt.QGroupBox("Channels states"))
        group: Qt.QGroupBox = getattr(self, f"checkbox_group_{dev_name}")

        controls_ready = False
        try:
            # Check if device is connected and has data
            if not check_device_connection(ds):
                # Add a label indicating device is not connected
                error_label = QtWidgets.QLabel(f"Device {dev_name} not connected")
                error_label.setStyleSheet("color: red; font-weight: bold;")
                lo_state.addWidget(error_label)
            elif not self.ids or not self.names or not self.states:
                # Device connected but no data yet
                loading_label = QtWidgets.QLabel(
                    f"Loading device data for {dev_name}..."
                )
                loading_label.setStyleSheet("color: orange; font-weight: bold;")
                lo_state.addWidget(loading_label)
            else:
                # Normal operation - create checkboxes
                try:
                    # Try to get number_outputs property, fall back to data length
                    number_outputs = len(self.ids)
                    try:
                        prop_outputs = int(
                            ds.get_property("number_outputs")["number_outputs"][0]
                        )
                        number_outputs = min(number_outputs, prop_outputs)
                    except:
                        pass  # Use data length

                    # Use safe data from initialization
                    names = self.names[:number_outputs]
                    ids = self.ids[:number_outputs]
                    states = self.states[:number_outputs]

                    widgets = [
                        QtWidgets.QCheckBox(f"{dev_name}:id:{id}")
                        for _, id in zip(range(number_outputs), ids)
                    ]

                    for cb, state, name, id in zip(widgets, states, names, ids):
                        setattr(self, f"cb{id}_{dev_name}", cb)
                        cb: QtWidgets.QCheckBox = getattr(self, f"cb{id}_{dev_name}")
                        cb.setChecked(bool(state))
                        cb.setText(f"{name}:id:{id}")
                        lo_state.addWidget(cb)
                        cb.clicked.connect(partial(self.cb_clicked, dev_name))
                    controls_ready = True
                except Exception as inner_e:
                    error_label = QtWidgets.QLabel(
                        f"Error creating controls: {inner_e}"
                    )
                    error_label.setStyleSheet("color: red;")
                    lo_state.addWidget(error_label)

        except Exception as e:
            print(f"Error in set_states for {dev_name}: {e}")
            error_label = QtWidgets.QLabel(f"Error: {e!s}")
            error_label.setStyleSheet("color: red;")
            lo_state.addWidget(error_label)
        finally:
            # Mark controls readiness for listeners
            self._controls_ready = bool(controls_ready)

        group.setLayout(lo_state)
        return group

    def cb_clicked(self, dev_name: str):
        try:
            ds: Device = getattr(self, f"ds_{dev_name}")

            # Use safe accessors and local data
            ids = get_device_ids_safely(ds) or self.ids
            names = get_device_names_safely(ds) or self.names

            states = []
            for id, name in zip(ids, names):
                try:
                    cb: QtWidgets.QCheckBox = getattr(self, f"cb{id}_{dev_name}")
                    states.append(int(cb.isChecked()))
                except AttributeError:
                    # Checkbox doesn't exist, use default state
                    states.append(0)

            # Only send command if we have a valid device connection
            if check_device_connection(ds):
                ds.set_channels_states(states)
            else:
                print(f"Warning: Cannot send command to disconnected device {dev_name}")

        except Exception as e:
            print(f"Error in cb_clicked for {dev_name}: {e}")

    def state_listener(self, event):
        try:
            # Skip updates until controls have been created
            if not getattr(self, "_controls_ready", False):
                return

            ds: Device = getattr(self, f"ds_{self.dev_name}")

            # Use safe accessors to get new data
            names_new = get_device_names_safely(ds)
            states_new = get_device_states_safely(ds)

            # Only proceed if we have valid data
            if not names_new or not states_new or len(names_new) != len(states_new):
                return

            # Update widgets if they exist
            for new_name, new_state, id in zip(names_new, states_new, self.ids):
                try:
                    cb: QtWidgets.QCheckBox = getattr(self, f"cb{id}_{self.dev_name}")

                    # Check bounds before accessing arrays
                    idx = id - 1
                    if 0 <= idx < len(self.names) and self.names[idx] != new_name:
                        cb.setText(f"{new_name}:id:{id}")

                    if 0 <= idx < len(self.states) and self.states[idx] != new_state:
                        cb.setChecked(bool(new_state))
                except (AttributeError, IndexError):
                    # Widget might not exist yet or index out of bounds
                    continue

            # Update stored data
            self.names = names_new
            self.states = states_new
        except Exception:
            # Avoid spamming prints on transient errors
            pass

    def set_the_control_value(self, value):
        pass
