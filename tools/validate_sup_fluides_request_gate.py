"""Check saved Supervision Page Fluides event 14, entirely offline.

Usage: python tools/validate_sup_fluides_request_gate.py SOURCE_EXPORT_ZIP
No VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_sup_modulator_request_gate import (
    checked_archive,
    cluster_fields,
    field,
    peers,
    require,
    unique,
    wire,
)


def ranges(selector):
    return [
        (case.findtext("start"), case.findtext("diagramIdx"))
        for case in selector.findall("SelectRangeArray32/*")
    ]


def validate(path: Path) -> list[str]:
    root, main = checked_archive(path)
    event = unique(root, "eventStruct", "5909")
    frames = event.find("diagramList")
    require(frames is not None and len(frames) == 34, "root event layout changed")
    page_event = frames[14]
    require(page_event.get("uid") == "38030", "Page Fluides event 14 changed")

    page_names = cluster_fields(main, "Page Fluides")
    dps_names = cluster_fields(main, "DPS")
    require(len(page_names) == 23 and len(dps_names) == 29,
            "Page Fluides or DPS schema changed")
    require(page_names[9].startswith("Marche r")
            and page_names[8].startswith("Arr")
            and [page_names[i] for i in (7, 6, 20, 19)] ==
            ["< Canon", "> Canon", "< Section", "> Section"],
            "Page Fluides button labels changed")
    require(dps_names[0] == "Marche refroidissement X"
            and dps_names[1].startswith("Arret refroidissement"),
            "DPS cooling labels changed")

    dps_ref = unique(root, "gRef", "38095")
    require(dps_ref in page_event.iter()
            and dps_ref.findtext("termList/*/dco/paramIdx") == "176",
            "local DPS gate source changed")
    for uid, prim_id in (("38487", "1169"), ("38498", "1910"),
                         ("27087", "1910"), ("9710", "1062"),
                         ("10152", "1815")):
        primitive = unique(root, "prim", uid)
        require(primitive in page_event.iter()
                and primitive.findtext("primResID") == prim_id,
                f"gate primitive {uid} changed")
    top = peers(page_event)
    for source, target in (
        ("38110", "38495"),  # local DPS -> Cluster To Array
        ("38492", "38504"),  # Boolean array -> Or Array Elements
        ("38500", "37170"),  # any DPS -> outer Or
        ("38074", "40647"),  # event NewVal -> temperature field mux
        ("42005", "39290"),  # lower Canon -> Build Array
        ("41995", "39752"),  # raise Canon -> Build Array
        ("40656", "39757"),  # lower Section -> Build Array
        ("40665", "39760"),  # raise Section -> Build Array
        ("39286", "35811"),  # four buttons -> Or Array Elements
        ("35808", "37173"),  # any temperature button -> outer Or
        ("35808", "38633"),  # same flag -> inner selector tunnel
        ("37167", "38119"),  # any DPS or temperature -> outer selector
    ):
        wire(top, source, target)

    outer = unique(root, "select", "38117")
    require(outer in page_event.iter()
            and ranges(outer) == [("0", "0"), ("1", "1")],
            "outer request selector changed")
    idle_frame, busy_or_temperature_frame = outer.find("diagramList")
    require(idle_frame.get("uid") == "38154"
            and busy_or_temperature_frame.get("uid") == "38451",
            "outer branch frames changed")
    cooling_source = unique(root, "nMux", "38181")
    cooling_target = unique(root, "nMux", "38212")
    cooling_base = unique(root, "gRef", "38203")
    cooling_writer = unique(root, "sharedVariableDynamicWrite", "38229")
    require(all(node in idle_frame.iter() for node in
                (cooling_source, cooling_target, cooling_base, cooling_writer)),
            "cooling DPS writer moved out of idle branch")
    require(cooling_base.findtext("termList/*/dco/paramIdx") == "176",
            "cooling DPS base local changed")
    require(field(cooling_source, "38187") == 16
            and field(cooling_source, "38191") == 15
            and field(cooling_target, "38222") == 1,
            "source or target field positions changed")
    require(unique(root, "nmxDCO", "38220") in cooling_target.iter(),
            "DPS field 0 target changed")
    idle = peers(idle_frame)
    for source, target in (
        ("38127", "38184"),  # NewVal -> two cooling buttons
        ("38187", "38218"),  # Marche regulation -> DPS 0
        ("38191", "38222"),  # Arret regulation -> DPS 1
        ("38209", "38214"),  # local DPS base -> bundle
        ("38214", "38246"),  # DPS bundle -> PSP write data
        ("38160", "38234"),  # literal PSP URI -> writer
    ):
        wire(idle, source, target)
    uri = idle_frame.find(".//*[@uid='38160']/dco/ConstValue")
    require(uri is not None and uri.text is not None
            and bytes.fromhex(uri.text)[4:].decode("ascii") ==
            "ni.var.psp://localhost/SUPERVISION/DPS",
            "cooling writer PSP URI changed")
    require(len([node for node in idle_frame.iter()
                 if node.get("class") == "sharedVariableDynamicWrite"]) == 1,
            "idle branch shared-variable writer count changed")

    temperature_gate = unique(root, "select", "39025")
    require(temperature_gate in busy_or_temperature_frame.iter()
            and ranges(temperature_gate) == [("0", "0"), ("1", "1")],
            "temperature selector changed")
    wire(peers(busy_or_temperature_frame), "38630", "43155")
    no_temperature, temperature_frame = temperature_gate.find("diagramList")
    require(no_temperature.get("uid") == "43139"
            and temperature_frame.get("uid") == "43145",
            "temperature branch frames changed")
    require(not any(node.get("class") == "sharedVariableDynamicWrite"
                    for node in no_temperature.iter()),
            "busy/no-temperature branch now publishes a shared variable")
    temperature_action = unique(root, "select", "19503")
    require(temperature_action in temperature_frame.iter()
            and ranges(temperature_action) ==
            [("0", "0"), ("1", "1"), ("2", "2"), ("4", "3"), ("8", "4")],
            "temperature action cases changed")
    require([frame.get("uid") for frame in temperature_action.find("diagramList")] ==
            ["41905", "41911", "38348", "39993", "27926"],
            "temperature action frame UIDs changed")
    require([writer.get("uid") for writer in temperature_action.iter()
             if writer.get("class") == "sharedVariableDynamicWrite"] ==
            ["36455", "42992", "44982", "48837"],
            "temperature shared-variable writes changed")
    steps = (
        # case frame, arithmetic UID/ID, literal 0.1, source mux/field,
        # arithmetic terminals (step, current, result), C8 bundle/field,
        # Page Fluides bundle/field, writer/URI literal/input.
        (1, "39304", "1051", "43510", "10154", "39243", "39818",
         "39821", "39815", "38656", "41084", 1, "13496", "16553",
         "36455", "36087", "36458"),
        (2, "13520", "1050", "43081", "43009", "43014", "39967",
         "39970", "39964", "43054", "43060", 1, "43043", "43050",
         "42992", "43093", "42994"),
        (3, "10570", "1051", "45195", "45031", "45048", "46362",
         "46373", "46355", "45113", "45129", 2, "45095", "45104",
         "44982", "45220", "44984"),
        (4, "19403", "1050", "48925", "48854", "48859", "49363",
         "49366", "29253", "48887", "48893", 2, "48877", "48883",
         "48837", "48937", "48839"),
    )
    temperature_frames = temperature_action.find("diagramList")
    for (case_index, arithmetic_uid, arithmetic_id, step_literal,
         source_mux_uid, source_term, step_input, current_input,
         result_term, c8_mux_uid, c8_term, c8_index, page_mux_uid,
         page_term, writer_uid, uri_uid, writer_uri_term) in steps:
        action_frame = temperature_frames[case_index]
        arithmetic = unique(root, "prim", arithmetic_uid)
        require(arithmetic in action_frame.iter()
                and arithmetic.findtext("primResID") == arithmetic_id,
                f"temperature case {case_index} arithmetic changed")
        source = unique(root, "nMux", source_mux_uid)
        c8 = unique(root, "nMux", c8_mux_uid)
        page = unique(root, "nMux", page_mux_uid)
        writer = unique(root, "sharedVariableDynamicWrite", writer_uid)
        require(all(node in action_frame.iter() for node in
                    (source, c8, page, writer)),
                f"temperature case {case_index} nodes moved")
        require(field(c8, c8_term) == c8_index,
                f"temperature case {case_index} C8 field changed")
        step = action_frame.find(f".//*[@uid='{step_literal}']/dco/ConstValue")
        require(step is not None and step.text == "3FB999999999999A",
                f"temperature case {case_index} step changed from 0.1")
        action_signals = peers(action_frame)
        for left, right in (
            (step_literal, step_input), (source_term, current_input),
            (result_term, c8_term), (result_term, page_term),
            (uri_uid, writer_uri_term),
        ):
            wire(action_signals, left, right)
        uri = action_frame.find(f".//*[@uid='{uri_uid}']/dco/ConstValue")
        require(uri is not None and uri.text is not None
                and bytes.fromhex(uri.text)[4:].decode("ascii") ==
                "ni.var.psp://localhost/SUPERVISION/C8NI6703",
                f"temperature case {case_index} C8 PSP URI changed")
        primitive_ids = {node.findtext("primResID") for node in action_frame.iter()
                         if node.get("class") == "prim"}
        require(primitive_ids == {"1302", arithmetic_id},
                f"temperature case {case_index} primitive set changed")
    return [
        "Page Fluides event 14: no pending DPS and no temperature button -> "
        "Page Fluides[9,8] to DPS[0,1] PSP write",
        "Temperature button active -> separate 1/2/4/8 adjustment selector; "
        "pending DPS without temperature button -> no DPS write",
        "One-hot temperature cases -> C8[1,1,2,2] +/-0.1 from the "
        "corresponding Page Fluides setpoint, with no clamp in those cases",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Page Fluides event 14 cooling-request gate and field wires")


if __name__ == "__main__":
    main()
