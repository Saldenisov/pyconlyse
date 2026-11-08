"""Reproduce the cleaning helper and Calc_clean's numeric selection region.

Native LabVIEW screenshots remain pending. Inputs replace only the caller's
class/graph reads; the selected region retains its original arithmetic edges.
The complete helper is generated without a numeric projection.
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
DOCS = ROOT / "docs/data-treatment"
TARGET = ROOT / "legacy/trancon_client/candidates/cleaning"
BASE = "d8058677e15c47094e725439bd72417fe9527754"
SOURCES = {
    Path(r"C:\dev\TRANCON\dependecies\clean-kinetics-SD.vi"):
        "7a5e0eec379fa662b7d34a2b8ae4367fe9e0ddb979aad05a898e89bc685144db",
    Path(r"C:\dev\TRANCON\Classes\Control\Control-Client\Calc_clean.vi"):
        "11fce4bdea3d6c67a941687ba06ae2575c6ac15f1e9994fb1d6654ddb5007521",
    Path(r"C:\dev\TRANCON\Classes\Control\Control-Client\CursorKinGraphMove.vi"):
        "5d1cf2a0a035f07407bf3905a24f12a4b42d0193d1972b7585df39e45a50f5ee",
    Path(r"C:\dev\TRANCON\Classes\Experiments\Experiment\get_data_exp.vi"):
        "8761960884a220be26bccfdb43d7c29945249829232f61895d3780917bc79487",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def short(uid):
    return uid.rsplit("::", 1)[-1]


def source_wires(graph, key):
    return [
        {"vi": key, "source_node_uid": short(e["source"].node_id),
         "source_terminal_uid": short(e["source"].terminal_id),
         "source_index": e["source"].index,
         "destination_node_uid": short(e["dest"].node_id),
         "destination_terminal_uid": short(e["dest"].terminal_id),
         "destination_index": e["dest"].index}
        for _a, _b, e in graph._graph.edges(data=True) if e.get("vi") == key
    ]


def project_kinetics(graph, key):
    """Cut at get_data_exp/min-max cursor outputs and Divide's output net."""
    keep = {"43", "80", "91", "106", "151", "202", "178", "210", "221",
            "140", "168", "192"}
    nodes = {uid: d["node"] for uid, d in graph._graph.nodes(data=True)
             if d.get("node") is not None and d["node"].vi_path == key}
    kept = {uid for uid in nodes if short(uid) in keep} | {key}
    if len(kept) != len(keep) + 1:
        raise RuntimeError("Calc_clean numeric node set changed")
    root = nodes[key]
    ports = []
    original_edges = [(a, b, e.copy()) for a, b, e in graph._graph.edges(data=True)
                      if e.get("vi") == key]
    for uid, name, direction, index in (
        ("488", "data", "input", 0),
        ("265", "wavelength min", "input", 1),
        ("268", "wavelength max", "input", 2),
        ("142", "kinetics", "output", 0),
    ):
        port = graph.get_terminal(key + "::" + uid).model_copy(deep=True)
        port.name, port.direction, port.index = name, direction, index
        ports.append(port)
        # Input producers are removed. Reattach only their edges into the
        # retained numeric region to root inputs, preserving terminal nets.
        if direction == "input":
            graph._term_to_node[port.id] = key
            for _a, b, edge in original_edges:
                if edge["source"].terminal_id == port.id and b in kept:
                    edge["source"] = edge["source"].model_copy(update={"node_id": key, "index": index})
                    graph._graph.add_edge(key, b, **edge)
        else:
            producer = graph._term_to_node[port.id]
            source = next(e["source"] for _a, _b, e in original_edges
                          if e["source"].terminal_id == port.id)
            port.id = key + "::kinetics_projection_output"
            graph._term_to_node[port.id] = key
            graph._graph.add_edge(producer, key, vi=key, source=source,
                                  dest=source.model_copy(update={"node_id": key,
                                                                 "terminal_id": port.id,
                                                                 "index": index}))
    root.terminals = ports
    root.name = "Calc_clean_kinetics.vi"
    root.connector_pattern_id = None
    interface_ids = {p.id for p in ports}
    erased = set(nodes) - kept
    for uid in erased:
        graph._graph.remove_nodes_from([t.id for t in nodes[uid].terminals
                                       if t.id not in interface_ids] + [uid])
        graph._vi_nodes[key].discard(uid)
    for uid in kept:
        node = nodes[uid]
        node.children = [c for c in node.children if c in kept]
        if node.parent not in kept:
            node.parent, node.frame = None, None
    def numeric_edges(edges):
        return sorted((e["source"].terminal_id, e["dest"].terminal_id)
                      for _a, _b, e in edges
                      if e["source"].node_id in kept - {key}
                      and e["dest"].node_id in kept - {key})
    if numeric_edges(original_edges) != numeric_edges(graph._graph.edges(data=True)):
        raise RuntimeError("Calc_clean projection changed internal numeric wires")
    return {"kept_original_node_uids": sorted(keep, key=int),
            "input_aliases": [{"terminal_uid": "488", "source_node_uid": "479", "name": "data"},
                              {"terminal_uid": "265", "source_node_uid": "250", "name": "wavelength_min"},
                              {"terminal_uid": "268", "source_node_uid": "250", "name": "wavelength_max"}],
            "output_alias_terminal_uid": "142", "numeric_edges_changed": False,
            "source_data_type": "[[SGL]]", "accumulator_type": "[DBL]",
            "class_ui_side_effects_replayed": False}


