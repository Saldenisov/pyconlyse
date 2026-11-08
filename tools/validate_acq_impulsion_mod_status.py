"""Validate saved ACQ NI6602 impulsion-start/stop local status fields.

Usage: python tools/validate_acq_impulsion_mod_status.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


CASES = (
    # Event, NewVal Case, sequence, status frame, EPS bundle, DPS bundle,
    # (EPS index, field terminal, literal terminal, Boolean), DPS tuple.
    (23, "45163", "45189", 1, "45320", "45347",
     ((55, "45326", "45282", False),
      (52, "45329", "45292", True)),
     (18, "45353", "45302", False)),
    (24, "40754", "40791", 2, "41217", "41245",
     ((42, "41223", "41169", True),
      (52, "41226", "41179", False)),
     (19, "41251", "41189", False)),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    events = unique(root, "eventStruct", "43").find("diagramList")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for (event_index, selector_uid, sequence_uid, frame_index,
         eps_mux_uid, dps_mux_uid, eps_fields, dps_field) in CASES:
        event = events[event_index]
        selector = unique(root, "select", selector_uid)
        sequence = unique(root, "sequence", sequence_uid)
        require(selector in event.iter()
                and [(entry.findtext("start"), entry.findtext("diagramIdx"))
                     for entry in selector.findall("SelectRangeArray32/*")]
                == [("0", "0"), ("1", "1")]
                and len(selector.find("diagramList")[0].find("zPlaneList")) == 0
                and sequence in selector.find("diagramList")[1].iter(),
                f"event {event_index} NewVal gate changed")
        frame = sequence.find("diagramList")[frame_index]
        eps_mux = unique(root, "nMux", eps_mux_uid)
        dps_mux = unique(root, "nMux", dps_mux_uid)
        require(eps_mux in frame.iter() and dps_mux in frame.iter(),
                f"event {event_index} status bundles moved")
        require(tuple(field(eps_mux, term.get("uid"))
                      for term in eps_mux.findall("termList/*")[2:])
                == tuple(item[0] for item in eps_fields),
                f"event {event_index} EPS field set changed")
        require(tuple(field(dps_mux, term.get("uid"))
                      for term in dps_mux.findall("termList/*")[2:])
                == (dps_field[0],),
                f"event {event_index} DPS field changed")
        for index, target_uid, literal_uid, value in (*eps_fields, dps_field):
            literal = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
            require(literal is not None
                    and literal.text == ("01" if value else "0000"),
                    f"event {event_index} field {index} literal changed")
            direct(literal_uid, target_uid)
        eps_writers = [node for node in event.iter()
                       if node.get("class") == "gRef"
                       and node.findtext("termList/*/dco/paramIdx") == "44"
                       and node.find("termList/*").findtext("objFlags") == "36864"]
        require(len(eps_writers) == 1 and eps_writers[0] in frame.iter(),
                f"event {event_index} additional EPS writer appeared")
    return [
        "Impulsion start event 23 assigns EPS[55]=False, EPS[52]=True, "
        "DPS[18]=False",
        "Impulsion stop event 24 assigns EPS[42]=True, EPS[52]=False, "
        "DPS[19]=False; it does not assign EPS[55] in that event",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ impulsion start/stop local status wires")


if __name__ == "__main__":
    main()
