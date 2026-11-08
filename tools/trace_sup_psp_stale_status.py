"""Local-only PSP ingest and Voie directe stale-snapshot proof.

No native PSP failure/default policy is simulated. Diagnostic examples supply
their own values and interleavings; they are not observations of a running VI.
"""

from __future__ import annotations

import argparse
import json

from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, SOURCE_SHA, digest, original
from trace_sup_beam_switches import Wires, terms, url_literal
from trace_sup_phase_status import exact_net, scalar_updates
from validate_sup_modulator_request_gate import require

OUTPUT = REPO / "Supervision/integration_analysis/psp_stale_status_20261017/RESULT.json"
PRIOR = {
    "phase": (
        "phase_status_20261017/RESULT.json",
        "92C9C259FB4EA154E513B84F88A36101F3954E0C4E04806D828B3BF98D9B7236",
    ),
    "guards": (
        "periodic_indicator_guards_20261017/RESULT.json",
        "B34424C1F8446EC680DE2C605BF7EDBB4F3D78E36C009051112E2638189536ED",
    ),
}
READS = (
    ("11793", "C1NI6071E", 0),
    ("12558", "C2NI6071E", 0),
    ("37001", "VAM-A", 0),
    ("15567", "C3_IN_DIO96", 1),
    ("15594", "C4_IN_DIO96", 1),
    ("15620", "C5_IN_DIO96", 1),
    ("27082", "VTA", 2),
    ("27194", "VTL", 2),
    ("48340", "EPS", 2),
    ("54724", "EPC", 2),
    ("50607", "VDM-A", 3),
)
READ_FRAMES = ["11895", "18099", "26343", "50532", "29693"]
TIMEOUT_FRAMES = ["14799", "15121", "49696", "13640", "7699", "53008", "50606", "27767"]
IMAGES = {
    "0__SUP__ELYSEd62.png": (
        "27A74C40C3DCA257BA9966041996B6A376E5029A588BD9760ED623A3EC3DEBFE"
    ),
    "0__SUP__ELYSEd63.png": (
        "72B43B578CAB716E4018A99994DC0E4C367FE553509536609667A83A83C33E3F"
    ),
    "0__SUP__ELYSEd64.png": (
        "5BE0D3BC559A50DD93687866073D61567797F8C14CB96E7DF0345957C0798C1A"
    ),
    "0__SUP__ELYSEd65.png": (
        "5E09BFD13D21FF3B04AFE978BD188B0953A2FC5FBE9AB7EA2DC9D576951EF85A"
    ),
    "0__SUP__ELYSEd172.png": (
        "A83C2CE80DED714FBD4B397159AD32AEE41FEE48CDF9F386642A8E825725F76E"
    ),
}


def prior_reports():
    reports, identities = {}, {}
    for name, (relative, sha) in PRIOR.items():
        path = REPO / "Supervision/integration_analysis" / relative
        require(sha is not None and digest(path) == sha, "prior evidence changed")
        value = json.loads(path.read_text("utf-8"))
        require(value["source_vi_sha256"] == SOURCE_SHA, "prior original mismatch")
        reports[name] = value
        identities[name] = {"path": str(path.relative_to(REPO)), "sha256": sha}
    return reports, identities


def read_ports(graph, uid):
    ports = terms(graph.nodes[uid])
    require(len(ports) == 7, "shared read terminal census changed")
    expected_ids = ["0B", "03", "08", None, "0A", "02", "01"]
    require(
        [p.findtext("dco/terminal_ID") for p in ports] == expected_ids,
        "shared read terminal identities changed",
    )
    require(
        [graph.is_input(p) for p in ports]
        == [True, False, True, False, True, False, False],
        "shared read terminal directions changed",
    )
    require(
        all(
            graph.table.heap(ports[i].findtext("dco/typeDesc")).get("Label")
            == "error IO"
            for i in (2, 3)
        ),
        "shared read error cluster type changed",
    )
    timestamp = graph.table.heap(ports[6].findtext("dco/typeDesc"))
    require(
        timestamp.get("Type") == "MeasureData"
        and timestamp.get("Flavor") == "TimeStamp",
        "shared read timestamp type changed",
    )
    return dict(
        zip(
            (
                "url",
                "ref_out",
                "error_in",
                "error_out",
                "typed_in",
                "value",
                "timestamp",
            ),
            (p.get("uid") for p in ports),
            strict=True,
        )
    )


