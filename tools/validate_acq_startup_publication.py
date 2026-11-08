"""Prove startup command literals and pilot-status publication, never run VI."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import checked_trees, heap_type
from validate_acq_runtime_publication import URI_PREFIX, local, operations

# Literal port, heap type, local UID/port/index, element type, values.
COMMANDS = (
    ("17752", 2033, "16383", "16390", 9, "NumFloat64", (0.0,) * 10),
    ("17752", 2033, "16398", "16401", 10, "NumFloat64", (0.0,) * 10),
    (
        "67948",
        2163,
        "16406",
        "16409",
        11,
        "NumFloat64",
        (0.0, 21.0, 27.9, 0.0, 0.0, 0.0, 360.0, 0.0, 0.0, 0.0),
    ),
    (
        "39466",
        2175,
        "16414",
        "16417",
        12,
        "NumFloat64",
        (6.5, 0.0, 4.755, 4.755, 2.126, 2.126, 2.126, 0.0, 0.0, 0.0),
    ),
    (
        "20833",
        2045,
        "16257",
        "16264",
        17,
        "Boolean",
        tuple(i in (1, 4) for i in range(40)),
    ),
    (
        "17346",
        2129,
        "16132",
        "16139",
        15,
        "Boolean",
        tuple(i in (1, 4, 6, 8, 17, 19) for i in range(32)),
    ),
    ("22493", 2087, "16005", "16012", 13, "Boolean", tuple(i == 33 for i in range(40))),
)
# Writer UID, local UID/index/port, URI constant/name, ordered five ports.
COMMAND_PUBLICATIONS = (
    (
        "16580",
        "24736",
        9,
        "24758",
        "24617",
        "C6NI6703",
        ("16588", "16591", "16594", "16597", "16600"),
    ),
    (
        "16609",
        "24834",
        10,
        "24837",
        "24635",
        "C7NI6703",
        ("21559", "21562", "21565", "21568", "21571"),
    ),
    (
        "16616",
        "24875",
        11,
        "24878",
        "24653",
        "C8NI6703",
        ("16624", "16627", "16630", "16633", "16636"),
    ),
    (
        "16615",
        "25050",
        12,
        "25053",
        "24671",
        "C9NI6703",
        ("16712", "16716", "16719", "16723", "16726"),
    ),
    (
        "426",
        "26050",
        17,
        "26053",
        "25996",
        "C3_OUT_DIO96",
        ("10089", "10485", "14966", "14971", "14975"),
    ),
    (
        "20071",
        "26058",
        15,
        "26061",
        "26014",
        "C4_OUT_DIO96",
        ("20079", "20082", "20085", "20088", "20091"),
    ),
    (
        "15613",
        "26066",
        13,
        "26069",
        "26032",
        "C5_OUT_DIO96",
        ("19230", "19233", "19236", "19239", "19242"),
    ),
)
STATUS_PUBLICATIONS = (
    (
        "34463",
        "34140",
        36,
        "34159",
        "34169",
        "DPS",
        ("34465", "34468", "34471", "34474", "34477"),
    ),
    (
        "34480",
        "34455",
        44,
        "34458",
        "34439",
        "EPS",
        ("34482", "34485", "34488", "34491", "34494"),
    ),
    (
        "27194",
        "27167",
        7,
        "27176",
        "27096",
        "VDM-A",
        ("27197", "27206", "27215", "27220", "27226"),
    ),
)
STATUS_WIRES = (
    ("24459", "31316"),
    ("28766", "24466"),
    ("31312", "27226", "22875"),
    ("27992", "28759"),
    ("27176", "31315"),
    ("34491", "27215"),
    ("27096", "27197"),
    ("34474", "34488"),
    ("34439", "34482"),
    ("34458", "34494"),
    ("34159", "34477"),
    ("34169", "34465"),
    ("18086", "18068"),
)


def cluster(main, heap, count, kind, label=None):
    descriptor, flat = heap_type(main, heap)
    members = descriptor.findall("TypeDesc")
    require(
        descriptor.get("Type") == "Cluster"
        and len(members) == count
        and all(flat[int(n.get("TypeID"))].get("Type") == kind for n in members)
        and (label is None or descriptor.get("Label") == label),
        "startup cluster shape/type/identity changed",
    )
    return descriptor, flat


def publication(frame, row):
    uid, alias, index, port, literal, name, ports = row
    node = unique(frame, "sharedVariableDynamicWrite", uid)
    terms = node.findall("termList/*")
    require(
        node.findtext("SharedVariableDynamicResID") == "5CE6"
        and [t.get("uid") for t in terms] == list(ports)
        and [t.findtext("dco/terminal_ID", "") for t in terms]
        == ["0B", "03", "08", "", "0A"]
        and [t.findtext("dco/objFlags") for t in terms]
        == ["128", "513", "512", "513", "128"],
        "startup PSP writer ports/directions changed",
    )
    local(frame, alias, port, index)
    uri = (URI_PREFIX + name).encode("ascii")
    require(
        bytes.fromhex(constant(frame, literal)) == len(uri).to_bytes(4, "big") + uri,
        "startup PSP URI changed",
    )


def validate_trees(bd, main):
    outer = unique(bd, "sequence", "201")
    require(
        [d.get("uid") for d in outer.findall("diagramList/*")]
        == ["20362", "227", "133", "1356", "21518", "7580"],
        "startup stage order changed",
    )
    raw = unique(bd, "sLoc", "25655")
    require(
        raw in outer.findall("seqLocDCOList/*")
        and raw.findtext("diagDefined") == "02"
        and raw.findtext("objFlags") == "1"
        and [t.get("uid") for t in raw.findall("termList/*")]
        == ["25686", "25687", "25688", "25689", "25690", "25691"],
        "raw pilot error sequence-local changed",
    )
    pilot = unique(bd, "diag", "133")
    exact_wires(
        pilot,
        (
            ("1309", "2107", "25688"),
            ("2112", "1320"),
            ("1195", "2639"),
            ("1678", "2648"),
            ("1664", "2645"),
        ),
        "raw pilot error source",
    )
    reader = unique(pilot, "iUse", "287")
    require(
        reader.findtext("label/textRec/text") == '"1_ACQ_READ_NI6071E.vi"',
        "pilot read callee changed",
    )
    public_term(reader, "1309", 0)
    require(
        reader.findtext("termList/*[@uid='1309']/dco/objFlags") == "513",
        "pilot read error port direction changed",
    )
    caller = unique(bd, "diag", "7580")
    operations(caller, [("sequence", "24603")], "startup final-stage caller")
    exact_wires(caller, (("25691", "28003"),), "raw pilot error transfer")
    sequence = unique(bd, "sequence", "24603")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")]
        == ["14803", "24611", "25990", "33052", "17881"]
        and len(sequence.find("termList")) == 1
        and [t.get("uid") for t in sequence.findall("tunnelList/*")] == ["27938"]
        and sequence.find("seqLocDCOList") is None,
        "startup final-stage topology changed",
    )
    tunnel = sequence.find("termList/*/dco")
    require(
        sequence.find("termList/*").get("uid") == "28003"
        and tunnel.get("class") == "seqTun"
        and tunnel.get("uid") == "27938"
        and tunnel.findtext("objFlags") == "2048"
        and [t.get("uid") for t in tunnel.findall("termList/*")]
        == ["27946", "27956", "27967", "27982", "27992", "28003"],
        "raw pilot error input tunnel changed",
    )
    for frame, port in zip(
        sequence.find("diagramList")[:4], ("27946", "27956", "27967", "27982")
    ):
        require(
            not frame.findall(f"signalList/*/termList/*[@uid='{port}']"),
            "raw pilot error gained an earlier consumer",
        )

    frame = unique(bd, "diag", "14803")
    operations(
        frame,
        [(None, uid) for uid in ("39466", "67948", "17346", "22493", "20833", "17752")]
        + [("gRef", row[2]) for row in COMMANDS]
        + [("label", "20690")],
        "startup command assignment",
    )
    exact_wires(
        frame,
        (
            ("39466", "16417"),
            ("67948", "16409"),
            ("17346", "16139"),
            ("22493", "16012"),
            ("20833", "16264"),
            ("17752", "16390", "16401"),
        ),
        "startup command assignment",
    )
    for literal, heap, alias, port, index, kind, values in COMMANDS:
        local(frame, alias, port, index, True)
        cluster(main, heap, len(values), kind)
        dco = frame.find(f"nodeList/*/termList/*[@uid='{literal}']/dco")
        require(
            dco.findtext("typeDesc") == f"TypeID({heap})",
            "startup literal heap identity changed",
        )
        expected = (
            struct.pack(">10d", *values) if kind == "NumFloat64" else bytes(values)
        )
        if literal == "17752":
            expected += b"\0"  # Original saved 81-byte zero cluster, pinned exactly.
        require(
            bytes.fromhex(constant(frame, literal)) == expected,
            "startup literal value/padding changed",
        )

    frame = unique(bd, "diag", "24611")
    ops = [("iUse", "26161"), ("label", "26194")]
    nets = []
    for i, row in enumerate(COMMAND_PUBLICATIONS):
        publication(frame, row)
        uid, alias, _, port, literal, _, ports = row
        ops.extend(
            (("sharedVariableDynamicWrite", uid), ("gRef", alias), (None, literal))
        )
        nets.extend(((literal, ports[0]), (port, ports[4])))
        if i:
            nets.append((COMMAND_PUBLICATIONS[i - 1][6][3], ports[2]))
    nets.append(("19239", "26191"))
    operations(frame, ops, "startup command publication")
    exact_wires(frame, nets, "startup command publication")
    handler = unique(frame, "iUse", "26161")
    require(
        handler.findtext("label/textRec/text") == '"Simple Error Handler.vi"',
        "startup command error consumer changed",
    )
    public_term(handler, "26191", 9)
    public_term(handler, "26188", 8)

    frame = unique(bd, "diag", "17881")
    ops = [
        ("prim", "24445"),
        ("prim", "16847"),
        ("nMux", "31306"),
        ("nMux", "28019"),
        ("gRef", "8662"),
        ("label", "34497"),
        (None, "18086"),
    ]
    for row in STATUS_PUBLICATIONS:
        publication(frame, row)
        ops.extend(
            (("sharedVariableDynamicWrite", row[0]), ("gRef", row[1]), (None, row[4]))
        )
    operations(frame, ops, "startup status publication")
    exact_wires(frame, STATUS_WIRES, "startup status publication")
    local(frame, "8662", "22875", 7, True)
    primitive(frame, "24445", 1064, ("24459", "24466"))
    primitive(frame, "16847", 1302, ("18065", "18068"))
    require(
        unique(frame, "prim", "24445").findtext("primIndex") == "29"
        and unique(frame, "prim", "16847").findtext("primIndex") == "160"
        and constant(frame, "18086") == "00000064",
        "startup NOT or independent 100-ms Wait changed",
    )
    for port, heap in (("24459", 2592), ("24466", 2593)):
        require(
            unique(frame, "prim", "24445").findtext(
                f"termList/*[@uid='{port}']/dco/typeDesc"
            )
            == f"TypeID({heap})"
            and heap_type(main, heap)[0].get("Type") == "Boolean",
            "startup NOT Boolean terminal type changed",
        )
    for uid, flag, ports, dco_uid, aggregate_uid, heap in (
        ("28019", "327680", ("28759", "28766"), "28767", "28763", 2598),
        ("31306", "262144", ("31312", "31315", "31316"), "31317", "31313", 2596),
    ):
        node = unique(frame, "nMux", uid)
        require(
            node.findtext("objFlags") == flag
            and [t.get("uid") for t in node.findall("termList/*")] == list(ports)
            and [d.get("uid") for d in node.findall("dcoList/*")] == [dco_uid]
            and node.find("dcoAgg").get("uid") == aggregate_uid,
            "startup bundle/unbundle topology changed",
        )
        member = node.find(f"termList/*/dco[@uid='{dco_uid}']")
        require(
            member.findtext("i", "0") == "0"
            and member.findtext("typeDesc") == f"TypeID({heap})"
            and member.findtext("objFlags", "0") == ("1" if uid == "28019" else "0"),
            "startup status field index/type/direction changed",
        )
        aggregate = node.find(f"termList/*/dco[@uid='{aggregate_uid}']")
        require(
            aggregate.findtext("typeDesc")
            == ("TypeID(2597)" if uid == "28019" else "TypeID(2595)"),
            "startup aggregate heap identity changed",
        )
    vdm, flat = cluster(main, 2595, 80, "Boolean", "VDM-A")
    require(
        flat[int(vdm.find("TypeDesc").get("TypeID"))].get("Label")
        == heap_type(main, 2596)[0].get("Label"),
        "pilot-present field identity changed",
    )
    require(
        heap_type(main, 2596)[0].get("Type") == "Boolean",
        "pilot-present field type changed",
    )
    error, flat = heap_type(main, 2597)
    require(
        error.get("Type") == "Cluster"
        and [
            (
                flat[int(n.get("TypeID"))].get("Type"),
                flat[int(n.get("TypeID"))].get("Label"),
            )
            for n in error.findall("TypeDesc")
        ]
        == [("Boolean", "status"), ("NumInt32", "code"), ("String", "source")],
        "raw error cluster field order changed",
    )
    require(
        heap_type(main, 2598)[0].get("Type") == "Boolean"
        and heap_type(main, 2598)[0].get("Label") == "status",
        "raw status output type changed",
    )
    for heap, size, name in ((2604, 80, "VDM-A"), (2615, 77, "EPS"), (2616, 29, "DPS")):
        cluster(main, heap, size, "Boolean", name)
    for uid, heap in (("27167", 2604), ("34455", 2615), ("34140", 2616)):
        require(
            unique(frame, "gRef", uid).findtext("termList/*/dco/typeDesc")
            == f"TypeID({heap})",
            "startup status snapshot heap changed",
        )
    return (
        "3 startup frames: 40 nets, 53 operations; "
        "raw pilot error retained; 152 command fields"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(validate_trees(*checked_trees(parser.parse_args().archive)))


if __name__ == "__main__":
    main()
