"""Read-only observer artifact checks; Python 3.4 standard library only.

This bounded RSRC envelope reader checks LVSR version/flags, not LabVIEW graph
execution. It never loads a VI, invokes a driver, or opens a network socket.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import struct


MAX_FILE_BYTES = 2 * 1024 * 1024
PROOF_SHA256 = "8d27a36bf7d743f72687ca70d06f82175fce7680f3fdc34c92325546a5502775"
PINS = {
    "SUP_Camera_Observe_U8_UNCOMPILED.vi":
        "c6387a4d2d5f41ded7829ed154c89c89faa840b2aa844c1f0803d76b04c235e9",
    "observer_v3/SUP_Camera_Queue_Latest.vi":
        "bef72a8c0a4b7cc269e1694668464ba5c75164519687fee3b428552e7bd49bb7",
}
DEFAULT_BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "legacy", "labview", "supervision_telemetry")


class BundleError(ValueError):
    pass


def _unpack(fmt, raw, offset, limit):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > limit or limit > len(raw):
        raise BundleError("RSRC field exceeds its declared region")
    return struct.unpack_from(fmt, raw, offset)


def _resource_sections(raw):
    """Read only bounded RSRC v3 directories and their raw section extents."""
    if len(raw) < 88 or len(raw) > MAX_FILE_BYTES:
        raise BundleError("VI size outside observer bundle bounds")
    h = _unpack(">6sH4s4sIIII", raw, 0, len(raw))
    magic, fmt, kind, creator, info, info_size, data, data_size = h
    if (magic, fmt, kind, creator) != (b"RSRC\r\n", 3, b"LVIN", b"LBVW"):
        raise BundleError("Expected a LabVIEW VI RSRC v3 container")
    if data != 32 or data + data_size != info or info + info_size != len(raw):
        raise BundleError("RSRC data/info regions do not cover the file")
    if info < data or info_size < 56 or raw[info:info + 32] != raw[:32]:
        raise BundleError("RSRC directory header mismatch")
    unused1, unused2, header_size, table_offset, table_size = _unpack(
        ">5I", raw, info + 32, len(raw))
    if header_size != 32 or table_offset != 52 or not 56 <= table_size <= info_size:
        raise BundleError("Unsupported RSRC directory layout")
    table = info + table_offset
    table_end = info + table_size
    count = _unpack(">I", raw, table, table_end)[0] + 1
    if not 1 <= count <= 128:
        raise BundleError("RSRC resource count outside bounds")
    directory_end = table + 4 + count * 12
    if directory_end > table_end:
        raise BundleError("Truncated RSRC resource directory")
    sections, tags, regions = {}, set(), []
    for index in range(count):
        tag, section_last, section_offset = _unpack(
            ">4sII", raw, table + 4 + index * 12, directory_end)
        if tag in tags or section_last >= 128:
            raise BundleError("Duplicate resource or excessive section count")
        tags.add(tag)
        section_table = table + section_offset
        if section_table < directory_end:
            raise BundleError("Section directory overlaps resource headers")
        for ordinal in range(section_last + 1):
            number, name, reserved, relative, reserved2 = _unpack(
                ">iIIII", raw, section_table + ordinal * 20, table_end)
            key = (tag, number)
            if key in sections or number < 0:
                raise BundleError("Duplicate or negative resource section")
            start = data + relative
            length = _unpack(">I", raw, start, info)[0]
            if start < data or length > MAX_FILE_BYTES or start + 4 + length > info:
                raise BundleError("Resource payload exceeds data region")
            sections[key] = (start + 4, length)
            regions.append((start, start + 4 + length))
    regions.sort()
    if any(a[1] > b[0] for a, b in zip(regions, regions[1:])):
        raise BundleError("Resource payloads overlap")
    return sections


def inspect_vi_rsrc(raw):
    sections = _resource_sections(raw)
    if (b"LVSR", 0) not in sections:
        raise BundleError("VI has no LVSR execution record")
    offset, length = sections[(b"LVSR", 0)]
    if length < 12:
        raise BundleError("Truncated LVSR execution record")
    version, execution, flags2 = _unpack(">III", raw, offset, offset + length)
    if version != 0x12008004:
        raise BundleError("Expected native LabVIEW 12.0.0 release build 4 format")
    if execution & (1 << 14):
        raise BundleError("RunOnOpen is forbidden in the observer proof bundle")
    if execution & (1 << 16) or flags2 & (1 << 10):
        raise BundleError("Uncompiled source candidate is not the pinned native export")
    return dict(version="12.0.0 release build 4", run_on_open=False,
                bad_compile=False, source_only=False, resource_sections=len(sections))


def _read(path, limit=MAX_FILE_BYTES):
    if os.path.islink(path):
        raise BundleError("Bundle symlinks are forbidden")
    with open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise BundleError("Bundle file exceeds size limit")
    return raw


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise BundleError("Duplicate JSON key")
        value[key] = item
    return value


def _json(path):
    return json.loads(_read(path, 128 * 1024).decode("utf-8"), object_pairs_hook=_unique_object)


def verify_bundle(root=DEFAULT_BUNDLE):
    root = os.path.abspath(root)
    if os.path.islink(root):
        raise BundleError("Bundle root must not be a symlink")
    manifest = _json(os.path.join(root, "manifest.json"))
    if (manifest.get("schema_version") != 1 or manifest.get("status") != "NOT_RUNTIME_QUALIFIED"
            or manifest.get("native2012_open_save_verified") is not False
            or manifest.get("physical_camera_verified") is not False):
        raise BundleError("Bundle qualification must remain explicit and incomplete")
    if manifest.get("proof_sha256") != PROOF_SHA256:
        raise BundleError("Manifest differs from the reviewed proof receipt hash")
    records = manifest.get("files")
    if not isinstance(records, dict) or set(records) != set(PINS):
        raise BundleError("Custom VI dependency closure differs from the reviewed pair")
    allowed = set(PINS) | {"manifest.json", "proof.json", "README.rst"}
    actual = set()
    for base, folders, files in os.walk(root):
        if len(actual) > 16 or any(os.path.islink(os.path.join(base, p)) for p in folders):
            raise BundleError("Unexpected bundle directory or symlink")
        for name in files:
            path = os.path.join(base, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path) or relative not in allowed:
                raise BundleError("Unexpected bundle file: " + relative)
            actual.add(relative)
    if actual != allowed:
        raise BundleError("Bundle is incomplete")
    checked = {}
    for name, expected in sorted(PINS.items()):
        if not re.match(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$", name):
            raise BundleError("Unsafe manifest path")
        record = records[name]
        if not isinstance(record, dict) or record.get("sha256") != expected:
            raise BundleError("Manifest differs from the pinned native VI hashes")
        raw = _read(os.path.join(root, *name.split("/")))
        if len(raw) != record.get("bytes") or hashlib.sha256(raw).hexdigest() != expected:
            raise BundleError("Native VI checksum/length mismatch: " + name)
        checked[name] = inspect_vi_rsrc(raw)
    proof = _read(os.path.join(root, "proof.json"), 128 * 1024)
    if hashlib.sha256(proof).hexdigest() != PROOF_SHA256:
        raise BundleError("Proof receipt checksum mismatch")
    return dict(status="NOT_RUNTIME_QUALIFIED", files=checked,
                native2012_open_save_verified=False, physical_camera_verified=False,
                validation="pinned bytes, bounded RSRC version/flags, explicit dependency closure",
                vi_loaded=False, vi_executed=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", default=DEFAULT_BUNDLE)
    args = parser.parse_args(argv)
    try:
        result = verify_bundle(args.bundle)
    except (BundleError, OSError, ValueError, struct.error) as error:
        parser.exit(1, "Observer bundle verification failed: {}\n".format(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
