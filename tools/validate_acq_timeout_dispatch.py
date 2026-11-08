"""Pin the entire Timeout procedure/counter ingress frame and every explicit arm.

Missing numeric default metadata and fractional index coercion remain gaps.
The counter helper has a separate complete source validator; this proves its
caller arguments, unconditional reset and disconnected publication error.
"""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

# Diagram, property node, saved target DDO, True constant, six terminals,
# registered event index. Values are pinned independently of generated CSV.
DISPATCH = (
    (
        "11259",
        "4217",
        "59266",
        "21898",
        ("4241", "4250", "4264", "4272", "4280", "26863"),
        3,
    ),
    (
        "1412",
        "1444",
        "59274",
        "1586",
        ("1448", "1454", "1461", "1473", "1488", "1520"),
        4,
    ),
    (
        "27623",
        "27658",
        "59370",
        "27749",
        ("27667", "27676", "27685", "27694", "27703", "27721"),
        5,
    ),
    (
        "22923",
        "22949",
        "59378",
        "23033",
        ("22956", "22960", "22970", "22978", "22983", "23001"),
        6,
    ),
    (
        "23712",
        "29098",
        "66579",
        "29145",
        ("29104", "29107", "29110", "29113", "29116", "29126"),
        12,
    ),
    (
        "24058",
        "24069",
        "66587",
        "24105",
        ("24074", "24079", "24082", "24085", "24088", "24094"),
        7,
    ),
    (
        "24408",
        "30677",
        "66627",
        "30785",
        ("30697", "30706", "30715", "30724", "30733", "30751"),
        13,
    ),
    (
        "25501",
        "31277",
        "66635",
        "31309",
        ("31280", "31283", "31286", "31289", "31292", "31298"),
        8,
    ),
    (
        "25517",
        "25528",
        "66675",
        "25628",
        ("25531", "25538", "25556", "25568", "25577", "25601"),
        14,
    ),
    (
        "26728",
        "31906",
        "66683",
        "31937",
        ("31909", "31912", "31915", "31918", "31921", "31927"),
        9,
    ),
    (
        "26791",
        "32446",
        "66723",
        "32477",
        ("32449", "32452", "32455", "32458", "32461", "32467"),
        15,
    ),
    (
        "26875",
        "26909",
        "66731",
        "33001",
        ("32973", "32976", "32979", "32982", "32985", "32991"),
        10,
    ),
    (
        "26947",
        "33514",
        "59386",
        "33545",
        ("33517", "33520", "33523", "33526", "33529", "33535"),
        11,
    ),
    (
        "26989",
        "27019",
        "59482",
        "34062",
        ("27028", "27037", "27046", "27055", "27064", "34052"),
        18,
    ),
    (
        "27334",
        "27364",
        "59474",
        "27460",
        ("27373", "27382", "27391", "27400", "27409", "27427"),
        19,
    ),
    (
        "17382",
        "22889",
        "59314",
        "23094",
        ("22902", "22909", "22919", "22946", "23027", "23071"),
        20,
    ),
    (
        "23812",
        "23823",
        "59330",
        "23858",
        ("23826", "23829", "23832", "23835", "23838", "23847"),
        22,
    ),
    (
        "27983",
        "28033",
        "59322",
        "28201",
        ("28042", "28051", "28060", "28069", "28084", "28114"),
        21,
    ),
    (
        "29231",
        "29242",
        "59426",
        "29273",
        ("29245", "29248", "29251", "29254", "29257", "29263"),
        23,
    ),
    (
        "31117",
        "31132",
        "59434",
        "31163",
        ("31135", "31138", "31141", "31144", "31147", "31153"),
        24,
    ),
    (
        "31791",
        "31802",
        "66411",
        "31833",
        ("31805", "31808", "31811", "31814", "31817", "31823"),
        16,
    ),
    (
        "32389",
        "32400",
        "66443",
        "32431",
        ("32403", "32406", "32409", "32412", "32415", "32421"),
        25,
    ),
    (
        "33033",
        "33044",
        "66459",
        "33077",
        ("33047", "33050", "33054", "33058", "33061", "33067"),
        None,
    ),
    (
        "33899",
        "33910",
        "66419",
        "33941",
        ("33913", "33916", "33919", "33922", "33925", "33931"),
        17,
    ),
)
NETS = {
    "22247": (
        ("22214", "17625", "22933"),
        ("17622", "15005"),
        ("11758", "22221"),
        ("21306", "22224"),
        ("15714", "21322"),
        ("44864", "24072", "29998"),
        ("24075", "5740", "21110", "28879"),
        ("1487", "28569"),
        ("22728", "23224"),
        ("21104", "22731"),
        ("5675", "22734"),
        ("22025", "21107"),
    ),
    "9471": (("85221", "19100"),),
    "23208": (),
    "23214": (("29989", "29942"), ("28875", "28860"), ("28560", "28516")),
    "23641": (
        ("29933", "30694"),
        ("26193", "22423", "21193"),
        ("23152", "22410"),
        ("22384", "31347", "22893"),
        ("22890", "21088"),
        ("23009", "26203"),
        ("28856", "23012"),
        ("23650", "22517"),
        ("21189", "23671"),
        ("27138", "26200"),
        ("21083", "23680"),
        ("31344", "23677"),
        ("29096", "21185"),
        ("30685", "21073"),
        ("28511", "29101"),
    ),
    "22979": (("24963", "23478"), ("23474", "23252"), ("23240", "23477")),
    "1507": (("5331", "21458"), ("5125", "21471")),
}
OPS = {
    "22247": [("label", x) for x in ("27559", "27317", "15988", "7938")]
    + [("gRef", x) for x in ("13820", "1823", "44855", "6")]
    + [("prim", x) for x in ("17616", "22203", "21295", "1984", "22666", "21098")]
    + [
        ("select", "8105"),
        ("select", "23199"),
        ("nMux", "22699"),
        (None, "11758"),
        (None, "22025"),
    ],
    "9471": [(None, "85221"), ("gRef", "19042")],
    "23208": [],
    "23214": [("sequence", "23633")],
    "23641": [
        (None, "23152"),
        (None, "27138"),
        ("prim", "22328"),
        ("prim", "22884"),
        ("prim", "15887"),
        ("prim", "26175"),
        ("iUse", "23634"),
        ("iUse", "22439"),
        ("aIndx", "21122"),
        ("aIndx", "21053"),
        ("prim", "20986"),
        ("prim", "29080"),
    ],
    "22979": [
        ("label", "20960"),
        (None, "24963"),
        ("nMux", "23468"),
        ("gRef", "23248"),
        ("gRef", "23233"),
    ],
    "1507": [
        ("label", "20431"),
        ("sharedVariableDynamicWrite", "21449"),
        (None, "5331"),
        ("gRef", "5036"),
    ],
}
PRIMITIVES = (
    ("17616", 1057, ("17622", "17625")),
    ("22203", 1901, ("22214", "22218", "22221", "22224")),
    ("21295", 1169, ("21306", "21322")),
    ("1984", 1117, ("5675", "5740")),
    ("22666", 1061, ("22728", "22731", "22734")),
    ("21098", 1111, ("21104", "21107", "21110")),
    ("22328", 1052, ("22384", "22410", "22423")),
    ("22884", 1057, ("22890", "22893")),
    ("15887", 1058, ("23009", "23012")),
    ("26175", 1056, ("26193", "26197", "26200", "26203")),
    ("20986", 1169, ("30685", "30694")),
    ("29080", 1169, ("29096", "29101")),
)


