"""Validate the saved ACQ Timeout raw cooling-flow Case selector.

Usage: python tools/validate_acq_cooling_flow_guard.py SOURCE_EXPORT_ZIP
Static, read-only verification; no VI, PSP, or hardware operation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


WIRES = (
    ("290", "70"),      # 20-ms Event Structure timeout input
    ("8395", "42283"),    # C3_IN local to unbundle
    ("10214", "51370"),  # C4_IN local to unbundle
    ("42286", "47325"),  # C3[0] inverted compound OR input
    ("42289", "47330"),  # C3[6] inverted compound OR input
    ("51373", "40066"),  # C4[19] OR input
    ("53472", "40063"),  # C4[38] OR input
    ("47316", "52237"),  # NOT C3[0] OR NOT C3[6] -> AND
    ("40060", "52240"),  # C4[19] OR C4[38] -> AND
    ("52234", "44205"),  # AND output -> flow-trip Case selector
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    runtime = unique(root, "eventStruct", "43")
    require(runtime.find("termList/*[@uid='70']") is not None
            and unique(root, "sRN", "114").findtext(
                "termList/*[@uid='290']/dco/ConstValue") == "00000014",
            "20-ms event timeout input changed")
    timeout = runtime.find("diagramList")[0]
    require(timeout.get("uid") == "53", "Timeout event moved")
    ordered = unique(root, "sequence", "10111")
    require(ordered in timeout.iter(), "Timeout ordered sequence moved")
    frame = ordered.find("diagramList")[3]
    require(frame.get("uid") == "42045", "cooling guard frame moved")
    case = unique(root, "select", "11044")
    require(case in frame.iter()
            and [term.get("uid") for term in case.findall("termList/*")] == ["44205"],
            "cooling flow Case selector changed")
    require(unique(root, "gRef", "7436").findtext("termList/*/dco/paramIdx") == "18"
            and unique(root, "gRef", "10202").findtext("termList/*/dco/paramIdx") == "16",
            "raw C3/C4 input local identity changed")
    c3 = unique(root, "nMux", "42277")
    c4 = unique(root, "nMux", "39336")
    require(field(c3, "42286") == 0 and field(c3, "42289") == 6
            and field(c4, "51373") == 19 and field(c4, "53472") == 38,
            "raw flow-guard input fields changed")
    compound = unique(root, "cpdArith", "47240")
    inverted_inputs = [
        compound.find(f"termList/*[@uid='{uid}']")
        for uid in ("47325", "47330")
    ]
    require(int(compound.findtext("objFlags", default="0")) & (0x7 << 16) == 3 << 16
            and all(term is not None and term.findtext("dco/objFlags") == "327680"
                    for term in inverted_inputs),
            "C3 inverted compound-OR operation changed")
    require(unique(root, "prim", "12948").findtext("primResID") == "1062"
            and unique(root, "prim", "52228").findtext("primResID") == "1061",
            "C4 OR / final AND primitive changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]
    for source, target in WIRES:
        require(any({source, target} <= group for group in signals),
                f"raw flow-guard wire {source}->{target} changed")
    return [
        "Case selector is directly fed by (C4[19] OR C4[38]) "
        "AND ((NOT C3[0]) OR (NOT C3[6]))",
        "No ACTION or EPS status input lies on this selector wire; "
        "the configured timeout is 20 ms, not a measured reevaluation period",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ cooling-flow selector raw wires")


if __name__ == "__main__":
    main()
