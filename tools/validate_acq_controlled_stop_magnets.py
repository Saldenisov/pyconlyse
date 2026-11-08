"""Validate saved ACQ controlled-stop phase-3 analog and DIO assignments.

Usage: python tools/validate_acq_controlled_stop_magnets.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


C6_ZERO_FIELDS = (0, 1, 2, 3, 4, 5, 6, 7, 9)
C7_ZERO_FIELDS = (0, 1, 3, 4, 5, 6, 7, 8, 9)
C3_FALSE_FIELDS = (9, 11, 15, 17, 21, 23, 25, 27, 29,
                   31, 32, 33, 34, 35, 36, 37, 38, 39)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    phase = unique(root, "sequence", "51954").find("diagramList")[3]
    require(phase.get("uid") == "129793", "magnet-stop phase moved")
    sequence = unique(root, "sequence", "128434")
    require(sequence in phase.iter(), "magnet-stop nested sequence moved")
    frames = sequence.find("diagramList")
    require([frame.get("uid") for frame in frames]
            == ["128452", "128743", "128773", "129221"],
            "magnet-stop frame order changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def together(*term_uids: str) -> None:
        require(any(set(term_uids) <= group for group in signals),
                f"direct signal containing {term_uids} changed")

    zero = frames[0].find(".//*[@uid='128468']/dco/ConstValue")
    require(zero is not None and zero.text == "000000000000000000",
            "magnet zero literal changed")
    for (source_uid, mux_uid, writer_uid, param_index, fields,
         base_term, output_term, writer_term) in (
            ("128522", "128488", "128480", "9", C6_ZERO_FIELDS,
             "128525", "128490", "128483"),
            ("128578", "128544", "128536", "10", C7_ZERO_FIELDS,
             "128581", "128546", "128539"),
    ):
        source = unique(root, "gRef", source_uid)
        mux = unique(root, "nMux", mux_uid)
        writer = unique(root, "gRef", writer_uid)
        require(all(node in frames[0].iter() for node in (source, mux, writer))
                and source.findtext("termList/*/dco/paramIdx") == param_index
                and writer.findtext("termList/*/dco/paramIdx") == param_index,
                f"magnet command bank {param_index} changed")
        # Field zero has an omitted <i> in this LabVIEW export.
        target_terms = mux.findall("termList/*")[2:]
        require(tuple(field(mux, term.get("uid")) for term in target_terms)
                == fields, f"magnet bank {param_index} field set changed")
        together("128468", *(term.get("uid") for term in target_terms))
        together(base_term, source.find("termList/*").get("uid"))
        together(output_term, writer_term)
    false = frames[2].find(".//*[@uid='128779']/dco/ConstValue")
    require(false is not None and false.text == "0000",
            "magnet-stop C3 False literal changed")
    c3_source = unique(root, "gRef", "128858")
    c3_mux = unique(root, "nMux", "128797")
    c3_writer = unique(root, "gRef", "128789")
    require(all(node in frames[2].iter() for node in
                (c3_source, c3_mux, c3_writer))
            and c3_source.findtext("termList/*/dco/paramIdx") == "17"
            and c3_writer.findtext("termList/*/dco/paramIdx") == "17",
            "magnet-stop C3 command bank changed")
    target_terms = [term for term in c3_mux.findall("termList/*")
                    if term.findtext("dco/i") is not None]
    require(tuple(field(c3_mux, term.get("uid")) for term in target_terms)
            == C3_FALSE_FIELDS, "magnet-stop C3 field set changed")
    together("128779", *(term.get("uid") for term in target_terms))
    together("128861", "128802")
    together("128799", "128792")
    for frame_index, wait_uid, literal_uid in (
        (1, "128761", "128749"), (3, "129239", "129227")
    ):
        wait = unique(root, "prim", wait_uid)
        literal = frames[frame_index].find(
            f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(wait in frames[frame_index].iter()
                and wait.findtext("primResID") == "1302"
                and literal is not None and literal.text == "000003E8",
                f"magnet-stop frame {frame_index} wait changed")
        together(literal_uid, wait.findall("termList/*")[-1].get("uid"))
    return [
        "Phase 3 assigns zero to C6 fields 0..7,9 and C7 fields "
        "0,1,3..9; then waits 1000 ms",
        "It assigns False to 18 C3 command fields 9,11,15,17,21,23,25,"
        "27,29,31..39; then waits 1000 ms",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop magnet-command phase")


if __name__ == "__main__":
    main()
