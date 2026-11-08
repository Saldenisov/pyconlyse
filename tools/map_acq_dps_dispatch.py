"""Read-only map of DPS request bits to ACQ timeout dispatch properties.

The mapping is established by VCTP cluster order, the raw selector wiring,
and the property nodes inside each branch. It does not prove that an event
handler or a physical action subsequently runs.
"""

from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from pathlib import Path


SELECT_UID = "8105"


def label(node: ET.Element) -> str:
    for part in node.findall("label"):
        if part.findtext("partID") == "16":
            return (part.findtext("textRec/text") or "").strip('"')
    return ""


def dps_fields(main_path: Path) -> list[str]:
    root = ET.parse(main_path).getroot()
    section = root.find("VCTP/Section")
    if section is None:
        raise RuntimeError("VCTP/Section absent")
    flat = [node for node in section if node.tag == "TypeDesc" and node.get("Type")]
    dps = [node for node in flat if node.get("Type") == "Cluster" and node.get("Label") == "DPS"]
    if len(dps) != 1:
        raise RuntimeError(f"Expected one DPS type, found {len(dps)}")
    return [flat[int(child.get("TypeID", "-1"))].get("Label", "") for child in dps[0]]


def dispatch_rows(bdhb_path: Path, fields: list[str]) -> list[dict[str, str | int]]:
    root = ET.parse(bdhb_path).getroot()
    selector = root.find(f".//*[@class='select'][@uid='{SELECT_UID}']")
    if selector is None:
        raise RuntimeError(f"Selector {SELECT_UID} absent")
    diagrams = selector.find("diagramList")
    if diagrams is None or len(diagrams) != 25:
        raise RuntimeError(f"Expected 25 selector diagrams, got {len(diagrams) if diagrams is not None else 0}")
    event = root.find(".//*[@class='eventStruct'][@uid='43']")
    if event is None:
        raise RuntimeError("Runtime event structure 43 absent")
    event_specs = event.find("EventNodeEvents")
    if event_specs is None or len(event_specs) != 26:
        raise RuntimeError("Expected 26 event specifications")
    event_by_ddo = {}
    for spec in event_specs:
        ddo_uid = spec.findtext("ddoUID", default="")
        if ddo_uid in ("", "0"):
            continue
        event_by_ddo.setdefault(ddo_uid, []).append(spec.findtext("diagramIdx", default=""))
    rows = []
    for case_idx, diagram in enumerate(diagrams):
        props = [node for node in diagram.findall("zPlaneList/*") if node.get("class") == "propNode"]
        if case_idx == 0:
            if props:
                raise RuntimeError("Default branch unexpectedly has property node")
            continue
        if len(props) != 1:
            raise RuntimeError(f"Case {case_idx} has {len(props)} direct property nodes")
        prop = props[0]
        prop_names = [node.text.strip('"') for node in prop.findall("termList/*/dco/propList/*/PropItemName") if node.text]
        if prop_names != ["Value", "Val(Sgnl)"]:
            raise RuntimeError(f"Case {case_idx}: unexpected properties {prop_names}")
        # Both property inputs share one Boolean True source in the saved VI.
        prop_inputs = [term for term in prop.findall("termList/*") if term.find("dco/propList") is not None]
        prop_input_uids = {term.get("uid", "") for term in prop_inputs}
        const_terms = {
            term.get("uid", ""): term.findtext("dco/ConstValue", default="")
            for node in diagram.findall("nodeList/*") if node.get("class") == "sRN"
            for term in node.findall("termList/*")
        }
        true_source_found = False
        for signal in diagram.findall("signalList/*"):
            peer_uids = {term.get("uid", "") for term in signal.findall("termList/*")}
            if prop_input_uids <= peer_uids and any(const_terms.get(uid) == "01" for uid in peer_uids):
                true_source_found = True
        if len(prop_inputs) != 2 or not true_source_found:
            raise RuntimeError(f"Case {case_idx}: both properties must share literal True")
        ddo = prop.find("ddo")
        ddo_uid = ddo.get("uid", "") if ddo is not None else ""
        rows.append({
            "case_idx": case_idx,
            "dps_field_idx": case_idx - 1,
            "dps_field_label": fields[case_idx - 1],
            "property_label": label(prop),
            "prop_uid": prop.get("uid", ""),
            "target_ddo_uid": ddo_uid,
            "event_case_indices": "+".join(event_by_ddo.get(ddo_uid, [])),
            "diag_uid": diagram.get("uid", ""),
            "property_names": "+".join(prop_names),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("main_xml", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    fields = dps_fields(args.main_xml)
    rows = dispatch_rows(args.bdhb_xml, fields)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"DPS fields: {len(fields)}, dispatch cases: {len(rows)} -> {args.output_csv}")
    for row in rows:
        print(f"{row['case_idx']:2} DPS[{row['dps_field_idx']:2}] {row['dps_field_label']} -> {row['property_label']} -> event {row['event_case_indices'] or 'NONE'}")


if __name__ == "__main__":
    main()
