"""Prove DIO96 saved read/write/error/alias flow and three root I/O edges."""

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

MEMBER = "1_ACQ_RW_DIO96.vi"
FILE_HASHES = {
    "vi.xml": "41D0E4DE78056E85A1656918E996F793EFDBF0B777CB0D01F1C0C201341855E3",
    "vi_BDHb.xml": "6646B660BA55A05388A670E9606CB85E44DBDDC5F8B89390E1DEAA6A9787830A",
    "vi_FPHb.xml": "2B237B831573ADFAFF9642CF0F24AB442988B0A7CCF7FEEE8ED49527EE372AC5",
}
DDO_ORDER = (
    "1280",
    "60",
    "720",
    "2651",
    "2791",
    "2801",
    "3462",
    "3472",
    "4127",
    "4137",
    "4867",
    "4877",
    "5468",
    "5478",
    "5469",
)
PORTS = (
    (
        "347",
        "350",
        "353",
        "356",
        "359",
        "362",
        "365",
        "368",
        "373",
        "376",
        "379",
        "382",
        "385",
        "388",
        "391",
        "394",
    ),
    (
        "1766",
        "1848",
        "1862",
        "2679",
        "2682",
        "2685",
        "2688",
        "2691",
        "2694",
        "2697",
        "2707",
        "2734",
        "2743",
        "3049",
        "3057",
        "3061",
    ),
    (
        "3491",
        "3494",
        "3497",
        "3949",
        "3952",
        "3955",
        "3958",
        "3961",
        "3964",
        "3967",
        "3970",
        "3973",
        "3976",
        "3981",
        "3984",
        "3990",
    ),
    (
        "2847",
        "2850",
        "2853",
        "2856",
        "2859",
        "2862",
        "2865",
        "2868",
        "2871",
        "2874",
        "2877",
        "2880",
        "2883",
        "2886",
        "2889",
        "2892",
    ),
    (
        "674",
        "710",
        "714",
        "733",
        "4629",
        "4632",
        "4635",
        "4773",
        "4776",
        "4779",
        "4782",
        "4786",
        "4789",
        "4792",
        "4795",
        "4798",
    ),
    (
        "835",
        "844",
        "852",
        "875",
        "879",
        "4897",
        "4900",
        "4904",
        "5292",
        "5295",
        "5298",
        "5301",
        "5304",
        "5307",
        "5310",
        "5313",
    ),
)
CALL_UIDS = ("232", "667", "1028", "2840", "38", "742")
BODY_WIRES = (
    ("5669", "382"),
    ("4798", "5301"),
    ("2892", "4786"),
    ("3990", "2880"),
    ("3061", "3973"),
    ("394", "2734"),
    ("4505", "835"),
    ("4502", "674"),
    ("4499", "2847"),
    ("5343", "4904"),
    ("5330", "844"),
    ("4816", "710"),
    ("4829", "4773"),
    ("68", "1312", "4496"),
    ("1547", "3491"),
    ("1529", "1766"),
    ("1316", "347"),
    ("3958", "4010"),
    ("2688", "3084"),
    ("1666", "2868"),
    ("538", "2850"),
    ("365", "1479"),
    ("5313", "4024"),
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
                f"DIO96 exchange XML hash changed: {name}",
            )
            roots[name] = ET.fromstring(data)
    return roots


