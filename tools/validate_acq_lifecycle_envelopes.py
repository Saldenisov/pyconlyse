"""Last root diagrams: sequence/join envelopes, stop I/O and property writes.

Typed graph qualification only. It does not resolve saved defaults, driver
success, UI property failures, loop scheduling or finite shutdown latency.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_controlled_stop import validate_stop
from validate_acq_final_cleanup import constant, exact_wires, validate_cleanup_tree
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type, validate_conversions
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

FRONT_PORTS = (
    "52017",
    "148176",
    "185697",
    "80696",
    "276504",
    "62060",
    "59732",
    "100283",
    "88594",
    "87129",
    "78947",
    "126843",
    "125422",
    "49244",
    "69774",
    "51644",
    "79103",
    "40751",
    "45857",
    "70725",
    "11778",
    "44215",
    "17796",
    "66774",
    "29891",
    "30645",
    "26360",
    "27125",
    "28643",
    "30499",
    "27888",
    "30641",
    "30534",
    "35016",
    "20312",
    "7724",
    "30937",
    "28030",
    "71105",
    "9101",
    "38962",
    "51110",
    "10073",
    "8128",
    "1734",
    "24685",
    "57801",
    "1150",
    "2537",
    "1614",
    "1050",
    "944",
    "1651",
    "280",
    "7379",
    "7264",
    "7149",
    "7034",
    "6914",
    "6526",
    "5994",
    "5678",
    "5074",
    "4686",
    "3827",
    "3208",
)
IO_CONVERSIONS = (
    ("55798", "55800", 7573, "55803", 7574, 10, "NumFloat64", 12),
    ("55790", "55792", 7575, "55795", 7576, 10, "NumFloat64", 11),
    ("55782", "55784", 7577, "55787", 7578, 10, "NumFloat64", 10),
    ("55774", "55776", 7579, "55779", 7580, 10, "NumFloat64", 9),
    ("55686", "55688", 7591, "55691", 7592, 40, "Boolean", 13),
    ("55678", "55680", 7593, "55683", 7594, 32, "Boolean", 15),
    ("55670", "55672", 7595, "55675", 7596, 40, "Boolean", 17),
    ("55662", "55664", 7597, "55667", 7598, 56, "Boolean", 14),
    ("55654", "55656", 7599, "55659", 7600, 64, "Boolean", 16),
    ("55646", "55648", 7601, "55651", 7602, 56, "Boolean", 18),
    ("55608", "55610", 7605, "55613", 7606, 64, "NumFloat64", 20),
    ("55600", "55602", 7607, "55605", 7608, 64, "NumFloat64", 19),
)
IO_LOCALS = (
    ("55814", "55817", 25, False),
    ("55806", "55809", 22, False),
    ("55766", "55769", 12, False),
    ("55758", "55761", 11, False),
    ("55750", "55753", 10, False),
    ("55742", "55745", 9, False),
    ("55734", "55737", 14, True),
    ("55726", "55729", 16, True),
    ("55718", "55721", 18, True),
    ("55710", "55713", 13, False),
    ("55702", "55705", 15, False),
    ("55694", "55697", 17, False),
    ("55638", "55641", 20, True),
    ("55630", "55633", 19, True),
    ("55592", "55595", 23, False),
    ("55584", "55587", 24, False),
)
IO_NETS = (
    ("48893", "116554"),
    ("55610", "55641", "48890"),
    ("46888", "46880"),
    ("43377", "41725"),
    ("55581", "55852"),
    ("55529", "55569"),
    ("55463", "55514"),
    ("55817", "55538"),
    ("55809", "55517"),
    ("55800", "55563"),
    ("55792", "55556"),
    ("55784", "55550"),
    ("55776", "55535"),
    ("55769", "55803"),
    ("55761", "55795"),
    ("55753", "55787"),
    ("55745", "55779"),
    ("55664", "55737"),
    ("55656", "55729"),
    ("55648", "55721"),
    ("55526", "55667"),
    ("55523", "55659"),
    ("55520", "55651"),
    ("55713", "55691"),
    ("55705", "55683"),
    ("55697", "55675"),
    ("55672", "55505"),
    ("55680", "55508"),
    ("55688", "55511"),
    ("55602", "55633"),
    ("55618", "55490"),
    ("55587", "55493"),
    ("55595", "55496"),
    ("55469", "55613"),
    ("55472", "55605"),
)
PROPERTY_ROWS = (
    ("14044", "79089", "178C", ("18872", "20842", "20871", "20902", "28680")),
    ("120269", "40722", "178D", ("120276", "120279", "120282", "120285", "120288")),
    ("119644", "70708", "178C", ("119651", "119654", "119657", "119660", "119663")),
    ("119018", "8957", "178C", ("119025", "119028", "119031", "119034", "119037")),
    ("117145", "11783", "178D", ("117152", "117155", "117158", "117161", "117164")),
)
DIAGRAMS = (
    "3",
    "135",
    "59492",
    "41058",
    "43496",
    "43502",
    "41713",
    "42610",
    "52989",
    "52995",
    "246",
    "1760",
)


def _kind(metadata, term):
    return heap_type(metadata, int(term.findtext("dco/typeDesc")[7:-1]))[0]


def _local(root, metadata, uid, port, bank, write, kind, label=None):
    local(root, uid, port, bank, write)
    desc = _kind(metadata, unique(root, "gRef", uid).find("termList/*"))
    require(
        desc.get("Type") == kind and (label is None or desc.get("Label") == label),
        "lifecycle local type/label changed",
    )


def _while(root, uid, body_uid, index, test):
    loop = unique(root, "whileLoop", uid)
    require(
        [f.get("uid") for f in loop.findall("diagramList/*")] == [body_uid]
        and all(
            not loop.findall(f"{tag}/*")
            for tag in ("srDCOList", "tunnelList", "termList")
        ),
        "lifecycle loop boundary changed",
    )
    body = unique(root, "diag", body_uid)
    for port, tag, klass, flags in (
        (index, "loopIndexDCO", "lCnt", None),
        (test, "loopTestDCO", "lTst", "65537"),
    ):
        dco = body.find(f"nodeList/*/termList/*[@uid='{port}']/dco")
        saved = loop.find(tag)
        require(
            saved.get("class") == klass
            and dco.get("uid") == saved.get("uid")
            and (flags is None or saved.findtext("objFlags") == flags),
            "lifecycle loop test/index changed",
        )


def validate_stop_io(root, metadata):
    frame = unique(root, "diag", "41713")
    operations(
        frame,
        [("gRef", r[0]) for r in IO_LOCALS]
        + [("prim", r[0]) for r in IO_CONVERSIONS]
        + [
            ("gRef", "116544"),
            ("nMux", "42777"),
            (None, "46888"),
            ("prim", "46871"),
            ("gRef", "43367"),
            (None, "55618"),
            (None, "41725"),
            (None, "41722"),
        ]
        + [("iUse", u) for u in ("55822", "55532", "55502", "55456")],
        "stop I/O",
    )
    exact_wires(frame, IO_NETS, "stop I/O")
    for row in IO_LOCALS:
        local(root, *row)
    validate_conversions(frame, metadata, IO_CONVERSIONS)
    require(
        constant(frame, "55618") == "000003E8"
        and constant(frame, "46888") == "00000032",
        "stop I/O counts changed",
    )
    names = call_names(metadata)
    for uid, name, flags in (
        (
            "55822",
            "Simple Error Handler.vi",
            (513, 513, 0, 0, 0, 513, 513, 513, 512, 512),
        ),
        (
            "55532",
            "1_ACQ_WRITE_NI6703.vi",
            (512, 512, 0, 0, 0, 512, 0, 512, 0, 512, 0, 512, 0, 0, 0, 513),
        ),
        ("55502", "1_ACQ_RW_DIO96.vi", (512, 512, 512, 512, 512, 513, 513, 513, 513)),
        (
            "55456",
            "1_ACQ_READ_NI6071E.vi",
            (513, 0, 513, 513, 0, 0, 0, 0, 516, 512, 512, 512),
        ),
    ):
        node = unique(root, "iUse", uid)
        terms = node.findall("termList/*")
        require(
            names.get(uid) == name
            and len(terms) == len(flags)
            and tuple(int(t.findtext("dco/paramIdx", "0")) for t in terms)
            == tuple(range(len(flags)))
            and tuple(int(t.findtext("dco/objFlags", "0")) for t in terms) == flags,
            "stop I/O connector changed",
        )
    _local(
        root,
        metadata,
        "116544",
        "116554",
        49,
        True,
        "NumFloat64",
        "Lecture alimentation HT:",
    )
    _local(root, metadata, "43367", "43377", 46, False, "Boolean", "stop urgence")
    mux = unique(root, "nMux", "42777")
    require(
        mux.findtext("objFlags") == "327680"
        and [t.get("uid") for t in mux.findall("termList/*")] == ["48890", "48893"]
        and mux.findall("termList/*")[1].findtext("dco/i") == "7"
        and _kind(metadata, mux.findall("termList/*")[0]).get("Label")
        == "C2_NI6071E_0:63"
        and _kind(metadata, mux.findall("termList/*")[1]).get("Type") == "NumFloat64",
        "stop HT readback bank/field changed",
    )
    wait = unique(root, "prim", "46871")
    require(
        wait.findtext("primResID") == "1302"
        and tuple(t.get("uid") for t in wait.findall("termList/*"))
        == ("46877", "46880"),
        "stop I/O Wait changed",
    )


def validate_envelopes(root, metadata):
    frame = unique(root, "diag", "3")
    operations(frame, [("sequence", "359")], "root")
    exact_wires(frame, (), "root")
    outer = unique(root, "sequence", "359")
    require(
        [d.get("uid") for d in outer.findall("diagramList/*")]
        == ["135", "188", "367", "41058", "246"]
        and not outer.findall("termList/*")
        and not outer.findall("tunnelList/*"),
        "root five-frame lifecycle changed",
    )
    declarations = unique(root, "diag", "135")
    operations(
        declarations,
        [(None, uid) for uid in FRONT_PORTS] + [("label", "156")],
        "front panel declarations",
    )
    exact_wires(declarations, (), "front panel declarations")
    require(
        [(n.get("class"), n.get("uid")) for n in declarations.findall("nodeList/*")]
        == [("sRN", "139")],
        "front panel declaration container changed",
    )
    terms = declarations.findall("nodeList/*/termList/*")
    require(
        len(terms) == len(FRONT_PORTS)
        and {t.get("uid") for t in terms} == set(FRONT_PORTS)
        and all(
            t.findtext("objFlags")
            == ("147520" if t.get("uid") in ("1614", "17796") else "131136")
            and t.find("dco").get("class") is None
            and len(t.find("dco")) == 0
            and t.find("dco/ConstValue") is None
            for t in terms
        ),
        "unwired FP terminals changed; no initial values inferred",
    )
    runtime = unique(root, "diag", "59492")
    operations(
        runtime,
        [
            ("sequence", "48312"),
            ("gRef", "18303"),
            ("gRef", "60120"),
            (None, "59505"),
            (None, "59502"),
        ],
        "runtime control wrapper",
    )
    exact_wires(
        runtime, (("59502", "71439"), ("60127", "59505")), "runtime control wrapper"
    )
    _local(root, metadata, "18303", "71439", 55, True, "NumInt32", "BVide")
    _local(root, metadata, "60120", "60127", 30, False, "Boolean", "stop")
    _while(root, "59483", "59492", "59502", "59505")
    for uid, body, index, test in (
        ("41705", "41713", "41722", "41725"),
        ("42592", "42610", "42633", "42640"),
    ):
        _while(root, uid, body, index, test)
    for selector, frames, port, aliases in (
        ("43488", ("43496", "43502"), "43512", ("43510", "43511", "43512")),
        ("52981", ("52989", "52995"), "53005", ("53003", "53004", "53005")),
    ):
        case = unique(root, "select", selector)
        require(
            tuple(d.get("uid") for d in case.findall("diagramList/*")) == frames
            and [
                (e.findtext("start"), e.findtext("diagramIdx"))
                for e in case.findall("SelectRangeArray32/*")
            ]
            == [("0", "0"), ("1", "1")],
            "lifecycle Boolean arms changed",
        )
        terms = case.findall("termList/*")
        require(
            len(terms) == 1
            and terms[0].get("uid") == port
            and tuple(p.get("uid") for p in terms[0].findall("dco/termList/*"))
            == aliases,
            "lifecycle case boundary changed",
        )
    specifications = {
        "41058": ([("select", "43488"), ("gRef", "7387")], (("7927", "43512"),)),
        "43496": ([], ()),
        "43502": ([("whileLoop", "41705"), ("whileLoop", "42592")], ()),
        "42610": (
            [
                (None, "11042"),
                ("prim", "1146"),
                ("gRef", "118957"),
                ("gRef", "115330"),
                ("select", "52981"),
                (None, "42640"),
                (None, "42633"),
            ],
            (("11042", "9791"), ("118967", "53005"), ("115354", "42640")),
        ),
        "52995": ([("sequence", "51954")], ()),
    }
    for uid, (ops, nets) in specifications.items():
        operations(unique(root, "diag", uid), ops, "lifecycle envelope")
        exact_wires(unique(root, "diag", uid), nets, "lifecycle envelope")
    for row in (
        ("7387", "7927", 45, False, "Boolean", "TCP ED"),
        ("118957", "118967", 47, False, "Boolean", None),
        ("115330", "115354", 46, False, "Boolean", "stop urgence"),
    ):
        _local(root, metadata, *row)
    stop_body = unique(root, "diag", "42610")
    require(
        constant(stop_body, "11042") == "00000032"
        and unique(root, "prim", "1146").findtext("primResID") == "1302",
        "operator stop Wait changed",
    )
    enabled = unique(root, "diag", "52989")
    operations(
        enabled,
        [("propNode", r[0]) for r in PROPERTY_ROWS] + [(None, "24897")],
        "Enabled properties",
    )
    exact_wires(
        enabled,
        (("24897", "117164", "119037", "119663", "120288", "28680"),),
        "Enabled properties",
    )
    require(constant(enabled, "24897") == "0000", "DisabledEnum constant changed")
    for uid, ddo, omid, ports in PROPERTY_ROWS:
        node = unique(root, "propNode", uid)
        require(
            node.find("ddo").get("uid") == ddo
            and node.findtext("oMId") == omid
            and [p.text for p in node.findall(".//PropItemCode")] == ["104013885"]
            and [p.text for p in node.findall(".//PropItemName")] == ['"DisabledEnum"']
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and tuple(
                t.findtext("dco/objFlags", "0") for t in node.findall("termList/*")
            )
            == ("65536", "262145", "131072", "524289", "0")
            and _kind(metadata, node.findall("termList/*")[-1]).get("Type")
            == "UnitUInt8",
            "UI property source/direction/type changed",
        )
    validate_stop_io(root, metadata)
    validate_cleanup_tree(root, metadata)
    return {
        "diagram_uids": DIAGRAMS,
        "diagrams": len(DIAGRAMS),
        "nets": sum(
            len(unique(root, "diag", uid).findall("signalList/*")) for uid in DIAGRAMS
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    root, metadata = checked_vam(parser.parse_args().source_export_zip)
    print(validate_envelopes(root, metadata))
    print(validate_stop(root, metadata))
    print("PASS: source graph facets only; no hardware or VI execution")


if __name__ == "__main__":
    main()
