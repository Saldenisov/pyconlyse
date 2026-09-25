"""The Qt panel reads millimetres and moves only after an operator click."""

import pytest


def test_zaber_widget_is_passive_until_move(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PyQt5.QtWidgets")
    from DeviceServers.motion.zaber import DS_Zaber_Widget as widget_module

    class FakeProxy:
        def __init__(self):
            self.commands = []

        def set_timeout_millis(self, _value):
            pass

        def state(self):
            return "ON"

        def status(self):
            return "Ready"

        def read_attribute(self, name):
            values = {"minimum_mm": 0.0, "maximum_mm": 50.8, "position_mm": 12.5}
            return type("Attribute", (), {"value": values[name]})()

        def command_inout(self, name, value=None):
            self.commands.append((name, value))

    fake = FakeProxy()
    monkeypatch.setattr(widget_module, "DeviceProxy", lambda _name: fake)
    app = widgets.QApplication.instance() or widgets.QApplication([])
    panel = widget_module.ZaberStageWidget()
    try:
        assert panel.position_label.text() == "Position: 12.500000 mm"
        assert fake.commands == []
        panel.target.setValue(20.25)
        panel._move()
        assert fake.commands == [("MoveAbsoluteMm", 20.25)]
    finally:
        panel.close()
        del app
