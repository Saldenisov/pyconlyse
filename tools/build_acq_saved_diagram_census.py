"""Inventory every diagram of hash-checked original Acquisition LLB members.

Run with the existing lvkit extraction environment. This performs binary
resource extraction, not LabVIEW execution. Rows are an audit queue, never
an automatic assertion of behavioral coverage.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


MANIFEST_SHA256 = "1DCE49EAD711CBDD7AB75578D5655AACEFA6A47C6B445D8FED2C4D402A0A37E0"
LLB_SHA256 = "EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A"
FIELDS = (
    "vi", "source_vi_sha256", "scope_path", "owner_class", "owner_uid",
    "frame_index", "diagram_uid", "ancestor_diagram_disable_uids",
    "direct_structure_uids", "direct_call_uids_and_qualified_names",
    "direct_primitive_uids_and_resource_ids", "direct_local_param_indices",
    "local_names_resolved", "wire_count", "behavioral_coverage",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def call_names(metadata):
    names = {}
    for link in metadata.findall(".//IUVI"):
        qualified = ":".join(s.text or "" for s in link.findall("LinkSaveQualName/String"))
        for offset in link.findall("LinkOffsetList/Offset"):
            uid = str(int(offset.text, 16))
            if uid in names and names[uid] != qualified:
                raise AssertionError(f"conflicting call link at UID {uid}")
            names[uid] = qualified
    return names


def diagram_rows(vi, source_hash, bd, metadata):
    names = call_names(metadata)

    def walk(diagram, owner_class, owner_uid, index, path, disabled):
        actual = list(diagram.findall("zPlaneList/*[@class]"))
        structures = [n for n in actual if n.find("diagramList") is not None
                      or n.find("sequenceList") is not None]
        direct_locals = [n for n in actual if n.get("class") == "gRef"]
        yield {
            "vi": vi, "source_vi_sha256": source_hash, "scope_path": path,
            "owner_class": owner_class, "owner_uid": owner_uid,
            "frame_index": index, "diagram_uid": diagram.get("uid"),
            "ancestor_diagram_disable_uids": ";".join(disabled),
            "direct_structure_uids": ";".join(n.get("class") + ":" + n.get("uid") for n in structures),
            "direct_call_uids_and_qualified_names": ";".join(
                n.get("uid") + ":" + names.get(n.get("uid"), n.findtext("label/textRec/text") or "UNRESOLVED")
                for n in actual if n.get("class") == "iUse"),
            "direct_primitive_uids_and_resource_ids": ";".join(
                n.get("uid") + ":" + (n.findtext("primResID") or "UNRESOLVED")
                for n in actual if n.get("class") == "prim"),
            "direct_local_param_indices": ";".join(sorted({
                n.findtext("termList/*/dco/paramIdx") or "UNRESOLVED" for n in direct_locals})),
            "local_names_resolved": False,
            "wire_count": len(diagram.findall("signalList/*")),
            "behavioral_coverage": "UNREVIEWED",
        }
        for node in structures:
            klass, uid = node.get("class"), node.get("uid")
            nested_disabled = disabled + ((uid,) if klass == "commentNode" else ())
            diagrams = node.find("diagramList")
            if diagrams is None:
                diagrams = [d for cell in node.find("sequenceList")
                            for d in cell.findall("diagramList/*")]
            for frame_index, frame in enumerate(diagrams):
                yield from walk(frame, klass, uid, frame_index,
                                f"{path}/{klass}:{uid}[{frame_index}]", nested_disabled)

    root = bd.find("root")
    if root is None:
        raise AssertionError(f"{vi}: top-level diagram absent")
    yield from walk(root, "root", root.get("uid"), 0, vi + "/root", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reuse-export-report", type=Path,
                        help="Reuse only XML whose hashes match a previous extraction report")
    args = parser.parse_args()
    if digest(args.manifest) != MANIFEST_SHA256:
        raise AssertionError("original member manifest hash changed")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    if manifest["source_llb_sha256"].upper() != LLB_SHA256 or manifest["member_count"] != 17:
        raise AssertionError("source LLB/member identity changed")
    if args.csv.exists() or args.report.exists():
        raise FileExistsError("do not overwrite an existing census or review report")
    sources = []
    for member in manifest["members"]:
        source = args.source_dir / member["name"]
        expected = member["sha256"].upper()
        if digest(source) != expected:
            raise AssertionError(f"source member drift: {member['name']}")
        sources.append((source, expected))
    cache = {}
    if args.reuse_export_report:
        previous = json.loads(args.reuse_export_report.read_text(encoding="utf-8"))
        if previous["member_manifest_sha256"] != MANIFEST_SHA256:
            raise AssertionError("cached export report has a different source manifest")
        cache = {m["vi"]: m for m in previous["members"]}
    else:
        from lvkit.extractor import _extract_in_process

    args.export_dir.mkdir(parents=True, exist_ok=True)
    rows, exports, graph = [], [], {}
    for source, source_hash in sources:
        target = args.export_dir / source.stem
        if cache:
            cached = cache[source.name]
            if cached["source_vi_sha256"] != source_hash or Path(cached["export_directory"]) != target.resolve():
                raise AssertionError(f"cached export source/path mismatch: {source.name}")
            for filename, expected in cached["export_xml_sha256"].items():
                if digest(target / filename) != expected:
                    raise AssertionError(f"cached XML changed: {source.name}/{filename}")
        else:
            target.mkdir(exist_ok=False)
            _extract_in_process(source, target.resolve(), "vi")
        if digest(source) != source_hash:
            raise AssertionError(f"source changed while extracting {source.name}")
        bd = ET.parse(target / "vi_BDHb.xml").getroot()
        metadata = ET.parse(target / "vi.xml").getroot()
        linked = call_names(metadata)
        actual_calls = {n.get("uid") for n in bd.findall(".//*[@class='iUse']")}
        graph[source.name] = sorted({linked[uid].split(":")[-1] for uid in actual_calls
                                     if uid in linked and linked[uid].split(":")[-1]
                                     in {p.name for p, _hash in sources}})
        member_rows = list(diagram_rows(source.name, source_hash, bd, metadata))
        raw_diagram_uids = {n.get("uid") for n in bd.iter() if n.get("class") == "diag"}
        if {row["diagram_uid"] for row in member_rows} != raw_diagram_uids:
            raise AssertionError(f"not every raw diagram was traversed: {source.name}")
        rows.extend(member_rows)
        exports.append({
            "vi": source.name, "source_vi_sha256": source_hash,
            "export_directory": str(target.resolve()),
            "export_xml_sha256": {p.name: digest(p) for p in sorted(target.glob("*.xml"))},
            "diagram_count": len(member_rows),
        })
        print(f"{source.name}: {len(member_rows)} raw diagrams", flush=True)
    keys = [(r["vi"], r["diagram_uid"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise AssertionError("duplicate diagram UID within member")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    reachable, queue = set(), ["0_ACQ_ELYSE.vi"]
    while queue:
        member = queue.pop()
        if member not in reachable:
            reachable.add(member)
            queue.extend(graph[member])
    report = {
        "source_llb_sha256": LLB_SHA256,
        "member_manifest_sha256": MANIFEST_SHA256,
        "source_vi_hashes_checked_before_and_after_extraction": True,
        "members": exports, "total_diagrams": len(rows),
        "owner_class_counts": dict(Counter(r["owner_class"] for r in rows)),
        "non_root_diagrams": sum(r["owner_class"] != "root" for r in rows),
        "local_call_graph": graph,
        "statically_reachable_members": sorted(reachable),
        "statically_unreferenced_members": sorted(set(graph) - reachable),
        "reachable_non_root_diagrams": sum(r["owner_class"] != "root" and r["vi"] in reachable for r in rows),
        "selector_frame_rows_excluding_root_and_while_for_bodies": sum(
            r["owner_class"] not in {"root", "whileLoop", "forLoop"} for r in rows),
        "all_rows_initially_unreviewed": True,
        "native_ui_access": False, "hardware_access": False,
        "parser_limit": "Some DFDS/variant resource exports emit decoding warnings. This census uses raw BDHb structure and IUVI links, not inferred default values or parameter names. Comment-structure ancestry is indexed without assuming which arm is active.",
        "claim_limit": "Structural census of saved original diagrams, not verified guards, local names, diagram-enable status, behavior, or live-source equivalence.",
        "csv": str(args.csv.resolve()), "csv_sha256": digest(args.csv),
    }
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(f"Total: {len(rows)} diagrams; no behavioral row promoted automatically")


if __name__ == "__main__":
    main()
