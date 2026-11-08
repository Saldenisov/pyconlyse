"""Offline handler-choice/cleanup proof; never opens a dialog or runs a VI.

Original 2012 project helpers and installed 2020 Simple Error Handler are
different evidence scopes. No equality with a remotely deployed vi.lib is
assumed. Missing legacy selector ranges are bounded by pinned receipts and
the active captions in saved native Print images, not guessed from ordinal.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter

from export_sup_beam_indicator_routes import (
    BASELINE,
    BASELINE_SHA,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, digest, original
from trace_sup_beam_switches import Wires, terms
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

FOLDER = REPO / "Supervision/integration_analysis/simple_error_handler_stop_20261017"
OUTPUT = FOLDER / "RESULT.json"
PINS = {
    "simple": (
        FOLDER / "library/receipt.json",
        "DE09FB2870F9D10DEBDCFD169B3C1577FA6FEFD828829A3B0B50D82FFBAAB37A",
        "50DBDF398DE7DE36AF277C30145A23BF1D613D8E6BA62AB13F41160394585073",
    ),
    "wrapper": (
        REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/26.json",
        "D69A197F76A00EE9D0D5D8FF5BC3046E67180185D1D8595542C3596EA9E3824A",
        "C184162B74BA6A1F7121C4F62F6C114D6A64A7420EEFB317E09A2E82F42B8F7B",
    ),
    "core": (
        REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/25.json",
        "E12B1A6FC0DD5173A42F25CB7E4E5BE242CCC4E98C95DF23BB7ACB91353DEFE0",
        "12A5F68A25702C2638F5CD599C8909DE43926FAA9DA23006386FD570A93A0A64",
    ),
    "not_found": (
        REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/31.json",
        "46ADB662F0D688F638622F9A879A45C2043417F5545EF17C703560A6F3ECA08E",
        "6DAA7DBDD94EC838F5AB1A8BF36B3933D40950DBB66AE78BD208090816D279C7",
    ),
    "details": (
        REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/14.json",
        "B85C9E064F015851D3CE2A45EF117F427C80B2B9003CEADBB295255D72D711D5",
        "58ABC11B9A7C92E8224C0D3C6401D5C181119859118268FE87F0D87086FA1426",
    ),
    "three_buttons": (
        REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/36.json",
        "9FA09D69FF45B05F40BEA7F260D6DC5899CB052870E59E5E3A5B8D6BA5A1373A",
        "D4535F1559A2E46BB93AACF7294C2D1329751E0566DEE5072A6F7868857C5E08",
    ),
}
IMAGE_PINS = {
    "analysis/labview_print_hidden_frames/Not_Found_Dialogd.png": (
        "4712434FDDE2B1F2217A9F988BE73004966E261C85FE246E47C5CF302B034A9A"
    ),
    "analysis/labview_print_hidden_frames/Details_Display_Dialogd.png": (
        "92C3EB1559AEE81879F3A4DF90C082A768617DE748752618422E2A2176FADA35"
    ),
    "analysis/labview_print_hidden_frames/Details_Display_Dialogd11.png": (
        "EF611FECB896BE811CB44E8AB82DBA43B7FF71DA68527ACFD985450FC8342E4E"
    ),
    "analysis/labview_print_hidden_frames/Details_Display_Dialogd12.png": (
        "813C7385FCDA84DD31140F1EA5195A1AC8A4686BDFC2AF61D240053E999538B3"
    ),
    "analysis/labview_print_hidden_frames/General_Error_Handler_COREd33.png": (
        "C934765F7F9F584C3399A247CA708B2F6C58B14BFD5245D0FC8B6F3368D5754C"
    ),
    "analysis/labview_print_hidden_frames/General_Error_Handlerd.png": (
        "DD23C763B26BE8A1BA973E40D8DFBA01FBA3E2EDBEF25FD41F2D45850D9402A6"
    ),
    "analysis/screenshots/0_SUP_ELYSE_outer_frame_3_full.png": (
        "86A2D09FF76648DAB97A62EE7C55BFF61E15DEA4F0BE0E51B6F6E639367DC726"
    ),
}


def load_sources():
    result = {"main": original()}
    for name, (path, receipt_sha, source_sha) in PINS.items():
        require(digest(path) == receipt_sha, f"{name} receipt changed")
        receipt = json.loads(path.read_text("utf-8"))
        require(
            receipt["sha256"] == source_sha and digest(receipt["source"]) == source_sha,
            f"{name} VI changed",
        )
        roots = {}
        for key, row in zip(("bd", "fp", "meta"), receipt["xml"], strict=True):
            require(digest(row["path"]) == row["sha256"], f"{name} XML changed")
            roots[key] = ET.parse(row["path"]).getroot()
        result[name] = receipt, roots
    return result


def stored_bytes(value):
    require(
        value is not None and value.startswith('"') and value.endswith('"'),
        "serialized default missing",
    )
    # html.unescape normalizes &#x00; to U+FFFD. LabVIEW uses it as byte zero.
    return re.sub(
        r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m[1], 16)), value[1:-1]
    ).encode("latin-1")


def embedded_integer(g, uid, expected):
    value = stored_bytes(g.nodes[uid].findtext("dco/DefaultData"))
    require(int.from_bytes(value, "big") == expected, f"constant {uid} changed")
    return value.hex().upper()


def primitive(g, uid, expected):
    n = g.nodes[uid]
    require(
        n.get("class") == "prim" and n.findtext("primResID") == str(expected),
        f"primitive {uid} changed",
    )


def call(g, uid, label):
    n = g.nodes[uid]
    require(
        n.get("class") == "iUse" and n.findtext("label/textRec/text") == f'"{label}"',
        f"callee {uid} changed",
    )
    return n


def control(g, roots, connector, expected_default=None):
    matches = [
        n
        for n in roots["fp"].iter()
        if n.get("class") == "fPDCO" and n.findtext("conNum") == str(connector)
    ]
    require(len(matches) == 1, "control connector missing/ambiguous")
    n = matches[0]
    if expected_default is not None:
        require(
            int.from_bytes(stored_bytes(n.findtext("DefaultData")), "big")
            == expected_default,
            "default dialog mode changed",
        )
    return n


def assert_caption(g, uid, text):
    require(
        text in g.nodes[uid].findtext("selString/textRec/text", ""),
        f"saved active case caption changed: {uid}",
    )


def choice_projection(mode, choice, route):
    """Fabricated supplied-choice diagnostic, not an operating dialog/model.

    Accept only the modes displaying Continue/Stop and literal button choices.
    A normally returning handler is not itself a request for Main cleanup.
    """
    if type(mode) is not int or mode not in (2, 3, 5):
        raise ValueError("explicit core Continue/Stop mode 2, 3 or 5 required")
    if choice not in ("Continue", "Stop") or route not in (
        "not_found",
        "details",
        "core_fallback",
    ):
        raise ValueError("explicit reviewed button and route required")
    stop_flag = choice == "Stop"
    abort = stop_flag and mode != 3
    # Not Found returns mode==3 in its Center arm. The regular fallback
    # returns literal False. Neither regular Stop branch normally returns.
    propagated = stop_flag and (mode == 3 or route == "details")
    return {
        "requests_Stop_primitive": abort,
        "stop_event_value_if_returned": propagated,
        "normal_return_expected_from_branch": not abort,
        "closes_dialog_FP_before_Stop": route == "details" and abort,
        "clears_error_cluster": False,
        "sets_Main_stop_local": False,
        "enters_Main_cleanup_by_itself": False,
        "cleanup_guaranteed": False,
        "effects_executed": False,
    }


def verify(sources=None):
    sources = load_sources() if sources is None else sources
    require(digest(BASELINE) == BASELINE_SHA, "frozen baseline changed")
    T, _ = components()
    graphs = {name: SourceGraph(r, x, T(x["meta"])) for name, (r, x) in sources.items()}
    s, wrapper, core, nf, details, main = (
        graphs[name]
        for name in ("simple", "wrapper", "core", "not_found", "details", "main")
    )

    # The installed wrapper has a real stored default, not the current FP value.
    simple_mode = control(s, sources["simple"][1], 8, 1)
    simple_error = control(s, sources["simple"][1], 9)
    call(s, "238", "General Error Handler.vi")
    exact_net(s, "220", ["204", "269"])
    exact_net(s, "221", ["207", "275"])
    require(
        s.nodes["204"].find("dco").get("uid") == simple_mode.get("uid"),
        "Simple mode control binding changed",
    )
    require(
        s.nodes["207"].find("dco").get("uid") == simple_error.get("uid"),
        "Simple error control binding changed",
    )
    require(
        s.nodes["269"].findtext("dco/paramIdx") == "9"
        and s.nodes["275"].findtext("dco/paramIdx") == "11",
        "Simple to General connector mapping changed",
    )
    require(
        [
            n.findtext("label/textRec/text")
            for n in s.nodes.values()
            if n.get("class") == "iUse"
        ]
        == ['"General Error Handler.vi"'],
        "Simple has additional callees",
    )

    control(wrapper, sources["wrapper"][1], 9, 1)
    call(wrapper, "325", "General Error Handler CORE.vi")
    exact_net(wrapper, "418", ["280", "414"])
    exact_net(wrapper, "400", ["434", "364"])
    remap = []
    for ordinal, (frame, literal, value) in enumerate(
        zip(
            ("406", "408", "397", "416", "404"),
            ("457", "504", "443", "447", "523"),
            (0, 1, 2, 4, 5),
            strict=True,
        )
    ):
        require(
            wrapper.nodes["403"].findall("diagramList/*")[ordinal].get("uid") == frame,
            "wrapper mapping frame changed",
        )
        require(frame in wrapper.ancestry(literal), "mapping constant left frame")
        embedded_integer(wrapper, literal, value)
        remap.append([ordinal, value])

    # Unknown-error-description dialog: Center=Stop; mode3 propagates instead.
    call(nf, "326", "Three Button Dialog.vi")
    assert_caption(
        nf,
        "83",
        '"continue or stop message", "auto error handling dialog", '
        '"continue/stop + warnings"',
    )
    for uid, value in (("384", 1), ("399", 2), ("270", 3), ("515", 0)):
        embedded_integer(nf, uid, value)
    for uid, resid in (
        ("374", 1102),
        ("364", 1105),
        ("240", 1102),
        ("437", 1064),
        ("431", 1350),
    ):
        primitive(nf, uid, resid)
    for net, ports in (
        ("415", ["347", "371", "381"]),
        ("425", ["384", "397"]),
        ("281", ["376", "495"]),
        ("315", ["325", "291"]),
        ("313", ["270", "294"]),
        ("474", ["241", "473"]),
        ("500", ["464", "496", "443"]),
        ("447", ["441", "434"]),
        ("417", ["399", "368"]),
        ("420", ["366", "324"]),
        ("426", ["318", "350"]),
        ("422", ["321", "353"]),
        ("430", ["322", "356"]),
        ("428", ["319", "359"]),
    ):
        exact_net(nf, net, ports)
    require(
        "483" in nf.ancestry("431")
        and nf.nodes["480"].findall("diagramList/*")[1].get("uid") == "483",
        "Not Found Stop left Center=True branch",
    )
    # Input names and selected enum captions agree with saved native Print.
    fp_labels = {
        n.get("uid"): nf.table.heap(n.findtext("typeDesc")).get("Label")
        for n in sources["not_found"][1]["fp"].iter()
        if n.get("class") == "fPDCO"
    }
    require(
        fp_labels["31"] == "Continue"
        and fp_labels["23"] == "Stop"
        and fp_labels["62"] == "Help",
        "dialog button names changed",
    )
    Wires(nf).path("255", "356")  # Continue String to left connector10
    Wires(nf).path("250", "353")  # Stop String to center connector9
    Wires(nf).path("266", "350")  # Help String to right connector8
    for connector, label in (
        (10, 'Left Button Text ("Yes")'),
        (9, 'Center Button Text ("No")'),
        (8, 'Right Button Text ("Cancel")'),
    ):
        n = control(graphs["three_buttons"], sources["three_buttons"][1], connector)
        require(
            graphs["three_buttons"].table.heap(n.findtext("typeDesc")).get("Label")
            == label,
            "Three Button connector caption changed",
        )
    choice_control = control(graphs["three_buttons"], sources["three_buttons"][1], 3)
    require(
        choice_control.findtext(".//buf")
        == '(4)"Left Button""Center Button""Right Button""Window Close"',
        "choice enum ordering changed",
    )

    # The known-error regular fallback contains a SECOND Stop primitive.
    assert_caption(
        core, "3001", '"continue or stop message", "continue/stop + warnings"'
    )
    for uid, resid in (("3092", 1341), ("2859", 1064), ("2855", 1350)):
        primitive(core, uid, resid)
    exact_net(core, "2908", ["3096", "2902"])
    exact_net(core, "3041", ["2901", "2858"])
    require("3078" in core.ancestry("2855"), "fallback Stop branch changed")
    embedded_integer(core, "3165", 0)
    exact_net(core, "3170", ["3165", "3080"])
    call(core, "2597", "Not Found Dialog.vi")
    call(core, "2692", "Details Display Dialog.vi")

    # Details dialog: close only its own FP, then gate Stop via a sequence tunnel.
    for uid, resid in (("1105", 1105), ("1084", 1061), ("403", 1350)):
        primitive(details, uid, resid)
    embedded_integer(details, "1598", 3)
    embedded_integer(details, "644", 0)
    embedded_integer(details, "1599", 1)
    embedded_integer(details, "1918", 1)
    for net, ports in (
        ("1872", ["644", "1813", "1888"]),
        ("1784", ["1599", "1464"]),
        ("1914", ["1918", "1792", "1795"]),
        ("1806", ["1809", "1088", "1096"]),
        ("1882", ["1598", "1112"]),
        ("1877", ["1108", "1091"]),
        ("1878", ["1087", "649"]),
        ("1874", ["1846", "1436"]),
        ("1881", ["671", "659"]),
        ("651", ["643", "406"]),
    ):
        exact_net(details, net, ports)
    require(
        details.nodes["1128"].findtext("termList/*/dco/propList/*/PropItemCode")
        == "534",
        "close FP property changed",
    )
    require(
        [n.get("uid") for n in details.nodes["422"].findall("diagramList/*")] == ["656"]
        and "656" in details.ancestry("403"),
        "post-close Stop sequence changed",
    )

    # Main call sites: only the error input is wired. No default->2 assumption.
    main_calls = []
    for uid, n in main.nodes.items():
        if n.get("class") != "iUse":
            continue
        label = n.findtext("label/textRec/text", "").strip('"')
        if label not in ("Simple Error Handler.vi", "General Error Handler.vi"):
            continue
        wired = [
            (t, [(net, ps) for net, ps in main.nets if t.get("uid") in ps])
            for t in terms(n)
        ]
        wired = [(t, nets) for t, nets in wired if nets]
        error_connector = "9" if label.startswith("Simple") else "11"
        require(
            len(wired) == 1 and wired[0][0].findtext("dco/paramIdx") == error_connector,
            f"Main handler {uid} has an override or consumed output",
        )
        ancestry = main.ancestry(uid)
        phase = next((p for p in ("5807", "5902", "14127") if p in ancestry), None)
        require(phase is not None, "handler outside audited lifecycle")
        main_calls.append(
            {
                "call": uid,
                "callee": label,
                "outer_frame": phase,
                "error_input": wired[0][0].get("uid"),
                "wire": wired[0][1][0][0],
                "dialog_override": False,
                "output_consumed": False,
            }
        )
    counts = Counter((r["callee"], r["outer_frame"]) for r in main_calls)
    require(
        counts
        == {
            ("General Error Handler.vi", "14127"): 2,
            ("General Error Handler.vi", "5807"): 2,
            ("Simple Error Handler.vi", "14127"): 1,
            ("Simple Error Handler.vi", "5807"): 1,
            ("Simple Error Handler.vi", "5902"): 35,
        },
        "Main handler census changed",
    )

    frames = [d.get("uid") for d in main.nodes["988"].findall("diagramList/*")]
    require(frames[2:4] == ["5902", "14127"], "runtime/cleanup frame order changed")
    for uid, label in (
        ("177515", "AbortMotion.vi"),
        ("192398", "Shutdown.vi"),
        ("22923", "IMAQ Close.vi"),
        ("14492", "Simple Error Handler.vi"),
    ):
        call(main, uid, label)
        require("14127" in main.ancestry(uid), "resource cleanup left frame3")
    exact_net(main, "177516", ["189901", "192419"])
    exact_net(main, "177509", ["192407", "194938"])
    exact_net(main, "23665", ["26390", "22950"])
    exact_net(main, "11757", ["22926", "23029"])
    exact_net(main, "282", ["12552", "14522"])
    exact_net(main, "12845", ["12839", "12688"])
    require(
        main.nodes["12839"].findtext("dco/ConstValue") == "0000",
        "cleanup stop=False reset changed",
    )
    require(
        len(terms(main.nodes["6334"])) - 1 == 13
        and len(terms(main.nodes["22201"])) - 1 == 9,
        "resource-array census changed",
    )

    journal_report = (
        REPO / "Supervision/integration_analysis/psp_journals_stop_20261017/RESULT.json"
    )
    require(
        digest(journal_report)
        == "909D63EC5A8E6E62E7EA85A8AD1553CAC80B61FCDA7AEA1B6A83B19B45670AB6",
        "previous error-sink qualification changed",
    )
    journal = json.loads(journal_report.read_text("utf-8"))
    psp_calls = [
        row["sink"]["call"]
        for row in journal["observations"]["runtime_PSP_write_error_sinks"]
        if row["sink"]["kind"] == "Simple Error Handler.vi"
    ]
    require(
        len(psp_calls) == 30 and set(psp_calls) <= {r["call"] for r in main_calls},
        "PSP handler linkage changed",
    )
    pictures = []
    for path, sha in IMAGE_PINS.items():
        p = REPO / "Supervision" / path
        require(digest(p) == sha, "saved screenshot changed")
        pictures.append({"path": str(p.relative_to(REPO)), "sha256": sha})
    return {
        "scope": (
            "Static control-flow proof, not a device controller "
            "or native abort experiment"
        ),
        "source_pins": {
            name: {"source": r["source"], "sha256": r["sha256"], "xml": r["xml"]}
            for name, (r, _) in sources.items()
        },
        "observations": {
            "Simple_installed_library": "LabVIEW 2020 32-bit vi.lib/Utility/error.llb",
            "Simple_dialog_default": 1,
            "Simple_dialog_default_label": "OK message",
            "Simple_to_General": {
                "call": "238",
                "mode_wire": "220",
                "error_wire": "221",
            },
            "General_wrapper_default": 1,
            "General_to_CORE_mode_remap": remap,
            "Main_handler_calls": main_calls,
            "Main_handler_counts": [
                {"callee": c, "outer_frame": f, "count": v}
                for (c, f), v in sorted(counts.items())
            ],
            "PSP_writes_using_default_Simple": 30,
            "Not_Found_Stop": {
                "dialog": "326",
                "choice_center": 1,
                "help_right": 2,
                "Stop_primitive": "431",
                "auto_mode_excluded": 3,
                "wire_to_Stop": "447",
                "stop_event_if_center_and_returned": "dialog_mode ==3",
            },
            "CORE_fallback_Stop": {
                "dialog": "3092",
                "Stop_primitive": "2855",
                "active_case": "continue or stop message, continue/stop + warnings",
                "wire_to_Stop": "3041",
                "normal_output_literal": False,
            },
            "Details_Stop": {
                "Continue_frame": "435",
                "Stop_frame": "1117",
                "event_loop": "1818",
                "close_FP_property": "1128",
                "post_close_sequence": "422",
                "Stop_primitive": "403",
                "Stop_gate": "Stop request AND dialog mode !=3",
            },
            "cleanup": {
                "outer_sequence": "988",
                "runtime_frame": "5902",
                "cleanup_frame": "14127",
                "PSP_connections": 13,
                "image_buffers": 9,
                "addressed_motion_abort_then_shutdown": True,
                "resource_groups_have_total_order": False,
                "stop_local_reset": False,
                "is_finally_handler": False,
            },
        },
        "inferences": [
            "Continue acknowledges the dialog and lets its normal caller path "
            "proceed; it does not itself stop the top-level VI, clear the underlying "
            "PSP error, repair/retry a failed write, or request Main cleanup.",
            "In ordinary Continue/Stop modes2 or5, Stop drives the LabVIEW Stop "
            "primitive, not the Main Boolean stop local. By Stop-primitive semantics "
            "this aborts the calling top-level hierarchy, not just the handler. "
            "It does not mean Quit LabVIEW or stopping an unrelated top-level "
            "VI/process.",
            "Auto error handling mode3 is an explicit exception: a Stop choice is "
            "propagated as a result but these branches suppress the actual Stop "
            "primitive. No conclusion about an external auto-handler caller is "
            "invented.",
            "Details Display Dialog requests closing its own front panel before "
            "its Stop primitive can run. This small dialog cleanup is not the "
            "application's "
            "PSP/IMAQ/CmdLib release region.",
            "Main frame3 is a later ordinary sequence frame, entered only after "
            "the runtime frame finishes normally. Aborting inside runtime bypasses "
            "this source-level cleanup path; no finally-style resource release or "
            "hardware safe state follows from pressing dialog Stop.",
            "If all runtime loops finish normally and native cleanup calls return, "
            "frame3 attempts PSP closes, image disposal/IMAQ Close and addressed "
            "AbortMotion then Shutdown. Independent chains have no total order; "
            "error propagation or a modal/aborted cleanup call can prevent complete "
            "successful release.",
            "All direct Main Simple/General handler calls consume only an error "
            "input. Thus the thirty already traced PSP-write handlers have no "
            "explicit Continue/Stop override. With the checked installed Simple "
            "wrapper, they use default1 OK-message mode, not Stop-choice mode. "
            "Remote/deployed library identity is still unqualified.",
            "The Not Found Center arm copies mode==3 to its stop-event output "
            "while its NOT feeds Stop. Thus normal Stop modes2/5 do not return "
            "a True result: they abort, and the wired result would be False. "
            "The older passive dialog_error.py projection records True for this "
            "nonreturning case; this additive trace does not promote that value "
            "to the actual original wire semantics.",
        ],
        "unknown_or_requires_further_evidence": [
            "The installed 2020 Simple Error Handler bytes are pinned, but the "
            "deployed Supervision computer's Simple/General/CORE vi.lib identities "
            "are not established. No XP access or version equivalence is claimed.",
            "Legacy extracted helper XML lacks SelectRangeArray32/EventNodeEvents. "
            "Current offline re-extraction of Not Found Dialog did not recover "
            "ranges. Active branch captions, connector wiring and saved Print "
            "images support the stated button paths; complete selector/event "
            "decoding is not certified.",
            "Actual abort scope/timing, simultaneous shared callers, OS key/close "
            "behavior, automatic LabVIEW/driver reclamation and cleanup-call "
            "success were not executed. No user shutdown frame is guaranteed "
            "by an abort.",
            "Error Code Database descriptions, special-tag policy, all native "
            "error-default behavior and all nested dependencies are not newly "
            "qualified. This is not full Supervision or hardware-safety coverage.",
            "Saved historical images lack capture-time VI hashes; they corroborate "
            "displayed paths rather than proving deployed version identity.",
        ],
        "saved_screenshots": pictures,
        "screenshots_are_not_capture_time_source_pins": True,
        "full_Supervision_coverage": False,
        "deployed_library_equivalence": False,
        "screen_used": False,
        "vi_run_or_save": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
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
    print(
        json.dumps(
            {
                "passed": True,
                "output": str(OUTPUT),
                "sha256": digest(OUTPUT),
                "screen_or_hardware_used": False,
            }
        )
    )


if __name__ == "__main__":
    main()
