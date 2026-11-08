"""Contrast saved ACQ event-6 Modulator stop with outer controlled stop.

Usage: python tools/validate_acq_two_stop_paths.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


EVENT6_PULSES = (
    (1, "55151", 8, "55203", False),
    (2, "31217", 8, "31262", True),
    (4, "33302", 17, "33347", False),
    (5, "35326", 17, "35353", True),
    (7, "36891", 6, "36918", False),
    (8, "23604", 6, "23636", True),
    (10, "25792", 4, "25850", False),
    (11, "29506", 4, "29587", True),
    (13, "30043", 1, "30124", False),
    (14, "32882", 1, "32909", True),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    gate = unique(root, "select", "26469")
    require([(entry.findtext("start"), entry.findtext("diagramIdx"))
             for entry in gate.findall("SelectRangeArray32/*")]
            == [("0", "0"), ("1", "1")]
            and len(gate.find("diagramList")[0].find("zPlaneList")) == 0,
            "event-6 NewVal gate changed")
    true_arm = gate.find("diagramList")[1]
    sequence = unique(root, "sequence", "26556")
    require(sequence in true_arm.iter(), "event-6 sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 17,
            "event-6 frame count changed")
    focal = unique(root, "iUse", "53841")
    clear = unique(root, "iUse", "49738")
    first = unique(root, "flatSequence", "53825")
    require(first in frames[0].iter()
            and focal in first.find("sequenceList")[0].iter()
            and clear in first.find("sequenceList")[0].iter()
            and focal.findtext("label/textRec/text") == '"1_Focales OFF.vi"'
            and clear.findtext("label/textRec/text") == '"Clear Errors.vi"',
            "event-6 Focales OFF or error clearing changed")
    direct("53844", "49778")
    for frame_index, mux_uid, field_index, literal_uid, state in EVENT6_PULSES:
        frame = frames[frame_index]
        mux = unique(root, "nMux", mux_uid)
        require(mux in frame.iter()
                and len(mux.findall("termList/*")) == 3
                and field(mux, mux.findall("termList/*")[2].get("uid")) == field_index,
                f"event-6 C4 pulse frame {frame_index} changed")
        local_refs = [node for node in frame.iter() if node.get("class") == "gRef"]
        require(len(local_refs) == 2
                and all(node.findtext("termList/*/dco/paramIdx") == "15"
                        for node in local_refs),
                f"event-6 pulse bank in frame {frame_index} changed")
        literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(literal is not None and literal.text == ("01" if state else "0000"),
                f"event-6 pulse value in frame {frame_index} changed")
        direct(literal_uid, mux.findall("termList/*")[2].get("uid"))
    for frame_index, literal_uid, expected in (
        (3, "27289", "000003E8"),
        (6, "35218", "000003E8"),
        (9, "23552", "000003E8"),
        (12, "24938", "000007D0"),
    ):
        literal = frames[frame_index].find(
            f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(literal is not None and literal.text == expected,
                f"event-6 interstage wait in frame {frame_index} changed")
    require(unique(root, "sharedVariableDynamicWrite", "37694") in frames[16].iter(),
            "event-6 terminal DPS PSP write moved")
    controlled = unique(root, "sequence", "51954")
    require(not any(node.get("class") == "sharedVariableDynamicWrite"
                    for node in controlled.iter()),
            "controlled-stop sequence gained direct PSP writer")
    require(not any(node.get("class") == "iUse"
                    and node.findtext("label/textRec/text") == '"1_Focales OFF.vi"'
                    for node in controlled.iter()),
            "controlled-stop sequence gained Focales OFF call")
    eps_writers = [node for node in controlled.iter()
                   if node.get("class") == "gRef"
                   and node.findtext("termList/*/dco/paramIdx") == "44"
                   and node.find("termList/*").findtext("objFlags") == "36864"]
    require({node.get("uid") for node in eps_writers} == {"54646", "58837"},
            "controlled-stop EPS writer set changed")
    return [
        "Normal ACQ event 6 has Focales OFF.vi before matching C4 stop-pulse "
        "fields 8,17,6,4,1, and a terminal DPS PSP write",
        "Outer seven-phase controlled stop has no Focales OFF.vi or direct "
        "PSP writer; its only EPS local writers are phase-5 cooling status",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ two stop paths remain distinct")


if __name__ == "__main__":
    main()
