"""Census saved Supervision root's local DPS writers, without running a VI.

Usage: python tools/validate_sup_dps_writer_census.py SOURCE_EXPORT_ZIP
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from validate_sup_modulator_request_gate import checked_archive, require


PARAM_IDX = "176"
EXPECTED_BUNDLE_WRITERS = {
    "38203": ("38212", {0, 1}, "38229"),
    "38967": ("38974", {15, 16, 17, 18, 19}, "38989"),
    "55371": ("55382", {13, 14}, "55466"),
    "47186": ("47198", {20, 21, 23}, "32048"),
    "33453": ("33466", set(range(2, 13)), "33792"),
}
PSP_INGEST_WRITER = "36152"


def owner(term: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element:
    return parents[parents[term]]


def containing_diagram(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element:
    current = node
    while current.get("class") != "diag":
        current = parents[current]
    return current


def wired_owners(
    terminal: ET.Element, diagram: ET.Element, parents: dict[ET.Element, ET.Element]
) -> set[tuple[str | None, str | None]]:
    nets = [
        net for net in diagram.findall("signalList/*")
        if terminal.get("uid") in {term.get("uid") for term in net.findall("termList/*")}
    ]
    require(len(nets) == 1, f"writer terminal {terminal.get('uid')} net count {len(nets)}")
    term_by_uid = {
        term.get("uid"): term
        for node in diagram.findall("zPlaneList/*")
        for term in node.findall("termList/*")
    }
    return {
        (owner(term_by_uid[peer.get("uid")], parents).get("class"),
         owner(term_by_uid[peer.get("uid")], parents).get("uid"))
        for peer in nets[0].findall("termList/*")
        if peer.get("uid") != terminal.get("uid")
    }


def validate(path: Path) -> dict[str, set[int]]:
    root, _ = checked_archive(path)
    parents = {child: parent for parent in root.iter() for child in parent}
    writers: dict[str, ET.Element] = {}
    for ref in root.findall(".//*[@class='gRef']"):
        terminal = ref.find("termList/*")
        if (terminal is not None
                and terminal.findtext("dco/paramIdx") == PARAM_IDX
                and terminal.findtext("objFlags") == "36864"):
            writers[ref.get("uid", "")] = ref
    require(set(writers) == set(EXPECTED_BUNDLE_WRITERS) | {PSP_INGEST_WRITER},
            f"DPS local-writer census changed: {sorted(writers)}")

    ingest = writers[PSP_INGEST_WRITER]
    ingest_terminal = ingest.find("termList/*")
    require(ingest_terminal is not None, "DPS PSP-ingest terminal absent")
    ingest_owners = wired_owners(
        ingest_terminal, containing_diagram(ingest, parents), parents
    )
    require(ingest_owners == {("sharedVariableDynamicRead", "36097")},
            f"DPS PSP-ingest source changed: {ingest_owners}")
    ingest_diagram = containing_diagram(ingest, parents)
    uri_terms = [term for term in ingest_diagram.findall("nodeList/*/termList/*")
                 if term.get("uid") == "36055"]
    require(len(uri_terms) == 1, "DPS PSP-ingest URI literal absent")
    uri_hex = uri_terms[0].findtext("dco/ConstValue")
    require(uri_hex is not None and bytes.fromhex(uri_hex)[4:].decode("ascii") ==
            "ni.var.psp://localhost/SUPERVISION/DPS", "DPS ingest URI changed")
    ingest_nets = [
        {term.get("uid") for term in net.findall("termList/*")}
        for net in ingest_diagram.findall("signalList/*")
    ]
    require(any({"36055", "36100"} <= net for net in ingest_nets),
            "DPS ingest URI-to-read wire changed")

    fields_by_writer: dict[str, set[int]] = {}
    for ref_uid, (mux_uid, expected_fields, psp_uid) in EXPECTED_BUNDLE_WRITERS.items():
        ref = writers[ref_uid]
        terminal = ref.find("termList/*")
        require(terminal is not None, f"DPS writer {ref_uid} terminal absent")
        owners = wired_owners(terminal, containing_diagram(ref, parents), parents)
        require(owners == {("nMux", mux_uid), ("sharedVariableDynamicWrite", psp_uid)},
                f"DPS writer {ref_uid} source/publisher changed: {owners}")
        muxes = root.findall(f".//*[@class='nMux'][@uid='{mux_uid}']")
        require(len(muxes) == 1, f"DPS bundle {mux_uid} missing/duplicated")
        # First two nMux terminals are aggregate input/output. Field zero's
        # own terminal omits <i>; later field terminals carry explicit indices.
        field_terms = muxes[0].findall("termList/*")[2:]
        fields = {
            int(value) if value is not None else 0
            for mux_term in field_terms
            for value in [mux_term.findtext("dco/i")]
        }
        require(fields == expected_fields,
                f"DPS writer {ref_uid} fields changed: {sorted(fields)}")
        fields_by_writer[ref_uid] = fields
    require(set().union(*fields_by_writer.values()) == set(range(22)) | {23},
            "DPS UI-producer field union changed")
    return fields_by_writer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    fields_by_writer = validate(args.source_export_zip)
    for uid, fields in fields_by_writer.items():
        print(f"local DPS writer {uid}: fields {sorted(fields)}")
    print("PASS: five SUP UI DPS bundles cover 0..21,23; sixth local writer ingests PSP")


if __name__ == "__main__":
    main()
