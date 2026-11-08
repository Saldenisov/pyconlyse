"""Check all20 stop-related gRefs and11 literal writers in the original VI.

Absence of a gRef initialization reset is not absence of UI/terminal/VI Server
writes. No loaded default or physical shutdown result is inferred.
"""

from __future__ import annotations

import sys
from pathlib import Path

from validate_acq_final_cleanup import constant
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_vam_status import checked_vam

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import STOP_RESETS
from DeviceServers.control.elyse_acq.vi_simulation.stop_schedule import (
    ERROR_SITES,
    RUNTIME_LOOPS,
)

# gRef, terminal, containing diagram, local bank, read/write, top-level frame.
SITES = (
    ("45441", "45666", "33052", 46, True, "188"),
    ("358", "7515", "33052", 45, True, "188"),
    ("47557", "47561", "47487", 30, False, "367"),
    ("60120", "60127", "59492", 30, False, "367"),
    ("43040", "43045", "42989", 45, True, "367"),
    ("43027", "43033", "42989", 30, True, "367"),
    ("21059", "21066", "20609", 30, False, "367"),
    ("1756", "1806", "211", 30, False, "367"),
    ("50019", "50022", "50030", 45, True, "367"),
    ("50011", "50014", "50030", 30, True, "367"),
    ("1888", "7921", "110", 30, False, "367"),
    ("85095", "85111", "40224", 30, True, "367"),
    ("68231", "68238", "40224", 45, True, "367"),
    ("43367", "43377", "41713", 46, False, "41058"),
    ("118957", "118967", "42610", 47, False, "41058"),
    ("115330", "115354", "42610", 46, False, "41058"),
    ("43536", "43559", "64826", 47, True, "41058"),
    ("18163", "29020", "64826", 46, True, "41058"),
    ("7387", "7927", "41058", 45, False, "41058"),
    ("12978", "12987", "246", 30, True, "246"),
)
WRITERS = {
    "45441": ("45782", False),
    "358": ("18008", False),
    "43040": ("43005", True),
    "43027": ("43005", True),
    "50019": ("49997", True),
    "50011": ("49997", True),
    "85095": ("44039", False),
    "68231": ("44039", False),
    "43536": ("46100", False),
    "18163": ("42334", True),
    "12978": ("13250", False),
}
LABELS = {30: "stop", 45: "TCP ED", 46: "stop urgence", 47: "Arrêt général"}
LOOP_TESTS = (
    ("47483", "47557", "47561", "47497", "47496"),
    ("59483", "60120", "60127", "59503", "59505"),
    ("20601", "21059", "21066", "20619", "20621"),
    ("203", "1756", "1806", "221", "223"),
    ("102", "1888", "7921", "120", "122"),
)


def validate_memory(root, metadata):
    parents = {child: node for node in root.iter() for child in node}
    actual = []
    for node in root.findall(".//*[@class='gRef']"):
        terms = node.findall("termList/*")
        bank = int(terms[0].findtext("dco/paramIdx", "0"))
        if bank not in LABELS:
            continue
        require(len(terms) == 1, "stop local terminal population changed")
        term = terms[0]
        ancestors = []
        frame = parents[node]
        while frame in parents:
            if frame.get("class") == "diag":
                ancestors.append(frame)
            frame = parents[frame]
        require(len(ancestors) >= 2, "stop local containing scope absent")
        flags = term.findtext("objFlags")
        require(flags in ("36864", "4096"), "stop local direction changed")
        write = flags == "36864"
        descriptor, _ = heap_type(metadata, int(term.findtext("dco/typeDesc")[7:-1]))
        require(
            term.findtext("dco/objFlags", "0") == ("0" if write else "1")
            and descriptor.get("Type") == "Boolean"
            and descriptor.get("Label") == LABELS[bank],
            "stop local type/label/consumer direction changed",
        )
        row = (
            node.get("uid"),
            term.get("uid"),
            ancestors[0].get("uid"),
            bank,
            write,
            ancestors[-2].get("uid"),
        )
        actual.append(row)
        if write:
            require(node.get("uid") in WRITERS, "unreviewed stop local writer")
            literal, value = WRITERS[node.get("uid")]
            require(
                constant(ancestors[0], literal) == ("01" if value else "0000"),
                "stop literal value changed",
            )
            literal_dco = ancestors[0].find(
                f"nodeList/*/termList/*[@uid='{literal}']/dco"
            )
            literal_type, _ = heap_type(
                metadata, int(literal_dco.findtext("typeDesc")[7:-1])
            )
            require(
                literal_type.get("Type") == "Boolean",
                "stop assignment literal is not Boolean",
            )
            nets = [
                set(t.get("uid") for t in s.findall("termList/*"))
                for s in ancestors[0].findall("signalList/*")
                if any(t.get("uid") == term.get("uid") for t in s.findall("termList/*"))
            ]
            require(
                len(nets) == 1 and {literal, term.get("uid")} <= nets[0],
                "stop literal assignment wire changed",
            )
    require(
        len(actual) == len(SITES) and set(actual) == set(SITES),
        "whole-root stop local census changed",
    )
    require(
        tuple(row[0] for row in LOOP_TESTS) == RUNTIME_LOOPS,
        "Python runtime-loop population/order changed",
    )
    for owner, reader, port, test, test_port in LOOP_TESTS:
        loop = unique(root, "whileLoop", owner)
        node = unique(root, "gRef", reader)
        conditional = unique(root, "lTst", test)
        require(
            node in loop.iter()
            and conditional in loop.iter()
            and conditional.findtext("objFlags") == "65537",
            "runtime stop condition owner/polarity changed",
        )
        frame = unique(root, "diag", next(r[2] for r in actual if r[0] == reader))
        nets = [
            set(t.get("uid") for t in s.findall("termList/*"))
            for s in frame.findall("signalList/*")
        ]
        require(
            sum({port, test_port} <= group for group in nets) == 1,
            "runtime condition snapshot wire changed",
        )
    for stage, top, nodes in (
        ("post_init", "188", ("358", "45441")),
        ("controlled_complete", "41058", ("18163", "43536")),
        ("final_cleanup", "246", ("12978",)),
    ):
        decoded = tuple(
            (next(r[3] for r in actual if r[0] == node), WRITERS[node][1])
            for node in nodes
        )
        require(decoded == STOP_RESETS[stage], "Python stop reset projection drifted")
        require(
            all(next(r[5] for r in actual if r[0] == n) == top for n in nodes),
            "stop reset top-level scope changed",
        )
    for selector, (owner, writes) in ERROR_SITES.items():
        require(owner in RUNTIME_LOOPS, "Python error-owner loop changed")
        case = unique(root, "select", selector)
        loop = unique(root, "whileLoop", owner)
        require(case in loop.iter(), "error selector moved outside its owner loop")
        for node, bank, value in writes:
            require(
                node in WRITERS
                and WRITERS[node][1] is value
                and next(r[3] for r in actual if r[0] == node) == bank
                and unique(root, "gRef", node) in case.iter(),
                "Python runtime fault assignment drifted",
            )
    return {
        "stop_local_references": 20,
        "literal_writers": 11,
        "init_gref_resets": ((45, False), (46, False)),
        "init_gref_reset_30_or_47": False,
        "loaded_initial_values_proven": False,
        "indirect_writers_excluded": False,
    }


if __name__ == "__main__":
    print(
        validate_memory(
            *checked_vam(
                REPO
                / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
            )
        )
    )
