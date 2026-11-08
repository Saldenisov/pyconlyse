"""Static command framing and both byte loops; no VISA or VI execution.

Fixed direct nets cover all remaining 27 Driver Core diagrams. Semantic
checks pin case polarity, primitive slots, register identity and literals.
This does not close external VISA returns or the suppress-warning helper.
"""

import argparse
from pathlib import Path

from validate_acq_final_cleanup import exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import operations
from validate_acq_tpg300_retry import NETS as OUTER_NETS
from validate_acq_tpg300_retry import validate_core
from validate_acq_tpg300_startup import checked_roots, saved_bytes, selectors


def groups(value):
    return tuple(tuple(group.split(",")) for group in value.split())


NETS = {
    uid: groups(value)
    for uid, value in {
        "184": "144,1624 1668,175 1629,172 166,1620 178,748",
        "1636": "1660,1714 1713,1632 1627,1727",
        "1642": "1628,1633",
        "229": (
            "3289,3381 4778,837 4386,4775 4772,3140 4781,243 5963,4769 "
            "842,803 848,910 749,855 232,859 864,211"
        ),
        "826": (
            "3307,3281 5021,5002 3157,4955 834,3169 3142,3348 3166,3305 "
            "3163,3223 3136,3175 240,3172 248,361 344,818 290,340 857,336 "
            "850,274 754,352 137,376 140,474 362,844 366,827"
        ),
        "371": (
            "3326,3302 3527,5052 4999,3524 3521,2393 3530,431,416 3344,3518 "
            "1785,795 792,692 786,1761 1776,347 457,1734 374,617 420,267 "
            "673,369 467,676 681,365 462,695,684 689,381 452,356 360,447 "
            "351,442 343,394 386,397 402,437 413,421 339,405 391,408"
        ),
        "475": "5045,3318 450,455,485 482,470 440,465,490 445,460",
        "497": "",
        "503": "509,519",
        "532": (
            "2156,3322 5049,2349 2164,551 2389,2357 435,2353 571,471,466 "
            "616,611 265,257 538,546,576 566,461 561,456 446,556 451,541"
        ),
        "583": "554,779 600,574 579,603 589,564 782,569 559,776",
        "625": (
            "595,1861 255,1834 1873,767 635,575 1849,638 555,1858,1805 "
            "770,570 1876,565 560,764"
        ),
        "295": "3022,5013 4948,3031 3028,3129 276,3034 3297,3037 300,292",
        "309": "313,323",
        "829": "835,3285 896,824 879,845 884,840",
        "987": (
            "3599,2404 3385,5085 5967,2822 997,1555 993,1585,1601 "
            "999,1582,1566 1594,1008 1588,1597 1576,932 1047,1546 "
            "1534,1525 991,1013"
        ),
        "1025": "5077,3591 1042,1001 1570,1550 1563,1532",
        "1044": (
            "3567,3595 5149,5130 5081,5103 2867,1981 2106,2840 1138,1575 "
            "1559,1030 1539,1533 149,1065 1053,1155 1080,1134 1017,1130 "
            "1048,1146"
        ),
        "1157": (
            "3523,3563 2704,5181 5127,2701 2698,2218 2707,1202,1216 "
            "1965,2695 1439,1553 1431,1538 1925,1426 1423,1450 1165,1910 "
            "1916,1141 1241,1898 1251,1434 1246,1453,1442 1447,1162 "
            "1236,1150 1154,1231 1145,1226 1137,1180 1172,1183 1188,1221 "
            "1199,1206 1133,1191 1177,1194"
        ),
        "1258": "5173,3511 1234,1239,1267 1264,1254 1224,1249,1273 1229,1244",
        "1280": "",
        "1286": "1292,1302",
        "1315": (
            "331,3515 5177,2652 2211,2658 2584,1331 1220,2655 1319,1326 "
            "1351,1250,1255 1346,1245 1341,1240 1230,1336 1235,1322"
        ),
        "1357": "1613,1354 1334,1372 1362,1344 1375,1349 1339,1369",
        "1387": "1518,1355 1511,1345 1335,1396 1399,1350 1340,1393",
        "1087": "2669,5141 5095,2678 2675,2859 2832,2684 1068,2681 1093,1083",
        "1101": "1107,1117",
    }.items()
}

