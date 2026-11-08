"""Pinned pressure helper, saved separator cases and three root call sites.

Static graph checks only. No LabVIEW, driver, clock or transport execution.
The consumer census proves direct bundle inputs, not downstream permissions.
"""

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6220_read_error_contract import connector_map
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import case, local, operations
from validate_acq_tpg300_startup import selectors

FILES = ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml")
PINS = {
    "pressure": (
        "5D499121F595353D24CED9F93CFABA162E9AB8AF05C912D576734FA704E166CC",
        (
            "CC6E9DF7B890B78659804B94A108E1BE467F58BF6D912E3CC438549287A28DEA",
            "F8C87DA1A488BAB5FBF42B8150301B3DF363299912FD0FCD294FFA2352C8DEC3",
            "4466F764D63D41DBF1BEC4DEBEFA7F4CBFB4BF88207FA43A3DBEED7EAEA44CDF",
        ),
    ),
    "point": (
        "C5AD9A875DF3EC4A410BC28A37A9A3A50F44C352C2E97E35D227133BB660712C",
        (
            "2A09E81B46D2DAF916C5486C491BC3DDE75915A1680C68AA68EDE0CD1471F552",
            "035E6F0B4E44D48E09EE61DFF88DC75F93E0ED381095BD06FA7E0975D68FFECA",
            "82C3EA07186124F9CFC00E69D376ABBAB00C0EE7F33C2319B984FAC3C5CF6EA0",
        ),
    ),
}
PRESSURE_NETS = (
    ("282", "384"),
    ("171", "299"),
    ("254", "291"),
    ("237", "377"),
    ("314", "222"),
    ("320", "273"),
    ("193", "326"),
    ("423", "303"),
    ("394", "432"),
    ("649", "403"),
    ("414", "720"),
    ("487", "364"),
    ("389", "463"),
    ("94", "286"),
    ("210", "183"),
    ("259", "185"),
)
POINT_NETS = {
    "36": (
        ("218", "205", "160"),
        ("154", "176"),
        ("148", "157"),
        ("181", "40"),
        ("38", "190"),
    ),
    "164": (("201", "196"), ("186", "68"), ("42", "59"), ("65", "178")),
    "44": (
        ("195", "78"),
        ("108", "234"),
        ("58", "235"),
        ("97", "64"),
        ("67", "228", "100"),
        ("89", "51", "103"),
        ("84", "106"),
        ("247", "55", "92"),
        ("245", "81"),
        ("238", "75"),
    ),
    "166": (("188", "179"),),
}
CALLER_NETS = {
    "48320": (
        ("45936", "45928"),
        ("53878", "45172"),
        ("46260", "53253"),
        ("46253", "70116"),
        ("53872", "70780"),
        ("46330", "46303"),
        ("47034", "46321"),
        ("48855", "53899"),
        ("48042", "53905"),
    ),
    "52460": (
        ("52653", "52650"),
        ("52484", "52640"),
        ("52478", "52626"),
        ("52678", "52505"),
        ("52470", "52511"),
    ),
}


def checked_export(path, kind):
    archive_hash, xml_hashes = PINS[kind]
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper() == archive_hash,
        kind + " archive changed",
    )
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 4, kind + " archive census changed")
        roots = {}
        for name, expected in zip(FILES, xml_hashes):
            data = archive.read(name)
            require(
                hashlib.sha256(data).hexdigest().upper() == expected,
                kind + " XML changed",
            )
            roots[name] = ET.fromstring(data)
        return roots


def census(bd, expected):
    require(
        {n.get("uid") for n in bd.iter() if n.get("class") == "diag"} == set(expected),
        "helper diagram census changed",
    )


