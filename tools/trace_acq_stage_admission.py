"""Offline EPS/request/event/DIO admission proof, not a hardware permit.

Reads hash-pinned original XML and historical images only. Prints a report
or compares it with --check; never runs LabVIEW or imports a device adapter.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build_acq_modulator_catalog import build as build_catalog
from trace_acq_modulator_stage_safety import ACQ, inspect_c4_consumers
from trace_acq_water_chroma_power import MEMBERS, SAVED_IMAGES, bank_labels, flatten_frames
from validate_acq_dio96_exchange import checked_roots, validate_callers, validate_exchange
from validate_acq_event_envelopes import validate_envelopes
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import validate_trees as validate_runtime_io
from validate_acq_timeout_reads import validate_reads
from validate_acq_vam_status import checked_vam


REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "docs/ELYSE_ACQ_STAGE_ADMISSION_2026-10-19.json"
FP = REPO / ".tmp/acq_original_diagram_census_20261001/0_ACQ_ELYSE/vi_FPHb.xml"
FP_SHA = "000E82C66074929C7A9C7434B66629ADF6934C411AB85109E663BF0474F49E72"
ROWS = (
    ("chauffage.start", 4, 12, 12, 14, 17, 3, "66579", "29098"),
    ("prema.start", 6, 13, 18, 20, 23, 5, "66627", "30677"),
    ("focales.start", 10, 15, 30, 32, 35, 7, "66723", "32446"),
)
READERS = {
    "21596", "34455", "18634", "19942", "39289", "18624", "22985",
    "35509", "28788", "24858", "27587", "31423", "23961", "34353",
    "38540", "29087", "36391", "40520", "32292", "39536", "42997",
    "31683", "35778", "49466", "43842", "43979", "54186", "47280",
    "32180", "32559", "33571", "45333", "45469", "41230", "41371",
    "39636", "39878", "54673", "58864",
}


def graph_index(root):
    owners, links = {}, {}
    for node in root.iter():
        for term in node.findall("termList/*[@class='term']"):
            uid = term.get("uid")
            require(uid not in owners, "Duplicate immediate terminal owner")
            owners[uid] = (node, term)
        if node.get("class") == "signal":
            ports = [t.get("uid") for t in node.findall("termList/*")]
            for port in ports:
                require(port not in links, "Terminal joined to multiple independent signals")
                links[port] = (node.get("uid"), [p for p in ports if p != port])
    return owners, links


def inspect_eps(root, meta):
    owners, links = graph_index(root)
    refs = [n for n in root.iter() if n.get("class") == "gRef"
            and n.findtext("termList/*/dco/paramIdx") == "44"]
    readers = [n for n in refs if n.findtext("termList/*/dco/objFlags") == "1"]
    require(all(n.findtext("termList/*/dco/objFlags", "0") in ("0", "1") for n in refs),
            "EPS local direction flags changed")
    require(len(refs) == 66 and len(refs) - len(readers) == 27,
            "EPS reference census changed")
    require({n.get("uid") for n in readers} == READERS, "EPS reader census changed")
    rows, assignments, categories = [], [], Counter()
    for ref in readers:
        port = ref.find("termList/*").get("uid")
        net, peers = links[port]
        require(len(peers) == 1, "EPS reader gained another consumer")
        node, term = owners[peers[0]]
        kind = node.get("class")
        if kind == "nMux":
            ts = node.findall("termList/*")
            require(node.findtext("objFlags") == "262144"
                    and ts[1] is term
                    and ts[0].find("dco").get("uid") == ts[1].find("dco").get("uid")
                    and ts[0].findtext("dco/objFlags") == "1",
                    "EPS read is not exclusively a Bundle base input")
            out = links[ts[0].get("uid")][1]
            require(len(out) == 1, "EPS bundle output gained a consumer")
            target, target_term = owners[out[0]]
            require(target.get("class") == "gRef"
                    and target_term.findtext("dco/paramIdx") == "44"
                    and target_term.findtext("dco/objFlags", "0") == "0",
                    "EPS Bundle no longer feeds only an EPS local writer")
            values = []
            for leaf in ts[2:]:
                require(int(leaf.findtext("objFlags", "0")) & 0x8000,
                        "EPS Bundle field is not an input")
                leaf_peers = links[leaf.get("uid")][1]
                require(len(leaf_peers) >= 1, "EPS Bundle field has no producer")
                constants = [owners[p][1].findtext("dco/ConstValue")
                             for p in leaf_peers if owners[p][0].get("class") == "sRN"]
                require(len(constants) == 1 and constants[0] in ("01", "0000"),
                        "EPS field now depends on a nonliteral expression")
                values.append([int(leaf.findtext("dco/i", "0")), constants[0] == "01"])
            assignments.append(dict(bundle_uid=node.get("uid"),
                                    writer_uid=target.get("uid"), fields=values))
            category = "preserve_other_fields_in_literal_bundle"
        else:
            expected = {
                "sharedVariableDynamicOpen": ("21963", "21977"),
                "sharedVariableDynamicRead": ("19997", "20012"),
            }
            require(kind == "sharedVariableDynamicWrite"
                    or expected.get(kind) == (node.get("uid"), term.get("uid")),
                    "EPS read has an unreviewed consumer")
            category = kind
        categories[category] += 1
        rows.append(dict(reader_uid=ref.get("uid"), port=port, net_uid=net,
                         consumer_uid=node.get("uid"), consumer_port=term.get("uid"),
                         category=category))
    require(dict(categories) == {
        "sharedVariableDynamicOpen": 1, "sharedVariableDynamicWrite": 12,
        "sharedVariableDynamicRead": 1, "preserve_other_fields_in_literal_bundle": 25,
    }, "EPS reader category census changed")
    # Main EPS front-panel terminal cannot provide a separate predicate path.
    terminal = unique(root, "fPTerm", "66774")
    require(terminal is not None and terminal.find("dco").get("uid") == "66772"
            and "66774" not in links, "EPS front-panel terminal gained a wire")
    ed_fields = {13, 19, 31}
    require(not any(i in ed_fields for row in assignments for i, _ in row["fields"]),
            "Stage ED flags gained a direct fieldwise writer")
    return dict(total_local_references=66, readers=rows, reader_categories=dict(categories),
                literal_fieldwise_writers=assignments,
                direct_fieldwise_writers_of_start_ed_13_19_31=[],
                other_writes=["startup all-zero cluster", "Timeout PSP whole-cluster replacement"],
                direct_eps_predicate_read_found=False, unwired_front_panel_terminal="66774")


def checked_fp():
    require(hashlib.sha256(FP.read_bytes()).hexdigest().upper() == FP_SHA,
            "Original EPS front-panel export changed")
    return ET.parse(FP).getroot()


def inspect_targets(root, fp):
    eps = unique(fp, "fPDCO", "66772")
    require(eps.findtext("conNum") == "-1", "EPS gained public VI connector")
    cluster = eps.find("ddo")
    require(cluster.get("uid") == "59243", "EPS parent DDO changed")
    fields = [n.get("uid") for n in cluster.findall("ddoList/*")]
    require(len(fields) == 77, "EPS field count changed")
    targets = [n for n in root.iter()
               if n.find("ddo") is not None
               and n.find("ddo").get("uid") in set(fields + ["59243"])]
    require(len(targets) == 24 and all(n.get("class") == "propNode" for n in targets),
            "EPS static property/reference census changed")
    require(all([p.text for p in n.findall(".//PropItemName")]
                == ['"Value"', '"Val(Sgnl)"'] for n in targets),
            "EPS properties gained another operation or read")
    require(all(t.findtext("dco/objFlags", "0") == "0"
                and int(t.findtext("objFlags", "0")) & 0x8000
                for n in targets for t in n.findall("termList/*")
                if t.find("dco/propList") is not None),
            "EPS property gained a read-side value")
    for _, _, event, request, _, _, _, ddo, prop in ROWS:
        require(fields[request] == ddo
                and unique(root, "propNode", prop).find("ddo").get("uid") == ddo,
                "DPS dispatch no longer targets expected EPS request field")
        specs = unique(root, "eventStruct", "43").findall("EventNodeEvents/*")
        require([x.findtext("diagramIdx") for x in specs if x.findtext("ddoUID") == ddo]
                == [str(event)], "EPS request event registration changed")
    return dict(eps_parent_ddo="59243", public_connector=-1,
                static_property_targets=24, all_static_properties="Value then Val(Sgnl), both True",
                limit="Direct local/static access only; external VI-server access is not excluded")


def stage_paths(catalog, labels):
    result = []
    for name, dps, event, request, ok, stopped, bit, ddo, prop in ROWS:
        procedure = catalog["procedures"][name]
        require(procedure["dps_request_field"] == dps and procedure["event"] == event,
                "Stage request/event identity changed")
        effects = list(flatten_frames(procedure["frames"]))
        c4 = [[frame, i, v] for frame, e in effects if e[:2] == ["write", 15]
              for i, v in e[2]]
        require([[i, v] for _, i, v in c4]
                == [[bit, True], [bit, False], [2, True], [2, False]],
                "Stage C4 command/reset order changed")
        eps_writes = [[i, v] for _, e in effects if e[:2] == ["write", 44] for i, v in e[2]]
        require(dict(eps_writes) == {request: False, ok: True, stopped: False},
                "Stage completion EPS assignments changed")
        result.append(dict(operation=name, dps_request=dps, eps_request=request,
                           eps_request_label=labels[request], property_uid=prop,
                           event=event, event_target_ddo=ddo, entry_condition="NewVal=True",
                           prior_eps_ok_or_ed_checked=[], prior_water_or_general_checked=[],
                           c4_assignments=c4, eps_completion_assignments=eps_writes,
                           focal_helper="1_Focales ON.vi" if event == 15 else None))
    return result


def build():
    root, meta = checked_vam(ACQ)
    eps = inspect_eps(root, meta)
    targets = inspect_targets(root, checked_fp())
    # These validators pin complete nets/operations, not only matching captions.
    proofs = [validate_reads(root, meta), validate_envelopes(root, meta),
              validate_runtime_io(root, meta), validate_callers(root),
              validate_exchange(checked_roots(MEMBERS))]
    catalog = build_catalog()  # Includes complete dispatch, procedure and Chroma graphs.
    return dict(
        date="2026-10-19", scope="PINNED_ACQUISITION_ADMISSION_NOT_ELECTRICAL_PERMISSION",
        source_vi_sha256="6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
        observations=dict(eps=eps, eps_request_targets=targets,
                          stages=stage_paths(catalog, bank_labels(root, meta, 44)),
                          c4_input_consumers=inspect_c4_consumers(root), proofs=proofs,
                          first_true_dps_dispatch="lowest True among 29 bits -> index+1 -> one explicit arm for DPS[0..23]",
                          runtime_write_path=[
                              "C4_OUT gRef2362:2365 -> ClusterToArray8025 -> helper686:694 (connector1)",
                              "1_ACQ_RW_DIO96: C4 DO local4826:4829 -> DAQmx Write38:4773",
                              "C4 DO task field4; digital1D Boolean selector0E; autoStart=True",
                              "NI6071E error -> DIO96; C3/C4/C5 reads -> C3/C4/C5 writes via errors",
                              "C4 write error-in4786 from C3 write2892; error-out4798 to C5 write5301",
                          ],
                          no_eps_action_or_water_mask_in_runtime_io=True,
                          focal_delay_ms=29000,
                          historical_image_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest().upper()
                                                   for p in SAVED_IMAGES[:3]}),
        supported_conclusions=[
            "No preceding EPS OK/ED, General, vacuum/oil/water admission predicate exists on these reviewed main-VI start-event or DIO data paths",
            "EPS request fields12/18/30 are signaling targets; EPS14/20/32 are later literal software completion flags, not input permits or hardware ACK",
            "EPS start ED13/19/31 have no direct fieldwise writers in this main graph; startup zeroing and whole-cluster PSP replacement can still change them",
            "DPS request arbitration, event scheduling, handler progress and the separate DIO loop are necessary execution boundaries, not physical safety permits",
        ],
        execution_limits=[
            "Lower-index DPS True can defer a later request; no queued delivery or bounded request latency is proven",
            "PSP failures/stale snapshots and unwired property error outputs do not establish successful request delivery",
            "Timeout and stage handlers share EventStructure43; Timeout cannot run between frames of one active stage event",
            "A later Timeout can replace local EPS and C4_OUT from remote whole-cluster snapshots; no snapshot freshness or atomicity is proven",
            "Assignments and Wait in one frame are unordered; separate NI loop might miss a short local pulse; no electrical pulse duration is proven",
            "Focales adds Chroma initialization/configuration/output-enable and Simple Error Handler; blocking/abort can prevent later frames",
            "Native DAQmx incoming-error/timeout behavior and physical write success are external boundaries, not established by these wrapper wires",
        ],
        unresolved=[
            "Which cabinet contacts/electrical safety logic actually block each supply and the Chroma mains contactor",
            "Installed source identity, pin polarity, physical wiring and current plant readiness",
            "Dynamic external VI-server access is not ruled out by this local static census",
        ],
        screen_used=False, hardware_commands_sent=False, vi_run_or_saved=False,
        runtime_code_changed=False, qualifies_hardware_start=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.check:
        require(json.loads(OUTPUT.read_text("utf-8")) == report, "Stage admission report differs")
        print("PASS: 66 EPS references, 39 read consumers, three signaling/event/output paths; no hardware")
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