def _structure(root, cls, uid, diagrams, ports):
    node = unique(root, cls, uid)
    require(
        tuple(d.get("uid") for d in node.findall("diagramList/*")) == diagrams
        and tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
        "Timeout structure frame order/port list changed",
    )
    if cls == "select":
        require(
            [
                (
                    x.findtext("start"),
                    x.findtext("end"),
                    x.findtext("diagramIdx"),
                    x.findtext("startRangeType"),
                    x.findtext("endRangeType"),
                )
                for x in node.findall("SelectRangeArray32/*")
            ]
            == [(str(i), str(i), str(i), "0", "0") for i in range(len(diagrams))]
            and node.find("SelectDefaultCase") is None,
            "Timeout explicit selector ranges/default metadata changed",
        )
    return node


def _fields(root, meta, uid, count, typ):
    desc = unique(root, "gRef", uid).findtext("termList/*/dco/typeDesc")
    aggregate, flat = heap_type(meta, int(desc[7:-1]))
    require(
        aggregate.get("Type") == "Cluster"
        and len(aggregate.findall("TypeDesc")) == count
        and all(
            flat[int(t.get("TypeID"))].get("Type") == typ
            for t in aggregate.findall("TypeDesc")
        ),
        "Timeout input bank type/field count changed",
    )


