"""Check saved Supervision EPS -> Page Modulateur OK indicator wires.

Usage: python tools/validate_sup_modulator_stage_ok_projection.py SOURCE_EXPORT_ZIP
No VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_sup_modulator_request_gate import (
    checked_archive,
    cluster_fields,
    field,
    peers,
    require,
    unique,
    wire,
)


WIRES = (
    (8, "30922", 54, "61269", "GENERAL MOD OK"),
    (14, "30942", 55, "54398", "CHAUFFAGE OK"),
    (20, "38150", 56, "54404", "PREMA OK"),
    (26, "41931", 57, "54407", "RELAIS HT OK"),
    (32, "47143", 58, "54410", "FOCALES OK"),
)


def validate(path: Path) -> list[str]:
    root, main = checked_archive(path)
    sequence = unique(root, "sequence", "49452")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 12,
            "Supervision status projection sequence changed")
    frame = frames[10]
    require(frame.get("uid") == "9031", "Modulateur OK frame moved")
    eps_ref = unique(root, "gRef", "30797")
    page_base = unique(root, "gRef", "53652")
    page_result = unique(root, "gRef", "53632")
    for ref, param in ((eps_ref, "175"), (page_base, "164"),
                       (page_result, "164")):
        require(ref in frame.iter()
                and ref.findtext("termList/*/dco/paramIdx") == param,
                f"Modulateur OK local reference {ref.get('uid')} changed")
    source = unique(root, "nMux", "30843")
    target = unique(root, "nMux", "61263")
    require(source in frame.iter() and target in frame.iter(),
            "EPS/Page Modulateur bundles moved")
    signals = peers(frame)
    wire(signals, "30810", "30848")  # EPS local -> unbundle
    wire(signals, "53659", "61268")  # Page Modulateur base -> bundle
    wire(signals, "61265", "53640")  # rebuilt page -> local indicator
    eps_names = cluster_fields(main, "EPS")
    page_names = cluster_fields(main, "Page Modulateur")
    require(len(eps_names) == 77 and len(page_names) == 59,
            "EPS/Page Modulateur schema changed")
    lines = []
    for eps_index, source_term, page_index, target_term, label in WIRES:
        require(field(source, source_term) == eps_index,
                f"EPS field {eps_index} changed")
        require(field(target, target_term) == page_index,
                f"Page Modulateur field {page_index} changed")
        require(page_names[page_index] == label,
                f"Page Modulateur label {page_index} changed")
        wire(signals, source_term, target_term)
        lines.append(f"EPS[{eps_index}] {eps_names[eps_index]} -> "
                     f"Page Modulateur[{page_index}] {label}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: five direct EPS -> Page Modulateur OK indicator wires")


if __name__ == "__main__":
    main()
