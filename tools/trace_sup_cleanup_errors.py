"""Offline cleanup error propagation: wrapper dispatch is not resource release.

Original Main/NewFocus source plus local NI2020 candidates and local NI help.
No VI, native library, network, screen or hardware operation is performed.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from export_sup_beam_indicator_routes import (
    BASELINE,
    BASELINE_SHA,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, digest, original
from trace_sup_beam_switches import COMPARISON, COMPARISON_SHA, terms
from trace_sup_native_timeouts import evidence as native_evidence
from trace_sup_normal_stop import bool_constant
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

FOLDER = REPO / "Supervision/integration_analysis/cleanup_errors_20261017"
OUTPUT = FOLDER / "RESULT.json"
INPUTS = FOLDER / "INPUTS.json"
INPUTS_SHA = "41AFF273F583C9EE2C1897F38947ECC76D39EDE708547B6ABC12DA8CDC379545"
PREVIOUS = {
    "normal_stop_20261017/RESULT.json": (
        "713FCFC90073EBB4212FF5927624A54945B8D5D076C941E67960CD87BED321BC"
    ),
    "native_timeouts_20261017/RESULT.json": (
        "F3427E4344F6D5E6AE5BEB76E0DAA18EE4D55878B4A61FADAD4E6963AF7D6CE4"
    ),
}


def load_added():
    require(digest(INPUTS) == INPUTS_SHA, "cleanup input catalog changed")
    catalog = json.loads(INPUTS.read_text("utf-8"))
    libraries, help_text = {}, {}
    for row in catalog["library"]:
        require(digest(row["path"]) == row["sha256"], "cleanup receipt changed")
        r = json.loads(Path(row["path"]).read_text("utf-8"))
        require(digest(r["source"]) == r["sha256"], "cleanup candidate VI changed")
        require(digest(r["archive"]) == r["archive_sha256"], "NI archive changed")
        roots = {}
        for key, entry in zip(("bd", "fp", "meta"), r["xml"], strict=True):
            require(digest(entry["path"]) == entry["sha256"], "cleanup XML changed")
            roots[key] = ET.parse(entry["path"]).getroot()
        require(not r["VI_executed"] and not r["native_library_loaded"], "IO evidence")
        libraries[row["name"]] = (r, roots)
    for row in catalog["local_NI_help"]:
        require(digest(row["path"]) == row["sha256"], "local help changed")
        require(digest(row["archive"]) == row["archive_sha256"], "help CHM changed")
        text = Path(row["path"]).read_text("cp1252")
        help_text[row["name"]] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
    for row in catalog["saved_screenshots"] + catalog["extractors"]:
        require(digest(row["path"]) == row["sha256"], "cleanup support changed")
    return catalog, libraries, help_text


def graph(bundle, table_type):
    receipt, roots = bundle
    return SourceGraph(receipt, roots, table_type(roots["meta"]))


def frames(g, uid):
    """Check Boolean/error selector ordinal-to-frame mapping, not BFS execution."""
    n = g.nodes[uid]
    require(n.get("class") == "select", "cleanup selector changed")
    ranges = n.findall("SelectRangeArray32/*")
    require(
        [
            (r.findtext("start"), r.findtext("end"), r.findtext("diagramIdx"))
            for r in ranges
        ]
        == [("0", "0", "0"), ("1", "1", "1")],
        "cleanup case polarity changed",
    )
    return [f.get("uid") for f in n.findall("diagramList/*")]


def alias(g, port, index):
    return g.nodes[port].findall("dco/termList/*")[index].get("uid")


def primitive(g, uid, res):
    n = g.nodes[uid]
    require(
        n.get("class") == "prim" and n.findtext("primResID") == res,
        "cleanup primitive changed",
    )


def main_chain(g):
    labels = {
        "177515": '"AbortMotion.vi"',
        "192398": '"Shutdown.vi"',
        "194898": '"General Error Handler.vi"',
        "22899": '"IMAQ Dispose"',
        "22923": '"IMAQ Close.vi"',
        "22962": '"General Error Handler.vi"',
    }
    for uid, name in labels.items():
        require(
            g.nodes[uid].findtext("label/textRec/text") == name,
            "Main cleanup callee changed",
        )
        require("14127" in g.ancestry(uid), "call left final cleanup frame")
    for net, ports in (
        ("177516", ["189901", "192419"]),
        ("177509", ["192407", "194938"]),
        ("26734", ["26728", "26396"]),
        ("24671", ["24664", "22905"]),
        ("22375", ["26394", "22920"]),
        ("23265", ["22911", "26385"]),
        ("23665", ["26390", "22950"]),
        ("11757", ["22926", "23029"]),
    ):
        exact_net(g, net, ports)
    require(not any("189913" in ps for _, ps in g.nets), "Abort input now wired")
    bool_constant(g, "24664", True)
    require(
        set(bytes.fromhex(g.nodes["26728"].findtext("dco/ConstValue"))) == {0},
        "image cleanup seed is no longer no-error",
    )
    require(len(terms(g.nodes["22201"])) - 1 == 9, "image cleanup count changed")
    return {
        "frame": "14127",
        "Abort_to_Shutdown_wire": "177516",
        "Shutdown_error_to_handler_wire": "177509",
        "Abort_error_input_wired": False,
        "image_count": 9,
        "Dispose_All_Images": True,
        "Dispose_initial_error": False,
        "Dispose_to_Close_wire": "23665",
        "Close_to_handler_wire": "11757",
        "runtime_error_not_directly_used_as_dispose_seed": True,
        "image_and_motion_cleanup_independent": True,
    }


def motion(abort, shutdown, docs):
    a, s = abort, shutdown
    require(frames(a, "117") == ["220", "214"], "Abort error case changed")
    require(frames(a, "938") == ["1175", "1169"], "Abort success case changed")
    require("220" in a.ancestry("340"), "Abort moved outside No Error case")
    require(
        a.nodes["340"].findtext("methName") == '"AbortMotion"', "Abort method changed"
    )
    for net, ports in (
        ("1221", ["363", "1185"]),
        ("1424", ["355", "1421"]),
        ("601", ["594", "798"]),
        ("200", ["184", "506"]),
        ("629", ["625", "511"]),
        ("368", ["794", "326"]),
    ):
        exact_net(a, net, ports)
    bool_constant(a, "594", True)
    require(
        a.nodes["184"].findtext("dco/ConstValue") == "00000001", "Abort code changed"
    )
    raw = bytes.fromhex(a.nodes["625"].findtext("dco/ConstValue"))
    require(raw[4:] == b"AbortMotion.vi I/O Error.", "Abort error source changed")
    require(a.nodes["679"].get("class") == "nMux", "Abort cluster update changed")
    require("1175" in a.ancestry("679"), "Abort false result no longer sets error")
    require(
        [n.get("uid") for n in s.nodes.values() if n.get("class") == "invokeNode"]
        == ["340"],
        "Shutdown method census changed",
    )
    require(
        not any(n.get("class") == "select" for n in s.nodes.values()),
        "Shutdown gained a case structure",
    )
    node = s.nodes["340"]
    require(
        node.findtext("methName") == '"Shutdown"'
        and node.findtext("invokeFlags") == "08",
        "Shutdown invoke metadata changed",
    )
    exact_net(s, "273", ["598", "352"])
    exact_net(s, "292", ["355", "168"])
    require(
        "standard error in" in docs["Invoke_Node_NET"], ".NET error contract missing"
    )
    require(
        "node operates in the same way as a standard" in docs["Invoke_Node_NET"],
        ".NET invoke exception contract changed",
    )
    require(
        "runs normally only if no error occurred before this node runs"
        in docs["using_standard_error_in"],
        "standard error-in short circuit changed",
    )
    return {
        "Abort_false_return": {
            "status": True,
            "code": 1,
            "source": "AbortMotion.vi I/O Error.",
        },
        "Shutdown_wrapper_entered_after_Abort_returns": True,
        "Shutdown_error_input_direct_to_DotNet_invoke": ["598", "352"],
        "Shutdown_raw_invokeFlags": "08",
        "invokeFlags_bit_meaning_decoded": False,
        "no_error_clear_or_cleanup_exception_in_wrapper": True,
        "contract_based_conclusion": (
            "Under the documented standard .NET Invoke error-in contract, an "
            "Abort error with status=True is passed through: the managed Shutdown "
            "method is NOT invoked. Wrapper scheduling is not method execution. "
            "A status=False warning does not impose that error short circuit."
        ),
        "contract_source": "local NI2020 .NET Invoke + standard error-in help",
        "LV2012_runtime_short_circuit_experiment": False,
        "Abort_never_returns": "Shutdown wrapper cannot proceed on its error wire",
        "error_handler": "Main194898 receives Shutdown error-out; not cleanup retry",
    }


def images(close, core, unregister, dispose, update, docs):
    c, i, u, d = close, core, unregister, dispose
    require(frames(c, "90") == ["94", "102"], "IMAQ Close ref gate changed")
    primitive(c, "109", "1102")
    for net, ports in (
        ("131", ["111", "91"]),
        ("133", ["126", "114"]),
        ("282", ["280", "92", "117"]),
        ("147", ["122", "152"]),
        ("167", ["99", "271"]),
        ("273", ["151", "256"]),
        ("150", ["237", "346", "228"]),
        ("166", ["247", "231"]),
        ("169", ["222", "213"]),
        ("165", ["207", "349"]),
        ("107", ["352", "141"]),
        ("158", ["153", "144"]),
    ):
        exact_net(c, net, ports)
    require(
        c.nodes["126"].findtext("dco/ddo/cnst") == "1A"
        and set(bytes.fromhex(c.nodes["126"].findtext("dco/ConstValue"))) == {0},
        "null reference constant changed",
    )
    require(
        alias(c, "92", 0) == "99"
        and alias(c, "152", 0) == "151"
        and alias(c, "145", 0) == "141",
        "Close false branch tunnels changed",
    )
    require(
        alias(c, "152", 1) == "153" and alias(c, "145", 1) == "144",
        "Close null branch passthrough changed",
    )
    require(c.nodes["341"].get("class") == "mergeErrors", "Close merge changed")
    require(
        [t.get("uid") for t in terms(c.nodes["341"])] == ["352", "346", "349"],
        "Close merge priority changed",
    )
    require(
        c.nodes["341"].find("RetainAllErrors") is None, "merge retains all errors now"
    )
    require(
        "reports the first error found" in docs["merge_errors_function"],
        "Merge default policy missing",
    )
    require(
        not any(n.get("class") == "select" for n in u.nodes.values()),
        "Unregister gained a guard",
    )
    require(
        u.nodes["119"].findtext("nodeName") == '"ImaqUnRegisterSesn"',
        "unregister native boundary changed",
    )
    exact_net(u, "168", ["155", "163"])
    exact_net(u, "148", ["150", "125"])
    exact_net(u, "152", ["132", "153"])
    require(
        not any(p in ps for _, ps in u.nets for p in ("241", "244")),
        "Unregister native error ports now connected",
    )
    require(frames(i, "115") == ["123", "170"], "imgClose zero gate changed")
    primitive(i, "107", "1113")
    for net, ports in (
        ("188", ["109", "117"]),
        ("190", ["186", "120", "112"]),
        ("192", ["228", "119"]),
        ("166", ["159", "137"]),
        ("168", ["153", "141"]),
        ("203", ["136", "216"]),
        ("125", ["150", "218"]),
        ("124", ["205", "162"]),
        ("179", ["176", "175"]),
    ):
        exact_net(i, net, ports)
    require(
        i.nodes["153"].findtext("dco/ConstValue") == "00000001",
        "imgClose clean flag changed",
    )
    n = i.nodes["131"]
    require(
        n.get("class") == "extFunc"
        and n.findtext("nodeName") == '"imgClose_LV"'
        and "123" in i.ancestry("131"),
        "close native dispatch changed",
    )
    require(
        alias(i, "119", 0) == "150" and alias(i, "120", 0) == "159",
        "imgClose false branch input aliases changed",
    )
    require(
        not any(p in ps for _, ps in i.nets for p in ("304", "307")),
        "imgClose native error ports now connected",
    )
    require(not n.findtext("abortCB"), "imgClose cancellation callback changed")
    require(update.nodes["179"].get("class") == "nMux", "error update input changed")
    exact_net(update, "122", ["151", "178", "486"])
    require(
        not any(n.get("class") == "select" for n in d.nodes.values()),
        "Dispose gained a diagram-level error gate",
    )
    require(
        d.nodes["120"].findtext("nodeName") == '"LV_Dispose"', "Dispose native changed"
    )
    for net, ports in (
        ("161", ["150", "134"]),
        ("159", ["137", "152"]),
        ("165", ["141", "130"]),
        ("167", ["156", "144"]),
    ):
        exact_net(d, net, ports)
    require(
        not any(p in ps for _, ps in d.nets for p in ("202", "206")),
        "Dispose CLFN error terminals changed",
    )
    require(
        "runs normally only if no error" in docs["IMAQ_Close"],
        "Close generic-help discrepancy changed",
    )
    return {
        "library_identity": "installed NI2020 candidates, not verified deployed NI2012",
        "IMAQ_Close_gate": (
            "session==null -> pass error; non-null -> unregister then imgClose"
        ),
        "incoming_error_used_as_close_selector": False,
        "unregister": {
            "native_symbol": "ImaqUnRegisterSesn",
            "diagram_error_gate": False,
            "input_error_to_output": ["155", "163"],
            "error_cluster_not_passed_to_native": True,
        },
        "imgClose_gate": (
            "interfaceID==0 -> pass error; nonzero -> native close attempt"
        ),
        "native_close": {
            "symbol": "imgClose_LV",
            "UID": "131",
            "frame": "123",
            "clean": 1,
            "native_error_cluster_input": False,
            "native_return_code_to_error_update": ["136", "216"],
            "prior_error_only_enters_post_call_error_update": ["150", "218"],
            "success_and_bounded_return_proven": False,
        },
        "merge_priority": [
            "unregister error = incoming error",
            "post-close error update",
        ],
        "prior_error_can_hide_close_error": True,
        "Dispose": {
            "native_symbol": "LV_Dispose",
            "diagram_error_gate": False,
            "error_cluster_is_native_argument": True,
            "DLL_internal_error_short_circuit_verified": False,
            "error_contract_documented_standard": True,
            "image_type_opaque": True,
        },
        "documentation_conflict": (
            "IMAQ Close help contains generic skip-on-error boilerplate, but the "
            "examined wrapper gates on null reference and zero interface ID, not "
            "error.status. The source graph governs this candidate conclusion."
        ),
        "conclusion": (
            "A returned Dispose error does NOT by itself prevent the NI2020 "
            "candidate imgClose_LV attempt when the session is non-null and "
            "unregistration yields a nonzero interface ID. A pending Dispose or "
            "Unregister still blocks downstream progress; a failed native close "
            "can leave resources open and be hidden behind the earlier error."
        ),
    }


def dispatch_witness(
    *,
    abort_returned,
    abort_error_status,
    session_non_null,
    interface_id,
    disposal_returned=True,
    unregister_returned=True,
):
    """Supplied-state contract model, NOT a LabVIEW/native execution or test."""
    return {
        "Shutdown_wrapper_eligible": bool(abort_returned),
        "Shutdown_method_eligible_under_standard_contract": bool(
            abort_returned and not abort_error_status
        ),
        "IMAQ_candidate_native_close_eligible": bool(
            disposal_returned
            and session_non_null
            and unregister_returned
            and interface_id
        ),
        "resource_release_confirmed": False,
    }


def verify(sources=None, supporting=None, added=None):
    receipt, roots = original() if sources is None else sources
    _, libraries, _ = native_evidence() if supporting is None else supporting
    catalog, extra, docs = load_added() if added is None else added
    require(digest(BASELINE) == BASELINE_SHA, "frozen coverage evidence changed")
    require(digest(COMPARISON) == COMPARISON_SHA, "comparison definitions changed")
    definitions = json.loads(COMPARISON.read_text("utf-8"))["primitives"]
    require(
        definitions["1102"]["name"] == "Equal?"
        and definitions["1113"]["name"] == "Equal To 0?",
        "comparison meanings changed",
    )
    previous = []
    for path, sha in PREVIOUS.items():
        p = REPO / "Supervision/integration_analysis" / path
        require(digest(p) == sha, "previous cleanup qualification changed")
        previous.append({"path": str(p), "sha256": sha})
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    graphs = {name: graph(bundle, T) for name, bundle in {**libraries, **extra}.items()}
    return {
        "scope": "Static error propagation in final Supervision cleanup only",
        "source_sha256": receipt.get("source_sha256", receipt.get("sha256")),
        "observations": {
            "Main": main_chain(g),
            "motion": motion(graphs["AbortMotion"], graphs["Shutdown"], docs),
            "image": images(
                graphs["IMAQ_Close"],
                graphs["imgClose"],
                graphs["IMAQUnregisterSession"],
                graphs["IMAQ_Dispose"],
                graphs["imgUpdateErrorCluster"],
                docs,
            ),
        },
        "supported_inferences": [
            "Motion cleanup is not finally: a returned Abort error suppresses the "
            "managed Shutdown method under the documented .NET Invoke contract.",
            "Image cleanup is different: the inspected NI2020 Close graph dispatches "
            "native close independently of error.status, subject to non-null session "
            "and nonzero interface ID. Dispatch is not proof of success.",
            "The preserved prior error can obscure a later camera-close failure. "
            "An error dialog alone cannot establish whether native close succeeded.",
        ],
        "unknowns": [
            "NI2020 Close/Dispose/helper byte identity with deployed NI2012 "
            "not proven. "
            "No historical screenshots of their internal branches are available.",
            "Shutdown invokeFlags=08 is pinned but its bit-level semantics are not "
            "reverse engineered. The skip conclusion is contract-based, not a new "
            "LabVIEW2012 runtime experiment or assembly execution.",
            "LV_Dispose takes the error cluster inside opaque native code. Wrapper "
            "entry cannot prove what it frees after an incoming error; no success "
            "or idempotency claim is made for repeated All Images=True calls.",
            "Null-reference comparison is not proof every stale non-null session is "
            "valid. A non-null session may still yield interface ID zero or fail.",
            "No total close deadline, automatic reference reclamation, device safe "
            "state or complete Supervision coverage is proven.",
        ],
        "previous_evidence": previous,
        "added_input_catalog": {"path": str(INPUTS), "sha256": INPUTS_SHA},
        "saved_screenshots": catalog["saved_screenshots"],
        "screen_used": False,
        "VI_run_or_save": False,
        "native_library_loaded": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
        "guaranteed_resource_release": False,
        "full_Supervision_coverage": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    result = verify()
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")), "cleanup report differs"
        )
    else:
        OUTPUT.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({"passed": True, "output": str(OUTPUT), "sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
