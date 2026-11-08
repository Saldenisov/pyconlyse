"""Check saved ACQ HF enable/disable EPS wires and pulse-stop status overlap.

Usage: python tools/validate_acq_hf_status_collision.py SOURCE_EXPORT_ZIP
Read-only: no VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique
from validate_acq_magnet_status import direct_literal
from validate_acq_impulsion_mod_status import validate as validate_impulsion


CASES = (
    (18, "34237", "34267", "35761", "35792",
     {42: False, 39: True}, {13: False}),
    (19, "43675", "43701", "43829", "43856",
     {42: True, 39: False}, {14: False}),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    events = unique(root, "eventStruct", "43").find("diagramList")
    require(events is not None and len(events) == 26, "ACQ event count changed")
    lines = []
    for (index, selector_uid, sequence_uid, eps_mux_uid, dps_mux_uid,
         eps_fields, dps_fields) in CASES:
        event = events[index]
        selector = unique(root, "select", selector_uid)
        sequence = unique(root, "sequence", sequence_uid)
        require(selector in event.iter()
                and [(entry.findtext("start"), entry.findtext("diagramIdx"))
                     for entry in selector.findall("SelectRangeArray32/*")]
                == [("0", "0"), ("1", "1")]
                and len(selector.find("diagramList")[0].find("zPlaneList")) == 0
                and sequence in selector.find("diagramList")[1].iter(),
                f"HF event {index} NewVal gate changed")
        frame = sequence.find("diagramList")[1]
        eps_mux = unique(root, "nMux", eps_mux_uid)
        dps_mux = unique(root, "nMux", dps_mux_uid)
        require(eps_mux in frame.iter() and dps_mux in frame.iter(),
                f"HF event {index} status frame moved")
        for mux, expected in ((eps_mux, eps_fields), (dps_mux, dps_fields)):
            terminals = mux.findall("termList/*")[2:]
            require([field(mux, term.get("uid")) for term in terminals]
                    == list(expected), f"HF event {index} status fields changed")
            for term in terminals:
                direct_literal(frame, term.get("uid"), expected[field(mux, term.get("uid"))])
        eps_writers = [
            node for node in event.iter() if node.get("class") == "gRef"
            and node.findtext("termList/*/dco/paramIdx") == "44"
            and node.find("termList/*").findtext("objFlags") == "36864"
        ]
        require(len(eps_writers) == 1 and eps_writers[0] in frame.iter(),
                f"HF event {index} EPS writer count changed")
        lines.append(f"event {index}: EPS {eps_fields}; DPS {dps_fields}")
    # Reuse the independently hash-pinned event-24 check rather than rely
    # on a normalized parser label for its surprising EPS[42] assignment.
    validate_impulsion(path)
    lines.append("event 24 pulse stop independently assigns EPS[42]=True, "
                 "EPS[52]=False and leaves EPS[39] unchanged in that event")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: HF power status and pulse-stop EPS[42] overlap")


if __name__ == "__main__":
    main()
