"""Cases collected through test_motion_recovery.py."""

if __package__:
    from .test_motion_recovery import (
        _make_owis_delay_line_stub,
        aggregator_module,
        types,
    )
else:
    from test_motion_recovery import (
        _make_owis_delay_line_stub,
        aggregator_module,
        types,
    )


def test_owis_aggregator_logs_expected_power_off_as_information():
    logs = []
    device = types.SimpleNamespace(
        device_name="OWIS Aggregator",
        _backend_alive={"three": True},
        _backend_proxies={"three": object()},
        _backend_reason={"three": ""},
        info=lambda message, *_args: logs.append(("info", message)),
        error=lambda message: logs.append(("error", message)),
    )

    aggregator_module.DS_OWIS_Aggregator._mark_backend_down(
        device, "three", "OWIS controller power is OFF (PDU output 2)"
    )

    assert device._backend_alive["three"] is False
    assert device._backend_proxies["three"] is None
    assert logs == [
        (
            "info",
            "OWIS Aggregator: backend 'three' is down: "
            "OWIS controller power is OFF (PDU output 2)",
        )
    ]

def test_owis_delay_line_status_and_read_position_have_explicit_results(monkeypatch):
    module, device, state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device._get_axis_state_ps90 = lambda *_args: (3, "")
    assert cls.get_controller_status_local(device) == 0
    assert state["value"] == module.DevState.ON

    device._get_axis_state_ps90 = lambda *_args: (0, "axis inactive")
    assert "not active" in cls.get_controller_status_local(device)
    assert state["value"] == module.DevState.FAULT

    device._get_pos_ex_ps90 = lambda *_args: (12.5, "")
    assert cls.read_position_local(device) == 0
    assert device._position == 12.5

    device._get_pos_ex_ps90 = lambda *_args: (False, "read failed")
    assert "read failed" in cls.read_position_local(device)

def test_owis_delay_line_power_contracts_return_zero_only_on_success(monkeypatch):
    module, device, _state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device._motor_init_ps90 = lambda *_args: (True, "")
    device._set_target_mode_ps90 = lambda *_args: (True, "")
    device._motor_off_ps90 = lambda *_args: (True, "")
    assert cls.turn_on_local(device) == 0

    device._set_target_mode_ps90 = lambda *_args: (False, "mode failed")
    assert "mode failed" in cls.turn_on_local(device)

    device._stop_axis_ps90 = lambda *_args: (True, "")
    device._motor_off_ps90 = lambda *_args: (True, "")
    assert cls.turn_off_local(device) == 0

    device._stop_axis_ps90 = lambda *_args: (False, "stop failed")
    assert "stop failed" in cls.turn_off_local(device)

def test_owis_delay_line_motion_contracts_return_zero_only_on_success(monkeypatch):
    module, device, _state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device._set_target_ex_ps90 = lambda *_args: (True, "")
    device._go_target_ps90 = lambda *_args: (True, "")
    assert cls.move_axis_local(device, 3.25) == 0

    device._set_target_ex_ps90 = lambda *_args: (False, "target failed")
    assert "target failed" in cls.move_axis_local(device, 3.25)

    device._stop_axis_ps90 = lambda *_args: (True, "")
    device._motor_off_ps90 = lambda *_args: (True, "")
    assert cls.stop_movement_local(device) == 0

    device._stop_axis_ps90 = lambda *_args: (False, "stop failed")
    assert "stop failed" in cls.stop_movement_local(device)

def test_owis_delay_line_write_position_propagates_move_result(monkeypatch):
    module, device, _state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device.move_axis = lambda position: 0 if position == 1.0 else "move rejected"

    assert cls.write_position_local(device, 1.0) == 0
    assert cls.write_position_local(device, 2.0) == "move rejected"
