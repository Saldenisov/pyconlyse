"""Reproduce bounded indicator joins in the pinned original Supervision VI.

Static evidence only: no VI loading, generated controller, network or device IO.
Missing saved field/connector indices remain unknown, not implicit zero.
The current LVKit type-table component is used without importing its runtime.
"""

from __future__ import annotations

import argparse
import importlib.util
import json

from export_sup_live_display_map import REPO, SOURCE_SHA, digest, original
from validate_sup_modulator_request_gate import require

OUTPUT = (
    REPO / "Supervision/integration_analysis/beam_indicator_join_20261016/routes.json"
)
KIT = (
    REPO
    / "Supervision/integration_analysis/orchestrator"
    / "full_coverage_orchestration_20261009/lvkit"
)
TYPE_COMPONENT = KIT / "src/lvkit/parser/saved_types.py"
BOOLEAN_COMPONENT = KIT / "src/lvkit/data/primitives/boolean.json"
TYPE_SHA = "4CEE5ACC195A43B9C3519D031DBCBB18E585FA988EB1D204C9D7BD3BCC1D54FD"
BOOLEAN_SHA = "6D410E1C3C6200CE9CBD5B33BB79D764B98BD9A47753B749608031A7287D04B5"
BASELINE = REPO / "Supervision/integration_analysis/CURRENT_EVIDENCE.json"
BASELINE_SHA = "D1F3379615EA71304B975E33051762561C1FA54DC2724061C84C3D8D0AF7AD7C"
FRAMES = ["32886", "61384", "37609", "12639", "47435", "25807", "47563", "84525"]
RUNNING = {
    "10168": {
        "local": "Voie directe",
        "source_mux": "15792",
        "pairs": [
            (31, 2),
            (28, 14),
            (35, 38),
            (37, 50),
            (39, 62),
            (41, 74),
            (12, 86),
            (14, 98),
            (43, 110),
            (45, 122),
        ],
    },
    "6785": {
        "local": "Voie déviée",
        "source_mux": "23807",
        "pairs": [
            (24, 2),
            (26, 14),
            (18, 26),
            (20, 38),
            (47, 50),
            (49, 62),
            (33, 74),
            (51, 86),
            (53, 98),
        ],
    },
}
FAULT = {
    "70571": {
        "local": "Voie directe",
        "source_mux": "47142",
        "call_port": "55332",
        "pairs": [
            (None, 4),
            (1, 16),
            (2, 40),
            (3, 52),
            (4, 62),
            (5, 76),
            (6, 88),
            (7, 100),
            (8, 112),
            (9, 124),
        ],
    },
    "70632": {
        "local": "Voie déviée",
        "source_mux": "47971",
        "call_port": "55329",
        "pairs": [
            (None, 4),
            (1, 16),
            (2, 40),
            (3, 52),
            (4, 64),
            (5, 76),
            (6, 88),
            (7, 100),
            (8, 28),
        ],
    },
}


