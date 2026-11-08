"""Check final ACQ cleanup and TPG300 Close dataflow without device access.

Usage: python tools/validate_acq_final_cleanup.py ROOT_EXPORT_ZIP TPG_CLOSE_ZIP
Only reads saved XML. Does not open LabVIEW or import a hardware adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from build_acq_saved_diagram_census import call_names
from validate_acq_modulator_start_event_guards import checked_root, require, unique

TPG_SOURCE_SHA256 = "308FA6A146F3F105D6D5A0CFD925F00ED1BCDD76EAA537E4B0B87569985C7B0D"
TPG_ARCHIVE_SHA256 = "D0140C8A69938D3957566F5D8B5FD51021F445C6D5EE54CD0ABD878CB6688CDC"
TPG_FILE_HASHES = {
    "vi.xml": "43E445EFE1EA72AF3C7218BEAD5D5E1F52905B3CD2857CFD4EDD26095F2BA1E3",
    "vi_BDHb.xml": "2B43CC3D94DF25825DCE6A3D7E799D8C9ACDCB6D6D84C20DA6B1D7DE0BAA7782",
    "vi_FPHb.xml": "6325E49259DA73B714406AC5FC2949F40283DB29F7ED51DAE4A24925961C976D",
}
VARIABLES = (
    "C1NI6071E",
    "C2NI6071E",
    "C3_IN_DIO96",
    "C3_OUT_DIO96",
    "C4_IN_DIO96",
    "C4_OUT_DIO96",
    "C5_IN_DIO96",
    "C5_OUT_DIO96",
    "C6NI6703",
    "C7NI6703",
    "C8NI6703",
    "C9NI6703",
    "C1011NI6602",
    "C12NI1409",
    "DPC",
    "DPS",
    "EPC",
    "EPS",
    "VAM-A",
    "VAD",
    "VAM-S",
    "VDD",
    "VDM-A",
    "VDM-S",
    "VTA",
    "VTL",
    "VTS",
)


def wires(frame):
    return {
        frozenset(t.get("uid") for t in s.findall("termList/*"))
        for s in frame.findall("signalList/*")
    }


def exact_wires(frame, expected, label):
    require(
        len(frame.findall("signalList/*")) == len(expected)
        and wires(frame) == {frozenset(group) for group in expected},
        f"{label} wire set changed",
    )


def public_term(node, uid, slot):
    terms = [t for t in node.findall("termList/*") if t.get("uid") == uid]
    require(
        len(terms) == 1 and int(terms[0].findtext("dco/paramIdx") or "0") == slot,
        f"call terminal {uid} connector slot changed",
    )


def constant(frame, uid):
    matches = frame.findall(f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue")
    require(len(matches) == 1, f"constant {uid} absent or duplicated")
    return matches[0].text


def tag_array(hex_value):
    payload = bytes.fromhex(hex_value)
    require(len(payload) >= 4, "cleanup URI array truncated")
    count = int.from_bytes(payload[:4], "big")
    offset = 4
    values = []
    for _ in range(count):
        require(offset + 4 <= len(payload), "cleanup URI length absent")
        size = int.from_bytes(payload[offset : offset + 4], "big")
        offset += 4
        require(offset + size <= len(payload), "cleanup URI bytes truncated")
        values.append(payload[offset : offset + size].decode("ascii"))
        offset += size
    require(offset == len(payload), "cleanup URI array trailing bytes")
    return values


def validate_cleanup_tree(root, metadata):
    sequence = unique(root, "sequence", "359")
    frames = sequence.find("diagramList")
    require(
        len(frames) == 5 and frames[4].get("uid") == "246",
        "outer cleanup frame changed",
    )
    frame = frames[4]
    require(
        {(n.get("class", ""), n.get("uid")) for n in frame.find("zPlaneList")}
        == {
            ("iUse", "68680"),
            ("iUse", "67965"),
            ("iUse", "66474"),
            ("gRef", "62403"),
            ("gRef", "61778"),
            ("iUse", "61121"),
            ("", "13250"),
            ("gRef", "12978"),
            ("", "18438"),
            ("iUse", "88"),
            ("forLoop", "1176"),
        }
        and len(frame.find("zPlaneList")) == 11,
        "cleanup operations added, removed or moved",
    )
    require(
        {(n.get("class"), n.get("uid")) for n in frame.findall("nodeList/*[@class]")}
        == {("sRN", "250")},
        "cleanup constant/terminal container changed",
    )
    expected_uris = [
        "ni.var.psp://10.20.30.2/SUPERVISION/" + name for name in VARIABLES
    ]
    require(
        tag_array(constant(frame, "18438")) == expected_uris,
        "cleanup fixed URI reference array changed",
    )
    require(constant(frame, "13250") == "0000", "cleanup stop reset is not False")
    stop = unique(root, "gRef", "12978")
    require(
        stop.findtext("termList/*/dco/paramIdx") == "30"
        and stop.findtext("termList/*/objFlags") == "36864",
        "cleanup stop local or write direction changed",
    )
    exact_wires(
        frame,
        (
            ("61128", "69347"),
            ("66492", "68059"),
            ("62410", "66580"),
            ("61785", "61161"),
            ("13250", "12987"),
            ("18438", "1772"),
            ("2048", "2225"),
        ),
        "cleanup frame",
    )

    loop = unique(root, "forLoop", "1176")
    require(
        loop in frame.find("zPlaneList") and len(loop.find("diagramList")) == 1,
        "cleanup For scope changed",
    )
    body = loop.find("diagramList")[0]
    require(
        body.get("uid") == "1760"
        and [(n.get("class"), n.get("uid")) for n in body.find("zPlaneList")]
        == [("prim", "536"), (None, "2465")],
        "cleanup For body operations changed",
    )
    close = unique(root, "prim", "536")
    require(
        close.findtext("primResID") == "23783" and close.findtext("primIndex") == "544",
        "cleanup connection-close primitive changed",
    )
    require(
        [t.get("uid") for t in close.findall("termList/*")] == ["542", "1626", "2610"],
        "connection-close terminal list changed",
    )
    for uid, slot in (("542", 0), ("1626", 8), ("2610", 11)):
        term = close.find(f"termList/*[@uid='{uid}']")
        require(
            int(term.findtext("dco/parmIndex") or "0") == slot,
            "connection-close parameter mapping changed",
        )
    tunnel = loop.find("termList/*[@uid='1772']/dco")
    require(
        tunnel is not None
        and tunnel.get("class") == "lpTun"
        and tunnel.findtext("TunnelType") == "01"
        and [t.get("uid") for t in tunnel.findall("termList/*")] == ["1768", "1772"],
        "cleanup URI auto-index tunnel changed",
    )
    right = loop.find("termList/*[@uid='2048']/dco")
    left = loop.find("termList/*[@uid='2051']/dco")
    require(
        right is not None
        and left is not None
        and right.get("class") == "rSR"
        and right.get("uid") == "149"
        and left.get("class") == "lSR"
        and left.get("uid") == "2041"
        and left.find("rsrDCO").get("uid") == "149"
        and right.find("lsrDCOList/*").get("uid") == "2041",
        "cleanup error shift-register pair changed",
    )
    exact_wires(
        body, (("2050", "1626"), ("542", "2044"), ("1768", "2610")), "cleanup For body"
    )

    for (
        call_uid,
        bank_uid,
        bank_index,
        input_uid,
        error_uid,
        handler_uid,
        handler_input,
    ) in (
        ("61121", "61778", "51", "61161", "61128", "68680", "69347"),
        ("66474", "62403", "52", "66580", "66492", "67965", "68059"),
    ):
        call = unique(root, "iUse", call_uid)
        bank = unique(root, "gRef", bank_uid)
        handler = unique(root, "iUse", handler_uid)
        require(
            call.findtext("label/textRec/text") == '"Close.vi"'
            and handler.findtext("label/textRec/text") == '"Simple Error Handler.vi"',
            "TPG close or error handler call changed",
        )
        require(
            bank.findtext("termList/*/dco/paramIdx") == bank_index
            and bank.findtext("termList/*/objFlags") == "4096",
            "TPG session bank or read direction changed",
        )
        public_term(call, input_uid, 11)
        public_term(call, error_uid, 0)
        public_term(handler, handler_input, 9)
        require(
            len(call.findall("termList/*")) == 12
            and [
                int(t.findtext("dco/paramIdx") or "0")
                for t in call.findall("termList/*")
            ]
            == list(range(12)),
            "TPG call connector inventory changed",
        )
    tpg_links = [
        n
        for n in metadata.findall(".//IUVI")
        if [s.text for s in n.findall("LinkSaveQualName/String")]
        == ["TPG 300.lvlib", "Close.vi"]
    ]
    require(
        len(tpg_links) == 1
        and [s.text or "" for s in tpg_links[0].findall("LinkSavePathRef/String")]
        == ["", "", "TPG300", "Close.vi"],
        "TPG Close qualified dependency changed",
    )
    validate_cleanup_handlers(root, metadata)
    return [
        "Final frame uses 27 fixed URI-tag references, not the dynamically "
        "opened local reference array",
        "PSP close For carries error in an uninitialized shift register; "
        "N is unwired and URI input is auto-indexed",
        "PSP and two TPG close branches each feed a separate unwired-mode "
        "handler; handler returns are unused and stop=False is independent",
        "No DAQ Stop/Clear or output-zero command is present in this final frame",
    ]


def validate_cleanup_handlers(root, metadata):
    """Pin all three handler connectors, including formerly unqualified UID88.

    The exact outer net set establishes absent mode inputs and unused outputs.
    A handler return is not a wire back to the uninitialized PSP register.
    """
    names = call_names(metadata)
    flags = (513, 513, 0, 0, 0, 513, 513, 513, 512, 512)
    rows = (
        ("88", "2198", "2222", "2225"),
        ("68680", "69320", "69344", "69347"),
        ("67965", "67984", "68056", "68059"),
    )
    for uid, output, mode, error_in in rows:
        handler = unique(root, "iUse", uid)
        terms = handler.findall("termList/*")
        require(
            names.get(uid) == "Simple Error Handler.vi"
            and handler.findtext("label/textRec/text") == '"Simple Error Handler.vi"'
            and len(terms) == 10
            and tuple(int(t.findtext("dco/paramIdx", "0")) for t in terms)
            == tuple(range(10))
            and tuple(int(t.findtext("dco/objFlags", "0")) for t in terms) == flags
            and (terms[0].get("uid"), terms[8].get("uid"), terms[9].get("uid"))
            == (output, mode, error_in),
            "cleanup error-handler identity/connector changed",
        )
    close = unique(root, "prim", "536")
    require(
        tuple(int(t.findtext("dco/objFlags", "0")) for t in close.findall("termList/*"))
        == (1, 65536, 0),
        "PSP close input/output directions changed",
    )


def checked_tpg_roots(path):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper() == TPG_ARCHIVE_SHA256,
        "TPG Close archive hash changed",
    )
    with ZipFile(path) as archive:
        require(
            set(archive.namelist()) == set(TPG_FILE_HASHES),
            "TPG Close archive members changed",
        )
        roots = {}
        for name, expected in TPG_FILE_HASHES.items():
            payload = archive.read(name)
            require(
                hashlib.sha256(payload).hexdigest().upper() == expected,
                f"TPG Close exported file hash changed: {name}",
            )
            roots[name] = ET.fromstring(payload)
    return roots


def validate_tpg_trees(roots):
    frame = roots["vi_BDHb.xml"].find("root")
    require(
        frame is not None
        and frame.get("uid") == "107"
        and [(n.get("class"), n.get("uid")) for n in frame.find("zPlaneList")]
        == [("prim", "104"), (None, "111"), (None, "109"), (None, "116")],
        "TPG Close body operations changed",
    )
    close = unique(frame, "prim", "104")
    require(
        close.findtext("primResID") == "1922" and close.findtext("primIndex") == "257",
        "TPG VISA Close primitive changed",
    )
    exact_wires(frame, (("111", "125"), ("116", "129"), ("124", "109")), "TPG Close")
    pane = roots["vi_FPHb.xml"].find(".//conPane")
    require(
        pane is not None
        and [
            (int(c.get("index", "0")), c.find("ConnectionDCO").get("uid"))
            for c in pane.find("cons")
        ]
        == [(0, "5"), (8, "3"), (11, "9")],
        "TPG Close connector mapping changed",
    )
    for uid, label in (
        ("5", '"error out"'),
        ("3", '"error in (no error)"'),
        ("9", '"VISA session"'),
    ):
        dco = unique(roots["vi_FPHb.xml"], "fPDCO", uid)
        require(
            dco.findtext("ddo/partsList/*/textRec/text") == label,
            "TPG Close control identity changed",
        )
    for uid, dco_uid in (("111", "3"), ("116", "9"), ("109", "5")):
        term = unique(frame, "fPTerm", uid)
        require(
            term.find("dco").get("uid") == dco_uid,
            "TPG Close public terminal association changed",
        )
    require(
        [int(t.findtext("dco/parmIndex") or "0") for t in close.findall("termList/*")]
        == [0, 8, 11],
        "TPG VISA Close terminal mapping changed",
    )
    return [
        "TPG300 Close directly wires public VISA session/error-in to VISA Close "
        "and error-out; no custom cases, retries or serial commands"
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_export", type=Path)
    parser.add_argument("tpg_close_export", type=Path)
    args = parser.parse_args()
    root = checked_root(args.root_export)
    with ZipFile(args.root_export) as archive:
        metadata = ET.fromstring(archive.read("vi.xml"))
    for line in validate_cleanup_tree(root, metadata) + validate_tpg_trees(
        checked_tpg_roots(args.tpg_close_export)
    ):
        print(line)
    print("PASS: final cleanup dataflow and TPG300 Close")


if __name__ == "__main__":
    main()
