"""Pin copied TPG startup sources and their saved state/tunnel graphs.

Initialize and Serial Init caller logic only; Driver Core protocol is OPEN.
No LabVIEW, VISA or serial execution. Primitive slot interpretation is from
the local lvkit primitive table, independently checked against NI semantics.
"""

import argparse
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import connector_map
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import operations

ARCHIVE_SHA256 = "AE6CC7EE631BEE764738D09E1E9787916BC1AAC01B843A50DB669C60F5A2CDB1"
XML_HASHES = {
    "Initialize": (
        "8C23EF29332A46089AA4F5E00AA6F48D518D2AE78EF27A541BF6AEA0ECFADA12",
        "D732A3E7389CA4B70AD55C1A4AB4F63504BA95F62EC75D60DC9C7EE1D1FE7854",
        "2BD45125E3DD46D4966B1EC19B5AFA8F5DCAF4E9030C33C0E6C03489B79EC9BC",
    ),
    "TPG300-Serial Init": (
        "62B871E3B5ABD2178E2D89752FBB2657FC87D07505F7D04AF93F57CC2198DC39",
        "CE87BECF1F38A6D169750E11B608636B8350C760E93C311C58144BD33E4382A8",
        "09A7A92F87257B62EC02888C1D4DB0A7A4986C143105FCE27BD007BE5D26C1EF",
    ),
    "TPG300-Driver Core": (
        "E0231C6262462C65F98ED2AF9D897271FDE7550EFC1564C07C67F2337988AC71",
        "FCB02DEA519D524C003EABEEA8941B281C57F084D753CF39BFE10C9847BE35B9",
        "EAC9AD8DD34AD7534E948AB2C8DC9E0C52ED94B29E2585DA28B7D622D9F58479",
    ),
}
FILES = ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml")
STATES = [
    "Init & Test",
    "Next Baud Rate",
    "Set Default ",
    "Communication OK",
    "Error Box",
]
INIT_NETS = {
    "98": (
        ("1455", "1296"),
        ("1193", "1385"),
        ("1517", "139"),
        ("1180", "1279"),
        ("167", "128", "405"),
        ("100", "147", "248", "525"),
    ),
    "107": (
        ("1487", "1451"),
        ("1382", "1371"),
        ("1555", "1513"),
        ("1275", "1324"),
        ("524", "504"),
        ("468", "124"),
        ("414", "114"),
        ("404", "427"),
        ("127", "121"),
        ("145", "268"),
    ),
    "117": (
        ("2030", "1467"),
        ("827", "187"),
        ("1352", "857"),
        ("740", "516", "863"),
        ("1626", "1527"),
        ("841", "1550"),
        ("1304", "866"),
        ("382", "334"),
        ("227", "471"),
        ("447", "439"),
        ("366", "327"),
        ("326", "158"),
        ("510", "338"),
        ("264", "513"),
    ),
    "198": (
        ("1947", "212"),
        ("925", "1944", "2022"),
        ("190", "913"),
        ("893", "1622"),
        ("1542", "872"),
        ("537", "896"),
        ("601", "916"),
        ("543", "885"),
        ("155", "209"),
        ("379", "215"),
        ("206", "223"),
    ),
    "130": (("191", "2026"), ("1546", "1618"), ("240", "224")),
    "173": (
        ("1355", "1471"),
        ("1308", "1531"),
        ("756", "282"),
        ("314", "225"),
        ("453", "440"),
        ("386", "317"),
        ("238", "323"),
        ("299", "320"),
        ("257", "302", "768"),
        ("775", "305"),
        ("290", "260"),
        ("149", "293"),
        ("279", "263"),
    ),
    "182": (
        ("1049", "1475"),
        ("1359", "984"),
        ("963", "1536"),
        ("1312", "931"),
        ("572", "966"),
        ("553", "935"),
        ("788", "583"),
        ("586", "569"),
        ("609", "589"),
        ("234", "171"),
        ("560", "566"),
        ("370", "232"),
    ),
    "394": (
        ("1099", "1479"),
        ("1002", "1087"),
        ("546", "1069"),
        ("606", "1057"),
        ("616", "1090"),
        ("1363", "1034"),
        ("397", "801", "1040"),
        ("1066", "1543"),
        ("1019", "1055"),
        ("1316", "1043"),
        ("399", "465"),
        ("408", "356"),
    ),
    "410": (("1393", "1483"), ("1320", "1548"), ("415", "466"), ("432", "357")),
}
INIT_OPS = {
    "98": (
        (None, "1296"),
        (None, "1193"),
        (None, "139"),
        (None, "1180"),
        ("whileLoop", "818"),
        (None, "248"),
        (None, "167"),
        (None, "100"),
    ),
    "107": (("select", "647"), (None, "114"), (None, "111")),
    "117": (
        ("iUse", "832"),
        ("gRef", "750"),
        ("prim", "506"),
        (None, "382"),
        (None, "447"),
        (None, "366"),
        ("prim", "308"),
        ("select", "652"),
    ),
    "198": (
        ("nMux", "289"),
        ("iUse", "902"),
        (None, "601"),
        (None, "543"),
        (None, "537"),
        (None, "379"),
        ("prim", "202"),
    ),
    "130": ((None, "240"),),
    "173": (
        ("gRef", "771"),
        ("gRef", "764"),
        ("gRef", "753"),
        (None, "453"),
        (None, "238"),
        (None, "386"),
        ("prim", "310"),
        ("prim", "295"),
        ("prim", "286"),
        ("prim", "275"),
        ("prim", "250"),
        (None, "149"),
    ),
    "182": (
        ("iUse", "953"),
        ("gRef", "784"),
        ("label", "612"),
        (None, "609"),
        (None, "234"),
        ("aIndx", "581"),
        ("concat", "565"),
        (None, "560"),
        (None, "553"),
        (None, "370"),
    ),
    "394": (
        ("iUse", "1051"),
        (None, "546"),
        (None, "606"),
        (None, "616"),
        ("iUse", "1007"),
        ("gRef", "798"),
        (None, "408"),
    ),
    "410": ((None, "1393"), (None, "432")),
}
INIT_TUNNELS = {
    "647": {
        "121": ("caseSel", "0", ("120", "176", "186", "399", "415", "121")),
        "268": ("selTun", "8192", ("264", "265", "246", "397", "413", "268")),
        "427": ("selTun", "0", ("424", "425", "426", "421", "398", "427")),
        "414": ("selTun", "1", ("439", "440", "171", "356", "357", "414")),
        "468": ("selTun", "1", ("471", "225", "232", "465", "466", "468")),
        "504": ("selTun", "0", ("502", "503", "505", "519", "521", "504")),
        "1324": ("selTun", "10240", ("1304", "1308", "1312", "1316", "1320", "1324")),
        "1555": ("selTun", "2049", ("1527", "1531", "1536", "1543", "1548", "1555")),
        "1371": ("selTun", "10240", ("1352", "1355", "1359", "1363", "1367", "1371")),
        "1487": ("selTun", "2049", ("1467", "1471", "1475", "1479", "1483", "1487")),
    },
    "652": {
        "187": ("caseSel", "0", ("190", "191", "187")),
        "227": ("selTun", "1", ("223", "224", "227")),
        "158": ("selTun", "0", ("155", "156", "158")),
        "1550": ("selTun", "2048", ("1542", "1546", "1550")),
        "1626": ("selTun", "2049", ("1622", "1618", "1626")),
        "2030": ("selTun", "2049", ("2022", "2026", "2030")),
    },
}


