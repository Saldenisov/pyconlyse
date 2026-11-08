"""Supervision saved-source completion ledger and NewFocus initialization trace.

Reuses frozen focused proofs without turning inventories into semantic coverage.
Only XML/files and supplied-return witnesses; no VI, GUI, native or hardware IO.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from export_sup_beam_indicator_routes import (
    BASELINE,
    BASELINE_SHA,
    SourceGraph,
    components,
)
from export_sup_live_display_map import REPO, digest, original
from trace_sup_beam_switches import terms
from trace_sup_cleanup_errors import images, load_added
from trace_sup_normal_stop import bool_constant
from trace_sup_phase_status import exact_net
from validate_sup_modulator_request_gate import require

FOLDER = REPO / "Supervision/integration_analysis/completion_audit_20261017"
OUTPUT = FOLDER / "RESULT.json"
INPUTS = FOLDER / "INPUTS.json"
INPUTS_SHA = "FD876B370E71E96AAA745E75B31E1615A1302C61F1ED0ADEC361116D7734EFE2"
RECEIPT = REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/receipt.json"
RECEIPT_SHA = "266206C05CADD3798B5EF4C6C43A76B8AD737830F53DBFC15E080BAF405743FB"
MOTOR = (
    REPO / "Supervision/analysis/lvkit_eval/parser_motor_release_20261003/receipt.json"
)
MOTOR_SHA = "1A8B1ED604D2D1365981973F9C89D9D542161753B6C1A274AC89448A9BA17825"
DIRECT_OUTPUT = (
    REPO
    / "Supervision/integration_analysis/direct_comparison_complete_20261017/RESULT.json"
)
DIRECT_SHA = "2CEB3001D35C1631B183151DFC7D11EBD5A6B549752A6FE80F7457518DD422E1"
STATES = {
    "CmdLib Out": (244, "61437", "61443", "273836", "273843"),
    "DeviceKey Out": (246, "61750", "61762", "286518", "286525"),
    "Device Address Out": (248, "77644", "77648", "91956", "95313"),
}


def pinned(path, sha):
    require(digest(path) == sha, f"source evidence changed: {path}")
    return json.loads(Path(path).read_text("utf-8"))


def load_inputs():
    catalog = pinned(INPUTS, INPUTS_SHA)
    remote, proofs = {}, {}
    for row in catalog["remote_cleanup"]:
        r = pinned(row["path"], row["sha256"])
        require(digest(r["source"]) == r["sha256"], "remote candidate VI changed")
        require(digest(r["archive"]) == r["archive_sha256"], "remote archive changed")
        roots = {}
        for key, item in zip(("bd", "fp", "meta"), r["xml"], strict=True):
            require(digest(item["path"]) == item["sha256"], "remote XML changed")
            roots[key] = ET.parse(item["path"]).getroot()
        remote[row["name"]] = (r, roots)
    for row in catalog["prior_focused_proofs"]:
        proofs[row["name"]] = pinned(row["path"], row["sha256"])
    for row in (
        catalog["historical_boundaries"]
        + catalog["saved_screenshots"]
        + catalog["local_help"]
        + [catalog["extractor"]]
    ):
        require(
            digest(row["path"]) == row["sha256"], "completion supporting input changed"
        )
    return catalog, remote, proofs


def inventory():
    index = pinned(RECEIPT, RECEIPT_SHA)
    entries = [(r["vi"], pinned(r["path"], r["sha256"])) for r in index["rows"]]
    entries.append(("Moteurs SdC GoTo.vi", pinned(MOTOR, MOTOR_SHA)))
    require(
        len(entries) == len({name for name, _ in entries}) == 39,
        "Supervision application member scope changed",
    )
    rows = []
    for name, r in entries:
        require(digest(r["source"]) == r["sha256"], "original VI changed")
        for item in r["xml"]:
            require(digest(item["path"]) == item["sha256"], "original XML changed")
        bd = ET.parse(r["xml"][0]["path"]).getroot()
        classes = Counter(n.get("class") for n in bd.iter() if n.get("class"))
        calls = Counter(
            n.findtext("label/textRec/text")
            for n in bd.iter()
            if n.get("class") == "iUse"
        )
        rows.append(
            {
                "name": name,
                "source": r["source"],
                "sha256": r["sha256"],
                "diagram_count": classes["diag"],
                "classes": dict(sorted(classes.items())),
                "VI_calls": [
                    {"name": k, "count": v}
                    for k, v in sorted(calls.items(), key=lambda kv: str(kv[0]))
                ],
                "original_bytes_and_XML_verified": True,
                "inventory_is_full_behavior_proof": False,
            }
        )
    return rows


def aliases(g, port):
    return [n.get("uid") for n in g.nodes[port].findall("dco/termList/*")]


def initialize(g, receipt):
    """Direct-wire proof, preserving native returns and unqualified scalar spans."""
    events = [n.get("uid") for n in g.nodes["5909"].findall("diagramList/*")]
    require(len(events) == 34 and events[27] == "248031", "init event ordinal changed")
    require(
        [n.get("uid") for n in g.nodes["250659"].findall("diagramList/*")]
        == ["250667", "266154", "88075"],
        "manual init phase order changed",
    )
    require(
        [n.get("uid") for n in g.nodes["683198"].findall("diagramList/*")]
        == ["683208", "683486"],
        "startup motor phase order changed",
    )
    for call in ("70317", "274396"):
        require(
            g.nodes[call].findtext("label/textRec/text") == '"InitSingleDevice.vi"',
            "NewFocus discovery target changed",
        )
    controls = {r["uid"]: r for r in receipt["locals"]}
    state_routes = []
    for name, (bank, control, fp, writer, port) in STATES.items():
        require(
            g.nodes[fp].get("class") == "fPTerm"
            and g.nodes[fp].find("dco").get("uid") == control,
            "startup target changed",
        )
        binding = controls[writer]
        require(
            binding["param_idx"] == bank
            and binding["control_uid"] == control
            and binding["name"] == name
            and g.is_input(g.nodes[port]),
            "startup/manual target identity differs",
        )
        writers = [
            uid
            for uid, row in controls.items()
            if row["param_idx"] == bank and g.is_input(terms(g.nodes[uid])[0])
        ]
        require(writers == [writer], "handle bank gained another named local writer")
        state_routes.append(
            {
                "name": name,
                "bank": bank,
                "FP_control": control,
                "startup_terminal": fp,
                "manual_writer": writer,
                "manual_terminal": port,
                "same_state_bank": True,
            }
        )
    for uid, raw in (
        ("61835", "00001388"),
        ("274090", "00001388"),
        ("62100", "00000004"),
        ("274188", "00000004"),
    ):
        require(
            g.nodes[uid].findtext("dco/ConstValue") == raw,
            "discovery delay/motor count changed",
        )
    for net, ports in (
        ("62636", ["61835", "70344"]),
        ("74304", ["274090", "274417"]),
        ("62812", ["70335", "61944", "61443"]),
        ("74289", ["274408", "274131", "273843"]),
        ("62806", ["70332", "61955", "61920"]),
        ("62753", ["61914", "61928"]),
        ("74330", ["274405", "274141", "274115"]),
        ("74316", ["274112", "274121"]),
        ("62563", ["61960", "74161", "61762"]),
        ("77688", ["74196", "77648"]),
        ("274386", ["274145", "274335", "286525"]),
        ("101692", ["274344", "95313"]),
        ("62074", ["61953", "61942"]),
        ("274179", ["274139", "274129"]),
    ):
        exact_net(g, net, ports)
    branches = []
    for select, length_node, positive, empty, err_in, err_out in (
        ("61925", "61909", "62087", "61965", "61950", "61937"),
        ("274119", "274110", "274182", "274148", "274136", "274126"),
    ):
        node = g.nodes[select]
        require(
            g.nodes[length_node].findtext("primResID") == "1502",
            "device key length calculation changed",
        )
        require(
            [n.get("uid") for n in node.findall("diagramList/*")] == [empty, positive],
            "discovery branches changed",
        )
        require(
            node.findtext("SelectDefaultCase") == "01", "nonempty-key default changed"
        )
        require(
            [
                (n.findtext("start"), n.findtext("end"), n.findtext("diagramIdx"))
                for n in node.findall("SelectRangeArray32/*")
            ]
            == [("0", "0", "0"), ("1", "1", "1")],
            "device-key ranges changed",
        )
        require(
            not any(
                n.get("class") in ("gRef", "fPTerm", "iUse", "nMux", "mux")
                for n in g.nodes[empty].iter()
            ),
            "empty-key branch gained state updates or an error setter",
        )
        require(
            "274182" in g.ancestry("286518") and "274182" in g.ancestry("91956"),
            "manual key/address write guard changed",
        )
        branches.append(
            {
                "selector": select,
                "zero_length": empty,
                "nonzero_length_default": positive,
                "empty_key_error_passthrough": [
                    aliases(g, err_in)[0],
                    aliases(g, err_out)[0],
                ],
                "empty_key_sets_failure_error": False,
            }
        )
    require(
        "266154" in g.ancestry("273836") and "274119" not in g.ancestry("273836"),
        "CmdLib assignment became key-conditional",
    )
    loops = []
    for (
        uid,
        count,
        input_port,
        inner_input,
        output_port,
        inner_output,
        call,
        motor_inc,
    ) in (
        ("62157", "62100", "62164", "62168", "62175", "62188", "77355", "62444"),
        (
            "274199",
            "274188",
            "274205",
            "274208",
            "274211",
            "274214",
            "274246",
            "274238",
        ),
    ):
        node = g.nodes[uid]
        require(
            node.get("class") == "forLoop"
            and not node.findall("srDCOList/*")
            and not node.findall("ConditionDCOList/*"),
            "zero-position loop gained feedback or early-exit condition",
        )
        require(
            g.nodes[input_port].find("dco").get("class") == "lpTun"
            and aliases(g, input_port) == [inner_input, input_port],
            "zero-position error input no longer invariant tunnel",
        )
        require(
            aliases(g, output_port) == [inner_output, output_port],
            "zero-position output tunnel changed",
        )
        require(
            g.table.heap(g.nodes[output_port].findtext("dco/typeDesc")).get("Type")
            == "Cluster",
            "zero-position output is no longer scalar cluster",
        )
        require(
            g.nodes[call].findtext("label/textRec/text") == '"SetZeroPosition.vi"'
            and g.nodes[motor_inc].findtext("primResID") == "1057",
            "zero-position command or motor increment changed",
        )
        require(uid in g.ancestry(call), "zero command left loop")
        loops.append(
            {
                "loop": uid,
                "count_literal": count,
                "iterations_when_calls_return": 4,
                "motor_indices": "loop i incremented:1..4",
                "call": call,
                "error_input_is_invariant_tunnel": True,
                "error_output_is_scalar_last_iteration": True,
                "per_motor_error_feedback_or_early_stop": False,
            }
        )
    for net, ports in (
        ("62514", ["62100", "62159"]),
        ("274368", ["274188", "274201"]),
        ("62558", ["74261", "62164"]),
        ("62505", ["62168", "77419"]),
        ("62497", ["77432", "62188"]),
        ("62547", ["62175", "61943"]),
        ("274383", ["274365", "274205"]),
        ("274312", ["274208", "274282"]),
        ("274309", ["274294", "274214"]),
        ("274380", ["274211", "274130"]),
        ("62469", ["62332", "62456"]),
        ("62466", ["62448", "77412"]),
        ("274303", ["274235", "274243"]),
        ("274300", ["274240", "274276"]),
        ("102227", ["96738", "96613", "96647", "96676", "96701", "96726"]),
        ("122479", ["122475", "105435"]),
    ):
        exact_net(g, net, ports)
    bool_constant(g, "96738", True)
    bool_constant(g, "122475", False)
    for uid in ("93919", "96626", "96661", "96686", "96711"):
        require(
            g.nodes[uid].get("class") == "propNode"
            and "88075" in g.ancestry(uid)
            and "77627" not in g.ancestry(uid),
            "motion controls gained success gating",
        )
    shutdown = [
        uid
        for uid, n in g.nodes.items()
        if n.get("class") == "iUse"
        and n.findtext("label/textRec/text") == '"Shutdown.vi"'
    ]
    require(
        shutdown == ["192398"] and "14127" in g.ancestry("192398"),
        "Shutdown site census changed",
    )
    return {
        "manual_event": 27,
        "state_banks": state_routes,
        "discovery_delay_ms": 5000,
        "delay_is_total_initialization_deadline": False,
        "key_length_branches": branches,
        "zero_position_loops": loops,
        "manual_post_phase": {
            "frame": "88075",
            "movement_buttons_Visible_requested": True,
            "Initialisation_requested": False,
            "property_writes_outside_error_case": True,
        },
        "no_source_Shutdown_before_manual_reinitialization": True,
        "inferences": [
            "Startup and manual initialization target the SAME three stored banks, "
            "not independent handle sets. Startup uses FP terminals; manual init "
            "uses local aliases of those exact controls.",
            "After the manual discovery stage returns with an empty key, CmdLib "
            "has an unconditional replacement request, but DeviceKey/address "
            "have no assignment in the zero-length arm. Old key/address can remain "
            "paired with the new reference. This is a supplied-state counterexample, "
            "not an observed live stale-handle incident.",
            "Missing-device branch shows a modal message but does not itself set "
            "error.status=True. After the modal/earlier calls return, the final "
            "phase requests movement-button visibility without success gating.",
            "Each SetZeroPosition receives the same GetIdentification error via an "
            "ordinary loop tunnel, not the preceding motor error. Scalar output "
            "reports the last iteration: a returned failure on motor1..3 can be "
            "hidden by a successful motor4. This is not homing or a proof of motion.",
            "No original Main Shutdown call precedes manual replacement. Native "
            "internal cleanup is unknown, so a resource leak is not asserted.",
        ],
        "limits": [
            "Five-byte device-address literals are not decoded as assumed zero.",
            "Native return values, automatic disposal and UI property success "
            "are unverified.",
            "A blocked discovery, identification, zeroing call or modal dialog "
            "prevents the next phase.",
        ],
    }


def init_witness(
    previous_key,
    previous_address,
    new_reference,
    discovery_key,
    identification_address,
    zero_error_statuses,
    discovery_error=False,
):
    """Original local assignment/last-value witness with explicitly supplied returns."""
    require(type(discovery_key) is str, "supplied key must be a string")
    require(
        len(zero_error_statuses) == 4
        and all(type(v) is bool for v in zero_error_statuses),
        "four supplied motor statuses required",
    )
    found = bool(discovery_key)
    return {
        "CmdLib": new_reference,
        "DeviceKey": discovery_key if found else previous_key,
        "DeviceAddress": identification_address if found else previous_address,
        "out_error_status": zero_error_statuses[-1] if found else discovery_error,
        "button_visibility_request_after_return": True,
        "native_or_hardware_executed": False,
    }


def remote_cleanup(remote):
    _, _, docs = load_added()
    T, _ = components()
    graphs = {
        name: SourceGraph(r, roots, T(roots["meta"]))
        for name, (r, roots) in remote.items()
    }
    result = images(
        *(
            graphs[n]
            for n in (
                "IMAQ_Close",
                "imgClose",
                "IMAQUnregisterSession",
                "IMAQ_Dispose",
                "imgUpdateErrorCluster",
            )
        ),
        docs,
    )
    result["library_identity"] = (
        "copied remote_labview2012 archives; loaded identity unverified"
    )
    result["conclusion"] = (
        "The same null-session/nonzero-ID/native-close/error-merge predicates pass "
        "against all five copied NI2012 wrappers. This extends the NI2020 candidate "
        "finding to the saved remote copy, not to a currently loaded DLL "
        "or successful close."
    )
    return {
        "observations": result,
        "members": [
            {
                "name": name,
                "source_sha256": r["sha256"],
                "archive": r["archive"],
                "archive_sha256": r["archive_sha256"],
            }
            for name, (r, _) in sorted(remote.items())
        ],
        "same_selected_wire_predicates_as_NI2020": True,
        "native_library_equivalence": False,
    }


def verify(sources=None, added=None):
    receipt, roots = original() if sources is None else sources
    catalog, remote, _ = load_inputs() if added is None else added
    require(digest(BASELINE) == BASELINE_SHA, "frozen baseline changed")
    T, _ = components()
    g = SourceGraph(receipt, roots, T(roots["meta"]))
    members = inventory()
    direct = pinned(DIRECT_OUTPUT, DIRECT_SHA)
    require(
        direct["source_sha256"]
        == "5CD315417FDFC2FA5115D0C26D3450825E5EF54441A9C43FC6D0F6C0A9E45333"
        and direct["complete_source_defined_output_model_within_domain"]
        and not direct["native_connector_or_runtime_equivalence"],
        "direct comparison model source/domain changed",
    )
    whole = next(
        row
        for row in catalog["historical_boundaries"]
        if Path(row["path"]).name == "WHOLE_VI_STATUS.json"
    )
    old_status = json.loads(Path(whole["path"]).read_text("utf-8"))
    sup = [r for r in old_status["per_VI_original_baseline"] if r["program"] == "SUP"]
    return {
        "scope": (
            "Supervision original-source ledger, initialization/resource-state "
            "and copied NI2012 cleanup"
        ),
        "source_sha256": receipt["sha256"],
        "original_application_VIs": members,
        "member_count": len(members),
        "focused_proofs_reused": catalog["prior_focused_proofs"],
        "new_initialization_findings": initialize(g, receipt),
        "copied_remote_NI2012_cleanup": remote_cleanup(remote),
        "additional_finite_source_model": {
            "path": str(DIRECT_OUTPUT),
            "sha256": DIRECT_SHA,
            "source": "2_SUP_Ecart_lu_ecr_VDirecte.vi",
            "complete_final_OUT_projection_within_declared_domain": True,
            "complete_native_VI_replacement": False,
        },
        "completion_criteria": {
            "all_39_original_VI_and_XML_identities_accounted": True,
            "all_original_source_control_behavior_proven": False,
            "all_saved_screenshots_source_hash_bound_at_capture": False,
            "complete_Python_business_logic_replacement": False,
            "full_Supervision_coverage": False,
        },
        "remaining_source_work_not_replaced_by_inventory": {
            "historical_SUP_member_rows_still_not_whole_closed": len(sup),
            "historical_status_not_recomputed_as_current_coverage_percent": True,
            "concrete_source_obligations": [
                {
                    "source": "2_SUP_Graph _Radioprot.vi",
                    "obligation": (
                        "Original DCO780 five-byte UInt32 framing, absent named "
                        "field selection, quotient/remainder/coercion and "
                        "retained False-arm state."
                    ),
                },
                {
                    "source": "Search and Replace Pattern.vi",
                    "obligation": (
                        "Original DefaultData333 I32 framing, loop termination/"
                        "defaults and byte-pattern grammar; no native "
                        "string-equivalence claim."
                    ),
                },
                {
                    "source": "Validate.vi",
                    "obligation": (
                        "Original consumed Path/literal framing and validity/"
                        "encoding; not a caller-supplied-literal shortcut."
                    ),
                },
                {
                    "source": "Main event/value/property and camera/motor paths",
                    "obligation": (
                        "Finish whole-VI dependency closure for complex Event "
                        "NewVal/OldVal, remaining saved-state/field/coercion "
                        "facts and bounded procedure models."
                    ),
                },
            ],
            "separate_deployment_obligations": [
                "Actual PSP delivery, coherent snapshots, reconnect and "
                "native IO deadlines.",
                "Loaded NI/NewFocus version/overload identity and actual "
                "resource-close success.",
                "Current physical owner/limits and hardware response; "
                "not a static-source closure task.",
            ],
        },
        "saved_screenshots": catalog["saved_screenshots"],
        "screen_used": False,
        "VI_run_or_save": False,
        "native_library_loaded": False,
        "network_io": False,
        "hardware_io": False,
        "production_changes": False,
        "previous_frozen_reports_changed": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    result = verify()
    if args.check:
        require(
            result == json.loads(OUTPUT.read_text("utf-8")), "completion report differs"
        )
    else:
        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"passed": True, "output": str(OUTPUT), "sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
