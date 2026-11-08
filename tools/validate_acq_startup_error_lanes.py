"""Whole-source census of three distinct returning initialization error lanes.

Reuses independently checked parent/helper facets. Adds all sequence-local
port occurrences, including unused ports, across every original root diagram.
No VI execution, saved/native branch reconciliation or driver result inferred.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_initializer_caller_frame import (
    validate_caller,
    validate_disabled_parent,
    validate_discovery,
    validate_fallback,
    validate_parents,
)
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import checked_trees, heap_type
from validate_acq_startup_io import validate_trees as validate_io
from validate_acq_startup_postinit import validate_trees as validate_postinit
from validate_acq_startup_publication import validate_trees as validate_publication

# Local UID, heap type, defining frame index, six ordered frame ports,
# complete nonempty wire occurrences (diagram UID and ALL peers).
ERROR_LANES = (
    (
        "1063",
        2630,
        "01",
        ("20369", "1131", "1195", "1366", "21525", "7587"),
        (("227", ("562", "1131")), ("133", ("1195", "2639"))),
    ),
    (
        "306",
        2631,
        "02",
        ("20372", "1319", "1320", "1371", "21528", "7590"),
        (("133", ("2112", "1320")), ("1356", ("1371", "76738"))),
    ),
    (
        "25655",
        2632,
        "02",
        ("25686", "25687", "25688", "25689", "25690", "25691"),
        (("133", ("1309", "2107", "25688")), ("7580", ("25691", "28003"))),
    ),
)


def validate_error_lanes(root, metadata):
    sequence = unique(root, "sequence", "201")
    require(
        [n.get("uid") for n in sequence.findall("seqLocDCOList/*")]
        == [row[0] for row in ERROR_LANES],
        "initialization error-lane population/order changed",
    )
    require(
        [n.get("uid") for n in sequence.findall("diagramList/*")]
        == ["20362", "227", "133", "1356", "21518", "7580"],
        "error-lane ordered frame mapping changed",
    )
    diagrams = [n for n in root.iter() if n.get("class") == "diag"]
    for uid, heap, defining, ports, expected in ERROR_LANES:
        node = unique(root, "sLoc", uid)
        require(
            node in sequence.findall("seqLocDCOList/*")
            and node.findtext("objFlags") == "1"
            and node.findtext("diagDefined") == defining
            and node.findtext("typeDesc") == f"TypeID({heap})"
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
            f"error lane {uid} definition/type/ports changed",
        )
        descriptor, flat = heap_type(metadata, heap)
        require(
            descriptor.get("Type") == "Cluster"
            and [
                (
                    flat[int(t.get("TypeID"))].get("Type"),
                    flat[int(t.get("TypeID"))].get("Label"),
                )
                for t in descriptor.findall("TypeDesc")
            ]
            == [("Boolean", "status"), ("NumInt32", "code"), ("String", "source")],
            f"error lane {uid} cluster field order changed",
        )
        occurrences = []
        for diagram in diagrams:
            for signal in diagram.findall("signalList/*"):
                peers = tuple(
                    sorted(t.get("uid") for t in signal.findall("termList/*"))
                )
                if set(ports).intersection(peers):
                    occurrences.append((diagram.get("uid"), peers))
        require(
            sorted(occurrences) == sorted((d, tuple(sorted(p))) for d, p in expected),
            f"error lane {uid} whole-source wire census changed",
        )
    return "3 typed error lanes, 18 ports, 6 exact whole-source wire occurrences"


def validate_trees(root, metadata):
    results = [validate_error_lanes(root, metadata)]
    for proof in (
        validate_caller,
        validate_fallback,
        validate_parents,
        validate_disabled_parent,
        validate_discovery,
        validate_publication,
        validate_io,
        validate_postinit,
    ):
        results.append(proof(root, metadata))
    return tuple(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    for result in validate_trees(*checked_trees(parser.parse_args().archive)):
        print(result)


if __name__ == "__main__":
    main()
