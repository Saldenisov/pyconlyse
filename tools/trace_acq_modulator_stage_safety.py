"""Separate stage request wiring, cooling display and unproven permits.

Saved files only. Neither absence of a static property node nor EPS OK is
proof that a real machine can safely accept a heating/HT request.
"""
import argparse
import json

from export_sup_live_display_map import REPO, SOURCE_SHA, original, build_map, digest
from export_sup_modulator_panel import build_panel
from trace_sup_phase_status import fp_descendants
from validate_sup_modulator_request_gate import validate_tree, require
from validate_acq_cooling_flow_guard import validate as validate_flow
from validate_acq_modulator_start_event_guards import validate as validate_entries
from validate_acq_modulator_start_event_guards import checked_root, unique
from validate_sup_ht_request_gate import validate_tree as validate_ht
from legacy.xp_acq_agent.elyse_agent.acquisition_stage_model import load_model, CATALOG_SHA256


OUTPUT = REPO / "docs/ELYSE_MODULATOR_STAGE_SAFETY_2026-10-19.json"
ACQ = REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
DISABLED = {
    "67698": "61480", "67657": "59608", "67619": "42740", "67577": "40743",
    "70250": "61480", "68962": "59608", "67505": "42740", "7002": "40743",
    "269818": "19489", "186526": "19489", "267202": "19489", "267035": "19489",
}
CONTROL_REFS = {"20125": "37853", "40447": "37853", "7979": "7618",
                "33897": "83226", "20450": "20397"}
IMAGES = {
    "C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0033-event12-start-modulator-heating.png":
        "000F3F92AD1EB3C46B6A2B9A8B7B5DA3AB647CDEDDC6DE65D190F41B07D6A811",
    "C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0046-event15-focal-modulator-psp-dps.png":
        "BCD43CD852DA3615103EAAFF93920DB5EF9A7E9A4D81C8FE0A77DF6646850F42",
    "C:/dev/ELYSE-ACQ-analysis/review_20261015/native_evidence/MAIN-timeout3-cooling-guard-enabled.png":
        "5BBC9C88C1144CD42EBFDAD12BC78E5CF4AD1DBA831BB75E5765933E7ED4FCEF",
}

# All C4-input local references in the original main VI, including startup
# and final zeroing. Direction is saved gRefDCO objFlags, not label inference.
C4_REFS = {
    "8346": ("8356", "1", "1171", "4137", "sharedVariableDynamicOpen", "1168"),
    "19587": ("19590", "0", "18857", "19517", "prim", "19515"),
    "2352": ("2355", "0", "4165", "7750", "prim", "7748"),
    "25024": ("25027", "1", "42839", "4271", "sharedVariableDynamicWrite", "4245"),
    "10202": ("10214", "1", "40077", "51370", "nMux", "39336"),
    "55726": ("55729", "0", "42946", "55656", "prim", "55654"),
}


def inspect_c4_consumers(root):
    refs = {n.get("uid"): n for n in root.iter() if n.get("class") == "gRef"
            and n.findtext("termList/*/dco/paramIdx") == "16"}
    require(set(refs) == set(C4_REFS), "C4 input local-reference census changed")
    nodes = [n for n in root.iter() if n.get("class") not in (None, "diag", "term", "signal")]
    owners = {t.get("uid"): n for n in nodes for t in n.findall("termList/*")}
    rows = []
    for uid, (port, flags, net, peer, klass, owner) in C4_REFS.items():
        terms = refs[uid].findall("termList/*")
        require(len(terms) == 1 and terms[0].get("uid") == port
                and terms[0].findtext("dco/objFlags", "0") == flags,
                "C4 input reference direction changed")
        wires = [n for n in root.iter() if n.get("class") == "signal"
                 and any(t.get("uid") == port for t in n.findall("termList/*"))]
        require(len(wires) == 1 and wires[0].get("uid") == net
                and {t.get("uid") for t in wires[0].findall("termList/*")} == {port, peer},
                "C4 input reference gained/moved a net or fanout")
        require(owners[peer].get("uid") == owner and owners[peer].get("class") == klass,
                "C4 input wire peer changed")
        rows.append(dict(uid=uid, access="read" if flags == "1" else "write",
                         peer_class=klass, peer_uid=owner, net_uid=net))
    mux = unique(root, "nMux", "39336")
    require([(t.get("uid"), t.findtext("dco/i", "0")) for t in mux.findall("termList/*")]
            == [("51370", "0"), ("51373", "19"), ("53472", "38")],
            "Only directly selected C4-input local fields changed")
    return dict(references=rows, only_direct_local_unbundle_fields=[19, 38],
                klystron_fields_0_1_20_not_selected_on_these_local_read_nets=True,
                limit="Main-VI C4 local-reference census; not external control access or electrical interlocks")