def validate_exchange(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        tuple(t.get("uid") for t in fp.findall("root/ddoList/*")) == DDO_ORDER,
        "DIO96 front-panel local-index register changed",
    )
    require(
        connector_map(fp)
        == [
            (0, "4137"),
            (1, "4877"),
            (2, "5478"),
            (3, "5469"),
            (4, "60"),
            (5, "720"),
            (6, "2801"),
            (7, "3472"),
            (8, "1280"),
        ],
        "DIO96 connector map changed",
    )
    require(
        [t.get("Flags") for t in meta.findall("CPMp/Section/TypeDesc")]
        == [
            "0x0009",
            "0x0B00",
            "0x0D00",
            "0x0E00",
            "0x0100",
            "0x0200",
            "0x0500",
            "0x0700",
            "0x0000",
        ],
        "DIO96 connector/local flags changed",
    )
    sequence = unique(bd, "sequence", "8872")
    require(
        sequence in bd.find("root/zPlaneList")
        and [f.get("uid") for f in sequence.findall("diagramList/*")]
        == ["9110", "1684"]
        and {d.get("uid") for d in bd.findall(".//*[@class='diag']")}
        == {"3", "9110", "1684"},
        "DIO96 ordered frame scope changed",
    )
    root, first, body = (
        bd.find("root"),
        unique(bd, "diag", "9110"),
        unique(bd, "diag", "1684"),
    )
    require(
        [(n.get("class"), n.get("uid")) for n in root.findall("zPlaneList/*")]
        == [(None, "5473"), (None, "1282"), ("sequence", "8872")],
        "DIO96 root operation census changed",
    )
    require(
        not first.findall("zPlaneList/*[@class]"), "DIO96 first frame gained operation"
    )
    require(
        {(n.get("class"), n.get("uid")) for n in body.findall("zPlaneList/*[@class]")}
        == {
            ("gRef", "5340"),
            ("polyIUse", "742"),
            ("gRef", "4826"),
            ("polyIUse", "38"),
            ("nMux", "425"),
            ("gRef", "4007"),
            ("polyIUse", "1028"),
            ("gRef", "3081"),
            ("polyIUse", "667"),
            ("nMux", "913"),
            ("gRef", "32"),
            ("gRef", "843"),
            ("polyIUse", "232"),
            ("gRef", "854"),
            ("polyIUse", "2840"),
        },
        "DIO96 body operation census changed",
    )
    exact_wires(root, (("5473", "5673"), ("4028", "1282")), "DIO96 root")
    exact_wires(first, (), "DIO96 first frame")
    exact_wires(body, BODY_WIRES, "DIO96 exchange body")
    for outer, inner, dco, flags in (
        ("5673", ("5665", "5669", "5673"), "5663", "2048"),
        ("4028", ("4013", "4024", "4028"), "4005", "2049"),
    ):
        tunnel = sequence.find(f"termList/*[@uid='{outer}']/dco")
        require(
            tunnel is not None
            and tunnel.get("class") == "seqTun"
            and tunnel.get("uid") == dco
            and tunnel.findtext("objFlags") == flags
            and tuple(t.get("uid") for t in tunnel.findall("termList/*")) == inner,
            "DIO96 error sequence tunnel changed",
        )
    refs = (
        ("32", "68", "1", "4096", "1"),
        ("854", "1666", "9", "4096", "1"),
        ("4826", "4829", "11", "0", "1"),
        ("5340", "5343", "13", "0", "1"),
        ("843", "1479", "2", "36864", "0"),
        ("3081", "3084", "5", "32768", "0"),
        ("4007", "4010", "7", "32768", "0"),
    )
    require(
        {n.get("uid") for n in bd.findall(".//*[@class='gRef']")}
        == {row[0] for row in refs},
        "DIO96 local alias census changed",
    )
    for uid, port, index, flags, dco_flags in refs:
        node = unique(bd, "gRef", uid)
        require(
            node.find("termList/*").get("uid") == port
            and node.findtext("termList/*/dco/paramIdx") == index
            and node.findtext("termList/*/objFlags", "0") == flags
            and node.findtext("termList/*/dco/objFlags", "0") == dco_flags,
            "DIO96 local identity/direction changed",
        )
    for uid, fields in (("913", (0, 1, 2)), ("425", (3, 4, 5))):
        mux = unique(bd, "nMux", uid)
        require(
            tuple(int(t.findtext("dco/i", "0")) for t in mux.findall("termList/*")[1:])
            == fields,
            "DIO96 task-cluster field order changed",
        )
    connected = {
        t.get("uid")
        for s in body.findall("signalList/*")
        for t in s.findall("termList/*")
    }
    for index, (uid, ports) in enumerate(zip(CALL_UIDS, PORTS)):
        node = unique(bd, "polyIUse", uid)
        reading = index < 3
        require(
            node.findtext("label/textRec/text")
            == ('"DAQmx Read.vi"' if reading else '"DAQmx Write.vi"')
            and node.findtext("instanceSelector/menuInstanceUsed")
            == ("0F" if reading else "0E"),
            "DIO96 polymorphic boundary changed",
        )
        require(
            tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
            "DIO96 call port identities changed",
        )
        for slot, port in enumerate(ports):
            public_term(node, port, slot)
        expected_connected = {0, 6, 11, 15} if reading else {0, 1, 7, 11, 15}
        require(
            {slot for slot, port in enumerate(ports) if port in connected}
            == expected_connected,
            "DIO96 unwired task/count/timeout or other port changed",
        )
    for uid in ("538", "4816", "5330"):
        require(constant(body, uid) == "01", "DIO96 autoStart is not True")
    for port, control in (("5473", "5469"), ("1282", "1280")):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control,
            "DIO96 public error terminal changed",
        )
    return (
        "DIO96: Read C3/C4/C5 -> Write C3/C4/C5; public error chain; "
        "read data assigned without error guard; independent DI/DO task fields; "
        "autoStart True; timeout/task/count ports unwired"
    )


