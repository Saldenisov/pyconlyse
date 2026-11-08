"""Check saved ACQ cooling-stop event 4 output/status wires, offline.

Usage: python tools/validate_acq_cooling_stop_completion.py SOURCE_EXPORT_ZIP
This does not run a VI, publish PSP, or access an NI card.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import (
    checked_root,
    field,
    literal,
    peers,
    require,
    unique,
    wire,
)


COMMAND_FRAMES = (
    (0, "11019", "13606", 1, "7970", "0000", "13611", "10838"),
    (1, "20420", "20429", 1, "18873", "01", "20437", "20410"),
    (3, "21826", "21954", 4, "21733", "0000", "21967", "21773"),
    (4, "22115", "22131", 4, "22071", "01", "22138", "22098"),
)
EPS_TERMINALS = (
    (1, "22975", "22921", "0000"),
    (2, "22968", "22900", "0000"),
    (3, "22965", "22885", "0000"),
    (5, "22972", "22910", "01"),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    runtime = unique(root, "eventStruct", "43")
    events = runtime.find("diagramList")
    require(events is not None and len(events) == 26,
            "ACQ runtime event frame count changed")
    event = events[4]
    require(event.get("uid") == "17899", "cooling-stop event 4 moved")
    refs = {ref.findtext("termList/*/dco/paramIdx")
            for ref in event.iter() if ref.get("class") == "gRef"}
    require(refs == {"17", "35", "36", "44"},
            f"event 4 local-reference set changed: {refs}")
    selector = unique(root, "select", "17947")
    require(selector in event.iter()
            and [(case.findtext("start"), case.findtext("diagramIdx"))
                 for case in selector.findall("SelectRangeArray32/*")] ==
            [("0", "0"), ("1", "1")], "stop NewVal case selector changed")
    false_frame, true_frame = selector.find("diagramList")
    require(false_frame.get("uid") == "17964"
            and true_frame.get("uid") == "17970"
            and len(false_frame.find("zPlaneList")) == 0,
            "event 4 False arm no longer empty")
    new_val = unique(root, "eventDataNode", "17919")
    require(new_val in event.iter(), "event 4 NewVal node moved")
    wire(peers(event), "17939", "17950")
    sequence = unique(root, "sequence", "7929")
    require(sequence in true_frame.iter(), "ordered stop sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 7,
            "ordered cooling-stop frame count changed")
    for (index, mux_uid, field_term, target_field, literal_uid,
         value, base_uid, result_uid) in COMMAND_FRAMES:
        frame = frames[index]
        mux = unique(root, "nMux", mux_uid)
        base = unique(root, "gRef", base_uid)
        result = unique(root, "gRef", result_uid)
        require(all(node in frame.iter() for node in (mux, base, result)),
                f"stop frame {index} output nodes moved")
        require(base.findtext("termList/*/dco/paramIdx") == "17"
                and result.findtext("termList/*/dco/paramIdx") == "17",
                f"stop frame {index} output bank changed")
        require(field(mux, field_term) == target_field,
                f"stop frame {index} output field changed")
        literal(frame, literal_uid, value)
        wire(peers(frame), literal_uid, field_term)
    literal(event, "18551", "00000096")  # shared 150-ms wait source
    wire(peers(event), "18551", "17956")
    wire(peers(true_frame), "17961", "7941")
    for index, wait_uid, tunnel_term, wait_input in (
        (0, "16362", "7949", "16413"),
        (3, "21990", "7952", "22010"),
        (4, "22147", "7953", "22162"),
    ):
        wait = unique(root, "prim", wait_uid)
        require(wait in frames[index].iter()
                and wait.findtext("primResID") == "1302",
                f"stop frame {index} 150-ms wait moved")
        wire(peers(frames[index]), tunnel_term, wait_input)
    literal(frames[2], "21486", "00000190")  # 400 ms
    literal(frames[6], "23123", "00000064")  # 100 ms

    status_frame = frames[5]
    eps_mux = unique(root, "nMux", "22959")
    dps_mux = unique(root, "nMux", "23043")
    require(eps_mux in status_frame.iter() and dps_mux in status_frame.iter(),
            "stop status bundles moved")
    status_signals = peers(status_frame)
    for target_index, field_term, literal_uid, value in EPS_TERMINALS:
        require(field(eps_mux, field_term) == target_index,
                f"stop EPS field {target_index} moved")
        literal(status_frame, literal_uid, value)
        wire(status_signals, literal_uid, field_term)
    require(field(dps_mux, "23052") == 1, "stop DPS field changed")
    literal(status_frame, "22931", "0000")
    wire(status_signals, "22931", "23052")
    require(not any(field(eps_mux, term.get("uid")) == 8
                    for term in eps_mux.findall("termList/*")
                    if term.findtext("dco/i") is not None),
            "event 4 now changes EPS GENERAL Mod. OK")
    for uid, param in (("22951", "44"), ("22985", "44"),
                       ("23005", "36"), ("23076", "36")):
        ref = unique(root, "gRef", uid)
        require(ref in status_frame.iter()
                and ref.findtext("termList/*/dco/paramIdx") == param,
                f"stop completion local reference {uid} changed")
    final_frame = frames[6]
    writer = unique(root, "sharedVariableDynamicWrite", "23177")
    require(writer in final_frame.iter(), "stop DPS writer moved")
    uri = final_frame.find(".//*[@uid='23135']/dco/ConstValue")
    require(uri is not None and uri.text is not None
            and bytes.fromhex(uri.text)[4:].decode("ascii") ==
            "ni.var.psp://10.20.30.2/SUPERVISION/DPS",
            "stop DPS PSP URI changed")
    wire(peers(final_frame), "23135", "23179")
    return [
        "ACQ event 4: 7 ordered frames, C3_OUT[1,4] False->True stop pairs",
        "Separate 150-ms wait in frame 4 accompanies Section stop restore",
        "Completion: EPS[1,2,3,5], DPS[1] local assignments; "
        "EPS[8] untouched in this event",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ cooling-stop event 4 outputs, wait, and completion flags")


if __name__ == "__main__":
    main()
