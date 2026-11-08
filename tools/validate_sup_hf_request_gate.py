"""Check saved Supervision Page HF request/adjustment gate and DPS wires.

Usage: python tools/validate_sup_hf_request_gate.py SOURCE_EXPORT_ZIP
Read-only: no VI, PSP variable, or NI card is accessed.
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


ARROWS = (2, 4, 3, 1, 14, 16, 15, 13)
COMMANDS = ((7, "55326", 13, "55399"),
            (6, "55334", 14, "55417"))


def validate(path: Path) -> list[str]:
    root, main = checked_archive(path)
    event = unique(root, "eventStruct", "5909")
    frames = event.find("diagramList")
    require(frames is not None and len(frames) == 34, "root event count changed")
    page_event = frames[16]
    require(page_event.get("uid") == "53716", "Page HF event moved")
    local_indices = {
        ref.findtext("termList/*/dco/paramIdx")
        for ref in page_event.iter() if ref.get("class") == "gRef"
    }
    require(local_indices == {"176", "184", "167", "24"},
            f"Page HF local-reference set changed: {local_indices}")

    for uid, primitive_id in (("58094", "1169"), ("58102", "1910"),
                              ("58189", "1910"), ("58142", "1062")):
        primitive = unique(root, "prim", uid)
        require(primitive in page_event.iter()
                and primitive.findtext("primResID") == primitive_id,
                f"Page HF gate primitive {uid} changed")
    source_ref = unique(root, "gRef", "53769")
    arrows = unique(root, "nMux", "58110")
    require(source_ref.findtext("termList/*/dco/paramIdx") == "176"
            and arrows in page_event.iter(), "Page HF gate input changed")
    arrow_terms = arrows.findall("termList/*")[1:]
    require(tuple(field(arrows, term.get("uid")) for term in arrow_terms) == ARROWS,
            "Page HF eight adjustment fields changed")

    outer_signals = peers(page_event)
    for source, target in (
        ("53773", "58099"),  # DPS -> Cluster To Array
        ("58096", "58107"),  # DPS Boolean array -> OR elements
        ("58104", "58149"),  # any DPS -> final OR
        ("53762", "58112"),  # Page HF NewVal -> arrow unbundle
        ("58160", "58194"),  # eight-arrow array -> OR elements
        ("58191", "58154"),  # any arrow -> final OR
        ("58144", "53784"),  # either busy condition -> Case selector
    ):
        wire(outer_signals, source, target)
    arrow_wires = (("58115", "58163"), ("58118", "58166"),
                   ("58122", "58169"), ("58125", "58172"),
                   ("58128", "58175"), ("58131", "58178"),
                   ("58134", "58181"), ("58137", "58184"))
    for source, target in arrow_wires:
        wire(outer_signals, source, target)

    gate = unique(root, "select", "53782")
    require(gate in page_event.iter(), "Page HF request gate moved")
    ranges = gate.find("SelectRangeArray32")
    require(ranges is not None and [
        (case.findtext("start"), case.findtext("diagramIdx"))
        for case in ranges
    ] == [("0", "0"), ("1", "1")], "Page HF gate polarity changed")
    idle, busy = gate.find("diagramList")
    require(idle.get("uid") == "53851" and busy.get("uid") == "55584",
            "Page HF gate frame identities changed")

    source_mux = unique(root, "nMux", "55312")
    target_mux = unique(root, "nMux", "55382")
    dps_base = unique(root, "gRef", "55371")
    writer = unique(root, "sharedVariableDynamicWrite", "55466")
    require(all(node in idle.iter() for node in
                (source_mux, target_mux, dps_base, writer)),
            "Page HF DPS-write nodes moved from idle branch")
    require(dps_base.findtext("termList/*/dco/paramIdx") == "176",
            "Page HF DPS base local changed")
    require(not any(node.get("class") == "gRef"
                    and node.findtext("termList/*/dco/paramIdx") == "176"
                    for node in busy.iter()),
            "Page HF busy branch now accesses local DPS")
    idle_signals = peers(idle)
    for source, target in (
        ("53792", "55318"),  # event NewVal -> command unbundle
        ("55389", "55375"),  # local DPS base -> bundle
        ("55389", "55500"),  # built DPS -> PSP writer payload
        ("53857", "55469"),  # DPS URI literal -> PSP writer reference
    ):
        wire(idle_signals, source, target)
    uri_terms = [term for term in idle.findall("nodeList/*/termList/*")
                 if term.get("uid") == "53857"]
    require(len(uri_terms) == 1, "Page HF DPS URI literal absent")
    uri_hex = uri_terms[0].findtext("dco/ConstValue")
    require(uri_hex is not None and bytes.fromhex(uri_hex)[4:].decode("ascii") ==
            "ni.var.psp://localhost/SUPERVISION/DPS", "Page HF DPS URI changed")

    page_names = cluster_fields(main, "Page HF")
    dps_names = cluster_fields(main, "DPS")
    require(len(page_names) == 26 and len(dps_names) == 29,
            "Page HF or DPS schema changed")
    lines = []
    for source_i, source_uid, target_i, target_uid in COMMANDS:
        require(field(source_mux, source_uid) == source_i
                and field(target_mux, target_uid) == target_i,
                f"Page HF command field {source_i}->{target_i} changed")
        wire(idle_signals, source_uid, target_uid)
        lines.append(f"Page HF[{source_i}] {page_names[source_i]} -> "
                     f"DPS[{target_i}] {dps_names[target_i]}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Page HF any-DPS/arrow gate and two direct request wires")


if __name__ == "__main__":
    main()
