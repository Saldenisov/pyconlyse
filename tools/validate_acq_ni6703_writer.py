"""Prove original NI6703 conversion, four-write error chain and caller edges.

Reads pinned saved XML only. No NI, PSP, XP, VISA or LabVIEW execution.
The three caller facets do not prove every operation in their parent frames.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6220_read_error_contract import (
    ALL_MEMBERS_ARCHIVE_SHA256,
    connector_map,
)

MEMBER = "1_ACQ_WRITE_NI6703.vi"
FILE_HASHES = {
    "vi.xml": "8188B80D33E0943F4F093E2C9BE058E1EAFBE438EF1DF1EB96A57867F6FD1FAE",
    "vi_BDHb.xml": "2432B10879A5EC011A84356E0A2192A461E8C436391648A48D8693787C693B7D",
    "vi_FPHb.xml": "A4AE50E63C16C359F1D503CD51C1A4A5EB6655AE2962397C796827C84474A668",
}
ARRAYS = {
    "378": (1, 1, 0.5, 0.5, 1, 0.5, 1, 0.5, 1, 0.5),
    "420": (0.25, 0.25, 0.25, 0.25, 0.25, 0.0416666, 0.25, 0.25, 0.25, 0.25),
    "453": (1, 0.2, 0.2, 1, 1, 0.0277777777, 0.025, 0.1111111111, 0.1111111111, 1),
    "485": (0.5, 0.25, 1, 1, 1, 1, 1, 1, 1, 1),
    "1246": (0, -2, -2, 0, 0, 0, 0, 0, 0, 0),
}
FORMULAS = (
    ("748", "750", "753", "y=57.3*acos(10**(-x/20));"),
    ("568", "583", "706", "y=(-4*10**-6)*x**3+0.0006*x**2-0.0624*x+3.8587;"),
    (
        "1158",
        "1164",
        "1167",
        "y=(8*10**-9)*(x**4)-((7*10**-7)*x**3)-((3*10**-5)*x**2)-(0.0181*x)+2.1775;",
    ),
)
ROOT_WIRES = (
    ("706", "1150"),
    ("1370", "1156"),
    ("1167", "1003"),
    ("1229", "1008"),
    ("1000", "2025"),
    ("620", "1216", "997"),
    ("762", "750"),
    ("791", "767"),
    ("753", "583"),
    ("1219", "1164"),
    ("1347", "1222"),
    ("485", "782"),
    ("776", "2286"),
    ("1087", "779"),
    ("1246", "626"),
    ("555", "623"),
    ("453", "561"),
    ("976", "558"),
    ("420", "1089"),
    ("1081", "1734"),
    ("859", "1084"),
    ("378", "814"),
    ("743", "811"),
    ("808", "1386"),
    ("1876", "1405"),
    ("62", "243", "1843", "2098", "2358"),
    ("2321", "1282"),
    ("2049", "2298"),
    ("1802", "2037"),
    ("1426", "1773"),
    ("2348", "2268"),
    ("2336", "2292"),
    ("2361", "2265"),
    ("2101", "1992"),
    ("2076", "2031"),
    ("2088", "1995"),
    ("1830", "1702"),
    ("1818", "1750"),
    ("1847", "1699"),
    ("246", "1327"),
    ("1076", "1411"),
    ("1954", "1339"),
)
CALLS = (
    ("592", "69", "1954", "1876"),
    ("1696", "1840", "1830", "1818"),
    ("1989", "2096", "2088", "2076"),
    ("1200", "2356", "2348", "2336"),
)
CALL_PORTS = (
    (
        "1327",
        "1339",
        "1343",
        "1350",
        "1359",
        "1368",
        "1377",
        "1386",
        "1395",
        "1405",
        "1408",
        "1411",
        "1415",
        "1418",
        "1423",
        "1426",
    ),
    (
        "1699",
        "1702",
        "1705",
        "1708",
        "1712",
        "1715",
        "1721",
        "1734",
        "1746",
        "1750",
        "1753",
        "1773",
        "1782",
        "1796",
        "1799",
        "1802",
    ),
    (
        "1992",
        "1995",
        "1998",
        "2001",
        "2005",
        "2012",
        "2021",
        "2025",
        "2028",
        "2031",
        "2034",
        "2037",
        "2040",
        "2043",
        "2046",
        "2049",
    ),
    (
        "2265",
        "2268",
        "2271",
        "2274",
        "2277",
        "2280",
        "2283",
        "2286",
        "2289",
        "2292",
        "2295",
        "2298",
        "2301",
        "2304",
        "2317",
        "2321",
    ),
)
TASK_PORTS = (("243", "246"), ("1843", "1847"), ("2098", "2101"), ("2358", "2361"))


def checked_writer_roots(path):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper()
        == ALL_MEMBERS_ARCHIVE_SHA256,
        "original member archive hash changed",
    )
    roots = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original XML member count changed")
        for name, expected in FILE_HASHES.items():
            payload = archive.read(MEMBER + "/" + name)
            require(
                hashlib.sha256(payload).hexdigest().upper() == expected,
                f"NI6703 writer XML hash changed: {name}",
            )
            roots[name] = ET.fromstring(payload)
    return roots


def numeric_array(frame, uid):
    data = bytes.fromhex(constant(frame, uid))
    require(
        len(data) == 84 and data[:4] == b"\x00\x00\x00\x0a",
        f"NI6703 array {uid} shape changed",
    )
    return struct.unpack(">10d", data[4:])


def validate_writer(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    frame = bd.find("root")
    require(
        frame.get("uid") == "3"
        and [d.get("uid") for d in bd.findall(".//*[@class='diag']")]
        == ["3", "1093", "1100"],
        "NI6703 writer diagram scope changed",
    )
    require(
        connector_map(fp)
        == [
            (0, "630"),
            (1, "60"),
            (5, "773"),
            (7, "903"),
            (9, "1004"),
            (11, "1074"),
            (15, "1280"),
        ],
        "NI6703 writer connector map changed",
    )
    require(
        [n.get("Flags") for n in meta.findall("CPMp/Section/TypeDesc")]
        == [
            "0x0300",
            "0x0100",
            "-1",
            "-1",
            "-1",
            "0x0400",
            "-1",
            "0x0500",
            "-1",
            "0x0600",
            "-1",
            "0x0200",
            "-1",
            "-1",
            "-1",
            "0x0000",
        ],
        "NI6703 writer local mapping changed",
    )
    for terminal, control in (
        ("743", "630"),
        ("62", "60"),
        ("859", "773"),
        ("976", "903"),
        ("1087", "1004"),
        ("1076", "1074"),
        ("1282", "1280"),
    ):
        require(
            unique(bd, "fPTerm", terminal).find("dco").get("uid") == control,
            "NI6703 writer public terminal changed",
        )
    require(
        Counter(n.get("class") for n in frame.findall("zPlaneList/*[@class]"))
        == {
            "label": 9,
            "aReplace": 1,
            "fBox": 3,
            "aIndx": 1,
            "commentNode": 1,
            "prim": 5,
            "nMux": 4,
            "polyIUse": 4,
        },
        "NI6703 writer operation census changed",
    )
    exact_wires(frame, ROOT_WIRES, "NI6703 writer root")
    for uid, expected in ARRAYS.items():
        require(
            numeric_array(frame, uid) == expected,
            f"NI6703 coefficient array {uid} changed",
        )
    for uid, expected in (
        ("1347", "00000003"),
        ("1229", "00000003"),
        ("791", "00000004"),
        ("1370", "00000004"),
    ):
        require(
            constant(frame, uid) == expected, "NI6703 nonlinear channel index changed"
        )
    for uid, inp, out, formula in FORMULAS:
        node = unique(bd, "fBox", uid)
        require(
            node.findtext("formula/text") == f'"{formula}"'
            and [
                (t.get("uid"), t.findtext("dco/vblName/text"))
                for t in node.findall("termList/*")
            ]
            == [(inp, '"x"'), (out, '"y"')],
            "NI6703 active formula changed",
        )
    for uid, resource, index, ports in (
        ("802", "1052", "105", ("808", "811", "814")),
        ("1072", "1052", "105", ("1081", "1084", "1089")),
        ("549", "1052", "105", ("555", "558", "561")),
        ("295", "1050", "103", ("620", "623", "626")),
        ("769", "1052", "105", ("776", "779", "782")),
    ):
        node = unique(bd, "prim", uid)
        require(
            node.findtext("primResID") == resource
            and node.findtext("primIndex") == index
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and [t.findtext("dco/parmIndex", "0") for t in node.findall("termList/*")]
            == ["0", "1", "2"],
            "NI6703 arithmetic operation/ports changed",
        )
    for klass, uid, ports in (
        ("aIndx", "1210", ("1216", "1219", "1222", "762", "767")),
        ("aReplace", "991", ("997", "1000", "1003", "1008", "1150", "1156")),
    ):
        require(
            tuple(t.get("uid") for t in unique(bd, klass, uid).findall("termList/*"))
            == ports,
            "NI6703 nonlinear array ports changed",
        )
    connected = {
        t.get("uid")
        for s in frame.findall("signalList/*")
        for t in s.findall("termList/*")
    }
    for field, (uid, unbundle_uid, auto_uid, timeout_uid) in enumerate(CALLS):
        node = unique(bd, "polyIUse", uid)
        require(
            node.findtext("label/textRec/text") == '"DAQmx Write.vi"'
            and node.findtext("instanceSelector/menuInstanceUsed") == "06",
            "NI6703 write polymorphic selection changed",
        )
        terms = node.findall("termList/*")
        require(
            tuple(t.get("uid") for t in terms) == CALL_PORTS[field],
            "NI6703 write connector identities changed",
        )
        for slot, term in enumerate(terms):
            public_term(node, term.get("uid"), slot)
        require(
            terms[4].get("uid") not in connected
            and terms[10].get("uid") not in connected,
            "NI6703 returned task/count gained consumer",
        )
        require(
            constant(frame, auto_uid) == "01"
            and constant(frame, timeout_uid) == "4034000000000000",
            "NI6703 autoStart/timeout changed",
        )
        unbundle = unique(bd, "nMux", unbundle_uid)
        require(
            tuple(t.get("uid") for t in unbundle.findall("termList/*"))
            == TASK_PORTS[field]
            and unbundle.findtext("termList/*[2]/dco/i", "0") == str(field),
            "NI6703 input task field order changed",
        )
    comment = unique(bd, "commentNode", "1070")
    require(
        comment.findtext("activeDiag") == "01"
        and comment.findtext("defaultDiag") == "01"
        and comment.findtext("commentMode") == "True"
        and not comment.findall("termList/*")
        and not comment.findall("tunnelList/*"),
        "NI6703 disabled implementation mode changed",
    )
    old, empty = comment.findall("diagramList/*")
    require(
        not empty.findall("zPlaneList/*"), "NI6703 empty enabled arm gained operation"
    )
    exact_wires(empty, (), "NI6703 empty enabled arm")
    exact_wires(
        old,
        (
            ("666", "610"),
            ("652", "615"),
            ("594", "661"),
            ("590", "673"),
            ("692", "658"),
            ("678", "669"),
            ("647", "636"),
            ("600", "644"),
            ("639", "625"),
            ("578", "618"),
            ("597", "575"),
        ),
        "NI6703 disabled old arm",
    )
    return (
        "NI6703 writer: 40 connected slopes, two C8 offsets, "
        "indices 3/4 nonlinear formulas; C6->C9 error chain; "
        "autoStart True/20 s; no task/count consumer, retry or rollback; "
        "old arm inactive"
    )


def connected_group(frame, terminal):
    matches = [
        tuple(t.get("uid") for t in s.findall("termList/*"))
        for s in frame.findall("signalList/*")
        if terminal in {t.get("uid") for t in s.findall("termList/*")}
    ]
    require(len(matches) == 1, "NI6703 caller terminal wire absent/duplicated")
    return frozenset(matches[0])


def validate_caller_edges(root):
    # writer, frame, four converters, four source locals, task local, DIO, handler
    callers = (
        (
            "19408",
            "25990",
            ("19635", "19643", "19651", "19659"),
            ("19603", "19611", "19619", "19627"),
            "19675",
            "19376",
            "16070",
        ),
        (
            "278",
            "7386",
            ("7588", "8669", "8677", "7611"),
            ("2388", "2448", "2486", "2494"),
            "1828",
            "686",
            "11701",
        ),
        (
            "55532",
            "41713",
            ("55774", "55782", "55790", "55798"),
            ("55742", "55750", "55758", "55766"),
            "55814",
            "55502",
            "55822",
        ),
    )
    actual = {
        n.get("uid")
        for n in root.findall(".//*[@class='iUse']")
        if n.findtext("label/textRec/text") == f'"{MEMBER}"'
    }
    require(actual == {c[0] for c in callers}, "NI6703 root call-site census changed")
    lines = []
    for uid, frame_uid, converters, locals_, task_uid, dio_uid, handler_uid in callers:
        frame = unique(root, "diag", frame_uid)
        call = unique(root, "iUse", uid)
        require(call in frame.findall("zPlaneList/*"), "NI6703 caller moved frame")
        terms = call.findall("termList/*")
        require(len(terms) == 16, "NI6703 caller connector changed")
        for slot, term in enumerate(terms):
            public_term(call, term.get("uid"), slot)
        for bank, slot, conv_uid, local_uid in zip(
            range(9, 13), (0, 5, 7, 9), converters, locals_
        ):
            conv, local = (
                unique(root, "prim", conv_uid),
                unique(root, "gRef", local_uid),
            )
            require(
                conv in frame.findall("zPlaneList/*")
                and local in frame.findall("zPlaneList/*")
                and conv.findtext("primResID") == "1169"
                and conv.findtext("primIndex") == "157"
                and local.findtext("termList/*/dco/paramIdx") == str(bank)
                and local.findtext("termList/*/objFlags") == "4096",
                "NI6703 caller logical bank/converter changed",
            )
            ports = conv.findall("termList/*")
            require(
                len(ports) == 2
                and [p.findtext("dco/parmIndex", "0") for p in ports] == ["0", "1"],
                "NI6703 caller converter ports changed",
            )
            require(
                connected_group(frame, terms[slot].get("uid"))
                == {terms[slot].get("uid"), ports[0].get("uid")}
                and connected_group(frame, ports[1].get("uid"))
                == {ports[1].get("uid"), local.find("termList/*").get("uid")},
                "NI6703 caller bank wire changed",
            )
        task = unique(root, "gRef", task_uid)
        dio, handler = unique(root, "iUse", dio_uid), unique(root, "iUse", handler_uid)
        require(
            task in frame.findall("zPlaneList/*")
            and task.findtext("termList/*/dco/paramIdx") == "25"
            and task.findtext("termList/*/objFlags") == "4096"
            and dio.findtext("label/textRec/text") == '"1_ACQ_RW_DIO96.vi"'
            and handler.findtext("label/textRec/text") == '"Simple Error Handler.vi"',
            "NI6703 caller task/error peer changed",
        )
        for slot, peer in (
            (1, task.find("termList/*")),
            (11, dio.findall("termList/*")[8]),
            (15, handler.findall("termList/*")[9]),
        ):
            require(
                connected_group(frame, terms[slot].get("uid"))
                == {terms[slot].get("uid"), peer.get("uid")},
                "NI6703 caller task/error wire changed",
            )
        lines.append(
            f"caller {uid}/diagram {frame_uid}: "
            "local banks 9..12 -> array -> C6..C9; task local 25; "
            "DIO error -> writer -> Simple Error Handler"
        )
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("members_archive", type=Path)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_writer(checked_writer_roots(args.members_archive)))
    for line in validate_caller_edges(checked_root(args.root_archive)):
        print(line)


if __name__ == "__main__":
    main()
