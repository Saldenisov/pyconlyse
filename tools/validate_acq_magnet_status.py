"""Check saved ACQ magnet start/stop/zero local EPS/DPS assignments.

Usage: python tools/validate_acq_magnet_status.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


# Event case, NewVal selector, ordered sequence, completion frame,
# EPS bundle, DPS bundle, exact local Boolean assignments.
CASES = (
    (16, "29880", "30036", 13, "32270", "32306",
     {56: False, 58: True, 64: False, 67: False}, {20: False}),
    (17, "42497", "42523", 4, "42975", "43011",
     {65: False, 58: False, 64: False, 67: True, 61: False}, {23: False}),
    (25, "38772", "38798", 3, "39579", "39675",
     {59: False, 64: False, 61: True}, {21: False}),
)


def direct_literal(frame, terminal_uid: str, expected: bool) -> None:
    nets = [
        net for net in frame.findall("signalList/*")
        if terminal_uid in {term.get("uid") for term in net.findall("termList/*")}
    ]
    require(len(nets) == 1, f"status terminal {terminal_uid} net count changed")
    peers = {term.get("uid") for term in nets[0].findall("termList/*")}
    require(len(peers) == 2, f"status terminal {terminal_uid} source changed")
    source_uid = next(uid for uid in peers if uid != terminal_uid)
    literals = frame.findall(f".//*[@uid='{source_uid}']/dco/ConstValue")
    require(len(literals) == 1
            and literals[0].text == ("01" if expected else "0000"),
            f"status terminal {terminal_uid} literal value changed")


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    event_frames = unique(root, "eventStruct", "43").find("diagramList")
    require(event_frames is not None and len(event_frames) == 26,
            "ACQ runtime event count changed")
    lines = []
    for (event_index, selector_uid, sequence_uid, frame_index,
         eps_mux_uid, dps_mux_uid, eps_fields, dps_fields) in CASES:
        event = event_frames[event_index]
        selector = unique(root, "select", selector_uid)
        sequence = unique(root, "sequence", sequence_uid)
        require(selector in event.iter()
                and [(item.findtext("start"), item.findtext("diagramIdx"))
                     for item in selector.findall("SelectRangeArray32/*")]
                == [("0", "0"), ("1", "1")]
                and len(selector.find("diagramList")[0].find("zPlaneList")) == 0
                and sequence in selector.find("diagramList")[1].iter(),
                f"event {event_index} NewVal gate changed")
        frame = sequence.find("diagramList")[frame_index]
        eps_mux = unique(root, "nMux", eps_mux_uid)
        dps_mux = unique(root, "nMux", dps_mux_uid)
        require(eps_mux in frame.iter() and dps_mux in frame.iter(),
                f"event {event_index} status bundle moved")
        for mux, expected_fields in ((eps_mux, eps_fields), (dps_mux, dps_fields)):
            terminals = mux.findall("termList/*")[2:]
            actual_fields = [field(mux, term.get("uid")) for term in terminals]
            require(actual_fields == list(expected_fields),
                    f"event {event_index} status field set changed: {actual_fields}")
            for term in terminals:
                index = field(mux, term.get("uid"))
                direct_literal(frame, term.get("uid"), expected_fields[index])
        for param in ("44", "36"):
            writers = [
                node for node in event.iter() if node.get("class") == "gRef"
                and node.findtext("termList/*/dco/paramIdx") == param
                and node.find("termList/*").findtext("objFlags") == "36864"
            ]
            require(len(writers) == 1 and writers[0] in frame.iter(),
                    f"event {event_index} local status writer count changed for {param}")
        lines.append(f"event {event_index}: EPS {eps_fields}; DPS {dps_fields}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: three magnet-event local status bundles and literal wires")


if __name__ == "__main__":
    main()
