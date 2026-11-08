"""Package already-reviewed native VIs; no VI execution or network access."""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import build_acq_telemetry_release as baseline
import validate_acq_autostart as lifecycle
import validate_acq_legacy_hook_retirement as retirement

PROJECT = "ACQ_Telemetry_Launch_20261017.lvproj"
CHECKLIST = "LAUNCH_CHECKLIST_20261017.txt"
PARENT = baseline.EVIDENCE / "2026-10-16/auto_launch_error1100_fixed"


def project_xml(helper_names):
    root = ET.Element("Project", {"Type": "Project", "LVVersion": "12008004"})
    ET.SubElement(
        root,
        "Property",
        {
            "Name": "NI.Project.Description",
            "Type": "Str",
        },
    ).text = (
        "Operator trial only. START launches the original hardware main and "
        "an isolated read-only telemetry worker. Never run beside production."
    )
    target = ET.SubElement(root, "Item", {"Name": "My Computer", "Type": "My Computer"})
    entry = ET.SubElement(
        target,
        "Item",
        {
            "Name": "OPERATOR ONLY - START owns NI cards",
            "Type": "Folder",
        },
    )
    ET.SubElement(
        entry,
        "Item",
        {
            "Name": lifecycle.START + ".vi",
            "Type": "VI",
            "URL": "../" + lifecycle.START + ".vi",
        },
    )
    helpers = ET.SubElement(
        target,
        "Item",
        {
            "Name": "Dependencies - do not run separately",
            "Type": "Folder",
        },
    )
    ET.SubElement(
        helpers,
        "Item",
        {
            "Name": "0_ACQ_ELYSE.vi",
            "Type": "VI",
            "URL": "../ACQUISITION.llb/0_ACQ_ELYSE.vi",
        },
    )
    for name in sorted(helper_names):
        if name != lifecycle.START + ".vi":
            ET.SubElement(
                helpers,
                "Item",
                {
                    "Name": name,
                    "Type": "VI",
                    "URL": "../" + name,
                },
            )
    ET.SubElement(target, "Item", {"Name": "Dependencies", "Type": "Dependencies"})
    ET.SubElement(target, "Item", {"Name": "Build Specifications", "Type": "Build"})
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build(parent=PARENT):
    lifecycle.audit()
    retirement_report = retirement.audit()
    source = lifecycle.NATIVE / lifecycle.FOLDER
    ready = baseline.DEFAULT_PARENT / baseline.RELEASE_NAME
    manifest = json.loads((ready / "release_manifest.json").read_text(encoding="utf-8"))
    destination = Path(parent) / lifecycle.FOLDER
    if destination.exists():
        raise FileExistsError("preserve existing release: " + str(destination))
    sources = {}
    for name, expected in manifest["files"].items():
        if name.endswith((".lvproj", ".txt")) or name == "ACQ_SharedState_Transport.vi":
            continue
        if baseline.digest(source / name) != expected:
            raise ValueError("unchanged acquisition/dependency hash differs: " + name)
        sources[name] = source / name
    for name in (lifecycle.START, lifecycle.WORKER):
        sources[name + ".vi"] = source / (name + ".vi")
    # The old package had seven init hooks borrowing a queue START never owns.
    # Keep Main and its hardware dependencies byte-identical, but package the
    # native, connector-compatible retired shim instead of reintroducing 1100.
    sources[retirement.NAME + ".vi"] = retirement.SOURCE
    destination.mkdir(parents=True)
    for name, path in sources.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    # Keep the vendor project, excluding experimental top-level projects.
    for path in (ready / "TPG300").glob("*.lvproj"):
        if baseline.digest(path) != baseline.digest(source / "TPG300" / path.name):
            raise ValueError("vendor project differs")
        shutil.copy2(path, destination / "TPG300" / path.name)
    (destination / PROJECT).write_bytes(
        project_xml([name for name in sources if name.endswith(".vi")])
    )
    shutil.copy2(
        Path(__file__).parent / "templates/acq_autostart_checklist.rst",
        destination / CHECKLIST,
    )
    report = {
        "release": lifecycle.FOLDER,
        "project": PROJECT,
        "entry_point": lifecycle.START + ".vi",
        "xp_directory": "C:/" + lifecycle.FOLDER,
        "queue_capacity": 1,
        "stop_queue_capacity": 1,
        "banks": 27,
        "storage": "latest-only RAM; no history or SQLite",
        "hardware_main_changed_this_release": False,
        "hardware_main_executed_during_preparation": False,
        "main_retains_original_hardware_initialization_and_writes": True,
        "secrets_included": False,
        "test_fixtures_included": False,
        "obsolete_init_hook_retirement": retirement_report,
        "native_nonhardware_test": {
            "scope": "Inherited pinned lifecycle evidence; not a new hardware trial",
            "empty_start_stop_repeat_passed": True,
            "fixture_iterations": 1000,
            "xp_new_accepted": 260,
            "everest_new_acknowledged": 81,
            "new_pending_replacements": 179,
            "final_pending": 0,
            "final_inflight": 0,
            "final_rejected": 0,
            "final_bank_read_errors": 0,
            "automatic_worker_stop_observed": True,
        },
        "limitations": [
            "Legacy initialization queue publications are retired; "
            "telemetry consists of runtime Timeout-4 snapshots only",
            "Live card values and timing are not verified; "
            "hardware trial remains operator-only",
            "Snapshot reads 27 front-panel controls sequentially, not atomically",
            "Existing 20 ms Event Timeout is not a guaranteed telemetry sample period",
            "Enqueue/setup queue failures have no launcher-level gating "
            "of hardware startup",
            "Transport errors are isolated; they do not stop or change "
            "acquisition controls",
            "Worker sends no guaranteed final flush after main returns",
            "This is not proof of all 73 publication sites or "
            "complete business-logic coverage",
        ],
        "files": {
            p.relative_to(destination).as_posix(): baseline.digest(p)
            for p in sorted(destination.rglob("*"))
            if p.is_file()
        },
    }
    (destination / "auto_launch_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive = Path(parent) / (lifecycle.FOLDER + ".zip")
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zipped:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(parent))
    return {
        "directory": str(destination),
        "archive": str(archive),
        "sha256": baseline.digest(archive),
        "file_count": len(report["files"]),
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
