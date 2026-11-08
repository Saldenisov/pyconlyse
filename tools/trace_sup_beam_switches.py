"""Static M/A and X1/X10 event-to-Acquisition trace. Never actuates anything."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path

from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, SOURCE_SHA, original
from export_sup_workspace import CORRECTOR_BUTTONS
from validate_acq_final_cleanup import constant
from validate_acq_modulator_start_event_guards import ARCHIVE_SHA256, require
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local
from validate_acq_timeout_reads import SITES
from validate_acq_vam_status import checked_vam

OUTPUT = REPO / "Supervision/integration_analysis/beam_switch_trace_20261016/trace.json"
ACQ_ARCHIVE = (
    REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
)
COMPARISON = (
    REPO
    / "Supervision/integration_analysis/orchestrator"
    / "full_coverage_orchestration_20261009/lvkit"
    / "src/lvkit/data/primitives/comparison.json"
)
COMPARISON_SHA = "60F30921BD335FE1E736ACC16022674E7462740D31E8B7B289D8EACFE5BD42DB"
LINES = {
    "direct": ("14098", "8243", "8096", "8174", "8148", "8425", "11830", "7799"),
    "deviated": (
        "33504",
        "34080",
        "34005",
        "34040",
        "34030",
        "46437",
        "46564",
        "33755",
    ),
}
GROUPS = {
    "direct": ((1,), (2,), (0, 7, 8), (3, 4, 5, 6, 9, 10)),
    "deviated": ((0, 1, 2, 3, 6), (4, 5, 7, 8)),
}
FORWARD = {
    "direct": ("8491", {"8553": "C6NI6703", "7543": "C7NI6703", "12004": "C8NI6703"}),
    "deviated": ("46593", {"46640": "C6NI6703", "46679": "C7NI6703"}),
}


class Wires:
    """Edges are saved wires or explicit structural tunnel/local aliases.

    No primitive input/output, bundle fields or separate local-variable reads
    are joined. A path is a static binding, not a scheduling/execution trace.
    """

    def __init__(self, graph):
        self.graph = graph
        self.adj = defaultdict(list)
        for net, ports in graph.nets:
            for port in ports[1:]:
                self.add(ports[0], port, "wire", net)
        for node in graph.nodes.values():
            if node.get("class") == "term":
                for alias in node.findall("dco/termList/*"):
                    self.add(
                        node.get("uid"), alias.get("uid"), "tunnel", node.get("uid")
                    )
            elif node.get("class") == "sLoc":
                ports = [t.get("uid") for t in node.findall("termList/*")]
                for port in ports[1:]:
                    self.add(ports[0], port, "sequence-local", node.get("uid"))

    def add(self, a, b, kind, uid):
        if a != b:
            self.adj[a].append((b, kind, uid))
            self.adj[b].append((a, kind, uid))

    def component(self, source):
        found, pending = {source}, [source]
        while pending:
            for peer, _, _ in self.adj[pending.pop()]:
                if peer not in found:
                    found.add(peer)
                    pending.append(peer)
        return found

    def path(self, source, target):
        queue, previous = deque([source]), {source: None}
        while queue and target not in previous:
            current = queue.popleft()
            for peer, kind, uid in self.adj[current]:
                if peer not in previous:
                    previous[peer] = (kind, uid, current)
                    queue.append(peer)
        require(target in previous, f"saved wire path absent: {source}->{target}")
        result = []
        while target != source:
            kind, uid, ancestor = previous[target]
            result.append(dict(source=ancestor, target=target, kind=kind, uid=uid))
            target = ancestor
        return list(reversed(result))

    def literals(self, port):
        return [
            (uid, self.graph.nodes[uid].findtext("dco/ConstValue"))
            for uid in sorted(self.component(port))
            if uid in self.graph.nodes
            and self.graph.nodes[uid].findtext("dco/ConstValue") is not None
        ]


def terms(node):
    return node.findall("termList/*")


def alias(term, ordinal):
    aliases = [a.get("uid") for a in term.findall("dco/termList/*")]
    require(aliases and aliases[-1] == term.get("uid"), "tunnel alias grammar changed")
    return aliases[ordinal]


def scalar_literal(wires, port):
    values = wires.literals(port)
    require(len(values) == 1, "literal binding missing/ambiguous")
    uid, raw = values[0]
    return uid, struct.unpack(">d", bytes.fromhex(raw)[:8])[0]


def url_literal(wires, port):
    values = wires.literals(port)
    require(len(values) == 1, "PSP URI binding missing/ambiguous")
    uid, text = values[0]
    raw = bytes.fromhex(text)
    require(len(raw) - 4 == int.from_bytes(raw[:4], "big"), "PSP URI encoding changed")
    return uid, raw[4:].decode("ascii")


def check_whole_cluster_helpers():
    """Exclude hidden transport/callee nodes in the two whole-line consumers."""
    result = []
    for name, expected in (
        ("04", "4BC73489268882E3DC1DB68BA62553684C6D1D38D082234F1FD3AEDF7165473A"),
        ("05", "1352A7DCB4C91A59AA22202FD800F4B1C3265E3C4C3643A66E9C642775FFCE84"),
    ):
        path = (
            REPO
            / f"Supervision/analysis/lvkit_eval/parser_release_20261003/{name}.json"
        )
        require(
            hashlib.sha256(path.read_bytes()).hexdigest().upper() == expected,
            "whole-cluster helper receipt changed",
        )
        receipt = json.loads(path.read_text("utf-8"))
        require(
            hashlib.sha256(Path(receipt["source"]).read_bytes()).hexdigest().upper()
            == receipt["sha256"],
            "whole-cluster helper source changed",
        )
        entry = next(x for x in receipt["xml"] if x["path"].endswith("_BDHb.xml"))
        data = Path(entry["path"]).read_bytes()
        require(
            hashlib.sha256(data).hexdigest().upper() == entry["sha256"],
            "helper XML changed",
        )
        bd = ET.fromstring(data)
        classes = {n.get("class") for n in bd.iter() if n.get("class")}
        require(
            classes
            <= {
                "oHExt",
                "diag",
                "sequence",
                "term",
                "seqTun",
                "gRef",
                "gRefDCO",
                "label",
                "Image",
                "textHair",
                "sRN",
                "signal",
                "nMux",
                "nmxDCO",
                "prim",
                "parm",
                "overridableParm",
                "bDConstDCO",
                "stdBool",
                "multiCosm",
                "annex",
                "fontRun",
                "fPTerm",
            },
            "whole-cluster helper gained a call, property, transport "
            "or other operation",
        )
        result.append(
            dict(
                source=receipt["source"],
                source_sha256=receipt["sha256"],
                bd_sha256=entry["sha256"],
                calls=0,
                PSP_nodes=0,
                qualification=(
                    "saved node-class census only; no whole-VI native/ABI promotion"
                ),
            )
        )
    return result


def build_trace(receipt=None, roots=None, acq=None):
    if roots is None:
        receipt, roots = original()
    saved_types, _ = components()
    require(
        hashlib.sha256(COMPARISON.read_bytes()).hexdigest().upper() == COMPARISON_SHA,
        "current Select metadata hash changed",
    )
    graph = SourceGraph(receipt, roots, saved_types(roots["meta"]))
    wires = Wires(graph)
    explicit_ma_reads = []
    for node in graph.nodes.values():
        if node.get("class") != "nMux":
            continue
        agg = graph.aggregate(node.get("uid"))
        fields = graph.table.fields(graph.table.heap(agg.findtext("dco/typeDesc")))
        if not fields:
            continue
        for term in terms(node):
            raw = term.findtext("dco/i")
            if raw is None or graph.is_input(term):
                continue
            index = int(raw)
            if index < len(fields) and fields[index]["label_path"][-1] == "M/A":
                explicit_ma_reads.append(term.get("uid"))
    require(not explicit_ma_reads, "new explicit M/A consumer requires analysis")
    select = json.loads(COMPARISON.read_text("utf-8"))["primitives"]["1516"]
    require(
        [t["name"] for t in select["terminals"][1:]]
        == ["f_value", "selector", "t_value"]
        and select["python_code"]["result"] == "in_3 if in_2 else in_1",
        "current LVKit Select metadata changed",
    )
    results = {}
    for line, (
        seq,
        case_uid,
        source_mux,
        target_mux,
        x1,
        compare,
        gate,
        mask,
    ) in LINES.items():
        case = graph.nodes[case_uid]
        ranges = [
            (
                int(r.findtext("start")),
                int(r.findtext("end")),
                int(r.findtext("diagramIdx")),
            )
            for r in case.findall("SelectRangeArray32/*")
        ]
        require(
            ranges
            == [
                (code, code, i)
                for i, code in enumerate((0, 1, 16, 128, 256, 512, 1024))
            ],
            "switch/arrow selector cases changed",
        )
        passes = []
        for code, ordinal in ((1, 1), (16, 2)):
            diagram = case.findall("diagramList/*")[ordinal]
            actual = {
                frozenset(t.get("uid") for t in net.findall("termList/*"))
                for net in diagram.findall("signalList/*")
            }
            expected = {
                frozenset(
                    (
                        alias(terms(case)[i], ordinal),
                        alias(terms(case)[15 - i], ordinal),
                    )
                )
                for i in range(1, 8)
            }
            require(
                actual == expected and len(actual) == 7,
                "switch arm is no longer seven unchanged pass-through wires",
            )
            require(
                {n.get("class") for n in diagram.findall("nodeList/*")} == {"sRN"}
                and not diagram.findall("zPlaneList/*"),
                "switch arm gained an operation",
            )
            passes.append(
                dict(
                    action=code,
                    diagram=diagram.get("uid"),
                    unchanged_fields=7,
                    direct_wires=[
                        sorted(n) for n in sorted(actual, key=lambda v: sorted(v))
                    ],
                )
            )
        source = graph.field(x1)
        require(
            source["mux_uid"] == source_mux
            and source["raw_index"] == 4
            and source["label_path"] == ["X1/X10"],
            "X1 field identity changed",
        )
        agg_uid = graph.aggregate(source_mux).get("uid")
        unnamed = [
            t
            for t in terms(graph.nodes[source_mux])
            if t.get("uid") != agg_uid and t.findtext("dco/i") is None
        ]
        require(len(unnamed) == 1, "unnamed retained cell field population changed")
        unnamed_port = unnamed[0].get("uid")
        component = wires.component(unnamed_port)
        active_consumers = []
        for port in component:
            owner = graph.owners.get(port)
            if owner is None:
                continue
            if owner.get("class") in (
                "prim",
                "iUse",
                "propNode",
                "sharedVariableDynamicWrite",
            ):
                active_consumers.append(port)
            if owner.get("class") == "select" and terms(owner)[0].get("uid") == port:
                active_consumers.append(port)
        require(
            not active_consumers,
            "unnamed retained Boolean gained a computation/conditional consumer",
        )
        # Check threshold/mask literals and the actual sequence-local-to-gate path.
        cmp_ports, mask_ports = terms(graph.nodes[compare]), terms(graph.nodes[mask])
        require(
            graph.nodes[compare].findtext("primResID") == "1103"
            and graph.nodes[mask].findtext("primResID") == "1061",
            "guard primitives changed",
        )
        require(
            [int(raw, 16) for _, raw in wires.literals(cmp_ports[1].get("uid"))]
            == [128]
            and [int(raw, 16) for _, raw in wires.literals(mask_ports[1].get("uid"))]
            == [1937],
            "switch transfer mask/threshold changed",
        )
        guard_path = wires.path(
            cmp_ports[0].get("uid"), terms(graph.nodes[gate])[0].get("uid")
        )
        forward_source, targets = FORWARD[line]
        graph.mux_local(
            forward_source, "Voie directe" if line == "direct" else "Voie déviée"
        )
        for uid, bank_name in targets.items():
            graph.mux_local(uid, bank_name)
        forward_routes = []
        true_diagram = graph.nodes[gate].findall("diagramList/*")[1]
        for net in true_diagram.findall("signalList/*"):
            ports = [t.get("uid") for t in net.findall("termList/*")]
            sources = [
                p
                for p in ports
                if p in graph.owners and graph.owners[p].get("uid") == forward_source
            ]
            destinations = [
                p
                for p in ports
                if p in graph.owners
                and graph.owners[p].get("uid") in targets
                and graph.is_input(graph.nodes[p])
            ]
            if len(sources) == len(destinations) == 1:
                source_field, target_field = (
                    graph.field(sources[0]),
                    graph.field(destinations[0]),
                )
                require(
                    source_field["label_path"][-1] == "Consigne",
                    "forward source no longer Consigne",
                )
                forward_routes.append(
                    dict(
                        source=source_field,
                        destination=target_field,
                        bank=targets[target_field["mux_uid"]],
                        net=net.get("uid"),
                        target_field_qualified=target_field["raw_index"] is not None,
                    )
                )
        require(
            len(forward_routes) == (11 if line == "direct" else 9),
            "forward route census changed",
        )
        step_paths = []
        for action, _, nested, _, _, _, _, _ in CORRECTOR_BUTTONS[line]:
            for ordinal, diagram in enumerate(
                graph.nodes[nested].findall("diagramList/*")
            ):
                nodes = [
                    n
                    for n in diagram.findall("zPlaneList/*")
                    if n.get("class") == "prim"
                ]
                selectors = [n for n in nodes if n.findtext("primResID") == "1516"]
                if not selectors:
                    continue
                require(len(selectors) == 1, "step selector population changed")
                node = selectors[0]
                ts = terms(node)
                require(
                    [t.findtext("dco/parmIndex") for t in ts[1:]] == ["1", "2", "3"],
                    "explicit Select terminal indices changed",
                )
                false_uid, false_value = scalar_literal(wires, ts[1].get("uid"))
                true_uid, true_value = scalar_literal(wires, ts[3].get("uid"))
                if line == "direct" and ordinal == 0:
                    expected_steps = (
                        (1.0, 10.0) if action in (128, 1024) else (0.1, 1.0)
                    )
                elif line == "direct" and ordinal == 1:
                    expected_steps = (
                        (5.0, 50.0) if action in (128, 1024) else (1.0, 5.0)
                    )
                else:
                    expected_steps = (
                        (0.1, 1.0) if action in (128, 1024) else (0.01, 0.1)
                    )
                require(
                    (false_value, true_value) == expected_steps,
                    "step values/polarity changed",
                )
                group = tuple(
                    row
                    for row in range(11 if line == "direct" else 9)
                    if any(
                        int(r.findtext("start")) <= row <= int(r.findtext("end"))
                        and int(r.findtext("diagramIdx")) == ordinal
                        for r in graph.nodes[nested].findall("SelectRangeArray32/*")
                    )
                )
                require(group == GROUPS[line][ordinal], "step device group changed")
                step_paths.append(
                    dict(
                        action=action,
                        diagram=diagram.get("uid"),
                        row_indices=list(group),
                        select_uid=node.get("uid"),
                        false_step=false_value,
                        true_step=true_value,
                        false_literal=false_uid,
                        true_literal=true_uid,
                        x1_path=wires.path(x1, ts[2].get("uid")),
                    )
                )
        require(
            len(step_paths) == (16 if line == "direct" else 8),
            "step path census changed",
        )
        frame = graph.nodes[seq].findall("diagramList/*")[2]
        publications = []
        for writer in frame.findall("zPlaneList/*"):
            if writer.get("class") != "sharedVariableDynamicWrite":
                continue
            ts = terms(writer)
            uri_uid, uri = url_literal(wires, ts[0].get("uid"))
            names = [
                (graph.names[graph.owners[p].get("uid")], p)
                for p in wires.component(ts[4].get("uid"))
                if p in graph.owners and graph.owners[p].get("class") == "gRef"
            ]
            require(
                len(names) == 1
                and uri == "ni.var.psp://localhost/SUPERVISION/" + names[0][0],
                "publication bank/data identity changed",
            )
            publications.append(
                dict(
                    writer_uid=writer.get("uid"),
                    uri=uri,
                    uri_literal=uri_uid,
                    bank=names[0][0],
                    local_terminal=names[0][1],
                    data_terminal=ts[4].get("uid"),
                )
            )
        require(
            sorted(p["bank"] for p in publications)
            == [f"C{i}NI6703" for i in range(6, 10)],
            "event no longer publishes only the four analog banks",
        )
        all_writers = [
            n.get("uid")
            for n in graph.nodes[seq].iter()
            if n.get("class") == "sharedVariableDynamicWrite"
        ]
        require(
            set(all_writers) == {p["writer_uid"] for p in publications},
            "event gained another PSP writer",
        )
        results[line] = dict(
            sequence_uid=seq,
            selector_uid=case_uid,
            pass_through=passes,
            x1_explicit_field=source,
            step_paths=step_paths,
            transfer_mask=1937,
            transfer_threshold=128,
            guard_path=guard_path,
            switch_only_transfer=False,
            publications=publications,
            publication_frame=frame.get("uid"),
            publication_is_outside_transfer_guard=True,
            omitted_MA_named_index_remains_unqualified=True,
            forward_setpoint_routes=forward_routes,
            unnamed_retained_boolean_port=unnamed_port,
            unnamed_retained_boolean_active_consumers=active_consumers,
        )

    if acq is None:
        acq = checked_vam(ACQ_ARCHIVE)
    bd, meta = acq
    nodes = {n.get("uid"): n for n in bd.iter() if n.get("class")}
    frame = nodes["10115"]
    nets = [
        {t.get("uid") for t in s.findall("termList/*")}
        for s in frame.findall("signalList/*")
    ]
    receivers = []
    for (
        call,
        literal,
        tag,
        read,
        read_port,
        write,
        write_port,
        bank,
        size,
        element,
        ports,
    ) in SITES[:4]:
        uri_raw = bytes.fromhex(constant(frame, literal))
        uri = uri_raw[4:].decode("ascii")
        require(
            uri == "ni.var.psp://10.20.30.2/SUPERVISION/" + tag,
            "ACQ receiver URI changed",
        )
        require(
            any({literal, ports[0]} <= net for net in nets)
            and any({ports[5], write_port} <= net for net in nets),
            "ACQ receive wire changed",
        )
        local(bd, write, write_port, bank, True)
        desc, flat = heap_type(
            meta,
            int(
                nodes[call].findtext(f"termList/*[@uid='{ports[5]}']/dco/typeDesc")[
                    7:-1
                ]
            ),
        )
        require(
            desc.get("Type") == "Cluster"
            and len(desc) == 10
            and all(
                flat[int(t.get("TypeID"))].get("Type") == "NumFloat64" for t in desc
            ),
            "ACQ analog payload shape changed",
        )
        receivers.append(
            dict(
                bank=tag,
                reader_uid=call,
                uri=uri,
                local_bank=bank,
                local_writer_uid=write,
                shape="10 DBL; no M/A or X1/X10 Boolean field",
            )
        )
    # Select only the already documented runtime caller, not startup/stop reruns.
    io = nodes["7386"]
    io_nets = [
        {t.get("uid") for t in s.findall("termList/*")}
        for s in io.findall("signalList/*")
    ]
    call = nodes["278"]
    require(
        call.findtext("label/textRec/text") == '"1_ACQ_WRITE_NI6703.vi"',
        "ACQ runtime writer callee changed",
    )
    runtime = []
    for bank, local_uid, converter, pos in zip(
        range(9, 13),
        ("2388", "2448", "2486", "2494"),
        ("7588", "8669", "8677", "7611"),
        (0, 5, 7, 9),
    ):
        lt, ct, target = (
            terms(nodes[local_uid])[0],
            terms(nodes[converter]),
            terms(call)[pos],
        )
        require(
            lt.findtext("dco/paramIdx") == str(bank)
            and nodes[converter].findtext("primResID") == "1169"
            and any({lt.get("uid"), ct[1].get("uid")} <= n for n in io_nets)
            and any({ct[0].get("uid"), target.get("uid")} <= n for n in io_nets),
            "ACQ runtime bank-to-writer edge changed",
        )
        runtime.append(
            dict(
                local_bank=bank,
                local_uid=local_uid,
                cluster_to_array_uid=converter,
                call_uid="278",
                call_terminal=target.get("uid"),
                raw_connector_index=target.findtext("dco/paramIdx"),
            )
        )
    line_signaling = [
        n.get("uid")
        for n in bd.iter()
        if n.get("class") == "propNode"
        and n.find("ddo") is not None
        and n.find("ddo").get("uid") in ("1660", "16917")
        and any(
            p.text == '"Val(Sgnl)"'
            for p in n.findall("termList/*/dco/propList/*/PropItemName")
        )
    ]
    require(not line_signaling, "ACQ gained a line signaling writer; examine new path")
    return dict(
        source_vi_sha256=SOURCE_SHA,
        source_inputs=receipt["xml"],
        lines=results,
        acq_archive=str(ACQ_ARCHIVE),
        acq_archive_sha256=ARCHIVE_SHA256,
        acq_receivers=receivers,
        acq_runtime_writer=runtime,
        explicit_named_MA_read_ports=explicit_ma_reads,
        acq_explicit_line_signaling_writers=line_signaling,
        whole_cluster_helpers=check_whole_cluster_helpers(),
        select_semantics_reference="https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/select.html",
        lvkit_select_metadata_sha256=hashlib.sha256(
            COMPARISON.read_bytes()
        ).hexdigest(),
        findings=[
            "M/A-only and X1/X10-only changes preserve seven retained cell fields "
            "and do not transfer new analog setpoints.",
            "For a single arrow event the retained M/A Boolean is not an enable "
            "condition for the adjustment or frame-1 transfer guard.",
            "Both events still republish C6-C9; this is real write intent, "
            "not a no-traffic assertion.",
            "X1/X10 explicitly drives Select: False chooses the smaller literal, "
            "True the larger; 24 source paths checked.",
            "No separate M/A start/stop or X1/X10 mode field is sent "
            "to Acquisition by these events.",
            "Acquisition receives the analog banks into locals9-12 and separately "
            "reads those locals into runtime NI6703 call278.",
        ],
        limits=[
            "This closes the selected saved event/receiver/caller trace, "
            "not deployed-source equality or native execution.",
            "M/A omitted named-field indices are not normalized to zero. "
            "All seven fields pass unchanged regardless of "
            "that unresolved label binding.",
            "No assertion that M/A can start a supply: an independent start/stop "
            "command path was not found in these event handlers.",
            "Whole-cluster helpers have no calls/transport nodes; their native "
            "ABI/local-value semantics are not promoted by this census.",
            "External VI Server clients, races, property failures, coalesced "
            "multi-control changes and cross-loop read epochs "
            "remain outside this trace.",
            "Two forward Bundle target indices are omitted; their banks and "
            "wires are known, but no zero-index default or native equivalence "
            "is invented for them.",
            "The root has no explicit named M/A scalar read index; omitted-index "
            "Boolean cell ports and whole-cluster consumers are not classified "
            "by that census. Absence is not proof about external clients.",
            "Acquisition runtime is a different loop; last accepted command "
            "is not a physical acknowledgement.",
        ],
        hardware_io=False,
        network_io=False,
        vi_run_or_save=False,
        deployment=False,
        complete_controller_equivalence=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--refresh-owned-report", action="store_true")
    args = parser.parse_args()
    result = build_trace()
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")),
            "saved switch trace differs",
        )
    else:
        require(
            not OUTPUT.exists() or args.refresh_owned_report,
            "trace exists; review before replacement",
        )
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8"
        )
    print(
        json.dumps(
            dict(
                checked=args.check, output=str(OUTPUT), step_paths=24, hardware_io=False
            )
        )
    )


if __name__ == "__main__":
    main()