def evidence(graph, key, path):
    """Capture panes and raw loop DCO type chains independently of codegen."""
    import xml.etree.ElementTree as ET
    from lvkit.codegen.context import CodeGenContext
    from lvkit.extractor import extract_vi_xml
    from lvkit.parser.type_resolution import parse_type_chain
    from lvkit.parser.type_mapping import parse_type_map_rich
    from lvkit.graph.models import LoopNode

    bd, _fp, main = extract_vi_xml(path)
    root = ET.parse(bd).getroot()
    chain, types = parse_type_chain(main), parse_type_map_rich(main)
    ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
    nodes, tunnels = [], []
    for uid, attrs in graph._graph.nodes(data=True):
        node = attrs.get("node")
        if node is None or node.vi_path != key:
            continue
        nodes.append({"uid": short(uid), "class": type(node).__name__,
                      "name": node.name, "node_type": node.node_type,
                      "parent_uid": short(node.parent) if node.parent else None,
                      "frame": node.frame,
                      "terminals": [{"uid": short(t.id), "index": t.index,
                                     "direction": t.direction, "name": t.name,
                                     "type": t.lv_type.type_descriptor() if t.lv_type else None,
                                     "wired": graph.terminal_is_wired(t.id),
                                     "default": t.default_value}
                                    for t in node.terminals]})
        if not isinstance(node, LoopNode):
            continue
        for tunnel in ctx.tunnels(node):
            outer = graph.get_terminal(tunnel.outer_terminal_uid)
            inner = graph.get_terminal(tunnel.inner_terminal_uid)
            dco = root.find(f'.//*[@class="term"][@uid="{short(outer.id)}"]/dco')
            if dco is None:
                continue
            chain_rows = []
            for face, field in (("outer", "typeDesc"), ("inner", "innerLpTunDCO/typeDesc")):
                desc = dco.findtext(field)
                if desc is None or not desc.startswith("TypeID("):
                    continue
                heap = int(desc.removeprefix("TypeID(").removesuffix(")"))
                cons = chain["heap_to_consolidated"][heap][0]
                chain_rows.append({"face": face, "heap_type_id": heap,
                                   "consolidated_type_id": cons,
                                   "flat_type_id": chain["consolidated_to_flat"][cons],
                                   "type": types[heap].type_descriptor()})
            tunnels.append({"loop_uid": short(uid), "outer_terminal_uid": short(outer.id),
                            "inner_terminal_uid": short(inner.id),
                            "lvkit_mode": tunnel.mode.value if tunnel.mode else None,
                            "tunnel_type": dco.findtext("TunnelType"),
                            "inner_obj_flags": dco.findtext("innerLpTunDCO/objFlags"),
                            "type_chain": chain_rows})
    return {"path": str(path), "sha256": digest(path), "nodes": nodes, "tunnels": tunnels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter", type=Path, required=True)
    args = parser.parse_args()
    converter = args.converter.resolve(strict=True)
    if subprocess.check_output(["git", "-C", str(converter), "rev-parse", "HEAD"],
                               text=True).strip() != BASE:
        raise RuntimeError("Unexpected lvkit base")
    for path, expected in SOURCES.items():
        if digest(path) != expected:
            raise RuntimeError(f"Source VI fingerprint changed: {path}")
    sys.path.insert(0, str(converter / "src"))
    from lvkit.graph import InMemoryVIGraph
    from lvkit.load_mode import LoadMode
    from lvkit.codegen import build_module
    from lvkit.render import render_vi

    TARGET.mkdir(parents=True, exist_ok=True)
    generated, wire_rows, evidence_rows, projection = [], [], [], {}
    for i, path in enumerate(SOURCES):
        graph = InMemoryVIGraph()
        key = graph.load_vi(path, mode=LoadMode.MINIMAL, layout=True)
        wire_rows.extend(source_wires(graph, key))
        evidence_rows.append(evidence(graph, key, path))
        if i < 2:
            # Render original topology before projecting. The mode display
            # alone changes for the two helper snapshots; source VI is read-only.
            if i == 0:
                case = graph._graph.nodes[key + "::5109"]["node"]
                for uid in ("1089", "887"):
                    classification = graph._graph.nodes[key + "::" + uid]["node"]
                    classification.displayed_frame = next(j for j, f in enumerate(classification.frames)
                                                          if str(f.selector_value) == "True")
                for uid in ("536", "1032"):
                    neighbor = graph._graph.nodes[key + "::" + uid]["node"]
                    neighbor.displayed_frame = next(j for j, f in enumerate(neighbor.frames)
                                                    if str(f.selector_value) == "False")
                for mode in (0, 1):
                    case.displayed_frame = mode
                    svg = render_vi(graph, key, interactive=False)
                    if svg is None:
                        raise RuntimeError("Cleaning geometry incomplete")
                    (DOCS / f"images/CLEAN_KINETICS_MODE{mode}_LVKIT_2026-10-04.svg").write_text(svg, encoding="utf-8")
            else:
                svg = render_vi(graph, key, interactive=False)
                if svg is None:
                    raise RuntimeError("Calc_clean geometry incomplete")
                (DOCS / "images/CALC_CLEAN_LVKIT_2026-10-04.svg").write_text(svg, encoding="utf-8")
                projection = project_kinetics(graph, key)
            code = build_module(graph.get_vi_context(key), key, graph=graph)
            if i == 0 and "clean_mode: int=1" not in code:
                raise RuntimeError("Saved approx default was lost")
            name = "clean_kinetics_sd.py" if i == 0 else "calc_clean_kinetics.py"
            output = TARGET / name
            code = code.replace("from lvkit.runtime import lv as _lv", "from . import _runtime as _lv")
            ast.parse(code)
            output.write_text(code + "\n", encoding="utf-8", newline="\n")
            generated.append(output)

    runtime_path = converter / "src/lvkit/runtime/lv.py"
    runtime_tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    functions = {n.name: n for n in runtime_tree.body if isinstance(n, ast.FunctionDef)}
    helpers = {n.attr for file in generated for n in ast.walk(ast.parse(file.read_text(encoding="utf-8")))
               if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "_lv"}
    while True:
        added = set()
        for name in helpers:
            fn = functions[name]
            locals_ = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            locals_.update(arg.arg for arg in fn.args.args)
            added.update(n.id for n in ast.walk(fn)
                         if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                         and n.id in functions and n.id not in locals_)
        if added <= helpers:
            break
        helpers |= added
    runtime = TARGET / "_runtime.py"
    runtime.write_text('"""AST-extracted lvkit helpers; native cleaning qualification pending."""\n'
                       'from __future__ import annotations\nimport math as _math\n'
                       'import operator as _op\nfrom collections.abc import Callable\n\n'
                       + "\n\n".join(ast.unparse(n) for n in runtime_tree.body
                                      if isinstance(n, ast.FunctionDef) and n.name in helpers) + "\n",
                       encoding="utf-8", newline="\n")
    details = DOCS / "TRANCON_CLEANING_TOPOLOGY_2026-10-04.json"
    details.write_text(json.dumps({"native_screenshot_verified": False,
                                   "sources": evidence_rows, "projection": projection,
                                   "runtime_helpers": sorted(helpers)}, indent=2) + "\n", encoding="utf-8")
    wires = DOCS / "TRANCON_CLEANING_WIRES_2026-10-04.csv"
    with wires.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(wire_rows[0]))
        writer.writeheader()
        writer.writerows(wire_rows)
    records = []
    for kind, paths in (
        ("source_vi", SOURCES), ("generated_candidate", generated),
        ("runtime_subset", [runtime]), ("source_topology", [details]), ("source_wires", [wires]),
        ("converter", sorted((converter / "src/lvkit").rglob("*.py"))),
        ("converter_data", sorted((converter / "src/lvkit/data").rglob("*.json"))),
        ("patch", [ROOT / "tools/trancon_lvkit_overlay.patch",
                   ROOT / "tools/trancon_lvkit_baseline_2026-10-04.patch",
                   ROOT / "tools/trancon_lvkit_cleaning_2026-10-04.patch"]),
        ("driver_or_adapter", [Path(__file__), TARGET / "__init__.py",
                               Path(__file__).with_name("test_trancon_cleaning_candidate.py"),
                               Path(__file__).with_name("audit_trancon_cleaning.py")]),
        ("archive_audit", [DOCS / "TRANCON_CLEANING_AUDIT_2026-10-04.csv"]),
        ("web_release_gate", [ROOT / "tests/web/test_trancon_cleaning_gate.py"]),
        ("qualification_report", [DOCS / "TRANCON_CLEANING_ANALYSIS_2026-10-04.md"]),
        ("lvkit_reconstruction", sorted((DOCS / "images").glob("*CLEAN*LVKIT_2026-10-04.*"))),
        ("license", [ROOT / "legacy/trancon_client/LVKIT_LICENSE"]),
    ):
        records.extend({"kind": kind, "path": str(path), "sha256": digest(path),
                        "native_screenshot_verified": False} for path in paths)
    manifest = DOCS / "TRANCON_CLEANING_PROVENANCE_2026-10-04.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"Cleaning candidate generated: {len(wire_rows)} original edges, helpers {sorted(helpers)}")


if __name__ == "__main__":
    main()
