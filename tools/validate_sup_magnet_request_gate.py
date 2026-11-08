"""Check saved Supervision magnet-request gate and three DPS wires, offline.

Usage: python tools/validate_sup_magnet_request_gate.py SOURCE_EXPORT_ZIP
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_sup_modulator_request_gate import (
    checked_archive,
    field,
    peers,
    require,
    unique,
    wire,
)


# UI order from the saved native Page Alimentations event print. The raw
# nMux <i> values are retained separately; they are not assumed to be the
# 14-field VCTP Page Alimentations cluster offsets.
COMMANDS = (
    ("Marche Aimants.", "47179", 11, "47204", 20),
    ("Arrêt Aimants", "47182", 10, "47207", 23),
    ("Aimant 0V", "67149", 19, "68861", 21),
)


def validate(path: Path) -> list[str]:
    root, _ = checked_archive(path)
    event = unique(root, "eventStruct", "5909")
    frames = event.find("diagramList")
    require(frames is not None and len(frames) == 34, "root event count changed")
    page_event = frames[17]
    require(page_event.get("uid") == "47072", "Page Alimentations event moved")
    local_indices = {
        ref.findtext("termList/*/dco/paramIdx")
        for ref in page_event.iter() if ref.get("class") == "gRef"
    }
    require(local_indices == {"176", "184"},
            f"Page Alimentations local-reference set changed: {local_indices}")

    source_ref = unique(root, "gRef", "47137")
    require(source_ref in page_event.iter()
            and source_ref.findtext("termList/*/dco/paramIdx") == "176",
            "DPS gate source local changed")
    for uid, primitive_id in (("38462", "1169"), ("40386", "1910")):
        primitive = unique(root, "prim", uid)
        require(primitive in page_event.iter()
                and primitive.findtext("primResID") == primitive_id,
                f"DPS gate primitive {uid} changed")
    event_signals = peers(page_event)
    for source, target in (
        ("47140", "38471"),  # local DPS -> Cluster To Array
        ("38468", "40396"),  # Boolean array -> Or Array Elements
        ("40393", "47156"),  # any pending DPS -> Case selector
        ("47129", "47161"),  # Page NewVal -> Case tunnel
    ):
        wire(event_signals, source, target)

    gate = unique(root, "select", "47154")
    require(gate in page_event.iter(), "magnet DPS gate moved")
    ranges = gate.find("SelectRangeArray32")
    require(ranges is not None and [
        (case.findtext("start"), case.findtext("diagramIdx"))
        for case in ranges
    ] == [("0", "0"), ("1", "1")], "magnet DPS gate polarity changed")
    idle, busy = gate.find("diagramList")
    require(idle.get("uid") == "47168" and busy.get("uid") == "47226",
            "magnet DPS gate frames changed")
    require(not any(node.get("class") == "sharedVariableDynamicWrite"
                    for node in busy.iter()), "busy branch now publishes DPS")

    source_mux = unique(root, "nMux", "47174")
    target_mux = unique(root, "nMux", "47198")
    dps_base = unique(root, "gRef", "47186")
    writer = unique(root, "sharedVariableDynamicWrite", "32048")
    require(all(node in idle.iter() for node in
                (source_mux, target_mux, dps_base, writer)),
            "magnet DPS nodes moved from idle branch")
    require(dps_base.findtext("termList/*/dco/paramIdx") == "176",
            "magnet DPS base local changed")
    idle_signals = peers(idle)
    for source, target in (
        ("47164", "47176"),  # event NewVal -> source mux
        ("47200", "47189"),  # DPS base -> target mux
        ("47200", "32664"),  # built DPS -> PSP writer payload
        ("31390", "32652"),  # literal DPS URI -> PSP writer reference
        ("32661", "36566"),  # write error -> nested error display Case
    ):
        wire(idle_signals, source, target)
    uri_terms = [term for term in idle.findall("nodeList/*/termList/*")
                 if term.get("uid") == "31390"]
    require(len(uri_terms) == 1, "DPS URI constant absent")
    uri_hex = uri_terms[0].findtext("dco/ConstValue")
    require(uri_hex is not None and bytes.fromhex(uri_hex)[4:].decode("ascii") ==
            "ni.var.psp://localhost/SUPERVISION/DPS", "DPS URI changed")

    lines = []
    for label, source_uid, source_i, target_uid, target_i in COMMANDS:
        require(field(source_mux, source_uid) == source_i,
                f"{label} source nMux slot changed")
        require(field(target_mux, target_uid) == target_i,
                f"{label} DPS target field changed")
        wire(idle_signals, source_uid, target_uid)
        lines.append(f"{label} -> DPS[{target_i}]")
    require(22 not in {entry[4] for entry in COMMANDS},
            "PT field unexpectedly listed as UI command")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Page Alimentations idle-DPS gate and three direct request wires")


if __name__ == "__main__":
    main()
