"""Cold opt-in test permission; never relabel hardware qualification as verified."""
import hashlib
import json
import os
import runpy


def configure(target, closed_check=None, write=None):
    helpers = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "configure_acq_command_transport.py"))
    closed_check = closed_check or helpers["require_closed"]
    write = write or helpers["atomic_write"]
    read = helpers["read"]
    closed_check()
    config_path = os.path.join(target, "config.acquisition.json")
    manifest_path = os.path.join(target, "manifest.json")
    before, manifest_before = read(config_path), read(manifest_path)
    config, manifest = json.loads(before.decode("utf-8")), json.loads(manifest_before.decode("utf-8"))
    original = dict(config)
    config["operator_supervised_test"] = True
    encoded = json.dumps(config, indent=2).encode("utf-8")
    records = [item for item in manifest["files"] if item["path"] == "config.acquisition.json"]
    if len(records) != 1:
        raise ValueError("Exact installed base configuration record required")
    records[0]["sha256"] = hashlib.sha256(encoded).hexdigest()
    manifest["supervised_test_override"] = "Operator-stepped test; physical qualification flags unchanged"
    backup = config_path + ".before-supervised-test-" + hashlib.sha256(before).hexdigest()[:16]
    if not os.path.exists(backup):
        with open(backup, "xb") as stream:
            stream.write(before)
    attempted = False
    try:
        closed_check()
        if read(config_path) != before or read(manifest_path) != manifest_before:
            raise RuntimeError("Configuration changed during supervised-mode preflight")
        attempted = True
        write(config_path, encoded)
        write(manifest_path, json.dumps(manifest, indent=2).encode("utf-8"))
        installed = json.loads(read(config_path).decode("utf-8"))
        installed.pop("operator_supervised_test")
        original.pop("operator_supervised_test", None)
        if installed != original:
            raise RuntimeError("Unrelated hardware configuration changed")
    except Exception:
        if attempted:
            helpers["atomic_write"](config_path, before)
            helpers["atomic_write"](manifest_path, manifest_before)
        raise
    return dict(operator_supervised_test=True, physical_qualification_changed=False,
                backup=backup, hardware_commands_sent=False, cards_initialized=False)