def validate_dispatch(root, meta):
    for uid, nets in NETS.items():
        frame = unique(root, "diag", uid)
        exact_wires(frame, nets, "Timeout procedure/counter " + uid)
        operations(frame, OPS[uid], "Timeout procedure/counter " + uid)
    for args in PRIMITIVES:
        primitive(root, *args)
    for args in (
        ("13820", "22933", 43, True),
        ("1823", "15714", 36, False),
        ("44855", "44864", 39, False),
        ("6", "1487", 21, False),
        ("19042", "19100", 35, True),
        ("23248", "23252", 39, True),
        ("23233", "23240", 39, False),
        ("5036", "5125", 39, False),
    ):
        local(root, *args)
    _fields(root, meta, "1823", 29, "Boolean")
    _fields(root, meta, "44855", 33, "NumFloat64")
    _fields(root, meta, "6", 8, "Refnum")
    _structure(
        root,
        "select",
        "8105",
        ("9471",) + tuple(row[0] for row in DISPATCH),
        ("15005",),
    )
    _structure(
        root,
        "select",
        "23199",
        ("23208", "23214"),
        ("23224", "28569", "28879", "29998"),
    )
    _structure(
        root,
        "sequence",
        "23633",
        ("23641", "22979", "1507"),
        ("28516", "28860", "29942"),
    )
    for cls, uid, links in (
        (
            "select",
            "23199",
            (
                ("23222", "23223", "23224"),
                ("28549", "28560", "28569"),
                ("28871", "28875", "28879"),
                ("29979", "29989", "29998"),
            ),
        ),
        (
            "sequence",
            "23633",
            (
                ("28511", "22987", "1534", "28516"),
                ("28856", "22993", "1543", "28860"),
                ("29933", "22996", "1552", "29942"),
            ),
        ),
    ):
        require(
            tuple(
                tuple(x.get("uid") for x in t.findall("dco/termList/*"))
                for t in unique(root, cls, uid).findall("termList/*")
            )
            == links,
            "Timeout parent/child tunnel identity changed",
        )
    for frame_uid, port, value in (
        ("22247", "11758", "01"),
        ("22247", "22025", "4031000000000000"),
        ("9471", "85221", "0000"),
        ("23641", "23152", "4000000000000000"),
        ("23641", "27138", "4000000000000000"),
        ("22979", "24963", "BFF0000000000000"),
    ):
        require(
            constant(unique(root, "diag", frame_uid), port) == value,
            "Timeout search/range/arithmetic/reset literal changed",
        )

    event_specs = unique(root, "eventStruct", "43").findall("EventNodeEvents/*")
    require(len(event_specs) == 26, "Timeout event register count changed")
    for diag, prop, ddo, literal, ports, event in DISPATCH:
        frame = unique(root, "diag", diag)
        operations(frame, [("propNode", prop), (None, literal)], "DPS signaling arm")
        exact_wires(frame, ((literal, ports[4], ports[5]),), "DPS signaling arm")
        require(constant(frame, literal) == "01", "DPS property value not True")
        node = unique(root, "propNode", prop)
        terms = node.findall("termList/*")
        require(
            node.find("ddo").get("uid") == ddo
            and tuple(t.get("uid") for t in terms) == ports
            and [t.findtext("dco/objFlags", "0") for t in terms]
            == ["65536", "262145", "131072", "524289", "0", "0"]
            and [t.findtext("dco/propList/*/PropItemName") for t in terms[4:]]
            == ['"Value"', '"Val(Sgnl)"']
            and [t.findtext("dco/propList/*/PropItemCode") for t in terms[4:]]
            == ["104013842", "104013860"],
            "DPS property target/order/direction changed",
        )
        matches = [
            x.findtext("diagramIdx") for x in event_specs if x.findtext("ddoUID") == ddo
        ]
        require(
            matches == ([] if event is None else [str(event)]),
            "DPS event registration target changed",
        )

    for uid, flags, ports, indices in (
        ("22699", "327680", ("24072", "24075"), (0, 32)),
        ("23468", "262144", ("23474", "23477", "23478"), (0, 0, 32)),
    ):
        node = unique(root, "nMux", uid)
        require(
            node.findtext("objFlags") == flags
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and tuple(int(t.findtext("dco/i", "0")) for t in node.findall("termList/*"))
            == indices,
            "Timeout counter unbundle/reset index changed",
        )
    for uid, ports in (
        ("21122", ("21185", "21189", "21193")),
        ("21053", ("21073", "31344", "31347", "21083", "21088")),
    ):
        require(
            tuple(
                t.get("uid") for t in unique(root, "aIndx", uid).findall("termList/*")
            )
            == ports,
            "Timeout task/timing Index Array ports changed",
        )
    names = call_names(meta)
    for uid, name, ports in (
        (
            "23634",
            "1_ACQ_WRITE_NI6602.vi",
            (
                "23650",
                "23653",
                "23656",
                "23659",
                "23662",
                "23665",
                "23668",
                "23671",
                "23674",
                "23677",
                "23680",
                "23683",
            ),
        ),
        (
            "22439",
            "Simple Error Handler.vi",
            (
                "22446",
                "22459",
                "22469",
                "22483",
                "22494",
                "22500",
                "22504",
                "22510",
                "22514",
                "22517",
            ),
        ),
    ):
        node = unique(root, "iUse", uid)
        require(
            names[uid] == name
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
            "Timeout counter helper identity/connector changed",
        )
        for i, port in enumerate(ports):
            public_term(node, port, i)
    frame = unique(root, "diag", "1507")
    uri = b"ni.var.psp://10.20.30.2/SUPERVISION/C1011NI6602"
    require(
        bytes.fromhex(constant(frame, "5331")) == len(uri).to_bytes(4, "big") + uri,
        "Timeout counter publication URI changed",
    )
    writer = unique(root, "sharedVariableDynamicWrite", "21449")
    require(
        tuple(t.get("uid") for t in writer.findall("termList/*"))
        == ("21458", "21461", "21464", "21468", "21471")
        and [t.findtext("dco/terminal_ID", "") for t in writer.findall("termList/*")]
        == ["0B", "03", "08", "", "0A"],
        "Timeout counter PSP caller ports changed",
    )
    return (
        "PASS: Timeout procedure/counter ingress 31 diagrams / 60 nets / "
        "24 explicit property targets"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_dispatch(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
