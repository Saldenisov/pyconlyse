"""Validate saved ACQ controlled-stop phase-5 cooling and status wires.

Usage: python tools/validate_acq_controlled_stop_cooling.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


COOLING_WRITES = (
    (0, 1, "54327", "54337", "54319", "54299", False),
    (1, 1, "54413", "54423", "54407", "54397", True),
    (3, 4, "54492", "54502", "54486", "54476", False),
    (4, 4, "54552", "54562", "54546", "54536", True),
)
STATUS_WRITES = (
    (5, "54654", "54673", "54646", "54687", "54697", "54679",
     ((3, "54596", False), (2, "54606", False),
      (5, "54616", True), (1, "54626", False)), "54636"),
    (6, "58845", "58864", "58837", "58878", "58888", "58870",
     ((3, "58935", False), (2, "58925", False),
      (5, "58915", True), (1, "58904", False)), "58894"),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    phase = unique(root, "sequence", "51954").find("diagramList")[5]
    require(phase.get("uid") == "52159", "cooling-stop phase moved")
    sequence = unique(root, "sequence", "54275")
    require(sequence in phase.iter(), "cooling-stop sequence moved")
    frames = sequence.find("diagramList")
    require([frame.get("uid") for frame in frames]
            == ["54293", "54391", "54440", "54470",
                "54530", "54590", "58827", "54731"],
            "cooling-stop frame order changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    def bank_write(frame_index: int, mux_uid: str, reader_uid: str,
                   writer_uid: str, param_index: str,
                   field_literals: tuple[tuple[int, str, bool], ...]) -> None:
        frame = frames[frame_index]
        mux = unique(root, "nMux", mux_uid)
        reader = unique(root, "gRef", reader_uid)
        writer = unique(root, "gRef", writer_uid)
        require(all(node in frame.iter() for node in (mux, reader, writer))
                and reader.findtext("termList/*/dco/paramIdx") == param_index
                and writer.findtext("termList/*/dco/paramIdx") == param_index,
                f"cooling-stop frame {frame_index} bank {param_index} changed")
        terms = mux.findall("termList/*")
        require(tuple(field(mux, term.get("uid")) for term in terms[2:])
                == tuple(index for index, _, _ in field_literals),
                f"cooling-stop frame {frame_index} field set changed")
        direct(reader.find("termList/*").get("uid"), terms[1].get("uid"))
        direct(terms[0].get("uid"), writer.find("termList/*").get("uid"))
        for (_, literal_uid, value), term in zip(field_literals, terms[2:]):
            literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
            require(literal is not None and literal.text == ("01" if value else "0000"),
                    f"cooling-stop frame {frame_index} literal changed")
            direct(literal_uid, term.get("uid"))

    for frame_index, field_index, mux_uid, reader_uid, writer_uid, literal_uid, value in COOLING_WRITES:
        bank_write(frame_index, mux_uid, reader_uid, writer_uid, "17",
                   ((field_index, literal_uid, value),))
    for (frame_index, eps_mux, eps_reader, eps_writer, dps_mux,
         dps_reader, dps_writer, eps_literals, dps_literal) in STATUS_WRITES:
        bank_write(frame_index, eps_mux, eps_reader, eps_writer, "44",
                   eps_literals)
        bank_write(frame_index, dps_mux, dps_reader, dps_writer, "36",
                   ((1, dps_literal, False),))
    for frame_index, wait_uid in ((0, "54353"), (3, "54508"), (4, "54568")):
        wait = unique(root, "prim", wait_uid)
        require(wait in frames[frame_index].iter()
                and wait.findtext("primResID") == "1302",
                f"cooling-stop frame {frame_index} unresolved wait moved")
    for frame_index, wait_uid, literal_uid, expected in (
        (2, "54458", "54446", "00000190"),
        (7, "54767", "54737", "00000064"),
    ):
        frame = frames[frame_index]
        wait = unique(root, "prim", wait_uid)
        literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        require(wait in frame.iter() and wait.findtext("primResID") == "1302"
                and literal is not None and literal.text == expected,
                f"cooling-stop frame {frame_index} explicit wait changed")
        direct(literal_uid, wait.findall("termList/*")[-1].get("uid"))
    require(not any(node.get("class") == "sharedVariableDynamicWrite"
                    for node in sequence.iter()),
            "cooling-stop sequence now has direct PSP writer")
    return [
        "Phase 5 orders C3[1] False/True, 400-ms wait, C3[4] False/True",
        "Frames 5 and 6 each set EPS[3,2,5,1] to F,F,T,F and DPS[1] "
        "to False; frame 7 waits 100 ms; no direct PSP writer",
        "Same-frame wait durations in frames 0,3,4 remain unresolved in raw XML",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop cooling and local status")


if __name__ == "__main__":
    main()
