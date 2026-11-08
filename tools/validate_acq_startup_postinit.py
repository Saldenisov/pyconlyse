"""Prove NI6220/TPG initialization caller, independent resets and UI disabling."""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import checked_trees, heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_startup_publication import cluster

LOCALS = (
    ("91986", "91996", 58, False),
    ("91287", "91297", 57, False),
    ("81412", "81422", 56, True),
    ("73174", "73184", 52, True),
    ("72477", "72487", 51, True),
    ("45441", "45666", 46, True),
    ("358", "7515", 45, True),
    ("30267", "30295", 44, True),
    ("31118", "31128", 36, True),
)
CALLS = (
    (
        "198078",
        "1_ACQ_INIT_NI6220.vi",
        (
            "198087",
            "198090",
            "198093",
            "198096",
            "198099",
            "198102",
            "198105",
            "198108",
        ),
    ),
    (
        "126853",
        "TPG 300.lvlib:Initialize.vi",
        (
            "126856",
            "126859",
            "126862",
            "126865",
            "126868",
            "126871",
            "126874",
            "126877",
            "126880",
            "126883",
            "126886",
            "126889",
        ),
    ),
    (
        "123241",
        "TPG 300.lvlib:Initialize.vi",
        (
            "123248",
            "123251",
            "123254",
            "123257",
            "123260",
            "123263",
            "123266",
            "123269",
            "123272",
            "123275",
            "123278",
            "123281",
        ),
    ),
    (
        "49978",
        "Simple Error Handler.vi",
        (
            "49986",
            "49992",
            "49996",
            "50007",
            "50016",
            "50021",
            "50026",
            "50029",
            "50033",
            "50038",
        ),
    ),
    (
        "10951",
        "Simple Error Handler.vi",
        (
            "43722",
            "43736",
            "43748",
            "43762",
            "43775",
            "43781",
            "43786",
            "43790",
            "43799",
            "43805",
        ),
    ),
    (
        "73977",
        "Simple Error Handler.vi",
        (
            "73984",
            "73987",
            "73990",
            "73993",
            "73996",
            "73999",
            "74002",
            "74005",
            "74008",
            "74011",
        ),
    ),
)
# UI node, saved attached DDO identity, data port, data heap type, five ports.
PROPERTIES = (
    ("45759", "79089", "45774", 2432, ("45762", "45765", "45768", "45771", "45774")),
    ("45718", "40722", "45733", 2439, ("45721", "45724", "45727", "45730", "45733")),
    ("45693", "70708", "45708", 2446, ("45696", "45699", "45702", "45705", "45708")),
    ("45668", "8957", "45683", 2453, ("45671", "45674", "45677", "45680", "45683")),
    ("45440", "11783", "45604", 2460, ("45455", "45462", "45506", "45557", "45604")),
)
WIRES = (
    ("91297", "198099"),
    ("91996", "198093"),
    ("198102", "81422"),
    ("126865", "73184"),
    ("123257", "72487"),
    ("198108", "50038"),
    ("126856", "43805"),
    ("123248", "74011"),
    ("126897", "126889"),
    ("126917", "126886"),
    ("124689", "123278"),
    ("123289", "123281"),
    ("45782", "45666"),
    ("45745", "45604", "45683", "45708", "45733", "45774"),
    ("18008", "7515"),
    ("25379", "30295"),
    ("28919", "31128"),
)
LITERALS = {
    "25379": (2466, "00" * 78),
    "28919": (2545, "00" * 30),
    "18008": (2576, "0000"),
    "45745": (2578, "02"),
    "45782": (2580, "0000"),
    "123289": (2582, "00000004434F4D32"),
    "124689": (2585, "0004"),
    "126897": (2587, "00000004434F4D31"),
    "126917": (2590, "0004"),
}
ENUM_LABELS = ["Enabled", "Disabled", "Disabled and Grayed Out"]


def validate_trees(bd, metadata):
    require(
        unique(bd, "sequence", "24603").find("diagramList")[3].get("uid") == "33052",
        "post-initialization frame order changed",
    )
    frame = unique(bd, "diag", "33052")
    operations(
        frame,
        [("iUse", r[0]) for r in CALLS]
        + [("gRef", r[0]) for r in LOCALS]
        + [("propNode", r[0]) for r in PROPERTIES]
        + [(None, uid) for uid in LITERALS]
        + [("label", "44446"), ("label", "45061")],
        "post-initialization frame",
    )
    exact_wires(frame, WIRES, "post-initialization frame")
    names = call_names(metadata)
    for uid, name, ports in CALLS:
        node = unique(frame, "iUse", uid)
        require(
            names.get(uid) == name
            and [t.get("uid") for t in node.findall("termList/*")] == list(ports),
            "post-initialization qualified callee/connector changed",
        )
        for slot, port in enumerate(ports):
            public_term(node, port, slot)
    for uid, port, index, write in LOCALS:
        local(frame, uid, port, index, write)
    for uid, (heap, value) in LITERALS.items():
        require(
            constant(frame, uid) == value
            and frame.findtext(f"nodeList/*/termList/*[@uid='{uid}']/dco/typeDesc")
            == f"TypeID({heap})",
            "post-initialization constant value/type changed",
        )
    cluster(metadata, 2466, 77, "Boolean", "EPS")
    cluster(metadata, 2545, 29, "Boolean", "DPS")
    for heap in (2576, 2580):
        require(
            heap_type(metadata, heap)[0].get("Type") == "Boolean",
            "startup reset literal is not Boolean",
        )
    for heap, kind in (
        (2363, "NumFloat64"),
        (2364, "NumInt32"),
        (2585, "NumUInt16"),
        (2590, "NumUInt16"),
    ):
        require(
            heap_type(metadata, heap)[0].get("Type") == kind,
            "NI6220 clock/TPG baud selector type changed",
        )
    enum, _ = heap_type(metadata, 2578)
    require(
        enum.get("Type") == "UnitUInt8"
        and [n.text for n in enum.findall("EnumLabel")] == ENUM_LABELS,
        "DisabledEnum literal interpretation changed",
    )
    for uid, ddo, port, heap, ports in PROPERTIES:
        node = unique(frame, "propNode", uid)
        require(
            [t.get("uid") for t in node.findall("termList/*")] == list(ports)
            and node.find("ddo").get("uid") == ddo
            and len(node.find("dcoList")) == 1,
            "UI property target/terminal inventory changed",
        )
        item = node.find(f"termList/*[@uid='{port}']/dco")
        require(
            item.findtext("typeDesc") == f"TypeID({heap})"
            and len(item.find("propList")) == 1
            and item.findtext("propList/*/objFlags") == "4096"
            and item.findtext("propList/*/PropItemName") == '"DisabledEnum"'
            and item.findtext("propList/*/PropItemCode") == "104013885",
            "UI property name/write direction changed",
        )
        descriptor, _ = heap_type(metadata, heap)
        require(
            descriptor.get("Type") == "UnitUInt8"
            and [n.text for n in descriptor.findall("EnumLabel")] == ENUM_LABELS,
            "UI DisabledEnum property interpretation changed",
        )
    return (
        "Post-init: 31 operations, 17 nets; three independent error handlers; "
        "ungated resets and UI disable"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(validate_trees(*checked_trees(parser.parse_args().archive)))


if __name__ == "__main__":
    main()
