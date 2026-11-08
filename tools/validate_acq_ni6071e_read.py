"""Prove original two-card AI read/mean/calibration and three I/O callers."""

from __future__ import annotations

import argparse
import hashlib
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6220_read_error_contract import (
    ALL_MEMBERS_ARCHIVE_SHA256,
    connector_map,
)
from validate_acq_ni6602_writer import operations, primitive
from validate_acq_ni6703_writer import connected_group

MEMBER = "1_ACQ_READ_NI6071E.vi"
FILE_HASHES = {
    "vi.xml": "04C1E9CB96949EE2753ABEF67625F2A33BC77DF08A5E2DF7A6C5B6AFC0C90E1C",
    "vi_BDHb.xml": "6C6CB0D8D885EDC3D0442BA6D6477CEB7FBF3866F33724166A9C097C6D17692A",
    "vi_FPHb.xml": "746A154CEA33A147DBC6F409878034CBE8F913A6A80FDACD8C27A9E9FA71381A",
}
WIRES = {
    "3": (
        ("1160", "885"),
        ("1016", "1707"),
        ("1152", "1001"),
        ("987", "488"),
        ("519", "916"),
        ("71", "294"),
        ("763", "422", "1293"),
        ("168", "1272"),
        ("809", "512"),
        ("418", "531"),
        ("823", "437"),
        ("57", "1299"),
        ("1290", "276"),
        ("670", "2442"),
        ("467", "594"),
        ("597", "979"),
        ("1317", "590"),
        ("1074", "1305", "443"),
    ),
    "869": (("914", "985"), ("999", "1014")),
    "875": (
        ("677", "1015"),
        ("804", "683"),
        ("756", "667"),
        ("659", "680"),
        ("1000", "663"),
        ("1089", "386"),
        ("383", "986"),
        ("1023", "366"),
        ("915", "369"),
        ("363", "392"),
    ),
    "591": (("536", "578"), ("598", "525")),
    "639": (("272", "551"), ("554", "1147")),
}
CALIBRATION = (
    (1, "756", "804"),
    (2, "1023", "1089"),
)
ARRAY_HASHES = {
    "756": "8A367340CEACAAB7BAF68CE961DF5AF980539A622BDBC9F46A6FC7EA9334ECF0",
    "804": "7D7C37273E3847B69082EE61A2132B800AFE20B924B6EF1637B91472D21877A7",
    "1023": "4BD64144BC3D1071452D4FD0AB29C0408D0C454B0CD691F327421F171625097A",
    "1089": "E9D64AC07363C38773A1D6F355864D4365D37A8267B9D7EE3429906C44E0311D",
}


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
                f"NI6071E read XML hash changed: {name}",
            )
            roots[name] = ET.fromstring(data)
    return roots


def decoded_calibration(roots):
    frame = unique(roots["vi_BDHb.xml"], "diag", "875")

    def doubles(uid):
        raw = bytes.fromhex(constant(frame, uid))
        require(
            len(raw) == 4 + 64 * 8 and int.from_bytes(raw[:4], "big") == 64,
            "NI6071E coefficient array dimension changed",
        )
        require(
            hashlib.sha256(raw).hexdigest().upper() == ARRAY_HASHES[uid],
            "NI6071E connected coefficient array changed",
        )
        return struct.unpack(">64d", raw[4:])

    return tuple((doubles(slope), doubles(offset)) for _, slope, offset in CALIBRATION)


