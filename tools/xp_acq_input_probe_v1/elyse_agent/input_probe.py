"""One-card-at-a-time NI-DAQmx input probe for the XP acquisition host.

Only analog-input channels are eligible. On PCI-DIO-96, creating a digital
input task may reconfigure an 8255 chip and reset neighboring output ports.
Each attempted measurement owns one short-lived input task and closes it.
The normal acquisition task timing/trigger is deliberately not configured:
this probe asks the driver for one software-timed sample of each channel.
"""

from __future__ import division

import datetime

from .daqmx_backend import AI_TASK_SPECS


INPUT_CARDS = dict((spec["name"], spec) for spec in AI_TASK_SPECS)


def _timestamp():
    return datetime.datetime.utcnow().isoformat() + "Z"


def _device_number(task_name):
    return task_name.split("_", 1)[0][1:]


def _index_range(spec, index):
    for key, limits in spec["ranges"].items():
        if key == "default":
            continue
        if ":" in key:
            first, last = (int(part) for part in key.split(":"))
        else:
            first = last = int(key)
        if first <= index <= last:
            return tuple(limits)
    return tuple(spec["ranges"]["default"])


def discover_inventory(daqmx=None):
    if daqmx is None:
        import nidaqmx as daqmx

    system = daqmx.system.System.local()
    version = system.driver_version
    devices = []
    for device in system.devices:
        card = {
            "name": device.name,
            "product_type": device.product_type,
            "channel_counts": {},
            "channel_bounds": {},
            "query_errors": {},
        }
        for kind, attribute in (
            ("ai", "ai_physical_chans"),
            ("ao", "ao_physical_chans"),
            ("di", "di_lines"),
            ("do", "do_lines"),
            ("ci", "ci_physical_chans"),
            ("co", "co_physical_chans"),
        ):
            try:
                names = list(getattr(device, attribute).channel_names)
                card["channel_counts"][kind] = len(names)
                card["channel_bounds"][kind] = [names[0], names[-1]] if names else []
            except Exception as error:
                card["query_errors"][kind] = "{0}: {1}".format(
                    type(error).__name__, error
                )
        for key, attribute, convert in (
            ("serial_number", "dev_serial_num", int),
            ("simulated", "dev_is_simulated", bool),
        ):
            try:
                card[key] = convert(getattr(device, attribute))
            except Exception as error:
                card["query_errors"][key] = "{0}: {1}".format(
                    type(error).__name__, error
                )
        card["successful_channel_queries"] = len(card["channel_counts"])
        card["status"] = "queried" if len(card["channel_counts"]) == 6 else "partial"
        devices.append(card)
    return {
        "timestamp_utc": _timestamp(),
        "driver_version": "{0}.{1}.{2}".format(
            version.major_version, version.minor_version, version.update_version
        ),
        "device_count": len(devices),
        "devices": devices,
        "tasks_created": 0,
        "hardware_writes": False,
        "readings_taken": 0,
    }


def _read_analog(daqmx, task_name, channel_index, timeout_seconds, terminal_mode):
    spec = INPUT_CARDS[task_name]
    physical = "/{0}/ai{1}".format(_device_number(task_name), channel_index)
    minimum, maximum = _index_range(spec, channel_index)
    task = daqmx.Task()
    try:
        task.ai_channels.add_ai_voltage_chan(
            physical,
            terminal_config=getattr(daqmx.constants.TerminalConfiguration, terminal_mode),
            min_val=minimum,
            max_val=maximum,
        )
        value = float(task.read(timeout=float(timeout_seconds)))
        return {
            "physical_channel": physical,
            "terminal_configuration": terminal_mode,
            "value": value,
            "unit": "V",
        }
    finally:
        task.close()


def probe_card(task_name, scope="first", timeout_seconds=2.0, daqmx=None):
    """Read first input or whole card; stop at first driver error.

    No digital, output, or counter task can be requested through this function.
    """
    if task_name not in INPUT_CARDS:
        raise ValueError("unsupported input card: {0}".format(task_name))
    if scope not in ("first", "all", "ai8_rse", "ai8_plus_rse"):
        raise ValueError("unsupported analog probe scope")
    if not 0 < float(timeout_seconds) <= 10:
        raise ValueError("timeout_seconds must be in (0, 10]")
    if daqmx is None:
        import nidaqmx as daqmx

    spec = INPUT_CARDS[task_name]
    count = int(spec["physical_channels"].rsplit(":", 1)[1]) + 1
    if scope == "first":
        channels = range(1)
    elif scope == "all":
        channels = range(count)
    elif scope == "ai8_rse":
        channels = range(8, 9)
    else:
        channels = range(8, count)
    report = {
        "timestamp_utc": _timestamp(),
        "card": task_name,
        "device": _device_number(task_name),
        "kind": "analog_input",
        "scope": scope,
        "terminal_configuration": "DIFFERENTIAL ai0:7; RSE ai8+" if scope == "all" else (
            "DIFFERENTIAL" if scope == "first" else "RSE"
        ),
        "interpretation": "raw diagnostic; terminal wiring not yet verified",
        "expected_channels": count,
        "attempted": 0,
        "read_count": 0,
        "results": [],
        "error": None,
        "hardware_writes": False,
        "status": "pending",
    }
    for index in channels:
        terminal_mode = "DIFFERENTIAL" if index < 8 and scope in ("first", "all") else "RSE"
        report["attempted"] += 1
        try:
            result = _read_analog(daqmx, task_name, index, timeout_seconds, terminal_mode)
        except Exception as error:
            report["error"] = {
                "index": index,
                "type": type(error).__name__,
                "message": str(error),
            }
            report["status"] = "failed"
            break
        report["results"].append(result)
        report["read_count"] += 1
    if report["error"] is None:
        report["status"] = "complete"
    report["completed_utc"] = _timestamp()
    return report
