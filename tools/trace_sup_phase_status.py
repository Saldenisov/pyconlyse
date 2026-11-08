"""Static Phase HF/Laser flag provenance and copy-back writers; no VI loading.

Retaining an input value is not a hardware status measurement. Missing saved
defaults and native Controls[]/connector semantics remain explicitly unknown.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET

from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, SOURCE_SHA, digest, original
from trace_sup_beam_switches import Wires, alias, terms
from validate_sup_modulator_request_gate import require

OUTPUT = REPO / "Supervision/integration_analysis/phase_status_20261017/RESULT.json"
HELPER_RECEIPT = (
    REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/04.json"
)
HELPER_RECEIPT_SHA = "4BC73489268882E3DC1DB68BA62553684C6D1D38D082234F1FD3AEDF7165473A"
HELPER_SHA = "5CD315417FDFC2FA5115D0C26D3450825E5EF54441A9C43FC6D0F6C0A9E45333"
PHASE = "Phase HF / Laser"
FLAGS = {"en marche", "en défaut"}
LOCAL_WRITERS = {
    "7430": ("11207", "Timeout command/setpoint refresh"),
    "7502": ("12099", "Timeout measured-value refresh"),
    "7649": ("10168", "periodic sequence32847 frame0 running flags"),
    "61451": ("61408", "periodic sequence32847 frame1 raw fault flags"),
    "70618": ("70571", "periodic frame3 computed faults, saved gate False"),
}
BRANCH_NETS = (
    (0, "8464", "8509", "8503"),
    (1, "8515", "8560", "8554"),
    (16, "8566", "8611", "8605"),
    (128, "8617", "9074", "9068"),
    (256, "6002", "17414", "17408"),
    (512, "7494", "10182", "10172"),
    (1024, "7655", "11559", "11553"),
)
IMAGES = {
    "analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_19_full.png": (
        "283FDDED972B1768313CF83A688D47DC06175C88E2F19F4345711EE5992BFC93"
    ),
    "analysis/labview_print_hidden_frames/2__SUP__Ecart__lu__ecr__VDirected1.png": (
        "76E01DB8163BCBBFC1E683EBF053D1BFB00A6793BA19C61B59DDB4D10800A840"
    ),
    "analysis/labview_print_hidden_frames/2__SUP__Ecart__lu__ecr__VDirected2.png": (
        "A620777CB1503DF27E090A983F2903B809B48B7A169477F343D00C22836B6155"
    ),
}


def helper_sources():
    require(digest(HELPER_RECEIPT) == HELPER_RECEIPT_SHA, "helper receipt changed")
    receipt = json.loads(HELPER_RECEIPT.read_text("utf-8"))
    require(
        receipt["sha256"] == HELPER_SHA and digest(receipt["source"]) == HELPER_SHA,
        "original comparison helper changed",
    )
    roots = {}
    for key, entry in zip(("bd", "fp", "meta"), receipt["xml"], strict=True):
        require(digest(entry["path"]) == entry["sha256"], "helper XML changed")
        roots[key] = ET.parse(entry["path"]).getroot()
    return receipt, roots


def exact_net(graph, uid, ports):
    require(
        [t.get("uid") for t in terms(graph.nodes[uid])] == list(ports),
        f"source wire changed: {uid}",
    )


def scalar_updates(graph, mux):
    node = graph.nodes[mux]
    members = {d.get("uid") for d in node.findall("dcoList/*")}
    selected = [t for t in terms(node) if t.find("dco").get("uid") in members]
    require(len(selected) == len(members), "named field terminal census changed")
    require(
        all(t.find("dco/i") is not None for t in selected),
        "new omitted field index in audited writer",
    )
    result = [graph.field(t.get("uid")) for t in selected]
    require(all(graph.is_input(t) for t in selected), "writer field direction changed")
    return result


def fp_descendants(fp, uid):
    found, pending = {uid}, [uid]
    while pending:
        for child in fp[pending.pop()].findall("ddoList/*"):
            peer = child.get("uid")
            if peer not in found:
                found.add(peer)
                pending.append(peer)
    return found


def verify(receipt=None, roots=None, helper=None):
    if receipt is None:
        receipt, roots = original()
    require(receipt["sha256"] == SOURCE_SHA, "wrong main source version")
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    # Census by raw paramIdx independently of the decoded local-name ledger.
    direct_refs = {
        uid: node
        for uid, node in g.nodes.items()
        if node.get("class") == "gRef"
        and node.findtext("termList/*/dco/paramIdx") == "45"
    }
    ledger = {
        r["uid"]: r for r in receipt["graph_locals"] if r["name"] == "Voie directe"
    }
    require(
        set(direct_refs) == set(ledger) and len(ledger) == 15,
        "direct local census changed",
    )
    writers = {uid for uid, row in ledger.items() if row["write"]}
    require(
        writers == set(LOCAL_WRITERS) | {"16437"}, "direct local writer census changed"
    )
    local_routes = []
    for writer, (mux, purpose) in LOCAL_WRITERS.items():
        port = terms(direct_refs[writer])[0]
        require(g.is_input(port), "root local write direction changed")
        net, _, owner = g.peer(port.get("uid"), "nMux")
        require(owner.get("uid") == mux, "local writer mux changed")
        # dcoAgg's typed terminal is the bundle OUTPUT in these five nodes.
        # Its second, referenced terminal is the aggregate INPUT. Do not call
        # the first connected local a read merely because it has the typeDesc.
        aggregate_id = g.nodes[mux].find("dcoAgg").get("uid")
        aggregate_input = next(
            t
            for t in terms(g.nodes[mux])
            if t.find("dco").get("uid") == aggregate_id and g.is_input(t)
        )
        in_net, in_port, reader = g.peer(aggregate_input.get("uid"), "gRef")
        require(
            reader.get("uid") in ledger
            and not ledger[reader.get("uid")]["write"]
            and not g.is_input(g.nodes[in_port]),
            "bundle source local is not a read",
        )
        incoming = {
            "local_uid": reader.get("uid"),
            "terminal": in_port,
            "wire": in_net,
            "bundle_input": aggregate_input.get("uid"),
        }
        updates = scalar_updates(g, mux)
        require(
            not any(
                f["label_path"] == [PHASE]
                or (f["label_path"][0] == PHASE and f["label_path"][-1] in FLAGS)
                for f in updates
            ),
            "local writer now changes Phase flags or whole Phase row",
        )
        local_routes.append(
            {
                "writer_uid": writer,
                "purpose": purpose,
                "mux_uid": mux,
                "source_snapshot": incoming,
                "output_wire": net,
                "updated_fields": updates,
                "Phase_flags": "retained from source snapshot",
                "inactive_with_saved_literal": writer == "70618",
            }
        )
    require(
        sum(len(r["updated_fields"]) for r in local_routes) == 52,
        "whole-cluster scalar update count changed",
    )
    exact_net(g, "13546", ("18821", "16446"))
    exact_net(g, "14957", ("16461", "18824"))
    require(
        g.names["16457"] == g.names["16437"] == "Voie directe",
        "comparison caller cluster binding changed",
    )
    # The control terminal itself is unwired; it is not another diagram sink.
    require(
        g.nodes["7644"].get("class") == "fPTerm"
        and all("7644" not in ports for _, ports in g.nets),
        "control terminal gained a wire",
    )

    # Explicit reference targets, including every nested row/leaf.
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    ids = fp_descendants(fp, "7618")
    require(len(ids) == 133 and "20222" in ids, "direct FP descendant census changed")
    require(
        fp["7618"].findall("ddoList/*")[2].get("uid") == "20222",
        "Phase FP row ordering changed",
    )
    phase_fields = [
        f
        for f in g.table.fields(g.table.heap(fp["7642"].findtext("typeDesc")))
        if f["label_path"][0] == PHASE and f["label_path"][-1] in FLAGS
    ]
    require(
        [(f["flattened_index"], f["label_path"][-1], f["type"]) for f in phase_fields]
        == [(26, "en marche", "Boolean"), (28, "en défaut", "Boolean")],
        "Phase root flag schema changed",
    )
    phase_leaves = [d.get("uid") for d in fp["20222"].findall("ddoList/*")]
    require(
        phase_leaves[1:4] == ["20261", "20254", "20247"], "Phase lamp ordering changed"
    )
    for uid, label in (("20261", "en marche"), ("20247", "en défaut")):
        require(
            fp[uid].findtext("partsList/*/textRec/text").strip('"') == label,
            "Phase FP lamp identity changed",
        )
    refs = [
        n
        for n in g.nodes.values()
        if n.get("class") in ("ctlRefConst", "propNode")
        and n.find("ddo") is not None
        and n.find("ddo").get("uid") in ids
    ]
    require(
        [(n.get("uid"), n.get("class")) for n in refs] == [("7979", "ctlRefConst")],
        "direct or nested static property/reference census changed",
    )
    for uid, prop in (("7957", "Controls[]"), ("8048", "Value"), ("8025", "Value")):
        require(
            [
                n.findtext("PropItemName").strip('"')
                for n in g.nodes[uid].iter()
                if n.get("class") == "propItemInfo"
            ]
            == [prop],
            "row property changed",
        )
    for uid, ports in {
        "11120": ("7982", "7996"),
        "11117": ("7987", "7959"),
        "11111": ("7971", "8015"),
        "11108": ("8018", "8027", "8050"),
        "11105": ("8067", "65026"),
        "11102": ("65045", "8102"),
        "11099": ("8180", "8039"),
        "11078": ("8120", "8308"),
        "11069": ("8338", "8200"),
        "11084": ("8138", "8285"),
        "11063": ("8359", "8216"),
    }.items():
        exact_net(g, uid, ports)
    require(
        g.nodes["7985"].findtext("primResID") == "8016"
        and g.nodes["65015"].findtext("primResID") == "8003",
        "reference/value conversion changed",
    )
    for source, target, field in (
        ("8120", "8200", "en marche"),
        ("8138", "8216", "en défaut"),
    ):
        require(
            g.field(source)["label_path"] == g.field(target)["label_path"] == [field],
            "row retained field identity changed",
        )
    branches = []
    select = g.nodes["8243"]
    for ordinal, (action, diagram, running_net, fault_net) in enumerate(BRANCH_NETS):
        require(
            select.findall("diagramList/*")[ordinal].get("uid") == diagram,
            "button case order changed",
        )
        require(
            any(
                int(r.findtext("start")) == int(r.findtext("end")) == action
                and int(r.findtext("diagramIdx")) == ordinal
                for r in select.findall("SelectRangeArray32/*")
            ),
            "button range changed",
        )
        proofs = []
        for entry, exit_, net in (
            ("8308", "8338", running_net),
            ("8285", "8359", fault_net),
        ):
            ports = (alias(g.nodes[entry], ordinal), alias(g.nodes[exit_], ordinal))
            exact_net(g, net, ports)
            require(
                g.nodes[net] in g.nodes[diagram].findall("signalList/*"),
                "status pass-through left its button case",
            )
            proofs.append({"wire": net, "ports": list(ports)})
        branches.append(
            {"action": action, "diagram": diagram, "identity_wires": proofs}
        )

    hr, hx = helper or helper_sources()
    require(hr["sha256"] == HELPER_SHA, "wrong helper source version")
    h = SourceGraph(hr, hx, T(hx["meta"]))
    hw = Wires(h)
    helper_fields = scalar_updates(h, "1555")
    require(
        len(helper_fields) == 11
        and all(f["label_path"][-1] == "orange" for f in helper_fields),
        "comparison helper gained non-orange field write",
    )
    require(
        h.field("1586")["label_path"] == [PHASE, "orange"],
        "Phase orange target changed",
    )
    exact_net(h, "1341", ("3056", "1586"))
    require(
        h.nodes["3056"].findtext("dco/ConstValue") == "0000"
        and h.table.heap(h.nodes["3056"].findtext("dco/typeDesc")).get("Type")
        == "Boolean",
        "Phase orange False source changed",
    )
    copy_path = hw.path("1304", "5934")
    read_path = hw.path("1369", "1577")
    write_path = hw.path("1565", "3813")
    require(
        [e["uid"] for e in copy_path] == ["2647", "5180", "5964"]
        and [e["uid"] for e in read_path] == ["1330"]
        and [e["uid"] for e in write_path] == ["3862"],
        "helper copy/update paths changed",
    )
    require(
        [d.get("uid") for d in h.nodes["2636"].findall("diagramList/*")]
        == ["5910", "5053"],
        "helper frame order changed",
    )
    require(
        {n.get("uid") for n in h.nodes.values() if n.get("class") == "gRef"}
        == {"5927", "3800", "1336"},
        "helper local census changed",
    )
    require(
        not any(n.get("class") in ("propNode", "iUse") for n in h.nodes.values()),
        "helper gained another callable or property writer",
    )
    images = []
    for name, sha in IMAGES.items():
        path = REPO / "Supervision" / name
        require(digest(path) == sha, "saved Phase screenshot changed")
        images.append({"path": str(path.relative_to(REPO)), "sha256": sha})
    load_frames = {
        str(i): g.nodes["5909"].findall("diagramList/*")[i].get("uid") for i in (22, 23)
    }
    require(
        all(
            d not in g.ancestry(uid)
            for d in load_frames.values()
            for uid in writers | {"8025"}
        ),
        "LOAD gained an audited Phase writer",
    )
    # Correct an auxiliary role label in the earlier H1/Triplet source report.
    # The two named OUT00 destinations were right, but its bank_input/local
    # write-path labels inverted these aggregate read/write roles.
    bank_directions = []
    all_locals = {row["uid"]: row for row in receipt["graph_locals"]}
    for mux, reader_uid, writer_uid in (
        ("8553", "15529", "6122"),
        ("7543", "9302", "8562"),
    ):
        agg = g.nodes[mux].find("dcoAgg").get("uid")
        bound = {}
        for port in terms(g.nodes[mux]):
            if port.find("dco").get("uid") != agg:
                continue
            net, peer, ref = g.peer(port.get("uid"), "gRef")
            role = "read" if g.is_input(port) else "write"
            require(
                all_locals[ref.get("uid")]["write"] == (role == "write")
                and g.is_input(g.nodes[peer]) == (role == "write"),
                "bank aggregate/local direction conflict",
            )
            bound[role] = {
                "local": ref.get("uid"),
                "port": peer,
                "aggregate_terminal": port.get("uid"),
                "wire": net,
            }
        require(
            bound["read"]["local"] == reader_uid
            and bound["write"]["local"] == writer_uid,
            "bank aggregate direction route changed",
        )
        bank_directions.append({"mux": mux, **bound})
    return {
        "source_vi_sha256": SOURCE_SHA,
        "helper_vi_sha256": HELPER_SHA,
        "scope": (
            "Original main direct-line local/property writers "
            "and direct comparison helper"
        ),
        "observations": {
            "direct_local_aliases": 15,
            "direct_local_writers": 6,
            "whole_cluster_local_writers": local_routes,
            "comparison_whole_cluster_writer": {
                "uid": "16437",
                "call": "18812",
                "output_wire": "13546",
                "input_wire": "14957",
                "input_local": "16457",
            },
            "row_Value_write": {
                "uid": "8025",
                "read_uid": "8048",
                "same_reference_wire": "11108",
                "source_control_reference": "7979",
                "branches": branches,
                "flags": "copied unchanged after successful typed read",
            },
            "static_reference_target_census": {
                "direct_and_nested_controls": 133,
                "matching_nodes": ["7979"],
                "direct_bound_property_nodes": [],
            },
            "FP_flags": {"en marche": "20261", "en défaut": "20247"},
            "Phase_root_named_fields": phase_fields,
            "control_terminal_7644_connected": False,
            "load_event_frame_ids": load_frames,
            "helper": {
                "input_copy_path": copy_path,
                "copied_output_read_path": read_path,
                "output_write_path": write_path,
                "fields_changed": helper_fields,
                "Phase_orange": {"value": False, "literal": "3056", "net": "1341"},
                "Phase_running_and_fault": "retained from helper input cluster",
            },
        },
        "inferences": [
            "No hardware-bit or calculated producer of the two Phase flags "
            "was found in these audited paths.",
            "The five main nMux local writers echo Phase flags "
            "from a previously read cluster; "
            "the sixth local writer echoes them through the comparison helper.",
            "The event19 selected-row Value writer echoes both flags "
            "in all seven saved arms.",
            "A whole-cluster or whole-row copy-back can restore an older flag "
            "value if another actor changed it after the source snapshot; "
            "this race is possible, not observed.",
            "The flags therefore originate from pre-existing UI state "
            "in these paths, not "
            "from independently verified equipment feedback.",
            "Correction to broad earlier summaries: Phase orange is forced False "
            "in the original "
            "comparison helper, not driven by its command/readback comparison.",
        ],
        "saved_screenshots": images,
        "correction_to_prior_auxiliary_role_labels": {
            "prior_report": "h1_triplet_source_20261017/RESULT.json",
            "unchanged": "H1 maps to C6.OUT00; Triplet1-1 maps to C7.OUT00",
            "corrected_bank_local_directions": bank_directions,
            "note": "Earlier bank_input/bank_local_write_path labels were reversed. "
            "The wire endpoints and named destinations are unchanged. "
            "This additive correction does not rewrite the earlier evidence.",
        },
        "requires_LabVIEW_or_remains_unknown": [
            "Initial Phase Boolean values: saved DFDS and native startup/default "
            "semantics are unqualified. No False default is inferred "
            "from a palette or missing field.",
            "Historical screenshots lack capture-time source hashes; "
            "source-version-native "
            "correspondence remains open.",
            "The native Controls[] row-order/reference ABI "
            "and omitted caller output connector "
            "index are not promoted by this source trace.",
            "External UI/VI Server clients, deployed-version changes "
            "and all unreviewed dynamic "
            "reference/error paths are not excluded by a local main-VI writer census.",
            "Property/Variant error behavior, copy-back races "
            "and actual initial/live values "
            "were not executed or measured.",
        ],
        "complete_Supervision_coverage": False,
        "native_defaults_verified": False,
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
        require(result == json.loads(OUTPUT.read_text("utf-8")), "Phase report changed")
    print(
        json.dumps(
            {
                "local_writers": 6,
                "row_copy_branches": 7,
                "Phase_orange": False,
                "hardware_io": False,
                "report": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
