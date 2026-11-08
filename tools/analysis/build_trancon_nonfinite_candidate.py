"""Generate Nan_Inf_replaced with an explicitly substituted historical OpenG VI.

The absent installed OpenG binary is not claimed to match this substitute.
Candidate remains separate from qualified numeric exports; native capture and
NaN-search behavior must be checked in the original LabVIEW environment.
"""

import argparse
import csv
import hashlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r"C:\dev\TRANCON\dependecies\Nan_Inf_replaced.vi")
SOURCE_HASH = "7e0fdc6eae10a1ad974d22d0324eadd1144e09043f497f280a60a5d301c206ef"
OPENG_COMMIT = "c6f61a9350216cca8075158840aa8c819af3c1dd"
OPENG_PATH = "source/library/Search Array/Search 1D Array (DBL).vi"
OPENG_HASH = "e2cdcac50197d1a86873d04fe58c205d098a000076e19620e3b5b73affe947a9"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--openg-repository", type=Path,
                        default=Path(r"C:\dev\TRANCON-analysis\dependencies\OpenG-Array-Library"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--node-packages", type=Path, required=True)
    args = parser.parse_args()
    if sha(SOURCE) != SOURCE_HASH:
        raise RuntimeError("Original TRANCON source fingerprint changed")
    if subprocess.check_output(["git", "-C", str(args.converter), "rev-parse", "HEAD"],
                               text=True).strip() != "d8058677e15c47094e725439bd72417fe9527754":
        raise RuntimeError("Unexpected lvkit base commit")
    env = {**os.environ, "PYTHONPATH": str(args.converter.resolve() / "src")}
    records = []

    def record(kind, path, note="", original_hash=""):
        records.append({"kind": kind, "path": str(path), "sha256": sha(path),
                        "original_sha256": original_hash, "note": note,
                        "native_screenshot_verified": False})

    record("source_vi", SOURCE)
    # Capture endpoint identities from the original binary graph, without aliases.
    sys.path.insert(0, str(args.converter.resolve() / "src"))
    from lvkit.graph import InMemoryVIGraph, LoadMode
    graph = InMemoryVIGraph()
    graph.load_vi(str(SOURCE), LoadMode.MINIMAL)
    wire_rows = []
    for _, _, attributes in graph._graph.edges(data=True):
        if attributes.get("vi") != str(SOURCE):
            continue
        source_end, dest_end = attributes["source"], attributes["dest"]
        source_node = graph._graph.nodes[source_end.node_id]["node"]
        dest_node = graph._graph.nodes[dest_end.node_id]["node"]
        wire_rows.append({
            "source_node_uid": source_end.node_id.rsplit("::", 1)[-1],
            "source_name": source_node.name or source_node.node_type or source_node.kind,
            "source_terminal_uid": source_end.terminal_id.rsplit("::", 1)[-1],
            "source_index": source_end.index,
            "source_constant": getattr(source_node, "value", ""),
            "destination_node_uid": dest_end.node_id.rsplit("::", 1)[-1],
            "destination_name": dest_node.name or dest_node.node_type or dest_node.kind,
            "destination_terminal_uid": dest_end.terminal_id.rsplit("::", 1)[-1],
            "destination_index": dest_end.index,
        })
    wire_path = ROOT / "docs/data-treatment/TRANCON_NONFINITE_WIRES_2026-10-03.csv"
    with wire_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(wire_rows[0]))
        writer.writeheader()
        writer.writerows(wire_rows)
    record("wire_endpoints", wire_path, "Original source binary; missing helper was not substituted")
    dependency = args.work / "openg-source"
    dependency.mkdir(parents=True, exist_ok=True)
    payload = subprocess.check_output(
        ["git", "-C", str(args.openg_repository), "show", f"{OPENG_COMMIT}:{OPENG_PATH}"])
    if hashlib.sha256(payload).hexdigest() != OPENG_HASH:
        raise RuntimeError("OpenG source hash changed")
    # Literal byte-identical aliases bridge packaged __ogtk filenames only.
    for filename in ("Search Array__ogtk.vi", "Search 1D Array (DBL)__ogtk.vi"):
        path = dependency / filename
        path.write_bytes(payload)
        record("substitute_dependency_alias", path,
               f"OpenG {OPENG_COMMIT}:{OPENG_PATH}; not installed project binary")

    def lvkit(*command):
        result = subprocess.run([str(args.python), "-m", "lvkit", *map(str, command)],
                                env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode or "-> FAILED" in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout, result.stderr

    output = args.work / "generated"
    out, err = lvkit("generate", SOURCE, "-o", output, "--load-mode", "minimal",
                    "--no-auto-vilib", "--search-path", dependency)
    (args.work / "generation.log").write_text(out + err, encoding="utf-8")
    destination = ROOT / "legacy/trancon_client/candidates/nan_inf_replaced"
    destination.mkdir(parents=True, exist_ok=True)
    (destination.parent / "__init__.py").write_text(
        '"""Experimental translations requiring original dependency and native validation."""\n',
        encoding="utf-8")
    for path in sorted((output / "nan_inf_replaced").rglob("*.py")):
        target = destination / path.relative_to(output / "nan_inf_replaced")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        record("generated_candidate", target, "Unedited lvkit output", sha(path))
    license_path = destination / "OPENG_LICENSE"
    license_path.write_bytes((args.openg_repository / "LICENSE").read_bytes())
    record("license", license_path, "OpenG upstream BSD license")

    # Both diagrams are static reconstructions of the stored wires.
    image_dir = ROOT / "docs/data-treatment/images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for source, prefix in ((SOURCE, "TRANCON_NAN_INF_REPLACED"),
                           (dependency / "Search 1D Array (DBL)__ogtk.vi", "TRANCON_OPENG_SEARCH_DBL")):
        svg = image_dir / f"{prefix}_LVKIT_2026-10-03.svg"
        lvkit("render", source, "-o", svg, "--no-cache", "--load-mode", "minimal", "--no-auto-vilib")
        record("lvkit_diagram", svg, "Reconstruction, not a native LabVIEW screenshot")
        png = svg.with_suffix(".png")
        subprocess.run([str(args.node), str(ROOT / "tools/analysis/rasterize_lvkit_svg.cjs"),
                        str(svg), str(png)], env={**os.environ, "NODE_PATH": str(args.node_packages)},
                       check=True, capture_output=True)
        record("lvkit_png", png, "SVG rasterization, not a native LabVIEW screenshot")
        net, err = lvkit("describe", source, "--format", "lvnet", "-v",
                         "--load-mode", "minimal", "--no-auto-vilib")
        netfile = ROOT / "docs/data-treatment" / f"{prefix}_2026-10-03.lvnet"
        netfile.write_text(net, encoding="utf-8")
        record("lvnet", netfile)
    for path in (args.converter / "src/lvkit/codegen/context.py", Path(__file__),
                 Path(__file__).with_name("test_trancon_lvkit_nonfinite.py"),
                 Path(__file__).with_name("verify_trancon_nonfinite_candidate.py"),
                 Path(__file__).with_name("rasterize_lvkit_svg.cjs")):
        record("converter_or_driver", path)
    patch = ROOT / "tools/trancon_lvkit_nonfinite_2026-10-03.patch"
    if patch.exists():
        record("converter_patch", patch, "Apply after trancon_lvkit_overlay.patch")
    manifest = ROOT / "docs/data-treatment/TRANCON_NONFINITE_PROVENANCE_2026-10-03.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(out)
    print(f"Candidate: {destination}; native_screenshot_verified=False")


if __name__ == "__main__":
    main()
