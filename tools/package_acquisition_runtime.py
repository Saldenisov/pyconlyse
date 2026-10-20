"""Package the cold XP GUI service without keys, logs, history or auto-init."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


MODULES = (
    "__init__.py", "acquisition_backend.py", "acquisition_gui.py", "acquisition_http.py",
    "acquisition_runtime.py", "acquisition_startup.py", "acquisition_procedures.py", "hardware_tasks.py",
    "acquisition_ht_shutdown.py",
    "hardware_plan.py", "input_tasks.py", "transforms.py", "errors.py", "chroma_focal_stop.py",
    "acquisition_stage_model.py",
    "acquisition_stage_execution.py", "acquisition_cooling_trip.py",
)
DATA = ("calibration_map.csv", "ni6602_timing.csv", "modulator_stage_catalog.json")


def build(output, root=None, control_profile="legacy_full"):
    if control_profile not in ("legacy_full", "general_only_test", "extended_ht_stop"):
        raise ValueError("Unknown acquisition control profile")
    root = Path(root or Path(__file__).resolve().parents[1])
    source = root / "legacy/xp_acq_agent"
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new package output directory")
    paths = [Path("acquisition_server.pyw"), Path("config.acquisition.json")]
    # A clean checkout has the reviewed template, never the private/site
    # configuration. Packaging must not silently inherit live permissions.
    config_template = source / "config.acquisition.example.json"
    paths += [Path("elyse_agent") / name for name in MODULES]
    paths += [Path("data") / name for name in DATA]
    for path in paths:
        input_path = config_template if path.as_posix() == "config.acquisition.json" else source / path
        if not input_path.is_file():
            raise ValueError("Missing package input: " + str(path))
    output.mkdir(parents=True)
    records = []
    for relative in paths:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        input_path = config_template if relative.as_posix() == "config.acquisition.json" else source / relative
        shutil.copy2(input_path, target)
        if relative.as_posix() == "config.acquisition.json":
            # Pin both profiles explicitly: the full candidate must not inherit
            # a commissioning subset from a future source-config change.
            config = json.loads(target.read_text(encoding="utf-8"))
            config["control_profile"] = control_profile
            config["stage_controls_verified"] = False
            config["cooling_trip_verified"] = False
            config["ht_controls_verified"] = False
            config.setdefault("focal_stop", {})["resources_verified"] = False
            # No uncommissioned feedback claim is packaged as a permit, even
            # in a profile where that extension currently remains unused.
            config["ht_shutdown"] = dict(feedback_verified=False,
                                         zero_tolerance_kv=0.0, timeout_seconds=10.0)
            target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        records.append(dict(path=relative.as_posix(), sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    manifest = dict(schema_version=1, python="3.4", driver_wrapper="nidaqmx==0.5.7",
                    auto_initialize=False, mode="operator_commissioning_not_complete_vi_replacement",
                    control_profile=control_profile,
                    general_stop_scope=("python_8kv_ht_preamble_then_source_event_6" if control_profile == "extended_ht_stop" else
                                        "source_event_6_frames_13_to_16" if control_profile == "general_only_test"
                                        else "source_event_6_all_17_frames"),
                    general_stop_includes_ht_supply_stop=control_profile == "extended_ht_stop",
                    ht_feedback_commissioning_required=control_profile == "extended_ht_stop",
                    source_stage_paths_implemented=12, source_stage_controls_default_enabled=False,
                    cooling_trip_default_enabled=False,
                    ht_stage_controls_default_enabled=False,
                    initialized_hardware_during_packaging=False, secret_files_included=False,
                    telemetry_storage="ram_latest", files=records,
                    limitations=["Not the full LabVIEW business/safety state machine",
                                 "NI task cleanup is not electrical emergency shutdown",
                                 "Only local GUI initialization; remote HTTP reads only",
                                 "NI runtime commissioning on XP still required",
                                 ("Python HT preamble + event6, not source-identical General Arret; no later stages without fresh zero/OFF and successful counter stops"
                                  if control_profile == "extended_ht_stop" else
                                  "General-only Arret uses frames 13..16 and General status fields only; other stages must already be OFF"
                                  if control_profile == "general_only_test" else
                                  "General Arret is event 6, not full acquisition shutdown or emergency stop"),
                                 ("No Chroma calls in General-only test; not an installation-wide stop"
                                  if control_profile == "general_only_test" else
                                  "Chroma COM10/11/12 mapping must be verified before General Marche"),
                                 "Chroma OFF native adapter has not been commissioned on hardware",
                                 "Source General Arret does not command separate HT-supply stop C4[19] or cooling stop",
                                 "Python extended_ht_stop adds an8-kV/zero-readback HT preamble; not source-identical; feedback permission defaults False",
                                 "Twelve additional source-stage paths and cooling-trip execution require separate commissioning; disabled in this package",
                                 "Standalone HT start can energize existing commanded voltage; requires independent HT commissioning",
                                 "No additional stage GUI buttons or HTTP/Tango mutation routes"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = output.with_suffix(".zip")
    if archive.exists():
        raise ValueError("Archive already exists; package folder retained")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, output.name + "/" + path.relative_to(output).as_posix())
    return dict(directory=str(output), archive=str(archive), files=len(records), auto_initialize=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("--control-profile", choices=("legacy_full", "general_only_test", "extended_ht_stop"), default="legacy_full")
    args = parser.parse_args()
    print(json.dumps(build(args.output, control_profile=args.control_profile), indent=2))
