"""Bound saved Supervision root consumption of ACQ EPS pulse-stop flags.

Usage: python tools/validate_sup_impulsion_eps_consumers.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_sup_modulator_request_gate import checked_archive, field, require, unique


def validate(path: Path) -> list[str]:
    root, _ = checked_archive(path)
    refs = [node for node in root.findall(".//*[@class='gRef']")
            if node.findtext("termList/*/dco/paramIdx") == "175"]
    require({node.get("uid") for node in refs}
            == {"48425", "48321", "48950", "30797"},
            "Supervision root EPS local-reference census changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for reader_uid, term_uid, mux_uid, input_uid, expected_fields in (
        ("48950", "48954", "48963", "48966", (58,)),
        ("30797", "30810", "30843", "30848", (8, 14, 20, 26, 32)),
    ):
        reader = unique(root, "gRef", reader_uid)
        mux = unique(root, "nMux", mux_uid)
        require(reader.find("termList/*").findtext("objFlags") == "4096",
                f"EPS reader {reader_uid} direction changed")
        direct(term_uid, input_uid)
        require(tuple(field(mux, term.get("uid"))
                      for term in mux.findall("termList/*")[1:])
                == expected_fields,
                f"EPS consumer field set at {mux_uid} changed")
    writer = unique(root, "gRef", "48425")
    require(writer.find("termList/*").findtext("objFlags") == "36864",
            "EPS ingest local writer direction changed")
    direct("48402", "48439")
    direct("48326", "48393")
    require(unique(root, "sharedVariableDynamicRead", "48340") is not None,
            "EPS PSP read moved")
    return [
        "Saved Supervision root EPS local has four references: one PSP-ingest "
        "writer, one PSP-read type input, and readers of fields 58 and "
        "8/14/20/26/32",
        "No direct root EPS[42] or EPS[55] consumer exists in this saved VI",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Supervision root EPS consumer census")


if __name__ == "__main__":
    main()
