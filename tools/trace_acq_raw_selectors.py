"""Inventory case-selector wires directly from a LabVIEW BDHb XML heap.

This deliberately reports raw node/terminal identities.  A local-variable
``paramIdx`` is *not* treated as an index into the front-panel z-order: that
shortcut has produced demonstrably type-incompatible names for ACQ ELYSE.
The script only reads the extracted XML and writes a CSV; it does not open a VI.
"""

from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from pathlib import Path


def ancestor_with_class(element: ET.Element, parents: dict[ET.Element, ET.Element], wanted: str) -> ET.Element | None:
    current = parents.get(element)
    while current is not None:
        if current.get("class") == wanted:
            return current
        current = parents.get(current)
    return None


def selector_rows(xml_path: Path, diagram_uid: str | None = None) -> list[dict[str, str]]:
    root = ET.parse(xml_path).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}

    term_owners: dict[str, ET.Element] = {}
    for node in root.iter():
        if not node.get("class") or node.get("class") == "signal":
            continue
        term_list = node.find("termList")
        if term_list is None:
            continue
        for term in term_list:
            if term.get("class") == "term" and term.get("uid"):
                term_owners[term.get("uid", "")] = node

    signals_by_term: dict[str, list[tuple[str, list[str]]]] = {}
    for signal in root.iter():
        if signal.get("class") != "signal":
            continue
        term_list = signal.find("termList")
        if term_list is None:
            continue
        term_uids = [item.get("uid", "") for item in term_list]
        for uid in term_uids:
            signals_by_term.setdefault(uid, []).append((signal.get("uid", ""), term_uids))

    if diagram_uid is not None:
        diagram = root.find(f".//*[@class='diag'][@uid='{diagram_uid}']")
        if diagram is None:
            raise SystemExit(f"diagram UID {diagram_uid} not found")
        zplane = diagram.find("zPlaneList")
        print(f"diagram {diagram_uid} direct nodes:")
        for node in zplane if zplane is not None else []:
            if not node.get("class"):
                continue
            extra = ""
            if node.get("class") == "gRef":
                extra = " paramIdx=" + node.findtext("termList/*/dco/paramIdx", default="")
            elif node.get("class") == "nMux":
                term_list = node.find("termList")
                extra = " fields=" + ",".join(
                    f"{term.get('uid')}:{term.findtext('dco/i', default='0')}:{term.findtext('objFlags', default='')}"
                    for term in (term_list if term_list is not None else [])
                )
            elif node.get("class") == "label":
                extra = " text=" + node.findtext("textRec/text", default="")
            print("  ", node.get("class"), node.get("uid"),
                  "flags=" + node.findtext("objFlags", default=""),
                  "prim=" + node.findtext("primResID", default="") + "/" + node.findtext("primIndex", default=""),
                  "bounds=" + node.findtext("bounds", default="") + extra)
        print(f"diagram {diagram_uid} direct signals:")
        signal_list = diagram.find("signalList")
        for signal in signal_list if signal_list is not None else []:
            term_list = signal.find("termList")
            peers = []
            for item in term_list if term_list is not None else []:
                owner = term_owners.get(item.get("uid", ""))
                peers.append(f"{item.get('uid')}:{owner.get('class')}:{owner.get('uid')}" if owner is not None else item.get("uid", ""))
            print("  ", signal.get("uid"), " ".join(peers))
        node_list = diagram.find("nodeList")
        for node in node_list if node_list is not None else []:
            if node.get("class") != "sRN":
                continue
            term_list = node.find("termList")
            for term in term_list if term_list is not None else []:
                dco = term.find("dco")
                if dco is None or dco.get("class") != "bDConstDCO":
                    continue
                label = dco.findtext("ddo/partsList/*[@class='label']/textRec/text", default="")
                print("  constant", term.get("uid"), "value=" + dco.findtext("ConstValue", default=""), "label=" + label)

    rows: list[dict[str, str]] = []
    for selector in root.iter():
        if selector.get("class") != "select":
            continue
        select_terms = selector.find("termList")
        if select_terms is None:
            continue
        term_uids = [item.get("uid", "") for item in select_terms if item.get("class") == "term"]
        for select_term_uid in term_uids:
            connections = signals_by_term.get(select_term_uid, [])
            if not connections:
                rows.append({
                    "selector_uid": selector.get("uid", ""),
                    "selector_term_uid": select_term_uid,
                    "signal_uid": "",
                    "peer_term_uid": "",
                    "peer_class": "",
                    "peer_uid": "",
                    "gref_param_idx": "",
                    "gref_type_desc": "",
                    "parent_diag_uid": (ancestor_with_class(selector, parents, "diag") or ET.Element("none")).get("uid", ""),
                })
                continue
            for signal_uid, connected_terms in connections:
                for peer_term_uid in connected_terms:
                    if peer_term_uid == select_term_uid:
                        continue
                    peer = term_owners.get(peer_term_uid)
                    peer_class = peer.get("class", "") if peer is not None else "unresolved"
                    gref_dco = peer.find("termList/*/dco") if peer is not None and peer_class == "gRef" else None
                    parent_diag = ancestor_with_class(selector, parents, "diag")
                    rows.append({
                        "selector_uid": selector.get("uid", ""),
                        "selector_term_uid": select_term_uid,
                        "signal_uid": signal_uid,
                        "peer_term_uid": peer_term_uid,
                        "peer_class": peer_class,
                        "peer_uid": peer.get("uid", "") if peer is not None else "",
                        "gref_param_idx": gref_dco.findtext("paramIdx", default="") if gref_dco is not None else "",
                        "gref_type_desc": gref_dco.findtext("typeDesc", default="") if gref_dco is not None else "",
                        "parent_diag_uid": parent_diag.get("uid", "") if parent_diag is not None else "",
                    })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--diagram-uid")
    parser.add_argument("--node-uid")
    parser.add_argument("--sequence-uid")
    parser.add_argument("--select-uid")
    parser.add_argument("--frame-index", type=int)
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    if args.node_uid is not None:
        if args.diagram_uid is not None or args.sequence_uid is not None or args.select_uid is not None:
            raise SystemExit("--node-uid excludes explicit scope")
        root = ET.parse(args.bdhb_xml).getroot()
        parents = {child: parent for parent in root.iter() for child in parent}
        node = root.find(f".//*[@class][@uid='{args.node_uid}']")
        if node is None:
            raise SystemExit(f"node UID {args.node_uid} not found")
        current = node
        while current is not None:
            if current.get("class") in {"diag", "sequence", "select", "eventStruct", "whileLoop"}:
                parent = parents.get(current)
                frame = ""
                if parent is not None and parent.get("class") is None:
                    parent = parents.get(parent)
                if current.get("class") == "diag" and parent is not None and parent.get("class") in {"sequence", "select", "eventStruct"}:
                    diagrams = parent.find("diagramList")
                    if diagrams is not None:
                        frame = " frame=" + str(list(diagrams).index(current))
                print("ancestor", current.get("class"), current.get("uid") + frame)
                if args.diagram_uid is None and current.get("class") == "diag":
                    args.diagram_uid = current.get("uid")
            current = parents.get(current)
    if args.sequence_uid is not None or args.select_uid is not None:
        if args.diagram_uid is not None or args.frame_index is None:
            raise SystemExit("--sequence-uid/--select-uid requires --frame-index and excludes --diagram-uid")
        if args.sequence_uid is not None and args.select_uid is not None:
            raise SystemExit("Choose one scope UID")
        root = ET.parse(args.bdhb_xml).getroot()
        scope_class = "sequence" if args.sequence_uid is not None else "select"
        scope_uid = args.sequence_uid if args.sequence_uid is not None else args.select_uid
        scope = root.find(f".//*[@class='{scope_class}'][@uid='{scope_uid}']")
        if scope is None:
            raise SystemExit(f"{scope_class} UID {scope_uid} not found")
        diagrams = scope.find("diagramList")
        if diagrams is None or not 0 <= args.frame_index < len(diagrams):
            raise SystemExit("sequence frame index out of range")
        args.diagram_uid = diagrams[args.frame_index].get("uid")
    rows = selector_rows(args.bdhb_xml, args.diagram_uid)
    if args.inspect_only:
        return
    fieldnames = [
        "selector_uid", "selector_term_uid", "signal_uid", "peer_term_uid",
        "peer_class", "peer_uid", "gref_param_idx", "gref_type_desc",
        "parent_diag_uid",
    ]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} raw selector peer rows -> {args.output_csv}")


if __name__ == "__main__":
    main()
