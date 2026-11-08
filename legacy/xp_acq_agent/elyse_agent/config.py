from __future__ import print_function

import copy
import json
import os

from .errors import ConfigError


DEFAULT_CONFIG = {
    "agent_name": "elyse-acq-xp",
    "mode": "discover_only",
    "bind_host": "127.0.0.1",
    "command_port": 8765,
    "max_frame_bytes": 1048576,
    "socket_timeout_seconds": 10.0,
    "allow_input_task_creation": False,
    "allow_hardware_writes": False,
    "allow_remote_shutdown": False,
    "audit_path": "runtime/audit.jsonl",
    "data_path": "data",
}


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _absolute_from_root(path_value):
    if os.path.isabs(path_value):
        return os.path.abspath(path_value)
    return os.path.abspath(os.path.join(_project_root(), path_value))


def load_config(path=None):
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path:
        with open(path, "r") as stream:
            supplied = json.load(stream)
        if not isinstance(supplied, dict):
            raise ConfigError("configuration root must be an object")
        unknown = sorted(set(supplied) - set(DEFAULT_CONFIG))
        if unknown:
            raise ConfigError("unknown configuration keys: {0}".format(", ".join(unknown)))
        config.update(supplied)

    if config["mode"] not in ("simulation", "discover_only"):
        raise ConfigError("mode must be simulation or discover_only")
    if not isinstance(config["bind_host"], str) or not config["bind_host"]:
        raise ConfigError("bind_host must be a non-empty string")
    if not isinstance(config["command_port"], int) or not 1 <= config["command_port"] <= 65535:
        raise ConfigError("command_port must be in 1..65535")
    if not isinstance(config["max_frame_bytes"], int) or config["max_frame_bytes"] < 256:
        raise ConfigError("max_frame_bytes must be at least 256")
    if float(config["socket_timeout_seconds"]) <= 0:
        raise ConfigError("socket_timeout_seconds must be positive")
    if config["allow_hardware_writes"] is not False:
        raise ConfigError(
            "hardware writes are not commissioned in this release; "
            "allow_hardware_writes must remain false"
        )
    if not isinstance(config["allow_input_task_creation"], bool):
        raise ConfigError("allow_input_task_creation must be true or false")
    config["audit_path"] = _absolute_from_root(config["audit_path"])
    config["data_path"] = _absolute_from_root(config["data_path"])
    return config
