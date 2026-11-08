"""Original Main cooperative-stop and cleanup proof, without executing a VI.

Checks every runtime loop in Main. Callee-internal cancellation, native resource
release and physical safe states remain outside this static qualification.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from export_sup_beam_indicator_routes import (
    BASELINE,
    BASELINE_SHA,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, digest, original
from trace_sup_beam_switches import (
    COMPARISON,
    COMPARISON_SHA,
    Wires,
    terms,
    url_literal,
)
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

OUTPUT = REPO / "Supervision/integration_analysis/normal_stop_20261017/RESULT.json"
OUTER = {
    "17671": ("timed monitoring", "15290", "15304", "17961", "38219"),
    "6017": ("event dispatch", "11786", "14053", "6080", "11791"),
    "5846": ("periodic PSP/UI processing", "26092", "26099", "6059", "3683"),
    "5841": ("camera processing", "21235", "21242", "6039", "21395"),
}
MOTOR = {
    "95809": ("96014", "96017", "95850"),
    "266207": ("266408", "266411", "266244"),
    "89716": ("92738", "92746", "89729"),
    "89775": ("89837", "89849", "89805"),
    "91149": ("91192", "91195", "91178"),
    "82586": ("83448", "83451", "187540"),
    "40191": ("114357", "114364", "101992"),
}
FOR_LOOPS = {"42544", "7742", "33677", "1195", "274199", "115256"}
WAIT_WRITERS = {
    "57122": ("57172", False),
    "14709": ("14803", False),
    "16708": ("18376", True),
    "92224": ("92202", True),
    "58781": ("61608", False),
    "14418": ("12976", True),
    "95369": ("95359", False),
    "72350": ("72358", True),
    "72251": ("72125", False),
}
PICTURES = {
    "0_SUP_ELYSE_front_panel_full.png": (
        "8DB4F2C6EC79A4C16E790885AA9BCF285B455846F501C40719BB72211ABCB5C0"
    ),
    "0_SUP_ELYSE_outer_frame_2_full.png": (
        "654E0427A5D0038A5B564F1A7AAFC7BC3A8D09F1AF90BA69ECFE7026295BE5F1"
    ),
    "0_SUP_ELYSE_outer_frame_3_full.png": (
        "86A2D09FF76648DAB97A62EE7C55BFF61E15DEA4F0BE0E51B6F6E639367DC726"
    ),
    "0_SUP_ELYSE_outer_frame_2_camera_sequence_frame_09_full.png": (
        "E99E475100049DD39BEFC0B82AE24B812EEFD9A692228F9D8265CF084ABACD6A"
    ),
}
PREVIOUS = {
    "simple_error_handler_stop_20261017/RESULT.json": (
        "3AA7E2E8130356339F93D0A7E30747DD539C63DCC56FA70B1B0386359274B09F"
    ),
    "psp_journals_stop_20261017/RESULT.json": (
        "909D63EC5A8E6E62E7EA85A8AD1553CAC80B61FCDA7AEA1B6A83B19B45670AB6"
    ),
}


def loop_mode(node):
    flags = int(node.findtext("loopTestDCO/objFlags") or "0")
    return "stop-if-true" if flags & 0x10000 else "continue-if-true"


def local_port(g, uid, name, write=False):
    n = g.nodes[uid]
    require(n.get("class") == "gRef" and g.names.get(uid) == name, f"wrong local {uid}")
    ts = terms(n)
    require(
        len(ts) == 1 and g.is_input(ts[0]) == write, f"local direction changed: {uid}"
    )
    return ts[0].get("uid")


def bool_constant(g, uid, value):
    n = g.nodes[uid]
    raw = n.findtext("dco/ConstValue")
    require(
        raw is not None and int.from_bytes(bytes.fromhex(raw), "big") == int(value),
        f"Boolean literal changed: {uid}",
    )
    desc = g.table.heap(n.findtext("dco/typeDesc"))
    require(desc.get("Type") == "Boolean", "Boolean literal type changed")


def error_status(g, aggregate, status):
    cluster = g.table.heap(g.nodes[aggregate].findtext("dco/typeDesc"))
    scalar = g.table.heap(g.nodes[status].findtext("dco/typeDesc"))
    require(
        cluster.get("Type") == "Cluster"
        and cluster.get("Label") == "error out"
        and [f["type"] for f in g.table.fields(cluster)]
        == ["Boolean", "NumInt32", "String"]
        and scalar.get("Type") == "Boolean"
        and scalar.get("Label") == "status",
        "error-status unbundle type changed",
    )


def or_dependency(g, source, target, seen=None):
    """Find a Boolean influence through exact saved wires and OR nodes only.

    Never joins Case alternatives, local reads at different times or arbitrary
    primitive input/output pairs. Non-OR predicate branches are left opaque.
    """
    if source == target:
        return []
    seen = set() if seen is None else seen
    if target in seen:
        return None
    seen = seen | {target}
    nets = [(uid, ps) for uid, ps in g.nets if target in ps and ps[0] != target]
    if len(nets) != 1:
        return None
    net, ports = nets[0]
    producer = ports[0]
    edge = {"kind": "wire", "uid": net, "from": producer, "to": target}
    if producer == source:
        return [edge]
    owner = g.owners.get(producer)
    if (
        owner is None
        or owner.get("class") != "prim"
        or owner.findtext("primResID") != "1062"
    ):
        return None
    for t in terms(owner):
        if not g.is_input(t):
            continue
        before = or_dependency(g, source, t.get("uid"), seen)
        if before is not None:
            return before + [
                {
                    "kind": "OR",
                    "uid": owner.get("uid"),
                    "from": t.get("uid"),
                    "to": producer,
                },
                edge,
            ]
    return None


def cooperative_witness(stop_samples, *, wait_held=False, motion_pending=False):
    """Supplied-state witness only; no scheduler, UI event or native call.

    Samples are one per outer-loop condition, after the fabricated iteration
    finishes. A stuck child prevents its containing outer body from completing.
    """
    if (
        not isinstance(stop_samples, tuple)
        or len(stop_samples) != 4
        or any(type(v) is not bool for v in stop_samples)
        or type(wait_held) is not bool
        or type(motion_pending) is not bool
    ):
        raise ValueError(
            "four explicit Boolean samples and Boolean child states required"
        )
    completed = tuple(
        v and not blocked
        for v, blocked in zip(
            stop_samples, (False, motion_pending, False, wait_held), strict=True
        )
    )
    eligible = all(completed)
    return {
        "outer_bodies_finished_and_stop_seen": completed,
        "cleanup_frame_eligible": eligible,
        "cleanup_success_proven": False,
        "effects_executed": False,
    }


def verify(receipt=None, roots=None):
    if receipt is None:
        receipt, roots = original()
    require(digest(BASELINE) == BASELINE_SHA, "frozen baseline changed")
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    w = Wires(g)
    frames = [d.get("uid") for d in g.nodes["988"].findall("diagramList/*")]
    require(
        frames == ["1034", "5807", "5902", "14127", "41997"],
        "lifecycle frame order changed",
    )

    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    require(
        g.nodes["6061"].find("dco").get("uid") == "6042"
        and fp["6042"].get("class") == "fPDCO"
        and fp["6042"].find("ddo").get("uid") == "6015",
        "stop control binding changed",
    )
    require(
        fp["6015"].findtext("partsList/*[@class='label']/textRec/text") == '"stop"'
        and fp["6015"].findtext("partsList/*[@class='multiLabel']/textRec/text")
        == '"STOP"',
        "STOP caption changed",
    )
    require(not any("6061" in ps for _, ps in g.nets), "stop FP terminal gained a wire")
    refs = [
        n
        for n in g.nodes.values()
        if n.get("class") == "gRef" and n.findtext("termList/*/dco/paramIdx") == "49"
    ]
    require(
        {n.get("uid") for n in refs}
        == {"15290", "11786", "26092", "21235", "26296", "12664"},
        "stop local census changed",
    )
    writers = [n.get("uid") for n in refs if g.is_input(terms(n)[0])]
    require(writers == ["12664"], "stop gained a program writer")
    local_port(g, "12664", "stop", True)
    bool_constant(g, "12839", False)
    exact_net(g, "12845", ["12839", "12688"])
    require("14127" in g.ancestry("12664"), "stop reset left cleanup")
    bound_refs = [
        n.get("uid")
        for n in g.nodes.values()
        if n.get("class") in ("propNode", "ctlRefConst")
        and n.find("ddo") is not None
        and n.find("ddo").get("uid") in ("6042", "6015")
    ]
    require(not bound_refs, "stop gained a statically bound property/reference")

    specs = [
        {e.tag: e.text for e in s} for s in g.nodes["5909"].findall("EventNodeEvents/*")
    ]
    require(
        len(specs) == 38 and all(s["ddoUID"] not in ("6042", "6015") for s in specs),
        "STOP gained an event registration",
    )
    require(
        g.nodes["5960"].findtext("dco/ConstValue") == "00000050",
        "event timeout changed",
    )
    exact_net(g, "5964", ["5960", "5934"])
    event_frames = [d.get("uid") for d in g.nodes["5909"].findall("diagramList/*")]

    outer = []
    for loop, (name, reader, src, test, net) in OUTER.items():
        n = g.nodes[loop]
        require(
            g.ancestry(loop)[0] == "5902" and loop_mode(n) == "stop-if-true",
            "outer runtime loop boundary/polarity changed",
        )
        require(
            local_port(g, reader, "stop") == src
            and n.find("loopTestDCO/termList/*").get("uid") == test,
            "outer stop port changed",
        )
        require(
            g.ancestry(reader)[0] == n.find("diagramList/*").get("uid"),
            "stop sample gained an inner-sequence ordering",
        )
        exact_net(g, net, [src, test])
        outer.append(
            {
                "loop": loop,
                "name": name,
                "stop_reader": reader,
                "source_port": src,
                "test_port": test,
                "wire": net,
                "stop_if_true": True,
                "iteration_must_finish": True,
            }
        )

    loops = {
        uid: n
        for uid, n in g.nodes.items()
        if n.get("class") in ("whileLoop", "timeLoop", "forLoop")
        and "5902" in g.ancestry(uid)
    }
    require(
        set(loops) == set(OUTER) | set(MOTOR) | FOR_LOOPS | {"80242", "21949", "6584"},
        "runtime loop census changed",
    )
    loop_rows = []
    for uid, n in loops.items():
        ancestry = g.ancestry(uid)
        local_refs = [
            [r.get("uid"), g.names.get(r.get("uid"))]
            for r in refs
            if uid in g.ancestry(r.get("uid")) and not g.is_input(terms(r)[0])
        ]
        test = n.find("loopTestDCO/termList/*")
        loop_rows.append(
            {
                "loop": uid,
                "class": n.get("class"),
                "event": next(
                    (i for i, f in enumerate(event_frames) if f in ancestry), None
                ),
                "stop_local_reads_within_body": local_refs,
                "test_port": None if test is None else test.get("uid"),
                "mode": "counted" if test is None else loop_mode(n),
            }
        )
    for loop in FOR_LOOPS:
        require(
            loops[loop].get("class") == "forLoop"
            and loops[loop].find("loopTestDCO") is None,
            "counted loop gained a cancellation terminal",
        )

    # Seven motion/autotune loops depend on stop motor, NOT on Main stop.
    motor = []
    for loop, (reader, src, test) in MOTOR.items():
        require(
            local_port(g, reader, "stop motor") == src, "motor stop binding changed"
        )
        require(
            loop in g.ancestry(reader) and loop_mode(loops[loop]) == "stop-if-true",
            "motor loop scope/polarity changed",
        )
        route = or_dependency(g, src, test)
        require(route, "stop motor lost its OR influence on loop termination")
        require(
            not any(loop in g.ancestry(r.get("uid")) for r in refs),
            "motor loop now reads global stop",
        )
        motor.append(
            {"loop": loop, "reader": reader, "port": src, "test": test, "route": route}
        )
    # Full straight-line predicate for forward/reverse motion polling.
    for uid in ("95900", "95880", "266294", "266274"):
        require(g.nodes[uid].findtext("primResID") == "1062", "motion OR changed")
    for net, ports in (
        ("96147", ["96017", "95913", "95905"]),
        ("96168", ["95882", "95908"]),
        ("96177", ["95896", "95885"]),
        ("96171", ["96059", "95888"]),
        ("266542", ["266411", "266307", "266299"]),
        ("266563", ["266276", "266302"]),
        ("266572", ["266290", "266279"]),
        ("266566", ["266457", "266282"]),
    ):
        exact_net(g, net, ports)
    error_status(g, "95893", "95896")
    error_status(g, "266287", "266290")

    # Camera retry notices stop; the separate Wait loop does not.
    require(
        loop_mode(loops["21949"]) == loop_mode(loops["6584"]) == "continue-if-true",
        "camera inner-loop polarity changed",
    )
    require(
        local_port(g, "26296", "stop") == "26305"
        and g.nodes["26598"].findtext("primResID") == "1064"
        and g.nodes["26998"].findtext("primResID") == "1061",
        "camera retry gate changed",
    )
    error_status(g, "22255", "22368")
    for net, ports in (
        ("26613", ["26305", "26607"]),
        ("6984", ["26604", "27018"]),
        ("27704", ["22368", "27021"]),
        ("27696", ["27004", "21983"]),
        ("6569", ["15806", "20770"]),
        ("14308", ["14274", "14304"]),
    ):
        exact_net(g, net, ports)
    require(
        local_port(g, "15754", "Wait") == "15806"
        and g.nodes["14274"].findtext("dco/ConstValue") == "00000032"
        and g.nodes["14299"].findtext("primResID") == "1302",
        "Wait loop changed",
    )
    require(
        not any("6584" in g.ancestry(r.get("uid")) for r in refs),
        "Wait loop gained a global stop read",
    )
    require(
        g.nodes["57073"].findtext("dco/ConstValue") == "000004B0"
        and g.nodes["55105"].findtext("primResID") == "1110",
        "iteration-comparison constant/operator changed",
    )
    require(
        digest(COMPARISON) == COMPARISON_SHA, "qualified comparison definitions changed"
    )
    greater = json.loads(COMPARISON.read_text("utf-8"))["primitives"]["1110"]
    require(
        greater["python_code"] == {"result": "in_2 > in_1"}
        and g.nodes["55137"].findtext("dco/parmIndex") == "1"
        and g.nodes["55159"].findtext("dco/parmIndex") == "2",
        "comparison operand order changed",
    )
    exact_net(g, "57077", ["57073", "55137"])
    exact_net(g, "55178", ["80259", "55159"])
    require(
        g.nodes["80242"].find("loopIndexDCO").get("uid") == "80257"
        and g.owners["80259"].get("uid") == "80257"
        and or_dependency(g, "55123", "80262"),
        "counter-limit route changed",
    )
    require(
        g.nodes["54545"].findtext("primResID") == "1302", "counter loop Wait changed"
    )
    exact_net(g, "81042", ["56493", "54561"])
    counter_wait_ms = int.from_bytes(
        bytes.fromhex(g.nodes["56493"].findtext("dco/ConstValue")), "big"
    )

    wait_writes = []
    all_wait_writers = {
        uid
        for uid, n in g.nodes.items()
        if n.get("class") == "gRef"
        and g.names.get(uid) == "Wait"
        and g.is_input(terms(n)[0])
    }
    require(all_wait_writers == set(WAIT_WRITERS), "Wait writer census changed")
    for uid, (literal, value) in WAIT_WRITERS.items():
        port = local_port(g, uid, "Wait", True)
        bool_constant(g, literal, value)
        path = w.path(literal, port)
        require("14127" not in g.ancestry(uid), "Wait clear moved into cleanup")
        wait_writes.append(
            {
                "writer": uid,
                "literal": literal,
                "value": value,
                "event": next(
                    (i for i, f in enumerate(event_frames) if f in g.ancestry(uid)),
                    None,
                ),
                "path": path,
            }
        )

    # Reproduce resource chains, but do not claim native closes succeeded.
    cleanup = g.nodes["14127"]
    require(
        not any(n.get("class") == "sharedVariableDynamicWrite" for n in cleanup.iter()),
        "cleanup gained a PSP state-reset publisher",
    )
    require(
        len(terms(g.nodes["6334"])) - 1 == 13 and len(terms(g.nodes["22201"])) - 1 == 9,
        "cleanup array sizes changed",
    )
    close_targets = [
        url_literal(w, t.get("uid"))[1] for t in terms(g.nodes["6334"]) if g.is_input(t)
    ]
    prefix = "ni.var.psp://localhost/SUPERVISION/"
    require(
        close_targets
        == [
            prefix + bank
            for bank in (
                "C1NI6071E",
                "C2NI6071E",
                "C3_IN_DIO96",
                "C3_OUT_DIO96",
                "C4_IN_DIO96",
                "C4_OUT_DIO96",
                "C5_IN_DIO96",
                "C5_OUT_DIO96",
                "C6NI6703",
                "C7NI6703",
                "C8NI6703",
                "C9NI6703",
                "MARA",
            )
        ],
        "explicit close target list changed",
    )
    runtime_urls = {}
    for uid, n in g.nodes.items():
        if n.get("class") not in (
            "sharedVariableDynamicRead",
            "sharedVariableDynamicWrite",
        ):
            continue
        if "5902" not in g.ancestry(uid):
            continue
        found = set()
        for t in terms(n):
            if not g.is_input(t):
                continue
            for _, raw in w.literals(t.get("uid")):
                value = bytes.fromhex(raw)
                if value[4:].startswith(b"ni.var.psp:"):
                    require(
                        int.from_bytes(value[:4], "big") == len(value) - 4,
                        "runtime URI encoding changed",
                    )
                    found.add(value[4:].decode("ascii"))
        require(len(found) == 1, "runtime PSP URI binding missing/ambiguous")
        url = found.pop()
        runtime_urls.setdefault(url, []).append(uid)
    missing_close = sorted(set(runtime_urls) - set(close_targets))
    require(
        len(runtime_urls) == 24
        and missing_close
        == sorted(
            prefix + bank
            for bank in (
                "VAD",
                "VDD",
                "DPS",
                "DPC",
                "C1011NI6602",
                "VTS",
                "VTA",
                "VTL",
                "VAM-A",
                "EPC",
                "EPS",
                "VDM-A",
            )
        ),
        "PSP resource coverage changed",
    )
    require(
        [
            uid
            for uid, n in g.nodes.items()
            if n.get("class") == "prim" and n.findtext("primResID") == "23783"
        ]
        == ["14463"],
        "Main PSP close sites changed",
    )
    require(
        g.nodes["14463"].findtext("primResID") == "23783", "PSP close primitive changed"
    )
    require(
        g.nodes["12555"].find("dco").get("class") == "lSR"
        and not any("12555" in ps for _, ps in g.nets),
        "PSP close register gained an initializer",
    )
    for net, ports in (
        ("6131", ["7438", "14471"]),
        ("11856", ["12554", "14468"]),
        ("11792", ["14465", "11937"]),
        ("282", ["12552", "14522"]),
        ("26734", ["26728", "26396"]),
        ("24671", ["24664", "22905"]),
        ("22219", ["19088", "22908"]),
        ("22375", ["26394", "22920"]),
        ("23265", ["22911", "26385"]),
        ("23665", ["26390", "22950"]),
        ("11757", ["22926", "23029"]),
        ("177516", ["189901", "192419"]),
        ("177509", ["192407", "194938"]),
    ):
        exact_net(g, net, ports)
    bool_constant(g, "24664", True)
    require(
        set(bytes.fromhex(g.nodes["26728"].findtext("dco/ConstValue"))) == {0},
        "image-disposal initial error cluster changed",
    )
    cleanup_calls = {
        uid: g.nodes[uid].findtext("label/textRec/text")
        for uid in ("14492", "22899", "22923", "22962", "177515", "192398", "194898")
    }
    require(
        cleanup_calls
        == {
            "14492": '"Simple Error Handler.vi"',
            "22899": '"IMAQ Dispose"',
            "22923": '"IMAQ Close.vi"',
            "22962": '"General Error Handler.vi"',
            "177515": '"AbortMotion.vi"',
            "192398": '"Shutdown.vi"',
            "194898": '"General Error Handler.vi"',
        },
        "cleanup callees changed",
    )
    require(
        all("14127" in g.ancestry(uid) for uid in cleanup_calls), "callee left cleanup"
    )

    # Preserve earlier qualifications rather than rerunning their entire work.
    previous = []
    for relative, sha in PREVIOUS.items():
        p = REPO / "Supervision/integration_analysis" / relative
        require(digest(p) == sha, "previous error/cleanup proof changed")
        previous.append({"path": str(p.relative_to(REPO)), "sha256": sha})
    pictures = []
    for name, sha in PICTURES.items():
        p = REPO / "Supervision/analysis/screenshots" / name
        require(digest(p) == sha, "saved screenshot changed")
        pictures.append({"path": str(p.relative_to(REPO)), "sha256": sha})
    return {
        "scope": (
            "Every runtime loop of pinned original Main, cooperative stop "
            "and frame3 cleanup"
        ),
        "source": {
            "VI": receipt["source"],
            "sha256": receipt["sha256"],
            "xml": receipt["xml"],
        },
        "observations": {
            "lifecycle_frames": frames,
            "stop_control": {
                "control": "6042",
                "ddo": "6015",
                "label": "stop",
                "caption": "STOP",
                "Main_local_bank": 49,
                "unused_FP_terminal": "6061",
                "program_True_writers": [],
                "sole_program_writer": {
                    "uid": "12664",
                    "value": False,
                    "frame": "14127",
                },
                "statically_bound_property_writers": bound_refs,
            },
            "event_registrations": specs,
            "STOP_event_registered": False,
            "event_timeout_ms": 80,
            "outer_loops": outer,
            "runtime_loop_census": loop_rows,
            "loop_class_counts": dict(Counter(n.get("class") for n in loops.values())),
            "motor_stop_routes": motor,
            "motion_poll_exit": (
                "stop motor OR Boolean from motion error cluster "
                "OR GetMotionDone result"
            ),
            "camera_retry": {
                "loop": "21949",
                "continue_when": "NOT stop AND Boolean from setup error cluster",
            },
            "camera_wait": {
                "loop": "6584",
                "continue_when": "Wait",
                "sleep_ms": 50,
                "checks_global_stop": False,
            },
            "Wait_writers": wait_writes,
            "other_nested_loop": {
                "loop": "80242",
                "iteration_cap_predicate": "i >1200",
                "max_completed_iterations_without_earlier_exit": 1202,
                "wait_ms_per_iteration": counter_wait_ms,
                "checks_global_stop": False,
                "remaining_predicates_not_newly_interpreted": True,
            },
            "cleanup": {
                "frame": "14127",
                "requires_runtime_frame_completion": True,
                "PSP_close_loop": "11851",
                "PSP_URL_count": 13,
                "PSP_close_target_URLs": close_targets,
                "runtime_PSP_URL_sites": runtime_urls,
                "runtime_PSP_URLs_not_in_explicit_close_array": missing_close,
                "Main_PSP_close_primitive_sites": ["14463"],
                "PSP_initial_error_shift_register_not_wired": True,
                "image_disposal_loop": "21424",
                "image_count": 9,
                "image_disposal_all": True,
                "initial_image_error_cluster_zero": True,
                "addressed_AbortMotion_then_Shutdown": ["177515", "192398"],
                "handler_calls": ["14492", "22962", "194898"],
                "independent_group_order": "no total order",
                "stop_False_reset_ordered_after_resource_closes": False,
                "Main_PSP_zeroing_or_shutdown_writes": [],
            },
        },
        "inferences": [
            "The ordinary request is the front-panel STOP control value read "
            "by Main locals. There is no Main program writer setting it True, "
            "no STOP event callback and no statically bound property writer "
            "to this control. Operator/UI is a source; external VI Server or "
            "dynamic name-based control writers are not excluded.",
            "Each of four outer runtime loops exits only after its current "
            "body finishes and its conditional terminal sees stop=True. The "
            "stop read has no explicit dependency ordering it after that "
            "loop's sequence/event work, so its sample can be older than the "
            "user's latest request. Current work is not cancelled.",
            "The event Timeout constant is 80 ms, not a global shutdown "
            "deadline. Busy event cases, modal handlers, motion polling, UI "
            "locking and native calls can delay completion. A queued action "
            "is not automatically flushed by STOP.",
            "Seven motion/autotune while loops use separate stop motor in "
            "their OR conditions, not Main stop. Forward/reverse polling "
            "also exits on motion-done or its Boolean error-cluster output. "
            "Pending motion without either exit condition can keep the "
            "enclosing event loop from finishing despite Main STOP.",
            "The camera setup/retry loop explicitly includes NOT stop. The "
            "separate camera Wait loop continues while Wait=True, sleeping "
            "50 ms, without any stop read. Wait is set/cleared by "
            "initialization and event24/25/30 sequences; normal STOP does "
            "not itself clear it. This is a distinct cooperative-stop gap.",
            "The remaining event3 nested loop80242 has i>1200 OR another predicate, "
            "so it ends by completed iteration index1201 even if the other predicate "
            "stays False. This bounds completed iteration count, not wall-clock time "
            "or response to STOP; all body operations still have to return.",
            "All twenty runtime loops of Main are enumerated: four "
            "top-level, ten nested conditional loops and six counted loops. "
            "Counted loops have no cancellation terminal and must finish "
            "their bodies. Callee-internal loops are not thereby qualified "
            "or guaranteed to return.",
            "Frame3 becomes eligible only when the entire runtime frame2 "
            "has completed. If all four outer loops return, it attempts "
            "thirteen PSP closes, nine image disposals and IMAQ Close, and "
            "addressed AbortMotion followed by Shutdown. These are three "
            "independent chains, not one ordered shutdown transaction.",
            "The explicit close array is not a complete runtime PSP inventory: "
            "Main uses twenty-four distinct saved runtime URLs, while twelve "
            "of them are absent from its thirteen-target close array. MARA is "
            "in the close list but not this runtime-site census. This is an "
            "explicit-cleanup coverage gap, not proof of a native leak: "
            "automatic connection reclamation remains unqualified.",
            "The stop=False reset runs independently inside frame3, not "
            "after successful resource release. A released STOP button is "
            "therefore not a cleanup-success acknowledgement. A failed "
            "native close or a waiting error dialog can leave partial "
            "cleanup. The PSP close error register has no explicit "
            "initializer.",
            "Normal application exit is not an emergency hardware shutdown. "
            "Main cleanup has no PSP state-zeroing publication and does not "
            "establish Acquisition card safe outputs. The addressed motor "
            "AbortMotion is a different, limited action.",
        ],
        "unknown_or_requires_further_evidence": [
            "Actual front-panel mechanical action, OS/UI event locking, "
            "deployed source identity, native operation timeouts and "
            "measured shutdown latency were not tested.",
            "Saved camera sequence frame08/09 filenames are misleading: "
            "their displayed camera selector is 0[0..9], not Wait frame9. "
            "They cannot visually certify the Wait-loop path; that path "
            "is supported here by pinned source XML only.",
            "The other predicate ORed with i>1200 in nested loop80242, "
            "and automatic "
            "reclamation/closure of every resource acquired inside every "
            "callee, are not "
            "newly established. No guaranteed full-release or full-Supervision claim.",
            "Motion-done/error values and Wait persistence witnesses are "
            "supplied states, not observations that a hang or unsafe "
            "hardware state occurred on the machine.",
        ],
        "previous_proofs": previous,
        "saved_screenshots": pictures,
        "screen_used": False,
        "VI_run_or_save": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
        "all_runtime_Main_loops_enumerated": True,
        "all_stop_paths_finish_cleanup_guaranteed": False,
        "hardware_safe_state_proven": False,
        "full_Supervision_coverage": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.check:
        require(result == json.loads(OUTPUT.read_text("utf-8")), "saved result differs")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({"passed": True, "output": str(OUTPUT), "sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
