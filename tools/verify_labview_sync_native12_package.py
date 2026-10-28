"""Read-only native12 package checks; standard library, Python3.4 compatible.

Reads RSRC directory/LVSR only. Does not compile, execute or load LabVIEW.
Pinned native-export hashes preserve the separately audited call-link bytes.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import struct
import xml.etree.ElementTree as ET


def _u32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("RSRC offset outside file")
    return struct.unpack_from(">I", data, offset)[0]


def rsrc_sections(data):
    """Read bounded format3 section slices without interpreting any G code."""
    if len(data) < 32 or data[:6] != b"RSRC\r\n" or data[8:16] != b"LVINLBVW":
        raise ValueError("Expected a native VI RSRC container")
    info, start = _u32(data, 16), _u32(data, 24)
    if info < 32 or data[info : info + 6] != b"RSRC\r\n":
        raise ValueError("Invalid RSRC info directory")
    directory = info + _u32(data, info + 44)
    count = _u32(data, directory) + 1
    if not 1 <= count <= 4096:
        raise ValueError("Invalid resource count")
    result = {}
    for index in range(count):
        header = directory + 4 + index * 12
        ident = data[header : header + 4]
        sections = _u32(data, header + 4) + 1
        table = directory + _u32(data, header + 8)
        if not 1 <= sections <= 4096:
            raise ValueError("Invalid section count")
        for number in range(sections):
            entry = table + number * 20
            section = _u32(data, entry)
            position = start + _u32(data, entry + 12)
            size = _u32(data, position)
            if position + 4 + size > info:
                raise ValueError("Resource data outside data area")
            key = (ident, section)
            if key in result:
                raise ValueError("Duplicate resource section")
            result[key] = data[position + 4 : position + 4 + size]
    return result


def vi_header(data):
    sections = rsrc_sections(data)
    record = sections.get((b"LVSR", 0), b"")
    if len(record) < 12 or (b"BDHb", 0) not in sections:
        raise ValueError("Native save record or source diagram missing")
    encoded = _u32(record, 0)
    try:
        major = int("{:02x}".format(encoded >> 24))
    except ValueError:
        raise ValueError("Invalid BCD LabVIEW major version")
    return dict(
        major=major,
        encoded_version="{:08x}".format(encoded),
        RunOnOpen=bool(_u32(record, 4) & (1 << 14)),
        source_diagram=True,
    )


def _inside(root, path):
    root = os.path.normcase(os.path.realpath(root))
    target = os.path.normcase(os.path.realpath(path))
    if not target.startswith(root.rstrip(os.sep) + os.sep):
        raise ValueError("Dependency escapes package")
    return path


def verify_package(root):
    root = os.path.abspath(root)
    with open(os.path.join(root, "package_manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if (
        manifest.get("full_camera_pipeline_ready") is True
        or manifest.get("native2012_runtime_proven") is True
    ):
        raise ValueError(
            "Offline helper packet cannot claim runtime/pipeline readiness"
        )
    records = {}
    for row in manifest["files"]:
        path = _inside(root, os.path.join(root, *row["path"].split("/")))
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Pinned native-export hash/size mismatch: " + row["path"])
        if row["path"].lower().endswith(".vi"):
            header = vi_header(raw)
            if header["major"] != 12 or header["RunOnOpen"]:
                raise ValueError("Expected native12 VI with RunOnOpen0")
            records[row["path"]] = header
    actual = set()
    components = manifest.get("additional_components", [])
    historical_metadata = set(manifest.get("historical_metadata_files", []))
    known_metadata = {
        "epoch_native2020_semantic_snapshot.json",
        "camera_frametap_checkpoint_20261028.json",
        "setup_native2020_semantic_snapshot.json",
        "qualification.json",
    }
    if historical_metadata - known_metadata:
        raise ValueError("Unreviewed historical metadata filename")
    allowed_files = (
        set(row["path"] for row in manifest["files"])
        | {
            "package_manifest.json",
            "README.md",
            "README.rst",
            ".gitattributes",
            manifest["source_receipt"],
        }
        | historical_metadata
    )
    component_roots = set(
        os.path.normcase(
            os.path.realpath(_inside(root, os.path.join(root, *c["path"].split("/"))))
        )
        for c in components
    )
    for parent, dirs, files in os.walk(root):
        dirs[:] = [
            d
            for d in dirs
            if os.path.normcase(os.path.realpath(os.path.join(parent, d)))
            not in component_roots
        ]
        for name in files:
            relative = os.path.relpath(os.path.join(parent, name), root).replace(
                "\\", "/"
            )
            if relative not in allowed_files:
                raise ValueError("Unexpected helper packet file: " + relative)
            if name.lower().endswith(".vi"):
                actual.add(
                    os.path.relpath(os.path.join(parent, name), root).replace("\\", "/")
                )
    if actual != set(records) or len(records) != 3:
        raise ValueError("Only the three qualified sync VIs may be packaged")
    project = os.path.join(root, *manifest["project"].split("/"))
    tree = ET.parse(project).getroot()
    if tree.get("LVVersion") != "12008004":
        raise ValueError("Project is not the native12 export")
    refs = set()
    for item in tree.iter("Item"):
        if item.get("Type") != "VI":
            continue
        # Native LabVIEW anchors this URL at the project FILE itself.
        target = _inside(root, os.path.normpath(os.path.join(project, item.get("URL"))))
        relative = os.path.relpath(target, root).replace("\\", "/")
        if relative not in records or not os.path.isfile(target):
            raise ValueError("Project VI reference does not resolve inside package")
        refs.add(relative)
    if refs != set(records):
        raise ValueError("Project does not reference exactly the packaged three VIs")
    for link in manifest["custom_relative_links"]:
        caller = os.path.join(root, *link["caller"].split("/"))
        parts = [".." if p == "" else p for p in link["components"]]
        target = _inside(root, os.path.normpath(os.path.join(caller, *parts)))
        if os.path.relpath(target, root).replace("\\", "/") != link["target"]:
            raise ValueError("Pinned relative call-link closure changed")
        if link["target"] not in records:
            raise ValueError("Call dependency not in package")
    component_results = []
    for component in components:
        component_root = _inside(
            root, os.path.join(root, *component["path"].split("/"))
        )
        with open(
            os.path.join(component_root, "package_manifest.json"), "rb"
        ) as stream:
            if (
                hashlib.sha256(stream.read()).hexdigest()
                != component["manifest_sha256"]
            ):
                raise ValueError("Additional component manifest pin changed")
        try:
            from tools.verify_labview_native_helper_package import verify_component
        except ImportError:  # Direct python tools/... invocation.
            from verify_labview_native_helper_package import verify_component
        component_results.append(verify_component(component_root))
    return dict(
        status="PASS",
        native12_VIs=records,
        project_URLs_closed=True,
        pinned_relative_call_closure=True,
        executed=False,
        native_runtime_proved=False,
        additional_components=component_results,
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
        ),
    )
    args = parser.parse_args()
    print(json.dumps(verify_package(args.root), indent=2, sort_keys=True))