OPS = {
    uid: tuple(
        (None if c == "_" else c, u)
        for c, u in (pair.split(":") for pair in value.split())
    )
    for uid, value in {
        "184": "_:1668 select:1674 concat:170 _:144",
        "1636": "prim:1720 _:1660",
        "1642": "",
        "229": "propNode:1968 select:1677",
        "826": "prim:3151 whileLoop:2041 sequence:269 _:248 _:754 _:137 _:140",
        "371": (
            "propNode:3353 prim:1769 prim:790 _:786 prim:671 prim:687 "
            "prim:679 prim:411 select:1678 prim:400 prim:389 prim:384 "
            "_:381 _:378"
        ),
        "475": "prim:480 select:1680",
        "497": "",
        "503": "_:509 prim:514",
        "532": "prim:306 prim:536 select:1683",
        "583": "concat:771 prim:598 _:589",
        "625": "prim:1856 prim:1830 label:822 label:821 concat:759 prim:633",
        "295": "prim:1940 prim:298",
        "309": "prim:318 _:313",
        "829": "_:896 _:884 _:879",
        "987": "prim:1592 cpdArith:1580 select:1685",
        "1025": "",
        "1044": "whileLoop:2059 _:149 sequence:1058 _:1053 _:1048",
        "1157": (
            "propNode:1028 prim:1906 prim:1421 _:1165 prim:1429 prim:1445 "
            "prim:1437 prim:1197 select:1684 prim:1186 prim:1175 prim:1170 "
            "_:1162 _:1159"
        ),
        "1258": "prim:1262 select:1687",
        "1280": "",
        "1286": "_:1292 prim:1297",
        "1315": "prim:278 prim:1317 select:1690",
        "1357": "_:1613 concat:1367 _:1362",
        "1387": "_:1518 _:1511 concat:1391",
        "1087": "prim:1878 prim:1091",
        "1101": "prim:1112 _:1107",
    }.items()
}

CASES = {
    "1674": ("1636", "1642", "1620:1622,1623 1624:1627,1628 1629:1632,1633"),
    "1677": (
        "826",
        "829",
        (
            "837:834,835 842:827,840 848:844,845 855:850,838 859:857,858 "
            "243:240,241 864:818,824 3140:3136,3132 3289:3281,3285"
        ),
    ),
    "1678": (
        "475",
        "532",
        (
            "421:424,425 431:434,435 437:440,441 442:445,446 447:450,451 "
            "452:455,456 457:460,461 462:465,466 467:470,471 267:263,265 "
            "617:615,616 2393:2384,2389 5052:5045,5049 3326:3318,3322"
        ),
    ),
    "1680": ("497", "503", "490:493,494"),
    "1683": (
        "583",
        "625",
        (
            "546:549,550 551:554,555 556:559,560 561:564,565 566:569,570 "
            "571:574,575 576:579,580 257:254,255 611:582,595"
        ),
    ),
    "1685": (
        "1025",
        "1044",
        (
            "1008:1011,1012 1013:1016,1017 1534:1532,1533 1047:1550,1030 "
            "1576:1001,1575 1566:1563,1565 1601:1570,1600 1555:1042,1043 "
            "2822:1103,2106 5085:5077,5081 3599:3591,3595"
        ),
    ),
    "1684": (
        "1258",
        "1315",
        (
            "1206:1209,1210 1216:1219,1220 1221:1224,1225 1226:1229,1230 "
            "1231:1234,1235 1236:1239,1240 1241:1244,1245 1246:1249,1250 "
            "1251:1254,1255 2218:2202,2211 5181:5173,5177 3523:3511,3515"
        ),
    ),
    "1687": ("1280", "1286", "1273:1276,1277"),
    "1690": (
        "1357",
        "1387",
        (
            "1326:1329,1330 1331:1334,1335 1336:1339,1340 1341:1344,1345 "
            "1346:1349,1350 1351:1354,1355"
        ),
    ),
}

