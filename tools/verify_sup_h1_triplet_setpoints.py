"""Offline, narrowly typed proof for two Supervision setpoint destinations.

An omitted nMux dco/i stays absent. A separately saved, labelled scalar type
can identify a unique cluster member without assuming an omitted index is zero.
This is a source-level proof, not fresh native LabVIEW or hardware acceptance.
"""

from __future__ import annotations

import argparse
import json

from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, SOURCE_SHA, digest, original
from trace_sup_beam_switches import Wires, terms, url_literal
from validate_sup_modulator_request_gate import require

OUTPUT = (
    REPO / "Supervision/integration_analysis/h1_triplet_source_20261017/RESULT.json"
)
PREVIOUS = (
    REPO / "Supervision/integration_analysis/beam_switch_trace_20261016/trace.json"
)
PREVIOUS_SHA = "3F99461538321F152A9134D87AC1969F5E1CAAAF9A2464574DB9443EA3C74F7F"
IMAGES = {
    "0__SUP__ELYSEd347.png": (
        "3EA87F99F64A02A248D6DC8CA7C4411E050E8683B54C85342A8F6B1F415987AC"
    ),
    "0__SUP__ELYSEd350.png": (
        "08B206C74FEE6B4773A24E4FCEDCF0FBC4A2FDB897A7921DCA7B1939B0DDA9B3"
    ),
}
CASES = (
    {
        "name": "H1",
        "source_path": ["Correcteur H1", "Consigne"],
        "source_terminal": "13325",
        "source_raw_index": 42,
        "net": "8488",
        "target_terminal": "14331",
        "target_mux": "8553",
        "target_type_ref": "TypeID(7369)",
        "label": "00 OUT00 b01 Cmd Guidage H1",
        "bank": "C6NI6703",
        "local_writer": "15529",
        "psp_writer": "12969",
    },
    {
        "name": "Triplet 1-1",
        "source_path": ["Triplet 1-1", "Consigne"],
        "source_terminal": "15225",
        "source_raw_index": 90,
        "net": "7998",
        "target_terminal": "14067",
        "target_mux": "7543",
        "target_type_ref": "TypeID(7364)",
        "label": "00 OUT00 b01 Cmd I Triplet 1-1",
        "bank": "C7NI6703",
        "local_writer": "9302",
        "psp_writer": "13145",
    },
)


def labelled_member(graph, terminal):
    """Require unique full labelled-type identity; no positional fallback."""
    node = graph.nodes[terminal]
    owner = graph.owners[terminal]
    require(owner.get("class") == "nMux", "target is not a named mux terminal")
    desc = graph.table.heap(node.findtext("dco/typeDesc"))
    require(
        desc is not None
        and desc.get("Type") == "NumFloat64"
        and bool(desc.get("Label")),
        "labelled scalar type required",
    )
    aggregate = graph.aggregate(owner.get("uid"))
    cluster = graph.table.heap(aggregate.findtext("dco/typeDesc"))
    candidates = []
    for field in graph.table.fields(cluster):
        require(field["flat_type_id"] is not None, "explicit member type required")
        member = graph.table.flat[field["flat_type_id"]]
        if graph.table.tree(member) == graph.table.tree(desc):
            candidates.append(field)
    require(len(candidates) == 1, "labelled scalar member missing or ambiguous")
    field = candidates[0]
    raw = node.findtext("dco/i")
    require(
        raw is None or int(raw) == field["flattened_index"],
        "explicit index conflicts with labelled scalar type",
    )
    return {
        "raw_index": None if raw is None else int(raw),
        "resolution": "unique-full-labelled-saved-type-match",
        "terminal_type_ref": node.findtext("dco/typeDesc"),
        "terminal_saved_type": graph.table.tree(desc),
        "matched_member": field,
        "index_was_defaulted": False,
    }


