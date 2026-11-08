"""Implementation for _v0_targets and related operations."""


def _bind_pump_probe_v0_api_parts_v0_targets(api):
    """Bind implementation to the owning module and its runtime state."""

    def _v0_targets(config, action):
        aggregator = str(config["owis_aggregator_device"])
        backend = str(config["owis_backend_device"])
        andor = str(config["andor_device"])
        dg645 = str(config["dg645_device"])
        daqmx = str(config["daqmx_device"])
        if action == "v0.initialize":
            targets = [
                {"device": backend, "command": "get_status_axis"},
                {"device": backend, "command": "read_position_axis"},
                {"device": backend, "command": "turn_on_axis"},
                {"device": dg645, "command": "scpi_query"},
                {"device": daqmx, "command": "read_counter"},
            ]
            for output in api.V0_PREPARATION_NETIO_OUTPUTS:
                targets.append({"device": str(output["device"]), "command": "set_channels_states"})
            preparation_devices = (
                *api.V0_PREPARATION_PDU_DEVICES, *api.V0_CAMERA_DEVICES, *api.V0_LASER_POINTING_DEVICES,
                aggregator, backend, str(config["owis_legacy_device"]),
                dg645, daqmx,
            )
            for device in preparation_devices:
                targets.extend(
                    {"device": device, "command": command}
                    for command in ("recover", "turn_on", "Init")
                )
            targets.extend(
                {"device": api.V0_STARTER_DEVICE, "command": command}
                for command in ("DevStart",)
            )
            targets.extend({"device": camera, "command": "start_grabbing"}
                           for camera in api.V0_CAMERA_DEVICES)
            return targets
        if action in {"v0.stage-move", "v0.sample-stage-move"}:
            return [{"device": aggregator, "command": "move_axis"}]
        if action in {"v0.stage-stop", "v0.sample-stage-stop"}:
            return [{"device": aggregator, "command": "stop_axis"}]
        if action == "v0.run":
            return [
                {"device": dg645, "command": "scpi_write"},
                {"device": dg645, "command": "scpi_query"},
                {"device": andor, "command": "start_grabbing"},
                {"device": andor, "command": "register_order"},
                {"device": andor, "command": "is_order_ready"},
                {"device": andor, "command": "give_order"},
            ]
        if action == "v0.realtime":
            return [
                {"device": andor, "command": "start_grabbing"},
                {"device": andor, "command": "register_order"},
                {"device": andor, "command": "is_order_ready"},
                {"device": andor, "command": "give_order"},
            ]
        raise ValueError(f"Unsupported V0 hardware action: {action}")

    _v0_targets.__module__ = api.__name__
    _v0_targets.__qualname__ = "_v0_targets"

    return {
        "_v0_targets": _v0_targets,
    }
