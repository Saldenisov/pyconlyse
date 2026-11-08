"""Validate saved ACQ controlled-stop phase-2 HT supply command and markers.

Usage: python tools/validate_acq_controlled_stop_ht_supply.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


# Outer controlled-stop phase, numeric local writer, literal terminal,
# raw DBL literal. The 6..0 meaning is inferred, not labelled by this trace.
PHASE_MARKERS = (
    (0, "206173", "51420", "4018000000000000"),
    (1, "52774", "53457", "4014000000000000"),
    (2, "55331", "55348", "4010000000000000"),
    (3, "57519", "57565", "4008000000000000"),
    (4, "59077", "59094", "4000000000000000"),
    (5, "52743", "52760", "3FF0000000000000"),
    (6, "63433", "63466", "000000000000000000"),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    phases = unique(root, "sequence", "51954").find("diagramList")
    require(phases is not None and len(phases) == 7,
            "controlled-stop phase count changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for phase_index, writer_uid, literal_uid, value in PHASE_MARKERS:
        writer = unique(root, "gRef", writer_uid)
        require(writer in phases[phase_index].iter()
                and writer.findtext("termList/*/dco/paramIdx") == "50",
                f"controlled-stop phase {phase_index} marker local changed")
        constant = phases[phase_index].find(
            f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(constant is not None and constant.text == value,
                f"controlled-stop phase {phase_index} marker value changed")
        direct(literal_uid, writer.find("termList/*").get("uid"))

    ht = unique(root, "sequence", "49098")
    require(ht in phases[2].iter(), "HT supply stop moved from phase 2")
    frames = ht.find("diagramList")
    require([frame.get("uid") for frame in frames]
            == ["49114", "49284", "49853"],
            "HT supply stop frame order changed")
    for (frame_index, mux_uid, field_uid, literal_uid, literal_value,
         base_uid, writer_uid) in (
            (0, "49153", "49159", "49120", "0000", "49172", "49140"),
            (1, "49339", "49349", "49300", "01", "49355", "49322"),
        ):
        frame = frames[frame_index]
        mux = unique(root, "nMux", mux_uid)
        base = unique(root, "gRef", base_uid)
        writer = unique(root, "gRef", writer_uid)
        require(all(node in frame.iter() for node in (mux, base, writer))
                and base.findtext("termList/*/dco/paramIdx") == "15"
                and writer.findtext("termList/*/dco/paramIdx") == "15"
                and field(mux, field_uid) == 19,
                f"HT stop logical C4 field in frame {frame_index} changed")
        literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(literal is not None and literal.text == literal_value,
                f"HT stop Boolean literal in frame {frame_index} changed")
        direct(literal_uid, field_uid)
    for frame_index, wait_uid, source_uid, expected in (
        (0, "50402", "51761", "00000096"),  # 150 ms in False-write frame
        (2, "49871", "49859", "000003E8"),  # 1000 ms after restore frame
    ):
        frame = frames[frame_index]
        wait = unique(root, "prim", wait_uid)
        require(wait in frame.iter() and wait.findtext("primResID") == "1302",
                f"HT stop wait frame {frame_index} changed")
        value = frame.find(f".//*[@uid='{source_uid}']/dco/ConstValue")
        require(value is not None and value.text == expected,
                f"HT stop wait literal in frame {frame_index} changed")
        input_terms = {term.get("uid") for term in wait.findall("termList/*")}
        require(any(source_uid in group and bool(input_terms & group)
                    for group in signals),
                f"HT stop wait input wire in frame {frame_index} changed")
    require(not any(node.get("class") == "sharedVariableDynamicWrite"
                    for node in ht.iter()),
            "HT supply stop now has direct PSP writer")
    return [
        "Controlled-stop phase markers write local param 50 as "
        "6,5,4,3,2,1,0 across phases 0..6",
        "Phase 2 orders C4_OUT_DIO96[19] False (same frame as 150-ms wait), "
        "then True, then a 1000-ms wait; no direct PSP writer in these frames",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop HT supply and seven phase markers")


if __name__ == "__main__":
    main()
