"""Map root-VI local ``paramIdx`` values to PSP URIs by direct raw wires.

Only accepts a shared-variable node with exactly one gRef peer and one URI
constant peer in the same diagram. This is a type/URI association at one call
site, not a global proof of every local-variable identity. Read-only input.
"""

from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def parent_diag(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> str:
    current = parents.get(node)
    while current is not None:
        if current.get("class") == "diag":
            return current.get("uid", "")
        current = parents.get(current)
    return ""


def decode_uri(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        payload = bytes.fromhex(raw)
    except ValueError:
        return None
    if len(payload) < 4:
        return None
    size = int.from_bytes(payload[:4], "big")
    data = payload[4:4 + size]
    if len(data) != size:
        return None
    try:
        uri = data.decode("ascii")
    except UnicodeDecodeError:
        return None
    return uri if uri.startswith("ni.var.psp://") else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    root = ET.parse(args.bdhb_xml).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    term_owner: dict[str, ET.Element] = {}
    term_element: dict[str, ET.Element] = {}
    for node in root.iter():
        if not node.get("class") or node.get("class") == "signal":
            continue
        term_list = node.find("termList")
        for term in term_list if term_list is not None else []:
            if term.get("class") != "term" or not term.get("uid"):
                continue
            term_owner[term.get("uid", "")] = node
            term_element[term.get("uid", "")] = term

    peer_by_term: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for signal in root.findall(".//*[@class='signal']"):
        term_list = signal.find("termList")
        if term_list is None:
            continue
        terms = [term.get("uid", "") for term in term_list]
        for uid in terms:
            for other in terms:
                if other != uid:
                    peer_by_term[uid].append((signal.get("uid", ""), other))

    rows = []
    skipped = []
    classes = {"sharedVariableDynamicOpen", "sharedVariableDynamicWrite", "sharedVariableDynamicRead"}
    for node in root.iter():
        if node.get("class") not in classes:
            continue
        grefs = {}
        uris = {}
        term_list = node.find("termList")
        for term in term_list if term_list is not None else []:
            for signal_uid, peer_uid in peer_by_term.get(term.get("uid", ""), []):
                owner = term_owner.get(peer_uid)
                peer_term = term_element.get(peer_uid)
                if owner is None or peer_term is None:
                    continue
                if owner.get("class") == "gRef":
                    idx = peer_term.findtext("dco/paramIdx")
                    if idx and idx.isdigit():
                        grefs[(idx, owner.get("uid", ""))] = signal_uid
                if owner.get("class") == "sRN":
                    uri = decode_uri(peer_term.findtext("dco/ConstValue"))
                    if uri:
                        uris[uri] = signal_uid
        if len(grefs) == 1 and len(uris) == 1:
            (param_idx, gref_uid), value_signal = next(iter(grefs.items()))
            uri, uri_signal = next(iter(uris.items()))
            rows.append({
                "param_idx": param_idx,
                "uri": uri,
                "shared_variable_class": node.get("class", ""),
                "node_uid": node.get("uid", ""),
                "diagram_uid": parent_diag(node, parents),
                "gref_uid": gref_uid,
                "value_signal_uid": value_signal,
                "uri_signal_uid": uri_signal,
            })
        elif grefs or uris:
            skipped.append((node.get("uid"), len(grefs), len(uris)))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        fieldnames = ["param_idx", "uri", "shared_variable_class", "node_uid", "diagram_uid", "gref_uid", "value_signal_uid", "uri_signal_uid"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    mapping = defaultdict(set)
    for row in rows:
        mapping[int(row["param_idx"])].add(row["uri"])
    print(f"verified one-to-one call sites: {len(rows)}; distinct paramIdx: {len(mapping)}; ambiguous nodes skipped: {len(skipped)}")
    for idx, uris in sorted(mapping.items()):
        print(f"{idx:2d}: {', '.join(sorted(uris))}")
    conflicts = {idx: uris for idx, uris in mapping.items() if len(uris) > 1}
    print(f"paramIdx values with conflicting URIs: {len(conflicts)}")
    if skipped:
        print("skipped examples:", skipped[:10])


if __name__ == "__main__":
    main()