def validate_pressure(roots):
    meta, bd, fp = (roots[n] for n in FILES)
    census(bd, ("86",))
    frame = unique(bd, "diag", "86")
    operations(
        frame,
        [
            ("iUse", "428"),
            ("iUse", "369"),
            ("prim", "308"),
            ("prim", "293"),
            ("prim", "85"),
            ("prim", "206"),
        ]
        + [
            (None, uid)
            for uid in (
                "254",
                "237",
                "193",
                "171",
                "720",
                "649",
                "487",
                "463",
                "183",
                "185",
                "94",
            )
        ],
        "pressure helper",
    )
    exact_wires(frame, PRESSURE_NETS, "pressure helper")
    require(
        connector_map(fp)
        == [
            (0, "718"),
            (1, "28"),
            (2, "35"),
            (3, "461"),
            (8, "647"),
            (9, "20"),
            (11, "484"),
        ],
        "pressure connector identity changed",
    )
    require(
        call_names(meta)
        == {"369": "TPG300-Driver Core.vi", "428": "TPG300 Point -- Terminator.vi"},
        "pressure custom calls changed",
    )
    for port, control in (
        ("720", "718"),
        ("649", "647"),
        ("487", "484"),
        ("463", "461"),
        ("183", "28"),
        ("185", "35"),
        ("94", "20"),
    ):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control,
            "pressure FP binding changed",
        )
    for port, slot in (
        ("364", 0),
        ("377", 1),
        ("389", 4),
        ("384", 5),
        ("394", 8),
        ("403", 11),
        ("414", 15),
    ):
        public_term(unique(bd, "iUse", "369"), port, slot)
    for port, slot in (("423", 0), ("432", 1)):
        public_term(unique(bd, "iUse", "428"), port, slot)
    for port, value in (
        ("171", "0000000150"),
        ("193", "000000012C"),
        ("237", "0000"),
        ("254", "00000004000000024131000000024132000000024231000000024232"),
    ):
        require(
            constant(frame, port) == value, "pressure command/parser literal changed"
        )
    primitive(bd, "293", 1531, ("282", "286", "291", "299"))
    primitive(bd, "308", 1535, ("303", "326", "311", "314", "317", "320", "323"))
    primitive(bd, "206", 1184, ("210", "213", "216", "219", "222"))
    primitive(bd, "85", 1187, ("259", "260", "264", "266", "269", "273"))
    for uid, port, expected in (
        ("206", "210", "NumInt32"),
        ("85", "259", "NumFloat64"),
        ("85", "264", "Boolean"),
    ):
        descriptor = unique(bd, "prim", uid).findtext(
            f"termList/*[@uid='{port}']/dco/typeDesc"
        )
        value, _ = heap_type(meta, int(descriptor[7:-1]))
        require(
            value.get("Type") == expected, "pressure primitive representation changed"
        )
    return "Pressure helper: one diagram, 16 nets; no error-gated numeric assignment"


def validate_point(roots):
    meta, bd, fp = (roots[n] for n in FILES)
    census(bd, POINT_NETS)
    ops = {
        "36": [
            (None, "218"),
            ("select", "207"),
            ("prim", "150"),
            (None, "148"),
            (None, "40"),
            (None, "38"),
        ],
        "164": [("whileLoop", "281"), (None, "42")],
        "44": [
            ("prim", "236"),
            (None, "108"),
            ("prim", "93"),
            ("prim", "85"),
            ("concat", "70"),
            (None, "51"),
            (None, "48"),
        ],
        "166": [],
    }
    for uid, nets in POINT_NETS.items():
        frame = unique(bd, "diag", uid)
        operations(frame, ops[uid], "point helper " + uid)
        exact_wires(frame, nets, "point helper " + uid)
    require(
        connector_map(fp) == [(0, "14"), (1, "7")] and not call_names(meta),
        "point helper connector/calls changed",
    )
    primitive(bd, "150", 1102, ("154", "157", "160"))
    require(
        unique(bd, "prim", "150").findtext("objFlags") == "65536",
        "point comparison string mode changed",
    )
    for uid, port, value in (
        ("36", "218", "000000012C"),
        ("36", "148", "000000012E"),
        ("164", "42", "0000000000"),
        ("44", "108", "000000025C2E"),
    ):
        require(
            constant(unique(bd, "diag", uid), port) == value,
            "point helper literal changed",
        )
    selectors(unique(bd, "select", "207"), ("164", "166"))
    # False contains the replacement loop; True forwards input unchanged.
    # The saved literal comparison is ',' == '.', hence False, not a locale query.
    primitive(bd, "236", 1535, ("228", "234", "235", "238", "241", "245", "247"))
    primitive(bd, "93", 1516, ("97", "100", "103", "106"))
    primitive(bd, "85", 1114, ("89", "92"))
    loop = unique(bd, "whileLoop", "281")
    require(
        loop.find("loopTestDCO").get("uid") == "49"
        and loop.findtext("loopTestDCO/objFlags") == "1"
        and loop.find("loopTestDCO/termList/*").get("uid") == "51",
        "point loop Continue-if-True condition changed",
    )
    for port, control in (("38", "7"), ("40", "14")):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control,
            "point helper FP binding changed",
        )
    for port, children in (
        ("176", ("173", "174", "176")),
        ("181", ("178", "179", "181")),
        ("190", ("186", "188", "190")),
        ("205", ("201", "202", "205")),
    ):
        dco = unique(bd, "select", "207").find(f"termList/*[@uid='{port}']/dco")
        require(
            tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
            "point case tunnel mapping changed",
        )
    for port, children in (
        ("196", ("195", "196")),
        ("68", ("67", "68")),
        ("59", ("58", "59")),
    ):
        dco = loop.find(f"termList/*[@uid='{port}']/dco")
        require(
            tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
            "point loop input/feedback mapping changed",
        )
    for port, right, children in (
        ("68", "61", ("64", "65")),
        ("59", "52", ("55", "56")),
    ):
        rsr = loop.find(f"termList/*[@uid='{port}']/dco/rsrDCO")
        require(
            rsr.get("uid") == right
            and tuple(t.get("uid") for t in rsr.findall("termList/*")) == children,
            "point loop output/feedback mapping changed",
        )
    concat = unique(bd, "concat", "70")
    require(
        tuple(t.get("uid") for t in concat.findall("termList/*"))
        == ("84", "75", "78", "81"),
        "point concat port order changed",
    )
    return (
        "Point helper: four diagrams, 20 nets; "
        "saved comma/period test enters replacement loop"
    )


