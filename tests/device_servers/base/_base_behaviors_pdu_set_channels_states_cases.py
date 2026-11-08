"""Cases collected through test_base_behaviors.py."""

if __package__:
    from .test_base_behaviors import (
        BlockingDummyMonoMotor,
        BlockingDummyMultiMotor,
        DummyCamera,
        DummyCameraCCD,
        DummyMonoMotor,
        DummyMultiMotor,
        DummyPDU,
        Thread,
        camera_module,
        general_module,
        np,
    )
else:
    from test_base_behaviors import (
        BlockingDummyMonoMotor,
        BlockingDummyMultiMotor,
        DummyCamera,
        DummyCameraCCD,
        DummyMonoMotor,
        DummyMultiMotor,
        DummyPDU,
        Thread,
        camera_module,
        general_module,
        np,
    )


def test_pdu_set_channels_states_uses_timing_wrapper():
    device = DummyPDU()

    device.set_channels_states([1, 0])

    assert device.timed_calls == ["set_channels_states_local"]
    assert device.set_calls == [[1, 0]]

def test_pdu_set_channels_states_is_blocked_in_fault_state():
    device = DummyPDU()
    device.set_state(general_module.DevState.FAULT)

    device.set_channels_states([1, 1])

    assert device.set_calls == []

def test_motor_important_parameters_include_presets():
    device = DummyMonoMotor()

    assert device.important_parameters() == [0.0, 10.0, 5.0, 1.0, 2.5]

def test_motor_write_position_calls_local_within_limits():
    device = DummyMonoMotor()

    device.write_position(7.5)

    assert device.last_written == 7.5
    assert device.get_pos() == 7.5

def test_motor_write_position_rejects_out_of_range_values():
    device = DummyMonoMotor()

    device.write_position(11)

    assert device.last_written is None
    assert "position out of limit" in device.last_error()

def test_motor_move_axis_rel_uses_current_position():
    device = DummyMonoMotor()
    device._position = 3.0

    device.move_axis_rel(2.5)

    assert device.last_moved_to == 5.5
    assert device.get_pos() == 5.5

def test_motor_stop_movement_runs_local_handler():
    device = DummyMonoMotor()

    device.stop_movement()

    assert device.stop_calls == 1
    assert device.controller_status_calls == 1

def test_motor_stop_movement_records_backend_failure():
    device = DummyMonoMotor()
    device.stop_result = "backend stop failed"

    device.stop_movement()

    assert device.stop_calls == 1
    assert device.controller_status_calls == 0
    assert "backend stop failed" in device.last_error()

def test_motor_explicit_zero_backend_result_refreshes_readback():
    device = DummyMonoMotor()
    device.move_result = 0
    device.stop_result = 0

    assert device.move_axis(7.5) == 0
    device.stop_movement()

    assert device.read_position_calls == 1
    assert device.controller_status_calls == 1
    assert device.last_error() == "..."

def test_motor_move_returns_backend_and_validation_failures():
    device = DummyMonoMotor()
    device.move_result = "backend move failed"

    assert device.move_axis(7.5) == "backend move failed"
    assert "backend move failed" in device.last_error()

    assert "position out of limit" in device.move_axis(11.0)

def test_motor_stop_does_not_wait_for_blocking_move():
    device = BlockingDummyMonoMotor()
    move_thread = Thread(target=device.move_axis, args=(7.5,))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    device.stop_movement()

    assert device.stop_calls == 1
    assert device.controller_status_calls == 1
    assert move_thread.is_alive()
    assert device.read_position_calls == 0

    device.release_move.set()
    move_thread.join(timeout=1.0)
    assert not move_thread.is_alive()
    assert device.read_position_calls == 0

def test_motor_rejects_concurrent_move_while_active_move_is_blocking():
    device = BlockingDummyMonoMotor()
    move_thread = Thread(target=device.move_axis, args=(7.5,))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    device.move_axis(6.0)

    assert device.last_moved_to == 7.5
    assert "another move is already in progress" in device.last_error()

    device.release_move.set()
    move_thread.join(timeout=1.0)
    assert not move_thread.is_alive()

def test_motor_rejects_new_move_while_stop_is_in_progress():
    device = BlockingDummyMonoMotor()
    device.block_stop = True
    move_thread = Thread(target=device.move_axis, args=(7.5,))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    stop_thread = Thread(target=device.stop_movement)
    stop_thread.start()
    assert device.stop_entered.wait(timeout=1.0)

    device.move_axis(6.0)
    assert device.last_moved_to == 7.5
    assert "stop is already in progress" in device.last_error()

    device.release_stop.set()
    stop_thread.join(timeout=1.0)
    device.release_move.set()
    move_thread.join(timeout=1.0)
    assert not stop_thread.is_alive()
    assert not move_thread.is_alive()

def test_motor_failed_stop_does_not_suppress_blocking_move_readback():
    device = BlockingDummyMonoMotor()
    device.stop_result = "backend stop failed"
    move_thread = Thread(target=device.move_axis, args=(7.5,))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    device.stop_movement()
    assert device.stop_calls == 1
    assert device.read_position_calls == 0

    device.release_move.set()
    move_thread.join(timeout=1.0)

    assert not move_thread.is_alive()
    assert device.read_position_calls == 1
    assert "backend stop failed" in device.last_error()

