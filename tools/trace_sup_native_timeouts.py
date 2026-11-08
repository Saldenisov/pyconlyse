"""Bounded static IMAQ/NewFocus timeout and cleanup evidence, never a controller.

Installed NI 2020 wrappers and copied NewFocus DLLs are candidates, not proof of
the deployed 2012 library configuration. No VI, assembly or method is executed.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

from export_sup_beam_indicator_routes import (
    BASELINE,
    BASELINE_SHA,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, digest, original
from trace_sup_beam_switches import Wires, terms
from trace_sup_normal_stop import bool_constant
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

FOLDER = REPO / "Supervision/integration_analysis/native_timeouts_20261017"
OUTPUT = FOLDER / "RESULT.json"
INPUTS = FOLDER / "INPUTS.json"
INPUTS_SHA = "7E077B286A88C116629D312BFC96FD341C31471DFA444EFB27A29E03DF65E344"
PREVIOUS = {
    "normal_stop_20261017/RESULT.json": (
        "713FCFC90073EBB4212FF5927624A54945B8D5D076C941E67960CD87BED321BC"
    ),
    "wait_motor_stop_20261017/RESULT.json": (
        "206FC7DF8358651FB40F1AB0F4228EE90978F1787ED16449B35E076FE0A7236D"
    ),
}
VENDOR = {
    "InitSingleDevice": "CmdLib8742",
    "GetIdentification": "GetIdentification",
    "SetZeroPosition": "SetZeroPosition",
    "RelativeMove": "RelativeMove",
    "GetErrorMsg": "GetErrorMsg",
    "GetMotionDone": "GetMotionDone",
    "GetPosition": "GetPosition",
    "AbortMotion": "AbortMotion",
    "Shutdown": "Shutdown",
}
CORE_NATIVE = {
    "IMAQ_Grab_Acquire": ("405", "imgGrabAcquire_LV"),
    "imgGrabArea": ("302", "imgGrabArea"),
    "imgGrabSetup": ("184", "imgGrabSetup"),
    "imgSessionStopAcquisition": ("102", "imgSessionStopAcquisition"),
    "imgClose": ("131", "imgClose_LV"),
}
CONFIG_PINS = {
    "source/PILOTAGE_ELYSE_SUP/img0.iid": (
        "743753A9B614FCFD2C863F920A0908DE842F56BF0567BD2A9CC1D5EC69DE2498"
    ),
    "source/PILOTAGE_ELYSE_SUP/CCIR(1409).icd": (
        "260BED2236BBA8DE205959C020E55EF902E4D6BF8B97FE049741E114DAFC87C1"
    ),
    "extracted/PILOTAGE_ELYSE_SUP/img0.iid": (
        "743753A9B614FCFD2C863F920A0908DE842F56BF0567BD2A9CC1D5EC69DE2498"
    ),
    "extracted/PILOTAGE_ELYSE_SUP/CCIR(1409).icd": (
        "260BED2236BBA8DE205959C020E55EF902E4D6BF8B97FE049741E114DAFC87C1"
    ),
}
PICTURES = {
    "analysis/labview_print_hidden_frames/InitSingleDeviced.png": (
        "19CB24CB62D6C8AC2E0E1F752D8156F397B22B9B406AC0605223C745406C35E5"
    ),
    "analysis/labview_print_hidden_frames/GetMotionDoned.png": (
        "9DCBCE8D43DA18175DDD9B62A8A1CB873A84AABF13DF2A12CFF78EC687B17D5E"
    ),
    "analysis/labview_print_hidden_frames/Shutdownd.png": (
        "9A7A41270AEEE6C4ED575EEB62ACE6CBC97FDACE5AFBF0CE70A005229DF62F92"
    ),
    "analysis/labview_print_hidden_frames/RelativeMoved.png": (
        "0E7BE2DE92A4094575DC8ECE10255C71F1B9E64C9ABFFBC2F58EAB0C65AA4225"
    ),
    "analysis/screenshots/0_SUP_ELYSE_outer_frame_3_full.png": (
        "86A2D09FF76648DAB97A62EE7C55BFF61E15DEA4F0BE0E51B6F6E639367DC726"
    ),
}


def evidence():
    require(digest(INPUTS) == INPUTS_SHA, "native input catalog changed")
    index = json.loads(INPUTS.read_text("utf-8"))
    libraries = {}
    for row in index["library"]:
        require(digest(row["path"]) == row["sha256"], "wrapper receipt changed")
        receipt = json.loads(Path(row["path"]).read_text("utf-8"))
        require(digest(receipt["source"]) == row["source_sha256"], "wrapper VI changed")
        roots = {}
        for key, entry in zip(("bd", "fp", "meta"), receipt["xml"], strict=True):
            require(digest(entry["path"]) == entry["sha256"], "wrapper XML changed")
            roots[key] = ET.parse(entry["path"]).getroot()
        libraries[row["name"]] = (receipt, roots)
    other = {}
    for row in index["other"] + index["extractors"]:
        require(
            digest(row["path"]) == row["sha256"], "native supporting evidence changed"
        )
        if row.get("name", "").endswith(".h"):
            other["header"] = row
        elif row.get("name"):
            other[row["name"]] = json.loads(Path(row["path"]).read_text("utf-8"))
    return index, libraries, other


def boundary(g, uid, expected):
    n = g.nodes[uid]
    require(
        n.get("class") == "extFunc" and n.findtext("nodeName") == f'"{expected}"',
        "native function identity changed",
    )
    require(
        n.find("abortCB") is not None and not n.findtext("abortCB"),
        "native abort callback changed",
    )
    args = []
    for t in terms(n):
        d = t.find("dco")
        if d is None or d.get("class") != "extFuncArg":
            continue
        td = g.table.heap(d.findtext("typeDesc"))
        args.append(
            {
                "port": t.get("uid"),
                "type": td.get("Type"),
                "label": td.get("Label"),
                "input": g.is_input(t),
            }
        )
    require(
        not any("timeout" in (a["label"] or "").lower() for a in args),
        "native call gained an explicit timeout argument",
    )
    return {
        "uid": uid,
        "symbol": expected,
        "library_path_bytes": n.findtext("libPath"),
        "arguments": args,
        "abort_callback": None,
        "driver_internal_deadline_known": False,
    }


def validate_il(assembly):
    """Check every disassembled instruction against the pinned binary bytes."""
    require(digest(assembly["source"]) == assembly["sha256"], "candidate DLL changed")
    data = Path(assembly["source"]).read_bytes()
    for method in assembly["methods"]:
        for ins in method["IL"]:
            code = bytes.fromhex(ins["bytes"])
            offset = ins["file_offset"]
            require(
                data[offset : offset + len(code)] == code, "IL instruction bytes differ"
            )
    require(
        not assembly["assembly_loaded"] and not assembly["methods_executed"],
        "native evidence was generated by managed execution",
    )


def calls(method, owner, name):
    return [
        i
        for i in method["IL"]
        if i["ref"]
        and i["ref"].get("owner") == owner
        and i["ref"].get("name") == name
        and i["op"] in ("call", "callvirt")
    ]


def ethernet_contract(assembly):
    methods = {m["token"]: m for m in assembly["methods"]}
    opening = methods["0x0600002A"]
    reading = methods["0x0600002D"]
    query = methods["0x06000032"]
    require(
        opening["name"] == "Open"
        and reading["name"] == "Read"
        and query["name"] == "Query",
        "Ethernet method identities changed",
    )
    require(
        len(calls(opening, "System.Net.Sockets.Socket", "Connect")) == 1,
        "synchronous Connect call changed",
    )
    require(
        len(calls(reading, "System.Threading.Monitor", "Enter")) == 1,
        "Read lock changed",
    )
    polls = calls(reading, "System.Net.Sockets.Socket", "Poll")
    require(len(polls) == 3, "Read polling sites changed")
    by_offset = {i["offset"]: i for i in reading["IL"]}
    for offset in (100, 114, 128):
        require(
            by_offset[offset]["op"] == "ldc.i4" and by_offset[offset]["arg"] == 500000,
            "Poll duration changed",
        )
    require(
        by_offset[71]["arg"] == 10
        and by_offset[83]["arg"] == 30
        and by_offset[85]["branch_target"] == 62,
        "10ms/30-iteration availability wait changed",
    )
    require(
        len(calls(reading, "System.Net.Sockets.Socket", "Receive")) == 1,
        "Read Receive boundary changed",
    )
    require(
        by_offset[263]["branch_target"] == 224, "Available-driven receive loop changed"
    )
    setters = [
        i
        for m in assembly["methods"]
        for i in m["IL"]
        if i["ref"]
        and i["ref"].get("name") in ("set_ReceiveTimeout", "set_SendTimeout")
    ]
    require(not setters, "candidate gained socket deadline setters")
    require(
        len(calls(query, "Newport.Ethernet.Ethernet", "Read")) == 1
        and len(calls(query, "Newport.Ethernet.Ethernet", "Write")) == 1,
        "Query call chain changed",
    )
    return {
        "assembly": assembly["assembly"],
        "version": assembly["version"],
        "sha256": assembly["sha256"],
        "Open_method": opening["token"],
        "Read_method": reading["token"],
        "Query_method": query["token"],
        "availability_wait": {"Sleep_ms": 10, "iteration_limit": 30},
        "Poll_arguments": [500000, 500000, 500000],
        "Poll_argument_units": "microseconds in System.Net.Sockets.Socket.Poll",
        "whole_operation_deadline_proven": False,
        "synchronous_native_boundaries": [
            "Monitor.Enter",
            "Socket.Connect",
            "Socket.Send",
            "Socket.Receive",
        ],
        "receive_loop": "continues while Available>0; no total-time counter",
        "socket_ReceiveTimeout_or_SendTimeout_setters_found": [],
        "meaning": (
            "Local waits/Poll durations do not cap lock, Connect, Send, "
            "Receive or reconnect"
        ),
    }


def candidate_query_path(assembly):
    """A possible static call path, not a claim about selected live transport."""
    methods = {m["token"]: m for m in assembly["methods"]}
    queue = deque([("0x060000D6", [])])
    seen = set()
    while queue:
        token, path = queue.popleft()
        if token in seen:
            continue
        seen.add(token)
        method = methods[token]
        path = path + [
            {"token": token, "owner": method["owner"], "name": method["name"]}
        ]
        for ins in method.get("instructions", []):
            ref = ins["token_reference"]
            if not ref or ins["opcode"] not in ("call", "callvirt"):
                continue
            if (
                ref.get("owner") == "Newport.Ethernet.Ethernet"
                and ref.get("name") == "Query"
            ):
                return path + [ref]
            if ref["kind"] == "MethodDef" and ref["token"] in methods:
                queue.append((ref["token"], path))
    raise AssertionError("candidate GetMotionDone-to-Ethernet.Query route lost")


def shutdown_witness(
    stop,
    *,
    init_returned,
    runtime_returned,
    wait_clear,
    motion_finished,
    cleanup_returned,
):
    """Supplied-state dependency witness only; no scheduler or real time model.

    runtime_returned means runtime IO calls returned, not that frame2 completed.
    """
    values = (
        stop,
        init_returned,
        runtime_returned,
        wait_clear,
        motion_finished,
        cleanup_returned,
    )
    if any(type(v) is not bool for v in values):
        raise ValueError("explicit Boolean supplied states required")
    entered = (
        stop and init_returned and runtime_returned and wait_clear and motion_finished
    )
    return {
        "cleanup_entered": entered,
        "cleanup_frame_finished": entered and cleanup_returned,
        "all_resources_released": None,
    }


def config_contract(iid, icd):
    """Saved configuration, not a read of the live NI session or MAX registry."""
    require('InterfaceName = "img0.iid"' in iid, "saved interface identity changed")
    require(
        re.findall(r'^Channel[0-3] = "([^"]+)"', iid, re.M)[:4]
        == ["CCIR(1409).icd"] * 4,
        "saved camera channel assignments changed",
    )
    require("InterfaceInfo (1409)" in icd, "saved board type changed")
    require(
        re.findall(r"\bFrameTimeout\s*\((\d+)\)", icd) == ["1000"],
        "saved frame timeout changed",
    )
    return {
        "interface": "img0",
        "interface_file": "img0.iid",
        "channel_0_to_3_camera_file": "CCIR(1409).icd",
        "saved_frame_timeout_ms": 1000,
        "currently_loaded_file_identity_proven": False,
    }


def verify(sources=None, supporting=None):
    receipt, roots = original() if sources is None else sources
    index, libraries, other = evidence() if supporting is None else supporting
    require(digest(BASELINE) == BASELINE_SHA, "frozen baseline changed")
    for path, sha in PREVIOUS.items():
        require(
            digest(REPO / "Supervision/integration_analysis" / path) == sha,
            "previous cancellation proof changed",
        )
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    w = Wires(g)
    lib = {name: SourceGraph(r, x, T(x["meta"])) for name, (r, x) in libraries.items()}
    bool_constant(g, "13352", False)
    exact_net(g, "20910", ["13352", "15787"])
    for port, literal in (("18989", "18857"), ("22642", "22436")):
        require(
            w.literals(port) == [(literal, "00000004696D6730")],
            "Main interface name no longer img0",
        )
    configurations = []
    for path, sha in CONFIG_PINS.items():
        full = REPO / "Supervision" / path
        require(digest(full) == sha, "saved NI configuration changed")
        configurations.append({"path": str(full), "sha256": sha})
    root = REPO / "Supervision/source/PILOTAGE_ELYSE_SUP"
    camera_config = config_contract(
        (root / "img0.iid").read_text("utf-8"),
        (root / "CCIR(1409).icd").read_text("utf-8"),
    )
    require(
        g.nodes["15740"].findtext("label/textRec/text") == '"IMAQ Grab Acquire.vi"'
        and "5841" in g.ancestry("15740"),
        "Main acquisition call moved",
    )
    discovery = []
    for call, literal, port, net in (
        ("70317", "61835", "70344", "62636"),
        ("274396", "274090", "274417", "74304"),
    ):
        require(
            g.nodes[literal].findtext("dco/ConstValue") == "00001388",
            "discovery delay literal changed",
        )
        exact_net(g, net, [literal, port])
        td = g.table.heap(g.nodes[port].findtext("dco/typeDesc"))
        require(
            td.get("Label") == "msecDelayForDiscovery", "discovery argument changed"
        )
        discovery.append(
            {
                "call": call,
                "input": port,
                "value_ms": 5000,
                "role": "msecDelayForDiscovery, not a command deadline",
            }
        )
    vendor = []
    for name, method in VENDOR.items():
        graph = lib[name]
        nodes = [
            n
            for n in graph.nodes.values()
            if n.get("class") in ("constructorNode", "invokeNode")
        ]
        require(
            len(nodes) == 1 and nodes[0].findtext("methName") == f'"{method}"',
            "NewFocus wrapper method binding changed",
        )
        labels = [
            graph.table.heap(t.findtext("dco/typeDesc")).get("Label", "")
            for t in terms(nodes[0])
            if t.findtext("dco/typeDesc")
        ]
        require(
            not any(
                any(s in label.lower() for s in ("timeout", "cancel", "stop"))
                for label in labels
            ),
            "NewFocus call gained cancellation/deadline input",
        )
        vendor.append(
            {
                "VI": name + ".vi",
                "node": nodes[0].get("uid"),
                "method": method,
                "typed_port_labels": labels,
                "explicit_timeout_or_cancel_input": False,
            }
        )
    require(
        lib["InitSingleDevice"].nodes["43"].findtext("methName") == '"CmdLib8742"',
        "discovery constructor changed",
    )
    ctor_td = lib["InitSingleDevice"].table.heap(
        lib["InitSingleDevice"].nodes["77"].findtext("dco/typeDesc")
    )
    require(
        ctor_td.get("Label") == "msecDelayForDiscovery", "constructor delay label lost"
    )
    boundaries = {
        name: boundary(lib[name], uid, symbol)
        for name, (uid, symbol) in CORE_NATIVE.items()
    }
    # Installed wrapper exposes frame timeout, but this setup path selects a
    # buffer-list attribute (37), not timeout (42). No deployed value is inferred.
    attrs = libraries["IMAQ_Attribute"][1]["fp"]
    texts = [
        n.text for n in attrs.iter("buf") if n.text and "Frame timeout (ms)" in n.text
    ]
    require(len(texts) == 1, "attribute ring missing")
    labels = re.findall(r'"([^"]*)"', texts[0])
    require(
        len(labels) == 52
        and labels[42] == "Frame timeout (ms)"
        and labels[37] == "Current buffer list ID",
        "IMAQ attribute ring changed",
    )
    sw = Wires(lib["IMAQ_Grab_Setup"])
    require(
        sw.literals("455") == [("364", "0025")], "setup attribute selection changed"
    )
    imaq_props = []
    for uid, n in g.nodes.items():
        if n.get("class") != "propNode":
            continue
        descriptors = [
            g.table.heap(t.findtext("dco/typeDesc"))
            for t in terms(n)
            if t.findtext("dco/typeDesc")
        ]
        if not any(
            td is not None and td.get("RefType") == "Imaq" for td in descriptors
        ):
            continue
        names = [td.get("Label") for td in descriptors if td is not None]
        require(
            not any("timeout" in (name or "").lower() for name in names),
            "Main gained an IMAQ timeout property",
        )
        imaq_props.append({"uid": uid, "typed_labels": names})
    require(
        {r["uid"] for r in imaq_props} == {"15292", "15786", "21773"},
        "Main IMAQ property census changed",
    )
    sites = []
    for uid, n in g.nodes.items():
        if n.get("class") != "iUse":
            continue
        name = n.findtext("label/textRec/text", "").strip('"')
        if not (name.startswith("IMAQ ") or name.removesuffix(".vi") in VENDOR):
            continue
        ancestry = g.ancestry(uid)
        phase = next(
            (
                p
                for p, frame in (
                    ("init", "5807"),
                    ("runtime", "5902"),
                    ("cleanup", "14127"),
                )
                if frame in ancestry
            ),
            "other",
        )
        sites.append({"uid": uid, "name": name, "phase": phase, "ancestry": ancestry})
    # Cleanup waits for the preceding runtime frame and contains its own native
    # boundaries. Error wiring orders AbortMotion before Shutdown, not finally.
    exact_net(g, "177516", ["189901", "192419"])
    for uid in ("177515", "192398", "22923", "22899"):
        require("14127" in g.ancestry(uid), "cleanup native call moved")
    for name in ("NpEthernet", "UsbDllWrap"):
        validate_il(other[name])
    ethernet = ethernet_contract(other["NpEthernet"])
    usb_read = next(
        m for m in other["UsbDllWrap"]["methods"] if m["token"] == "0x06000035"
    )
    require(
        calls(usb_read, "Newport.USBComm.USB", "newp_usb_get_ascii"),
        "USB native read boundary changed",
    )
    cmdlib = next(
        a
        for a in other["CMDLIB_PE_NET_EVIDENCE.json"]["assemblies"]
        if a["assembly"]["name"] == "CmdLib"
    )
    require(
        digest(cmdlib["representative_path"]) == cmdlib["sha256"],
        "candidate CmdLib binary changed since the prior IL receipt",
    )
    route = candidate_query_path(cmdlib)
    images = []
    for path, sha in PICTURES.items():
        full = REPO / "Supervision" / path
        require(digest(full) == sha, "saved native screenshot changed")
        images.append({"path": str(full), "sha256": sha})
    return {
        "scope": (
            "Saved Supervision IMAQ acquisition/NewFocus IO boundaries "
            "and ordinary STOP"
        ),
        "Main_source": {"path": receipt["source"], "sha256": receipt["sha256"]},
        "input_catalog": {"path": str(INPUTS), "sha256": INPUTS_SHA},
        "library_wrappers_checked": len(index["library"]),
        "observations": {
            "Main_call_sites": sites,
            "acquire": {
                "call": "15740",
                "Immediate": False,
                "literal": "13352",
                "wired_input": "15787",
                "own_total_deadline": None,
            },
            "discovery": discovery,
            "NewFocus_wrappers": vendor,
            "NI_candidate_boundaries": boundaries,
            "Main_IMAQ_properties": imaq_props,
            "NI_frame_timeout": {
                "available_attribute": labels[42],
                "ring_ordinal": 42,
                "setup_selected_ordinal": 37,
                "setup_selected_label": labels[37],
                "actual_session_value_ms": None,
                "saved_configuration": camera_config,
                "config_files": configurations,
                "configuration_or_driver_default_not_recovered": False,
            },
            "candidate_ethernet": ethernet,
            "candidate_CmdLib": {
                "path": cmdlib["representative_path"],
                "sha256": cmdlib["sha256"],
                "assembly": cmdlib["assembly"],
            },
            "candidate_GetMotionDone_to_Ethernet_Query": route,
            "candidate_USB": {
                "Read": "0x06000035",
                "native_boundary": "newp_usb_get_ascii",
                "native_timeout_value_established": False,
            },
            "cleanup": {
                "frame": "14127",
                "after_runtime_frame": "5902",
                "motion_order": ["177515 AbortMotion.vi", "192398 Shutdown.vi"],
                "image_close": "22923 IMAQ Close.vi",
                "native_deadlines_proven": False,
                "independent_PSP_image_motion_chains": True,
            },
        },
        "inferences": [
            "Ordinary Main STOP is a cooperative Boolean, not an IMAQ/.NET "
            "cancellation token or native watchdog. It cannot preempt the current "
            "call. Polling "
            "Main stop in camera setup retry only helps after Init/Grab Setup return.",
            "Main Grab Acquire is non-immediate (False) and has no caller-specified "
            "deadline. Installed NI wrappers reach imgGrabAcquire_LV or old-style "
            "imgGrabArea. The saved img0.iid maps all four channels to CCIR(1409).icd, "
            "which specifies FrameTimeout(1000ms). Current loaded file/session "
            "identity was not verified. Absence of a timeout pin does NOT prove an "
            "infinite driver timeout; no finite shutdown bound is established either.",
            "NewFocus discovery 5000ms, event Timeout 80ms and autotune sleeps are "
            "not total IO or motion deadlines. The nine copied NewFocus wrappers "
            "invoke synchronous constructor/method nodes without "
            "deadline/cancel inputs.",
            "The local candidate Ethernet DLL contains a 30x10ms availability wait "
            "and three Poll(500000 microseconds) sites, but also untimed "
            "Monitor.Enter, Connect/Send/Receive/reconnect paths and an "
            "Available-driven receive loop. "
            "Those small waits cannot be advertised as a whole-command deadline. "
            "USB read reaches an opaque native USB function without a "
            "qualified deadline.",
            "If acquisition or a motion query never returns, its containing runtime "
            "body cannot complete and frame3 cleanup cannot start, despite STOP=True. "
            "Main STOP also cannot release an initialization call stuck "
            "before runtime.",
            "Manual AbortMotion is downstream in the same motion-loop iteration. "
            "It does not run while preceding GetErrorMsg/GetMotionDone/GetPosition "
            "is pending. A late STOP MOTOR is also only a new Boolean sample, not "
            "a change to an already-passed motor-subVI input.",
            "After a call returns with an error/timeout, cleanup still requires "
            "all runtime loops to finish: Wait and motor cancellation gaps remain. "
            "A returned error is not an automatic finally or resource-close "
            "acknowledgement.",
            "Cleanup itself can wait in IMAQ Close, AbortMotion or Shutdown. Abort "
            "must return before the wired Shutdown call can proceed. Independent "
            "PSP/image/motion cleanup chains can make partial progress; frame3 "
            "completion and full resource release are not guaranteed by entering it.",
        ],
        "unknowns": [
            "Installed NI2020 VIs and copied NewFocus2.0.1/NpEthernet1.0.4/USB1.0.6 "
            "are local candidates. Identity with the deployed 2012 library, exact "
            "runtime overload/transport and driver/firmware behavior are not proven.",
            "Actual NI session Frame timeout(ms) and loaded .icd/MAX configuration: "
            "the saved file says1000ms, not proof of the active session. Also driver "
            "watchdogs, OS connect/send/receive bounds and native USB read bounds.",
            "Automatic error short-circuit of .NET Shutdown after an incoming "
            "AbortMotion error is not newly qualified; only its data "
            "dependency is proven.",
            "Binary extraction emitted VITS/CONP/CPC2 and legacy IMAQ image-type "
            "warnings/corrupt-stub image types. No semantic claim relies on decoding "
            "those opaque image buffers, variant payloads or unsupported "
            "connector blocks.",
            "NI wrapper native branches are checked from hashed local XML, not new "
            "LabVIEW screen captures. Vision image-processing native bodies are not "
            "individually timed or declared fully covered by this IO-focused audit.",
            "No live hang, timeout duration, native abort or successful shutdown "
            "was tested. Native error handlers and auto resource reclamation can "
            "change runtime outcomes; no physical safety claim is made.",
        ],
        "saved_screenshots": images,
        "screen_used": False,
        "VI_run_or_save": False,
        "DLL_loaded_or_executed": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
        "guaranteed_shutdown_deadline_seconds": None,
        "guaranteed_resource_release": False,
        "full_Supervision_coverage": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")),
            "saved native report differs",
        )
    else:
        OUTPUT.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({"passed": True, "output": str(OUTPUT), "sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
