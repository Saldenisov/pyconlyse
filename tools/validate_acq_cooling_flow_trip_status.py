"""Check saved ACQ Timeout cooling-flow trip status assignments offline.

Usage: python tools/validate_acq_cooling_flow_trip_status.py SOURCE_EXPORT_ZIP
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


EPS_TERMINALS = (
    (1, "39285", "32862", "01"),
    (2, "38971", "32179", "0000"),
    (3, "38924", "32022", "0000"),
    (5, "39282", "32391", "01"),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    runtime = unique(root, "eventStruct", "43")
    timeout = runtime.find("diagramList")[0]
    ordered = unique(root, "sequence", "10111")
    require(ordered in timeout.iter(), "Timeout ordered frames moved")
    safety_frame = ordered.find("diagramList")[3]
    require(safety_frame.get("uid") == "42045",
            "Timeout cooling safety frame moved")
    guard_case = unique(root, "select", "11044")
    require(guard_case in safety_frame.iter(), "cooling flow Case moved")
    false_frame, true_frame = guard_case.find("diagramList")
    require(false_frame.get("uid") == "44189"
            and true_frame.get("uid") == "44195"
            and len(false_frame.find("zPlaneList")) == 0,
            "cooling flow Case arms changed")
    sequence = unique(root, "sequence", "8256")
    require(sequence in true_frame.iter(), "trip command sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 7,
            "trip sequence frame count changed")
    status_frame = frames[5]
    require(status_frame.get("uid") == "31857", "trip status frame moved")
    eps_mux = unique(root, "nMux", "38770")
    dps_mux = unique(root, "nMux", "39303")
    require(eps_mux in status_frame.iter() and dps_mux in status_frame.iter(),
            "trip status bundles moved")
    signals = peers(status_frame)
    for index, target_term, literal_uid, value in EPS_TERMINALS:
        require(field(eps_mux, target_term) == index,
                f"trip EPS field {index} changed")
        literal(status_frame, literal_uid, value)
        wire(signals, literal_uid, target_term)
    require(field(dps_mux, "39309") == 1,
            "trip DPS stop-request field changed")
    literal(status_frame, "38646", "0000")
    wire(signals, "38646", "39309")
    require(all(term.findtext("dco/i") != "8"
                for term in eps_mux.findall("termList/*")),
            "trip frame now assigns EPS GENERAL Mod. OK")
    for uid, param in (("39289", "44"), ("38731", "44"),
                       ("39313", "36"), ("39295", "36")):
        ref = unique(root, "gRef", uid)
        require(ref in status_frame.iter()
                and ref.findtext("termList/*/dco/paramIdx") == param,
                f"trip status local reference {uid} changed")
    return [
        "ACQ Timeout cooling-flow True arm frame 5: EPS[1]=True, "
        "EPS[2]=False, EPS[3]=False, EPS[5]=True, DPS[1]=False",
        "No EPS[8] assignment in this trip status bundle",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ cooling-flow trip local status wires")


if __name__ == "__main__":
    main()