def verify(receipt=None, roots=None):
    if receipt is None:
        receipt, roots = original()
    require(receipt["sha256"] == SOURCE_SHA, "wrong original source version")
    type_table, _ = components()
    graph = SourceGraph(receipt, roots, type_table(roots["meta"]))
    wires = Wires(graph)
    require(digest(PREVIOUS) == PREVIOUS_SHA, "previous trace changed")
    previous = json.loads(PREVIOUS.read_text("utf-8"))
    # Independent consistency census, not a universal omitted-index rule.
    explicit = []
    for owner in graph.nodes.values():
        if owner.get("class") != "nMux":
            continue
        for terminal in terms(owner):
            desc = graph.table.heap(terminal.findtext("dco/typeDesc"))
            if terminal.find("dco/i") is None or desc is None:
                continue
            if desc.get("Type") != "NumFloat64":
                continue
            known = graph.field(terminal.get("uid"))
            require(
                desc.get("Label") == known["label_path"][-1]
                and known["type"] == "NumFloat64",
                "explicit scalar terminal label conflicts with cluster field",
            )
            explicit.append(terminal.get("uid"))
    require(len(explicit) == 302, "explicit scalar consistency census changed")
    routes = []
    for case in CASES:
        src, dst = case["source_terminal"], case["target_terminal"]
        source = graph.field(src)
        require(
            source["mux_uid"] == "8491"
            and source["label_path"] == case["source_path"]
            and source["raw_index"] == case["source_raw_index"],
            "setpoint source identity changed",
        )
        require(
            graph.owners[dst].get("uid") == case["target_mux"]
            and graph.is_input(graph.nodes[dst])
            and graph.nodes[dst].find("dco/i") is None,
            "destination mux/direction/raw index changed",
        )
        require(
            [t.get("uid") for t in terms(graph.nodes[case["net"]])] == [src, dst],
            "setpoint direct wire changed",
        )
        require(
            graph.ancestry(case["target_mux"])[:4]
            == ["12863", "11830", "18505", "14098"],
            "transfer True/frame1 membership changed",
        )
        member = labelled_member(graph, dst)
        require(
            member["terminal_type_ref"] == case["target_type_ref"]
            and member["matched_member"]["label_path"] == [case["label"]]
            and member["matched_member"]["position_path"] == [0],
            "expected named destination changed",
        )
        bank_input = graph.mux_local(case["target_mux"], case["bank"])
        writer = graph.nodes[case["local_writer"]]
        require(
            graph.names[case["local_writer"]] == case["bank"]
            and terms(writer)[0].findtext("objFlags") == "4096"
            and terms(writer)[0].findtext("dco/objFlags") == "1",
            "bank local writer identity/direction changed",
        )
        aggregate_output = next(
            t
            for t in terms(graph.nodes[case["target_mux"]])
            if t.get("uid") != bank_input["aggregate_terminal"]
            and t.find("dco").get("uid")
            == graph.nodes[case["target_mux"]].find("dcoAgg").get("uid")
        )
        local_write_path = wires.path(
            aggregate_output.get("uid"), terms(writer)[0].get("uid")
        )
        psp = graph.nodes[case["psp_writer"]]
        require(
            psp.get("class") == "sharedVariableDynamicWrite"
            and "7620" in graph.ancestry(case["psp_writer"]),
            "PSP writer/frame2 changed",
        )
        literal, uri = url_literal(wires, terms(psp)[0].get("uid"))
        require(
            uri == "ni.var.psp://localhost/SUPERVISION/" + case["bank"],
            "PSP destination URI changed",
        )
        refs = [
            (p, graph.owners[p])
            for p in wires.component(terms(psp)[4].get("uid"))
            if p in graph.owners and graph.owners[p].get("class") == "gRef"
        ]
        require(
            len(refs) == 1 and graph.names[refs[0][1].get("uid")] == case["bank"],
            "PSP payload bank changed",
        )
        receiver = next(
            r for r in previous["acq_receivers"] if r["bank"] == case["bank"]
        )
        runtime = next(
            r
            for r in previous["acq_runtime_writer"]
            if r["local_bank"] == receiver["local_bank"]
        )
        routes.append(
            {
                "name": case["name"],
                "source": source,
                "direct_wire": {"net": case["net"], "source": src, "destination": dst},
                "destination_mux": case["target_mux"],
                "destination": member,
                "bank_input": bank_input,
                "bank_local_write_path": local_write_path,
                "psp": {"writer": case["psp_writer"], "uri": uri, "literal": literal},
                "acquisition_receipt": receiver,
                "acquisition_writer_receipt": runtime,
                "source_level_named_route_resolved": True,
            }
        )
    images = []
    for name, expected in IMAGES.items():
        path = REPO / "Supervision/analysis/labview_print_hidden_frames" / name
        require(digest(path) == expected, "corroborating screenshot changed")
        images.append({"path": str(path.relative_to(REPO)), "sha256": expected})
    return {
        "source_vi_sha256": SOURCE_SHA,
        "scope": (
            "H1 and Triplet 1-1, direct-line event19 "
            "frame1 transfer/frame2 PSP publication"
        ),
        "method": (
            "saved source wires plus unique labelled terminal/member type identity"
        ),
        "routes": routes,
        "explicit_NumFloat64_terminal_labels_checked": len(explicit),
        "explicit_label_conflicts": 0,
        "previous_trace": {
            "path": str(PREVIOUS.relative_to(REPO)),
            "sha256": PREVIOUS_SHA,
        },
        "saved_images": images,
        "image_observation": (
            "d347 shows both named setpoint-to-OUT00 wires; "
            "d350 shows C6/C7 PSP publications"
        ),
        "image_capture_time_vi_sha256": None,
        "image_role": (
            "corroboration only; no fresh native source-version qualification"
        ),
        "fresh_native_labview_verification": False,
        "all_omitted_indices_qualified": False,
        "physical_channel_or_pin_verified": False,
        "limits": [
            "The named software destinations are resolved; raw dco/i remains null.",
            "Member position0 is derived by unique full labelled-type match, "
            "not a missing-index default.",
            "The existing Acquisition receipt preserves C6 call-terminal298 "
            "raw connector index as unknown.",
            "Local-variable writes/reads in distinct frames/loops are not "
            "one continuous wire or atomic epoch.",
            "This does not prove execution, delivery, DAQmx ABI, "
            "voltage/current calibration or hardware response.",
        ],
        "screen_used": False,
        "vi_run_or_save": False,
        "hardware_io": False,
        "network_io": False,
        "deployment": False,
    }


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
            result == json.loads(OUTPUT.read_text("utf-8")), "source report changed"
        )
    print(
        json.dumps(
            {
                "named_source_routes_resolved": 2,
                "explicit_label_checks": result[
                    "explicit_NumFloat64_terminal_labels_checked"
                ],
                "fresh_native_verification": False,
                "report": str(OUTPUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
