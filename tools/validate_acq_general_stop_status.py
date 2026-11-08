"""Check saved ACQ General Modulator stop local status frame offline.

Usage: python tools/validate_acq_general_stop_status.py SOURCE_EXPORT_ZIP
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


FALSE_EPS = (
    (8, "28779"), (14, "30016"), (20, "30196"),
    (26, "30205"), (32, "30214"), (9, "44931"),
)
TRUE_EPS = (
    (11, "31248"), (17, "31647"), (23, "36547"),
    (29, "36851"), (35, "23531"),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    runtime = unique(root, "eventStruct", "43")
    event = runtime.find("diagramList")[6]
    require(event.get("uid") == "25330", "General-stop event 6 moved")
    selector = unique(root, "select", "26469")
    require(selector in event.iter()
            and [(case.findtext("start"), case.findtext("diagramIdx"))
                 for case in selector.findall("SelectRangeArray32/*")] ==
            [("0", "0"), ("1", "1")], "General-stop NewVal case changed")
    false_frame, true_frame = selector.find("diagramList")
    require(false_frame.get("uid") == "26520"
            and true_frame.get("uid") == "26538"
            and len(false_frame.find("zPlaneList")) == 0,
            "General-stop False arm no longer empty")
    wire(peers(event), "26424", "26478")
    sequence = unique(root, "sequence", "26556")
    require(sequence in true_frame.iter(), "General-stop ordered sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 17,
            "General-stop sequence frame count changed")
    status = frames[15]
    require(status.get("uid") == "28661", "General-stop status frame moved")
    eps_mux = unique(root, "nMux", "28738")
    dps_mux = unique(root, "nMux", "28821")
    require(eps_mux in status.iter() and dps_mux in status.iter(),
            "General-stop EPS/DPS bundles moved")
    for uid, param in (("28788", "44"), ("28721", "44"),
                       ("35113", "36"), ("28802", "36")):
        ref = unique(root, "gRef", uid)
        require(ref in status.iter()
                and ref.findtext("termList/*/dco/paramIdx") == param,
                f"General-stop reference {uid} changed")
    literal(status, "28667", "0000")
    literal(status, "28677", "01")
    literal(status, "28699", "0000")
    signals = peers(status)
    for index, target_term in FALSE_EPS:
        require(field(eps_mux, target_term) == index,
                f"General-stop EPS False field {index} changed")
        wire(signals, "28667", target_term)
    for index, target_term in TRUE_EPS:
        require(field(eps_mux, target_term) == index,
                f"General-stop EPS True field {index} changed")
        wire(signals, "28677", target_term)
    require(field(dps_mux, "35108") == 3,
            "General-stop DPS request field changed")
    wire(signals, "28699", "35108")
    return [
        "ACQ General-stop event 6 frame 15 clears five stage-OK EPS bits "
        "8/14/20/26/32, sets five stop-OK bits 11/17/23/29/35, "
        "clears EPS[9] and DPS[3]",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ General Modulator stop local status wires")


if __name__ == "__main__":
    main()
