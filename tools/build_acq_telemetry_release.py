"""Stage a pinned native ACQ candidate; never execute VI or contact hardware.

The candidate preserves sixteen LLB subVIs byte-for-byte against the snapshot
before the Timeout-4 hook. Its main already includes that audited hook and the
earlier publication wrappers. Native dependency resolution remains a separate
XP LabVIEW check, not a claim made by this builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EVIDENCE = Path(r"C:\dev\ELYSE-ACQ-telemetry")
GOOD = EVIDENCE / "2026-10-13/xp_snapshot_timeout4_safeopen_20261013"
BEFORE = EVIDENCE / "2026-10-13/xp_snapshot_before_timeout4_20261013"
HELPERS = (
    EVIDENCE / "2026-10-14/xp_native_transport_20261014/ELYSE_ACQ_TELEMETRY_20261012"
)
TRANSPORT = EVIDENCE / "2026-10-14/transport_timeout_guard_20261014"
DEFAULT_PARENT = EVIDENCE / "2026-10-14/release_ready_20261017"
RELEASE_NAME = "ELYSE_ACQ_TELEMETRY_READY_20261017"
PROJECT_NAME = "ACQ_Telemetry_READY_20261017.lvproj"
XP_ROOT = "C:/" + RELEASE_NAME
PINS = {
    "ACQUISITION.llb": (
        "4DF22D4E0EB63ECA9025068CAAF4C49236017027ADF1CF87A862A88AF1C010FB"
    ),
    "ACQ_SharedState_Collect_Local.vi": (
        "A63BAAAB3EB8D60B37FD5EC624C8A27446F4D513FAAA4472E719F3331DB1B472"
    ),
    "ACQ_SharedState_Queue_Latest.vi": (
        "1FF9B3E0AAC58DBEA98EE9A2175EF70CBCCCB268D4604B3899B7DD16CC5D69F2"
    ),
    "ACQ_SharedState_Transport.vi": (
        "873D1484E7368077F823100570EFCC9B8E6B51051B43125FAF1B05D46930BC5A"
    ),
}
MAIN_HASH = "E2C1F2D5EFF005E1944ED0F0F286B4C7AD6B3E2AF6114D5AE62B6CF1FCFD220A"
EXCLUDED = {
    "ACQ_SharedState_Probe.vi",
    "ACQ_Telemetry_Soak.vi",
    "ACQ_Telemetry_XML_Fixture.vi",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def check_members(good: Path = GOOD, before: Path = BEFORE) -> dict[str, str]:
    current = {p.name: p for p in (good / "members").glob("*.vi")}
    baseline = {p.name: p for p in (before / "members").glob("*.vi")}
    if len(current) != 17 or current.keys() != baseline.keys():
        raise ValueError("expected identical seventeen-member LLB inventories")
    if digest(current["0_ACQ_ELYSE.vi"]) != MAIN_HASH:
        raise ValueError("audited Timeout-4 main hash changed")
    hashes = {name: digest(path) for name, path in current.items()}
    for name, value in hashes.items():
        if name != "0_ACQ_ELYSE.vi" and value != digest(baseline[name]):
            raise ValueError("hardware subVI changed: " + name)
    return hashes


def project_xml(helper_names: list[str]) -> bytes:
    root = ET.Element("Project", {"Type": "Project", "LVVersion": "12008004"})
    ET.SubElement(
        root, "Property", {"Name": "NI.Project.Description", "Type": "Str"}
    ).text = (
        "Operator-only hardware trial. Python telemetry is non-actuating. "
        "Never run this main alongside production Acquisition."
    )
    target = ET.SubElement(root, "Item", {"Name": "My Computer", "Type": "My Computer"})
    folder = ET.SubElement(
        target, "Item", {"Name": "OPERATOR ONLY - owns NI cards", "Type": "Folder"}
    )
    ET.SubElement(
        folder,
        "Item",
        {
            "Name": "0_ACQ_ELYSE.vi",
            "Type": "VI",
            "URL": "../ACQUISITION.llb/0_ACQ_ELYSE.vi",
        },
    )
    ET.SubElement(
        target,
        "Item",
        {
            "Name": "ACQ_SharedState_Transport.vi",
            "Type": "VI",
            "URL": "../ACQ_SharedState_Transport.vi",
        },
    )
    helpers = ET.SubElement(
        target,
        "Item",
        {"Name": "Telemetry dependencies - do not run", "Type": "Folder"},
    )
    for name in sorted(helper_names):
        if name != "ACQ_SharedState_Transport.vi":
            ET.SubElement(
                helpers,
                "Item",
                {"Name": name, "Type": "VI", "URL": "../" + name},
            )
    ET.SubElement(target, "Item", {"Name": "Dependencies", "Type": "Dependencies"})
    ET.SubElement(target, "Item", {"Name": "Build Specifications", "Type": "Build"})
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build(parent: Path = DEFAULT_PARENT) -> dict:
    destination = parent / RELEASE_NAME
    if destination.exists():
        raise FileExistsError(
            "preserve existing candidate; choose a fresh parent: " + str(destination)
        )
    members = check_members()
    sources = {p.name: p for p in HELPERS.glob("*.vi") if p.name not in EXCLUDED}
    sources["ACQUISITION.llb"] = GOOD / "ACQUISITION.llb"
    sources["ACQ_SharedState_Transport.vi"] = TRANSPORT / "ACQ_SharedState_Transport.vi"
    for name, expected in PINS.items():
        if name not in sources or digest(sources[name]) != expected:
            raise ValueError("reviewed source hash changed: " + name)
    if any(not name.startswith("ACQ_") for name in sources if name.endswith(".vi")):
        raise ValueError("unexpected external native VI")
    destination.mkdir(parents=True)
    for name, source in sources.items():
        shutil.copy2(source, destination / name)
    shutil.copytree(HELPERS / "TPG300", destination / "TPG300")
    shutil.copy2(
        Path(__file__).parent / "templates/acq_telemetry_saturday_checklist.rst",
        destination / "CHECKLIST_20261017.txt",
    )
    (destination / PROJECT_NAME).write_bytes(
        project_xml([name for name in sources if name.endswith(".vi")])
    )
    manifest = {
        "release": RELEASE_NAME,
        "operator_trial_date": "2026-10-17",
        "xp_install_directory": XP_ROOT,
        "origin_llb": str(sources["ACQUISITION.llb"]),
        "llb_member_sha256": members,
        "hardware_subvis_byte_identical_to_pre_timeout4": 16,
        "main_already_contains_timeout4_hook": True,
        "native_main_executed_by_builder": False,
        "native_dependency_resolution_verified_by_builder": False,
        "continuous_performance_verified_by_builder": False,
        "main_retains_original_hardware_access": True,
        "python_hardware_access": False,
        "python_bridge": "C:/ACQ_SharedState_Python34_20261014",
        "xml_wire_encoding": "cp1252",
        "queue_capacity": 1,
        "telemetry_bank_count": 27,
        "secrets_included": False,
        "synthetic_fixtures_included": False,
        "files": {
            p.relative_to(destination).as_posix(): digest(p)
            for p in sorted(destination.rglob("*"))
            if p.is_file()
        },
    }
    (destination / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    archive = parent / (RELEASE_NAME + ".zip")
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zipped:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(parent))
    return {
        "directory": str(destination),
        "archive": str(archive),
        "archive_sha256": digest(archive),
        "manifest": manifest,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    print(json.dumps(build(parser.parse_args().parent), ensure_ascii=False, indent=2))