def validate_read(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        tuple(t.get("uid") for t in fp.findall("root/ddoList/*"))
        == ("1705", "68", "163", "977", "1072", "761", "297"),
        "NI6071E read local register changed",
    )
    require(
        connector_map(fp)
        == [
            (0, "977"),
            (2, "297"),
            (3, "1705"),
            (8, "1072"),
            (9, "761"),
            (10, "68"),
            (11, "163"),
        ],
        "NI6071E read public connector changed",
    )
    require(
        [t.get("Flags") for t in meta.findall("CPMp/Section/TypeDesc")]
        == [
            "0x0300",
            "-1",
            "0x0600",
            "0x0000",
            "-1",
            "-1",
            "-1",
            "-1",
            "0x0400",
            "0x0500",
            "0x0100",
            "0x0200",
        ],
        "NI6071E read connector/local flags changed",
    )
    require(
        {d.get("uid") for d in bd.findall(".//*[@class='diag']")} == set(WIRES),
        "NI6071E read diagram census changed",
    )
    frames = {uid: unique(bd, "diag", uid) for uid in WIRES}
    operations(
        frames["3"],
        (
            ("mergeErrors", "584"),
            ("label", "1174"),
            ("select", "861"),
            ("forLoop", "510"),
            ("polyIUse", "269"),
            ("forLoop", "612"),
            ("polyIUse", "1269"),
        ),
        "NI6071E read root",
    )
    operations(frames["869"], (), "NI6071E raw arm")
    operations(
        frames["875"],
        (("prim", "675"), ("prim", "651"), ("prim", "377"), ("prim", "357")),
        "NI6071E calibration",
    )
    operations(frames["591"], (("polyIUse", "319"),), "NI6071E C2 mean body")
    operations(frames["639"], (("polyIUse", "359"),), "NI6071E C1 mean body")
    for uid, wires in WIRES.items():
        exact_wires(frames[uid], wires, "NI6071E read " + uid)
    for port, control in (
        ("1707", "1705"),
        ("979", "977"),
        ("1074", "1072"),
        ("488", "297"),
        ("168", "163"),
        ("71", "68"),
        ("763", "761"),
    ):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control,
            "NI6071E read public terminal mapping changed",
        )
    for uid, task, data, count, timeout, err_in, err_out in (
        ("269", "294", "418", "422", "437", "443", "467"),
        ("1269", "1272", "1290", "1293", "1299", "1305", "1317"),
    ):
        call = unique(bd, "polyIUse", uid)
        require(
            call.findtext("label/textRec/text") == '"DAQmx Read.vi"'
            and call.findtext("instanceSelector/menuInstanceUsed") == "08",
            "NI6071E read polymorphic selection changed",
        )
        connected = {t for wire in WIRES["3"] for t in wire}
        active = {0: task, 6: data, 7: count, 9: timeout, 11: err_in, 15: err_out}
        for slot, term in enumerate(call.findall("termList/*")):
            public_term(call, term.get("uid"), slot)
            require(
                (term.get("uid") in connected) == (slot in active)
                and (slot not in active or term.get("uid") == active[slot]),
                "NI6071E read task/data/error/unused port changed",
            )
    root = frames["3"]
    for uid, value in (
        ("670", "00000040"),
        ("809", "00000040"),
        ("57", "3FF0000000000000"),
        ("823", "3FF0000000000000"),
        ("1160", "01"),
    ):
        require(
            constant(root, uid) == value,
            "NI6071E count/timeout/calibration literal changed",
        )
    case = unique(bd, "select", "861")
    require(
        [f.get("uid") for f in case.findall("diagramList/*")] == ["869", "875"]
        and [
            (n.findtext("start"), n.findtext("diagramIdx"))
            for n in case.findall("SelectRangeArray32/*")
        ]
        == [("0", "0"), ("1", "1")],
        "NI6071E calibration Case mapping changed",
    )
    for outer, inner, flags in (
        ("916", ("914", "915"), "2048"),
        ("987", ("985", "986"), "2049"),
        ("1001", ("999", "1000"), "2048"),
        ("1016", ("1014", "1015"), "2049"),
    ):
        tunnel = case.find(f"termList/*[@uid='{outer}']/dco")
        require(
            tunnel is not None
            and tunnel.get("class") == "selTun"
            and tunnel.findtext("objFlags") == flags
            and [t.get("uid") for t in tunnel.findall("termList/*")] == [*inner, outer],
            "NI6071E calibration tunnel direction changed",
        )
    for uid, body, n_port, data_in, inner_data, data_out, inner_out, mean_uid in (
        ("510", "591", "512", "531", "536", "519", "525", "319"),
        ("612", "639", "2442", "276", "272", "1152", "1147", "359"),
    ):
        loop = unique(bd, "forLoop", uid)
        require(
            [f.get("uid") for f in loop.findall("diagramList/*")] == [body]
            and loop.find(f"termList/*[@uid='{n_port}']/dco").get("class") == "lMax"
            and not loop.findall("termList/*/dco[@class='lSR']")
            and not loop.findall("ConditionDCOList/*"),
            "NI6071E mean loop count/conditional scope changed",
        )
        for outer, inner, flags in (
            (data_in, inner_data, "2048"),
            (data_out, inner_out, "2049"),
        ):
            tunnel = loop.find(f"termList/*[@uid='{outer}']/dco")
            require(
                tunnel is not None
                and tunnel.get("class") == "lpTun"
                and tunnel.findtext("objFlags") == flags
                and tunnel.findtext("TunnelType") == "01"
                and [t.get("uid") for t in tunnel.findall("termList/*")]
                == [inner, outer],
                "NI6071E mean auto-index tunnel changed",
            )
        mean = unique(bd, "polyIUse", mean_uid)
        require(
            mean.findtext("label/textRec/text") == '"Mean.vi"',
            "NI6071E mean boundary changed",
        )
        connected = {t for wire in WIRES[body] for t in wire}
        require(
            len(mean.findall("termList/*")) == 3
            and [t.get("uid") in connected for t in mean.findall("termList/*")]
            == [True, True, False],
            "NI6071E Mean error output became consumed",
        )
    for uid, resource, ports in (
        ("675", 1050, ("677", "680", "683")),
        ("651", 1052, ("659", "663", "667")),
        ("377", 1050, ("383", "386", "392")),
        ("357", 1052, ("363", "366", "369")),
    ):
        primitive(bd, uid, resource, ports)
    decoded_calibration(roots)
    merge = unique(bd, "mergeErrors", "584")
    require(
        [t.get("uid") for t in merge.findall("termList/*")] == ["597", "590", "594"]
        and [d.get("uid") for d in merge.findall("dcoList/*")] == ["588", "592"]
        and merge.findtext("objFlags", "0") == "0",
        "NI6071E merge error order/mode changed",
    )
    return (
        "NI6071E: independent C1/C2 Read branches; 1-second timeouts; "
        "N=64 auto-indexed channel means; saved True calibration, 256 coefficients; "
        "raw False arm; error merge C1 before C2, not a data-validity gate"
    )


