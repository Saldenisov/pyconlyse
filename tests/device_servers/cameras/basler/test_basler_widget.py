import sys
import types
from enum import Enum
from types import SimpleNamespace

import tango
import taurus.core

# The software-only collection lane installs intentionally inert Taurus
# package shells.  Supply only the names needed to import the widget; these
# tests call its Grab lifecycle methods without constructing a GUI.
taurus.core.TaurusDevState = SimpleNamespace(Ready="Ready")
qt_module = sys.modules["taurus.external.qt"]
qt_module.Qt = SimpleNamespace(
    QHBoxLayout=object,
    QLayout=object,
    QVBoxLayout=object,
    QLabel=object,
)
qt_module.QtCore = SimpleNamespace(QTimer=object)

button_module = sys.modules["taurus.qt.qtgui.button"]
button_module.TaurusCommandButton = object
display_module = types.ModuleType("taurus.qt.qtgui.display")
display_module.TaurusLabel = object
display_module.TaurusLed = object
sys.modules[display_module.__name__] = display_module
input_module = sys.modules["taurus.qt.qtgui.input"]
input_module.TaurusValueComboBox = object
input_module.TaurusValueSpinBox = object

widget_module = types.ModuleType("DeviceServers.shared.DS_Widget")
widget_module.DS_General_Widget = object
widget_module.VisType = SimpleNamespace(FULL="full")
sys.modules[widget_module.__name__] = widget_module

from DeviceServers.cameras.basler.DS_BASLER_Widget import Basler_camera


class FakeButton:
    def __init__(self):
        self.text = "Grab"
        self.tooltip = ""

    def setText(self, value):
        self.text = value

    def setToolTip(self, value):
        self.tooltip = value


class FakeTimer:
    def __init__(self):
        self.running = False

    def start(self, _interval):
        self.running = True

    def stop(self):
        self.running = False


class FakeProxy:
    class Source(Enum):
        DEV = "direct"
        CACHE_DEV = "cached"

    def __init__(self, device):
        self.device = device
        self.source = self.Source.CACHE_DEV
        self.cached_isgrabbing = device.isgrabbing

    def state(self):
        return self.device.state

    def get_source(self):
        return self.source

    def set_source(self, source):
        self.source = source

    def read_attribute(self, name):
        assert name == "isgrabbing"
        value = (
            self.device.isgrabbing
            if self.source == self.Source.DEV
            else self.cached_isgrabbing
        )
        return SimpleNamespace(value=value)


class FakeCamera:
    def __init__(self, state=tango.DevState.OFF, start_succeeds=True):
        self.state = state
        self.isgrabbing = False
        self.last_error = ""
        self.start_succeeds = start_succeeds
        self.calls = []
        self.proxy = FakeProxy(self)
        self.before_stop = None

    def getDeviceProxy(self):
        return self.proxy

    def turn_on(self):
        self.calls.append("turn_on")
        self.state = tango.DevState.ON

    def start_grabbing(self):
        self.calls.append("start_grabbing")
        self.isgrabbing = self.start_succeeds

    def stop_grabbing(self):
        self.calls.append("stop_grabbing")
        if self.before_stop is not None:
            self.before_stop()
        self.isgrabbing = False


def make_widget(camera):
    button = FakeButton()
    status = SimpleNamespace(text="", clear=lambda: setattr(status, "text", ""))
    status.setText = lambda value: setattr(status, "text", value)
    widget = SimpleNamespace(
        dev_name="camera/test",
        grabbing=False,
        timer=FakeTimer(),
        grab_status_label=status,
        **{"ds_camera/test": camera, "button_start_grabbing_camera/test": button},
    )
    widget._camera_state_name = Basler_camera._camera_state_name
    widget._read_grabbing_state = Basler_camera._read_grabbing_state
    widget._set_grabbing_ui = lambda grabbing: Basler_camera._set_grabbing_ui(
        widget, grabbing
    )
    widget._show_grab_error = lambda message: Basler_camera._show_grab_error(
        widget, message
    )
    return widget, button, status


def test_grab_turns_on_minimal_camera_before_starting_acquisition():
    camera = FakeCamera()
    widget, button, status = make_widget(camera)

    Basler_camera.grab_clicked(widget)

    assert camera.calls == ["turn_on", "start_grabbing"]
    assert widget.grabbing is True
    assert widget.timer.running is True
    assert button.text == "Stop grab"
    assert status.text == ""


def test_grab_stops_an_acquisition_already_running_on_the_server():
    camera = FakeCamera(state=tango.DevState.ON)
    camera.isgrabbing = True
    camera.proxy.cached_isgrabbing = True
    widget, button, _status = make_widget(camera)
    widget._set_grabbing_ui(True)
    camera.before_stop = lambda: assert_image_timer_stopped(widget)

    Basler_camera.grab_clicked(widget)

    assert camera.calls == ["stop_grabbing"]
    assert widget.grabbing is False
    assert widget.timer.running is False
    assert button.text == "Grab"
    assert camera.proxy.source == FakeProxy.Source.CACHE_DEV


def assert_image_timer_stopped(widget):
    assert widget.timer.running is False


def test_grab_failure_is_visible_and_does_not_start_image_timer():
    camera = FakeCamera(state=tango.DevState.ON, start_succeeds=False)
    camera.last_error = "camera rejected acquisition"
    widget, button, status = make_widget(camera)

    Basler_camera.grab_clicked(widget)

    assert camera.calls == ["start_grabbing"]
    assert widget.grabbing is False
    assert widget.timer.running is False
    assert button.text == "Grab failed"
    assert "camera rejected acquisition" in status.text
