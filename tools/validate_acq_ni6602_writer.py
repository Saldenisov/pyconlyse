"""Prove saved NI6602 poll/timing/error graph and ACQ-only request caller."""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6220_read_error_contract import (
    ALL_MEMBERS_ARCHIVE_SHA256,
    connector_map,
)
from validate_acq_ni6703_writer import connected_group

MEMBER = "1_ACQ_WRITE_NI6602.vi"
FILE_HASHES = {
    "vi.xml": "58F39810067EC428A1BB8B825D0BB6C54F535CE330DC8FEC48031ABAB2ECB899",
    "vi_BDHb.xml": "9973BC934A351E8B3969D5FD6D8CAC67139285F0589D57A0BBAC1AE01D4C4FBB",
    "vi_FPHb.xml": "7B8F89BC1E8F21283AD6382670F1E9BBA30658BB3CF0DBFF576BEB31DCA40B0F",
}
ROOT_WIRES = (
    ("316", "3091"),
    ("3028", "334"),
    ("2758", "3135"),
    ("2995", "3085"),
    ("3088", "3035"),
    ("3094", "3068"),
    ("3131", "3016"),
    ("3143", "2983"),
    ("201", "3109"),
    ("163", "3097", "3103"),
    ("13371", "204"),
    ("13356", "166"),
    ("13127", "13365"),
    ("13077", "13378"),
    ("13230", "13375"),
    ("13218", "13361"),
    ("13028", "184"),
    ("3080", "13111"),
)
POLL_WIRES = (
    ("325", "429"),
    ("3185", "587"),
    ("426", "3158"),
    ("368", "328"),
    ("3155", "331"),
    ("180", "3210"),
    ("3207", "3146"),
    ("3213", "3134"),
    ("3216", "3191"),
    ("3138", "3204"),
    ("3171", "3199"),
    ("3161", "3188"),
)


def checked_roots(path):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper()
        == ALL_MEMBERS_ARCHIVE_SHA256,
        "original member archive hash changed",
    )
    roots = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original XML member count changed")
        for name, expected in FILE_HASHES.items():
            data = archive.read(MEMBER + "/" + name)
            require(
                hashlib.sha256(data).hexdigest().upper() == expected,
                f"NI6602 writer XML hash changed: {name}",
            )
            roots[name] = ET.fromstring(data)
    return roots


def operations(frame, expected, label):
    actual = [
        (n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*[@class]")
    ]
    require(
        len(actual) == len(expected) and set(actual) == set(expected),
        label + " operation census changed",
    )


def primitive(bd, uid, resource, ports):
    node = unique(bd, "prim", uid)
    require(
        node.findtext("primResID") == str(resource)
        and tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
        "NI6602 numeric/Boolean primitive changed",
    )
    for index, term in enumerate(node.findall("termList/*")):
        require(
            int(term.findtext("dco/parmIndex", "0")) == index,
            "NI6602 primitive input-slot interpretation changed",
        )


def validate_writer(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        tuple(t.get("uid") for t in fp.findall("root/ddoList/*"))
        == ("13026", "13107", "13070", "13124", "2756"),
        "NI6602 front-panel local register changed",
    )
    require(
        connector_map(fp)
        == [(0, "13107"), (7, "2756"), (8, "13026"), (9, "13124"), (10, "13070")],
        "NI6602 writer connector changed",
    )
    require(
        [t.get("Flags") for t in meta.findall("CPMp/Section/TypeDesc")]
        == [
            "0x0100",
            "-1",
            "-1",
            "-1",
            "-1",
            "-1",
            "-1",
            "0x0400",
            "0x0000",
            "0x0300",
            "0x0200",
            "-1",
        ],
        "NI6602 connector/local flags changed",
    )
    require(
        {d.get("uid") for d in bd.findall(".//*[@class='diag']")} == {"3", "3149"},
        "NI6602 diagram census changed",
    )
    root, body = bd.find("root"), unique(bd, "diag", "3149")
    operations(
        root,
        (
            ("iUse", "309"),
            ("whileLoop", "3129"),
            ("propNode", "3083"),
            ("iUse", "3032"),
            ("iUse", "2976"),
            ("label", "341"),
            ("prim", "183"),
            ("prim", "157"),
            ("prim", "13369"),
            ("prim", "13352"),
        ),
        "NI6602 root",
    )
    operations(
        body,
        (
            ("cpdArith", "420"),
            ("prim", "127"),
            ("propNode", "3202"),
            ("prim", "3194"),
            ("prim", "3183"),
        ),
        "NI6602 poll",
    )
    exact_wires(root, ROOT_WIRES, "NI6602 root")
    exact_wires(body, POLL_WIRES, "NI6602 poll")
    loop = unique(bd, "whileLoop", "3129")
    require(
        loop.find("srDCOList").get("elements") == "0"
        and not loop.findall("srDCOList/*")
        and loop.findtext("loopTestDCO/objFlags") == "65537"
        and loop.find("loopTestDCO").get("uid") == "3159"
        and loop.find("loopIndexDCO").get("uid") == "3156",
        "NI6602 stop polarity/index/shift-register scope changed",
    )
    for outer, inner, flags in (
        ("3131", "3134", "2049"),
        ("3135", "3138", "2048"),
        ("3143", "3146", "2049"),
        ("184", "180", "2048"),
    ):
        tunnel = loop.find(f"termList/*[@uid='{outer}']/dco")
        require(
            tunnel is not None
            and tunnel.get("class") == "lpTun"
            and tunnel.findtext("objFlags") == flags
            and [t.get("uid") for t in tunnel.findall("termList/*")] == [inner, outer],
            "NI6602 ordinary loop tunnel changed",
        )
    compound = unique(bd, "cpdArith", "420")
    require(
        compound.findtext("objFlags") == "720896"
        and [t.findtext("dco/objFlags") for t in compound.findall("termList/*")]
        == ["131073", "262144", "262144"],
        "NI6602 non-inverted OR changed",
    )
    for uid, resource, ports in (
        ("127", 1110, ("325", "328", "331")),
        ("3183", 1102, ("3185", "3188", "3191")),
        ("3194", 1302, ("3196", "3199")),
        ("13369", 1052, ("13371", "13375", "13378")),
        ("13352", 1052, ("13356", "13361", "13365")),
        ("183", 1142, ("201", "204")),
        ("157", 1142, ("163", "166")),
    ):
        primitive(bd, uid, resource, ports)
    for frame, uid, value in (
        (body, "368", "00000014"),
        (body, "3171", "00000001"),
        (body, "3161", "01"),
        (root, "13218", "4034000000000000"),
        (root, "13230", "4034000000000000"),
    ):
        require(constant(frame, uid) == value, "NI6602 literal changed")
    for uid, codes, ports, flags in (
        (
            "3202",
            ("6414",),
            ("3204", "3207", "3210", "3213", "3216"),
            ("65536", "262145", "131072", "524289", "1"),
        ),
        (
            "3083",
            ("664", "4465", "4457"),
            ("3085", "3088", "3091", "3094", "3097", "3103", "3109"),
            ("65536", "262145", "131072", "524289", "0", "0", "0"),
        ),
    ):
        node = unique(bd, "propNode", uid)
        require(
            tuple(node.itertext())
            and node.findtext("oMId") == "0061"
            and tuple(e.text for e in node.findall(".//PropItemCode")) == codes
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and tuple(
                t.findtext("dco/objFlags", "0") for t in node.findall("termList/*")
            )
            == flags,
            "NI6602 property order/identity/direction changed",
        )
    for uid, label, wired_slots in (
        ("309", "Clear Errors.vi", (0, 4)),
        ("2976", "DAQmx Stop Task.vi", (0, 4, 11, 15)),
        ("3032", "DAQmx Start Task.vi", (0, 11, 15)),
    ):
        call = unique(bd, "iUse", uid)
        require(
            call.findtext("label/textRec/text") == '"' + label + '"',
            "NI6602 post-poll call changed",
        )
        connected = {t for wire in ROOT_WIRES for t in wire}
        for slot, term in enumerate(call.findall("termList/*")):
            public_term(call, term.get("uid"), slot)
            require(
                (term.get("uid") in connected) == (slot in wired_slots),
                "NI6602 unused external port became wired",
            )
    for port, control in (
        ("13028", "13026"),
        ("13111", "13107"),
        ("2758", "2756"),
        ("13127", "13124"),
        ("13077", "13070"),
    ):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control,
            "NI6602 public terminal mapping changed",
        )
    return (
        "NI6602: stop when Done==True OR i>20; ordinary task/error tunnels; "
        "Wait 1 ms independent; Stop -> Clear Errors -> InitialDelay/Low/High "
        "properties -> Start; two 20.0 multipliers and conversion primitives "
        "1142; property-input coercion remains a separate boundary"
    )


