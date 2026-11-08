"""Read-only raw-wire audit of the NI6602 command path in ACQ ELYSE."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("--params", type=int, nargs="+", default=(21, 39))
    parser.add_argument("--nodes", type=int, nargs="+", default=(22699, 20986, 29080, 15887, 26175, 22328, 22884, 21053, 21122, 23634))
    args = parser.parse_args()
    root = ET.parse(args.bdhb_xml).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    owners = {}
    for node in root.iter():
        if not node.get("class") or node.get("class") == "signal":
            continue
        terms = node.find("termList")
        if terms is None:
            continue
        for term in terms:
            if term.get("class") == "term":
                owners[term.get("uid")] = node

    def diag_uid(node: ET.Element) -> str:
        node = parents.get(node)
        while node is not None and node.get("class") != "diag":
            node = parents.get(node)
        return node.get("uid", "") if node is not None else ""

    def fmt(uid: str) -> str:
        node = owners.get(uid)
        if node is None:
            return uid
        tag = node.get("class", "")
        detail = ""
        if tag == "gRef":
            detail = ":param" + node.findtext("termList/*/dco/paramIdx", default="?")
        elif tag == "nMux":
            term = node.find(f"termList/*[@uid='{uid}']")
            detail = ":field" + (term.findtext("dco/i", default="?") if term is not None else "?")
        elif tag == "iUse":
            term = node.find(f"termList/*[@uid='{uid}']")
            detail = ":input" + (term.findtext("dco/paramIdx", default="0") if term is not None else "?")
        return f"{uid}:{tag}:{node.get('uid')}{detail}"

    term_to_signals: dict[str, list[ET.Element]] = {}
    for signal in root.iter():
        if signal.get("class") != "signal":
            continue
        terms = signal.find("termList")
        if terms is None:
            continue
        for term in terms:
            term_to_signals.setdefault(term.get("uid", ""), []).append(signal)

    for param in args.params:
        print(f"gRef paramIdx {param}")
        for node in root.iter():
            if node.get("class") != "gRef" or node.findtext("termList/*/dco/paramIdx") != str(param):
                continue
            term = node.find("termList/*")
            if term is None:
                continue
            uid = term.get("uid", "")
            for signal in term_to_signals.get(uid, []):
                peers = [fmt(t.get("uid", "")) for t in signal.findall("termList/*")]
                print(" ", "diag", diag_uid(node), "signal", signal.get("uid"), " ".join(peers))

    for uid in args.nodes:
        node = root.find(f".//*[@class][@uid='{uid}']")
        if node is None:
            continue
        print("node", uid, node.get("class"), "diag", diag_uid(node))
        for term in node.findall("termList/*"):
            term_uid = term.get("uid", "")
            for signal in term_to_signals.get(term_uid, []):
                print("  ", "signal", signal.get("uid"), " ".join(fmt(t.get("uid", "")) for t in signal.findall("termList/*")))


if __name__ == "__main__":
    main()