def copy_back(snapshot, changed_fields):
    """Pure RMW witness; caller supplies a snapshot, not a live current value.

    This intentionally does not merge with current UI state. It models one
    evidenced whole-cluster Bundle output, not a complete LabVIEW scheduler.
    """
    return {**snapshot, **changed_fields}


def verify(receipt=None, roots=None):
    if receipt is None:
        receipt, roots = original()
    require(receipt["sha256"] == SOURCE_SHA, "wrong original source")
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    wires = Wires(g)
    reports, identities = prior_reports()
    require(
        reports["guards"]["observations"]["orange_gate"]["value"] is True
        and reports["guards"]["observations"]["computed_fault_gate"]["value"] is False,
        "prior indicator gate result changed",
    )
    require(g.nodes["9257"].get("class") == "sequence", "ingest owner changed")
    require(
        [d.get("uid") for d in g.nodes["9257"].findall("diagramList/*")] == READ_FRAMES,
        "ingest frame order changed",
    )
    require(
        g.ancestry("9257")[:6] == ["9501", "9424", "6047", "5846", "5902", "988"]
        and g.nodes["9424"].findall("diagramList/*")[4].get("uid") == "9501"
        and g.nodes["9424"].findall("diagramList/*")[6].get("uid") == "29143",
        "ingest/indicator loop or frame placement changed",
    )
    inventory = {
        uid
        for uid, node in g.nodes.items()
        if node.get("class") == "sharedVariableDynamicRead"
        and "9257" in g.ancestry(uid)
    }
    require(inventory == {row[0] for row in READS}, "periodic reader census changed")
    reads, previous_error = [], None
    for uid, bank, ordinal in READS:
        require(
            g.ancestry(uid)[:3] == [READ_FRAMES[ordinal], "9257", "9501"],
            "read gained a guard or moved frames",
        )
        ports = read_ports(g, uid)
        literal, uri = url_literal(wires, ports["url"])
        require(uri == "ni.var.psp://localhost/SUPERVISION/" + bank, "read URL changed")
        data_net, write_port, writer = g.peer(ports["value"], "gRef")
        typed_net, read_port, reader = g.peer(ports["typed_in"], "gRef")
        require(
            g.names[writer.get("uid")] == g.names[reader.get("uid")] == bank
            and g.is_input(g.nodes[write_port])
            and not g.is_input(g.nodes[read_port]),
            "PSP bank local binding/direction changed",
        )
        require(
            g.ancestry(writer.get("uid"))[:3] == [READ_FRAMES[ordinal], "9257", "9501"],
            "PSP local result gained an error guard",
        )
        exact_net(g, data_net, (ports["value"], write_port))
        require(
            not any(ports["timestamp"] in ps for _, ps in g.nets),
            "PSP timestamp gained a freshness consumer",
        )
        path = (
            []
            if previous_error is None
            else wires.path(previous_error, ports["error_in"])
        )
        require(
            all(step["kind"] in ("wire", "sequence-local") for step in path),
            "read error chain gained a case, conversion or reset",
        )
        reads.append(
            {
                "uid": uid,
                "bank": bank,
                "frame": ordinal,
                "uri": uri,
                "uri_literal": literal,
                "ports": ports,
                "typed_input_local": reader.get("uid"),
                "typed_input_wire": typed_net,
                "result_local_writer": writer.get("uid"),
                "result_wire": data_net,
                "result_write_error_gated": False,
                "timestamp_connected": False,
                "previous_read_error_path": path,
            }
        )
        previous_error = ports["error_out"]
    c3 = next(row for row in reads if row["bank"] == "C3_IN_DIO96")
    require(c3["result_local_writer"] == "15663", "C3 result local changed")
    c3_refs = {
        uid: n
        for uid, n in g.nodes.items()
        if n.get("class") == "gRef" and n.findtext("termList/*/dco/paramIdx") == "31"
    }
    require(
        {uid for uid, n in c3_refs.items() if g.is_input(terms(n)[0])} == {"15663"},
        "C3 local writer census changed",
    )
    require(
        not any("64593" in ps for _, ps in g.nets),
        "C3 FP terminal gained a source wire",
    )

    require(
        g.nodes["13595"].get("class") == "sequence"
        and [d.get("uid") for d in g.nodes["13595"].findall("diagramList/*")]
        == TIMEOUT_FRAMES,
        "Timeout sequence identity/order changed",
    )
    rmws = []
    prior_routes = reports["phase"]["observations"]["whole_cluster_local_writers"]
    for writer, mux, reader, leaf, frame in (
        ("7430", "11207", "9745", "Consigne", "7699"),
        ("7502", "12099", "12100", "Lecture", "7699"),
        ("7649", "10168", "15775", "en marche", "32886"),
        ("61451", "61408", "61400", "en défaut", "61384"),
    ):
        reference = next(r for r in prior_routes if r["writer_uid"] == writer)
        fields = scalar_updates(g, mux)
        require(fields == reference["updated_fields"], "RMW field schema changed")
        require(
            all(f["label_path"][-1] == leaf for f in fields),
            "RMW field purpose changed",
        )
        aggregate = g.nodes[mux].find("dcoAgg").get("uid")
        input_, output = (
            next(
                p
                for p in terms(g.nodes[mux])
                if p.find("dco").get("uid") == aggregate and g.is_input(p) == direction
            )
            for direction in (True, False)
        )
        in_net, in_peer, r = g.peer(input_.get("uid"), "gRef")
        out_net, out_peer, w = g.peer(output.get("uid"), "gRef")
        require(
            r.get("uid") == reader
            and w.get("uid") == writer
            and g.names[reader] == g.names[writer] == "Voie directe"
            and not g.is_input(g.nodes[in_peer])
            and g.is_input(g.nodes[out_peer]),
            "RMW local source/destination changed",
        )
        require(
            g.ancestry(reader)[0]
            == g.ancestry(writer)[0]
            == g.ancestry(mux)[0]
            == frame,
            "RMW gained a nested guard/barrier",
        )
        exact_net(g, in_net, (in_peer, input_.get("uid")))
        exact_net(g, out_net, (output.get("uid"), out_peer))
        rmws.append(
            {
                "writer": writer,
                "bundle": mux,
                "reader": reader,
                "frame_uid": frame,
                "changed_leaf": leaf,
                "changed_indices": [f["raw_index"] for f in fields],
                "read_wire": in_net,
                "write_wire": out_net,
                "whole_cluster_output": True,
                "retained_fields_source": (
                    "earlier source local snapshot, not latest UI at write time"
                ),
                "loop": "6017" if frame == "7699" else "5846",
            }
        )
    require(
        g.ancestry("7699")[:6] == ["13595", "5917", "5909", "6068", "6017", "5902"],
        "numeric refresh is not an unconditional Timeout sequence frame",
    )
    for loop in ("6017", "5846"):
        require(
            g.nodes[loop].get("class") == "whileLoop"
            and g.ancestry(loop)[0] == "5902"
            and not terms(g.nodes[loop])
            and not g.nodes[loop].findall("tunnelList/*"),
            "independent loop boundary gained a wire/tunnel",
        )
    bank_snapshots = []
    for mux, expected_reader, frame in (("15792", "14210", 0), ("61466", "61458", 1)):
        binding = g.mux_local(mux, "C3_IN_DIO96")
        require(
            binding["reference_uid"] == expected_reader and g.frame(mux) == frame,
            "periodic C3 snapshot reader changed",
        )
        require(
            not g.is_input(g.nodes[binding["reference_terminal"]]),
            "C3 snapshot direction changed",
        )
        bank_snapshots.append({"frame": frame, **binding})

    images = []
    for name, sha in IMAGES.items():
        path = REPO / "Supervision/analysis/labview_print_hidden_frames" / name
        require(digest(path) == sha, "saved PSP/copy-back screenshot changed")
        images.append({"path": str(path.relative_to(REPO)), "sha256": sha})
    return {
        "source_vi_sha256": SOURCE_SHA,
        "prior_evidence": identities,
        "observations": {
            "periodic_PSP_read_chain": reads,
            "C3_local_writer_census": ["15663"],
            "C3_status_snapshots": bank_snapshots,
            "ingest_outer_frame": 4,
            "indicator_outer_frame": 6,
            "Voie_directe_RMW_writers": rmws,
            "numeric_RMWs_in_same_frame_are_not_ordered_by_sequence": True,
            "numeric_frame_is_sequence_not_True_case": {
                "sequence": "13595",
                "ordinal": 4,
                "diagram": "7699",
            },
            "comparison_writer": reports["phase"]["observations"][
                "comparison_whole_cluster_writer"
            ],
            "row_property_writer": reports["phase"]["observations"]["row_Value_write"],
            "computed_fault_writer_enabled": False,
            "comparison_writer_enabled": True,
            "C3_internal_writer_and_status_readers_share_one_ordered_loop": True,
        },
        "inferences": [
            "All eleven periodic read results are wired directly to local writers. "
            "Their TimeStamp outputs are unused. The audited path has no per-bank "
            "age/quality policy that invalidates direct-line lamps.",
            "C3 receives the preceding C1/C2/VAM-A error chain without a per-bank "
            "reset. Native read behavior on an incoming/outgoing error "
            "is not inferred.",
            "Once reads complete and execution reaches sequence32847, running and "
            "raw-fault updates are not conditioned on PSP success. The main-loop "
            "sequence orders frames4 then6, but not the independent Timeout loop.",
            "If a native read supplies old bits, periodic raw indicators recompute "
            "from those old bits; re-execution alone does not establish freshness.",
            "If execution stalls before the next writer, the audited writers do "
            "not independently expire the already displayed statuses.",
            "Timeout Consigne/Lecture writers echo all running/fault flags from "
            "their own earlier whole-cluster read. A write after another loop's "
            "status refresh can restore older flags. This is a source-supported "
            "interleaving, not an observed native race or measured probability.",
            "A stale numeric writer can replace a newer numeric field too: "
            "Consigne and Lecture are separate whole-cluster RMWs in the same "
            "frame, with no direct ordering edge between them.",
            "The comparison helper and selected-row Value writer likewise retain "
            "running/fault snapshots; neither is an independent fresh status source.",
            "The comparison helper follows raw updates in the same periodic loop; "
            "its copy-back is not evidence of a race with that loop's next raw pass.",
            "A following successful periodic pass can repair the ten raw running "
            "and ten raw fault fields, unless another older copy-back follows it. "
            "Phase running/fault have no such repair producer in the audited paths.",
            "C3 has one diagram local writer, in this same periodic loop before "
            "both status frames. Separate running/fault C3 reads alone do not "
            "prove different C3 generations within a pass; no intervening Main "
            "diagram write was found. External UI/VI Server writes are not excluded.",
            "A completed display pass is nevertheless not an atomic multi-bank "
            "equipment snapshot: eleven PSP reads are sequential, running/fault "
            "are separate UI writes, and Timeout changes Voie directe independently.",
        ],
        "requires_native_evidence_or_remains_unknown": [
            "PSP returned values, caching, output timestamp and blocking behavior "
            "on a failed read or pre-existing input error. No zero, retention, "
            "cached-success or skip-on-error default is assumed.",
            "Actual scheduling, observed race frequency, recovery latency and "
            "status colors on deployed systems; neither timing nor live values "
            "were measured.",
            "Property/Variant errors and external UI/VI Server writers remain "
            "unqualified; the previous seven-arm successful-read proof is reused.",
            "Historical screenshots have no capture-time VI hash. They corroborate "
            "displayed fragments, not identity of a deployed VI.",
            "End-to-end local/remote error journaling, its propagation across "
            "other procedures and every loop-exit path are outside this bounded trace.",
        ],
        "saved_screenshots": images,
        "native_PSP_failure_policy_verified": False,
        "observed_live_race": False,
        "complete_Supervision_coverage": False,
        "screen_used": False,
        "vi_run_or_save": False,
        "hardware_io": False,
        "network_io": False,
        "production_changes": False,
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
            result == json.loads(OUTPUT.read_text("utf-8")), "PSP/stale report changed"
        )
    print(
        json.dumps(
            {
                "periodic_PSP_reads": 11,
                "timestamp_consumers": 0,
                "numeric_whole_cluster_writers": 2,
                "hardware_io": False,
                "report": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