def validate_acq_caller(root):
    frame = unique(root, "diag", "23641")
    call = unique(root, "iUse", "23634")
    require(
        call in frame.iter()
        and call.findtext("label/textRec/text") == '"1_ACQ_WRITE_NI6602.vi"',
        "ACQ NI6602 caller moved",
    )
    for slot, port, peer in (
        (7, "23671", "21189"),
        (9, "23677", "31344"),
        (10, "23680", "21083"),
        (0, "23650", "22517"),
    ):
        public_term(call, port, slot)
        require(
            connected_group(frame, port) == {port, peer},
            "ACQ NI6602 task/timing/handler edge changed",
        )
    require(
        not any(
            "23674" in {t.get("uid") for t in s.findall("termList/*")}
            for s in frame.findall("signalList/*")
        ),
        "ACQ NI6602 incoming error became wired",
    )
    sequence = unique(root, "sequence", "23633")
    require(
        [f.get("uid") for f in sequence.findall("diagramList/*")]
        == ["23641", "22979", "1507"],
        "ACQ NI6602 call/reset/publication order changed",
    )
    reset, publish = (unique(root, "diag", uid) for uid in ("22979", "1507"))
    exact_wires(
        reset,
        (("24963", "23478"), ("23474", "23252"), ("23240", "23477")),
        "ACQ counter reset",
    )
    exact_wires(
        publish, (("5331", "21458"), ("5125", "21471")), "ACQ counter publication"
    )
    require(
        constant(reset, "24963") == "BFF0000000000000"
        and unique(root, "nMux", "23468").findtext("termList/*[@uid='23478']/dco/i")
        == "32",
        "ACQ counter selector reset changed",
    )
    for uid, direction in (("23248", "36864"), ("23233", "4096"), ("5036", "4096")):
        alias = unique(root, "gRef", uid)
        require(
            alias.findtext("termList/*/dco/paramIdx") == "39"
            and alias.findtext("termList/*/objFlags") == direction,
            "ACQ counter reset/publish local alias changed",
        )
    return (
        "ACQ caller: task/delay/width inputs 7/9/10; error input unwired; "
        "returned error to handler; ordered reset field 32=-1 then PSP boundary; "
        "reset is not hardware-success acknowledgement"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("members_archive", type=Path)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_writer(checked_roots(args.members_archive)))
    print(validate_acq_caller(checked_root(args.root_archive)))


if __name__ == "__main__":
    main()
