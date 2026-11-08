"""Prove both original focal command graphs; vendor calls remain boundaries."""

from __future__ import annotations

import argparse
import hashlib
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import (
    ALL_MEMBERS_ARCHIVE_SHA256,
    connector_map,
)
from validate_acq_runtime_publication import operations

FILE_HASHES = {
    "1_Focales ON.vi": {
        "vi.xml": "BC97A8A4B6482A5C94E5B5D17B8328E8904AF0D84811AD16023C1DFB451678D7",
        "vi_BDHb.xml": (
            "3848E72F8D91973176CABD97941729AC487C81216E74901F8813882E50D643CC"
        ),
        "vi_FPHb.xml": (
            "6E4145B416003BA69B52B8DBEAB38B190475E7E1413DBE8BE2919FDC38934C4A"
        ),
    },
    "1_Focales OFF.vi": {
        "vi.xml": "0E8892C47C75205FB066294855230E3904969392693DF7B23716382DB094F5F3",
        "vi_BDHb.xml": (
            "0BF7BD64195B86A0067EEDBA84E72AE100453B6E94FA3A30A52FC2EFDB97EDDE"
        ),
        "vi_FPHb.xml": (
            "3DF6C628BD3BB4868BFF05CCB373728B0C86DD23D0375588D126772C96E293C4"
        ),
    },
}
# Focal number; ordered init/voltage/slew/current/output/close node UIDs;
# resource FP terminal/DCO; init ID query/reset, voltage/slew/current/output
# literal ports; unconnected baud literal port; merge input port.
ON_BRANCHES = (
    (
        3,
        ("738", "839", "1050", "902", "963", "585"),
        "564",
        "561",
        ("714", "685", "1040", "1028", "1016", "1006"),
        "650",
        "2808",
    ),
    (
        2,
        ("567", "2188", "2789", "2246", "2497", "2288"),
        "2134",
        "2126",
        ("2352", "2342", "2747", "2735", "2723", "2711"),
        "2329",
        "2811",
    ),
    (
        1,
        ("659", "2788", "3857", "3731", "3770", "2560"),
        "2423",
        "2421",
        ("2624", "2614", "3847", "3835", "3823", "3811"),
        "2601",
        "2825",
    ),
)
OFF_BRANCHES = (
    (
        3,
        ("670", "712", "909", "751", "790", "594"),
        "580",
        "578",
        ("662", "650", "891", "870", "845", "832"),
        "637",
        "2808",
    ),
    *ON_BRANCHES[1:],
)
STEPS = (
    "Initialize",
    "Set Voltage",
    "Set Current Slew",
    "Set Current",
    "Set Output",
    "Close",
)
VALUES = {3: (70.0, 0.02, 15.1), 2: (80.0, 0.02, 20.9), 1: (80.0, 0.02, 13.73)}


def checked_roots(path):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper()
        == ALL_MEMBERS_ARCHIVE_SHA256,
        "original member archive hash changed",
    )
    result = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original XML member count changed")
        for member, hashes in FILE_HASHES.items():
            result[member] = {}
            for name, expected in hashes.items():
                payload = archive.read(member + "/" + name)
                require(
                    hashlib.sha256(payload).hexdigest().upper() == expected,
                    "focal XML hash changed: " + member + "/" + name,
                )
                result[member][name] = ET.fromstring(payload)
    return result


def ports(root, uid, step):
    node = unique(root, "iUse", uid)
    terms = node.findall("termList/*")
    require(
        node.findtext("label/textRec/text") == '"chr62000 ' + step + '.vi"'
        and len(terms) == 12
        and [int(t.findtext("dco/paramIdx", "0")) for t in terms] == list(range(12)),
        "focal call member/connector slots changed",
    )
    active = {0: "513", 8: "512", 11: "128"}
    if step == "Initialize":
        active.update({3: "513", 9: "512", 10: "512", 11: "512"})
    elif step != "Close":
        active.update({3: "513", 10: "512"})
    require(
        all(
            t.findtext("dco/objFlags", "0") == active.get(i, "0")
            for i, t in enumerate(terms)
            if i != 7
        ),
        "focal call port directions changed",
    )
    require(
        terms[7].findtext("dco/objFlags", "0") in ("0", "4"),
        "focal unused connector port changed",
    )
    return [t.get("uid") for t in terms]


