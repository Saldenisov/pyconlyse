"""Cases collected through test_device_api_smoke.py."""

if __package__:
    from .test_device_api_smoke import (
        FakeAttributeConfig,
        FakeDevice,
        _make_client,
        importlib,
        json,
    )
else:
    from test_device_api_smoke import (
        FakeAttributeConfig,
        FakeDevice,
        _make_client,
        importlib,
        json,
    )


def test_laser_pointing_snapshot_exposes_convergence_and_interlock(monkeypatch):
    client, devices = _make_client(monkeypatch)
    controller_name = "manip/v0/laserpointing-cam1"
    camera_name = "manip/v0/cam1"
    x_name = "manip/v0/x1"
    y_name = "manip/v0/y1"
    stage_name = "manip/general/owis-aggregator"
    diaphragm_name = "manip/v0/dv01"
    half_wave_name = "manip/v0/l-2_1"
    flipper_name = "manip/v0/s1"
    controller = FakeDevice(
        controller_name,
        attributes={
            "get_rules": str({"point1": {"CrimpingDiaphragm1": 40}}),
            "get_ds_dict": str({
                "Camera": camera_name,
                "ActuatorX1": x_name,
                "ActuatorY1": y_name,
                "CrimpingDiaphragm1": diaphragm_name,
                "HalfWavePlate1": half_wave_name,
                "Shutter1": flipper_name,
                "TranslationStage1": (stage_name, [3]),
            }),
            "get_groups": str({
                "Actuators 1": ("ActuatorX1", "ActuatorY1"),
                "Translation stages": "TranslationStage1",
            }),
            "automatic_search_status": "running",
            "automatic_search_progress": json.dumps({
                "phase": "measuring",
                "roundness_error_pct": 3.2,
                "reference_roundness_pct": 96.0,
                "test_roundness_pct": 93.0,
            }),
            "automatic_search_config": json.dumps({
                "tolerance_px": 2,
                "roundness_tolerance_pct": 7,
            }),
            "automatic_search_history": json.dumps([
                {
                    "elapsed_s": 4.5,
                    "roundness_error_pct": 3.2,
                    "error_px": 3.2,
                    "actuator_group": 1,
                    "diaphragm": 1,
                }
            ]),
            "adaptive_search_model_json": json.dumps({
                "group1": {"point3": {"safe_step": 2.5}},
            }),
            "alignment_reference_json": json.dumps({
                "revision": 2,
                "accepted_at_utc": "2026-09-18T08:00:00+00:00",
            }),
            "alignment_reference_revision": 2,
            "alignment_pending_reference_json": json.dumps({
                "session_id": "pending-session",
            }),
            "alignment_session_event_json": json.dumps({
                "event_type": "search_completed",
            }),
            "alignment_session_event_count": 12,
            "active_point": "point3",
            "active_actuator_group": 1,
            "actuator_initialization_status": json.dumps({
                "phase": "ready_to_initialize",
                "group": 1,
            }),
        },
    )
    controller.get_command_list = lambda: [
        "start_automatic_search",
        "pause_automatic_search",
        "resume_automatic_search",
        "cancel_automatic_search",
        "accept_alignment_reference",
        "save_current_alignment_reference",
        "apply_controller_point",
        "select_manual_point",
        "initialize_active_pair",
        "move_active_actuator",
    ]
    devices[controller_name] = controller
    devices[camera_name] = FakeDevice(
        camera_name, attributes={
            "cg": "{'X': 12, 'Y': 18}",
            "cg_valid": True,
            "isgrabbing": True,
            "beam_visibility_status": "beam_visible",
            "beam_visibility_message": "A distinct laser beam is visible.",
            "ambient_light_high": False,
            "beam_background": 12.5,
            "beam_contrast": 180.0,
            "beam_foreground_fraction": 0.24,
        }
    )
    devices[x_name] = FakeDevice(x_name, attributes={
        "position": 1.5,
        "hardware_connection_state": "READY",
        "initialization_state": "SUCCEEDED",
        "hardware_lifecycle_status": "axis ready",
    })
    devices[y_name] = FakeDevice(y_name, attributes={
        "position": -2.0,
        "hardware_connection_state": "DISCONNECTED",
        "initialization_state": "NOT_REQUESTED",
        "hardware_lifecycle_status": "USB unavailable",
    })
    devices[x_name]._state = "ON"
    devices[y_name]._state = "STANDBY"
    devices[stage_name] = FakeDevice(stage_name, attributes={
        "pos3": -700.0,
        "hardware_connection_state": "READY",
        "initialization_state": "SUCCEEDED",
        "hardware_lifecycle_status": "OWIS ready",
    })
    devices[diaphragm_name] = FakeDevice(
        diaphragm_name,
        attributes={
            "position": 40.0,
            "hardware_connection_state": "READY",
            "initialization_state": "SUCCEEDED",
            "hardware_lifecycle_status": "diaphragm ready",
        },
        attr_configs={"position": FakeAttributeConfig(unit="%")},
    )
    devices[half_wave_name] = FakeDevice(
        half_wave_name,
        attributes={
            "position": 100.0,
            "hardware_connection_state": "READY",
            "initialization_state": "SUCCEEDED",
            "hardware_lifecycle_status": "wave plate ready",
        },
        attr_configs={"position": FakeAttributeConfig(unit="%")},
    )
    devices[flipper_name] = FakeDevice(
        flipper_name,
        attributes={
            "position": 0.0,
            "commanded_flipper_state": "UP_BLOCKED",
        },
        attr_configs={"position": FakeAttributeConfig(unit="state")},
    )
    fake_db = importlib.import_module("device_api").tango_gateway.create_database()
    fake_db.properties[diaphragm_name] = {
        "friendly_name": ["IrisExp_1"],
        "preset_pos": ["0", "5", "10", "15", "25", "40", "100"],
        "unit": ["%"],
        "limit_min": ["0"],
        "limit_max": ["100"],
    }
    fake_db.properties[half_wave_name] = {
        "friendly_name": ["Lambda_2_Exp"],
        "preset_pos": ["0", "5", "10", "15", "20", "50", "100"],
        "unit": ["%"],
        "limit_min": ["0"],
        "limit_max": ["100"],
    }

    response = client.get(f"/api/laser-pointing/{controller_name}/snapshot")
    payload = response.get_json()

    assert response.status_code == 200
    snapshot = payload["snapshot"]
    assert snapshot["capabilities"]["interlocked_motion"] is True
    assert snapshot["capabilities"]["manual_point_selection"] is True
    assert snapshot["capabilities"]["initialize_active_pair"] is True
    assert snapshot["capabilities"]["pause_search"] is True
    assert snapshot["capabilities"]["resume_search"] is True
    assert snapshot["capabilities"]["cancel_search_keep_current"] is True
    assert snapshot["capabilities"]["accept_alignment_reference"] is True
    assert snapshot["capabilities"]["save_current_alignment_reference"] is True
    assert snapshot["active_point"] == "point3"
    assert snapshot["active_actuator_group"] == 1
    assert snapshot["automatic_search"]["history"][0]["elapsed_s"] == 4.5
    assert (
        snapshot["automatic_search"]["history"][0]["roundness_error_pct"]
        == 3.2
    )
    assert snapshot["automatic_search"]["config"]["roundness_tolerance_pct"] == 7
    assert (
        snapshot["automatic_search"]["adaptive_model"]["group1"]["point3"][
            "safe_step"
        ]
        == 2.5
    )
    assert snapshot["automatic_search"]["reference_revision"] == 2
    assert snapshot["automatic_search"]["pending_reference"]["session_id"] == "pending-session"
    assert snapshot["automatic_search"]["session_event_count"] == 12
    assert snapshot["pair_initialization"]["group"] == 1
    assert snapshot["camera"]["grabbing"] is True
    assert snapshot["camera"]["beam_visibility_status"] == "beam_visible"
    assert snapshot["camera"]["ambient_light_high"] is False
    assert snapshot["camera"]["beam_background"] == 12.5
    assert snapshot["camera"]["beam_contrast"] == 180.0
    assert snapshot["camera"]["beam_foreground_fraction"] == 0.24
    assert snapshot["actuators"][0]["ready"] is True
    assert snapshot["actuators"][0]["move_supported"] is True
    assert snapshot["actuators"][1]["disconnected"] is True
    assert snapshot["diaphragms"] == [{
        "role": "CrimpingDiaphragm1",
        "control_type": "diaphragm",
        "friendly_name": "IrisExp_1",
        "device": diaphragm_name,
        "position": 40.0,
        "preset_positions": [0.0, 5.0, 10.0, 15.0, 25.0, 40.0, 100.0],
        "unit": "%",
        "minimum": 0.0,
        "maximum": 100.0,
        "state": "ON",
        "move_supported": True,
        "stop_supported": True,
        "hardware_connection_state": "READY",
        "initialization_state": "SUCCEEDED",
        "hardware_lifecycle_status": "diaphragm ready",
        "disconnected": False,
        "ready": True,
    }]
    assert snapshot["other_devices"][1] == {
        "role": "HalfWavePlate1",
        "control_type": "half_wave_plate",
        "friendly_name": "Lambda_2_Exp",
        "device": half_wave_name,
        "position": 100.0,
        "preset_positions": [0.0, 5.0, 10.0, 15.0, 20.0, 50.0, 100.0],
        "unit": "%",
        "minimum": 0.0,
        "maximum": 100.0,
        "state": "ON",
        "move_supported": True,
        "stop_supported": True,
        "hardware_connection_state": "READY",
        "initialization_state": "SUCCEEDED",
        "hardware_lifecycle_status": "wave plate ready",
        "disconnected": False,
        "ready": True,
    }
    flipper = next(
        item for item in snapshot["other_devices"] if item["role"] == "Shutter1"
    )
    assert flipper["position"] == 0.0
    assert flipper["commanded_flipper_state"] == "UP_BLOCKED"
    assert snapshot["manual_devices"] == [{
        "role": "TranslationStage1",
        "device": stage_name,
        "state": "ON",
        "axes": [{"axis": 3, "position": -700.0}],
        "move_supported": True,
        "hardware_connection_state": "READY",
        "initialization_state": "SUCCEEDED",
        "hardware_lifecycle_status": "OWIS ready",
        "disconnected": False,
        "ready": True,
    }]

