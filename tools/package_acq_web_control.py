"""Package both XP orchestrators and the existing unified Tango device."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
XP = ROOT / "legacy/xp_acq_control"
BRIDGE = ROOT / "DeviceServers/control/elyse_acq"


def xp_release_paths():
    """Explicit cold application closure, never arbitrary runtime/repair files."""
    from legacy.xp_acq_control.elyse_agent.runtime_identity import SOURCE_PATHS
    from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import CONTROL_MODULES
    return sorted(set(SOURCE_PATHS) | {"elyse_agent/" + name for name in CONTROL_MODULES}
        | {"__init__.py", "acquisition_control_server.pyw", "supervision_control_server.pyw", "config.acquisition.json",
           "config.acquisition.control.json", "config.supervision.control.json", "data/standard_telemetry_schema.json"})


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
                     "command_protocol.py", "acquisition_counter_timing.py", "command_broker.py", "command_http.py", "command_dispatch.py",
                     "standard_banks.py", "telemetry_publisher.py", "telemetry_view.py",
                     "cooling_safety.py", "journal_worker.py", "federation_wire.py",
                     "shared_state.py", "labview_telemetry.py", "telemetry_relay.py", "protocol.py", "supervision_wire.py", "errors.py"):
            files.append((XP / "elyse_agent" / name, "legacy/xp_acq_control/elyse_agent/" + name))
        for name in ("__init__.py", "shared_state.py", "labview_telemetry.py", "telemetry_relay.py",
                     "protocol.py", "supervision_wire.py", "errors.py", "cooling_safety.py"):
            files.append((ROOT / "legacy/xp_acq_agent/elyse_agent" / name, "legacy/xp_acq_agent/elyse_agent/" + name))
        for name in ("DeviceServers/__init__.py", "DeviceServers/control/__init__.py", "DeviceServers/control/elyse_acq/__init__.py",
                     "legacy/__init__.py", "legacy/xp_acq_control/__init__.py"):
            files.append((ROOT / name, name))
        files.append((XP / "data/standard_telemetry_schema.json", "legacy/xp_acq_control/data/standard_telemetry_schema.json"))
        for name in ("federated_telemetry.py", "hybrid_telemetry.py"):
            files.append((BRIDGE / name, "DeviceServers/control/elyse_acq/" + name))
    else:
        files = [(XP / relative, relative) for relative in xp_release_paths()]
    destination.mkdir(parents=True)
    manifest = dict(schema_version=1, role="everest_tango" if everest else "xp_python34",
                    release="everest-two-orchestrators-20261026-r18" if everest else "elyse-card-process-orchestrators-20261026-r18", default_xp_port=8772,
                    standard_bank_count=27, telemetry_port=8767, tango_device="elyse/acquisition/telemetry",
                    xp_modes=["IDLE: loopback VI bridge", "initialized: Python NI owner"],
                    vi_loopback_port=8766, tango_source_property="unified_acquisition",
                    reused_release="acq-control-candidate-20261021-v1 / everest-v2",
                    commands_default_enabled=False, auto_initialize=False, hardware_activated=False,
                    ni_execution="retained_local_controller_with_optional_per_card_owner_processes",
                    native_wait_sampling="disabled_until_aggregate_read_budget_qualified",
                    default_live_source_changed=False, files=[])
    if not everest:
        manifest.update(canonical_entrypoint="acquisition_control_server.pyw",
            compatibility_alias="acquisition_server.pyw (same unified application)",
            standalone_telemetry_application_included=False,
            application_exclusion="config-scoped OS lock plus fixed endpoints before journal writer",
            recovery="explicit local operator handover only; no automatic marker deletion",
            historical_journal_ack="durable local acknowledgment; incidents/current storage errors preserved",
            native_analog_processing="last_raw_sample_of_finite_block",
            native_software_averaging=False,
            native_bootstrap="Modules plus NI library/TaskHandle metadata before stdin reader; no Task constructed",
            native_initialization="11 concurrent card preparation workers; 30s total deadline; startup effects after all ready",
            native_child_input="PeekNamedPipe plus ReadFile; no idle buffered stdin read",
            operator_supervised_test_supported=True,
            operator_test_is_physical_qualification=False,
            native_finite_samples_per_channel=10,
            native_selected_sample_index=9,
            vi_forwarded_processing_unchanged=True,
            native_software_status_banks=["EPS", "DPS"],
            native_software_status_semantics="Complete owner software memory, not hardware readback or permits",
            execution_telemetry="Separate software observations and qualified current-operation samples",
            execution_sampling_default=None,
            native_packet_age="Oldest populated source category; stale measurements remain unavailable",
            beamline_pulses_default_enabled=False,
            beamline_commands=["faraday_1.en_pulse", "faraday_3.en_pulse",
                               "laser_mirror.en_pulse", "laser_mirror.hors_pulse"],
            faraday_hors_commands_qualified=False,
            faraday_3_position_feedback_qualified=False,
            ht_increase_requires_software_supply_and_modulator=True,
            autonomous_ht_ramp=False)
    manifest.update(named_operation_count=25, matched_control_capability_set_required=True,
                    local_orchestrator_roles=["acquisition", "supervision"],
                    native_isolation_modes=["single_owner", "per_card"],
                    native_isolation_default="per_card",
                    federation_default_enabled=False,
                    per_card_restart="Explicit affected-output OFF, known clean close and joined child; no automatic replay",
                    circulation_confirmation="Per current incident before 120s; software audit only; no NI effect",
                    circulation_activation="Qualified measured HT above existing zero tolerance plus supply ON; not General",
                    fault_readback="Fresh diagnostic inputs with sticky FAULT and independent command gates",
                    synchronization_command="counter_timing.set", synchronization_counter_card=10,
                    synchronization_already_running_required=True, synchronization_c11_enabled=False,
                    runtime_protocol_version=2, control_envelope_version=1)
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
