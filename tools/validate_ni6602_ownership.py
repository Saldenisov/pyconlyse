"""Assert source-terminal anchors for saved SUP/ACQ NI6602 routing.

Read-only. This is intentionally tied to the two saved source copies and
their raw XML UIDs; it is not a generic LabVIEW equivalence checker.
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def root_and_signals(path: Path) -> tuple[ET.Element, dict[str, list[frozenset[str]]]]:
    root = ET.parse(path).getroot()
    signals: dict[str, list[frozenset[str]]] = {}
    for diagram in root.iter():
        if diagram.get("class") != "diag":
            continue
        signal_list = diagram.find("signalList")
        if signal_list is None:
            continue
        signals[diagram.get("uid", "")] = [
            frozenset(term.get("uid", "") for term in signal.findall("termList/*"))
            for signal in signal_list
        ]
    return root, signals


def edge(signals: dict[str, list[frozenset[str]]], diagram: str, *terms: str) -> None:
    expected = set(terms)
    if not any(expected <= signal for signal in signals.get(diagram, [])):
        raise AssertionError(f"missing raw signal in diagram {diagram}: {terms}")


def node(root: ET.Element, uid: str, cls: str) -> ET.Element:
    found = root.find(f".//*[@class='{cls}'][@uid='{uid}']")
    if found is None:
        raise AssertionError(f"missing {cls} {uid}")
    return found


def gref(root: ET.Element, uid: str, param: int) -> None:
    actual = node(root, uid, "gRef").findtext("termList/*/dco/paramIdx")
    if actual != str(param):
        raise AssertionError((uid, actual, param))


def constant(root: ET.Element, uid: str, raw_hex: str) -> None:
    matches = [
        term.findtext("dco/ConstValue")
        for term in root.iter()
        if term.get("class") == "term" and term.get("uid") == uid
    ]
    if raw_hex not in matches:
        raise AssertionError((uid, raw_hex, matches))


def validate(acq_path: Path, sup_path: Path) -> None:
    acq, acq_edges = root_and_signals(acq_path)
    sup, sup_edges = root_and_signals(sup_path)

    # Acquisition init output 1 -> local task cluster; PSP-backed timing bank.
    gref(acq, "1053", 21)
    gref(acq, "6", 21)
    gref(acq, "44855", 39)
    edge(acq_edges, "227", "601", "1156")
    edge(acq_edges, "22247", "1487", "28569")
    edge(acq_edges, "22247", "44864", "29998")
    edge(acq_edges, "22247", "24075", "28879")
    assert node(acq, "24075", "term").findtext("dco/i") == "32"
    constant(acq, "27138", "4000000000000000")  # divide by 2
    constant(acq, "23152", "4000000000000000")  # multiply by 2
    for terms in (
        ("28856", "23012"),  # selector -> decrement
        ("23009", "26203"),  # decrement -> quotient
        ("26193", "21193"),  # quotient -> task index
        ("26193", "22423"),  # quotient -> multiply
        ("22384", "31347"), # 2q -> timing index
        ("22890", "21088"), # 2q+1 -> timing index
        ("21189", "23671"), # task -> writer input 7
        ("31344", "23677"), # delay -> writer input 9
        ("21083", "23680"), # width -> writer input 10
    ):
        edge(acq_edges, "23641", *terms)

    # Supervision init output 1 -> local Dev1 task cluster; >16 dispatch.
    gref(sup, "49689", 210)
    gref(sup, "57747", 210)
    gref(sup, "49826", 163)
    gref(sup, "56477", 170)
    edge(sup_edges, "23159", "66168", "49714")
    edge(sup_edges, "49696", "57754", "68299")
    edge(sup_edges, "49696", "51058", "76116")
    edge(sup_edges, "49696", "58826", "61165")
    assert node(sup, "58826", "term").findtext("dco/i") == "32"
    constant(sup, "59685", "4031000000000000")  # 17
    constant(sup, "66429", "4000000000000000")  # 2
    constant(sup, "53931", "4030000000000000")  # 16
    for terms in (
        ("55171", "58003"),  # selector -> n-17
        ("57997", "62861"),  # n-17 -> quotient
        ("62851", "53311"),  # quotient -> local task index
        ("53308", "67620"),  # task -> writer input 7
        ("51067", "54783"),  # 16+2q -> timing index
        ("51263", "68154"),  # 17+2q -> timing index
        ("54780", "67626"),  # delay -> writer input 9
        ("68149", "67629"),  # width -> writer input 10
    ):
        edge(sup_edges, "55043", *terms)
    print("PASS: saved raw NI6602 split ownership, task refs, selectors, and timing-pair wires")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acq_bdhb_xml", type=Path)
    parser.add_argument("sup_bdhb_xml", type=Path)
    args = parser.parse_args()
    validate(args.acq_bdhb_xml, args.sup_bdhb_xml)


if __name__ == "__main__":
    main()
