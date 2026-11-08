"""Validate saved ACQ controlled-stop final frame and loop-exit wires.

Usage: python tools/validate_acq_controlled_stop_completion.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, require, unique


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    phase = unique(root, "sequence", "51954").find("diagramList")[6]
    require(phase.get("uid") == "64826", "final stop phase moved")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for writer_uid, index, literal_uid, value in (
        ("18163", "46", "42334", "01"),  # stop urgence True
        ("43536", "47", "46100", "0000"),  # Arrêt général False
        ("63433", "50", "63466", "000000000000000000"),
    ):
        writer = unique(root, "gRef", writer_uid)
        literal = phase.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(writer in phase.iter()
                and writer.findtext("termList/*/dco/paramIdx") == index
                and literal is not None and literal.text == value,
                f"final stop local {index} changed")
        direct(literal_uid, writer.find("termList/*").get("uid"))
    wait = unique(root, "prim", "67189")
    literal = phase.find(".//*[@uid='67206']/dco/ConstValue")
    require(wait in phase.iter() and wait.findtext("primResID") == "1302"
            and literal is not None and literal.text == "000003E8",
            "final stop 1000-ms wait changed")
    direct("67206", "67198")
    require(not any("67195" in group for group in signals),
            "final wait acquired an output dependency")
    for loop_uid, reader_uid, test_uid, source_term, target_term in (
        ("41705", "43367", "41723", "43377", "41725"),
        ("42592", "115330", "42634", "115354", "42640"),
    ):
        loop = unique(root, "whileLoop", loop_uid)
        reader = unique(root, "gRef", reader_uid)
        test = unique(root, "lTst", test_uid)
        require(reader in loop.iter() and test in loop.iter()
                and reader.findtext("termList/*/dco/paramIdx") == "46"
                and test.findtext("objFlags") == "65537",
                f"controlled-stop loop {loop_uid} exit source changed")
        direct(source_term, target_term)
    # Wait and three local assignments are independent same-frame nodes;
    # there is no wire establishing wait-before-stop-flag order.
    return [
        "Phase 6 independently assigns local param 50=0, stop urgence=True, "
        "Arrêt général=False, and performs a 1000-ms Wait in one frame",
        "Both outer-frame-3 While loops exit on a param-46 stop urgence "
        "read; the wait is not wired before that flag assignment",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop final frame and loop exits")


if __name__ == "__main__":
    main()