def test_motor_waits_for_stop_that_starts_during_post_move_readback():
    device = BlockingDummyMonoMotor()
    device.block_read = True
    device.block_stop = True
    device.release_move.set()
    move_thread = Thread(target=device.move_axis, args=(7.5,))

    move_thread.start()
    assert device.read_entered.wait(timeout=1.0)

    stop_thread = Thread(target=device.stop_movement)
    stop_thread.start()
    assert device.stop_entered.wait(timeout=1.0)

    device.release_read.set()
    assert move_thread.is_alive()

    device.release_stop.set()
    stop_thread.join(timeout=1.0)
    move_thread.join(timeout=1.0)

    assert not stop_thread.is_alive()
    assert not move_thread.is_alive()

def test_multi_motor_accessors_render_axis_snapshots():
    device = DummyMultiMotor()

    assert device.states() == "{1: 1, 2: 3}"
    assert device.positions() == "{1: 1.5, 2: 3.0}"
    assert device.device_names() == "{1: 'axis-1', 2: 'axis-2'}"
    assert device.friendly_names() == "{1: 'Axis 1', 2: 'Axis 2'}"

def test_multi_motor_move_axis_calls_local_when_allowed():
    device = DummyMultiMotor()

    result = device.move_axis([1, 4.25])

    assert result == "0"
    assert device.move_calls == [[1, 4.25]]
    assert device.positions() == "{1: 4.25, 2: 3.0}"

def test_multi_motor_absolute_move_alias_uses_array_command_contract():
    device = DummyMultiMotor()

    result = device.move_axis_abs([1.0, 4.25])

    assert result == "0"
    assert device.move_calls == [[1, 4.25]]

def test_multi_motor_move_axis_returns_message_when_state_disallowed():
    device = DummyMultiMotor()
    device.set_state(general_module.DevState.FAULT)

    result = device.move_axis([1, 4.25])

    assert "check_func_allowance" in result
    assert device.move_calls == []

def test_multi_motor_move_axis_rejects_unknown_axis_and_out_of_range_position():
    device = DummyMultiMotor()

    unknown_result = device.move_axis([99, 1.0])
    limit_result = device.move_axis([1, 11.0])

    assert unknown_result == "unknown axis 99"
    assert "outside axis 1 limits" in limit_result
    assert device.move_calls == []

def test_multi_motor_stop_does_not_wait_for_blocking_move():
    device = BlockingDummyMultiMotor()
    move_thread = Thread(target=device.move_axis, args=([1, 4.25],))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    assert device.stop_axis(1) == "0"
    assert device.stop_calls == 1
    assert move_thread.is_alive()

    device.release_move.set()
    move_thread.join(timeout=1.0)

    assert not move_thread.is_alive()
    assert device.read_position_calls == []

def test_multi_motor_rejects_same_axis_concurrent_move():
    device = BlockingDummyMultiMotor()
    move_thread = Thread(target=device.move_axis, args=([1, 4.25],))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    result = device.move_axis([1, 5.0])

    assert result == "Axis 1 move rejected: movement already in progress."
    assert device.move_calls == [[1, 4.25]]

    device.release_move.set()
    move_thread.join(timeout=1.0)
    assert not move_thread.is_alive()

def test_multi_motor_allows_independent_move_on_different_axis():
    device = BlockingDummyMultiMotor()
    move_thread = Thread(target=device.move_axis, args=([1, 4.25],))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    result = device.move_axis([2, 5.0])

    assert result == "0"
    assert device.move_calls == [[1, 4.25], [2, 5.0]]
    assert device.read_position_calls == [2]

    device.release_move.set()
    move_thread.join(timeout=1.0)
    assert not move_thread.is_alive()

def test_multi_motor_rejects_new_move_while_axis_stop_is_in_progress():
    device = BlockingDummyMultiMotor()
    device.block_stop = True
    move_thread = Thread(target=device.move_axis, args=([1, 4.25],))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    stop_thread = Thread(target=device.stop_axis, args=(1,))
    stop_thread.start()
    assert device.stop_entered.wait(timeout=1.0)

    result = device.move_axis([1, 5.0])
    assert result == "Axis 1 move rejected: stop is already in progress."

    device.release_stop.set()
    stop_thread.join(timeout=1.0)
    device.release_move.set()
    move_thread.join(timeout=1.0)
    assert not stop_thread.is_alive()
    assert not move_thread.is_alive()

def test_multi_motor_failed_stop_does_not_suppress_post_move_readback():
    device = BlockingDummyMultiMotor()
    device.stop_result = "backend stop failed"
    move_thread = Thread(target=device.move_axis, args=([1, 4.25],))

    move_thread.start()
    assert device.move_entered.wait(timeout=1.0)

    assert device.stop_axis(1) == "backend stop failed"
    assert device.stop_calls == 1

    device.release_move.set()
    move_thread.join(timeout=1.0)

    assert not move_thread.is_alive()
    assert device.read_position_calls == [1]
    assert "backend stop failed" in device.last_error()

