"""Check initial AI/DIO/AO caller graph independently of the runtime copy."""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import checked_trees, validate_conversions
from validate_acq_runtime_publication import local, operations

CONVERSIONS = (
    ("19659", "19661", 2274, "19664", 2275, 10, "NumFloat64", 12),
    ("19651", "19653", 2276, "19656", 2277, 10, "NumFloat64", 11),
    ("19643", "19645", 2278, "19648", 2279, 10, "NumFloat64", 10),
    ("19635", "19637", 2280, "19640", 2281, 10, "NumFloat64", 9),
    ("19547", "19549", 2292, "19552", 2293, 40, "Boolean", 13),
    ("19539", "19541", 2294, "19544", 2295, 32, "Boolean", 15),
    ("19531", "19533", 2296, "19536", 2297, 40, "Boolean", 17),
    ("19523", "19525", 2298, "19528", 2299, 56, "Boolean", 14),
    ("19515", "19517", 2300, "19520", 2301, 64, "Boolean", 16),
    ("19507", "19509", 2302, "19512", 2303, 56, "Boolean", 18),
    ("19483", "19485", 2306, "19488", 2307, 64, "NumFloat64", 20),
    ("19475", "19477", 2308, "19480", 2309, 64, "NumFloat64", 19),
)
LOCALS = (
    ("19675", "19678", 25, False),
    ("19667", "19670", 22, False),
    ("19627", "19630", 12, False),
    ("19619", "19622", 11, False),
    ("19611", "19614", 10, False),
    ("19603", "19606", 9, False),
    ("19595", "19598", 14, True),
    ("19587", "19590", 16, True),
    ("19579", "19582", 18, True),
    ("19571", "19574", 13, False),
    ("19563", "19566", 15, False),
    ("19555", "19558", 17, False),
    ("19499", "19502", 20, True),
    ("19491", "19494", 19, True),
    ("19467", "19470", 23, False),
    ("19459", "19462", 24, False),
)
WIRES = (
    ("19456", "16105"),
    ("19349", "19480"),
    ("19346", "19488"),
    ("19470", "19373"),
    ("19462", "19370"),
    ("19298", "19367"),
    ("19477", "19494"),
    ("19485", "19502"),
    ("19549", "19385"),
    ("19541", "19382"),
    ("19533", "19379"),
    ("19558", "19536"),
    ("19566", "19544"),
    ("19574", "19552"),
    ("19395", "19512"),
    ("19399", "19520"),
    ("19402", "19528"),
    ("19509", "19582"),
    ("19517", "19590"),
    ("19525", "19598"),
    ("19606", "19640"),
    ("19614", "19648"),
    ("19622", "19656"),
    ("19630", "19664"),
    ("19637", "19411"),
    ("19645", "19426"),
    ("19653", "19432"),
    ("19661", "19438"),
    ("19670", "19391"),
    ("19678", "19414"),
    ("19340", "19388"),
    ("19405", "19444"),
)
# Complete connector slots in source order, including unused outputs.
CALLS = (
    (
        "19337",
        "1_ACQ_READ_NI6071E.vi",
        38,
        (
            "19340",
            "19343",
            "19346",
            "19349",
            "19352",
            "19355",
            "19358",
            "19361",
            "19364",
            "19367",
            "19370",
            "19373",
        ),
    ),
    (
        "19376",
        "1_ACQ_RW_DIO96.vi",
        48,
        (
            "19379",
            "19382",
            "19385",
            "19388",
            "19391",
            "19395",
            "19399",
            "19402",
            "19405",
        ),
    ),
    (
        "19408",
        "1_ACQ_WRITE_NI6703.vi",
        50,
        (
            "19411",
            "19414",
            "19417",
            "19420",
            "19423",
            "19426",
            "19429",
            "19432",
            "19435",
            "19438",
            "19441",
            "19444",
            "19447",
            "19450",
            "19453",
            "19456",
        ),
    ),
    (
        "16070",
        "Simple Error Handler.vi",
        52,
        (
            "16077",
            "16080",
            "16083",
            "16086",
            "16089",
            "16092",
            "16095",
            "16098",
            "16102",
            "16105",
        ),
    ),
)


def validate_trees(bd, metadata):
    sequence = unique(bd, "sequence", "24603")
    require(
        sequence.find("diagramList")[2].get("uid") == "25990",
        "initial I/O frame order changed",
    )
    frame = unique(bd, "diag", "25990")
    operations(
        frame,
        [("iUse", r[0]) for r in CALLS]
        + [("gRef", r[0]) for r in LOCALS]
        + [("prim", r[0]) for r in CONVERSIONS]
        + [(None, "19298")],
        "initial I/O frame",
    )
    exact_wires(frame, WIRES, "initial I/O frame")
    require(constant(frame, "19298") == "000003E8", "initial sample count changed")
    for uid, port, index, write in LOCALS:
        local(frame, uid, port, index, write)
    validate_conversions(frame, metadata, CONVERSIONS)
    names = call_names(metadata)
    for uid, name, short, ports in CALLS:
        node = unique(frame, "iUse", uid)
        require(
            names.get(uid) == name
            and node.findtext("shortCount") == str(short)
            and [t.get("uid") for t in node.findall("termList/*")] == list(ports),
            "initial I/O helper identity or connector inventory changed",
        )
        for slot, port in enumerate(ports):
            public_term(node, port, slot)
    return "Initial I/O: 32 nets, 33 operations, 12 conversions; no pilot-error gate"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(validate_trees(*checked_trees(parser.parse_args().archive)))


if __name__ == "__main__":
    main()
