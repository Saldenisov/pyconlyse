"""Prove runtime PSP error sinks, text-buffer clearing and loop-stop bindings.

Offline source analysis only. Wire connectivity across case tunnels is a binding
census, not a claim that alternative branches execute together. Native PSP,
modal-dialog, filesystem and abort/reconnect behavior remain unexecuted.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from collections import Counter

from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, SOURCE_SHA, digest, original
from trace_sup_beam_switches import Wires, terms
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

OUTPUT = (
    REPO / "Supervision/integration_analysis/psp_journals_stop_20261017/RESULT.json"
)
JOURNAL_RECEIPT = (
    REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/07.json"
)
JOURNAL_RECEIPT_SHA = "9B9EE2F3E6839747C4D3801AE1B497E7827C93B81C0D8F91B825200465BBE40D"
JOURNAL_SHA = "E8B8E05803ED7BC37F3AE82F2C133D4BC43E1DE7AD22E76B2C2D6DDA26681E49"
TER_CASES = {
    6: ("20154", "20156", "20535"),
    14: ("38249", "38251", "38326"),
    15: ("41026", "41029", "41201"),
    16: ("58205", "58207", "58262"),
    17: ("19594", "36566", "40558"),
    18: ("33976", "33992", "37686"),
}
IMAGES = {
    "0__SUP__ELYSEd50.png": (
        "F8BDDEEC4B71155865A8184B86AAACA8B48FB1D1AA607B9F5443304971C4833C"
    ),
    "0__SUP__ELYSEd54.png": (
        "86C0935C03CCA29EFB5C1E6F88EF458C7D95651EBF27BEB9A75267786D127CA4"
    ),
    "0__SUP__ELYSEd57.png": (
        "41CB3640CC54D03DE9F995FCB4A23103D7F7559BABB36C132303ED038AF917A7"
    ),
    "0__SUP__ELYSEd60.png": (
        "562E561D815E02EB02D316B234BC7B17C25A1EB52BC93F99B720C58A12A5C3FE"
    ),
    "2__SUP__Journal__des___erreursd.png": (
        "900FCE94757DB5CC970D2AF682382E179016088E6004099389608DB41ACA3BC2"
    ),
}


def journal_sources():
    require(digest(JOURNAL_RECEIPT) == JOURNAL_RECEIPT_SHA, "journal receipt changed")
    receipt = json.loads(JOURNAL_RECEIPT.read_text("utf-8"))
    require(
        receipt["sha256"] == JOURNAL_SHA and digest(receipt["source"]) == JOURNAL_SHA,
        "journal VI changed",
    )
    roots = {}
    for key, entry in zip(("bd", "fp", "meta"), receipt["xml"], strict=True):
        require(digest(entry["path"]) == entry["sha256"], "journal XML changed")
        roots[key] = ET.parse(entry["path"]).getroot()
    return receipt, roots


def error_port(graph, node, incoming):
    matches = []
    for p in terms(node):
        # Unwired PSP error inputs may carry 0x5000 instead of the wired input
        # flag 0x9000. Use the stored shared-variable terminal ID, not that flag.
        if node.get("class") in (
            "sharedVariableDynamicRead",
            "sharedVariableDynamicWrite",
        ):
            direction_matches = (
                p.findtext("dco/terminal_ID") == "08"
                if incoming
                else p.findtext("dco/terminal_ID") is None
            )
        else:
            direction_matches = graph.is_input(p) == incoming
        if not direction_matches or p.findtext("dco/typeDesc") is None:
            continue
        desc = graph.table.heap(p.findtext("dco/typeDesc"))
        if (
            desc is not None
            and desc.get("Type") == "Cluster"
            and [field["type"] for field in graph.table.fields(desc)]
            == ["Boolean", "NumInt32", "String"]
        ):
            matches.append(p.get("uid"))
    require(
        len(matches) == 1,
        f"error terminal missing/ambiguous: {node.get('uid')} incoming={incoming}",
    )
    return matches[0]


def boolean_case(graph, uid):
    node = graph.nodes[uid]
    ranges = [
        [int(r.findtext(k)) for k in ("start", "end", "diagramIdx")]
        for r in node.findall("SelectRangeArray32/*")
    ]
    require(
        node.get("class") == "select" and ranges == [[0, 0, 0], [1, 1, 1]],
        "Boolean/error case ranges changed",
    )
    return node.findall("diagramList/*")


def named_writes(graph, frame, name):
    return [
        n.get("uid")
        for n in frame.iter()
        if n.get("class") == "gRef"
        and graph.names.get(n.get("uid")) == name
        and graph.is_input(terms(n)[0])
    ]


def journal_returned_message(snapshot):
    """Diagnostic helper result after return; no file success is fabricated."""
    if type(snapshot) is not str:
        raise TypeError("explicit String snapshot required")
    return ""


def remote_head_intent(snapshot):
    """Pure nonempty-array witness, not a PSP read/write or an empty-array default."""
    if (
        not isinstance(snapshot, tuple)
        or not snapshot
        or any(type(v) is not str for v in snapshot)
    ):
        raise ValueError("explicit nonempty tuple of Strings required")
    return (
        None
        if snapshot[0] == ""
        else {"message": snapshot[0], "publish_tail": snapshot[1:]}
    )


def verify(receipt=None, roots=None, helper=None):
    if receipt is None:
        receipt, roots = original()
    require(receipt["sha256"] == SOURCE_SHA, "wrong original Main VI")
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    w = Wires(g)
    event_frames = [d.get("uid") for d in g.nodes["5909"].findall("diagramList/*")]
    require(len(event_frames) == 34, "event census changed")
    # The special synchronization write goes through UI operations before TER.
    # The downstream cluster may include new UI/conversion/format errors too.
    special = [
        {"node": "40236", "input": "40252", "output": "40259", "class": "propNode"},
        {
            "node": "40404",
            "input": "40418",
            "output": "40409",
            "class": "prim",
            "resid": "8016",
        },
        {"node": "40371", "input": "40379", "output": "40382", "class": "propNode"},
        {
            "node": "62591",
            "input": "62606",
            "output": "62617",
            "class": "prim",
            "resid": "8003",
        },
        {"node": "22086", "input": "53676", "output": "53679", "class": "printf"},
    ]
    writes = []
    for uid, n in g.nodes.items():
        if n.get("class") != "sharedVariableDynamicWrite" or "5902" not in g.ancestry(
            uid
        ):
            continue
        event = next(
            (i for i, f in enumerate(event_frames) if f in g.ancestry(uid)), None
        )
        out = error_port(g, n, False)
        path, sink = [], None
        if event in TER_CASES:
            case, selector, writer = TER_CASES[event]
            current = out
            bridges = special if event == 6 else []
            for bridge in bridges:
                op = g.nodes[bridge["node"]]
                require(
                    op.get("class") == bridge["class"]
                    and (
                        "resid" not in bridge
                        or op.findtext("primResID") == bridge["resid"]
                    ),
                    "synchronization error bridge changed",
                )
                require(
                    error_port(g, op, True) == bridge["input"]
                    and error_port(g, op, False) == bridge["output"],
                    "bridge error directions changed",
                )
                path.extend(w.path(current, bridge["input"]))
                current = bridge["output"]
            path.extend(w.path(current, selector))
            no_error, error = boolean_case(g, case)
            require(
                not named_writes(g, no_error, "TER")
                and named_writes(g, error, "TER") == [writer],
                "TER error/success branches changed",
            )
            require(g.names[writer] == "TER", "TER sink identity changed")
            sink = {
                "kind": "TER via downstream error case"
                if bridges
                else "TER error case",
                "case": case,
                "selector": selector,
                "writer": writer,
                "No_Error_clears_TER": False,
                "intervening_operations": bridges,
            }
        elif event is None:
            require(uid in ("26430", "41646"), "unexpected periodic PSP writer")
            sink = {"kind": "remote journal acknowledgement chain"}
        elif event in (0, 1, 7, 12, 13):
            require(
                not any(out in ps for _, ps in g.nets),
                "discarded PSP error gained a consumer",
            )
            sink = {"kind": "unwired error output"}
        else:
            net, port, call = g.peer(out, "iUse")
            require(
                call.findtext("label/textRec/text").strip('"')
                == "Simple Error Handler.vi"
                and g.is_input(g.nodes[port])
                and g.nodes[port].findtext("dco/paramIdx") == "9",
                "standard PSP error handler binding changed",
            )
            exact_net(g, net, (out, port))
            connected = [
                p.get("uid")
                for p in terms(call)
                if any(p.get("uid") in ps for _, ps in g.nets)
            ]
            require(
                connected == [port],
                "standard handler gained an override/output consumer",
            )
            sink = {
                "kind": "Simple Error Handler.vi",
                "call": call.get("uid"),
                "error_port": port,
                "dialog_override_wired": False,
                "wire": net,
            }
        writes.append(
            {
                "uid": uid,
                "event": event,
                "error_out": out,
                "sink": sink,
                "path_to_TER_selector": path,
            }
        )
    counts = dict(Counter(row["sink"]["kind"] for row in writes))
    require(
        len(writes) == 63
        and counts
        == {
            "unwired error output": 5,
            "Simple Error Handler.vi": 30,
            "TER via downstream error case": 1,
            "TER error case": 25,
            "remote journal acknowledgement chain": 2,
        },
        "runtime PSP write-error census changed",
    )

    # A connectivity superset is adequate for exclusion, not per-arm execution.
    read_sinks = []
    for terminal in ("8626", "52012", "50631"):
        component = w.component(terminal)
        permitted = {
            "sRN",
            "sLoc",
            "sharedVariableDynamicRead",
            "seqTun",
            "xTunnel",
            "commentTun",
            "caseSel",
            "select",
        }
        require(
            all(
                g.owners[p].get("class") in permitted
                for p in component
                if p in g.owners
            ),
            "read error acquired a nontrivial consumer",
        )
        cases = sorted(
            {
                n.get("uid")
                for n in g.nodes.values()
                if n.get("class") == "select"
                for p in terms(n)
                if p.get("uid") in component
                and p.find("dco") is not None
                and p.find("dco").get("class") == "caseSel"
            }
        )
        for case in cases:
            require(
                not any(
                    n.get("class")
                    in (
                        "iUse",
                        "polyIUse",
                        "gRef",
                        "propNode",
                        "sharedVariableDynamicRead",
                        "sharedVariableDynamicWrite",
                    )
                    for n in g.nodes[case].iter()
                ),
                "read error case gained an effect",
            )
        read_sinks.append(
            {
                "error_out": terminal,
                "component_size": len(component),
                "error_cases": cases,
                "journal_or_stop_writer_found": False,
            }
        )
    require(
        read_sinks[2]["error_cases"] == ["33861", "34296", "41732", "42334", "42824"],
        "periodic error-case census changed",
    )

    return finish_proof(g, w, T, helper, writes, counts, read_sinks)


def finish_proof(g, w, T, helper, writes, counts, read_sinks):
    """Journal helper, local/remote flush and shared stop consumers."""
    hr, hx = journal_sources() if helper is None else helper
    require(hr["sha256"] == JOURNAL_SHA, "wrong journal helper source")
    h = SourceGraph(hr, hx, T(hx["meta"]))
    fp = {n.get("uid"): n for n in hx["fp"].iter() if n.get("class")}
    require(
        fp["45"].findtext("conNum") == "1"
        and fp["45"].findtext("ddo/partsList/*/textRec/text").strip('"')
        == "Message OUTPUT"
        and h.table.heap(fp["45"].findtext("typeDesc")).get("Type") == "String",
        "helper Message OUTPUT connector changed",
    )
    require(
        h.nodes["378"].find("dco").get("uid") == "45"
        and h.nodes["455"].findtext("dco/ConstValue") == "0000000000"
        and h.table.heap(h.nodes["455"].findtext("dco/typeDesc")).get("Type")
        == "String",
        "helper empty String return changed",
    )
    exact_net(h, "353", ("455", "378"))
    require(
        not any(
            n.get("class") in ("select", "whileLoop", "sequence", "iUse")
            for n in h.nodes.values()
        ),
        "helper gained conditional/callable clearing logic",
    )
    disk = h.nodes["139"]
    require(
        disk.get("class") == "polyIUse"
        and disk.findtext("label/textRec/text").strip('"')
        == "Write To Spreadsheet File.vi",
        "spreadsheet call changed",
    )
    require(
        all(
            not any(p.get("uid") in ps for _, ps in h.nets)
            for p in terms(disk)
            if not h.is_input(p)
        ),
        "disk result gained a consumer",
    )
    exact_net(h, "343", ("68", "171", "627"))
    exact_net(h, "398", ("165", "65"))
    require(
        [p.get("uid") for p in terms(h.nodes["163"])]
        == ["165", "168", "171", "174", "213"],
        "in-memory journal concat order changed",
    )
    require(
        h.nodes["100"].findtext("dco/ConstValue") == "000000020D0A",
        "journal CRLF changed",
    )
    local_flush = []
    for name, case, compare, reader, writer, call, out, net, dst in (
        ("TER", "45128", "45345", "45115", "45305", "45223", "45239", "45327", "45310"),
        ("TME", "39474", "44921", "39455", "44766", "44471", "44560", "44834", "44773"),
    ):
        false, true = boolean_case(g, case)
        require(
            not named_writes(g, false, name)
            and named_writes(g, true, name) == [writer],
            "local journal clear branch changed",
        )
        require(
            g.nodes[compare].findtext("primResID") == "1105"
            and g.names[reader] == g.names[writer] == name,
            "local journal nonempty comparison changed",
        )
        # The comparator's other input is an explicitly stored empty String.
        inputs = [p for p in terms(g.nodes[compare]) if g.is_input(p)]
        constants = [raw for p in inputs for _, raw in w.literals(p.get("uid"))]
        require(
            constants == ["0000000000"],
            "local journal empty comparison literal changed",
        )
        require(
            g.owners[out].get("uid") == call
            and g.nodes[out].findtext("dco/paramIdx") == "1"
            and not g.is_input(g.nodes[out]),
            "journal clear output ABI changed",
        )
        exact_net(g, net, (out, dst))
        local_flush.append(
            {
                "buffer": name,
                "case": case,
                "nonempty_compare": compare,
                "source_local": reader,
                "clear_writer": writer,
                "helper": call,
                "message_output_port": out,
                "clear_wire": net,
                "cleared_when_helper_returns": True,
                "clearing_depends_on_disk_success": False,
            }
        )

    ter_writers = []
    for uid, node in g.nodes.items():
        if (
            node.get("class") != "gRef"
            or node.findtext("termList/*/dco/paramIdx") != "184"
            or not g.is_input(terms(node)[0])
        ):
            continue
        port = terms(node)[0].get("uid")
        if uid == "45305":
            ter_writers.append(
                {"writer": uid, "kind": "journal Message OUTPUT empty String"}
            )
            continue
        _, _, producer = g.peer(port, "concat")
        literals = [
            (literal, raw)
            for p in terms(producer)
            if g.is_input(p)
            for literal, raw in w.literals(p.get("uid"))
            if g.table.heap(g.nodes[literal].findtext("dco/typeDesc")).get("Type")
            == "String"
        ]
        require(literals, "TER formatter lost its stored String candidates")
        ter_writers.append(
            {
                "writer": uid,
                "kind": "String concat formatter",
                "concat": producer.get("uid"),
                "literal_candidates_not_branch_execution": sorted(
                    {p for p, _ in literals}
                ),
                "candidate_empty_literal_present": any(
                    int.from_bytes(bytes.fromhex(raw)[:4], "big") == 0
                    for _, raw in literals
                ),
            }
        )
    require(len(ter_writers) == 15, "Main TER local writer census changed")

    remote_flush = []
    for (
        bank,
        case,
        delete,
        amount,
        index,
        result,
        writer,
        local_port,
        wire,
        journal,
    ) in (
        (
            "VTA",
            "38605",
            "12642",
            "18115",
            "18150",
            "15550",
            "26430",
            "18184",
            "41510",
            "38650",
        ),
        (
            "VTL",
            "18268",
            "41595",
            "41184",
            "41249",
            "41624",
            "41646",
            "41637",
            "41712",
            "41487",
        ),
    ):
        boolean_case(g, case)
        require(
            g.nodes[delete].get("class") == "aDelete"
            and g.nodes[amount].findtext("dco/ConstValue") == "00000001"
            and g.nodes[index].findtext("dco/ConstValue") == "0000000000",
            "remote journal one-head deletion changed",
        )
        target = next(
            p for p in terms(g.nodes[writer]) if p.findtext("dco/terminal_ID") == "0A"
        )
        exact_net(g, wire, (result, local_port, target.get("uid")))
        require(
            g.names[g.owners[local_port].get("uid")] == bank
            and g.is_input(g.nodes[local_port]),
            "remote journal local queue write changed",
        )
        require(
            g.nodes[journal].findtext("label/textRec/text").strip('"')
            == "2_SUP_Journal_des _erreurs.vi",
            "remote journal helper changed",
        )
        remote_flush.append(
            {
                "bank": bank,
                "case": case,
                "delete": delete,
                "delete_count": 1,
                "delete_index": 0,
                "publish_tail_writer": writer,
                "tail_and_local_wire": wire,
                "journal_call": journal,
                "local_tail_write_error_gated": False,
                "journal_call_has_PSP_error_input": False,
            }
        )
    remote_ack_error_in = error_port(g, g.nodes["26430"], True)
    require(
        not any(remote_ack_error_in in ps for _, ps in g.nets),
        "first remote acknowledgement gained an incoming error",
    )
    ack_path = w.path(
        error_port(g, g.nodes["26430"], False), error_port(g, g.nodes["41646"], True)
    )
    reader_path = w.path(
        error_port(g, g.nodes["41646"], False), error_port(g, g.nodes["11793"], True)
    )
    require(
        all(
            step["kind"] in ("wire", "sequence-local", "tunnel")
            for step in ack_path + reader_path
        ),
        "acknowledgement error acquired transformation",
    )

    loop_stops = []
    for loop, reader, source, target, net in (
        ("17671", "15290", "15304", "17961", "38219"),
        ("6017", "11786", "14053", "6080", "11791"),
        ("5846", "26092", "26099", "6059", "3683"),
        ("5841", "21235", "21242", "6039", "21395"),
    ):
        require(
            g.names[reader] == "stop"
            and not g.is_input(g.nodes[source])
            and [p.get("uid") for p in g.nodes[loop].findall("loopTestDCO/termList/*")]
            == [target]
            and g.nodes[loop].findtext("loopTestDCO/objFlags") == "65537",
            "loop shared-stop consumer changed",
        )
        exact_net(g, net, (source, target))
        loop_stops.append(
            {"loop": loop, "stop_local": reader, "wire": net, "test_port": target}
        )
    refs = {
        u: n
        for u, n in g.nodes.items()
        if n.get("class") == "gRef" and n.findtext("termList/*/dco/paramIdx") == "49"
    }
    require(
        {u for u, n in refs.items() if g.is_input(terms(n)[0])} == {"12664"},
        "Main global stop gained another local writer",
    )
    require(
        g.ancestry("12664")[:2] == ["14127", "988"]
        and g.nodes["988"].findall("diagramList/*")[3].get("uid") == "14127"
        and g.nodes["12839"].findtext("dco/ConstValue") == "0000"
        and g.table.heap(g.nodes["12839"].findtext("dco/typeDesc")).get("Type")
        == "Boolean",
        "post-loop stop=False reset changed",
    )
    exact_net(g, "12845", ("12839", "12688"))
    require(
        not any("6061" in ps for _, ps in g.nets)
        and not any(
            n.get("class") in ("ctlRefConst", "propNode")
            and n.find("ddo") is not None
            and n.find("ddo").get("uid") == "6015"
            for n in g.nodes.values()
        ),
        "stop gained a terminal/property binding",
    )
    for loop in ("6017", "5846"):
        require(
            not terms(g.nodes[loop]) and not g.nodes[loop].findall("tunnelList/*"),
            "polling/event loop gained a cross-iteration terminal",
        )
    clears = []
    for uid, node in g.nodes.items():
        if (
            node.get("class") != "iUse"
            or "5902" not in g.ancestry(uid)
            or node.findtext("label/textRec/text", "").strip('"') != "Clear Errors.vi"
        ):
            continue
        event = next(
            (i for i, f in enumerate(event_frames(g)) if f in g.ancestry(uid)), None
        )
        require(
            event in (25, 30) or "5841" in g.ancestry(uid),
            "new PSP-relevant Clear Errors call",
        )
        clears.append(
            {"call": uid, "event": event, "camera_loop": "5841" in g.ancestry(uid)}
        )
    require(
        {r["call"] for r in clears} == {"72477", "32145", "71621", "7038"},
        "Clear Errors census changed",
    )
    images = []
    for name, sha in IMAGES.items():
        path = REPO / "Supervision/analysis/labview_print_hidden_frames" / name
        require(digest(path) == sha, "saved journal screenshot changed")
        images.append({"path": str(path.relative_to(REPO)), "sha256": sha})
    return {
        "source_vi_sha256": SOURCE_SHA,
        "journal_vi_sha256": JOURNAL_SHA,
        "scope": (
            "Original Main runtime PSP errors, journal clearing "
            "and shared-stop consumers"
        ),
        "observations": {
            "runtime_PSP_write_error_sink_counts": counts,
            "runtime_PSP_write_error_sinks": writes,
            "read_error_sinks": read_sinks,
            "journal_Message_OUTPUT": {
                "value": "",
                "connector": 1,
                "literal": "455",
                "wire": "353",
            },
            "in_memory_journal_order": "timestamp + message + CRLF + previous journal",
            "journal_disk_call_has_consumed_output": False,
            "local_flush": local_flush,
            "Main_TER_local_writers": ter_writers,
            "remote_flush": remote_flush,
            "acknowledgement_error_to_VTL": ack_path,
            "VTL_acknowledgement_error_to_first_card_read": reader_path,
            "global_stop_loop_consumers": loop_stops,
            "global_stop_local_writers": ["12664"],
            "global_stop_reset": {"outer_frame": 3, "value": False, "wire": "12845"},
            "explicit_Clear_Errors_calls": clears,
            "polling_or_event_error_shift_register_found": False,
        },
        "inferences": [
            "Runtime read errors and textual TER are distinct channels: the final "
            "Timeout error is unused, the independent counter-read error is unwired, "
            "and periodic-read errors reach only numeric calculation error cases, "
            "not a journal helper or a Main stop writer in this audited graph.",
            "Thirty write sites invoke Simple Error Handler with no wired dialog "
            "override or consumed output. Twenty-five feed TER error cases; one "
            "feeds a TER case after UI/property/conversion/format operations. Five "
            "discard their errors and two acknowledge remote journal queues.",
            "No Error in the six audited TER dispatch families does not clear TER. "
            "A nonempty TER is later flushed in periodic sequence9424 frame1. "
            "Once its helper returns, Message OUTPUT is an explicit empty String, "
            "so buffer clearing does not prove successful disk persistence.",
            "The fifteen Main TER local writers comprise fourteen String concat "
            "formatters and one journal-helper empty String "
            "return. Empty TER is therefore not proof of restored communication: "
            "its visible local clear is consumption by the journal, not a PSP "
            "success acknowledgement.",
            "TER and TME are single String slots, not transactional queues. Other "
            "event-loop producers can overwrite a pending message before flushing, "
            "or a pending clear can erase a newer message written after the read. "
            "These source-supported interleavings were not observed live.",
            "Remote VTA/VTL processing logs the first nonempty String and sends "
            "the array with its first entry deleted back to PSP and the local. "
            "Logging and acknowledgement have no success dependency in this frame; "
            "neither exactly-once delivery nor durable logging is established.",
            "If tail publication fails and a later read again supplies the old "
            "remote array, the same message can be logged again. A local tail write "
            "alone is not confirmation that the remote queue was cleared.",
            "The remote VTA acknowledgement starts without a wired error input; "
            "its error can feed VTL acknowledgement, whose result feeds C1 and the "
            "remaining periodic read chain. A journal-acknowledgement failure can "
            "therefore precede a card read even when that card is not the origin.",
            "No PSP error in this Main diagram writes global stop=True. Four outer "
            "runtime loops have direct shared stop bindings; the only local write "
            "to stop is False in outer frame3, after the runtime region completes.",
            "The four explicit Clear Errors calls belong to camera/motion work, "
            "not these periodic PSP error paths. No previous PSP error is wired "
            "through a shift register of the polling or event loop.",
            "If loops remain running and native calls return, later iterations "
            "make read attempts again, and acknowledgement attempts when a remote "
            "queue head is nonempty. Recovery is not gated by "
            "clearing TER or pressing a Main error-reset button. Native reconnection "
            "and fresh data are not guaranteed by these local wires.",
            "The cleanup stop=False assignment is not a communication-recovery "
            "routine and does not restart exited loops. Modal-handler aborts cannot "
            "be equated to orderly loop completion and resource cleanup.",
        ],
        "unknown_or_requires_native_qualification": [
            "Simple Error Handler implementation/default dialog mode at the deployed "
            "LabVIEW version, modal waiting, Continue/Stop actions and abort effects. "
            "The named standard callee can contain effects absent from Main.",
            "Native PSP caching, incoming-error behavior, reconnect delay, invalid "
            "outputs and defaults of unwired error-case output tunnels. No zero or "
            "previous-error retention default is invented.",
            "Spreadsheet polymorphic connector/native implementation, file error "
            "dialogs, actual disk persistence and completion under failure. The "
            "historical source receipt refused code generation for this dependency.",
            "Actual scheduling and message losses/duplicates. External UI/VI Server "
            "writers and termination inside standard VIs are not excluded.",
            "Command retry behavior inside every procedure, startup failure and "
            "hardware-safe-state equivalence are not established "
            "by this runtime trace.",
            "Historical screenshots lack capture-time source hashes; displayed "
            "fragments corroborate wiring but do not pin a deployed VI version.",
            "The additional fourteen-formatter census records candidate literals "
            "across alternative arms, not selected runtime prefixes. Some candidates "
            "are empty; nonempty output of every formatter is not newly proven.",
        ],
        "saved_screenshots": images,
        "paths_are_bindings_not_alternative_branch_execution": True,
        "native_failure_or_recovery_executed": False,
        "complete_Supervision_coverage": False,
        "screen_used": False,
        "vi_run_or_save": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
    }


def event_frames(graph):
    return [d.get("uid") for d in graph.nodes["5909"].findall("diagramList/*")]


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
            result == json.loads(OUTPUT.read_text("utf-8")),
            "journal/stop report changed",
        )
    print(
        json.dumps(
            {
                "runtime_PSP_writes": 63,
                "screen_used": False,
                "hardware_io": False,
                "report": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