def checked_roots(path):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper() == ARCHIVE_SHA256,
        "copied TPG archive hash changed",
    )
    result = {}
    with ZipFile(path) as archive:
        for folder, hashes in XML_HASHES.items():
            result[folder] = {}
            for name, expected in zip(FILES, hashes):
                data = archive.read(folder + "/" + name)
                require(
                    hashlib.sha256(data).hexdigest().upper() == expected,
                    "TPG XML hash changed: " + folder + "/" + name,
                )
                result[folder][name] = ET.fromstring(data)
    return result


def saved_bytes(fp, uid):
    value = unique(fp, "fPDCO", uid).findtext("DefaultData")
    require(value is not None and value[0] == value[-1] == '"', "FP default missing")
    # HTML unescape maps NUL/control entities to replacement characters;
    # these are saved binary bytes, not rendered HTML text.
    value = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m[1], 16)), value[1:-1])
    return re.sub(r"&#(\d+);", lambda m: chr(int(m[1])), value).encode("latin-1")


def selectors(node, frames):
    require(
        tuple(d.get("uid") for d in node.find("diagramList")) == frames,
        "TPG case frame order changed",
    )
    require(
        [
            (r.findtext("start"), r.findtext("end"), r.findtext("diagramIdx"))
            for r in node.findall("SelectRangeArray32/*")
        ]
        == [(str(i), str(i), str(i)) for i in range(len(frames))],
        "TPG selector-value/frame mapping changed",
    )