def validate_member(roots, *, enabled):
    bd, fp, meta = (roots[name] for name in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    frame = bd.find("root")
    branches = ON_BRANCHES if enabled else OFF_BRANCHES
    require(
        frame.get("uid") == "3" and len(bd.findall(".//*[@class='diag']")) == 1,
        "focal graph gained nested diagrams",
    )
    require(
        connector_map(fp) == [(0, "1193")]
        and [n.get("Flags") for n in meta.findall("CPMp/Section/TypeDesc")]
        == ["0x0000", "-1", "-1", "-1", "-1", "-1", "-1"],
        "focal public error-only connector changed",
    )
    require(
        [n.get("uid") for n in fp.findall("root/ddoList/*")]
        == ["1193", "2126", "2421", branches[0][3]],
        "focal FP parameter identity changed",
    )
    expected_ops = [("mergeErrors", "2758"), ("label", "705"), (None, "1195")]
    nets = [("2805", "1195")]
    for (
        focal,
        uids,
        resource_port,
        resource_dco,
        literal_ports,
        baud,
        merge,
    ) in branches:
        call_ports = [ports(bd, uid, step) for uid, step in zip(uids, STEPS)]
        expected_ops.extend(("iUse", uid) for uid in uids)
        expected_ops.extend(
            (None, uid) for uid in (resource_port, *literal_ports, baud)
        )
        require(
            constant(frame, literal_ports[0]) == "0000"
            and constant(frame, literal_ports[1]) == "01"
            and constant(frame, literal_ports[5]) == ("01" if enabled else "0000"),
            "focal ID-query/reset/output Boolean changed",
        )
        for port, value in zip(literal_ports[2:5], VALUES[focal]):
            require(
                struct.unpack(">d", bytes.fromhex(constant(frame, port)))[0] == value,
                "focal connected voltage/slew/current changed",
            )
        require(
            constant(frame, baud) == "00002580", "focal unused baud literal changed"
        )
        control = unique(fp, "fPDCO", resource_dco)
        require(
            control.findtext("conNum") == "-1"
            and control.findtext("DefaultData")
            == '"&#x00;&#x00;&#x00;&#x05;COM' + str(13 - focal) + '"',
            "focal resource default or public exposure changed",
        )
        terminals = frame.findall(f"nodeList/*/termList/*[@uid='{resource_port}']")
        require(
            len(terminals) == 1 and terminals[0].find("dco").get("uid") == resource_dco,
            "focal resource FP-to-diagram identity changed",
        )
        nets.extend(
            (
                (literal_ports[0], call_ports[0][9]),
                (literal_ports[1], call_ports[0][10]),
                (resource_port, call_ports[0][11]),
            )
        )
        nets.extend((literal_ports[i + 1], call_ports[i][10]) for i in range(1, 5))
        for previous, next_ports in zip(call_ports, call_ports[1:]):
            nets.extend(((previous[0], next_ports[8]), (previous[3], next_ports[11])))
        nets.append((call_ports[-1][0], merge))
    operations(frame, expected_ops, "focal root")
    exact_wires(frame, nets, "focal root")
    merge = unique(bd, "mergeErrors", "2758")
    require(
        [t.get("uid") for t in merge.findall("termList/*")]
        == ["2805", "2808", "2811", "2825"]
        and [t.get("uid") for t in merge.findall("dcoList/*")]
        == ["2809", "2812", "2824"],
        "focal error merge order changed",
    )
    return (
        "Focal " + ("ON" if enabled else "OFF") + ": three independent six-call "
        "chains; reset True/query False; V/slew/I before output "
        + str(enabled)
        + "; Close -> merge F3/F2/F1; baud literals unconnected."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("members_archive", type=Path)
    args = parser.parse_args()
    roots = checked_roots(args.members_archive)
    for enabled in (True, False):
        print(
            validate_member(
                roots["1_Focales " + ("ON" if enabled else "OFF") + ".vi"],
                enabled=enabled,
            )
        )


if __name__ == "__main__":
    main()
