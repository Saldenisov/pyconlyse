import sys
import types
from types import SimpleNamespace


# The software-only collection lane provides inert Taurus package shells.
# Supply only the symbols required to import the OWIS widget; these tests call
# its command handler without constructing Qt widgets or connecting to Tango.
sys.modules["taurus"].Device = object
qt_module = sys.modules["taurus.external.qt"]
qt_module.Qt = SimpleNamespace()

button_module = sys.modules["taurus.qt.qtgui.button"]
button_module.TaurusCommandButton = object

display_module = types.ModuleType("taurus.qt.qtgui.display")
display_module.TaurusLabel = object
display_module.TaurusLed = object
sys.modules[display_module.__name__] = display_module

input_module = sys.modules["taurus.qt.qtgui.input"]
input_module.TaurusValueLineEdit = object
input_module.TaurusWheelEdit = object

widget_module = types.ModuleType("DeviceServers.shared.DS_Widget")
widget_module.DS_General_Widget = object
widget_module.VisType = SimpleNamespace(FULL="full")
sys.modules[widget_module.__name__] = widget_module

my_widgets_module = types.ModuleType("gui.MyWidgets")
my_widgets_module.MyQLabel = object
sys.modules[my_widgets_module.__name__] = my_widgets_module

from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor


class FakeLineEdit:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class FakeDevice:
    def __init__(self):
        self.moves = []

    def move_axis(self, command):
        self.moves.append(command)

    def define_position_axis(self, _command):
        raise AssertionError("Move control must not redefine the current coordinate")


def test_absolute_move_control_commands_selected_axis():
    device = FakeDevice()
    widget = SimpleNamespace(
        dev_name="owis",
        ds_owis=device,
        pos_lineedit3_owis=FakeLineEdit("-12.5"),
    )

    OWIS_motor.set_clicked(widget, 3)

    assert device.moves == [[3, -12.5]]


def test_absolute_move_control_ignores_invalid_position():
    device = FakeDevice()
    widget = SimpleNamespace(
        dev_name="owis",
        ds_owis=device,
        pos_lineedit3_owis=FakeLineEdit("not-a-position"),
    )

    OWIS_motor.set_clicked(widget, 3)

    assert device.moves == []