def test_stopped_camera_image_read_does_not_restart_acquisition(monkeypatch):
    client, devices = _make_client(monkeypatch)
    camera_name = "manip/v0/stopped-camera"
    camera = FakeDevice(camera_name, attributes={
        "isgrabbing": False,
        "image": [[1, 2], [3, 4]],
        "cg": "{'X': 1, 'Y': 1}",
    })
    reads = []
    original_read = camera.read_attribute

    def tracked_read(attribute_name):
        reads.append(attribute_name)
        return original_read(attribute_name)

    camera.read_attribute = tracked_read
    devices[camera_name] = camera

    response = client.get(f"/api/camera/{camera_name}/image")
    payload = response.get_json()

    assert response.status_code == 409
    assert payload["grabbing"] is False
    assert payload["success"] is False
    assert reads == ["isgrabbing"]

def test_camera_image_can_include_current_camera_specific_contours(monkeypatch):
    client, devices = _make_client(monkeypatch)
    camera_name = "manip/v0/cam2_v0"
    devices[camera_name] = FakeDevice(camera_name, attributes={
        "isgrabbing": True,
        "image": [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]],
        "cg": "{'X': 1, 'Y': 1}",
        "center_gravity_threshold": 120,
        "width": 2,
        "height": 2,
    })
    metrics = importlib.import_module(
        "DeviceServers.control.laser_pointing.beam_metrics"
    )
    monkeypatch.setattr(
        metrics,
        "camera_contour_profile",
        lambda device, threshold: {
            "threshold": 20.0,
            "relative_heights": (0.03, 0.20, 0.75),
        },
    )
    monkeypatch.setattr(
        metrics,
        "beam_threshold_contours",
        lambda image, **settings: [{
            "relative_height": 0.20,
            "centre": [1.0, 1.0],
            "radius_px": 0.5,
            "points": [[0.5, 1.0], [1.5, 1.0]],
        }],
    )

    response = client.get(f"/api/camera/{camera_name}/image?contours=1")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["contour_profile"] == {
        "threshold": 20.0,
        "relative_heights": [0.03, 0.20, 0.75],
    }
    assert payload["contours"] == [{
        "relative_height": 0.20,
        "centre": [1.0, 1.0],
        "radius_px": 0.5,
    }]
    assert payload["contour_error"] == ""

