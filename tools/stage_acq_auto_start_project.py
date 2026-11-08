"""Create a fresh native-editor workspace for a single-entry telemetry launcher.

Only file assembly. No hardware access, VI execution or process control.
The launcher and lifecycle helpers are authored and compiled in native LabVIEW.
Until their separate verification, this directory is work in progress.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

import build_acq_telemetry_release as baseline

NAME = "ELYSE_ACQ_TELEMETRY_AUTO_20261017"
PARENT = baseline.EVIDENCE / "2026-10-14/auto_start_native_20261014"
DESTINATION = PARENT / NAME
PROJECT = "ACQ_Telemetry_AUTO_20261017.lvproj"
WORKER = "ACQ_SharedState_Transport_Auto.vi"


def stage() -> dict:
    if DESTINATION.exists():
        raise FileExistsError("preserve existing native-editor workspace")
    source = (
        baseline.EVIDENCE / "2026-10-14/release_ready_20261017" / baseline.RELEASE_NAME
    )
    manifest = json.loads(
        (source / "release_manifest.json").read_text(encoding="utf-8")
    )
    for name, expected in manifest["files"].items():
        if baseline.digest(source / name) != expected:
            raise ValueError("baseline release changed: " + name)
    DESTINATION.mkdir(parents=True)
    for path in source.glob("*.vi"):
        target = WORKER if path.name == "ACQ_SharedState_Transport.vi" else path.name
        shutil.copy2(path, DESTINATION / target)
    shutil.copy2(source / "ACQUISITION.llb", DESTINATION / "ACQUISITION.llb")
    shutil.copytree(source / "TPG300", DESTINATION / "TPG300")
    helpers = [p.name for p in DESTINATION.glob("*.vi")]
    root = ET.fromstring(baseline.project_xml(helpers))
    target = root.find("Item")
    old = target.find("Item[@Name='ACQ_SharedState_Transport.vi']")
    target.remove(old)
    folder = target.find("Item[@Name='Telemetry dependencies - do not run']")
    # The auto worker replaces the standalone worker. It is not a hardware VI.
    item = folder.find("Item[@Name='" + WORKER + "']")
    folder.remove(item)
    target.insert(1, item)
    root.find("Property").text = (
        "WORK IN PROGRESS: single-entry telemetry launcher being built. "
        "Do not run the hardware main alongside production Acquisition."
    )
    ET.indent(root)
    (DESTINATION / PROJECT).write_bytes(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )
    result = {
        "state": "Native editing only; startup wrapper not yet created or verified",
        "xp_destination": "C:/" + NAME,
        "project": PROJECT,
        "main_llb_sha256": baseline.digest(DESTINATION / "ACQUISITION.llb"),
        "main_unchanged": True,
        "worker_before_native_edits_sha256": baseline.digest(DESTINATION / WORKER),
        "baseline_manifest_sha256": hashlib.sha256(
            (source / "release_manifest.json").read_bytes()
        )
        .hexdigest()
        .upper(),
        "new_hardware_commands": False,
        "hardware_main_executed": False,
        "production_touched": False,
    }
    (PARENT / "stage_checkpoint.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(stage(), indent=2))
