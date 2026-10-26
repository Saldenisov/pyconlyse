"""Explicit cold command transport setup; no NI imports or hardware actions.

Provision a separate shared command key. Preserve every commissioning flag,
ownership record and calibration byte. Run only with the GUI listener closed.
Python 3.4 compatible. Key contents must never enter diagnostics or Git.
"""
import hashlib
import json
import os
import socket


def require_closed():
    connection = socket.socket()
    connection.settimeout(1)
    try:
        if connection.connect_ex(("127.0.0.1", 8772)) == 0:
            raise RuntimeError("Close the unified server on 8772 first")
    finally:
        connection.close()


def read(path):
    with open(path, "rb") as stream:
        return stream.read()


def atomic_write(path, value):
    temporary = path + ".command-transport-new"
    created = False
    try:
        with open(temporary, "xb") as stream:
            created = True
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if created and os.path.exists(temporary):
            os.unlink(temporary)


def configure(target, key, closed_check=require_closed, write=atomic_write):
    closed_check()
    key = key.strip()
    if len(key) < 32:
        raise ValueError("Separate command key of at least 32 bytes required")
    base_path = os.path.join(target, "config.acquisition.json")
    control_path = os.path.join(target, "config.acquisition.control.json")
    manifest_path = os.path.join(target, "manifest.json")
    base_bytes, control_bytes, manifest_bytes = [read(path) for path in
        (base_path, control_path, manifest_path)]
    base = json.loads(base_bytes.decode("utf-8"))
    read_key_path = os.path.join(target, base["key_file"])
    if key == read(read_key_path).strip():
        raise ValueError("Command and telemetry keys must differ")
    control = json.loads(control_bytes.decode("utf-8"))
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    digest = hashlib.sha256(key).hexdigest()
    relative_key = "runtime/acquisition-command-" + digest[:16] + ".key"
    key_path = os.path.join(target, *relative_key.split("/"))
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    if os.path.exists(key_path):
        if read(key_path) != key:
            raise RuntimeError("Existing command key path contains different bytes")
    else:
        with open(key_path, "xb") as stream:
            stream.write(key)
            stream.flush()
            os.fsync(stream.fileno())
    control.update(remote_control_enabled=True, command_key_file=relative_key)
    updated = json.dumps(control, indent=2).encode("utf-8")
    records = [item for item in manifest["files"] if item["path"] == "config.acquisition.control.json"]
    if len(records) != 1:
        raise ValueError("Exact installed control configuration record required")
    records[0]["sha256"] = hashlib.sha256(updated).hexdigest()
    manifest["command_transport_override"] = "Explicit separate command key; commissioning flags unchanged"
    backup = control_path + ".before-command-transport-" + hashlib.sha256(control_bytes).hexdigest()[:16]
    if not os.path.exists(backup):
        with open(backup, "xb") as stream:
            stream.write(control_bytes)
    write_attempted = False
    try:
        closed_check()
        if read(base_path) != base_bytes or read(control_path) != control_bytes:
            raise RuntimeError("Configuration changed during preflight")
        write_attempted = True
        write(control_path, updated)
        write(manifest_path, json.dumps(manifest, indent=2).encode("utf-8"))
        if read(base_path) != base_bytes:
            raise RuntimeError("Hardware configuration changed during transport setup")
    except Exception:
        if write_attempted:
            atomic_write(control_path, control_bytes)
            atomic_write(manifest_path, manifest_bytes)
        raise
    return dict(remote_control_enabled=True, command_key_sha256=digest,
                commissioning_configuration_preserved=True, backup=backup,
                hardware_commands_sent=False, cards_initialized=False)