def test_camera_stop_command_confirms_stopped_state(monkeypatch):
    client, devices = _make_client(monkeypatch)
    camera_name = "manip/v0/grabbing-camera"
    camera = FakeDevice(camera_name, attributes={"isgrabbing": True})
    camera.get_command_list = lambda: ["start_grabbing", "stop_grabbing"]

    def command(command_name, args=None):
        camera.command_calls.append((command_name, args))
        if command_name == "stop_grabbing":
            camera.attributes["isgrabbing"] = False
        return 0

    camera.command_inout = command
    devices[camera_name] = camera

    response = client.post(
        f"/api/camera/{camera_name}/grabbing",
        json={"action": "stop"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["grabbing"] is False
    assert payload["state_confirmed"] is True
    assert camera.command_calls == [("stop_grabbing", None)]

def test_camera_start_powers_on_an_off_camera_first(monkeypatch):
    client, devices = _make_client(monkeypatch)
    camera_name = "manip/v0/off-camera"
    camera = FakeDevice(camera_name, state="OFF", attributes={"isgrabbing": False})
    camera.get_command_list = lambda: [
        "turn_on", "start_grabbing", "stop_grabbing"
    ]

    def command(command_name, args=None):
        camera.command_calls.append((command_name, args))
        if command_name == "turn_on":
            camera._state = "ON"
        if command_name == "start_grabbing":
            camera.attributes["isgrabbing"] = True
        return 0

    camera.command_inout = command
    devices[camera_name] = camera

    response = client.post(
        f"/api/camera/{camera_name}/grabbing",
        json={"action": "start"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["powered_on"] is True
    assert payload["grabbing"] is True
    assert payload["state_confirmed"] is True
    assert camera.command_calls == [
        ("turn_on", None),
        ("start_grabbing", None),
    ]
