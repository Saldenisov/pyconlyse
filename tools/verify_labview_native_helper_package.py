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


# These are existing, independently native-saved/exported artifacts. This is
# not a generic exception for generated candidates or unreviewed dependencies.
RETAINED_NATIVE12 = {
    "SUP_Camera_Observe_U8_UNCOMPILED.vi": (
        "c6387a4d2d5f41ded7829ed154c89c89faa840b2aa844c1f0803d76b04c235e9",
        26533,
        "8d27a36bf7d743f72687ca70d06f82175fce7680f3fdc34c92325546a5502775",
        "native_labview_export",
    ),
    "observer_v3/SUP_Camera_Queue_Latest.vi": (
        "bef72a8c0a4b7cc269e1694668464ba5c75164519687fee3b428552e7bd49bb7",
        10059,
        "6e94050694daad6af7451fa626ede0b1eea76a1531ce692f555a6d6125d114d2",
        "native_labview_save",
    ),
    "SUP_Camera_Transport.vi": (
        "4ab066c45cc6b15c2e0b0f95b2bcd8f239b9b8d6989d33c49b84843f39c28f03",
        19484,
        "4940f425caa91b48b094c8f17168941e74b1cd4cf406f6494aa14cffed2bfa62",
        "native_labview_save",
    ),
}


def _fresh_evidence(fresh, source):
    return (
        fresh.get("passed") is True
        and fresh.get("FP") is True
        and fresh.get("BD") is True
        and fresh.get("stopped") is True
        and fresh.get("sha256") == source
        and bool(fresh.get("project"))
    )


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def qualify_helper(row, evidence):
    """Require pinned native Save, stopped fresh FP/BD and native12 export."""
    if evidence.get("qualification_mode") == "retained_native12":
        pin = RETAINED_NATIVE12.get(row["path"])
        prior = evidence.get("existing_native12_artifact", {})
        if not (
            pin
            and row.get("sha256") == pin[0]
            and row.get("bytes") == pin[1]
            and evidence.get("last_writer") == pin[3]
            and prior.get("receipt_sha256") == pin[2]
            and prior.get("artifact_sha256") == pin[0]
            and prior.get("passed") is True
            and prior.get("version") == "12.0"
            and evidence.get("implemented") is True
            and evidence.get("source_bytes_unchanged") is True
            and _fresh_evidence(evidence.get("fresh_project_load", {}), pin[0])
        ):
            raise ValueError(
                "Unreviewed retained native12 artifact or missing fresh evidence"
            )
        return True
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
    if not _fresh_evidence(fresh, source):
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
    if (
        manifest.get("full_camera_pipeline_ready") is True
        or manifest.get("native2012_runtime_proven") is True
    ):
        raise ValueError(
            "Offline helper packet cannot claim runtime/pipeline readiness"
        )
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
    qualification = json.loads(evidence_raw.decode("utf-8"))
    if (
        qualification.get("full_camera_pipeline_ready") is True
        or qualification.get("native2012_runtime_proven") is True
    ):
        raise ValueError("Qualification receipt cannot promote unexecuted runtime")
    evidence = qualification["helpers"]
    if set(evidence) != expected:
        raise ValueError("Every included helper needs its own qualification")
    allowed_files = set(records) | {
        "package_manifest.json",
        "README.md",
        ".gitattributes",
        "NATIVE_XP_CAMERA_LIFECYCLE_WORKSHEET.rst",
        manifest["qualification_receipt"],
    }
    for proof in manifest.get("proof_receipts", []):
        path = _inside(root, os.path.join(root, *proof["path"].split("/")))
        with open(path, "rb") as stream:
            if hashlib.sha256(stream.read()).hexdigest() != proof["sha256"]:
                raise ValueError("Declared proof receipt pin changed")
        allowed_files.add(proof["path"])
    for name in expected:
        qualify_helper(records[name], evidence[name])
        prior = evidence[name].get("existing_native12_artifact")
        if prior:
            allowed_files.add(prior["receipt"])
            proof = _inside(root, os.path.join(root, *prior["receipt"].split("/")))
            with open(proof, "rb") as stream:
                if hashlib.sha256(stream.read()).hexdigest() != prior["receipt_sha256"]:
                    raise ValueError("Retained native12 original receipt changed")
        review = evidence[name].get("read_only_runtime_findings")
        if review:
            allowed_files.add(review["path"])
            path = _inside(root, os.path.join(root, *review["path"].split("/")))
            with open(path, "rb") as stream:
                if hashlib.sha256(stream.read()).hexdigest() != review["sha256"]:
                    raise ValueError("Retained artifact runtime finding changed")
    frametap = "SUP_Camera_FrameTap.vi"
    implemented = frametap in expected
    if bool(manifest.get("FrameTap_implemented")) != implemented:
        raise ValueError(
            "FrameTap declaration does not match admitted helper inventory"
        )
    if implemented:
        proof = evidence[frametap]["source_graph_audit"]
        allowed_files.add(proof["path"])
        path = _inside(root, os.path.join(root, *proof["path"].split("/")))
        with open(path, "rb") as stream:
            raw = stream.read()
        if hashlib.sha256(raw).hexdigest() != proof["sha256"]:
            raise ValueError("FrameTap exported-source audit changed")
        graph = json.loads(raw.decode("utf-8"))
        if not (
            graph.get("source_sha256") == records[frametap]["sha256"]
            and graph.get("actual_native_saved_source_cases") == 4000
            and graph.get("private_dependency_closure_complete") is True
            and graph.get("InlineIfPossible") == 0
            and graph.get("ShouldInline") == 0
            and graph.get("flags", {}).get("IsReentrant") == 0
            and graph.get("native_insertion_constraint")
        ):
            raise ValueError("FrameTap gate/barrier/nonreentrancy audit missing")
    for parent, unused, files in os.walk(root):
        for name in files:
            relative = os.path.relpath(os.path.join(parent, name), root).replace(
                "\\", "/"
            )
            if relative not in allowed_files:
                raise ValueError("Unexpected component file: " + relative)
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
        qualification_scope="Offline native artifacts; runtime unapproved",
        projects=project_results,
        system_dependencies=sorted(system),
        system_dependencies_installed_verified=False,
        FrameTap_implemented=implemented,
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