def validate_callers(root):
    rows = (
        (
            "19376",
            "25990",
            ("19531", "19539", "19547"),
            ("19555", "19563", "19571"),
            ("19507", "19515", "19523"),
            ("19579", "19587", "19595"),
            "19667",
            "19337",
            "19408",
        ),
        (
            "686",
            "7386",
            ("7937", "8025", "8127"),
            ("2344", "2362", "2378"),
            ("7655", "7748", "7836"),
            ("2336", "2352", "2370"),
            "180",
            "647",
            "278",
        ),
        (
            "55502",
            "41713",
            ("55670", "55678", "55686"),
            ("55694", "55702", "55710"),
            ("55646", "55654", "55662"),
            ("55718", "55726", "55734"),
            "55806",
            "55456",
            "55532",
        ),
    )
    require(
        {
            n.get("uid")
            for n in root.findall(".//*[@class='iUse']")
            if n.findtext("label/textRec/text") == f'"{MEMBER}"'
        }
        == {r[0] for r in rows},
        "DIO96 root caller census changed",
    )
    for (
        uid,
        diagram,
        output_convs,
        output_locals,
        input_convs,
        input_locals,
        tasks,
        ai,
        ao,
    ) in rows:
        frame, call = unique(root, "diag", diagram), unique(root, "iUse", uid)
        require(call in frame.findall("zPlaneList/*"), "DIO96 caller moved frame")
        terms = call.findall("termList/*")
        require(len(terms) == 9, "DIO96 root connector size changed")
        for slot, term in enumerate(terms):
            public_term(call, term.get("uid"), slot)
        for convs, locals_, indices, slots, resource, direction in (
            (output_convs, output_locals, (17, 15, 13), (0, 1, 2), "1169", "4096"),
            (input_convs, input_locals, (18, 16, 14), (5, 6, 7), "1168", "36864"),
        ):
            for conv_uid, local_uid, bank, slot in zip(convs, locals_, indices, slots):
                conv, local = (
                    unique(root, "prim", conv_uid),
                    unique(root, "gRef", local_uid),
                )
                require(
                    conv in frame.findall("zPlaneList/*")
                    and local in frame.findall("zPlaneList/*")
                    and conv.findtext("primResID") == resource
                    and conv.findtext("primIndex")
                    == ("157" if resource == "1169" else "156")
                    and local.findtext("termList/*/dco/paramIdx") == str(bank)
                    and local.findtext("termList/*/objFlags") == direction,
                    "DIO96 root bank/converter changed",
                )
                ports = conv.findall("termList/*")
                require(len(ports) == 2, "DIO96 root converter shape changed")
                array_port, cluster_port = (
                    (ports[0], ports[1]) if resource == "1169" else (ports[1], ports[0])
                )
                require(
                    connected_group(frame, terms[slot].get("uid"))
                    == {terms[slot].get("uid"), array_port.get("uid")}
                    and connected_group(frame, cluster_port.get("uid"))
                    == {cluster_port.get("uid"), local.find("termList/*").get("uid")},
                    "DIO96 root data edge changed",
                )
        task = unique(root, "gRef", tasks)
        require(
            task.findtext("termList/*/dco/paramIdx") == "22",
            "DIO96 root task local changed",
        )
        ai_node, ao_node = unique(root, "iUse", ai), unique(root, "iUse", ao)
        require(
            ai_node.findtext("label/textRec/text") == '"1_ACQ_READ_NI6071E.vi"'
            and ao_node.findtext("label/textRec/text") == '"1_ACQ_WRITE_NI6703.vi"',
            "DIO96 root error peer changed",
        )
        for slot, peer in (
            (4, task.find("termList/*")),
            (3, ai_node.findall("termList/*")[0]),
            (8, ao_node.findall("termList/*")[11]),
        ):
            require(
                connected_group(frame, terms[slot].get("uid"))
                == {terms[slot].get("uid"), peer.get("uid")},
                "DIO96 root task/error edge changed",
            )
    return (
        "DIO96 root: all three callers preserve C3/C4/C5 banks via locals "
        "OUT 17/15/13, IN 18/16/14; task local 22; NI6071E error -> DIO96 -> NI6703"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("members_archive", type=Path)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_exchange(checked_roots(args.members_archive)))
    print(validate_callers(checked_root(args.root_archive)))


if __name__ == "__main__":
    main()
