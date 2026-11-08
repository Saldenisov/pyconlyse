"""Pin all six dormant NI6259 diagrams without activating their call paths.

The copied initializer is not NI6220: eight +/-0.2 V channels, input-mode
code0x277A, and Start Trigger (None). Public errors are unconnected. The
reader fixes mean-loop N=8 independently of requested samples. Standard
DAQ/Mean returns and the unwritten public error seed remain boundaries.
"""

from __future__ import annotations

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term, tag_array
from validate_acq_helper_source_facets import ARCHIVE, validate_dormant
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import (
    ALL_MEMBERS_ARCHIVE_SHA256,
    connector_map,
)
from validate_acq_ni6602_writer import operations, primitive
from validate_acq_runtime_io_frame import heap_type

INIT = "1_ACQ_INIT_NI6259.vi"
READ = "1_ACQ_READ_NI6259.vi"
SOURCE_HASHES = {
    INIT: "A8DE6D36566F3EF97F0B69B5C7E2AC6E8BCEAF8C48667D60A565DE05A09A323E",
    READ: "89BC9BE30E5F216474E25F47DF562316F970E0AF118AD5E24FC1E9E0956B7963",
}
FILE_HASHES = {
    INIT: {
        "vi.xml": "EDCB027E02E0F6FCFE2B0F36756A447FCCE1D6579107C95F913092CA3BCB49B3",
        "vi_BDHb.xml": (
            "52E805DE43C2D19736DC36FC335C16B47AED9171E37161878CF1EF69554FE801"
        ),
        "vi_FPHb.xml": (
            "9C1626A92E081063F0A6C933498AF0F72FD380513C2F42B6E174D2CEDC1DD99F"
        ),
    },
    READ: {
        "vi.xml": "15F1B7E7A71E2CFF5E02BE10A08045E9D81AB80B3D3D084154C6563E3A5BC5B3",
        "vi_BDHb.xml": (
            "F0D0B0E8E2FA8E47CF94B28E06E73A4C067DF066D33323EFD76657F5D21A1C2A"
        ),
        "vi_FPHb.xml": (
            "F70192D6DE743D11D26B1F449E088E2EC9FDA2F233BFCBA3AB9BE6C15CAF0173"
        ),
    },
}
INIT_WIRES = {
    "3": (
        ("842", "1351"),
        ("2575", "3464"),
        ("3390", "2411"),
        ("3413", "2402"),
        ("3539", "2737"),
        ("3638", "2682"),
        ("2677", "2700"),
        ("3649", "2638"),
        ("3659", "2635"),
        ("2644", "2694"),
        ("3670", "2620"),
        ("3680", "2602"),
        ("2549", "2584"),
        ("2469", "2566"),
        ("3693", "2399"),
        ("2442", "2525"),
        ("2408", "2457"),
        ("3719", "2423"),
        ("3732", "2417"),
        ("2690", "2429"),
        ("2686", "2396"),
    ),
    "2798": (
        ("3382", "2839"),
        ("3313", "2833"),
        ("1345", "2859"),
        ("616", "2845"),
        ("2703", "2915"),
        ("2740", "2895"),
        ("2697", "2824"),
        ("2951", "2693"),
        ("2850", "2689"),
    ),
}
READ_WIRES = {
    "3": (
        ("1187", "1310"),
        ("1290", "276", "1192", "1516"),
        ("1317", "979"),
        ("1160", "885"),
        ("1016", "1707"),
        ("1152", "1001"),
        ("763", "1293"),
        ("168", "1272"),
        ("57", "1299"),
        ("670", "2442"),
        ("1074", "1305"),
    ),
    "869": (("999", "1014"),),
    "875": (
        ("677", "1015"),
        ("804", "683"),
        ("756", "667"),
        ("659", "680"),
        ("1000", "663"),
    ),
    "639": (("272", "551"), ("554", "1147")),
}
COEFFICIENT_HASHES = {
    "756": "8A367340CEACAAB7BAF68CE961DF5AF980539A622BDBC9F46A6FC7EA9334ECF0",
    "804": "7D7C37273E3847B69082EE61A2132B800AFE20B924B6EF1637B91472D21877A7",
}


def checked_roots(path=ARCHIVE):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper()
        == ALL_MEMBERS_ARCHIVE_SHA256,
        "original17-member archive changed",
    )
    result = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original member population changed")
        for member, hashes in FILE_HASHES.items():
            result[member] = {}
            for name, expected in hashes.items():
                raw = archive.read(member + "/" + name)
                require(
                    hashlib.sha256(raw).hexdigest().upper() == expected,
                    "NI6259 XML hash changed: " + member + "/" + name,
                )
                result[member][name] = ET.fromstring(raw)
    return result