PRIMITIVES = {
    "1720": (1503, "1713,1714,1724,1727"),
    "1769": (1535, "1734,1761,1773,1776,1779,1782,1785"),
    "1856": (1535, "1858,1861,1864,1867,1870,1873,1876"),
    "1830": (1535, "1805,1834,1837,1840,1843,1846,1849"),
    "1906": (1535, "1898,1910,1913,1916,1919,1922,1925"),
    "790": (1118, "792,795"),
    "536": (1118, "538,541"),
    "633": (1118, "635,638"),
    "1421": (1118, "1423,1426"),
    "1317": (1118, "1319,1322"),
    "671": (1064, "673,676"),
    "679": (1064, "681,684"),
    "598": (1064, "600,603"),
    "1592": (1064, "1594,1597"),
    "1429": (1064, "1431,1434"),
    "1437": (1064, "1439,1442"),
    "687": (1061, "689,692,695"),
    "1445": (1061, "1447,1450,1453"),
    "411": (1117, "413,416"),
    "1197": (1117, "1199,1202"),
    "480": (1114, "482,485"),
    "1262": (1114, "1264,1267"),
    "400": (1111, "402,405,408"),
    "1186": (1111, "1188,1191,1194"),
    "389": (1051, "391,394,397"),
    "1175": (1051, "1177,1180,1183"),
    "384": (1300, "386"),
    "298": (1300, "300"),
    "1170": (1300, "1172"),
    "1091": (1300, "1093"),
    "514": (1302, "516,519"),
    "318": (1302, "320,323"),
    "1297": (1302, "1299,1302"),
    "1112": (1302, "1114,1117"),
}
VISA = {
    "3151": (1925, "3157,3160,3163,3166,3169,3172,3175"),
    "306": (1925, "2156,2160,2164,2329,2349,2353,2357"),
    "278": (1925, "331,982,2584,2649,2652,2655,2658"),
    "1940": (1926, "3022,3025,3028,3031,3034,3037"),
    "1878": (1926, "2669,2672,2675,2678,2681,2684"),
}
CONSTANTS = {
    "1658": "03",
    "1666": "000000010D",
    "510": "00000032",
    "590": "00000001",
    "784": "000000010D",
    "314": "00000032",
    "752": "0000000000",
    "249": "FFFFFFFF",
    "877": "01",
    "882": "0000",
    "894": "0000000000",
    "1293": "00000032",
    "1363": "00000001",
    "1611": "01",
    "1509": "00000001",
    "1516": "01",
    "1166": "000000010D",
    "1108": "00000032",
    "1049": "0000000000",
    "1054": "FFFFFFFF",
}

SEQUENCE_TUNNELS = {
    "183": (
        "220:219,232,991,812:8192 930:926,927,992,928:1 "
        "972:166,167,994,971:0 5975:5959,5963,5967,5971:10240 "
        "2463:2447,2451,2455,2459:2049 4398:4382,4386,4390,4394:2048 "
        "5235:5219,5223,5227,5231:2049"
    ),
    "269": (
        "274:276,277:0 290:292,293:1 3223:3215,3219:2048 "
        "3305:3297,3301:2048 3142:3129,3137:2049 4955:4948,4951:2048 "
        "5021:5013,5017:2049"
    ),
    "1058": (
        "1065:1068,1069:0 1080:1083,1084:1 2840:2832,2836:2048 "
        "2867:2859,2863:2049 5103:5095,5099:2048 5149:5141,5145:2049"
    ),
}


