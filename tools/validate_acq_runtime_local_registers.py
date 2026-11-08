"""Whole-root gRef census for ACTION, dispatcher index and WCM memory.

This is a local-reference facet, not a complete primary-terminal/property/
VI Server consumer audit or behavioral closure of its containing diagrams.
"""

import argparse
from pathlib import Path

from validate_acq_final_cleanup import constant
from validate_acq_modulator_start_event_guards import require
from validate_acq_runtime_io_frame import heap_type
from validate_acq_vam_status import checked_vam

# local node, port, containing diagram, literal port, raw Boolean literal.
ACTION = (
    ("19042", "19100", "9471", "85221", "0000"),
    ("10440", "10444", "10221", "10256", "01"),
    ("84158", "84168", "18796", "9188", "01"),
    ("16177", "16339", "7963", "8484", "01"),
    ("34760", "34769", "34617", "34660", "01"),
    ("26756", "26765", "26598", "26638", "01"),
    ("23357", "23360", "23304", "23320", "01"),
    ("26296", "26299", "26246", "26262", "01"),
    ("31106", "31109", "31017", "31064", "01"),
    ("23740", "23743", "23518", "23694", "01"),
    ("33747", "33750", "33697", "33713", "01"),
    ("38124", "38127", "38074", "38090", "01"),
    ("24495", "24751", "24338", "24380", "01"),
    ("36073", "36076", "36023", "36039", "01"),
    ("40212", "40215", "40162", "40178", "01"),
    ("30438", "30465", "30270", "30330", "01"),
    ("42608", "42611", "42539", "42555", "01"),
    ("34383", "34386", "34284", "34314", "01"),
    ("43763", "43766", "43712", "43728", "01"),
    ("54045", "54048", "53995", "54011", "01"),
    ("31847", "31851", "31696", "31749", "01"),
    ("33124", "33130", "32931", "33016", "01"),
    ("45254", "45257", "45203", "45220", "01"),
    ("40818", "40821", "40802", "40808", "01"),
    ("38889", "38892", "38812", "38818", "01"),
    ("47687", "47690", "51962", "47677", "01"),
)
OTHER = {
    43: (("13820", "22933", "22247", "0"),),
    65: (
        ("50544", "50572", "45510", "0"),
        ("47026", "47036", "206856", "0"),
        ("48168", "48174", "47080", "5"),
    ),
    68: (
        ("100549", "100552", "100537", "0"),
        ("100543", "100546", "100537", "1"),
        ("101615", "101618", "100569", "0"),
        ("100508", "100515", "45510", "1"),
        ("86041", "86048", "81862", "0"),
        ("85375", "85391", "81862", "1"),
        ("91670", "91677", "81868", "0"),
        ("74934", "74944", "206856", "1"),
    ),
}


def validate_registers(root, meta):
    parents = {child: node for node in root.iter() for child in node}
    expected = {
        35: tuple((uid, port, diag, "0") for uid, port, diag, *_ in ACTION),
        **OTHER,
    }
    kinds = {35: "Boolean", 43: "NumInt32", 65: "Array", 68: "NumUInt32"}
    frames = {}
    for bank, sites in expected.items():
        actual = []
        for node in root.findall(".//*[@class='gRef']"):
            if node.findtext("termList/*/dco/paramIdx") != str(bank):
                continue
            terms = node.findall("termList/*")
            require(len(terms) == 1, "runtime register local terminal count changed")
            term = terms[0]
            frame = parents[node]
            while frame.get("class") != "diag":
                frame = parents[frame]
            frames[frame.get("uid")] = frame
            actual.append(
                (
                    node.get("uid"),
                    term.get("uid"),
                    frame.get("uid"),
                    term.findtext("dco/objFlags", "0"),
                )
            )
            typ, _ = heap_type(meta, int(term.findtext("dco/typeDesc")[7:-1]))
            require(
                typ.get("Type") == kinds[bank], "runtime register saved type changed"
            )
        require(
            len(actual) == len(sites) and set(actual) == set(sites),
            "whole-root register read/write census changed",
        )
    for _, port, uid, literal, value in ACTION:
        frame = frames[uid]
        require(constant(frame, literal) == value, "ACTION literal changed")
        peers = [
            set(t.get("uid") for t in signal.findall("termList/*"))
            for signal in frame.findall("signalList/*")
        ]
        require(
            sum({port, literal} <= group for group in peers) == 1,
            "ACTION direct literal assignment wire changed",
        )
    return (
        "PASS: 38 root local references; ACTION26 writes/zero reads; "
        "WCM initialization gRef writers absent"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_registers(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
