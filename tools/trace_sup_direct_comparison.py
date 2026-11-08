"""Complete saved direct-line comparison output in an explicit finite domain.

This is a pure control-state projection, not native connector/runtime equivalence
and not a device controller. Field identities come from original explicit indices.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter

from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, digest
from trace_sup_beam_switches import COMPARISON, COMPARISON_SHA, Wires, terms
from trace_sup_phase_status import exact_net, helper_sources, scalar_updates
from validate_sup_modulator_request_gate import require

FOLDER = REPO / "Supervision/integration_analysis/direct_comparison_complete_20261017"
OUTPUT = FOLDER / "RESULT.json"
PHASE = 2


def verify(bundle=None):
    receipt, roots = helper_sources() if bundle is None else bundle
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    w = Wires(g)
    census = Counter(n.get("class") for n in g.nodes.values())
    require(
        census["diag"] == 3
        and census["sequence"] == 1
        and census["gRef"] == 3
        and census["fPTerm"] == 3,
        "comparison whole-body state/structure census changed",
    )
    require(
        not any(
            census[cls]
            for cls in (
                "select",
                "whileLoop",
                "forLoop",
                "iUse",
                "propNode",
                "invokeNode",
                "extFunc",
            )
        ),
        "comparison gained a branch, callee or external side effect",
    )
    primitive_counts = Counter(
        n.findtext("primResID") for n in g.nodes.values() if n.get("class") == "prim"
    )
    require(
        primitive_counts == {"1051": 11, "1054": 11, "1110": 11},
        "comparison arithmetic census changed",
    )
    require(
        [n.get("uid") for n in g.nodes["2636"].findall("diagramList/*")]
        == ["5910", "5053"],
        "comparison phase order changed",
    )
    require(
        {uid for uid, n in g.nodes.items() if n.get("class") == "gRef"}
        == {"5927", "1336", "3800"},
        "comparison locals changed",
    )
    require(
        digest(COMPARISON) == COMPARISON_SHA, "comparison primitive definitions changed"
    )
    require(
        json.loads(COMPARISON.read_text("utf-8"))["primitives"]["1110"]["python_code"]
        == {"result": "in_2 > in_1"},
        "greater operand policy changed",
    )
    paths = {
        "IN_to_initial_OUT": w.path("1304", "5934"),
        "IN_to_arithmetic": w.path("1304", "2574"),
        "threshold": w.path("1741", "5158"),
        "OUT_read_to_bundle": w.path("1369", "1577"),
        "bundle_to_final_OUT": w.path("1565", "3813"),
    }
    for uid, bank, writer in (("5927", 2, True), ("1336", 2, False), ("3800", 2, True)):
        t = terms(g.nodes[uid])[0]
        require(
            int(t.findtext("dco/paramIdx")) == bank and g.is_input(t) == writer,
            "comparison stored-state direction changed",
        )
    outputs = {tuple(r["position_path"]): r for r in scalar_updates(g, "1555")}
    require(
        set(outputs) == {(row, 2) for row in range(11)},
        "orange destination census changed",
    )
    all_fields = g.table.fields(
        g.table.heap(g.aggregate("1555").findtext("dco/typeDesc"))
    )
    leaves = [r for r in all_fields if len(r["position_path"]) == 2]
    require(
        len(leaves) == 121
        and all(
            r["type"]
            == ("NumFloat64" if r["position_path"][1] in (5, 6) else "Boolean")
            for r in leaves
        ),
        "control carrier is no longer11x11 Bool/DBL",
    )
    rows = []
    seen_arithmetic = set()
    for uid, greater in g.nodes.items():
        if greater.get("class") != "prim" or greater.findtext("primResID") != "1110":
            continue
        args = {
            int(t.findtext("dco/parmIndex") or "0"): t.get("uid")
            for t in terms(greater)
        }
        gt_out, limit, magnitude = args[0], args[1], args[2]
        require(
            any(ports[0] == "5158" and limit in ports for _, ports in g.nets),
            "threshold no longer drives greater input1",
        )
        abs_net, abs_out, absolute = g.peer(magnitude, "prim")
        require(
            absolute.findtext("primResID") == "1054", "magnitude is not absolute value"
        )
        abs_inputs = [t.get("uid") for t in terms(absolute) if g.is_input(t)]
        require(len(abs_inputs) == 1, "absolute arity changed")
        sub_net, sub_out, subtraction = g.peer(abs_inputs[0], "prim")
        require(
            subtraction.findtext("primResID") == "1051", "difference is not subtraction"
        )
        sub_args = {
            int(t.findtext("dco/parmIndex") or "0"): t.get("uid")
            for t in terms(subtraction)
        }
        fields = {}
        for operand, name in ((2, "Consigne"), (1, "Lecture")):
            wire, source_port, owner = g.peer(sub_args[operand], "nMux")
            require(owner.get("uid") == "2568", "numeric operand source changed")
            f = g.field(source_port)
            require(
                f["type"] == "NumFloat64" and f["label_path"][-1] == name,
                "numeric operand named identity changed",
            )
            fields[name] = {"field": f, "wire": wire, "operand": sub_args[operand]}
        row = fields["Consigne"]["field"]["position_path"][0]
        require(
            fields["Consigne"]["field"]["position_path"] == [row, 5]
            and fields["Lecture"]["field"]["position_path"] == [row, 6],
            "command and reading no longer belong to same row",
        )
        target = outputs[(row, 2)]
        if row == PHASE:
            require(
                not any(gt_out in ports for _, ports in g.nets),
                "Phase numeric comparator gained a consumer",
            )
            exact_net(g, "1341", ["3056", target["terminal"]])
            require(
                g.nodes["3056"].findtext("dco/ConstValue") == "0000"
                and g.table.heap(g.nodes["3056"].findtext("dco/typeDesc")).get("Type")
                == "Boolean",
                "Phase orange False literal changed",
            )
        else:
            require(
                any(ports == [gt_out, target["terminal"]] for _, ports in g.nets),
                "comparison output does not drive matching orange field",
            )
        seen_arithmetic.update((uid, absolute.get("uid"), subtraction.get("uid")))
        rows.append(
            {
                "row": row,
                "label": target["label_path"][0],
                "Consigne": fields["Consigne"],
                "Lecture": fields["Lecture"],
                "subtract": subtraction.get("uid"),
                "absolute": absolute.get("uid"),
                "greater": uid,
                "greater_output": gt_out,
                "arithmetic_wires": [sub_net, abs_net],
                "output": target,
                "result_used": row != PHASE,
                "orange_rule": "False"
                if row == PHASE
                else "abs(Consigne-Lecture)>threshold",
            }
        )
    require(
        len(rows) == len({r["row"] for r in rows}) == 11
        and len(seen_arithmetic) == census["prim"] == 33,
        "whole comparison arithmetic not fully accounted",
    )
    return {
        "source": receipt["source"],
        "source_sha256": receipt["sha256"],
        "scope": "Final stored OUT control state, finite isolated invocation",
        "complete_source_defined_output_model_within_domain": True,
        "native_connector_or_runtime_equivalence": False,
        "rows": sorted(rows, key=lambda r: r["row"]),
        "copy_paths": paths,
        "changed_fields": 11,
        "retained_fields": 110,
        "arithmetic_nodes_accounted": 33,
        "unused_Phase_arithmetic_nodes": 3,
        "domain": (
            "11x11 carrier;99 exact Bool/22 finite float;finite threshold "
            "and differences; isolated invocation"
        ),
        "inferences": [
            "OUT is first initialized from IN; no preexisting OUT default is required.",
            "Ten orange indicators use strict abs(command-reading)>threshold. "
            "Equality is not a deviation.",
            "Phase HF/Laser orange is forced False. Its numeric comparison "
            "exists but its result is unwired.",
            "All110 other fields are retained from IN; no command, status read "
            "or device IO is produced.",
        ],
        "limits": [
            "NaN/infinity/overflow, native connector invocation and panel "
            "concurrency are outside the domain.",
            "Recorded source arithmetic is not a claim that compiled native "
            "code evaluates unused expressions.",
        ],
        "screen_used": False,
        "VI_run_or_save": False,
        "hardware_io": False,
        "production_changes": False,
        "full_Supervision_coverage": False,
    }


def project(state, threshold):
    """Pure finite-domain OUT projection; no VI/default values or command transport."""

    def finite(v):
        require(type(v) is float and math.isfinite(v), "exact finite float required")
        return v

    finite(threshold)
    require(type(state) in (tuple, list) and len(state) == 11, "11 rows required")
    output = []
    for row, values in enumerate(state):
        require(
            type(values) in (tuple, list) and len(values) == 11, "11 fields required"
        )
        for col, value in enumerate(values):
            if col in (5, 6):
                finite(value)
            else:
                require(type(value) is bool, "exact Bool required")
        difference = values[5] - values[6]
        require(math.isfinite(difference), "finite difference required")
        updated = list(values)
        updated[2] = False if row == PHASE else abs(difference) > threshold
        output.append(tuple(updated))
    return tuple(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")),
            "direct comparison report differs",
        )
    else:
        FOLDER.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({"passed": True, "output": str(OUTPUT), "sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
