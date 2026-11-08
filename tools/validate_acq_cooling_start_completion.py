"""Check saved ACQ cooling-start event 3 output/status wires, offline.

Usage: python tools/validate_acq_cooling_start_completion.py SOURCE_EXPORT_ZIP
This does not run a VI, publish PSP, or access an NI card.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_modulator_start_event_guards import checked_root, require, unique


# Ordered sequence frame, selected bank, bundle, field terminal, field index,
# literal terminal, literal Boolean, local-bundle base/writer reference UIDs.
COMMAND_FRAMES = (
    (0, "17", "21228", "21239", 0, "22213", "01", "21489", "21016"),
    (1, "17", "23018", "23024", 0, "23054", "0000", "23028", "23006"),
    (3, "17", "25003", "25009", 3, "25021", "01", "25013", "24995"),
    (4, "17", "31643", "31649", 3, "31669", "0000", "31653", "31635"),
    (5, "15", "23543", "23549", 0, "23570", "01", "23554", "23535"),
    (6, "15", "26151", "26157", 0, "26209", "0000", "26163", "26132"),
    (8, "15", "28120", "28138", 2, "28174", "01", "28148", "28094"),
    (9, "15", "21883", "21911", 2, "31421", "0000", "24103", "21840"),
)
EPS_TERMINALS = (
    (0, "26406", "20683", "0000"),
    (1, "21833", "22311", "0000"),
    (2, "19235", "20495", "01"),
    (5, "9197", "20182", "0000"),
    (8, "31705", "23037", "01"),
)


def peers(frame):
    return [
        {term.get("uid", "") for term in signal.findall("termList/*")}
        for signal in frame.findall("signalList/*")
    ]


def wire(signals, source, target):
    require(any({source, target} <= group for group in signals),
            f"direct wire {source}->{target} absent")


def literal(frame, terminal_uid, expected):
    terms = frame.findall(f".//*[@uid='{terminal_uid}']/dco/ConstValue")
    require(len(terms) == 1 and terms[0].text == expected,
            f"literal terminal {terminal_uid} changed")


def field(mux, terminal_uid):
    terms = [term for term in mux.findall("termList/*")
             if term.get("uid") == terminal_uid]
    require(len(terms) == 1, f"bundle {mux.get('uid')} terminal changed")
    return int(terms[0].findtext("dco/i") or "0")


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    runtime = unique(root, "eventStruct", "43")
    event_frames = runtime.find("diagramList")
    require(event_frames is not None and len(event_frames) == 26,
            "ACQ runtime event frame count changed")
    event = event_frames[3]
    require(event.get("uid") == "19818", "cooling-start event 3 moved")
    refs = {ref.findtext("termList/*/dco/paramIdx")
            for ref in event.iter() if ref.get("class") == "gRef"}
    require(refs == {"15", "17", "35", "36", "44"},
            f"event 3 local-reference set changed: {refs}")
    selector = unique(root, "select", "19197")
    require(selector in event.iter()
            and [(case.findtext("start"), case.findtext("diagramIdx"))
                 for case in selector.findall("SelectRangeArray32/*")] ==
            [("0", "0"), ("1", "1")], "NewVal case selector changed")
    false_frame, true_frame = selector.find("diagramList")
    require(false_frame.get("uid") == "22648"
            and true_frame.get("uid") == "22654"
            and len(false_frame.find("zPlaneList")) == 0,
            "event 3 False arm no longer empty")
    event_data = unique(root, "eventDataNode", "22353")
    require(event_data in event.iter(), "event 3 NewVal node moved")
    new_val = [term for term in event_data.findall("termList/*")
               if term.findtext("dco/i") == "6"]
    require(len(new_val) == 1, "event 3 NewVal terminal changed")
    wire(peers(event), new_val[0].get("uid"), "22664")

    sequence = unique(root, "sequence", "18783")
    require(sequence in true_frame.iter(), "ordered start sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 12,
            "ordered cooling-start frame count changed")
    for (index, bank_param, mux_uid, field_term, target_field,
         literal_uid, value, base_uid, result_uid) in COMMAND_FRAMES:
        frame = frames[index]
        mux = unique(root, "nMux", mux_uid)
        base = unique(root, "gRef", base_uid)
        result = unique(root, "gRef", result_uid)
        require(all(node in frame.iter() for node in (mux, base, result)),
                f"frame {index} output nodes moved")
        require(base.findtext("termList/*/dco/paramIdx") == bank_param
                and result.findtext("termList/*/dco/paramIdx") == bank_param,
                f"frame {index} output bank changed")
        require(field(mux, field_term) == target_field,
                f"frame {index} output field changed")
        literal(frame, literal_uid, value)
        wire(peers(frame), literal_uid, field_term)
    for index in (2, 7, 11):
        require(any(node.get("class") == "prim"
                    and node.findtext("primResID") == "1302"
                    for node in frames[index].iter()),
                f"frame {index} wait moved")
    for index, literal_uid, value in (
        (2, "29129", "00000320"),  # 800 ms
        (7, "21690", "000001F4"),  # 500 ms
        (11, "25146", "00001388"),  # 5000 ms
    ):
        literal(frames[index], literal_uid, value)
    literal(event, "18713", "000003E8")  # shared 1000-ms pulse hold
    wire(peers(event), "18713", "19245")
    wire(peers(true_frame), "19238", "19196")
    for index, wait_uid, tunnel_term, wait_input in (
        (0, "11467", "19035", "18849"),
        (3, "22684", "24992", "22700"),
        (5, "23560", "23532", "23565"),
        (8, "13418", "28085", "21811"),
    ):
        wait = unique(root, "prim", wait_uid)
        require(wait in frames[index].iter()
                and wait.findtext("primResID") == "1302",
                f"frame {index} shared-duration wait moved")
        wire(peers(frames[index]), tunnel_term, wait_input)

    status_frame = frames[10]
    eps_mux = unique(root, "nMux", "18625")
    dps_mux = unique(root, "nMux", "23709")
    require(eps_mux in status_frame.iter() and dps_mux in status_frame.iter(),
            "completion status bundles moved")
    status_signals = peers(status_frame)
    for target_index, field_term, literal_uid, value in EPS_TERMINALS:
        require(field(eps_mux, field_term) == target_index,
                f"EPS field {target_index} moved")
        literal(status_frame, literal_uid, value)
        wire(status_signals, literal_uid, field_term)
    require(field(dps_mux, "23719") == 0, "DPS cooling request field moved")
    literal(status_frame, "19692", "0000")
    wire(status_signals, "19692", "23719")
    for uid, param in (("18624", "44"), ("18626", "44"),
                       ("23085", "36"), ("14535", "36")):
        ref = unique(root, "gRef", uid)
        require(ref in status_frame.iter()
                and ref.findtext("termList/*/dco/paramIdx") == param,
                f"completion local reference {uid} changed")

    publish_frame = frames[11]
    writer = unique(root, "sharedVariableDynamicWrite", "5681")
    require(writer in publish_frame.iter(), "DPS completion writer moved")
    uri = publish_frame.find(".//*[@uid='2549']/dco/ConstValue")
    require(uri is not None and uri.text is not None
            and bytes.fromhex(uri.text)[4:].decode("ascii") ==
            "ni.var.psp://10.20.30.2/SUPERVISION/DPS",
            "DPS completion PSP URI changed")
    wire(peers(publish_frame), "2549", "5997")
    return [
        "ACQ event 3: 12 ordered frames, C3_OUT[0,3] and C4_OUT[0,2] "
        "True->False command pairs",
        "Completion: EPS[0,1,2,5,8] and DPS[0] local assignments; "
        "DPS PSP publish in final frame",
        "No direct C3_IN/C4_IN local reference in event 3",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ cooling-start event 3 ordered outputs and completion flags")


if __name__ == "__main__":
    main()