def inspect_ui(roots):
    bd = roots["bd"]
    page = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    descendants = fp_descendants(page, "56140")
    require(len(descendants) == 60, "Modulateur panel descendant census changed")
    nodes = [n for n in bd.iter() if n.get("class") in ("propNode", "ctlRefConst")]
    static_targets = [n for n in nodes if n.find("ddo") is not None]
    require(not any(n.find("ddo").get("uid") in descendants for n in static_targets),
            "Modulateur gained a static property/control-reference target")
    disabled = {
        n.get("uid"): n.find("ddo").get("uid") if n.find("ddo") is not None else None
        for n in nodes if any(p.text == '"DisabledEnum"' for p in n.findall(".//PropItemName"))
    }
    require(disabled == DISABLED, "DisabledEnum property target census changed")
    refs = {n.get("uid"): n.find("ddo").get("uid")
            for n in nodes if n.get("class") == "ctlRefConst"}
    require(refs == CONTROL_REFS, "Static control-reference census changed")
    return dict(page_uid="56140", descendant_count=60,
                static_property_or_reference_targets=[], disabled_property_targets=disabled,
                static_control_references=refs,
                limit="No direct Modulateur property/reference found; not a proof about all external UI access or electrical interlocks")


def build():
    _, roots = original()
    request_wires = validate_tree(roots["bd"], roots["meta"])
    ht_wires = validate_ht(roots["bd"], roots["meta"])
    ui = inspect_ui(roots)
    c4_consumers = inspect_c4_consumers(checked_root(ACQ))
    entry_findings = validate_entries(ACQ)
    flow_findings = validate_flow(ACQ)
    for path, expected in IMAGES.items():
        require(digest(path) == expected, "Saved screenshot identity changed")
    display = build_map()["rules"]
    panel = build_panel()
    stage_model = load_model()
    general_c4 = [field for _, effects in stage_model.plan("general.stop")
                  for effect in effects if effect[0] == "write" and effect[1] == 15
                  for field, _ in effect[2]]
    ht_c4 = [field for _, effects in stage_model.plan("alimentation_ht.stop")
             for effect in effects if effect[0] == "write" and effect[1] == 15
             for field, _ in effect[2]]
    require(general_c4 == [8, 8, 17, 17, 6, 6, 4, 4, 1, 1] and ht_c4 == [19, 19],
            "General/HT stop scope changed")
    water = []
    for field, raw in ((15, 20), (16, 0), (17, 1), (18, 2), (19, 19), (45, 38)):
        rows = [r for r in display if r["page"] == "modulateur" and r["target_field"] == field]
        require(len(rows) == 1 and rows[0]["bank"] == "C4_IN_DIO96"
                and rows[0]["index"] == raw and rows[0]["transform"] == "identity",
                "Raw water display route changed")
        colors = panel["fields"][str(field)]
        require(colors["false_color"] == "#00C82D" and colors["true_color"] == "#FF3333",
                "Saved water Boolean palette changed")
        water.append(dict(raw_c4_field=raw, page_field=field, label=rows[0]["label"],
                          false_color=colors["false_color"], true_color=colors["true_color"],
                          transform="identity", electrical_polarity_qualified=False))
    return dict(
        scope="STATIC_REQUEST_DISPLAY_AND_PROCEDURE_BOUNDARIES_NOT_OPERATING_PERMISSION",
        source_supervision_vi_sha256=SOURCE_SHA,
        source_acquisition_vi_sha256="6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
        observations=dict(modulateur_request_wires=request_wires, ht_request_wires=ht_wires,
                          main_ui_property_census=ui, acq_start_entries=entry_findings,
                          acq_c4_local_reference_census=c4_consumers,
                          water_display=water, timeout_flow_guard=flow_findings,
                          stage_catalog_sha256=CATALOG_SHA256,
                          source_stage_count=16, modeled_source_frames=len(stage_model._frames),
                          general_stop_c4_field_sequence=general_c4,
                          alimentation_ht_stop_c4_field_sequence=ht_c4,
                          general_stop_does_not_directly_command_ht_supply_stop=True,
                          guard_is_not_klystron_body_collector_permission=True,
                          eps_ok_is_software_assignment_not_hardware_ack=True),
        inferences=[
            "The five reviewed start handlers do not enforce a preceding-stage or raw-water predicate at entry",
            "These main-VI request and property paths do not establish a klystron cooling admission interlock",
            "The Canon/Section timeout cooling-stop predicate cannot substitute for a Chauffage permit",
            "General stop and HT-supply stop are distinct commands; relay behavior cannot be inferred from software status alone",
        ],
        unresolved=[
            "Electrical truth table and independent interlocks for body/collector/focal water inputs",
            "Physical flow readiness and behavior on flow loss during heating",
            "Actual Chroma COM10/COM11/COM12 mapping and bounded ON/OFF behavior",
            "Installed VI version, asynchronous writer timing and fault/reset behavior",
            "Complete staged live-control state machine and qualified installation shutdown",
        ],
        saved_screenshots=IMAGES, screen_used=False, vi_run_or_saved=False,
        hardware_commands_sent=False, current_runtime_or_startup_changed=False,
        complete_live_control=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.write:
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    require(json.loads(OUTPUT.read_text("utf-8")) == result, "Stage safety report differs")
    print("PASS: 16 request wires, five start entries, six C4 local references, 12 DisabledEnum nodes, six water displays; no hardware")


if __name__ == "__main__":
    main()
