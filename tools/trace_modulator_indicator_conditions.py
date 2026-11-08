"""Prove Modulateur indicator colours and the all-green summary, offline.

The summary is not silently promoted to hardware permission. Raw NI Boolean
inputs, numeric measurements, source update frames and command gates remain
distinct. No VI, transport, native driver or device is executed.
"""

import argparse
import json
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from build_acq_modulator_catalog import build as build_catalog
from export_sup_beam_indicator_routes import SourceGraph, components
from export_sup_live_display_map import REPO, SOURCE_SHA, build_map, digest, original
from export_sup_modulator_panel import build_panel
from trace_acq_modulator_stage_safety import ACQ, inspect_c4_consumers, inspect_ui
from trace_acq_water_chroma_power import MEMBERS, bank_labels
from validate_acq_dio96_exchange import checked_roots, validate_callers, validate_exchange
from validate_acq_ni6703_writer import connected_group
from validate_acq_modulator_start_event_guards import validate as validate_entries
from validate_acq_vam_status import checked_vam
from validate_sup_modulator_request_gate import require, validate_tree


OUTPUT = REPO / "docs/ELYSE_MODULATOR_INDICATOR_CONDITIONS_2026-10-19.json"
SUMMARY_FIELDS = tuple(range(21)) + tuple(range(24, 31))
PAGE_REFS = {
    "27866": (0, "27819"), "27806": (1, "27819"),
    "51331": (0, "51304"), "29513": (1, "51304"),
    "42295": (0, "40520"), "29734": (1, "40520"),
    "58462": (0, "58415"), "50324": (1, "58415"),
    "43324": (1, "43337"), "48140": (1, "48148"),
    "53652": (5, "61263"), "53632": (0, "61263"),
}
WRITER_FIELDS = {
    "27819": [21, 22, 23, 46, 47, 48, 49, 50, 51, 52, 53],
    "51304": [3, 4, 7, 8, 9, 11, 13, 14, 16, 17, 18, 20, 27, 28, 29, 30],
    "40520": [0, 1, 2, 5, 6, 10, 12, 15, 19, 24, 25, 26, 45],
    "58415": list(range(31, 45)),
    "61263": list(range(54, 59)),
}
RAW_ROUTES = {
    0: 21, 1: 22, 2: 23, 3: 9, 4: 8, 5: 44, 6: 45, 7: 16,
    8: 12, 9: 15, 10: 18, 11: 4, 12: 39, 13: 17, 14: 5,
    15: 20, 16: 0, 17: 1, 18: 2, 19: 19, 20: 3,
    24: 43, 25: 42, 26: 41, 27: 6, 28: 7, 29: 11, 30: 14, 45: 38,
}
IMAGES = [
    REPO / "Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd147.png",
    REPO / "Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd148.png",
    REPO / "Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_18_full.png",
]


def graph_for(receipt, roots):
    table, _ = components()
    return SourceGraph(receipt, roots, table(roots["meta"]))


def exact_wire(graph, port, expected):
    nets = [(uid, ports) for uid, ports in graph.nets if port in ports]
    require(len(nets) == 1 and set(nets[0][1]) == set(expected),
            "Indicator/summary wire gained or changed a consumer")
    return nets[0][0]


