"""Offline water-display -> stage-request -> Chroma power-intent crosswalk.

Only pinned local XML, saved images and inert source validators are read.
No operating permission or electrical interlock truth table is inferred.
"""

import argparse
import json
from pathlib import Path

from build_acq_modulator_catalog import build as build_catalog
from export_sup_live_display_map import REPO, digest
from trace_acq_modulator_stage_safety import ACQ, build as build_safety
from validate_acq_dio96_exchange import checked_roots, validate_callers, validate_exchange
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_timeout_cooling_sequence import validate_cooling
from validate_acq_vam_status import checked_vam


OUTPUT = REPO / "docs/ELYSE_WATER_CHROMA_POWER_TRACE_2026-10-19.json"
MEMBERS = REPO / "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip"
STAGES = (
    ("chauffage.start", 46, 4, 12, 3, [150, 3000, 150, 100]),
    ("prema.start", 48, 6, 13, 5, [150, 500, 150, 250, 100]),
    ("focales.start", 52, 10, 15, 7, [150, 29000, 1500, 150, 250, 100]),
)
OUTPUT_LABELS = {
    2: "02 CPC2 b61 RAZ modulateur Bas Niveau",
    3: "03 CPC3 b59 Marche Chauffage",
    5: "05 CPC5 b55 Marche prémagnétisation",
    7: "07 CPC7 b51 Marche focale Klystron",
}
WATER_LABELS = {
    0: "00 APA0 b47 Eau corps Klystron",
    1: "01 APA1 b45 Eau collecteur Klystron",
    2: "02 APA2 b43 Eau cuve Klystron",
    19: "19 APC3 b09 Débit EAU CANON",
    20: "20 APC4 b07 Eau focale Klystron",
    38: "38 BPB6 b20 Débit EAU SECTION",
}
SAVED_IMAGES = (
    Path("C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0033-event12-start-modulator-heating.png"),
    Path("C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0034-event13-start-premagnetization.png"),
    Path("C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0046-event15-focal-modulator-psp-dps.png"),
    Path("C:/dev/ELYSE-ACQ-analysis/review_20261015/native_evidence/MAIN-timeout3-cooling-guard-enabled.png"),
    REPO / "Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_18_full.png",
)


def bank_labels(root, meta, bank):
    refs = [n for n in root.iter() if n.get("class") == "gRef"
            and n.findtext("termList/*/dco/paramIdx") == str(bank)]
    require(bool(refs), "Bank local absent")
    ident = refs[0].findtext("termList/*/dco/typeDesc")
    require(ident.startswith("TypeID(") and ident.endswith(")"), "Bank type absent")
    cluster, flat = heap_type(meta, int(ident[7:-1]))
    require(cluster.get("Type") == "Cluster", "Bank type is not a cluster")
    return [flat[int(c.get("TypeID"))].get("Label") for c in cluster.findall("TypeDesc")]


def inspect_labels(root, meta):
    result = {}
    for bank, expected, name in ((15, OUTPUT_LABELS, "C4_OUT_DIO96"),
                                 (16, WATER_LABELS, "C4_IN_DIO96")):
        labels = bank_labels(root, meta, bank)
        require(all(labels[i] == text for i, text in expected.items()),
                "Actual cluster field labels changed; do not use constant captions")
        result[name] = {str(i): labels[i] for i in expected}
    comments = {
        "40228": '"Marche des alimentations\ndes focales du modulateur"',
        "40319": '"Délais pour les alimentations CHROMA"',
    }
    for uid, expected in comments.items():
        require(unique(root, "label", uid).findtext("textRec/text") == expected,
                "Focal power-intent annotation changed")
    result["focal_annotations"] = comments
    return result


def flatten_frames(frames):
    for uid, effects in frames:
        for effect in effects:
            if effect[0] == "subsequence":
                yield from flatten_frames(effect[1])
            else:
                yield uid, effect


def inspect_stages(catalog, labels):
    rows = []
    for name, button, request, event, command, waits in STAGES:
        procedure = catalog["procedures"][name]
        require(procedure["event"] == event and procedure["dps_request_field"] == request,
                "Stage request/event identity changed")
        effects = list(flatten_frames(procedure["frames"]))
        c4 = [[uid, index, value] for uid, effect in effects
              if effect[0] == "write" and effect[1] == 15
              for index, value in effect[2]]
        require([[i, v] for _, i, v in c4]
                == [[command, True], [command, False], [2, True], [2, False]],
                "Stage C4 start/reset command order changed")
        require([e[1] for _, e in effects if e[0] == "wait"] == waits,
                "Stage requested Wait arguments changed")
        helpers = [[uid, e[1]] for uid, e in effects if e[0].startswith("call_")]
        require(helpers == ([["48404", "1_Focales ON.vi"]] if event == 15 else []),
                "Stage helper boundary changed")
        rows.append(dict(
            operation=name, supervision_page_field=button, dps_field=request,
            acq_event=event, c4_command_label=labels["C4_OUT_DIO96"][str(command)],
            c4_assignments=c4, requested_waits_ms=waits, helper_frames=helpers,
            source_entry_predicate="Boolean event NewVal=True only",
            software_water_admission_predicate_found=False,
            eps_ok_is_hardware_ack=False,
        ))
    return rows