def tunnel(loop, outer, inner, flags, indexed=False):
    node = loop.find(f"termList/*[@uid='{outer}']/dco")
    require(
        node is not None
        and node.get("class") == "lpTun"
        and node.findtext("objFlags") == flags
        and node.findtext("TunnelType") == ("01" if indexed else None)
        and [p.get("uid") for p in node.findall("termList/*")] == [inner, outer],
        "NI6259 loop tunnel changed: " + outer,
    )


def typed(node, port, meta, kind, rank=None):
    term = node.find(f"termList/*[@uid='{port}']")
    descriptor = term.findtext("dco/typeDesc", "") if term is not None else ""
    require(
        descriptor.startswith("TypeID(") and descriptor.endswith(")"),
        "NI6259 typed port missing: " + port,
    )
    desc, flat = heap_type(meta, int(descriptor[7:-1]))
    require(desc.get("Type") == kind, "NI6259 port type changed: " + port)
    if rank is not None:
        elements = desc.findall("TypeDesc")
        require(
            len(desc.findall("Dimension")) == rank
            and len(elements) == 1
            and flat[int(elements[0].get("TypeID"))].get("Type") == "NumFloat64",
            "NI6259 DBL array rank/type changed: " + port,
        )


def validate_initializer(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        connector_map(fp)
        == [(2, "128"), (3, "580"), (4, "266"), (5, "2322"), (7, "1280")],
        "NI6259 initializer public connector changed",
    )
    require(
        [t.get("Flags") for t in meta.findall("CPMp/Section/TypeDesc")]
        == ["-1", "-1", "0x0300", "0x0100", "0x0200", "0x0400", "-1", "0x0000"],
        "NI6259 initializer public/local mapping changed",
    )
    require(
        tuple(n.get("uid") for n in fp.findall("root/ddoList/*"))
        == ("1280", "580", "266", "128", "2322"),
        "NI6259 initializer local register changed",
    )
    for uid, control in (
        ("1282", "1280"),
        ("583", "580"),
        ("268", "266"),
        ("131", "128"),
        ("2324", "2322"),
    ):
        require(
            unique(bd, "fPTerm", uid).find("dco").get("uid") == control,
            "NI6259 initializer public terminal changed",
        )
    require(
        tuple(d.get("uid") for d in bd.findall(".//*[@class='diag']"))
        == tuple(INIT_WIRES),
        "NI6259 initializer diagram census changed",
    )
    frames = {uid: unique(bd, "diag", uid) for uid in INIT_WIRES}
    operations(
        frames["3"],
        (
            ("gRef", "3454"),
            ("gRef", "3402"),
            ("gRef", "3381"),
            ("forLoop", "2680"),
            ("iUse", "2629"),
            ("propNode", "2561"),
            ("polyIUse", "2454"),
            ("polyIUse", "2393"),
        ),
        "NI6259 initializer",
    )
    operations(frames["2798"], (("polyIUse", "2818"),), "NI6259 channel body")
    for uid, wires in INIT_WIRES.items():
        exact_wires(frames[uid], wires, "NI6259 initializer " + uid)
    require(
        call_names(meta)
        == {
            "2818": "DAQmx Create Channel (AI-Voltage-Basic).vi",
            "2393": "DAQmx Timing (Sample Clock).vi",
            "2629": "DAQmx Create Task.vi",
            "2454": "DAQmx Start Trigger (None).vi",
        },
        "NI6259 initializer concrete callees changed",
    )
    connected = {p for wires in INIT_WIRES.values() for wire in wires for p in wire}
    for uid, klass, label, selector, active in (
        ("2629", "iUse", "DAQmx Create Task.vi", None, (1, 2, 4, 15)),
        (
            "2818",
            "polyIUse",
            "DAQmx Create Virtual Channel.vi",
            "02",
            (0, 1, 2, 3, 4, 5, 9, 11, 15),
        ),
        ("2393", "polyIUse", "DAQmx Timing.vi", "02", (0, 1, 2, 4, 5, 7, 9, 11, 15)),
        ("2454", "polyIUse", "DAQmx Trigger.vi", "02", (0, 4, 11, 15)),
    ):
        node = unique(bd, klass, uid)
        require(
            node.findtext("label/textRec/text") == '"' + label + '"'
            and node.findtext("instanceSelector/menuInstanceUsed") == selector
            and len(node.findall("termList/*")) == 16,
            "NI6259 call selection changed: " + uid,
        )
        for slot, term in enumerate(node.findall("termList/*")):
            public_term(node, term.get("uid"), slot)
            require(
                (term.get("uid") in connected) == (slot in active),
                "NI6259 connected call slot changed: " + uid,
            )
    require(
        {
            (n.get("uid"), n.findtext("termList/*/dco/paramIdx"))
            for n in bd.findall(".//*[@class='gRef']")
        }
        == {("3454", "4"), ("3402", "2"), ("3381", "3")},
        "NI6259 public error locals became accessed",
    )
    for uid, flags, dco_flags in (
        ("3454", "32768", None),
        ("3402", None, "1"),
        ("3381", None, "1"),
    ):
        ref = unique(bd, "gRef", uid)
        require(
            ref.findtext("termList/*/objFlags") == flags
            and ref.findtext("termList/*/dco/objFlags") == dco_flags,
            "NI6259 local read/write direction changed",
        )
    require(
        not connected.intersection(
            ("583", "1282", "2593", "2665", "1770", "1808", "3094", "3706")
        ),
        "NI6259 disconnected errors or leftover constants became used",
    )
    frame, body = frames["3"], frames["2798"]
    require(
        tag_array(constant(frame, "842")) == [f"11/ai{i}" for i in range(8)],
        "NI6259 physical channel list changed",
    )
    for uid, value in (
        ("3638", "00000008"),
        ("3539", "0000286C"),
        ("3649", "01"),
        ("3659", "0000000943315F4E4936323230"),
        ("3670", "01"),
        ("3680", "000028B9"),
        ("3693", "000027C2"),
        ("3719", "00002828"),
        ("3732", "0000000C4F6E626F617264436C6F636B"),
    ):
        require(
            constant(frame, uid) == value, "NI6259 connected literal changed: " + uid
        )
    for uid, value in (
        ("616", "0000277A"),
        ("3313", "3FC999999999999A"),
        ("3382", "BFC999999999999A"),
    ):
        require(constant(body, uid) == value, "NI6259 channel setting changed: " + uid)
    loop = unique(bd, "forLoop", "2680")
    require(
        loop.find("termList/*[@uid='2682']/dco").get("class") == "lMax"
        and not loop.findall("srDCOList/*")
        and not loop.findall("ConditionDCOList/*"),
        "NI6259 channel loop bound/state changed",
    )
    for outer, inner, flags, indexed in (
        ("2686", "2689", "2049", False),
        ("2690", "2693", "2049", False),
        ("2694", "2697", "2048", False),
        ("2700", "2703", "2048", False),
        ("2737", "2740", "2048", False),
        ("1351", "1345", "16779264", True),
    ):
        tunnel(loop, outer, inner, flags, indexed)
    prop = unique(bd, "propNode", "2561")
    require(
        [
            (p.findtext("PropItemCode"), p.findtext("objFlags"))
            for p in prop.findall(".//*[@class='propItemInfo']")
        ]
        == [("6410", "4096"), ("6182", "4096")],
        "NI6259 Read property write contract changed",
    )
    return {
        "diagrams": 2,
        "direct_nets": 30,
        "channels": 8,
        "trigger": "DAQmx Start Trigger (None).vi",
        "public_error_in_consumed": False,
        "public_error_out_written": False,
    }


