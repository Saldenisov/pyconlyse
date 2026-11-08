"""Validate saved ACQ controlled-stop phase-4 stage output assignments.

Usage: python tools/validate_acq_controlled_stop_stage_pulses.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


# Ordered False/True frames: frame index, C4 field, nMux, reader, writer,
# literal terminal. The waits in the False frames have an unresolved sRN
# source in this export, so the validator does not assert their duration.
PULSE_WRITES = (
    (0, 8, "42462", "42480", "42452", "42430", False),
    (1, 8, "42596", "42662", "42582", "42557", True),
    (3, 17, "42823", "42843", "42796", "42772", False),
    (4, 17, "42976", "43076", "42955", "42909", True),
    (6, 6, "43223", "43234", "43217", "43204", False),
    (7, 6, "43287", "43297", "43280", "43270", True),
    (9, 4, "43379", "43389", "43368", "43351", False),
    (10, 4, "43440", "43450", "43434", "43424", True),
    (12, 1, "43544", "43560", "43538", "43528", False),
    (13, 1, "43611", "43621", "43605", "43595", True),
)
SHORT_WAIT_FRAMES = ((0, "42513"), (3, "42853"), (6, "43240"),
                     (9, "43395"), (12, "43566"))
INTERSTAGE_WAITS = ((2, "42744", "42728", "000003E8"),
                    (5, "43168", "43147", "000003E8"),
                    (8, "43333", "43321", "000003E8"),
                    (11, "43486", "43474", "000007D0"),
                    (14, "44060", "43945", "000003E8"))


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    phase = unique(root, "sequence", "51954").find("diagramList")[4]
    require(phase.get("uid") == "1722", "stage-stop phase moved")
    sequence = unique(root, "sequence", "42397")
    require(sequence in phase.iter(), "stage-stop sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 15,
            "stage-stop frame count changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for frame_index, field_index, mux_uid, reader_uid, writer_uid, literal_uid, state in PULSE_WRITES:
        frame = frames[frame_index]
        mux = unique(root, "nMux", mux_uid)
        reader = unique(root, "gRef", reader_uid)
        writer = unique(root, "gRef", writer_uid)
        require(all(node in frame.iter() for node in (mux, reader, writer))
                and reader.findtext("termList/*/dco/paramIdx") == "15"
                and writer.findtext("termList/*/dco/paramIdx") == "15",
                f"stage-stop frame {frame_index} C4 bank changed")
        terms = mux.findall("termList/*")
        require(len(terms) == 3 and field(mux, terms[2].get("uid")) == field_index,
                f"stage-stop frame {frame_index} C4 field changed")
        literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(literal is not None and literal.text == ("01" if state else "0000"),
                f"stage-stop frame {frame_index} Boolean value changed")
        direct(literal_uid, terms[2].get("uid"))
        direct(reader.find("termList/*").get("uid"), terms[1].get("uid"))
        direct(terms[0].get("uid"), writer.find("termList/*").get("uid"))
    for frame_index, wait_uid in SHORT_WAIT_FRAMES:
        wait = unique(root, "prim", wait_uid)
        require(wait in frames[frame_index].iter()
                and wait.findtext("primResID") == "1302",
                f"stage-stop short wait in frame {frame_index} changed")
    for frame_index, wait_uid, literal_uid, expected in INTERSTAGE_WAITS:
        frame = frames[frame_index]
        wait = unique(root, "prim", wait_uid)
        literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(wait in frame.iter() and wait.findtext("primResID") == "1302"
                and literal is not None and literal.text == expected,
                f"stage-stop interstage wait in frame {frame_index} changed")
        direct(literal_uid, wait.findall("termList/*")[-1].get("uid"))
    return [
        "Phase 4 orders C4 field pulses 8,17,6,4,1 as False then True",
        "After each pair, explicit waits are 1000,1000,1000,2000,1000 ms; "
        "the five same-frame wait durations are not proven by raw XML",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop stage output pulses")


if __name__ == "__main__":
    main()