def verify_summary(receipt, roots):
    graph = graph_for(receipt, roots)
    sequence = graph.nodes["49452"]
    require([d.get("uid") for d in sequence.findall("diagramList/*")]
            == ["49456", "36356", "52158", "39589", "45182", "4090",
                "54248", "4108", "60654", "48713", "9031", "73806"],
            "Summary sequence frame order changed")
    require(graph.nodes["9424"].findall("diagramList/*")[8].get("uid") == "27313"
            and "27313" in graph.ancestry("49452"), "Summary parent changed")
    steps = []
    for frame_uid, mux_uid, compound_uid, fields, ops in (
        ("39589", "43337", "43385", list(range(21)),
         [("label", "38821"), ("label", "15790"), ("cpdArith", "43385"),
          ("label", "43473"), ("nMux", "43337"), ("gRef", "43324")]),
        ("45182", "48148", "48228", list(range(24, 31)),
         [("gRef", "49489"), ("label", "48303"), ("label", "48304"),
          ("cpdArith", "48228"), ("label", "48305"), ("nMux", "48148"),
          ("gRef", "48140")]),
    ):
        frame, mux, compound = (graph.nodes[u] for u in (frame_uid, mux_uid, compound_uid))
        require([(n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*")] == ops,
                "Summary direct operation/if census changed")
        require(int(compound.findtext("objFlags")) == 659456
                and ((int(compound.findtext("objFlags")) >> 16) & 7) == 2,
                "Summary is no longer the saved AND operation")
        source = graph.mux_local(mux_uid, "Page Modulateur")
        used = {exact_wire(graph, source["reference_terminal"],
                           [source["reference_terminal"], source["aggregate_terminal"]])}
        source_terms = mux.findall("termList/*")[1:]
        require(len(source_terms) == len(fields), "Summary source field count changed")
        inputs = compound.findall("termList/*")[1:]
        require(len(inputs) == len(fields) + (frame_uid == "45182"),
                "Summary AND input count changed")
        wires = []
        for field, src, dst in zip(fields, source_terms, inputs):
            # This one native-print-confirmed first field omits i in XML.
            # Qualify its exact terminal only; never default arbitrary missing
            # indices to zero (SourceGraph intentionally leaves those unknown).
            raw_index = src.findtext("dco/i")
            require((field == 0 and src.get("uid") == "43342" and raw_index is None)
                    or (field != 0 and raw_index == str(field)),
                    "Summary field ordinal changed")
            require(dst.findtext("dco/objFlags") == "327680",
                    "Summary fault-input inversion changed")
            net = exact_wire(graph, src.get("uid"), [src.get("uid"), dst.get("uid")])
            used.add(net)
            wires.append([field, src.get("uid"), dst.get("uid"), net])
        output = compound.find("termList/*")
        require(output.findtext("dco/objFlags") == "131073",
                "Summary output gained inversion")
        if frame_uid == "39589":
            used.add(exact_wire(graph, output.get("uid"), ["43387", "47307"]))
        else:
            require(inputs[-1].get("uid") == "47507"
                    and inputs[-1].findtext("dco/objFlags") == "262144",
                    "Prior summary input/inversion changed")
            used.add(exact_wire(graph, "47507", ["48133", "47507"]))
            used.add(exact_wire(graph, output.get("uid"), ["48230", "49492"]))
        require({n.get("uid") for n in frame.findall("signalList/*")} == used,
                "Unaccounted summary net/if path")
        steps.append(dict(frame_uid=frame_uid, compound_uid=compound_uid,
                          page_fields=fields, operation="AND of inverted fault inputs",
                          wires=wires))
    locals_ = sequence.findall("seqLocDCOList/*")
    local = [n for n in locals_ if n.get("uid") == "38745"]
    require(len(local) == 1 and local[0].findtext("diagDefined") == "03"
            and [t.get("uid") for t in local[0].findall("termList/*")]
            == ["47294", "47298", "47302", "47307", "48133", "4111",
                "54267", "36426", "60661", "48720", "9708", "73815"],
            "Summary frame3-to-frame4 sequence-local binding changed")
    refs = [n for n in graph.nodes.values() if n.get("class") == "gRef"
            and n.findtext("termList/*/dco/paramIdx") == "60"]
    require(len(refs) == 1 and refs[0].get("uid") == "49489"
            and refs[0].findtext("termList/*/dco/objFlags", "0") == "0",
            "Somme Modulateur gained a local reader/other writer")
    require(all("27771" not in ports for _, ports in graph.nets),
            "Somme Modulateur front-panel terminal gained a wire")
    require(all(n.find("ddo") is None or n.find("ddo").get("uid") != "27757"
                for n in graph.nodes.values() if n.get("class") in ("propNode", "ctlRefConst")),
            "Somme Modulateur gained a static property/control-reference consumer")
    fp = [n for n in roots["fp"].iter() if n.get("class") == "fPDCO" and n.get("uid") == "27769"]
    require(len(fp) == 1 and fp[0].findtext("conNum") == "-1",
            "Summary control gained a public connector")
    return dict(steps=steps, formula="AND(NOT PageMod[0:21]) AND AND(NOT PageMod[24:31])",
                native_qualified_omitted_zero_terminal="43342: I Focale 1, native print d147; not a general missing-index rule",
                included_fields=list(SUMMARY_FIELDS), excludes_eau_section_field=45,
                summary_local_param=60, summary_local_writers=["49489"],
                summary_local_readers=[], front_panel_terminal_unwired=True,
                statically_addressed_property_consumers=[], public_connector=False,
                statically_connected_to_command_gate=False,
                snapshot_limit="Frame3 and frame4 read separate Page Modulateur snapshots, not one atomic hardware snapshot")


def verify_page_consumers(receipt, roots):
    graph = graph_for(receipt, roots)
    refs = {n.get("uid"): n for n in graph.nodes.values() if n.get("class") == "gRef"
            and n.findtext("termList/*/dco/paramIdx") == "164"}
    require(set(refs) == set(PAGE_REFS), "Page Modulateur reference census changed")
    for uid, (flags, mux) in PAGE_REFS.items():
        port = refs[uid].find("termList/*")
        require(int(port.findtext("dco/objFlags", "0")) == flags,
                "Page Modulateur reference direction/flags changed")
        _, peer, owner = graph.peer(port.get("uid"), "nMux")
        require(owner.get("uid") == mux, "Page Modulateur consumer changed")
        exact_wire(graph, port.get("uid"), [port.get("uid"), peer])
    for mux, fields in WRITER_FIELDS.items():
        selected = [int(t.findtext("dco/i", "0"))
                    for t in graph.nodes[mux].findall("termList/*")
                    if graph.is_input(t) and t.find("dco").get("class") == "nmxDCO"]
        require(sorted(selected) == fields, "Page Modulateur writer fields changed")
    require(all("56537" not in ports for _, ports in graph.nets),
            "Page Modulateur main terminal gained a wire")
    return dict(local_references=len(refs), writers=WRITER_FIELDS,
                two_summary_readers=["43324", "48140"],
                other_reads="Base snapshots for whole-cluster bundle updates",
                main_front_panel_terminal_unwired=True,
                concurrency_limit="Read-modify-write updates can restore retained old fields; no atomic current-state guarantee")


def project_summary(page_frame3, page_frame4):
    """Pure two-snapshot summary, never permission to start any stage."""
    first, second = tuple(page_frame3), tuple(page_frame4)
    require(len(first) == len(second) == 59, "Two explicit 59-field page snapshots required")
    values = [first[i] for i in range(21)] + [second[i] for i in range(24, 31)]
    require(all(type(v) is bool for v in values), "Selected summary fields must be Boolean")
    return all(not v for v in values)


def verify_acq_input_terminal(root):
    # MEMBERS is archive-hash-checked by checked_roots before this function.
    with ZipFile(MEMBERS) as archive:
        fp = ET.fromstring(archive.read("0_ACQ_ELYSE.vi/vi_FPHb.xml"))
    controls = [n for n in fp.iter() if n.get("class") == "fPDCO" and n.get("uid") == "5676"]
    require(len(controls) == 1 and controls[0].findtext("conNum") == "-1"
            and '"C4_IN_DIO96"' in [t.text for t in controls[0].findall("ddo/partsList/*/textRec/text")],
            "ACQ C4 raw input control identity/connector changed")
    terminals = [t for n in root.iter() for t in n.findall("termList/*")
                 if t.get("class") == "fPTerm" and t.find("dco") is not None
                 and t.find("dco").get("uid") == "5676"]
    require(len(terminals) == 1 and terminals[0].get("uid") == "5678",
            "ACQ C4 main input terminal changed")
    require(all(t.get("uid") != "5678" for n in root.iter() if n.get("class") == "signal"
                for t in n.findall("termList/*")), "ACQ C4 input terminal gained a guard wire")
    return dict(control_uid="5676", terminal_uid="5678", wired=False, public_connector=False)


def verify_acq_provenance(root, dio_roots):
    """Pin the DAQmx data wire and every main-VI C4 input-bank assignment."""
    helper = validate_exchange(dio_roots)
    callers = validate_callers(root)
    bd = dio_roots["vi_BDHb.xml"]
    body = next(n for n in bd.iter() if n.get("class") == "diag" and n.get("uid") == "1684")
    require(connected_group(body, "2688") == {"2688", "3084"},
            "Raw C4 DAQmx read data gained a calculation/filter")
    rows = []
    for phase, call_uid, conversion_uid, writer_uid in (
        ("startup I/O", "19376", "19515", "19587"),
        ("runtime I/O", "686", "7748", "2352"),
        ("controlled-stop I/O", "55502", "55654", "55726"),
    ):
        call = next(n for n in root.iter() if n.get("class") == "iUse" and n.get("uid") == call_uid)
        conversion = next(n for n in root.iter() if n.get("class") == "prim" and n.get("uid") == conversion_uid)
        writer = next(n for n in root.iter() if n.get("class") == "gRef" and n.get("uid") == writer_uid)
        rows.append(dict(phase=phase, dio_helper_call=call_uid,
                         helper_c4_output_terminal=call.findall("termList/*")[6].get("uid"),
                         converter_uid=conversion_uid, conversion="Array To Cluster, no predicate",
                         converter_array_input=conversion.findall("termList/*")[1].get("uid"),
                         converter_cluster_output=conversion.findall("termList/*")[0].get("uid"),
                         c4_input_writer=writer_uid, writer_terminal=writer.find("termList/*").get("uid")))
    consumers = inspect_c4_consumers(root)
    require({r["uid"] for r in consumers["references"] if r["access"] == "write"}
            == {"19587", "2352", "55726"}, "C4 bank gained another value producer")
    return dict(helper_proof=helper, caller_proof=callers,
                hardware_api_boundary="DAQmx Read.vi, saved Digital 1D Boolean selector 0F",
                read_node_uid="667", read_data_terminal="2688", helper_output_local_terminal="3084",
                helper_output_connector=6, main_assignments=rows,
                software_vacuum_oil_water_threshold_found=False,
                electrical_signal_source_identified=False,
                deployed_runtime_identity_verified=False,
                distinction="ACQ computes separate EPS procedure flags and writes DO commands; these C4 input bits are readback, not those computed flags")


def build():
    receipt, roots = original()
    summary = verify_summary(receipt, roots)
    page_consumers = verify_page_consumers(receipt, roots)
    request_proof = validate_tree(roots["bd"], roots["meta"])
    ui = inspect_ui(roots)
    acq, meta = checked_vam(ACQ)
    acq_consumers = inspect_c4_consumers(acq)
    starts = validate_entries(ACQ)
    catalog = build_catalog()
    dio_roots = checked_roots(MEMBERS)
    dio = validate_exchange(dio_roots)
    acq_provenance = verify_acq_provenance(acq, dio_roots)
    acq_input_terminal = verify_acq_input_terminal(acq)
    raw_labels = bank_labels(acq, meta, 16)
    rules = build_map()["rules"]
    palette = build_panel()["fields"]
    faults = [r for r in rules if r["page"] == "modulateur" and r["bank"] == "C4_IN_DIO96"]
    require({r["target_field"]: r["index"] for r in faults} == RAW_ROUTES,
            "Modulateur raw digital indicator route census changed")
    rows = []
    for r in sorted(faults, key=lambda r: r["target_field"]):
        field = r["target_field"]
        require(r["kind"] == "boolean" and r["transform"] == "identity"
                and palette[str(field)]["false_color"] == "#00C82D"
                and palette[str(field)]["true_color"] == "#FF3333",
                "Raw digital indicator now has a different transform/palette")
        rows.append(dict(page_field=field, label=r["label"], c4_field=r["index"],
                         raw_source_label=raw_labels[r["index"]],
                         source_terminal=r["source_terminal"], target_terminal=r["target_terminal"],
                         red_condition="raw Boolean True", green_condition="raw Boolean False",
                         included_in_summary=field in SUMMARY_FIELDS))
    return dict(
        scope="STATIC_INDICATOR_CONDITIONS_AND_CONSUMERS_NOT_HARDWARE_INTERLOCK_QUALIFICATION",
        source_supervision_sha256=SOURCE_SHA,
        source_acquisition_sha256="6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
        observations=dict(raw_digital_indicators=rows, all_green_summary=summary,
                          page_consumers=page_consumers, ui_reference_proof=ui,
                          supervision_request_proof=request_proof,
                          acq_start_entry_proof=starts, acq_c4_consumers=acq_consumers,
                          acq_c4_main_terminal=acq_input_terminal,
                          acq_c4_value_provenance=acq_provenance,
                          acq_command_procedures_source_checked=len(catalog["procedures"]),
                          dio_source_proof=dio,
                          label_identity_limit="C4[39] is Reserve in ACQ but Resistivite in SUP; C4[19] is Debit EAU CANON in ACQ but Eau section et canon in SUP. Labels do not qualify physical wiring."),
        conclusions=[
            "Oil level, klystron vacuum, water and V/I status icons are direct NI digital Boolean readbacks, not software comparisons of the displayed analogue measurements",
            "A software AND of 28 green conditions exists, including klystron vacuum and oil level; EAU SECTION is not part of this summary",
            "The summary has one local writer, no local readers, an unwired main terminal and no statically addressed property consumer in this saved main VI",
            "Reviewed Supervision and ACQ startup command paths do not consume this summary as a permission predicate",
        ],
        unresolved=[
            "Electrical sensors/comparators and contact polarity that generate each NI digital input",
            "Which physical interlock inhibits each cabinet contactor; a complete electrical schematic is required",
            "External VI Server/dynamic access, different deployed VI versions and stale/error readback validity are not qualified by this static main-VI trace",
        ],
        evidence_images={str(path): digest(path) for path in IMAGES},
        image_limit="Saved native prints support the two AND frames; source hashes pin XML separately, not original screenshot session provenance",
        screen_used=False, hardware_commands_sent=False, vi_run_or_saved=False,
        runtime_changed=False, safe_to_start_without_cooling=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        require(json.loads(OUTPUT.read_text("utf-8")) == result, "Indicator conditions report differs")
        print("PASS: 29 raw alarm lamps, 28-input AND, 12 page references, summary sink and separate start gates; no hardware")
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