def coefficients(roots):
    frame = unique(roots["vi_BDHb.xml"], "diag", "875")
    result = []
    for uid in ("756", "804"):
        raw = bytes.fromhex(constant(frame, uid))
        require(
            len(raw) == 516
            and raw[:4] == bytes.fromhex("00000040")
            and hashlib.sha256(raw).hexdigest().upper() == COEFFICIENT_HASHES[uid],
            "NI6259 inactive coefficient array changed",
        )
        result.append(struct.unpack(">64d", raw[4:]))
    return tuple(result)


def validate_reader(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        connector_map(fp)
        == [(0, "977"), (3, "1705"), (8, "1072"), (9, "761"), (11, "163")],
        "NI6259 reader public connector changed",
    )
    require(
        [t.get("Flags") for t in meta.findall("CPMp/Section/TypeDesc")]
        == [
            "0x0200",
            "-1",
            "-1",
            "0x0000",
            "-1",
            "-1",
            "-1",
            "-1",
            "0x0300",
            "0x0400",
            "-1",
            "0x0100",
        ],
        "NI6259 reader public/local mapping changed",
    )
    for uid, control in (
        ("979", "977"),
        ("1707", "1705"),
        ("1074", "1072"),
        ("763", "761"),
        ("168", "163"),
    ):
        require(
            unique(bd, "fPTerm", uid).find("dco").get("uid") == control,
            "NI6259 reader public terminal changed",
        )
    require(
        tuple(d.get("uid") for d in bd.findall(".//*[@class='diag']"))
        == tuple(READ_WIRES),
        "NI6259 reader diagram census changed",
    )
    frames = {uid: unique(bd, "diag", uid) for uid in READ_WIRES}
    for uid, ops in (
        (
            "3",
            (
                ("prim", "1181"),
                ("label", "1174"),
                ("select", "861"),
                ("forLoop", "612"),
                ("polyIUse", "1269"),
            ),
        ),
        ("869", ()),
        ("875", (("prim", "675"), ("prim", "651"))),
        ("639", (("polyIUse", "359"),)),
    ):
        operations(frames[uid], ops, "NI6259 reader " + uid)
        exact_wires(frames[uid], READ_WIRES[uid], "NI6259 reader " + uid)
    require(
        call_names(meta)
        == {
            "1269": "DAQmx Read (Analog 2D DBL NChan NSamp).vi",
            "359": "NI_AALBase.lvlib:Mean (DBL).vi",
        },
        "NI6259 reader concrete callees changed",
    )
    read = unique(bd, "polyIUse", "1269")
    require(
        read.findtext("label/textRec/text") == '"DAQmx Read.vi"'
        and read.findtext("instanceSelector/menuInstanceUsed") == "08"
        and len(read.findall("termList/*")) == 16,
        "NI6259 Read contract changed",
    )
    connected = {p for wire in READ_WIRES["3"] for p in wire}
    for slot, term in enumerate(read.findall("termList/*")):
        public_term(read, term.get("uid"), slot)
        require(
            (term.get("uid") in connected) == (slot in (0, 6, 7, 9, 11, 15)),
            "NI6259 Read connected slot changed",
        )
    for uid, value in (
        ("670", "00000008"),
        ("57", "BFF0000000000000"),
        ("1160", "0000"),
    ):
        require(
            constant(frames["3"], uid) == value, "NI6259 reader literal changed: " + uid
        )
    loop = unique(bd, "forLoop", "612")
    require(
        loop.find("termList/*[@uid='2442']/dco").get("class") == "lMax"
        and not loop.findall("srDCOList/*")
        and not loop.findall("ConditionDCOList/*"),
        "NI6259 mean loop state changed",
    )
    tunnel(loop, "276", "272", "2048", True)
    tunnel(loop, "1152", "1147", "2049", True)
    mean = unique(bd, "polyIUse", "359")
    require(
        mean.findtext("label/textRec/text") == '"Mean.vi"'
        and tuple(t.get("uid") for t in mean.findall("termList/*"))
        == ("551", "554", "557")
        and not any("557" in w for w in READ_WIRES["639"]),
        "NI6259 Mean/error output contract changed",
    )
    for slot, port in enumerate(("551", "554", "557")):
        public_term(mean, port, slot)
    typed(read, "1290", meta, "Array", 2)
    typed(mean, "551", meta, "Array", 1)
    typed(mean, "554", meta, "NumFloat64")
    case = unique(bd, "select", "861")
    require(
        [
            (r.findtext("start"), r.findtext("diagramIdx"))
            for r in case.findall("SelectRangeArray32/*")
        ]
        == [("0", "0"), ("1", "1")],
        "NI6259 raw/calibrated Case polarity changed",
    )
    for outer, inner, flags in (
        ("1001", ("999", "1000"), "2048"),
        ("1016", ("1014", "1015"), "2049"),
    ):
        t = case.find(f"termList/*[@uid='{outer}']/dco")
        require(
            t.get("class") == "selTun"
            and t.findtext("objFlags") == flags
            and [p.get("uid") for p in t.findall("termList/*")] == [*inner, outer],
            "NI6259 raw/calibrated tunnel changed",
        )
    for uid, resource, ports in (
        ("1181", 1809, ("1187", "1192")),
        ("675", 1050, ("677", "680", "683")),
        ("651", 1052, ("659", "663", "667")),
    ):
        primitive(bd, uid, resource, ports)
    for uid, ports in (("675", ("677", "680", "683")), ("651", ("659", "663", "667"))):
        for port in ports:
            typed(unique(bd, "prim", uid), port, meta, "Array", 1)
    coefficients(roots)
    return {
        "diagrams": 4,
        "direct_nets": 19,
        "mean_loop_limit": 8,
        "timeout_seconds": -1.0,
        "saved_calibration": False,
        "mean_error_consumed": False,
        "driver_failure_data_proven": False,
    }


def validate_all():
    excluded = validate_dormant()
    roots = checked_roots()
    return {
        "initializer": validate_initializer(roots[INIT]),
        "reader": validate_reader(roots[READ]),
        "static_inbound_calls": excluded["static_inbound_calls"],
        "whole_acquisition_closed": False,
        "native_evidence_complete": False,
        "hardware_executed": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate_all(), sort_keys=True))
