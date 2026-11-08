"""List all direct wire uses of one root-VI local cluster reference.

The caller must supply a *manually verified* gRef paramIdx. This does not
guess parameter identities from FPHb ordering. Read-only static analysis.
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def parent_diag(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element | None:
    current = parents.get(node)
    while current is not None:
        if current.get("class") == "diag":
            return current
        current = parents.get(current)
    return None


def scope_path(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> str:
    scopes = []
    current = node
    child_diag: ET.Element | None = None
    scope_classes = {"sequence", "select", "event", "eventStruct", "whileLoop", "forLoop", "diagramDisable"}
    while current in parents:
        current = parents[current]
        if current.get("class") == "diag":
            child_diag = current
        if current.get("class") not in scope_classes:
            continue
        idx = "?"
        diagrams = current.find("diagramList")
        if child_diag is not None and diagrams is not None:
            for i, diagram in enumerate(diagrams):
                if diagram.get("uid") == child_diag.get("uid"):
                    idx = str(i)
                    break
        scopes.append(f"{current.get('class')}:{current.get('uid')}[{idx}]")
        child_diag = None
    return "/".join(reversed(scopes))


def signal_peers(term_uid: str, links: dict[str, list[tuple[str, list[str]]]], owners: dict[str, ET.Element]) -> list[str]:
    result = []
    for signal_uid, term_uids in links.get(term_uid, []):
        for other_uid in term_uids:
            if other_uid == term_uid:
                continue
            peer = owners.get(other_uid)
            result.append(f"{signal_uid}:{other_uid}:{peer.get('class')}:{peer.get('uid')}" if peer is not None else f"{signal_uid}:{other_uid}:unresolved")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("param_idx", type=int)
    args = parser.parse_args()
    root = ET.parse(args.bdhb_xml).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    owners: dict[str, ET.Element] = {}
    for node in root.iter():
        if not node.get("class") or node.get("class") == "signal":
            continue
        term_list = node.find("termList")
        for term in term_list if term_list is not None else []:
            if term.get("class") == "term" and term.get("uid"):
                owners[term.get("uid", "")] = node
    links: dict[str, list[tuple[str, list[str]]]] = {}
    for signal in root.findall(".//*[@class='signal']"):
        term_list = signal.find("termList")
        if term_list is None:
            continue
        terms = [term.get("uid", "") for term in term_list]
        for term in terms:
            links.setdefault(term, []).append((signal.get("uid", ""), terms))

    targets = []
    for node in root.findall(".//*[@class='gRef']"):
        param = node.findtext("termList/*/dco/paramIdx")
        if param is not None and param.isdigit() and int(param) == args.param_idx:
            targets.append(node)
    print(f"paramIdx {args.param_idx}: {len(targets)} local references")
    for node in targets:
        diagram = parent_diag(node, parents)
        term_list = node.find("termList")
        term_uid = next((term.get("uid", "") for term in term_list), "") if term_list is not None else ""
        print(f"gRef {node.get('uid')} diag {diagram.get('uid') if diagram is not None else '?'} term {term_uid} scope {scope_path(node, parents)}")
        for peer in signal_peers(term_uid, links, owners):
            print("  ->", peer)
            parts = peer.split(":")
            if len(parts) < 4 or parts[2] != "nMux":
                continue
            mux = next((candidate for candidate in root.findall(".//*[@class='nMux']") if candidate.get("uid") == parts[3]), None)
            if mux is None:
                continue
            print("     nMux flags", mux.findtext("objFlags", default=""))
            mux_terms = mux.find("termList")
            for mux_term in mux_terms if mux_terms is not None else []:
                if mux_term.get("uid") == parts[1]:
                    continue
                print("     field", mux_term.findtext("dco/i", default="0"),
                      "term", mux_term.get("uid"),
                      "peers", ", ".join(signal_peers(mux_term.get("uid", ""), links, owners)))


if __name__ == "__main__":
    main()
