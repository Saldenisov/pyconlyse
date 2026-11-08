"""Prove runtime frame-0 wires and saved cluster shapes, without VI execution."""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_publication import local, operations

# UID, output port/type, input port/type, cluster size/element type, local field.
CONVERSIONS = (
    ("7611", "7617", 3020, "7621", 3021, 10, "NumFloat64", 12),
    ("8677", "8679", 3022, "8682", 3023, 10, "NumFloat64", 11),
    ("8669", "8671", 3024, "8674", 3025, 10, "NumFloat64", 10),
    ("7588", "7597", 3026, "7602", 3027, 10, "NumFloat64", 9),
    ("8127", "8133", 3038, "8136", 3039, 40, "Boolean", 13),
    ("8025", "8031", 3040, "8034", 3041, 32, "Boolean", 15),
    ("7937", "7943", 3042, "7946", 3043, 40, "Boolean", 17),
    ("7836", "7842", 3044, "7845", 3045, 56, "Boolean", 14),
    ("7748", "7750", 3046, "7753", 3047, 64, "Boolean", 16),
    ("7655", "7739", 3048, "7742", 3049, 56, "Boolean", 18),
    ("7599", "7605", 3052, "7608", 3053, 64, "NumFloat64", 20),
    ("7485", "7491", 3054, "7494", 3055, 64, "NumFloat64", 19),
)
LOCALS = (
    ("1828", "1878", 25, False),
    ("180", "1342", 22, False),
    ("2494", "2497", 12, False),
    ("2486", "2489", 11, False),
    ("2448", "2477", 10, False),
    ("2388", "2443", 9, False),
    ("2370", "2373", 14, True),
    ("2352", "2355", 16, True),
    ("2336", "2339", 18, True),
    ("2378", "2381", 13, False),
    ("2362", "2365", 15, False),
    ("2344", "2347", 17, False),
    ("2326", "2331", 20, True),
    ("2234", "2318", 19, True),
    ("1725", "1728", 23, False),
    ("1628", "1681", 24, False),
)
WIRES = (
    ("496", "46084"),
    ("715", "484"),
    ("652", "700"),
    ("1878", "454"),
    ("1342", "703"),
    ("7617", "478"),
    ("8679", "472"),
    ("8671", "466"),
    ("7597", "298"),
    ("2497", "7621"),
    ("2489", "8682"),
    ("2477", "8674"),
    ("2443", "7602"),
    ("7842", "2373"),
    ("7750", "2355"),
    ("7739", "2339"),
    ("712", "7845"),
    ("709", "7753"),
    ("706", "7742"),
    ("2381", "8136"),
    ("2365", "8034"),
    ("2347", "7946"),
    ("7943", "691"),
    ("8031", "694"),
    ("8133", "697"),
    ("7605", "2331"),
    ("7491", "2318"),
    ("8081", "679"),
    ("1681", "682"),
    ("1728", "685"),
    ("658", "7608"),
    ("661", "7494"),
)


def checked_trees(path):
    bd = checked_root(path)
    with ZipFile(path) as archive:
        main = ET.fromstring(archive.read("vi.xml"))
    return bd, main


def heap_type(main, heap_id):
    """Heap IDs are one-based within DTHP slice, not VCTP top-level IDs.

    Nested VCTP TypeDesc TypeID references are zero-based flat indices.
    The saved comments independently agree with this structural mapping.
    """
    section = main.find("DTHP/Section/TypeDescSlice")
    require(section is not None, "heap type slice absent")
    require(1 <= heap_id <= int(section.get("Count")), "heap type outside slice")
    consolidated = int(section.get("IndexShift")) + heap_id - 1
    vctp = main.find("VCTP/Section")
    matches = [n for n in vctp.find("TopLevel") if n.get("Index") == str(consolidated)]
    require(len(matches) == 1, "heap-to-consolidated type mapping changed")
    flat = vctp.findall("TypeDesc")
    return flat[int(matches[0].get("FlatTypeID"))], flat


def validate_conversions(frame, main, conversions):
    """Shared proof only; each caller pins its own nodes, nets and type IDs."""
    for position, row in enumerate(conversions):
        uid, out, out_type, incoming, in_type, count, kind, _ = row
        to_array = position < 7
        primitive(frame, uid, 1169 if to_array else 1168, (out, incoming))
        node = unique(frame, "prim", uid)
        require(
            node.findtext("primIndex") == ("157" if to_array else "156"),
            "conversion primitive index changed",
        )
        for term, type_id in zip(node.findall("termList/*"), (out_type, in_type)):
            match = re.fullmatch(r"TypeID\((\d+)\)", term.findtext("dco/typeDesc", ""))
            require(
                match is not None and int(match[1]) == type_id,
                "conversion terminal type changed",
            )
        cluster, flat = heap_type(main, in_type if to_array else out_type)
        array, _ = heap_type(main, out_type if to_array else in_type)
        members = cluster.findall("TypeDesc")
        require(
            cluster.get("Type") == "Cluster" and len(members) == count,
            "saved cluster size changed",
        )
        require(
            all(flat[int(n.get("TypeID"))].get("Type") == kind for n in members),
            "saved cluster element type changed",
        )
        require(
            array.get("Type") == ("SubArray" if to_array else "Array")
            and len(array.findall("Dimension")) == 1
            and len(array.findall("TypeDesc")) == 1
            and flat[int(array.find("TypeDesc").get("TypeID"))].get("Type") == kind,
            "saved array rank/element type changed",
        )


def validate_trees(bd, main):
    sequence = unique(bd, "sequence", "1244")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")]
        == ["7386", "7392", "2010", "8695", "1283", "18156", "1619"]
        and all(
            len(sequence.find(tag)) == 0
            for tag in ("termList", "tunnelList", "seqLocDCOList")
        ),
        "runtime sequence order or inter-frame connection changed",
    )
    frame = unique(bd, "diag", "7386")
    expected = [("iUse", u) for u in ("11701", "278", "686", "647")]
    expected += [("gRef", r[0]) for r in LOCALS]
    expected += [("prim", r[0]) for r in CONVERSIONS] + [(None, "8081")]
    operations(frame, expected, "runtime I/O frame")
    exact_wires(frame, WIRES, "runtime I/O frame")
    require(constant(frame, "8081") == "000003E8", "sample count changed")
    for uid, port, index, write in LOCALS:
        local(frame, uid, port, index, write)
    validate_conversions(frame, main, CONVERSIONS)
    for uid, short_count in (
        ("647", "38"),
        ("686", "48"),
        ("278", "50"),
        ("11701", "52"),
    ):
        require(
            unique(frame, "iUse", uid).findtext("shortCount") == short_count,
            "runtime helper identity changed",
        )
    return (
        "32 nets, 33 operations, 12 saved conversion shapes; "
        "short-array padding remains open"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(validate_trees(*checked_trees(args.archive)))


if __name__ == "__main__":
    main()