def build():
    safety = build_safety()
    catalog = build_catalog()
    root, meta = checked_vam(ACQ)
    labels = inspect_labels(root, meta)
    stages = inspect_stages(catalog, labels)
    cooling_proof = validate_cooling(root, meta)
    dio = dict(helper=validate_exchange(checked_roots(MEMBERS)),
               root_callers=validate_callers(root),
               software_water_mask_in_reviewed_dio_writer=False)
    focal = catalog["focal_helpers"]
    require(focal["output_on"]["1_Focales ON.vi"] is True
            and focal["parallel_branches"] is True,
            "Focal ON output/parallel command graph changed")
    return dict(
        scope="PINNED_SOURCE_REQUESTS_WATER_INDICATORS_AND_CHROMA_POWER_INTENT_NOT_ELECTRICAL_PERMISSION",
        date="2026-10-19",
        source_acquisition_vi_sha256=safety["source_acquisition_vi_sha256"],
        source_supervision_vi_sha256=safety["source_supervision_vi_sha256"],
        observations=dict(
            actual_cluster_labels=labels,
            water_displays=safety["observations"]["water_display"],
            supervision_request_gate="All 29 local DPS bits False; not a water or preceding-stage gate",
            source_stage_paths=stages,
            acq_c4_local_consumers=safety["observations"]["acq_c4_local_reference_census"],
            dio_dataflow=dio,
            focal_on_helpers=focal,
            focal_power_sequence=[
                "C4_OUT_DIO96[7]=True with independent Wait(150 ms), then next frame [7]=False",
                "Nested cell 46840: Wait(29000 ms); no supply-ready polling or water input",
                "Nested cell 48404: 1_Focales ON.vi -> Simple Error Handler",
                "Three independent branches: Initialize(query=False, reset=True) -> V -> current slew -> I -> Set Output(True) -> Close",
                "Nested cell 49054: Wait(1500 ms)",
                "C4_OUT_DIO96[2]=True with independent Wait(150 ms), then next frame [2]=False",
                "Wait(250 ms), software EPS completion and DPS request reset/publication",
            ],
            cooling_trip_predicate="(C4_IN[19] OR C4_IN[38]) AND ((NOT C3_IN[0]) OR (NOT C3_IN[6]))",
            cooling_trip_source_proof=cooling_proof,
            cooling_trip_direct_commands="Stop Canon cooling C3_OUT[1] False->True, then Section cooling C3_OUT[4] False->True; not direct Chauffage/PREMA/Focal/General stop",
        ),
        supported_inferences=[
            "The reviewed Supervision request, ACQ start events, Focales helper and DIO writer do not implement a software klystron-water admission gate",
            "Saved C4[7] command and CHROMA delay annotation support intended cabinet focal-supply energization before serial DC-output enable",
            "The DIO cabinet-start request and Chroma Set Output(True) are separate control layers; no serial call proves mains power was applied",
            "Red water indicators and a dark Chroma display alone do not identify the electrical blocking contact or its per-stage truth table",
        ],
        unresolved=[
            "Which body/collector/tank/focal cooling contacts electrically block Chauffage, PREMA, Focales or the Chroma mains contactor",
            "Whether C4_OUT[7], labeled CPC7 b51, actually energizes all three Chroma mains supplies, and through which relay/contactor",
            "Hardware polarity, cable routing, independent safety logic and present physical state",
            "Saved-source equality with currently deployed VI and external driver/instrument outcomes",
        ],
        evidence_images={str(path): digest(path) for path in SAVED_IMAGES},
        image_limit="Historical screenshots show selected frames only; complete command order is proved by pinned XML, not a new full native-frame sweep",
        user_reported_circulation=False,
        screen_used=False, vi_run_or_saved=False, serial_ports_opened=False,
        hardware_commands_sent=False, runtime_or_readiness_flags_changed=False,
        qualifies_hardware_start=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare saved diagnostic report")
    args = parser.parse_args()
    result = build()
    if args.check:
        require(json.loads(OUTPUT.read_text("utf-8")) == result, "Water/Chroma report differs")
        print("PASS: three stage paths, six water displays, focal DIO/delay/serial layers and unmasked DIO writer; no hardware")
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