def validate_protocol(roots):
    validate_core(roots)
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        {d.get("uid") for d in bd.iter() if d.get("class") == "diag"}
        == set(NETS) | set(OUTER_NETS),
        "Core complete diagram census changed",
    )
    for uid in NETS:
        frame = unique(bd, "diag", uid)
        exact_wires(frame, NETS[uid], "Core protocol " + uid)
        operations(frame, OPS[uid], "Core protocol " + uid)
    for uid, (false, true, tunnels) in CASES.items():
        node = unique(bd, "select", uid)
        selectors(node, (false, true))
        require(len(node.find("termList")) == len(tunnels.split()), "Extra case tunnel")
        for item in tunnels.split():
            port, children = item.split(":")
            dco = node.find(f"termList/*[@uid='{port}']/dco")
            require(
                dco is not None
                and tuple(t.get("uid") for t in dco.findall("termList/*"))
                == (*children.split(","), port),
                "Protocol case tunnel changed",
            )
            outputs = set(
                (
                    "1629 842 848 864 452 457 462 467 561 566 571 1534 1047 "
                    "1576 1236 1241 1246 1251 1341 1346 1351"
                ).split()
            )
            reference_inputs = set("3140 2393 5052 2822 5085 2218 5181".split())
            error_outputs = set("3289 3326 3599 3523".split())
            flag = (
                "1"
                if port in outputs
                else "2048"
                if port in reference_inputs
                else "2049"
                if port in error_outputs
                else "0"
            )
            selector = item == tunnels.split()[0]
            require(
                dco.get("class") == ("caseSel" if selector else "selTun")
                and dco.findtext("objFlags", "0") == flag,
                "Case tunnel kind/direction changed",
            )
    for uid, (resource, ports) in PRIMITIVES.items():
        primitive(bd, uid, resource, tuple(ports.split(",")))
    for uid, (resource, ports) in VISA.items():
        node = unique(bd, "prim", uid)
        terms = node.findall("termList/*")
        slots = (0, 1, 2, 3, 8, 10, 11) if resource == 1925 else (0, 2, 3, 8, 10, 11)
        require(
            node.findtext("primResID") == str(resource)
            and tuple(t.get("uid") for t in terms) == tuple(ports.split(","))
            and tuple(int(t.findtext("dco/parmIndex", "0")) for t in terms) == slots,
            "VISA read/write argument slots changed",
        )
    for uid, value in CONSTANTS.items():
        matches = [
            n
            for n in bd.iter()
            if n.get("uid") == uid and n.find("ConstValue") is not None
        ]
        require(
            len(matches) == 1 and matches[0].findtext("ConstValue") == value,
            "Core framing/timing literal changed " + uid,
        )
    for port, control, value in (
        ("140", "11", "0000000106"),
        ("137", "18", "0000000115"),
        ("149", "46", "0000000105"),
        ("146", "32", "00000258"),
    ):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control
            and saved_bytes(fp, control) == bytes.fromhex(value),
            "Core token/default binding changed",
        )
    for uid, test, registers in (
        ("2041", "381", ("354", "345")),
        ("2059", "1162", ("1148", "1139")),
    ):
        loop = unique(bd, "whileLoop", uid)
        require(
            loop.findtext("loopTestDCO/objFlags") == "1"
            and loop.find("loopTestDCO/termList/*").get("uid") == test
            and tuple(t.get("uid") for t in loop.findall("srDCOList/*")) == registers,
            "Core inner continue/register set changed",
        )
    for loop_uid, port, inner in (
        ("2041", "5002", "4999"),
        ("2041", "3348", "3344"),
        ("2059", "5130", "5127"),
        ("2059", "1981", "1965"),
    ):
        dco = unique(bd, "whileLoop", loop_uid).find(f"termList/*[@uid='{port}']/dco")
        require(
            dco.get("class") == "lpTun"
            and dco.findtext("objFlags") == "2048"
            and tuple(t.get("uid") for t in dco.findall("termList/*")) == (inner, port),
            "Core ordinary error/VISA input became feedback",
        )
    for uid, terms, left in (
        ("354", ("356", "353"), "358"),
        ("345", ("347", "344"), "349"),
        ("1148", ("1150", "1147"), "1152"),
        ("1139", ("1141", "1138"), "1143"),
    ):
        register = unique(bd, "rSR", uid)
        require(
            tuple(t.get("uid") for t in register.findall("termList/*")) == terms
            and tuple(t.get("uid") for t in register.findall("lsrDCOList/*"))
            == (left,),
            "Core buffer/index register pairing changed",
        )
    for uid, frames in (("269", ("295", "309")), ("1058", ("1087", "1101"))):
        require(
            tuple(
                t.get("uid")
                for t in unique(bd, "sequence", uid).findall("diagramList/*")
            )
            == frames,
            "Core write then wait phase order changed",
        )
    for uid, specs in SEQUENCE_TUNNELS.items():
        sequence = unique(bd, "sequence", uid)
        require(
            len(sequence.find("termList")) == len(specs.split()),
            "Core extra sequence tunnel",
        )
        for spec in specs.split():
            port, children, flag = spec.split(":")
            dco = sequence.find(f"termList/*[@uid='{port}']/dco")
            require(
                dco.get("class") == "seqTun"
                and dco.findtext("objFlags", "0") == flag
                and tuple(t.get("uid") for t in dco.findall("termList/*"))
                == (*children.split(","), port),
                "Core sequence argument/error/time origin changed",
            )
    for uid, origin, terms in (
        ("747", "00", ("748", "749", "995", "905")),
        ("814", "01", ("815", "211", "997", "906")),
        ("216", "01", ("246", "803", "999", "804")),
        ("908", "01", ("909", "910", "993", "805")),
        ("3370", "01", ("3377", "3381", "3385", "3389")),
    ):
        local = unique(bd, "sLoc", uid)
        require(
            local.findtext("diagDefined", "00") == origin
            and tuple(t.get("uid") for t in local.findall("termList/*")) == terms,
            "Core phase-one bytes/flags/error local changed",
        )
    for uid, ports in (
        ("170", ("178", "172", "175")),
        ("759", ("770", "764", "767")),
        ("771", ("782", "776", "779")),
        ("1367", ("1375", "1369", "1372")),
        ("1391", ("1399", "1393", "1396")),
    ):
        node = unique(bd, "concat", uid)
        require(
            node.findtext("objFlags", "0") == ("0" if uid == "170" else "65536")
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and tuple(t.get("uid") for t in node.findall("dcoList/*"))
            == tuple(
                node.find(f"termList/*[@uid='{port}']/dco").get("uid")
                for port in ports[1:]
            ),
            "Core byte concatenation order changed",
        )
    compound = unique(bd, "cpdArith", "1580")
    require(
        compound.findtext("objFlags") == "720896"
        and tuple(t.get("uid") for t in compound.findall("termList/*"))
        == ("1588", "1582", "1585")
        and [t.findtext("dco/objFlags") for t in compound.findall("termList/*")]
        == ["131073", "262144", "262144"],
        "Core phase-two gate is not non-inverted OR",
    )
    for uid in ("1968", "3353", "1028"):
        node = unique(bd, "propNode", uid)
        items = node.findall("termList/*/dco/propList/*")
        require(
            node.findtext("oMId") == "00B3"
            and len(items) == 1
            and items[0].findtext("PropItemCode") == "1073676460"
            and items[0].findtext("PropItemName")
            == '"Serial Settings:Number of Bytes at Serial Port"',
            "Core serial bytes-available property changed",
        )
    for uid in ("389", "1175", "384", "1170"):
        for term in unique(bd, "prim", uid).findall("termList/*"):
            index = int(term.findtext("dco/typeDesc")[7:-1])
            require(
                heap_type(meta, index)[0].get("Type") == "NumUInt32",
                "Core clock arithmetic representation changed",
            )
    return (
        f"Core protocol: 27 additional diagrams, {sum(map(len, NETS.values()))} "
        "direct nets; timeout bypass in byte branches"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(
        validate_protocol(
            checked_roots(parser.parse_args().archive)["TPG300-Driver Core"]
        )
    )


if __name__ == "__main__":
    main()
