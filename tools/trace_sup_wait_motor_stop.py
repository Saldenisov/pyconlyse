"""Static Wait/motor cancellation proof for saved Supervision, never a controller.

Loads pinned local XML, compares saved Print fragments and tests supplied-state
counterexamples. No LabVIEW execution, UI, network, device or production edits.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET

from export_sup_beam_indicator_routes import (
    BASELINE,
    BASELINE_SHA,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, digest, original
from trace_sup_beam_switches import Wires, terms
from trace_sup_normal_stop import (
    MOTOR,
    WAIT_WRITERS,
    bool_constant,
    local_port,
    loop_mode,
    or_dependency,
)
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

OUTPUT = REPO / "Supervision/integration_analysis/wait_motor_stop_20261017/RESULT.json"
PREVIOUS = REPO / "Supervision/integration_analysis/normal_stop_20261017/RESULT.json"
PREVIOUS_SHA = "713FCFC90073EBB4212FF5927624A54945B8D5D076C941E67960CD87BED321BC"
MOTOR_RECEIPT = (
    REPO / "Supervision/analysis/lvkit_eval/parser_motor_release_20261003/receipt.json"
)
MOTOR_RECEIPT_SHA = "1A8B1ED604D2D1365981973F9C89D9D542161753B6C1A274AC89448A9BA17825"
MAIN_RESETS = {
    "683300": ("683214", "5807", "initialization"),
    "96347": ("96325", "96319", "after forward-motion loop"),
    "266868": ("266818", "266812", "after reverse-motion loop"),
    "125466": ("92793", "92784", "after entire autotune loop"),
}
CALLEE_RESETS = {
    "4609": ("4534", "3904", "4517"),
    "6193": ("2427", "2253", "2338"),
    "2803": ("2766", "2016", "2757"),
    "3720": ("3684", "2994", "3678"),
}
CALLEE_LOOPS = {
    "3937": ("4142", "4145", "3978"),
    "493": ("1620", "1628", "2543"),
    "2051": ("2279", "2282", "2092"),
    "3061": ("3355", "3358", "3103"),
}
CALLEE_PREDICATES = {
    "3937": ("4021", "4024", "4213", "4163"),
    "493": ("2586", "2589", "7875", "7817"),
    "2051": ("2145", "2152", "2329", "2295"),
    "3061": ("3206", "3212", "3404", "3371"),
}
CALLS = {
    "102481": ("89849", "102578"),
    "35769": ("89849", "105915"),
    "36633": ("91195", "114222"),
    "116973": ("91195", "117000"),
    "99649": ("83451", "99676"),
    "71114": ("83451", "71145"),
    "36234": ("114364", "111463"),
    "108635": ("114364", "108662"),
}
CAMERA_FLATS = {
    "14231": ["14238", "14015", "16569", "14295"],
    "92850": ["92192", "92246", "72813", "92365", "92623"],
    "11854": ["12112", "15494", "19514", "28873", "33640", "93699", "51619", "89915"],
    "35260": ["87833", "36918", "71311", "71492", "71727", "71958", "79366", "82635"],
}
ERROR_GUARDS = {
    "92709": ("92711", "92444", "92728", "92791", "58781", "92829"),
    "95344": ("95346", "38588", "95353", "95378", "95369", "95417"),
    "72028": ("72033", "71788", "72044", "72290", "72251", "72329"),
}
PICTURES = {
    "0__SUP__ELYSEd400.png": (
        "FA676462658061CC31E681E831154B1E174C797234A73136DD6ADBD56A1C5811"
    ),
    "0__SUP__ELYSEd403.png": (
        "6D9FA82FBECF601AE50DA188EA0321724FFD0B3D0693FE328D8AAA3B39A14DA0"
    ),
    "0__SUP__ELYSEd404.png": (
        "207DF28578F7A307305CBE384DC4A8C5D7D57173BF70C98F56DCBAFF76E6ED03"
    ),
    "0__SUP__ELYSEd405.png": (
        "D9F8823EC050FAE305B45EDD8B62DF9C9F044690CA741EA8B2C2605CA6678477"
    ),
    "0__SUP__ELYSEd418.png": (
        "BC50744B13B808C3B587C2D0A393D957FD28E1DD3ED139BB0E931B38F8A55CE1"
    ),
    "0__SUP__ELYSEd420.png": (
        "9E54CE955B025E963C49439E654772F9F589F8F40423BF518DB90281F845D80D"
    ),
    "0__SUP__ELYSEd421.png": (
        "05E6526EFE564AC7F92FC4575E30023E734587FF11D669E2637FCC86C9E7F93C"
    ),
    "0__SUP__ELYSEd427.png": (
        "83416EADDBED4853F05FABCC9270FA05E23E4D302CBE6B9D8859909F691B141A"
    ),
    "0__SUP__ELYSEd430.png": (
        "962429969DD9ED3C890DB716998C5020BC1C9316C79390CE0AA26F11F5406238"
    ),
    "0__SUP__ELYSEd438.png": (
        "45BB2334E1C9DD3F646E421EF3F5B0AA4E41D3760549996A60E937789F6ED40D"
    ),
    "0__SUP__ELYSEd439.png": (
        "EA2ACA17BCE80492CC5409B4ADDE2F247B7C1F4C062EA42EBEEB447D87B2434D"
    ),
    "0__SUP__ELYSEd451.png": (
        "8B045372C5B9D3B2AF59B9B8173176D6D117E88A30A99A092AC530CA47AFD592"
    ),
    "0__SUP__ELYSEd464.png": (
        "78CCDBBA891D8FA3AC716E2E689A558B0E7192B550660EEC82765EF82CD3C811"
    ),
    "Moteurs_SdC_GoTod.png": (
        "A5BBDE8A27FB04469E16E148E88801958EEA5122F68CAB8BD5355615BF6AF02F"
    ),
    "Moteurs_SdC_GoTod16.png": (
        "CF451ED7FEBA316211A76AAA5E56D68A17BAE96D805602DAEBCC5CBC74D7A97A"
    ),
}


def motor_original():
    require(digest(MOTOR_RECEIPT) == MOTOR_RECEIPT_SHA, "motor receipt changed")
    receipt = json.loads(MOTOR_RECEIPT.read_text("utf-8"))
    require(digest(receipt["source"]) == receipt["sha256"], "motor source changed")
    roots = {}
    for key, row in zip(("bd", "fp", "meta"), receipt["xml"], strict=True):
        require(digest(row["path"]) == row["sha256"], f"motor {key} XML changed")
        roots[key] = ET.parse(row["path"]).getroot()
    return receipt, roots


def bools(*values):
    if any(type(value) is not bool for value in values):
        raise ValueError("explicit Boolean supplied states required")


def camera_wait_witness(wait, global_stop):
    """One completed Wait-loop iteration, not a UI/native scheduler."""
    bools(wait, global_stop)
    return {"continue": wait, "global_stop_changes_predicate": False}


def motion_poll_witness(stop_motor, done, error, global_stop):
    """Only the qualified forward/reverse stop predicate; no native IO."""
    bools(stop_motor, done, error, global_stop)
    return stop_motor or done or error


def camera_switch_witness(setup_error, *, ordered_set=True):
    """A completed set/driver/conditional-clear path with a supplied error.

    ordered_set=True is guaranteed for the two autotune flat sequences, not
    for event25's independent set node. No scheduler outcome is predicted.
    """
    bools(setup_error, ordered_set)
    return True if setup_error or not ordered_set else False


def local_census(g, name, bank, readers, writers):
    found = {
        uid: n
        for uid, n in g.nodes.items()
        if n.get("class") == "gRef"
        and n.findtext("termList/*/dco/paramIdx") == str(bank)
    }
    require(set(found) == set(readers) | set(writers), f"{name} local census changed")
    for uid in found:
        local_port(g, uid, name, uid in writers)


def literal_route(g, w, writer, literal, value, name):
    dst = local_port(g, writer, name, True)
    bool_constant(g, literal, value)
    route = w.path(literal, dst)
    require(route is not None, f"lost literal route {writer}")
    require(
        {u for u, _ in w.literals(dst)} == {literal},
        f"ambiguous reset literal {writer}",
    )
    return route


def case_ranges(g, uid, frames):
    n = g.nodes[uid]
    require(n.get("class") == "select", "expected a Case Structure")
    require(
        [d.get("uid") for d in n.findall("diagramList/*")] == frames,
        f"case frames changed {uid}",
    )
    ranges = [
        (
            int(r.findtext("start")),
            int(r.findtext("end")),
            int(r.findtext("diagramIdx")),
        )
        for r in n.findall("SelectRangeArray32/*")
    ]
    require(ranges == [(0, 0, 0), (1, 1, 1)], f"case ranges changed {uid}")


def reset_after_loop(g, writer, sequence, reset_frame, loop):
    frames = [d.get("uid") for d in g.nodes[sequence].findall("diagramList/*")]
    require(
        len(frames) == 2
        and frames[1] == reset_frame
        and frames[0] in g.ancestry(loop)
        and g.ancestry(writer)[0] == reset_frame,
        "motor reset no longer follows completed loop",
    )


def or_leaves(g, target, visited=None):
    """Exact OR-only predicate leaves; no joining of Case alternatives."""
    visited = set() if visited is None else visited
    require(target not in visited, "cyclic OR predicate")
    incoming = [ps for _, ps in g.nets if target in ps and ps[0] != target]
    require(len(incoming) == 1, "ambiguous or missing OR-predicate wire")
    source = incoming[0][0]
    owner = g.owners.get(source)
    if owner is None or owner.findtext("primResID") != "1062":
        return {source}
    inputs = [t for t in terms(owner) if g.is_input(t)]
    require(len(inputs) == 2, "OR arity changed")
    return set().union(
        *(or_leaves(g, t.get("uid"), visited | {target}) for t in inputs)
    )


def verify(receipt=None, roots=None, motor_sources=None):
    if receipt is None or roots is None:
        receipt, roots = original()
    mr, mx = motor_original() if motor_sources is None else motor_sources
    require(digest(BASELINE) == BASELINE_SHA, "frozen baseline changed")
    require(digest(PREVIOUS) == PREVIOUS_SHA, "normal-stop proof changed")
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    m = SourceGraph(mr, mx, T(mx["meta"]))
    w, mw = Wires(g), Wires(m)
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    specs = [
        {f.tag: f.text for f in e} for e in g.nodes["5909"].findall("EventNodeEvents/*")
    ]
    local_census(g, "Wait", 103, ["14784", "15754"], WAIT_WRITERS)
    local_census(g, "stop motor", 243, [v[0] for v in MOTOR.values()], MAIN_RESETS)
    local_census(g, "stop vi moteurs ", 234, [], ["683306"])
    controls = []
    for uid, ddo, terminal, name, bank in (
        ("14605", "14553", "14607", "Wait", 103),
        ("59251", "59169", "59283", "stop motor", 243),
        ("58392", "58304", "58400", "stop vi moteurs ", 234),
    ):
        require(fp[uid].find("ddo").get("uid") == ddo, "control/DDO binding changed")
        require(
            g.table.heap(fp[uid].findtext("typeDesc")).get("Label") == name,
            "control type label changed",
        )
        require(
            g.nodes[terminal].find("dco").get("uid") == uid,
            "FP terminal binding changed",
        )
        require(
            not any(terminal in ps for _, ps in g.nets), "FP terminal gained a wire"
        )
        bound = [
            u
            for u, n in g.nodes.items()
            if n.get("class") in ("propNode", "ctlRefConst")
            and n.find("ddo") is not None
            and n.find("ddo").get("uid") in (uid, ddo)
        ]
        require(not bound, "control gained a statically bound property/reference")
        require(
            all(s["ddoUID"] not in (uid, ddo) for s in specs),
            "control gained an event registration",
        )
        controls.append(
            {
                "control": uid,
                "ddo": ddo,
                "bank": bank,
                "name": name,
                "unwired_terminal": terminal,
                "bound_property_refs": bound,
            }
        )

    wait_writes = []
    for uid, (literal, value) in WAIT_WRITERS.items():
        route = literal_route(g, w, uid, literal, value, "Wait")
        ancestry = g.ancestry(uid)
        require("14127" not in ancestry, "Wait gained a cleanup reset")
        wait_writes.append(
            {
                "writer": uid,
                "literal": literal,
                "value": value,
                "ancestry": ancestry,
                "route": route,
            }
        )
    resets = []
    for uid, (literal, frame, role) in MAIN_RESETS.items():
        route = literal_route(g, w, uid, literal, False, "stop motor")
        require(frame in g.ancestry(uid), "Main motor reset moved")
        resets.append(
            {
                "writer": uid,
                "literal": literal,
                "value": False,
                "frame": frame,
                "role": role,
                "route": route,
            }
        )
    literal_route(g, w, "683306", "683214", False, "stop vi moteurs ")
    reset_after_loop(g, "96347", "95783", "96319", "95809")
    reset_after_loop(g, "266868", "266170", "266812", "266207")
    require(
        [d.get("uid") for d in g.nodes["89514"].findall("diagramList/*")]
        == ["89518", "89710", "92784"]
        and "89710" in g.ancestry("89716")
        and g.ancestry("125466")[0] == "92784",
        "autotune reset moved before its loop",
    )
    require(
        not any(g.names.get(u) == "Wait" for u in g.nodes if "92784" in g.ancestry(u)),
        "autotune finale gained Wait reset",
    )

    flats = []
    for uid, frames in CAMERA_FLATS.items():
        require(
            g.nodes[uid].get("class") == "flatSequence"
            and [f.get("uid") for f in g.nodes[uid].findall("sequenceList/*")]
            == frames,
            "camera reconfiguration frame order changed",
        )
        flats.append({"sequence": uid, "frames": frames})
    require(
        "14238" in g.ancestry("16708")
        and "14295" in g.ancestry("14803")
        and g.ancestry("14709")[0] == "14047",
        "threshold set/clear order changed",
    )
    require(
        g.ancestry("92224")[0] == "92143" and g.ancestry("92850")[0] == "92143",
        "event25 set node gained explicit sequence ordering",
    )
    require(
        "12112" in g.ancestry("14418")
        and "51619" in g.ancestry("95369")
        and "87833" in g.ancestry("72350")
        and "79366" in g.ancestry("72251"),
        "autotune set/conditional-clear order changed",
    )
    guards = []
    for uid, (selector, source, ok, error, clear, ter) in ERROR_GUARDS.items():
        case_ranges(g, uid, [ok, error])
        td = g.table.heap(g.nodes[selector].findtext("dco/typeDesc"))
        require(
            td.get("Type") == "Cluster"
            and [f["type"] for f in g.table.fields(td)]
            == ["Boolean", "NumInt32", "String"],
            "error Case selector type changed",
        )
        call = g.owners[source]
        require(
            call.findtext("label/textRec/text") == '"IMAQ Grab Setup.vi"',
            "guard no longer comes from Grab Setup error",
        )
        route = w.path(source, selector)
        require(route is not None, "camera error-selector route lost")
        require(g.ancestry(clear)[0] == ok, "Wait clear moved out of No Error")
        require(
            g.names[ter] == "TER" and g.ancestry(ter)[0] == error,
            "camera error reporting moved",
        )
        require(
            not any(
                g.names.get(u) == "Wait" for u in g.nodes if error in g.ancestry(u)
            ),
            "Error arm gained a Wait clear",
        )
        guards.append(
            {
                "case": uid,
                "selector": selector,
                "source": source,
                "source_call": call.get("uid"),
                "source_type": "error cluster",
                "No_Error": {"frame": ok, "Wait_False_writer": clear},
                "Error": {"frame": error, "TER_writer": ter, "Wait_written": False},
                "route": route,
            }
        )

    case_ranges(g, "14095", ["16547", "16554"])
    exact_net(g, "22139", ["16701", "16564"])
    require(local_port(g, "14784", "Wait") == "16701", "camera gate reader changed")
    require(
        g.ancestry("6584")[0] == "16554"
        and loop_mode(g.nodes["6584"]) == "continue-if-true",
        "Wait loop gate changed",
    )
    exact_net(g, "6569", ["15806", "20770"])
    require(local_port(g, "15754", "Wait") == "15806", "Wait loop reader changed")
    exact_net(g, "14308", ["14274", "14304"])
    require(
        g.nodes["14274"].findtext("dco/ConstValue") == "00000032",
        "Wait-loop delay changed",
    )
    require(
        not any(
            g.names.get(u) in ("stop", "stop motor")
            for u in g.nodes
            if "6584" in g.ancestry(u)
        ),
        "Wait loop gained stop cancellation",
    )

    motor_routes = []
    for loop, (reader, port, test) in MOTOR.items():
        require(
            local_port(g, reader, "stop motor") == port
            and loop_mode(g.nodes[loop]) == "stop-if-true",
            "motor loop changed",
        )
        route = or_dependency(g, port, test)
        require(route is not None, "motor stop OR route lost")
        require(
            not any(g.names.get(u) == "stop" for u in g.nodes if loop in g.ancestry(u)),
            "motor loop gained Main STOP reader",
        )
        motor_routes.append(
            {
                "loop": loop,
                "reader": reader,
                "port": port,
                "conditional_terminal": test,
                "route": route,
            }
        )
    aborts = []
    for uid, frames, selector, net, ports, call in (
        (
            "95911",
            ["95950", "95962"],
            "95913",
            "96147",
            ["96017", "95913", "95905"],
            "95968",
        ),
        (
            "266305",
            ["266344", "266356"],
            "266307",
            "266542",
            ["266411", "266307", "266299"],
            "266362",
        ),
    ):
        case_ranges(g, uid, frames)
        exact_net(g, net, ports)
        require(
            g.nodes[call].findtext("label/textRec/text") == '"AbortMotion.vi"'
            and g.ancestry(call)[0] == frames[1],
            "motor abort True arm changed",
        )
        aborts.append(
            {
                "case": uid,
                "selector": selector,
                "True_arm_call": call,
                "call": "AbortMotion.vi",
            }
        )

    call_routes = []
    found_calls = {
        u
        for u, n in g.nodes.items()
        if n.get("class") == "iUse"
        and n.findtext("label/textRec/text") == '"Moteurs SdC GoTo.vi"'
    }
    require(found_calls == set(CALLS), "Main motor callee census changed")
    for uid, (src, dst) in CALLS.items():
        require("86296" in g.ancestry(uid), "motor subVI call left autotune event")
        p = next(t for t in terms(g.nodes[uid]) if t.get("uid") == dst)
        td = g.table.heap(p.findtext("dco/typeDesc"))
        require(
            p.findtext("dco/paramIdx") == "6"
            and g.is_input(p)
            and td.get("Type") == "Boolean"
            and td.get("Label") == "stop motor",
            "callee stop input changed",
        )
        route = w.path(src, dst)
        require(route is not None, "Main stop sample no longer reaches callee")
        call_routes.append(
            {
                "call": uid,
                "Main_sample": src,
                "input": dst,
                "connector_index": 6,
                "type": "Boolean value, not reference",
                "route": route,
            }
        )
    local_census(
        m, "stop motor", 3, [v[0] for v in CALLEE_LOOPS.values()], CALLEE_RESETS
    )
    callee_fp = {n.get("uid"): n for n in mx["fp"].iter() if n.get("class")}
    require(callee_fp["402"].findtext("conNum") == "6", "callee stop binding changed")
    callee_rows = []
    for loop, (reader, port, test) in CALLEE_LOOPS.items():
        require(
            local_port(m, reader, "stop motor") == port
            and loop_mode(m.nodes[loop]) == "stop-if-true",
            "callee loop changed",
        )
        route = or_dependency(m, port, test)
        require(route is not None, "callee stop dependency lost")
        agg, status, done, done_call = CALLEE_PREDICATES[loop]
        require(
            or_leaves(m, test) == {port, status, done},
            "callee exit predicate gained or lost a leaf",
        )
        td = m.table.heap(m.nodes[agg].findtext("dco/typeDesc"))
        sd = m.table.heap(m.nodes[status].findtext("dco/typeDesc"))
        dd = m.table.heap(m.nodes[done].findtext("dco/typeDesc"))
        require(
            td.get("Type") == "Cluster"
            and [f["type"] for f in m.table.fields(td)]
            == ["Boolean", "NumInt32", "String"]
            and sd.get("Type") == "Boolean"
            and sd.get("Label") == "status"
            and dd.get("Type") == "Boolean"
            and m.owners[done].get("uid") == done_call
            and m.nodes[done_call].findtext("label/textRec/text")
            == '"GetMotionDone.vi"',
            "callee done/error leaf types changed",
        )
        callee_rows.append(
            {"loop": loop, "local_reader": reader, "local_bank": 3, "route": route}
        )
        callee_rows[-1]["exit_predicate"] = {
            "OR_only_leaves": sorted((port, status, done)),
            "stop_motor": port,
            "error_status": status,
            "motion_done": done,
            "formula": "callee stop motor OR error.status OR motion done",
        }
    callee_resets = []
    for (uid, (literal, sequence, frame)), loop in zip(
        CALLEE_RESETS.items(), CALLEE_LOOPS, strict=True
    ):
        route = literal_route(m, mw, uid, literal, False, "stop motor")
        reset_after_loop(m, uid, sequence, frame, loop)
        callee_resets.append(
            {"writer": uid, "value": False, "route": route, "after_loop": loop}
        )

    pictures = []
    for filename, sha in PICTURES.items():
        path = REPO / "Supervision/analysis/labview_print_hidden_frames" / filename
        require(digest(path) == sha, f"saved Print image changed {filename}")
        pictures.append({"path": str(path), "sha256": sha})
    events = []
    for idx in (24, 25, 28, 29, 30):
        entries = [s for s in specs if s["diagramIdx"] == str(idx)]
        labels = [
            fp[s["ddoUID"]].findtext("partsList/*[@class='label']/textRec/text")
            for s in entries
        ]
        events.append(
            {"ordinal": idx, "source_labels": labels, "registrations": entries}
        )
    return {
        "scope": "Wait and motor cancellation in pinned Main and Moteurs SdC GoTo",
        "Main_source": {"path": receipt["source"], "sha256": receipt["sha256"]},
        "motor_source": {
            "path": mr["source"],
            "sha256": mr["sha256"],
            "xml": mr["xml"],
        },
        "previous_normal_stop_proof": {"path": str(PREVIOUS), "sha256": PREVIOUS_SHA},
        "observations": {
            "controls": controls,
            "Wait_writers": wait_writes,
            "Main_motor_False_writers": resets,
            "Main_motor_True_program_writers": [],
            "events": events,
            "camera_flat_sequences": flats,
            "conditional_Wait_clears": guards,
            "threshold_Wait_clear": "unconditional False after flat sequence frame3",
            "event25_set_order": (
                "True write and reconfiguration flat sequence are independent nodes"
            ),
            "autotune_Wait_sets": ["14418", "72350"],
            "autotune_finale_Wait_reset": False,
            "camera_wait": {
                "gate": "14095",
                "True_arm": "16554",
                "loop": "6584",
                "continue_when": "Wait",
                "poll_ms": 50,
                "reads_Main_stop": False,
            },
            "Main_motor_loops": motor_routes,
            "Main_manual_motion_aborts": aborts,
            "Main_to_motor_subVI": call_routes,
            "motor_subVI_local_control": {
                "control": "402",
                "bank": 3,
                "connector": 6,
                "same_as_Main_bank243": False,
            },
            "motor_subVI_loops": callee_rows,
            "motor_subVI_resets": callee_resets,
            "stop_vi_moteurs": (
                "Main bank234: initialization False only; no Main reader/event/FP wire"
            ),
        },
        "inferences": [
            "Wait=True is written by threshold Mouse Up, camera-channel change "
            "and two autotune reconfiguration sequences. Initialization and the "
            "threshold sequence clear it; channel/autotune clears are conditional "
            "on No Error.",
            "If Grab Setup returns an error and the True write executes, the "
            "corresponding Error arm reports TER but leaves Wait=True. Later "
            "successful camera reconfiguration or the unconditional threshold "
            "clear can recover it if the event loop is still dispatching. A later "
            "autotune channel switch can overwrite an earlier failure; recovery "
            "is not automatic or guaranteed.",
            "Camera loop6584 can remain active with Main stop=True while Wait "
            "stays True. It contains no Main-stop reader; runtime frame2 therefore "
            "need not finish and frame3 cleanup need not start. This is a "
            "source-supported supplied-state counterexample, not an observed "
            "machine hang.",
            "Event25 has no explicit dependency ordering its True writer before "
            "its successful False clear. Delays make the intended ordering "
            "plausible but do not prove it. No live race is asserted.",
            "Main stop motor has no program True writer or statically bound "
            "property writer; STOP MOTOR is an operator control. All four Main "
            "code writers reset it False. External/dynamic VI Server actors and "
            "native UI behavior are not exhaustively excluded.",
            "stop motor=True is an exit request, not a blocking state, for seven "
            "Main motor loops. Holding it False while done/error remain False "
            "can keep motion polling active despite Main STOP. Manual "
            "forward/reverse True arms call AbortMotion, but only when execution "
            "reaches them and native calls return.",
            "All eight autotune calls pass a Boolean sample to a separate callee "
            "control, not a shared mutable reference. Changing Main STOP MOTOR "
            "during a running call does not update that call's already-passed "
            "value. A callee motion loop that never reaches done/error can hold "
            "its caller before Main can sample a new stop request.",
            "Normal motion/autotune resets occur after the corresponding loops, "
            "so they cannot be relied on to release those loops. Main stop, Main "
            "stop motor and callee stop motor are three different scopes. No "
            "automatic Main STOP-to-motor cancellation bridge was found.",
            "All Wait/motion-producing event cases share one Event Structure "
            "and execute serially in this Main event loop. No race between "
            "simultaneously executing Main event cases is claimed; the camera "
            "loop is independent.",
        ],
        "remaining_unknowns": [
            "Actual deployed VI/library identity, UI lock/mechanical behavior "
            "and reaction latency; raw EventSpec regFlags are retained without "
            "a new native decoding claim.",
            "Completion/timeouts of native IMAQ/NewFocus calls; a Boolean cannot "
            "preempt a call that does not return. No hardware safe-state claim "
            "follows from these diagrams.",
            "No new native screenshot of camera sequence frame9/Wait gate is "
            "available: earlier named frame08/frame09 captures show frame0. "
            "That gate is qualified from pinned XML, not falsely attributed "
            "to those pictures.",
            "Saved Print images corroborate visible branches but lack "
            "capture-time VI byte hashes; the pinned source files are not "
            "a proof of current deployed bytes.",
            "No live deadlock, shutdown test or scheduler interleaving was "
            "executed; counterexamples are conditional on explicitly supplied "
            "Wait/done/error/call states.",
        ],
        "saved_Print_images": pictures,
        "screen_used": False,
        "VI_run_or_save": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
        "full_Supervision_coverage": False,
        "guaranteed_normal_shutdown": False,
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
