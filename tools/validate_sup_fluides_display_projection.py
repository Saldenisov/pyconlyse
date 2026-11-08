"""Check saved Supervision raw-input -> Page Fluides display wires offline.

Usage: python tools/validate_sup_fluides_display_projection.py SOURCE_EXPORT_ZIP
No VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_sup_modulator_request_gate import (
    checked_archive,
    cluster_fields,
    peers,
    require,
    unique,
    wire,
)


# Source field index and terminal, destination terminal. Destination labels
# are cross-checked against the saved Page Fluides type and frame audit.
C3_WIRES = (
    (0, "26417", "31581"),  # Canon 220V
    (1, "27270", "32100"),  # Canon Defauts
    (4, "27276", "32105"),  # Canon Pressostat
    (6, "27787", "32108"),  # Section 220V
    (7, "29658", "30827"),  # Section Defauts
    (10, "30123", "30832"), # Section Pressostat
)
C4_WIRES = (
    (19, "54136", "92264"), # Canon debimetre
    (38, "53515", "92269"), # Section debimetre
    (39, "89259", "92272"), # Resistivite
)
C1_WIRES = (
    (0, "55142", "53081"),  # Canon measured temperature
    (8, "55151", "53086"),  # Section measured temperature
)


def source_index(mux, terminal_uid):
    terms = [term for term in mux.findall("termList/*")
             if term.get("uid") == terminal_uid]
    require(len(terms) == 1, f"source terminal {terminal_uid} absent")
    return int(terms[0].findtext("dco/i") or "0")


def validate(path: Path) -> list[str]:
    root, main = checked_archive(path)
    sequence = unique(root, "sequence", "36869")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 23,
            "Supervision display sequence changed")
    frame = frames[8]
    require(frame.get("uid") == "23993", "Page Fluides display frame moved")
    refs = {ref.findtext("termList/*/dco/paramIdx")
            for ref in frame.iter() if ref.get("class") == "gRef"}
    require(refs == {"4", "29", "31", "32"},
            f"display frame local-reference set changed: {refs}")
    for uid, param in (("1558", "4"), ("26850", "4"),
                       ("26367", "31"), ("54116", "29"),
                       ("55094", "32")):
        ref = unique(root, "gRef", uid)
        require(ref in frame.iter()
                and ref.findtext("termList/*/dco/paramIdx") == param,
                f"display reference {uid} changed")
    source_c3 = unique(root, "nMux", "1559")
    source_c4 = unique(root, "nMux", "54131")
    source_c1 = unique(root, "nMux", "55130")
    target = unique(root, "nMux", "31571")
    require(all(node in frame.iter() for node in
                (source_c3, source_c4, source_c1, target)),
            "display source/target bundles moved")
    names_c3 = cluster_fields(main, "C3_IN_DIO96")
    names_c4 = cluster_fields(main, "C4_IN_DIO96")
    names_page = cluster_fields(main, "Page Fluides")
    require(len(names_c3) == 56 and len(names_c4) == 64
            and len(names_page) == 23, "display bank schema changed")
    require([names_page[index] for index in (15, 11, 14, 17, 0, 18, 12, 1, 13)]
            == ["Canon 220V", "Canon Défauts", "Canon Pressostat",
                "Section 220V", "Section Défauts", "Section Pressostat",
                "Canon débimètre", "Section débimètre", "Résistivité"],
            "Page Fluides display labels changed")
    signals = peers(frame)
    results = []
    for bank, mux, wires in (("C3_IN_DIO96", source_c3, C3_WIRES),
                             ("C4_IN_DIO96", source_c4, C4_WIRES),
                             ("C1NI6071E", source_c1, C1_WIRES)):
        for index, source_term, target_term in wires:
            require(source_index(mux, source_term) == index,
                    f"{bank}[{index}] source field changed")
            require(any(term.get("uid") == target_term
                        for term in target.findall("termList/*")),
                    f"Page Fluides target terminal {target_term} changed")
            wire(signals, source_term, target_term)
            results.append(f"{bank}[{index}] -> Page Fluides terminal {target_term}")
    wire(signals, "7267", "31580")  # old Page Fluides cluster -> bundle base
    wire(signals, "31577", "26858") # rebuilt cluster -> local Page Fluides
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: nine raw digital and two analog Page Fluides display wires")


if __name__ == "__main__":
    main()
