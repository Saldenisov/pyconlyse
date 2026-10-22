"""Package one XP owner and the existing unified telemetry Tango device."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
XP = ROOT / "legacy/xp_acq_control"
BRIDGE = ROOT / "DeviceServers/control/elyse_acq"


def package(destination, everest=False):
    destination = Path(destination).resolve()
    if destination.exists() or destination.with_suffix(".zip").exists():
        raise ValueError("New output directory and zip required; existing release preserved")
    files = []
    if everest:
        for name in ("DS_AcqTelemetry.py", "telemetry_sink.py", "telemetry_archive.py", "telemetry_archive.sql", "control_client.py", "control_runtime_client.py", "control_runtime_health.py",
                     "engine.py", "plans.py", "contracts.py", "simulator.py"):
            files.append((BRIDGE / name, "DeviceServers/control/elyse_acq/" + name))
        for name in ("__init__.py", "acquisition_remote.py", "acquisition_http.py", "runtime_identity.py", "native_telemetry.py",
                     "command_protocol.py", "command_broker.py", "command_http.py", "command_dispatch.py",
                     "standard_banks.py", "telemetry_publisher.py", "telemetry_view.py",
                     "shared_state.py", "labview_telemetry.py", "telemetry_relay.py", "protocol.py", "supervision_wire.py", "errors.py"):
            files.append((XP / "elyse_agent" / name, "legacy/xp_acq_control/elyse_agent/" + name))
        for name in ("__init__.py", "shared_state.py", "labview_telemetry.py", "telemetry_relay.py",
                     "protocol.py", "supervision_wire.py", "errors.py", "cooling_safety.py"):
            files.append((ROOT / "legacy/xp_acq_agent/elyse_agent" / name, "legacy/xp_acq_agent/elyse_agent/" + name))
        for name in ("DeviceServers/__init__.py", "DeviceServers/control/__init__.py", "DeviceServers/control/elyse_acq/__init__.py",
                     "legacy/__init__.py", "legacy/xp_acq_control/__init__.py"):
            files.append((ROOT / name, name))
        files.append((XP / "data/standard_telemetry_schema.json", "legacy/xp_acq_control/data/standard_telemetry_schema.json"))
    else:
        files = [(path, path.relative_to(XP).as_posix()) for path in XP.rglob("*")
                 if path.is_file() and path.suffix in (".py", ".pyw", ".csv", ".json")
                 and "__pycache__" not in path.parts]
    destination.mkdir(parents=True)
    manifest = dict(schema_version=1, role="everest_tango" if everest else "xp_python34",
                    release="everest-postgres-20261022-v1" if everest else "acq-isolated-telemetry-20261022-v8", default_xp_port=8772,
                    standard_bank_count=27, telemetry_port=8767, tango_device="elyse/acquisition/telemetry",
                    xp_modes=["IDLE: loopback VI bridge", "initialized: Python NI owner"],
                    vi_loopback_port=8766, tango_source_property="unified_acquisition",
                    reused_release="acq-control-candidate-20261021-v1 / everest-v2",
                    commands_default_enabled=False, auto_initialize=False, hardware_activated=False,
                    ni_execution="one_retained_child_owner_process",
                    native_wait_sampling="disabled_until_aggregate_read_budget_qualified",
                    default_live_source_changed=False, files=[])
    for source, relative in sorted(files, key=lambda item: item[1]):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest["files"].append(dict(path=relative, sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with zipfile.ZipFile(destination.with_suffix(".zip"), "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in destination.rglob("*"):
            if path.is_file(): archive.write(path, path.relative_to(destination).as_posix())
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    parser.add_argument("--everest", action="store_true")
    args = parser.parse_args()
    result = package(args.destination, args.everest)
    print(json.dumps(dict(role=result["role"], files=len(result["files"]), hardware_activated=False)))
