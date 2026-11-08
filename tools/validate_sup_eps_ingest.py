"""Check saved Supervision EPS PSP ingest wires, offline.

Usage: python tools/validate_sup_eps_ingest.py SOURCE_EXPORT_ZIP
No VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_sup_modulator_request_gate import (
    checked_archive,
    peers,
    require,
    unique,
    wire,
)


def validate(path: Path) -> list[str]:
    root, main = checked_archive(path)
    sequence = unique(root, "sequence", "9257")
    runtime_loop = unique(root, "whileLoop", "5846")
    outer = unique(root, "sequence", "988")
    require(sequence in runtime_loop.iter()
            and outer.find("diagramList")[2].get("uid") == "5902"
            and runtime_loop in outer.find("diagramList")[2].iter(),
            "Supervision EPS ingest moved out of runtime loop")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 5,
            "Supervision shared-variable read sequence changed")
    frame = frames[2]
    require(frame.get("uid") == "26343", "EPS ingest frame moved")
    reader = unique(root, "sharedVariableDynamicRead", "48340")
    eps_local = unique(root, "gRef", "48321")
    require(reader in frame.iter() and eps_local in frame.iter()
            and eps_local.findtext("termList/*/dco/paramIdx") == "175",
            "EPS read/local nodes changed")
    signals = peers(frame)
    wire(signals, "48283", "48344")  # literal EPS URI -> reader
    wire(signals, "48393", "48326")  # reader data -> local EPS
    uri = frame.find(".//*[@uid='48283']/dco/ConstValue")
    require(uri is not None and uri.text is not None
            and bytes.fromhex(uri.text)[4:].decode("ascii") ==
            "ni.var.psp://localhost/SUPERVISION/EPS",
            "Supervision EPS PSP URI changed")
    literal_uri = "ni.var.psp://localhost/SUPERVISION/EPS".encode("ascii")
    encoded_uri = (len(literal_uri).to_bytes(4, "big") + literal_uri).hex().upper()
    uri_terminals = {
        term.get("uid")
        for node in root.findall(".//*[@class='sRN']")
        for term in node.findall("termList/*")
        if term.findtext("dco/ConstValue", default="").upper() == encoded_uri
    }
    require(uri_terminals == {"48283"},
            f"Supervision direct EPS PSP URI literal set changed: {uri_terminals}")
    section = main.find("VCTP/Section")
    require(section is not None, "Supervision type section absent")
    flat = [node for node in section
            if node.tag == "TypeDesc" and node.get("Type")]
    eps_types = [node for node in flat
                 if node.get("Type") == "Cluster" and node.get("Label") == "EPS"]
    require(len(eps_types) == 1 and len(eps_types[0]) == 77,
            "EPS cluster schema changed")
    return [
        "Supervision runtime loop 5846 sequence 9257 frame 2 reads local SUPERVISION/EPS PSP",
        "Read result wires to local reference paramIdx=175; UI use/freshness "
        "are not established by this ingest wire",
        "Only one direct EPS PSP URI literal occurs in this Supervision root graph",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Supervision EPS ingest raw wires")


if __name__ == "__main__":
    main()