def validate_io_callers(root):
    expected = (
        (
            "19337",
            "25990",
            "19298",
            "19467",
            "19459",
            "19475",
            "19483",
            "19491",
            "19499",
        ),
        ("647", "7386", "8081", "1725", "1628", "7485", "7599", "2234", "2326"),
        (
            "55456",
            "41713",
            "55618",
            "55592",
            "55584",
            "55600",
            "55608",
            "55630",
            "55638",
        ),
    )
    for (
        call_uid,
        frame_uid,
        count_uid,
        c1_task_uid,
        c2_task_uid,
        c1_convert_uid,
        c2_convert_uid,
        c1_local_uid,
        c2_local_uid,
    ) in expected:
        frame = unique(root, "diag", frame_uid)
        call = unique(root, "iUse", call_uid)
        terms = call.findall("termList/*")
        require(
            call in frame.findall("zPlaneList/*")
            and constant(frame, count_uid) == "000003E8",
            "NI6071E root I/O caller/count changed",
        )
        require(
            connected_group(frame, terms[9].get("uid"))
            == {terms[9].get("uid"), count_uid},
            "NI6071E root sample-count edge changed",
        )
        for task_uid, slot, index in ((c1_task_uid, 11, "23"), (c2_task_uid, 10, "24")):
            alias = unique(root, "gRef", task_uid)
            port = alias.find("termList/*").get("uid")
            require(
                alias.findtext("termList/*/dco/paramIdx") == index
                and alias.findtext("termList/*/objFlags") == "4096"
                and connected_group(frame, terms[slot].get("uid"))
                == {terms[slot].get("uid"), port},
                "NI6071E root task bank changed",
            )
        for converter_uid, local_uid, slot, index in (
            (c1_convert_uid, c1_local_uid, 3, "19"),
            (c2_convert_uid, c2_local_uid, 2, "20"),
        ):
            converter = unique(root, "prim", converter_uid)
            alias = unique(root, "gRef", local_uid)
            outs, ins = converter.findall("termList/*")
            port = alias.find("termList/*").get("uid")
            require(
                converter.findtext("primResID") == "1168"
                and alias.findtext("termList/*/dco/paramIdx") == index
                and alias.findtext("termList/*/objFlags") == "36864"
                and connected_group(frame, ins.get("uid"))
                == {terms[slot].get("uid"), ins.get("uid")}
                and {outs.get("uid"), port} <= connected_group(frame, outs.get("uid")),
                "NI6071E root output bank/converter changed",
            )
        for slot, term in enumerate(terms):
            public_term(call, term.get("uid"), slot)
        require(
            not any(
                terms[8].get("uid") in {t.get("uid") for t in s.findall("termList/*")}
                for s in frame.findall("signalList/*")
            ),
            "NI6071E root I/O incoming error became wired",
        )
    return (
        "Three I/O callers: requested 1000 samples/channel, task locals 23/24; "
        "C1/C2 results -> local banks 19/20; error input unwired. "
        "Separate pilot-test call 287 remains governed by the AI-fallback proof."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("members_archive", type=Path)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_read(checked_roots(args.members_archive)))
    print(validate_io_callers(checked_root(args.root_archive)))


if __name__ == "__main__":
    main()