def components():
    require(digest(TYPE_COMPONENT) == TYPE_SHA, "current LVKit type component changed")
    require(
        digest(BOOLEAN_COMPONENT) == BOOLEAN_SHA,
        "current LVKit Boolean metadata changed",
    )
    spec = importlib.util.spec_from_file_location(
        "sup_indicator_saved_types", TYPE_COMPONENT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    primitive = json.loads(BOOLEAN_COMPONENT.read_text("utf-8"))["primitives"]["1064"]
    require(primitive["name"] == "Not", "LVKit primitive 1064 mapping changed")
    return module.SavedTypeTable, primitive


class SourceGraph:
    def __init__(self, receipt, roots, table):
        self.roots = roots
        self.table = table
        self.nodes = {n.get("uid"): n for n in roots["bd"].iter() if n.get("class")}
        self.parents = {
            child: parent for parent in roots["bd"].iter() for child in parent
        }
        self.names = {row["uid"]: row["name"] for row in receipt["locals"]}
        self.owners = {
            term.get("uid"): node
            for node in self.nodes.values()
            if node.get("class") not in ("term", "diag", "signal", "selTun", "nmxDCO")
            for term in node.findall("termList/*")
        }
        self.nets = [
            (node.get("uid"), [t.get("uid") for t in node.findall("termList/*")])
            for node in self.nodes.values()
            if node.get("class") == "signal"
        ]

    def connected(self, port, cls):
        return [
            (net, peer, self.owners[peer])
            for net, ports in self.nets
            if port in ports
            for peer in ports
            if peer != port
            and peer in self.owners
            and self.owners[peer].get("class") == cls
        ]

    def peer(self, port, cls):
        peers = self.connected(port, cls)
        require(len(peers) == 1, f"ambiguous/missing {cls} peer for terminal {port}")
        return peers[0]

    def aggregate(self, mux):
        node = self.nodes[mux]
        agg = node.find("dcoAgg").get("uid")
        return next(
            t for t in node.findall("termList/*") if t.find("dco").get("uid") == agg
        )

    def mux_local(self, mux, expected):
        agg = self.aggregate(mux)
        net, port, ref = self.peer(agg.get("uid"), "gRef")
        require(
            self.names.get(ref.get("uid")) == expected,
            f"mux local identity changed: {mux}",
        )
        return {
            "name": expected,
            "reference_uid": ref.get("uid"),
            "reference_terminal": port,
            "aggregate_terminal": agg.get("uid"),
            "net": net,
        }

    def field(self, port):
        node = self.owners[port]
        require(node.get("class") == "nMux", "field owner is not nMux")
        term = self.nodes[port]
        raw = term.findtext("dco/i")
        result = {
            "mux_uid": node.get("uid"),
            "terminal": port,
            "raw_index": None if raw is None else int(raw),
            "label_path": None,
            "type": None,
            "addressing": "omitted-index-unqualified"
            if raw is None
            else "explicit-index",
        }
        if raw is not None:
            aggregate = self.aggregate(node.get("uid"))
            fields = self.table.fields(
                self.table.heap(aggregate.findtext("dco/typeDesc"))
            )
            index = int(raw)
            require(0 <= index < len(fields), "explicit named field index out of range")
            result.update(
                {k: fields[index][k] for k in ("label_path", "type", "position_path")}
            )
        return result

    def leaf_inputs(self, mux):
        # nmxDCO reference inputs have no typeDesc and are not scalar updates.
        return [
            t
            for t in self.nodes[mux].findall("termList/*")
            if t.find("dco/i") is not None and self.is_input(t)
        ]

    @staticmethod
    def is_input(term):
        return bool(int(term.findtext("objFlags") or "0") & 0x8000)

    def ancestry(self, uid):
        current, result = self.nodes[uid], []
        while current in self.parents:
            current = self.parents[current]
            if current.get("uid") is not None:
                result.append(current.get("uid"))
        return result

    def frame(self, uid):
        ancestor_uids = self.ancestry(uid)
        frames = [i for i, diagram in enumerate(FRAMES) if diagram in ancestor_uids]
        require(
            len(frames) == 1 and "32847" in ancestor_uids, "frame membership changed"
        )
        return frames[0]

    def guard(self, uid, expected_selector, expected_net, expected_source):
        node = self.nodes[uid]
        ranges = [
            [int(r.findtext(k)) for k in ("start", "end", "diagramIdx")]
            for r in node.findall("SelectRangeArray32/*")
        ]
        require(ranges == [[0, 0, 0], [1, 1, 1]], "Boolean guard case ranges changed")
        diagrams = [d.get("uid") for d in node.findall("diagramList/*")]
        ports = node.findall("termList/*")
        require(
            len(ports) == 1 and ports[0].get("uid") == expected_selector,
            "Boolean selector changed",
        )
        net, port, source = self.peer(expected_selector, "sRN")
        require(
            (net, source.get("uid")) == (expected_net, expected_source),
            "guard shift-register source changed",
        )
        return {
            "case_uid": uid,
            "ranges": ranges,
            "true_diagram": diagrams[1],
            "selector_terminal": expected_selector,
            "selector_net": net,
            "shift_register_uid": expected_source,
            "shift_register_terminal": port,
            "runtime_selector_value": None,
        }

    def call_local(self, uid, port, expected_index, expected_local):
        node = self.nodes[uid]
        term = next(t for t in node.findall("termList/*") if t.get("uid") == port)
        raw = term.findtext("dco/paramIdx")
        require(
            raw == (None if expected_index is None else str(expected_index)),
            "call raw connector index changed",
        )
        net, peer, ref = self.peer(port, "gRef")
        require(
            self.names.get(ref.get("uid")) == expected_local,
            "call local source changed",
        )
        return {
            "call_uid": uid,
            "call_terminal": port,
            "raw_param_index": expected_index,
            "direction": "in" if self.is_input(term) else "out",
            "net": net,
            "local": expected_local,
            "reference_uid": ref.get("uid"),
            "reference_terminal": peer,
        }


def build_routes(receipt=None, roots=None):
    if roots is None:
        receipt, roots = original()
    saved_types, primitive = components()
    require(
        digest(BASELINE) == BASELINE_SHA,
        "published evidence baseline changed; rebase audit",
    )
    graph = SourceGraph(receipt, roots, saved_types(roots["meta"]))
    require(
        [d.get("uid") for d in graph.nodes["32847"].findall("diagramList/*")] == FRAMES,
        "monitor sequence frame order changed",
    )
    running = []
    for writer, expected in RUNNING.items():
        graph.mux_local(writer, expected["local"])
        graph.mux_local(expected["source_mux"], "C3_IN_DIO96")
        pairs = []
        for target in graph.leaf_inputs(writer):
            out_net, out_port, prim = graph.peer(target.get("uid"), "prim")
            require(prim.findtext("primResID") == "1064", "running primitive changed")
            require(
                not graph.is_input(graph.nodes[out_port]),
                "running primitive output changed",
            )
            inputs = [t for t in prim.findall("termList/*") if graph.is_input(t)]
            require(len(inputs) == 1, "running NOT arity changed")
            in_net, source_port, source_mux = graph.peer(inputs[0].get("uid"), "nMux")
            require(
                source_mux.get("uid") == expected["source_mux"],
                "running bank mux changed",
            )
            source, destination = (
                graph.field(source_port),
                graph.field(target.get("uid")),
            )
            require(
                source["type"] == destination["type"] == "Boolean",
                "running type changed",
            )
            require(
                destination["label_path"][-1] == "en marche",
                "running target lamp changed",
            )
            require(
                graph.frame(writer) == graph.frame(prim.get("uid")) == 0,
                "running update frame changed",
            )
            pairs.append((source["raw_index"], destination["raw_index"]))
            running.append(
                {
                    "local": expected["local"],
                    "frame": 0,
                    "source_bank": "C3_IN_DIO96",
                    "source": source,
                    "primitive_uid": prim.get("uid"),
                    "primitive_res_id": "1064",
                    "input_net": in_net,
                    "output_net": out_net,
                    "destination": destination,
                    "inference": (
                        "destination = not source, conditional on current "
                        "LVKit 1064 mapping"
                    ),
                }
            )
        require(
            sorted(pairs) == sorted(expected["pairs"]),
            "running explicit field route changed",
        )

    fault_guard = graph.guard("13076", "13136", "50037", "27183")
    orange_guard = graph.guard("6792", "6823", "38988", "37626")
    fault_call = graph.nodes["55320"]
    require(
        fault_call.findtext("label/textRec/text").strip('"')
        == "3_SUP_en_défaut_alims.vi",
        "fault helper callee changed",
    )
    require(
        fault_guard["true_diagram"] in graph.ancestry("55320")
        and graph.frame("55320") == 3,
        "fault helper branch/frame changed",
    )
    fault_inputs = [
        graph.call_local("55320", port, index, name)
        for port, index, name in (
            ("55335", 2, "C3_OUT_DIO96"),
            ("55338", 3, "C3_IN_DIO96"),
        )
    ]
    faults, fault_outputs = [], []
    for writer, expected in FAULT.items():
        graph.mux_local(writer, expected["local"])
        agg = graph.aggregate(expected["source_mux"])
        net, call_port, call = graph.peer(agg.get("uid"), "iUse")
        require(
            call.get("uid") == "55320" and call_port == expected["call_port"],
            "fault helper aggregate route changed",
        )
        raw_index = graph.nodes[call_port].findtext("dco/paramIdx")
        require(
            raw_index == ("1" if writer == "70571" else None),
            "fault output connector changed",
        )
        fault_outputs.append(
            {
                "call_terminal": call_port,
                "raw_param_index": raw_index,
                "net": net,
                "aggregate_terminal": agg.get("uid"),
                "source_mux": expected["source_mux"],
            }
        )
        pairs = []
        for target in graph.leaf_inputs(writer):
            net, source_port, source_mux = graph.peer(target.get("uid"), "nMux")
            require(
                source_mux.get("uid") == expected["source_mux"],
                "fault source mux changed",
            )
            source, destination = (
                graph.field(source_port),
                graph.field(target.get("uid")),
            )
            require(
                fault_guard["true_diagram"] in graph.ancestry(writer)
                and graph.frame(writer) == 3,
                "fault update branch/frame changed",
            )
            pairs.append((source["raw_index"], destination["raw_index"]))
            faults.append(
                {
                    "local": expected["local"],
                    "frame": 3,
                    "net": net,
                    "source": source,
                    "destination": destination,
                }
            )
        # Sort by destination because two omitted source indices must stay None.
        require(
            sorted(pairs, key=lambda p: p[1])
            == sorted(expected["pairs"], key=lambda p: p[1]),
            "fault explicit field route changed",
        )
    h2 = next(r for r in faults if r["destination"]["terminal"] == "70594")
    require(
        h2["source"]["terminal"] == "55850"
        and h2["net"] == "40012"
        and h2["source"]["label_path"] == ["H2"]
        and h2["destination"]["label_path"] == ["Correcteur H2", "en marche"],
        "H2 original cross-lamp route changed",
    )
    earlier_fault = graph.field("61432")
    require(
        earlier_fault["label_path"] == ["Correcteur H2", "en défaut"]
        and graph.frame("61408") == 1,
        "earlier H2 fault writer changed",
    )
    graph.mux_local("61408", "Voie directe")
    earlier_net, earlier_port, earlier_mux = graph.peer("61432", "nMux")

    comparisons = []
    for uid, name, ports, label in (
        (
            "18812",
            "2_SUP_Ecart_lu_ecr_VDirecte.vi",
            ("18821", "18824", "18827"),
            "Voie directe",
        ),
        (
            "26357",
            "2_SUP_Ecart_lu_ecr_VDéviée.vi",
            ("26368", "26372", "26376"),
            "Voie déviée",
        ),
    ):
        node = graph.nodes[uid]
        require(
            node.findtext("label/textRec/text").strip('"') == name,
            "comparison callee changed",
        )
        require(
            orange_guard["true_diagram"] in graph.ancestry(uid)
            and graph.frame(uid) == 2,
            "comparison branch/frame changed",
        )
        io = [
            graph.call_local(uid, port, index, local)
            for port, index, local in (
                (ports[0], None, label),
                (ports[1], 1, label),
                (ports[2], 2, "Ecart lu / écrit "),
            )
        ]
        require(
            [p["direction"] for p in io] == ["out", "in", "in"],
            "comparison direction changed",
        )
        comparisons.append({"call_uid": uid, "callee": name, "frame": 2, "io": io})
    thresholds = [r["io"][2] for r in comparisons]
    require(
        all(t["net"] == "16526" and t["reference_uid"] == "16157" for t in thresholds),
        "shared comparison threshold route changed",
    )

    # Independent FPHb field ordering corroborates the H2 lamp label, not the
    # raw saved-version nMux addressing grammar or a native execution trace.
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    row = fp["39127"]
    labels = [
        fp[d.get("uid")].findtext("partsList/*/textRec/text").strip('"')
        for d in row.findall("ddoList/*")
    ]
    require(
        labels[1:4] == ["en marche", "orange", "en défaut"],
        "native H2 lamp order changed",
    )
    return {
        "source_vi_sha256": SOURCE_SHA,
        "source": receipt["source"],
        "xml_inputs": receipt["xml"],
        "lvkit_components": [
            {"path": str(TYPE_COMPONENT), "sha256": TYPE_SHA},
            {"path": str(BOOLEAN_COMPONENT), "sha256": BOOLEAN_SHA},
        ],
        "lvkit_use": (
            "isolated saved-type component and Boolean metadata; "
            "no full parser/codegen execution"
        ),
        "published_baseline_sha256": BASELINE_SHA,
        "scope": (
            "caller wire/type/sequence joins only, not complete indicator "
            "or button equivalence"
        ),
        "observations": {
            "sequence_uid": "32847",
            "ordered_diagrams": FRAMES,
            "running_routes": running,
            "running_route_count": len(running),
            "fault_helper": {
                "call_uid": "55320",
                "inputs": fault_inputs,
                "outputs": fault_outputs,
                "guard": fault_guard,
            },
            "fault_routes": faults,
            "fault_route_count": len(faults),
            "explicit_fault_source_indices": sum(
                r["source"]["raw_index"] is not None for r in faults
            ),
            "comparison_calls": comparisons,
            "comparison_guard": orange_guard,
            "h2_cross_lamp": h2,
            "earlier_h2_fault": {
                "frame": 1,
                "destination": earlier_fault,
                "net": earlier_net,
                "source_terminal": earlier_port,
                "source_mux": earlier_mux.get("uid"),
            },
            "h2_native_panel": {
                "row_uid": "39127",
                "lamp_uids": ["39166", "39159", "39152"],
                "lamp_labels": labels[1:4],
            },
            "primitive_1064_name_in_current_lvkit": primitive["name"],
        },
        "inferences": [
            "Nineteen frame-0 running updates invert explicit C3_IN_DIO96 leaves "
            "if LVKit primitive 1064=Not is accepted.",
            "A stateless one-bank lamp mapping would omit later gated writers "
            "and Supervision-local threshold/state.",
            "H2 helper output targets running rather than fault in frame 3; "
            "this is a source-level cross-lamp anomaly, "
            "not measured hardware behaviour.",
            "The two comparison callers share one local threshold, "
            "not an established constant live threshold.",
        ],
        "unknowns": [
            "No native screenshot pinpoints the newly joined H2 wire; "
            "FPHb/BDHb/type-table joins are static only.",
            "Saved-version omitted nMux/connector index defaults remain unqualified; "
            "no absent index becomes zero.",
            "Helper original whole-VI/native ABI equivalence is not promoted "
            "by these caller joins.",
            "Frame-0 Phase HF / Laser lamp is not updated by writer 10168; "
            "its complete producer path remains open.",
            "C3 index51 typed label contains Reserve text whereas target is H5; "
            "physical assignment is not established here.",
            "Guard shift-register runtime values, other writers, iteration timing "
            "and race/flash behaviour remain open.",
            "M/A, X1/X10 and button command/latch behaviour are not closed "
            "by this indicator audit.",
            "Runtime threshold and local UI states are not reconstructed "
            "from saved defaults or the 27 ACQ banks.",
        ],
        "hardware_writes": False,
        "network_io": False,
        "vi_run_or_save": False,
        "web_deployment": False,
        "commands_enabled": False,
        "new_whole_vi_models": 0,
        "native_equivalence_claims": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Compare saved report without writing"
    )
    args = parser.parse_args()
    result = build_routes()
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")),
            "saved indicator report differs",
        )
    else:
        require(
            not OUTPUT.exists(),
            "report already exists; review changes before replacement",
        )
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8"
        )
    print(
        json.dumps(
            {
                "check": args.check,
                "running_routes": 19,
                "fault_routes": 19,
                "omitted_fault_source_indices": 2,
                "output": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