def test_multi_motor_waits_for_stop_that_starts_during_readback():
    device = BlockingDummyMultiMotor()
    device.block_read = True
    device.block_stop = True
    device.release_move.set()
    move_thread = Thread(target=device.move_axis, args=([1, 4.25],))

    move_thread.start()
    assert device.read_entered.wait(timeout=1.0)

    stop_thread = Thread(target=device.stop_axis, args=(1,))
    stop_thread.start()
    assert device.stop_entered.wait(timeout=1.0)

    device.release_read.set()
    assert move_thread.is_alive()

    device.release_stop.set()
    stop_thread.join(timeout=1.0)
    move_thread.join(timeout=1.0)

    assert not stop_thread.is_alive()
    assert not move_thread.is_alive()

def test_camera_register_order_and_give_order_use_uint16_arrays():
    device = DummyCamera()

    assert device.register_order_local("ord-1", [3]) == 0
    returned = device.give_order_local("ord-1")

    assert returned.dtype == np.uint16
    assert device.orders["ord-1"].ready_to_delete is True
    assert returned.tolist() == [[100, 200, 300]]

def test_camera_give_order_returns_last_image_for_unknown_order():
    device = DummyCamera()
    device.last_image = np.array([9, 8, 7], dtype=np.int32)

    returned = device.give_order_local("missing")

    assert returned.dtype == np.uint16
    assert returned.tolist() == [9, 8, 7]

def test_camera_load_dll_uses_windll_and_unlocks(monkeypatch):
    device = DummyCamera()

    monkeypatch.setattr(
        camera_module.ctypes,
        "WinDLL",
        lambda path: {"loaded_from": path},
        raising=False,
    )

    dll = device.load_dll()

    assert dll == {"loaded_from": str(device.dll_path)}
    assert device._dll_lock is False

def test_camera_ccd_device_friendly_name_reads_and_caches_value():
    device = DummyCameraCCD()

    result = device.device_friendly_name()

    assert result == "CCD A"
    assert device.friendly_name == "CCD A"

def test_camera_ccd_write_camera_friendly_name_delegates_to_backend():
    device = DummyCameraCCD()

    device.write_camera_friendly_name("CCD B")

    assert device.camera_name == "CCD B"

def test_camera_ccd_write_exposure_time_updates_backend():
    device = DummyCameraCCD()

    device.write_exposure_time(0.25)

    assert device.exposure_writes == [0.25]
    assert device.exposure_time() == 0.25

def test_camera_ccd_set_param_after_init_calls_local_handler():
    device = DummyCameraCCD()

    device.set_param_after_init()

    assert device.param_after_init_calls == 1

def test_camera_ccd_init_does_not_power_or_configure_camera():
    device = DummyCameraCCD()

    device.init_device()

    assert device.turn_on_calls == 0
    assert device.param_after_init_calls == 0
    assert device.get_state() == general_module.DevState.OFF
    device.delete_device()

def test_camera_ccd_explicit_turn_on_applies_initial_parameters_once():
    device = DummyCameraCCD()
    device.set_state(general_module.DevState.OFF)

    device.turn_on()

    assert device.turn_on_calls == 1
    assert device.param_after_init_calls == 1

def test_camera_ccd_turn_on_applies_settings_when_discovery_already_is_on():
    device = DummyCameraCCD()
    device.set_state(general_module.DevState.ON)

    device.turn_on()

    assert device.turn_on_calls == 0
    assert device.param_after_init_calls == 1

def test_camera_ccd_grab_mode_commands_toggle_latestimage_flag():
    device = DummyCameraCCD()

    device.OneByOne()
    assert device.latestimage is False

    device.LatestImageOnly()
    assert device.latestimage is True

def test_camera_ccd_start_and_stop_grabbing_delegate_to_backend():
    device = DummyCameraCCD()

    device.start_grabbing()
    assert device.start_calls == 1
    assert device.grabbing is True

    device.stop_grabbing()
    assert device.stop_calls == 1
    assert device.grabbing is False

def test_camera_ccd_image_reads_from_backend():
    device = DummyCameraCCD()

    result = device.image()

    assert device.image_reads == 1
    assert result.tolist() == [1, 2, 3]

def test_camera_ccd_treat_orders_appends_data_and_completes_order():
    device = DummyCameraCCD()
    device.register_order_local("job-1", [2])

    device.treat_orders(np.array([[10, 20, 30], [11, 21, 31]], dtype=np.uint16))

    order = device.orders["job-1"]
    assert len(device.data_deque) == 2
    assert len(device.time_stamp_deque) == 2
    assert order.order_done is True
    assert order.order_array.shape == (3, 3)
    assert order.order_array[-1].tolist() == [11, 21, 31]

def test_camera_ccd_treat_orders_drops_stale_orders():
    device = DummyCameraCCD()
    device.register_order_local("stale-job", [5])
    device.orders["stale-job"].order_timestamp -= 101

    device.treat_orders(np.array([[1, 2, 3]], dtype=np.uint16))

    assert "stale-job" not in device.orders
