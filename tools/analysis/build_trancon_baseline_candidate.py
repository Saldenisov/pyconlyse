"""Generate BG_corrSD's Aver branch without changing its numeric wiring.

The global selector becomes an explicit input, fixed to Aver by the candidate
adapter. SG descendants are excluded before codegen. Plot/global writes are
outside this pure adapter's boundary. Native diagrams remain unverified;
the indexed scalar-background tunnel prevents release into Web V0.
"""

import argparse
import ast
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r"C:\dev\TRANCON\dependecies\BG_corrSD.vi")
SOURCE_HASH = "fd598d757b70af95e25020ccb759d963e7dee0a35e887c51a4bc9ed027b73e39"
BASE = "d8058677e15c47094e725439bd72417fe9527754"
TARGET = ROOT / "legacy/trancon_client/candidates/baseline"
DOCS = ROOT / "docs/data-treatment"
RUNTIME = {"_binop", "sub", "_real64_divide_scalar", "real64_divide",
           "index_array_nd", "array_size", "array_subset_nd"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_aver(graph, key):
    """Only constrain mode/global boundary; retain arithmetic and lpTun modes."""
    from lvkit.graph.models import CaseStructureNode, LocalVariableNode

    scope = graph._graph.nodes[key + "::1444"]["node"]
    selector = graph._graph.nodes[key + "::807"]["node"]
    if (not isinstance(scope, CaseStructureNode)
            or not isinstance(selector, LocalVariableNode)
            or selector.is_write or len(selector.terminals) != 1
            or {str(f.selector_value) for f in scope.frames} != {"1", "Default"}):
        raise RuntimeError("BG mode topology changed")
    values = selector.terminals[0].lv_type.values
    if values["Aver"].value != 0 or values["Savitzky-Golay"].value != 1:
        raise RuntimeError("BG mode enum changed")
    # Alias only the global read's existing output net to a pure function input.
    virtual = selector.terminals[0].model_copy(deep=True)
    virtual.name = "baseline mode"
    virtual.direction = "input"
    virtual.default_value = "0"
    graph._graph.nodes[key]["node"].terminals.append(virtual)
    graph._term_to_node[virtual.id] = key
    # Retain the original graph node and wire edge endpoints. Its global read
    # is excluded by lvkit's unreviewed-local boundary; the input binds its net.

    erased = {uid for uid, data in graph._graph.nodes(data=True)
              if (node := data.get("node")) is not None
              and node.parent == scope.id and node.frame == "1"}
    while True:
        descendants = {uid for uid, data in graph._graph.nodes(data=True)
                       if (node := data.get("node")) is not None and node.parent in erased}
        if descendants <= erased:
            break
        erased |= descendants
    for uid in erased:
        node = graph._graph.nodes[uid]["node"]
        graph._graph.remove_nodes_from([term.id for term in node.terminals] + [uid])
        graph._vi_nodes[key].discard(uid)
    scope.frames = [frame for frame in scope.frames if frame.is_default]
    for _uid, data in graph._graph.nodes(data=True):
        if (node := data.get("node")) is not None:
            node.children = [child for child in node.children if child not in erased]
    return {"fixed_mode": "Aver", "mode_value": 0,
            "global_read_uid": "807", "virtual_input_terminal_uid": "814",
            "excluded_sg_node_uids": sorted(uid.rsplit("::", 1)[-1] for uid in erased),
            "numeric_tunnels_changed": False,
            "plot_global_side_effects_replayed": False,
            "native_screenshot_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter", type=Path, required=True)
    args = parser.parse_args()
    converter = args.converter.resolve(strict=True)
    if digest(SOURCE) != SOURCE_HASH:
        raise RuntimeError("BG_corrSD source fingerprint changed")
    if subprocess.check_output(["git", "-C", str(converter), "rev-parse", "HEAD"],
                               text=True).strip() != BASE:
        raise RuntimeError("Unexpected lvkit base")
    sys.path.insert(0, str(converter / "src"))
    from lvkit.graph import InMemoryVIGraph
    from lvkit.load_mode import LoadMode
    from lvkit.codegen import build_module
    from lvkit.codegen.context import CodeGenContext
    from lvkit.extractor import extract_vi_xml
    from lvkit.parser.type_resolution import parse_type_chain
    from lvkit.parser.type_mapping import parse_type_map_rich
    import xml.etree.ElementTree as ET

    graph = InMemoryVIGraph()
    key = graph.load_vi(SOURCE, mode=LoadMode.MINIMAL)
    # Preserve raw tunnel encoding and the complete heap -> consolidated ->
    # flat type chain. An inferred tunnel mode alone is insufficient evidence.
    bd_xml, _fp_xml, main_xml = extract_vi_xml(SOURCE)
    root = ET.parse(bd_xml).getroot()
    main_root = ET.parse(main_xml).getroot()
    chain, types = parse_type_chain(main_xml), parse_type_map_rich(main_xml)
    flat_types = main_root.find(".//VCTP/Section").findall("TypeDesc")
    context = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
    evidence = []
    for tunnel in context.tunnels(graph._graph.nodes[key + "::2207"]["node"]):
        if tunnel.tunnel_type != "lpTun":
            continue
        outer = graph.get_terminal(tunnel.outer_terminal_uid)
        inner = graph.get_terminal(tunnel.inner_terminal_uid)
        outer_uid = outer.id.rsplit("::", 1)[-1]
        dco = root.find(f'.//*[@class="term"][@uid="{outer_uid}"]/dco')
        type_chain = []
        for face, dco_type in (("outer", dco.findtext("typeDesc")),
                               ("inner", dco.findtext("innerLpTunDCO/typeDesc"))):
            heap = int(dco_type.removeprefix("TypeID(").removesuffix(")"))
            consolidated = chain["heap_to_consolidated"][heap][0]
            flat = chain["consolidated_to_flat"][consolidated]
            type_chain.append({"face": face, "heap_type_id": heap,
                               "consolidated_type_id": consolidated, "flat_type_id": flat,
                               "type": types[heap].type_descriptor(),
                               "flat_type_xml": ET.tostring(flat_types[flat], encoding="unicode")})
        evidence.append({"loop_uid": "2207", "outer_terminal_uid": outer_uid,
                         "inner_terminal_uid": inner.id.rsplit("::", 1)[-1],
                         "direction": outer.direction, "lvkit_mode": tunnel.mode.value,
                         "tunnel_type": dco.findtext("TunnelType"),
                         "inner_obj_flags": dco.findtext("innerLpTunDCO/objFlags"),
                         "type_chain": type_chain})
    evidence_path = DOCS / "TRANCON_BASELINE_TUNNELS_2026-10-04.json"
    evidence_path.write_text(json.dumps({"source_sha256": SOURCE_HASH, "tunnels": evidence},
                                       indent=2) + "\n", encoding="utf-8")
    wire_rows = []
    for _a, _b, attrs in graph._graph.edges(data=True):
        if attrs.get("vi") != key:
            continue
        src, dst = attrs["source"], attrs["dest"]
        wire_rows.append({"source_node_uid": src.node_id.rsplit("::", 1)[-1],
                          "source_terminal_uid": src.terminal_id.rsplit("::", 1)[-1],
                          "source_index": src.index,
                          "destination_node_uid": dst.node_id.rsplit("::", 1)[-1],
                          "destination_terminal_uid": dst.terminal_id.rsplit("::", 1)[-1],
                          "destination_index": dst.index})
    wire_path = DOCS / "TRANCON_BASELINE_WIRES_2026-10-04.csv"
    with wire_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(wire_rows[0]))
        writer.writeheader()
        writer.writerows(wire_rows)

    projection = project_aver(graph, key)
    code = build_module(graph.get_vi_context(key), key, graph=graph)
    if ("array_subset_nd" not in code or "min(len(data), len(" not in code
            or "if not baseline_mode:" not in code or "if not selector:" in code):
        raise RuntimeError("Candidate numeric topology changed; re-review")
    TARGET.mkdir(parents=True, exist_ok=True)
    original_hash = hashlib.sha256(code.encode()).hexdigest()
    code = code.replace("from lvkit.runtime import lv as _lv", "from . import _runtime as _lv")
    ast.parse(code)
    generated = TARGET / "bg_corrsd.py"
    generated.write_text(code, encoding="utf-8", newline="\n")
    runtime_path = converter / "src/lvkit/runtime/lv.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in RUNTIME]
    if {node.name for node in helpers} != RUNTIME:
        raise RuntimeError("Runtime helper set changed")
    runtime = TARGET / "_runtime.py"
    runtime.write_text('"""AST-extracted lvkit subset; native qualification pending."""\n'
                       'from __future__ import annotations\nimport math as _math\n'
                       'import operator as _op\nfrom collections.abc import Callable\n\n'
                       + "\n\n".join(ast.unparse(node) for node in helpers) + "\n",
                       encoding="utf-8", newline="\n")
    projection_path = DOCS / "TRANCON_BASELINE_PROJECTION_2026-10-04.json"
    projection_path.write_text(json.dumps({"source_sha256": SOURCE_HASH,
                                          "generated_original_sha256": original_hash,
                                          **projection}, indent=2) + "\n", encoding="utf-8")
    records = []
    for kind, paths in (
        ("source_vi", [SOURCE]), ("generated_candidate", [generated]),
        ("source_dependency", [SOURCE.with_name("globalVarSD.vi")]),
        ("runtime_subset", [runtime]), ("source_wires", [wire_path]),
        ("source_tunnels", [evidence_path]),
        ("projection", [projection_path]),
        ("converter", sorted((converter / "src/lvkit").rglob("*.py"))),
        ("patch", [ROOT / "tools/trancon_lvkit_overlay.patch",
                   ROOT / "tools/trancon_lvkit_baseline_2026-10-04.patch"]),
        ("driver_or_adapter", [Path(__file__), TARGET / "__init__.py",
                               Path(__file__).with_name("test_trancon_baseline_candidate.py")]),
        ("qualification_report", [DOCS / "TRANCON_BASELINE_ANALYSIS_2026-10-04.md"]),
        ("lvkit_reconstruction", [DOCS / "images/BG_CORRSD_LVKIT_2026-10-04.svg",
                                  DOCS / "images/BG_CORRSD_LVKIT_2026-10-04.png"]),
        ("web_rejection_gate", [ROOT / "tests/web/test_trancon_v0_processing.py"]),
        ("license", [ROOT / "legacy/trancon_client/LVKIT_LICENSE"]),
    ):
        records.extend({"kind": kind, "path": str(path), "sha256": digest(path),
                        "native_screenshot_verified": False} for path in paths)
    manifest = DOCS / "TRANCON_BASELINE_PROVENANCE_2026-10-04.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"Aver candidate generated; {len(wire_rows)} original wires; native verification pending")


if __name__ == "__main__":
    main()