def validate_initializer(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        {d.get("uid") for d in bd.iter() if d.get("class") == "diag"} == set(INIT_NETS),
        "TPG Initialize diagram census changed",
    )
    require(
        connector_map(fp)
        == [(0, "1294"), (3, "137"), (8, "1190"), (10, "6"), (11, "1177")],
        "TPG Initialize connector mapping changed",
    )
    for uid, nets in INIT_NETS.items():
        frame = unique(bd, "diag", uid)
        exact_wires(frame, nets, "TPG Initialize frame " + uid)
        operations(frame, INIT_OPS[uid], "TPG Initialize frame " + uid)
    selectors(unique(bd, "select", "647"), ("117", "173", "182", "394", "410"))
    selectors(unique(bd, "select", "652"), ("198", "130"))
    for uid, specs in INIT_TUNNELS.items():
        node = unique(bd, "select", uid)
        require(len(node.find("termList")) == len(specs), "TPG extra selector tunnel")
        for port, (kind, flags, children) in specs.items():
            dco = node.find(f"termList/*[@uid='{port}']/dco")
            require(
                dco is not None
                and dco.get("class") == kind
                and dco.findtext("objFlags", "0") == flags
                and tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
                "TPG case tunnel identity/direction changed",
            )
    loop = unique(bd, "whileLoop", "818")
    require(
        loop.findtext("loopTestDCO/objFlags") == "1"
        and loop.find("loopTestDCO").get("uid") == "112"
        and loop.find("loopTestDCO/termList/*").get("uid") == "114",
        "TPG continue-if-true loop condition changed",
    )
    require(
        tuple(t.get("uid") for t in loop.findall("srDCOList/*")) == ("122",),
        "TPG state history register changed",
    )
    rsr = unique(bd, "rSR", "122")
    require(
        tuple(t.get("uid") for t in rsr.findall("termList/*")) == ("124", "125")
        and tuple(t.get("uid") for t in rsr.findall("lsrDCOList/*")) == ("123", "416"),
        "TPG two-element state history changed",
    )
    for port, kind, flags, children in (
        ("525", "lpTun", "0", ("524", "525")),
        ("147", "lpTun", "0", ("145", "147")),
        ("405", "lSR", "0", ("404", "405")),
        ("128", "lSR", "0", ("127", "128")),
        ("1279", "lpTun", "2048", ("1275", "1279")),
        ("1517", "lpTun", "2049", ("1513", "1517")),
        ("1385", "lpTun", "2048", ("1382", "1385")),
        ("1455", "lpTun", "2049", ("1451", "1455")),
    ):
        dco = loop.find(f"termList/*[@uid='{port}']/dco")
        require(
            dco is not None
            and dco.get("class") == kind
            and dco.findtext("objFlags", "0") == flags
            and tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
            "TPG ordinary input/output tunnel or history changed",
        )
    for uid, resource, ports in (
        ("506", 1102, ("510", "513", "516")),
        ("295", 1102, ("299", "302", "305")),
        ("308", 1516, ("326", "334", "338", "327")),
        ("202", 1516, ("206", "209", "212", "215")),
        ("310", 1516, ("314", "317", "320", "323")),
        ("250", 1056, ("254", "257", "260", "263")),
        ("275", 1057, ("279", "282")),
        ("286", 1057, ("290", "293")),
    ):
        primitive(bd, uid, resource, ports)
    for uid, port, index, write in (
        ("750", "740", 0, False),
        ("753", "756", 0, False),
        ("764", "768", 0, True),
        ("771", "775", 2, False),
        ("784", "788", 2, False),
        ("798", "801", 0, True),
    ):
        n = unique(bd, "gRef", uid)
        require(
            n.find("termList/*").get("uid") == port
            and n.findtext("termList/*/dco/paramIdx", "0") == str(index)
            and n.findtext("termList/*/dco/objFlags", "0") == ("0" if write else "1"),
            "TPG Baud/Def.Value local mapping changed",
        )
    names = call_names(meta)
    for uid, name in (
        ("832", "TPG300-Serial Init.vi"),
        ("1007", "TPG300-Serial Init.vi"),
        ("902", "TPG300-Driver Core.vi"),
        ("953", "TPG300-Driver Core.vi"),
        ("1051", "TPG300-Driver Core.vi"),
    ):
        require(names.get(uid) == name, "TPG helper qualified identity changed")
        node = unique(bd, "iUse", uid)
        serial = uid in ("832", "1007")
        require(
            len(node.find("termList")) == (12 if serial else 16),
            "TPG helper connector size changed",
        )
        for slot, term in enumerate(node.findall("termList/*")):
            public_term(node, term.get("uid"), slot)
        types = (
            (
                (0, "Cluster"),
                (3, "Refnum"),
                (8, "Cluster"),
                (10, "NumUInt16"),
                (11, "Refnum"),
            )
            if serial
            else (
                (0, "Refnum"),
                (1, "Boolean"),
                (4, "Refnum"),
                (5, "String"),
                (11, "Cluster"),
                (12, "NumUInt32"),
                (13, "NumInt32"),
                (15, "Cluster"),
            )
        )
        for slot, kind in types:
            td = node.findall("termList/*")[slot].findtext("dco/typeDesc")
            require(
                heap_type(meta, int(td[7:-1]))[0].get("Type") == kind,
                "TPG helper public error/VISA/command type interpretation changed",
            )
    for port, dco in (("100", "6"), ("248", "27"), ("149", "20"), ("609", "43")):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == dco,
            "TPG requested/Max/Def/Bau FP binding changed",
        )
    for frame, uid, value in (
        ("98", "167", "000000"),
        ("117", "382", "0002"),
        ("117", "366", "0003"),
        ("117", "447", "01"),
        ("198", "537", "00000003504E52"),
        ("198", "601", "000002BC"),
        ("198", "543", "0000"),
        ("198", "379", "0001"),
        ("130", "240", "0004"),
        ("173", "453", "01"),
        ("173", "386", "000000"),
        ("173", "238", "0004"),
        ("182", "560", "000000044241552C"),
        ("182", "553", "01"),
        ("182", "234", "01"),
        ("182", "370", "0003"),
        ("394", "546", "00000003504E52"),
        ("394", "606", "0000"),
        ("394", "616", "000002BC"),
        ("394", "408", "0000"),
        ("410", "432", "0000"),
        ("410", "1393", "01000000000000000A496E6974204572726F72"),
    ):
        require(
            constant(unique(bd, "diag", frame), uid) == value,
            "TPG state/command/error literal changed",
        )
    descriptor, _ = heap_type(meta, 216)
    require(
        [n.text for n in descriptor.findall("EnumLabel")] == STATES,
        "TPG enum state meaning changed",
    )
    require(
        saved_bytes(fp, "6") == b"\x00\x04"
        and saved_bytes(fp, "20") == b"\x00\x04"
        and saved_bytes(fp, "27") == b"\x00\x01"
        and saved_bytes(fp, "43")
        == bytes.fromhex("0000000500000001330000000131000000013200000001340000000139"),
        "TPG Baud/Max/Def/Bau defaults changed",
    )
    return (
        f"TPG Initialize: nine diagrams, {sum(map(len, INIT_NETS.values()))} nets; "
        "five states; Driver Core remains external"
    )


