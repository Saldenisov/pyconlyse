"""Native lifecycle release preflight. Read-only, standard library, Python3.4.

Receipts attest native events; this checker never creates those events or runs
LabVIEW. Model/parser success cannot substitute for native qualification.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET

try:
    from tools.verify_labview_sync_native12_package import _inside, vi_header
except ImportError:  # Direct python tools/... invocation.
    from verify_labview_sync_native12_package import _inside, vi_header


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def qualify_helper(row, evidence):
    """Require pinned native Save, stopped fresh FP/BD and native12 export."""
    if evidence.get("last_writer") != "native_labview_export":
        raise ValueError("Current VI last writer must be native LabVIEW export")
    if evidence.get("implemented") is not True:
        raise ValueError("Unimplemented helper cannot enter release packet")
    source = evidence.get("native20_source_sha256")
    if not source or source != row.get("native20_source_sha256"):
        raise ValueError("Native source hash does not match qualification")
    save = evidence.get("native_save", {})
    fresh = evidence.get("fresh_project_load", {})
    export = evidence.get("native_export", {})
    if not (
        save.get("passed") is True
        and save.get("stopped") is True
        and save.get("last_writer") == "native_labview_save"
        and save.get("sha256") == source
        and save.get("bitness") == 32
    ):
        raise ValueError("Pinned stopped native x86 Save evidence required")
    if not (
        fresh.get("passed") is True
        and fresh.get("FP") is True
        and fresh.get("BD") is True
        and fresh.get("stopped") is True
        and fresh.get("sha256") == source
        and fresh.get("project")
    ):
        raise ValueError("Pinned stopped fresh-project FP/BD evidence required")
    if not (
        export.get("passed") is True
        and export.get("version") == "12.0"
        and export.get("last_writer") == "native_labview_export"
        and export.get("source_sha256") == source
        and export.get("sha256") == row["sha256"]
    ):
        raise ValueError("Pinned native12 export evidence required")
    return True


def verify_component(root):
    root = os.path.abspath(root)
    manifest = read_json(os.path.join(root, "package_manifest.json"))
    records = {}
    for row in manifest["files"]:
        relative = row["path"]
        if relative in records:
            raise ValueError("Duplicate component file")
        path = _inside(root, os.path.join(root, *relative.split("/")))
        with open(path, "rb") as stream:
            raw = stream.read()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Pinned native file mismatch: " + relative)
        records[relative] = row
        if relative.lower().endswith(".vi"):
            header = vi_header(raw)
            if header["major"] != 12 or header["RunOnOpen"]:
                raise ValueError("Expected native12 stopped-load VI")
    expected = set(k for k in records if k.lower().endswith(".vi"))
    actual = set()
    for parent, unused, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".vi"):
                actual.add(
                    os.path.relpath(os.path.join(parent, name), root).replace("\\", "/")
                )
    if actual != expected:
        raise ValueError("Unlisted or missing VI; candidates cannot be included")
    evidence_path = _inside(
        root, os.path.join(root, *manifest["qualification_receipt"].split("/"))
    )
    with open(evidence_path, "rb") as stream:
        evidence_raw = stream.read()
    if hashlib.sha256(evidence_raw).hexdigest() != manifest["qualification_sha256"]:
        raise ValueError("Qualification receipt pin changed")
    evidence = json.loads(evidence_raw.decode("utf-8"))["helpers"]
    if set(evidence) != expected:
        raise ValueError("Every included helper needs its own qualification")
    for name in expected:
        qualify_helper(records[name], evidence[name])
    system = set(manifest.get("system_dependencies", []))
    project_results = []
    for project in manifest["projects"]:
        path = _inside(root, os.path.join(root, *project["path"].split("/")))
        if project["path"] not in records:
            raise ValueError("Project must be byte-pinned")
        tree = ET.parse(path).getroot()
        if tree.get("LVVersion") != "12008004":
            raise ValueError("Expected native12 project version")
        refs = set()
        for item in tree.iter("Item"):
            if item.get("Type") != "VI":
                continue
            url = item.get("URL", "")
            if url.startswith("/<vilib>/"):
                if url not in system:
                    raise ValueError("Undeclared NI system dependency")
                continue
            # Native2020 UI + native SaveForPrevious12 both prove FILE-based URL.
            target = _inside(root, os.path.normpath(os.path.join(path, url)))
            relative = os.path.relpath(target, root).replace("\\", "/")
            if relative not in expected or not os.path.isfile(target):
                raise ValueError(
                    "Project URL does not resolve; fallback search forbidden"
                )
            refs.add(relative)
        if refs != set(project["VI_members"]):
            raise ValueError("Project helper membership differs from manifest")
        project_results.append(project["path"])
    for link in manifest["custom_relative_links"]:
        if link["caller"] not in expected:
            raise ValueError("Custom link caller is not a listed helper")
        caller = os.path.join(root, *link["caller"].split("/"))
        parts = [".." if part == "" else part for part in link["components"]]
        target = _inside(root, os.path.normpath(os.path.join(caller, *parts)))
        relative = os.path.relpath(target, root).replace("\\", "/")
        if relative != link["target"] or relative not in expected:
            raise ValueError("Pinned custom dependency closure changed")
    return dict(
        status="PASS",
        helpers=sorted(expected),
        native_event_evidence_verified=True,
        projects=project_results,
        system_dependencies=sorted(system),
        system_dependencies_installed_verified=False,
        FrameTap_implemented=False,
        full_camera_pipeline_ready=False,
        native2012_runtime_proven=False,
        executed=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=os.path.join(
            os.path.dirname(__file__),
            "..",
            "legacy",
            "labview",
            "supervision_telemetry",
            "individual_helpers",
            "camera",
        ),
    )
    args = parser.parse_args()
    print(json.dumps(verify_component(args.root), indent=2, sort_keys=True))
