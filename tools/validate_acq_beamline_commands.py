"""Prove ten complete beam-line tail diagrams against pinned original XML.

Frame0 arithmetic/UI handling is not closed. Its Boolean sequence-local
producer and >=128 comparator wires are checked as a supplemental facet.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

# Events: sequence, four frames, selector/port, False/True, sequence-local
# definition/four ports, comparator/three ports and threshold literal.
EVENTS = {
    1: (
        "11069",
        ("11087", "14333", "14553", "15917"),
        "14339",
        "14341",
        "14348",
        "14354",
        "11240",
        ("11239", "11242", "11243", "15930"),
        "14212",
        ("14214", "14217", "14220"),
        "11227",
    ),
    2: (
        "19041",
        ("19057", "64765", "64942", "14963"),
        "64771",
        "64773",
        "64780",
        "64786",
        "19191",
        ("19190", "19193", "62725", "14976"),
        "64642",
        ("64644", "64647", "64650"),
        "19178",
    ),
}
SOURCES = {
    1: (
        "14360",
        "14363",
        28,
        "14366",
        "14368",
        (
            ("14371", 42),
            ("14374", 54),
            ("14377", 66),
            ("14380", 78),
            ("14383", 114),
            ("14386", 126),
            ("14389", 6),
            ("14392", 18),
            ("14395", 90),
            ("14398", 102),
            ("14401", 30),
        ),
    ),
    2: (
        "64792",
        "64795",
        33,
        "64798",
        "64800",
        (
            ("64803", 54),
            ("64806", 66),
            ("64809", 102),
            ("64812", 90),
            ("64815", 78),
            ("64818", 6),
            ("64821", 18),
            ("64824", 30),
            ("64827", 42),
        ),
    ),
}
# Bank, read node/port, write node/port, Bundle node/output/input and fields.
BUNDLES = {
    1: (
        (
            9,
            "14405",
            "14408",
            "14436",
            "14439",
            "14411",
            "14413",
            "14416",
            (
                ("14417", 0, "14371"),
                ("14420", 1, "14374"),
                ("14423", 2, "14377"),
                ("14426", 3, "14380"),
                ("14429", 4, "14383"),
                ("14432", 5, "14386"),
            ),
        ),
        (
            10,
            "14442",
            "14445",
            "14467",
            "14470",
            "14448",
            "14450",
            "14453",
            (
                ("14454", 8, "14389"),
                ("14457", 5, "14392"),
                ("14460", 0, "14395"),
                ("14463", 1, "14398"),
            ),
        ),
        (
            11,
            "14473",
            "14476",
            "14489",
            "14492",
            "14479",
            "14481",
            "14484",
            (("14485", 5, "14401"),),
        ),
    ),
    2: (
        (
            9,
            "64831",
            "64834",
            "64856",
            "64859",
            "64837",
            "64839",
            "64842",
            (
                ("64843", 6, "64803"),
                ("64846", 7, "64806"),
                ("64849", 9, "64809"),
                ("64852", 8, "64812"),
            ),
        ),
        (
            10,
            "64862",
            "64865",
            "64890",
            "64893",
            "64868",
            "64870",
            "64873",
            (
                ("64874", 9, "64815"),
                ("64877", 6, "64818"),
                ("64880", 7, "64821"),
                ("64883", 3, "64824"),
                ("64886", 4, "64827"),
            ),
        ),
    ),
}
# Bank, local node/port, URI literal, writer/five ports, error-handler/ten ports.
PUBLICATIONS = {
    1: (
        (
            9,
            "14631",
            "14634",
            "14559",
            "14787",
            ("14789", "14792", "14795", "14798", "14801"),
            "14637",
            (
                "14640",
                "14643",
                "14646",
                "14649",
                "14652",
                "14655",
                "14658",
                "14661",
                "14664",
                "14667",
            ),
        ),
        (
            10,
            "14670",
            "14673",
            "14577",
            "14804",
            ("14806", "14809", "14812", "14815", "14818"),
            "14676",
            (
                "14679",
                "14682",
                "14685",
                "14688",
                "14691",
                "14694",
                "14697",
                "14700",
                "14703",
                "14706",
            ),
        ),
        (
            11,
            "14709",
            "14712",
            "14595",
            "14821",
            ("14823", "14826", "14829", "14832", "14835"),
            "14715",
            (
                "14718",
                "14721",
                "14724",
                "14727",
                "14730",
                "14733",
                "14736",
                "14739",
                "14742",
                "14745",
            ),
        ),
        (
            12,
            "14748",
            "14751",
            "14613",
            "14838",
            ("14840", "14843", "14846", "14849", "14852"),
            "14754",
            (
                "14757",
                "14760",
                "14763",
                "14766",
                "14769",
                "14772",
                "14775",
                "14778",
                "14781",
                "14784",
            ),
        ),
    ),
    2: (
        (
            9,
            "65020",
            "65023",
            "64948",
            "65176",
            ("65178", "65181", "65184", "65187", "65190"),
            "65026",
            (
                "65029",
                "65032",
                "65035",
                "65038",
                "65041",
                "65044",
                "65047",
                "65050",
                "65053",
                "65056",
            ),
        ),
        (
            10,
            "65059",
            "65062",
            "64966",
            "65193",
            ("65195", "65198", "65201", "65204", "65207"),
            "65065",
            (
                "65068",
                "65071",
                "65074",
                "65077",
                "65080",
                "65083",
                "65086",
                "65089",
                "65092",
                "65095",
            ),
        ),
        (
            11,
            "65098",
            "65101",
            "64984",
            "65210",
            ("65212", "65215", "65218", "65221", "65224"),
            "65104",
            (
                "65107",
                "65110",
                "65113",
                "65116",
                "65119",
                "65122",
                "65125",
                "65128",
                "65131",
                "65134",
            ),
        ),
        (
            12,
            "65137",
            "65140",
            "65002",
            "65227",
            ("65229", "65232", "65235", "65238", "65241"),
            "65143",
            (
                "65146",
                "65149",
                "65152",
                "65155",
                "65158",
                "65161",
                "65164",
                "65167",
                "65170",
                "65173",
            ),
        ),
    ),
}
WAITS = {
    1: ("10870", "15319", "15176", ("15182", "15185")),
    2: ("14791", "14756", "14705", ("14723", "14732")),
}


def td(meta, term):
    value = term.findtext("dco/typeDesc")
    require(value and value.startswith("TypeID("), "typed terminal absent")
    return heap_type(meta, int(value[7:-1]))[0]


def bank_type(meta, term, bank):
    desc = td(meta, term)
    flat = heap_type(meta, int(term.findtext("dco/typeDesc")[7:-1]))[1]
    fields = desc.findall("TypeDesc")
    require(
        desc.get("Type") == "Cluster"
        and desc.get("Label") == f"C{bank - 3}NI6703"
        and len(fields) == 10
        and all(flat[int(f.get("TypeID"))].get("Type") == "NumFloat64" for f in fields),
        "command bank identity/ten DBL fields changed",
    )


def mux(root, meta, uid, flags, ports, indices):
    node = unique(root, "nMux", uid)
    terms = node.findall("termList/*")
    require(
        node.findtext("objFlags") == flags
        and tuple(t.get("uid") for t in terms) == ports
        and tuple(int(t.findtext("dco/i", "0")) for t in terms) == indices,
        "beam-line Bundle/Unbundle field order changed",
    )
    require(
        node.find("dcoAgg").get("uid") == terms[0].find("dco").get("uid")
        and tuple(t.get("uid") for t in node.findall("dcoList/*"))
        == tuple(
            t.find("dco").get("uid") for t in terms[1 if flags == "327680" else 2 :]
        ),
        "beam-line Bundle/Unbundle DCO order changed",
    )
    first_field = 1 if flags == "327680" else 2
    require(
        terms[0].findtext("dco/objFlags", "0") == ("0" if first_field == 1 else "1")
        and all(
            t.findtext("dco/objFlags", "0") == ("1" if first_field == 1 else "0")
            and td(meta, t).get("Type") == "NumFloat64"
            for t in terms[first_field:]
        ),
        "beam-line Bundle/Unbundle direction/type changed",
    )
    if first_field == 2:
        require(
            tuple(t.get("uid") for t in terms[0].findall("dco/termList/*")) == ports[:2]
            and terms[1].find("dco").get("uid") == terms[0].find("dco").get("uid"),
            "Bundle input/output aggregate alias changed",
        )
    return terms


def validate_tail(root, meta):
    names = call_names(meta)
    mappings = {}
    for event, row in EVENTS.items():
        (
            seq,
            frames,
            sel,
            sel_port,
            false_uid,
            true_uid,
            sloc,
            sloc_ports,
            comp,
            comp_ports,
            lit,
        ) = row
        sequence = unique(root, "sequence", seq)
        require(
            tuple(f.get("uid") for f in sequence.findall("diagramList/*")) == frames,
            "beam-line four-frame execution order changed",
        )
        s = sequence.find("seqLocDCOList")
        require(
            len(s) == 1
            and s[0].get("class") == "sLoc"
            and s[0].get("uid") == sloc
            and s[0].findtext("objFlags") == "1"
            and tuple(t.get("uid") for t in s[0].findall("termList/*")) == sloc_ports,
            "beam-line Boolean sequence-local connection changed",
        )
        selector = unique(root, "select", sel)
        terms = selector.findall("termList/*")
        require(
            len(terms) == 1
            and terms[0].get("uid") == sel_port
            and td(meta, terms[0]).get("Type") == "Boolean"
            and tuple(f.get("uid") for f in selector.findall("diagramList/*"))
            == (false_uid, true_uid)
            and len(selector.find("tunnelList")) == 0
            and [
                (
                    x.findtext("start"),
                    x.findtext("end"),
                    x.findtext("diagramIdx"),
                    x.findtext("startRangeType"),
                    x.findtext("endRangeType"),
                )
                for x in selector.findall("SelectRangeArray32/*")
            ]
            == [("0", "0", "0", "0", "0"), ("1", "1", "1", "0", "0")],
            "beam-line Boolean False/True selection changed",
        )
        operations(
            unique(root, "diag", frames[1]), [("select", sel)], "beam-line frame1"
        )
        exact_wires(
            unique(root, "diag", frames[1]),
            ((sloc_ports[1], sel_port),),
            "beam-line frame1",
        )
        false = unique(root, "diag", false_uid)
        operations(false, [], "beam-line False")
        exact_wires(false, (), "beam-line False")
        # Supplemental parent facet only: no claim of complete frame0 coverage.
        parent = unique(root, "diag", frames[0])
        cmp = unique(root, "prim", comp)
        ct = cmp.findall("termList/*")
        require(
            cmp.findtext("primResID") == "1103"
            and tuple(t.get("uid") for t in ct) == comp_ports
            and [td(meta, t).get("Type") for t in ct]
            == ["Boolean", "NumUInt32", "NumUInt32"]
            and [t.findtext("dco/parmIndex", "0") for t in ct] == ["0", "1", "2"]
            and [t.findtext("dco/objFlags", "0") for t in ct] == ["1", "0", "0"]
            and constant(parent, lit) == "00000080",
            "beam-line supplemental >=128 comparator changed",
        )
        for expected in ((comp_ports[0], sloc_ports[0]), (lit, comp_ports[1])):
            nets = [
                frozenset(t.get("uid") for t in n.findall("termList/*"))
                for n in parent.findall("signalList/*")
                if any(t.get("uid") == expected[0] for t in n.findall("termList/*"))
            ]
            require(
                nets == [frozenset(expected)],
                "beam-line supplemental comparator wire changed",
            )
        # Complete True diagram, independently deriving the source-to-bank map.
        src_uid, src_port, index, unbundle, agg, fields = SOURCES[event]
        local(root, src_uid, src_port, index)
        un = mux(
            root,
            meta,
            unbundle,
            "327680",
            (agg, *(p for p, _ in fields)),
            (0, *(i for _, i in fields)),
        )
        desc, flat = heap_type(meta, int(un[0].findtext("dco/typeDesc")[7:-1]))
        cells = desc.findall("TypeDesc")
        require(
            desc.get("Type") == "Cluster"
            and len(cells) == (11 if event == 1 else 9)
            and td(meta, unique(root, "gRef", src_uid).find("termList/*")) == desc,
            "beam-line nested source identity changed",
        )
        for cell in cells:
            group = flat[int(cell.get("TypeID"))]
            children = [flat[int(f.get("TypeID"))] for f in group.findall("TypeDesc")]
            require(
                group.get("Type") == "Cluster"
                and len(children) == 11
                and [c.get("Type") for c in children]
                == ["Boolean"] * 5 + ["NumFloat64"] * 2 + ["Boolean"] * 4
                and children[5].get("Label") == "Consigne",
                "nested Consigne schema changed",
            )
        ops, nets, mapping = (
            [("gRef", src_uid), ("nMux", unbundle)],
            [(src_port, agg)],
            [],
        )
        source_indices = dict(fields)
        for bank, read, rp, write, wp, bund, out, inp, copies in BUNDLES[event]:
            local(root, read, rp, bank)
            local(root, write, wp, bank, True)
            bt = mux(
                root,
                meta,
                bund,
                "262144",
                (out, inp, *(p for p, _, _ in copies)),
                (0, 0, *(i for _, i, _ in copies)),
            )
            bank_type(meta, bt[0], bank)
            bank_type(meta, unique(root, "gRef", read).find("termList/*"), bank)
            bank_type(meta, unique(root, "gRef", write).find("termList/*"), bank)
            ops.extend((("gRef", read), ("gRef", write), ("nMux", bund)))
            nets.extend(((rp, inp), (out, wp)))
            for port, destination, source in copies:
                field = source_indices[source]
                require(
                    field % 12 == 6
                    and td(meta, next(t for t in un if t.get("uid") == source)).get(
                        "Label"
                    )
                    == "Consigne",
                    "copy is no longer a nested Consigne leaf",
                )
                mapping.append((field // 12, bank, destination))
                nets.append((source, port))
        true = unique(root, "diag", true_uid)
        operations(true, ops, "beam-line True")
        exact_wires(true, nets, "beam-line True")
        mappings[event] = tuple(mapping)
        # Four independent errors, not the one-chain topology of events3..25.
        pub = unique(root, "diag", frames[2])
        ops, nets = [], []
        for bank, read, rp, uri, writer, ports, handler, hp in PUBLICATIONS[event]:
            local(root, read, rp, bank)
            bank_type(meta, unique(root, "gRef", read).find("termList/*"), bank)
            wt = unique(root, "sharedVariableDynamicWrite", writer).findall(
                "termList/*"
            )
            require(
                tuple(t.get("uid") for t in wt) == ports
                and [t.findtext("dco/terminal_ID", "") for t in wt]
                == ["0B", "03", "08", "", "0A"]
                and [t.findtext("dco/objFlags") for t in wt]
                == ["128", "513", "512", "513", "128"],
                "beam-line PSP connector changed",
            )
            bank_type(meta, wt[4], bank)
            uri_term = pub.find(f"nodeList/*/termList/*[@uid='{uri}']")
            uri_type = td(meta, uri_term)
            expected = f"ni.var.psp://10.20.30.2/SUPERVISION/C{bank - 3}NI6703".encode(
                "ascii"
            )
            require(
                uri_type.get("Type") == "Refnum"
                and uri_type.get("Ident") == "Variable"
                and bytes.fromhex(constant(pub, uri))
                == len(expected).to_bytes(4, "big") + expected,
                "beam-line PSP URI identity changed",
            )
            ht = unique(root, "iUse", handler).findall("termList/*")
            require(
                names.get(handler) == "Simple Error Handler.vi"
                and tuple(t.get("uid") for t in ht) == hp
                and [int(t.findtext("dco/paramIdx", "0")) for t in ht]
                == list(range(10))
                and ht[9].findtext("dco/objFlags") == "512",
                "independent beam-line error handler changed",
            )
            ops.extend(
                (
                    ("gRef", read),
                    (None, uri),
                    ("sharedVariableDynamicWrite", writer),
                    ("iUse", handler),
                )
            )
            nets.extend(((uri, ports[0]), (rp, ports[4]), (ports[3], hp[9])))
        operations(pub, ops, "beam-line independent publication")
        exact_wires(pub, nets, "beam-line independent publication")
        label, literal, primitive, ports = WAITS[event]
        wait = unique(root, "diag", frames[3])
        operations(
            wait,
            [("label", label), (None, literal), ("prim", primitive)],
            "beam-line wait",
        )
        pt = unique(root, "prim", primitive).findall("termList/*")
        require(
            unique(root, "prim", primitive).findtext("primResID") == "1302"
            and tuple(t.get("uid") for t in pt) == ports
            and td(meta, pt[1]).get("Type") == "NumUInt32"
            and constant(wait, literal) == "00000064",
            "beam-line100ms wait changed",
        )
        exact_wires(wait, ((literal, ports[1]),), "beam-line wait")
    return mappings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    result = validate_tail(*checked_vam(args.root_archive))
    print(
        "PASS: 10 complete tail diagrams / 60 direct nets / 20 Consigne copies / "
        "8 independent publications / two100ms waits; frame0 remains open"
    )
    print(result)


if __name__ == "__main__":
    main()
