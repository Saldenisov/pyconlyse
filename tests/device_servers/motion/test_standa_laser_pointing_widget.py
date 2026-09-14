import sys
import types
from types import SimpleNamespace

from PyQt5 import QtWidgets


# The software-only collection lane installs inert Taurus package shells.
# Supply only the symbols needed to import this widget without constructing Qt.
sys.modules["taurus"].Device = object
display_module = types.ModuleType("taurus.qt.qtgui.display")
display_module.TaurusLabel = object
sys.modules[display_module.__name__] = display_module

widget_module = types.ModuleType("DeviceServers.shared.DS_Widget")
widget_module.DS_General_Widget = object
widget_module.VisType = SimpleNamespace(MIN="min", FULL="full")
sys.modules[widget_module.__name__] = widget_module

from DeviceServers.motion.standa.DS_STANDA_LaserPointing_Widget import (
    Standa_LaserPointing,
)


class FakeWidget:
    def __init__(self, parent):
        self.parent = parent
        self.dev_name = "standa1_x"
        self.styles = []

    def setStyleSheet(self, style):
        self.styles.append(style)


def test_double_click_is_safe_for_embedded_laser_pointing_parent():
    parent = SimpleNamespace()
    widget = FakeWidget(parent)

    Standa_LaserPointing.mouseDoubleClickEvent(widget, None)

    assert parent.active_widget == "standa1_x"
    assert widget.styles[-1] == (
        "background-color: lightgreen; border: 1px solid black;"
    )


def test_double_click_notifies_standalone_panel_callback():
    calls = []
    parent = SimpleNamespace(update_active_widget=lambda: calls.append("active"))
    widget = FakeWidget(parent)

    Standa_LaserPointing.mouseDoubleClickEvent(widget, None)

    assert calls == ["active"]


def test_double_click_supports_background_only_panels():
    calls = []
    parent = SimpleNamespace(
        update_background_widgets=lambda: calls.append("background")
    )
    widget = FakeWidget(parent)

    Standa_LaserPointing.mouseDoubleClickEvent(widget, None)

    assert calls == ["background"]


def test_percentage_optics_expose_configured_presets():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    properties = {
        "unit": {"unit": ["%"]},
        "preset_pos": {"preset_pos": ["0", "20.5", "100"]},
    }
    device = SimpleNamespace(get_property=lambda name: properties[name])
    widget = SimpleNamespace(
        dev_name="manip/v0/l-2_1",
        move_to_preset=lambda *_args: None,
    )

    selector = Standa_LaserPointing._create_optical_preset_selector(
        widget, device
    )

    assert app is not None
    assert [selector.itemText(index) for index in range(selector.count())] == [
        "Preset %",
        "0%",
        "20.5%",
        "100%",
    ]
    assert selector.itemData(2) == 20.5


def test_flipper_optics_expose_minus_and_plus_position_presets():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    properties = {
        "unit": {"unit": ["state"]},
        "preset_pos": {"preset_pos": ["-1", "1"]},
    }
    device = SimpleNamespace(get_property=lambda name: properties[name])
    widget = SimpleNamespace(
        dev_name="manip/v0/s2",
        move_to_preset=lambda *_args: None,
    )

    selector = Standa_LaserPointing._create_optical_preset_selector(
        widget, device
    )

    assert app is not None
    assert [selector.itemText(index) for index in range(selector.count())] == [
        "Preset",
        "-1",
        "1",
    ]


def test_step_size_accepts_requested_fractional_choices():
    widget = SimpleNamespace(relative_shift=1.0)

    Standa_LaserPointing.set_step_size(widget, 0.5)

    assert widget.relative_shift == 0.5
