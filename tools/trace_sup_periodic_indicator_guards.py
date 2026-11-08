"""Prove selected periodic beam-line indicator branches without executing a VI.

Saved Boolean literals are distinct from sequence locals and shift registers.
The pure projection below returns leaf updates only, never device commands.
"""

from __future__ import annotations

import argparse
import json

from export_sup_beam_indicator_routes import (
    FRAMES,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, SOURCE_SHA, digest, original
from trace_sup_beam_switches import terms
from validate_sup_modulator_request_gate import require

OUTPUT = (
    REPO
    / "Supervision/integration_analysis/periodic_indicator_guards_20261017/RESULT.json"
)
PRIOR = (
    REPO / "Supervision/integration_analysis/beam_indicator_join_20261016/routes.json"
)
PRIOR_SHA = "5B06ED186CF36CF9D39812B75F56D9670806F196A4808516BE471A816EAD1352"
RAW_FAULTS = {
    "61408": {
        "line": "Voie directe",
        "source_mux": "61466",
        "pairs": [
            (32, 4),
            (29, 16),
            (36, 40),
            (38, 52),
            (40, 64),
            (42, 76),
            (13, 88),
            (15, 100),
            (44, 112),
            (46, 124),
        ],
    },
    "61544": {
        "line": "Voie déviée",
        "source_mux": "61591",
        "pairs": [
            (25, 4),
            (27, 16),
            (21, 40),
            (48, 52),
            (50, 64),
            (34, 76),
            (None, 88),
            (54, 100),
            (19, 28),
        ],
    },
}
IMAGES = {
    "0__SUP__ELYSEd113.png": (
        "B2037BD96CE733B3514FF25AAA926EE116909975F2A35303DB5AB2E150B274FC"
    ),
    "0__SUP__ELYSEd115.png": (
        "F78CE936D5EB50866357751EF41D273B9C057613F1495902D10C16A8D4A3D7C9"
    ),
    "0__SUP__ELYSEd116.png": (
        "F026808117B66EC897872EE657A4978A058154340FED37FBA2821ADA15386173"
    ),
    "0__SUP__ELYSEd119.png": (
        "D4843C3D05D599732A866DD09FD96FCAD60F7EB7A95855D32A741D07863B3270"
    ),
    "0__SUP__ELYSEd120.png": (
        "D7EC98B962883BB530087802AC8DD480CC042D70BA19121EF5733157AC5FAE1C"
    ),
}


def gate(graph, uid, frame, source_uid, source_port, selector_port, net, raw):
    """A direct, single-driver literal wire; do not alias sRN frame terminals."""
    node = graph.nodes[uid]
    ranges = [
        [int(r.findtext(k)) for k in ("start", "end", "diagramIdx")]
        for r in node.findall("SelectRangeArray32/*")
    ]
    require(ranges == [[0, 0, 0], [1, 1, 1]], "Boolean case ranges changed")
    require(
        [t.get("uid") for t in terms(node)] == [selector_port]
        and graph.frame(uid) == frame,
        "indicator gate identity/frame changed",
    )
    source = graph.nodes[source_port]
    require(
        graph.owners[source_port].get("uid") == source_uid
        and graph.nodes[source_uid].get("class") == "sRN"
        and source.find("dco").get("class") == "bDConstDCO"
        and source.findtext("dco/ConstValue") == raw,
        "gate literal owner/value changed",
    )
    desc = graph.table.heap(source.findtext("dco/typeDesc"))
    require(
        desc is not None and desc.get("Type") == "Boolean", "Boolean literal required"
    )
    require(
        [t.get("uid") for t in terms(graph.nodes[net])] == [source_port, selector_port],
        "gate direct constant wire changed",
    )
    require(
        [(n, ps) for n, ps in graph.nets if source_port in ps]
        == [(net, [source_port, selector_port])],
        "gate constant gained another wire/driver",
    )
    false_frame, true_frame = node.findall("diagramList/*")
    operations = false_frame.findall("zPlaneList/*") + false_frame.findall("nodeList/*")
    require(
        all(n.get("class") == "sRN" for n in operations)
        and not false_frame.findall("signalList/*"),
        "False arm gained an operation or wire",
    )
    value = any(bytes.fromhex(raw))
    calls = [
        {"uid": n.get("uid"), "callee": n.findtext("label/textRec/text").strip('"')}
        for n in true_frame.iter()
        if n.get("class") == "iUse"
    ]
    return {
        "case_uid": uid,
        "frame": frame,
        "source_container": source_uid,
        "source_terminal": source_port,
        "selector_terminal": selector_port,
        "wire": net,
        "raw_const_value": raw,
        "saved_type": "Boolean",
        "value": value,
        "False_arm_uid": false_frame.get("uid"),
        "True_arm_uid": true_frame.get("uid"),
        "False_arm_has_effects": False,
        "calls_in_True_arm": calls,
        "calls_enabled_when_sequence_is_entered": calls if value else [],
        "source_is_shift_register_or_sequence_local": False,
    }


def verify(receipt=None, roots=None):
    if receipt is None:
        receipt, roots = original()
    require(receipt["sha256"] == SOURCE_SHA, "wrong original source version")
    table, _ = components()
    graph = SourceGraph(receipt, roots, table(roots["meta"]))
    require(digest(PRIOR) == PRIOR_SHA, "prior caller receipt changed")
    prior = json.loads(PRIOR.read_text("utf-8"))
    require(
        [d.get("uid") for d in graph.nodes["32847"].findall("diagramList/*")] == FRAMES,
        "indicator frame order changed",
    )
    require(
        graph.ancestry("32847")[:6] == ["29143", "9424", "6047", "5846", "5902", "988"]
        and graph.nodes["9424"].findall("diagramList/*")[6].get("uid") == "29143"
        and graph.nodes["988"].findall("diagramList/*")[2].get("uid") == "5902",
        "outer sequence/loop ownership changed",
    )
    orange = gate(graph, "6792", 2, "37626", "24051", "6823", "38988", "01")
    fault = gate(graph, "13076", 3, "27183", "50022", "13136", "50037", "0000")
    require(
        {c["uid"] for c in orange["calls_in_True_arm"]} == {"18812", "26357"}
        and fault["calls_in_True_arm"]
        == [{"uid": "55320", "callee": "3_SUP_en_défaut_alims.vi"}],
        "guarded helper call census changed",
    )
    all_fault_calls = [
        n.get("uid")
        for n in graph.nodes.values()
        if n.get("class") == "iUse"
        and n.findtext("label/textRec/text", "").strip('"')
        == "3_SUP_en_défaut_alims.vi"
    ]
    require(all_fault_calls == ["55320"], "main gained another fault-helper call")
    raw_routes = []
    for mux, expected in RAW_FAULTS.items():
        graph.mux_local(mux, expected["line"])
        graph.mux_local(expected["source_mux"], "C3_IN_DIO96")
        require(graph.frame(mux) == 1, "raw fault write moved out of frame1")
        pairs = []
        for term in graph.leaf_inputs(mux):
            destination = graph.field(term.get("uid"))
            require(
                destination["type"] == "Boolean"
                and destination["label_path"][-1] == "en défaut",
                "raw fault destination changed",
            )
            if term.get("uid") == "61568":
                require(
                    graph.peer("61568", "sRN")[:2] == ("49854", "49833")
                    and graph.nodes["49833"].findtext("dco/ConstValue") == "0000"
                    and graph.table.heap(
                        graph.nodes["49833"].findtext("dco/typeDesc")
                    ).get("Type")
                    == "Boolean",
                    "H5 forced-False source changed",
                )
                source = {"kind": "literal", "terminal": "49833", "value": False}
                index, net = None, "49854"
            else:
                net, port, owner = graph.peer(term.get("uid"), "nMux")
                require(
                    owner.get("uid") == expected["source_mux"],
                    "raw fault source mux changed",
                )
                field = graph.field(port)
                require(field["type"] == "Boolean", "raw fault source type changed")
                index = field["raw_index"]
                source = {"kind": "C3_IN_DIO96", "field": field}
            pairs.append((index, destination["raw_index"]))
            raw_routes.append(
                {
                    "line": expected["line"],
                    "frame": 1,
                    "net": net,
                    "source": source,
                    "destination": destination,
                    "operation": "identity" if index is not None else "constant-False",
                }
            )
        require(
            sorted(pairs, key=lambda p: p[1])
            == sorted(expected["pairs"], key=lambda p: p[1]),
            "raw fault explicit route census changed",
        )
    reserve = graph.field("61618")
    require(
        reserve["raw_index"] == 52
        and all("61618" not in ports for _, ports in graph.nets),
        "H5 reserve field gained a wire",
    )
    h2_running = next(
        r
        for r in prior["observations"]["running_routes"]
        if r["destination"]["label_path"] == ["Correcteur H2", "en marche"]
    )
    require(h2_running["source"]["raw_index"] == 39, "prior H2 running source changed")
    h2_fault = next(
        r
        for r in raw_routes
        if r["destination"]["label_path"] == ["Correcteur H2", "en défaut"]
    )
    h5_fault = next(
        r
        for r in raw_routes
        if r["line"] == "Voie déviée"
        and r["destination"]["label_path"] == ["Correcteur H5", "en défaut"]
    )
    images = []
    for name, sha in IMAGES.items():
        path = REPO / "Supervision/analysis/labview_print_hidden_frames" / name
        require(digest(path) == sha, "saved native image changed")
        images.append({"path": str(path.relative_to(REPO)), "sha256": sha})
    return {
        "source_vi_sha256": SOURCE_SHA,
        "scope": (
            "Periodic direct/deviated line indicators, "
            "selected original-source branches"
        ),
        "observations": {
            "owner_path": (
                "main frame2 / while5846 / sequence9424 frame6 / sequence32847"
            ),
            "frame_order": FRAMES,
            "orange_gate": orange,
            "computed_fault_gate": fault,
            "raw_fault_routes": raw_routes,
            "unconnected_H5_reserve": reserve,
            "only_main_fault_helper_call_uid": "55320",
            "H2_running_prior_route": h2_running,
            "H2_raw_fault_route": h2_fault,
            "H5_raw_fault_route": h5_fault,
        },
        "inferences": [
            "Conditional on reaching this sequence, "
            "both comparison helpers run in frame2.",
            "The frame3 computed-fault True arm is unreachable "
            "with the saved False literal.",
            "The previously found helper-H2-to-running miswire "
            "remains a dormant source anomaly, "
            "not an active frame3 overwrite in this pinned original.",
            "In frames0/1 H2 running is NOT C3[39], while H2 fault is C3[40].",
            "H5 fault is forced False in frame1; it is not a health acknowledgement.",
            "These two selectors are literals, not changeable shift-register values.",
        ],
        "saved_native_images": images,
        "native_observations": [
            "d113: nineteen running flags are fed through NOT nodes.",
            "d115: direct fault copies and deviated H5 False constant are visible.",
            "d116: T feeds the comparison selector; "
            "the True arm contains both helpers.",
            "d119: F feeds the fault-helper selector "
            "even though its displayed arm is True.",
            "d120: the fault-selector False arm is empty.",
        ],
        "unknown_or_requires_LabVIEW": [
            "Capture-time VI identity of the historical images is unknown. "
            "Reinspect the pinned original to close "
            "native source-version correspondence.",
            "No identity comparison with a running/deployed "
            "Supervision version was made.",
            "Startup defaults, all whole-cluster writers, property clients and races "
            "may affect retained fields; "
            "no complete per-iteration UI state is asserted.",
            "Actual cadence and blocking/failure paths of preceding frames "
            "are not established.",
            "Phase HF/Laser running/fault producer paths remain "
            "outside this selected proof.",
            "H5 physical assignment, bit polarity and real equipment faults "
            "are unqualified.",
            "No palette/color, interlock, safety permission "
            "or hardware response follows "
            "from the Boolean projection alone.",
        ],
        "prior_receipt": {"path": str(PRIOR.relative_to(REPO)), "sha256": PRIOR_SHA},
        "complete_business_logic_coverage": False,
        "fresh_native_source_qualification": False,
        "screen_used": False,
        "vi_run_or_save": False,
        "hardware_io": False,
        "network_io": False,
        "runtime_or_web_changes": False,
    }


def project_raw_fault_leaf_updates(direct_bits, deviated_bits, report):
    """Pure frame1 leaf updates; two caller-supplied snapshots, not an atomic epoch.

    Missing/non-Boolean data is rejected by this diagnostic API. That validation
    is not claimed to reproduce LabVIEW's network failure or default behavior.
    """
    result = {"Voie directe": {}, "Voie déviée": {}}
    for route in report["observations"]["raw_fault_routes"]:
        source = route["source"]
        if source["kind"] == "literal":
            value = source["value"]
        else:
            bits = direct_bits if route["line"] == "Voie directe" else deviated_bits
            index = source["field"]["raw_index"]
            if index not in bits or type(bits[index]) is not bool:
                raise ValueError(
                    f"Explicit Boolean C3 snapshot field required: {index}"
                )
            value = bits[index]
        result[route["line"]][route["destination"]["label_path"][0]] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-owned-report", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write_owned_report:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8"
        )
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")), "indicator report changed"
        )
    print(
        json.dumps(
            {
                "raw_fault_routes": len(result["observations"]["raw_fault_routes"]),
                "orange_gate": result["observations"]["orange_gate"]["value"],
                "computed_fault_gate": result["observations"]["computed_fault_gate"][
                    "value"
                ],
                "hardware_io": False,
                "report": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