def validate_callers(root):
    ops = {
        "48320": [
            (None, "45936"),
            ("prim", "45909"),
            ("gRef", "45155"),
            ("gRef", "53243"),
            ("iUse", "70745"),
            ("iUse", "70082"),
            ("gRef", "47016"),
            (None, "46330"),
            ("iUse", "46178"),
            ("iUse", "53865"),
            (None, "48855"),
            ("gRef", "48012"),
        ],
        "52460": [
            (None, "52653"),
            ("prim", "52645"),
            ("gRef", "52637"),
            ("iUse", "52596"),
            ("iUse", "52475"),
            (None, "52678"),
            ("gRef", "52467"),
        ],
    }
    for uid, nets in CALLER_NETS.items():
        frame = unique(root, "diag", uid)
        operations(frame, ops[uid], "pressure caller " + uid)
        exact_wires(frame, nets, "pressure caller " + uid)
    sequence = unique(root, "sequence", "48312")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")] == ["48320", "52460"],
        "pressure sequence order changed",
    )
    for uid, port, bank, write in (
        ("53243", "53253", 53, True),
        ("45155", "45172", 54, True),
        ("52637", "52640", 60, True),
        ("47016", "47034", 52, False),
        ("48012", "48042", 51, False),
        ("52467", "52470", 51, False),
    ):
        local(root, uid, port, bank, write)
    for uid, term, value in (
        ("48320", "45936", "000001F4"),
        ("48320", "46330", "0000000000"),
        ("48320", "48855", "0000000000"),
        ("52460", "52653", "000001F4"),
        ("52460", "52678", "00000003"),
    ):
        require(
            constant(unique(root, "diag", uid), term) == value,
            "pressure caller sensor/wait literal changed",
        )
    primitive(root, "45909", 1302, ("45925", "45928"))
    primitive(root, "52645", 1302, ("52647", "52650"))
    for uid, ports in (
        ("46178", ("46253", "46257", "46260", "46303", "46321")),
        ("53865", ("53872", "53875", "53878", "53899", "53905")),
        ("52475", ("52478", "52481", "52484", "52505", "52511")),
    ):
        for port, slot in zip(ports, (0, 1, 2, 9, 11)):
            public_term(unique(root, "iUse", uid), port, slot)
    # Exhaustive saved-root local census: one writer and one direct reader each.
    expected = {
        53: {("48320", "53243", "53253", "0"), ("45859", "7630", "74655", "1")},
        54: {("48320", "45155", "45172", "0"), ("45859", "53929", "53939", "1")},
        60: {("52460", "52637", "52640", "0"), ("45859", "88601", "88609", "1")},
    }
    for bank, entries in expected.items():
        actual = set()
        for d in root.iter():
            if d.get("class") != "diag":
                continue
            for n in d.findall("zPlaneList/*"):
                if n.get("class") == "gRef" and n.findtext(
                    "termList/*/dco/paramIdx"
                ) == str(bank):
                    t = n.find("termList/*")
                    actual.add(
                        (
                            d.get("uid"),
                            n.get("uid"),
                            t.get("uid"),
                            t.findtext("dco/objFlags", "0"),
                        )
                    )
        require(actual == entries, "pressure bank reader/writer census changed")
    bundle = unique(root, "nMux", "21214")
    require(
        bundle.findtext("objFlags") == "262144", "pressure consumer bundle mode changed"
    )
    frame = unique(root, "diag", "45859")
    for source, port, field in (
        ("74655", "72069", 10),
        ("53939", "72076", 11),
        ("88609", "96061", 20),
    ):
        require(
            bundle.findtext(f"termList/*[@uid='{port}']/dco/i") == str(field),
            "pressure consumer field index changed",
        )
        matches = [
            tuple(t.get("uid") for t in s.findall("termList/*"))
            for s in frame.findall("signalList/*")
            if any(t.get("uid") == source for t in s.findall("termList/*"))
        ]
        require(matches == [(source, port)], "pressure direct consumer wire changed")
    local(root, "9174", "14825", 41)
    local(root, "30536", "30539", 41, True)
    for terms in (("14825", "21225"), ("21221", "30539")):
        require(
            terms
            in [
                tuple(t.get("uid") for t in s.findall("termList/*"))
                for s in frame.findall("signalList/*")
            ],
            "pressure VAM aggregate flow changed",
        )
    # The two whole-cluster writers' sequence order is checked in the VAM proof.
    writers = {
        n.get("uid")
        for n in root.iter()
        if n.get("class") == "gRef"
        and n.findtext("termList/*/dco/paramIdx") == "41"
        and n.findtext("termList/*/dco/objFlags", "0") == "0"
    }
    require(writers == {"30536", "46917"}, "VAM-A whole-cluster writer census changed")
    other = unique(root, "nMux", "46933")
    require(
        other.findtext("objFlags") == "262144"
        and tuple(
            int(t.findtext("dco/i"))
            for t in other.findall("termList/*")
            if t.find("dco/i") is not None
        )
        == (63, 32, 33, 34, 35, 36, 37, 38, 39),
        "other VAM-A writer fields changed",
    )
    local(root, "46926", "46930", 41)
    local(root, "46917", "46920", 41, True)
    frame = unique(root, "diag", "46898")
    for terms in (("46930", "46938"), ("46935", "46920")):
        require(
            terms
            in [
                tuple(t.get("uid") for t in s.findall("termList/*"))
                for s in frame.findall("signalList/*")
            ],
            "other VAM aggregate flow changed",
        )
    return (
        "Root callers: two frames, 14 nets; Status discarded; "
        "pressure banks feed VAM-A fields 10/11/20; two whole-cluster writers"
    )