def validate_serial(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        {d.get("uid") for d in bd.iter() if d.get("class") == "diag"}
        == {"493", "1200", "1209"},
        "TPG Serial Init diagram census changed",
    )
    nets = {
        "493": (
            ("1193", "335"),
            ("260", "1127"),
            ("1139", "1188"),
            ("1106", "1183"),
            ("715", "775"),
            ("1081", "1103"),
            ("514", "1178"),
            ("589", "1109"),
            ("2211", "1094"),
            ("579", "592"),
            ("495", "586"),
        ),
        "1200": (("1186", "706"), ("1191", "1196")),
        "1209": (
            ("1220", "711"),
            ("1217", "1197"),
            ("1192", "1223"),
            ("1182", "1226"),
            ("1187", "1232"),
        ),
    }
    for uid, wires in nets.items():
        exact_wires(unique(bd, "diag", uid), wires, "TPG Serial Init frame " + uid)
    operations(
        unique(bd, "diag", "493"),
        [
            (None, uid)
            for uid in ("335", "260", "775", "1081", "2211", "579", "514", "495")
        ]
        + [("polyIUse", "1091"), ("select", "1176"), ("aIndx", "582")],
        "Serial root",
    )
    operations(unique(bd, "diag", "1200"), [], "zero-buffer case")
    operations(unique(bd, "diag", "1209"), [("prim", "1215")], "nonzero-buffer case")
    selectors(unique(bd, "select", "1176"), ("1200", "1209"))
    require(
        unique(bd, "select", "1176").findtext("SelectDefaultCase") == "01",
        "nonzero buffer default case changed",
    )
    require(
        constant(unique(bd, "diag", "493"), "1081") == "0000",
        "termination-character disabling changed",
    )
    require(
        saved_bytes(fp, "171") == bytes.fromhex("1388")
        and saved_bytes(fp, "251")
        == bytes.fromhex("00000007012C04B0096012C025804B009600"),
        "TPG buffer/baud defaults changed",
    )
    node = unique(bd, "prim", "1215")
    require(
        node.findtext("primResID") == "2301"
        and [
            (t.get("uid"), t.findtext("dco/parmIndex", "0"))
            for t in node.findall("termList/*")
        ]
        == [
            ("1217", "0"),
            ("1220", "3"),
            ("1223", "8"),
            ("1226", "9"),
            ("1229", "10"),
            ("1232", "11"),
        ],
        "VISA buffer node connector changed",
    )
    return "TPG Serial Init: three diagrams, 18 nets; termination disabled, buffer 5000"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    roots = checked_roots(parser.parse_args().archive)
    print(validate_initializer(roots["Initialize"]))
    print(validate_serial(roots["TPG300-Serial Init"]))


if __name__ == "__main__":
    main()
