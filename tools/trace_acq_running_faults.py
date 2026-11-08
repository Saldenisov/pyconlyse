"""Offline post-start fault/stop provenance, never a hardware safety model.

Inventory every C4-output and DPS local writer before drawing an absence
conclusion. Keep cooling commands, requested stage stops and loop exits
distinct. Print JSON or compare the report with --check; no network I/O.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from trace_acq_local_cluster_uses import scope_path
from trace_acq_modulator_stage_safety import ACQ, inspect_c4_consumers
from trace_acq_stage_admission import graph_index
from trace_acq_water_chroma_power import bank_labels
from trace_acq_water_chroma_power import MEMBERS
from validate_acq_dio96_exchange import checked_roots, validate_callers, validate_exchange
from validate_acq_event_envelopes import validate_envelopes as validate_event_envelopes
from validate_acq_lifecycle_envelopes import validate_envelopes
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_publication import validate_tree as validate_publication
from validate_acq_stop_ingress import validate as validate_ingress
from validate_acq_stop_state_memory import validate_memory
from validate_acq_stop_ui_bindings import checked_trees
from validate_acq_timeout_cooling_sequence import validate_cooling
from validate_acq_timeout_reads import validate_reads

from DeviceServers.control.elyse_acq.vi_simulation.timeout_cooling import cooling_guard, trip_frame


REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "docs/ELYSE_ACQ_RUNNING_FAULT_RESPONSE_2026-10-19.json"
NATIVE = REPO / "docs/ELYSE_ACQ_NATIVE_STATIC_OBSERVATIONS_2026-10-15.json"
STOP_FIELDS = {4: "Chauffage", 6: "PREMA", 8: "Focales"}
STOP_SITES = {
    "23331": (4, False, "event7"), "23408": (4, True, "event7"),
    "25754": (4, False, "event6"), "29481": (4, True, "event6"),
    "43368": (4, False, "outer_controlled_stop"), "43434": (4, True, "outer_controlled_stop"),
    "26272": (6, False, "event8"), "26356": (6, True, "event8"),
    "36883": (6, False, "event6"), "23595": (6, True, "event6"),
    "43217": (6, False, "outer_controlled_stop"), "43280": (6, True, "outer_controlled_stop"),
    "54844": (8, False, "event10"), "23792": (8, True, "event10"),
    "55143": (8, False, "event6"), "31209": (8, True, "event6"),
    "42452": (8, False, "outer_controlled_stop"), "42582": (8, True, "outer_controlled_stop"),
}


def writer_census(root, bank):
    owners, links = graph_index(root)
    parents = {c: n for n in root.iter() for c in n}
    refs = [n for n in root.iter() if n.get("class") == "gRef"
            and n.findtext("termList/*/dco/paramIdx") == str(bank)]
    writers = [n for n in refs if int(n.findtext("termList/*/objFlags", "0")) & 0x8000]
    expected = {15: (145, 68, 66, "16132", "25478", "25426", "25443"),
                36: (82, 28, 26, "31118", "87", "19950", "19968")}[bank]
    total, count, bundles, startup, remote, reader, data = expected
    require(len(refs) == total and len(writers) == count, "Output/request writer census changed")
    kinds, fields, whole = Counter(), [], []
    for writer in writers:
        port = writer.find("termList/*").get("uid")
        net, peers = links[port]
        require(len(peers) == 1, "Writer gained another source")
        source, term = owners[peers[0]]
        kind = source.get("class")
        kinds[kind] += 1
        scope = scope_path(writer, parents)
        if kind == "nMux":
            ts = source.findall("termList/*")
            require(source.findtext("objFlags") == "262144" and ts[0] is term,
                    "Output/request producer is not a Bundle output")
            for leaf in ts[2:]:
                values = [owners[p][1].findtext("dco/ConstValue")
                          for p in links[leaf.get("uid")][1]
                          if owners[p][0].get("class") == "sRN"]
                require(len(values) == 1 and values[0] in ("0000", "01"),
                        "Output/request field has a nonliteral or ambiguous producer")
                fields.append(dict(writer=writer.get("uid"), bundle=source.get("uid"),
                                   field=int(leaf.findtext("dco/i", "0")),
                                   value=values[0] == "01", scope=scope))
        else:
            require((writer.get("uid") == startup and kind == "sRN"
                     and term.findtext("dco/ConstValue") is not None)
                    or (writer.get("uid") == remote and kind == "sharedVariableDynamicRead"
                        and source.get("uid") == reader and term.get("uid") == data),
                    "Unreviewed whole-cluster output/request writer")
            whole.append(dict(writer=writer.get("uid"), source_class=kind,
                              source_uid=source.get("uid"), source_port=term.get("uid"),
                              scope=scope))
    require(dict(kinds) == {"sRN": 1, "sharedVariableDynamicRead": 1, "nMux": bundles},
            "Output/request producer classes changed")
    if bank == 36:
        require(all(row["value"] is False for row in fields),
                "DPS gained an internal True request producer")
    return dict(local_references=total, local_writers=count, producer_classes=dict(kinds),
                fields=fields, whole_cluster_writers=whole)


def inspect_stop_sites(c4):
    selected = [r for r in c4["fields"] if r["field"] in STOP_FIELDS]
    actual = {}
    for row in selected:
        scope = row["scope"]
        if "sequence:359[3]/select:43488[1]" in scope:
            require("select:52981[1]/sequence:51954[4]" in scope,
                    "Stage stop is outside Arrêt général controlled-stop gate")
            tag = "outer_controlled_stop"
        else:
            matches = [n for n in (6, 7, 8, 10) if "eventStruct:43[" + str(n) + "]/" in scope]
            require(len(matches) == 1, "Stage stop gained an unreviewed automatic path")
            tag = "event" + str(matches[0])
        actual[row["writer"]] = (row["field"], row["value"], tag)
    require(actual == STOP_SITES, "Complete three-stage stop writer set changed")
    return selected


def inspect_native():
    record = json.loads(NATIVE.read_text("utf-8"))
    require(record["source_vi_sha256"]
            == "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
            and record["no_native_run_or_save"] is True
            and record["native_original_lv2012_runtime_equivalence"] is False,
            "Native evidence scope changed")
    row = next(n for n in record["comment_nodes"] if n["uid"] == "14478")
    require(row["observed_active_index"] == 0 and row["active_arm_contains_controller_operations"] is True,
            "Specific native20 enabled-arm observation changed")
    images = ["MAIN-timeout3-active-branch-selector.png",
              "MAIN-timeout3-cooling-guard-enabled.png"] + record["cooling_guard"]["images"]
    hashes = {}
    for name in images:
        path = Path(record["image_directory"]) / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        require(actual == record["image_sha256"][name], "Frozen cooling image changed")
        hashes[str(path)] = actual
    return dict(specific_native_version=record["native_executable_file_version"],
                nonempty_arm_seen_enabled=True, original_lv2012_runtime_equivalence=False,
                image_hashes=hashes)


def build(root=None, fp=None, meta=None):
    if root is None:
        root, fp, meta = checked_trees()
    c4_inputs = inspect_c4_consumers(root)
    _, links = graph_index(root)
    require("5678" not in links, "C4 input FP terminal gained a hidden predicate")
    control = unique(fp, "fPDCO", "5676")
    require(control.findtext("conNum") == "-1", "C4 input gained a public connector")
    c4_out, dps = writer_census(root, 15), writer_census(root, 36)
    sites = inspect_stop_sites(c4_out)
    cooling = validate_cooling(root, meta)
    # Separate error/loop-stop ingress from a hardware-fault response.
    stop_memory = validate_memory(root, meta)
    envelopes = validate_envelopes(root, meta)
    publication = validate_publication(root)
    reads = validate_reads(root, meta)
    events = validate_event_envelopes(root, meta)
    dio = [validate_callers(root), validate_exchange(checked_roots(MEMBERS))]
    c4_labels = bank_labels(root, meta, 16)
    result = dict(
        date="2026-10-19", scope="ORIGINAL_ACQUISITION_POST_START_FAULT_PROVENANCE_NOT_PHYSICAL_PROTECTION",
        source_vi_sha256="6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
        observations=dict(
            c4_input_census=c4_inputs,
            klystron_status_fields_not_selected_for_local_trip={str(i): c4_labels[i]
                for i in tuple(range(19)) + (20, 21, 22, 23)},
            c4_output_writer_summary={k: v for k, v in c4_out.items() if k != "fields"},
            all_three_stage_stop_field_writers=sites,
            dps_writer_census=dps,
            cooling=dict(
                condition="(C4_IN[19] OR C4_IN[38]) AND ((NOT C3_IN[0]) OR (NOT C3_IN[6]))",
                input_labels={"C4_IN[19]": c4_labels[19], "C4_IN[38]": c4_labels[38],
                              "C3_IN[0]": bank_labels(root, meta, 18)[0],
                              "C3_IN[6]": bank_labels(root, meta, 18)[6]},
                execution_context="Event43 Timeout frame3, nonempty Diagram Disable14478 arm",
                false_arm="empty: no stop, reset or automatic restart",
                direct_card_command_intents=[
                    [0, "C3_OUT_DIO96", 1, False], [1, "C3_OUT_DIO96", 1, True],
                    [3, "C3_OUT_DIO96", 4, False], [4, "C3_OUT_DIO96", 4, True]],
                requested_wait_ms=[150, None, 400, 150, None, None, 100],
                status_assignments={"EPS[1]": True, "EPS[2]": False,
                                    "EPS[3]": False, "EPS[5]": True, "DPS[1]": False},
                unchanged_by_this_branch=["C4_OUT_DIO96", "EPS[8,14,20,26,32]",
                                          "EPS[13,19,31]", "DPS[3,5,7,11]", "stop30", "TCP ED45"],
                publication="fresh DPS snapshot -> SUPERVISION/DPS -> Simple Error Handler39603",
                proof=cooling, native=inspect_native()),
            driver_path="C3_OUT local2378 -> ClusterToArray8127 -> DIO helper686 connector2 -> C3 DAQmx Write2840 data2868; errors precede C4 write38",
            other_stage_stop_paths=[
                "DPS[5/7/11] signaling EPS[15/21/33] -> events7/8/10 -> NewVal=True -> C4[4/6/8] False->True",
                "DPS[3] signaling EPS[9] -> event6 General Arrêt -> Focales OFF, then C4[8,17,6,4,1] False->True",
                "Outer stop: leave runtime frame2, TCP ED45=True, then Arrêt général47=True -> controlled stop stage phase4",
            ],
            psp_error_limits=[
                "Two publication error True arms set stop30=True and TCP ED45=True",
                "Timeout final read-error True arm instead sets both False; last-writer ordering is not fixed",
                "Five runtime loops each sample stop30 independently; blocked or in-flight calls have no cancellation proven here",
                "A loop exit alone is not a stage stop; outer staged stop additionally requires its TCP/general gates",
            ],
            supporting_proofs=dict(stop_memory=stop_memory, lifecycle=envelopes,
                                   runtime_publication=publication, timeout_reads=reads,
                                   event_envelopes=events, dio=dio)),
        supported_conclusions=[
            "No automatic software stop of these three stages is sourced from the local klystron water/vacuum/oil/current fault bits in this pinned main VI",
            "The four-input cooling branch commands only Canon and Section cooling stop lines, not Chauffage/PREMA/Focales stop lines or Chroma OFF",
            "All26 fieldwise DPS bundles write False only: no local fault-to-True stop request producer exists in this census",
            "Stage OK flags can remain True after this cooling branch; that is a software-state example, not proof supplies remain physically energized",
        ],
        boundaries=[
            "Raw Boolean polarity and actual loss-of-water transitions are not electrically qualified",
            "Incoming PSP whole clusters may change C4_OUT, DPS and EPS; external Supervision/VI-server actors are outside this local response proof",
            "The specific saved native20 import shows the cooling arm enabled; deployed LV2012 source/activation is not certified",
            "Timeout is configured20ms but shares Event43 with long stage procedures, including Focales29s wait and instrument calls",
            "No safety-response deadline, repeat-pulse rate or physical pulse width is guaranteed; assignments/Wait are unordered inside a frame",
            "NI failures/modal handler aborts are distinct from decoded hardware défaut; no complete LV2012 driver-error safe-shutdown claim is made",
            "Independent cabinet protection, actual relay wiring, physical shutdown and the deployed executable remain unverified",
        ],
        screen_used=False, hardware_commands_sent=False, vi_run_or_saved=False,
        runtime_code_changed=False, qualifies_hardware_start=False,
    )
    return json.loads(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        require(json.loads(OUTPUT.read_text("utf-8")) == result, "Running-fault report differs")
        print("PASS: complete C4/DPS writer censuses, cooling reaction and separate stage/loop stops; no hardware")
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