def validate_pressure_publication(root):
    frame = unique(root, "diag", "77141")
    operations(
        frame,
        [
            (None, "30605"),
            ("gRef", "76469"),
            ("select", "28682"),
            ("sharedVariableDynamicWrite", "24576"),
        ],
        "VAM-A pressure publication",
    )
    exact_wires(
        frame,
        (("24593", "40177"), ("30605", "24584"), ("76476", "24596")),
        "VAM-A pressure publication",
    )
    uri = b"ni.var.psp://10.20.30.2/SUPERVISION/VAM-A"
    require(
        bytes.fromhex(constant(frame, "30605")) == len(uri).to_bytes(4, "big") + uri,
        "VAM-A pressure publication destination changed",
    )
    local(root, "76469", "76476", 41)
    writer = unique(root, "sharedVariableDynamicWrite", "24576")
    require(
        [t.get("uid") for t in writer.findall("termList/*")]
        == ["24584", "24587", "24590", "24593", "24596"]
        and [t.findtext("dco/terminal_ID", "") for t in writer.findall("termList/*")]
        == ["0B", "03", "08", "", "0A"],
        "VAM-A writer argument slots changed",
    )
    true = case(root, "28682", "40197", "42989")
    operations(
        true,
        [("gRef", "43040"), (None, "43005"), ("gRef", "43027")],
        "VAM-A publication fault",
    )
    exact_wires(true, (("43005", "43033", "43045"),), "VAM-A publication fault")
    require(
        constant(true, "43005") == "01", "VAM-A publication stop assignment changed"
    )
    local(root, "43027", "43033", 30, True)
    local(root, "43040", "43045", 45, True)
    return (
        "VAM-A publication: three diagrams, four nets; "
        "publication fault sets stop banks 30/45"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    print(
        validate_pressure(
            checked_export(directory / "TPG300_pressure_XML_20261002.zip", "pressure")
        )
    )
    print(
        validate_point(
            checked_export(directory / "TPG300_point_XML_20261002.zip", "point")
        )
    )
    print(validate_callers(checked_root(directory / "0_ACQ_ELYSE_XML_sha6fe8.zip")))
    print(
        validate_pressure_publication(
            checked_root(directory / "0_ACQ_ELYSE_XML_sha6fe8.zip")
        )
    )


if __name__ == "__main__":
    main()
