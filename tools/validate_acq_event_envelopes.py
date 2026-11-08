"""Complete all event envelopes and23 procedure NewVal Boolean gates.

Nested sequence bodies retain their separate proof obligations. Event25's
special registration flag is pinned, not interpreted as enable/disable.
"""

import argparse
from pathlib import Path

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import operations
from validate_acq_timeout_dispatch import _structure
from validate_acq_vam_status import checked_vam

# Event diagram, two labels, duration constant, eventDataNode, NewVal port,
# Case node/selector/input tunnel, False/True diagrams, True tunnel port,
# procedure sequence/sequence input. Event indices start at3.
ROWS = (
    (
        "19818",
        "19144",
        "19182",
        "18713",
        "22353",
        "22639",
        "19197",
        "22664",
        "19245",
        "22648",
        "22654",
        "19238",
        "18783",
        "19196",
    ),
    (
        "17899",
        "18550",
        "18563",
        "18551",
        "17919",
        "17939",
        "17947",
        "17950",
        "17956",
        "17964",
        "17970",
        "17961",
        "7929",
        "7941",
    ),
    (
        "34531",
        "35688",
        "35701",
        "35689",
        "34547",
        "34564",
        "34571",
        "34573",
        "34578",
        "34585",
        "34591",
        "34582",
        "34597",
        "34599",
    ),
    (
        "25330",
        "37762",
        "37775",
        "37763",
        "26359",
        "26424",
        "26469",
        "26478",
        "26494",
        "26520",
        "26538",
        "26505",
        "26556",
        "26559",
    ),
    (
        "22879",
        "25943",
        "25977",
        "25950",
        "23160",
        "23211",
        "23245",
        "23251",
        "23261",
        "23269",
        "23275",
        "23265",
        "23281",
        "23283",
    ),
    (
        "26012",
        "28515",
        "28567",
        "28521",
        "26082",
        "26127",
        "26159",
        "26169",
        "26196",
        "26217",
        "26229",
        "26206",
        "26235",
        "26237",
    ),
    (
        "23449",
        "41620",
        "41633",
        "41621",
        "23465",
        "30776",
        "30860",
        "30868",
        "30909",
        "30947",
        "30965",
        "30936",
        "30983",
        "30990",
    ),
    (
        "23113",
        "24231",
        "24246",
        "24232",
        "23294",
        "23447",
        "23463",
        "23481",
        "23486",
        "23493",
        "23501",
        "23490",
        "23507",
        "23509",
    ),
    (
        "33620",
        "34127",
        "34141",
        "34128",
        "33636",
        "33653",
        "33660",
        "33662",
        "33667",
        "33674",
        "33680",
        "33671",
        "33686",
        "33688",
    ),
    (
        "37991",
        "38710",
        "38723",
        "38711",
        "38007",
        "38024",
        "38031",
        "38033",
        "38038",
        "38045",
        "38051",
        "38042",
        "38057",
        "38059",
    ),
    (
        "23143",
        "29783",
        "29814",
        "29785",
        "23924",
        "24263",
        "24272",
        "24274",
        "24279",
        "24286",
        "24292",
        "24283",
        "24303",
        "24306",
    ),
    (
        "35942",
        "36565",
        "36579",
        "36566",
        "35958",
        "35975",
        "35982",
        "35984",
        "35989",
        "35996",
        "36002",
        "35993",
        "36008",
        "36010",
    ),
    (
        "40079",
        "40691",
        "40704",
        "40692",
        "40097",
        "40114",
        "40121",
        "40123",
        "40128",
        "40135",
        "40141",
        "40132",
        "40147",
        "40149",
    ),
    (
        "23120",
        "32568",
        "32581",
        "32569",
        "29068",
        "29860",
        "29880",
        "29887",
        "29902",
        "29923",
        "29955",
        "29913",
        "30036",
        "30216",
    ),
    (
        "42457",
        "43182",
        "43195",
        "43183",
        "42473",
        "42490",
        "42497",
        "42499",
        "42504",
        "42511",
        "42517",
        "42508",
        "42523",
        "42525",
    ),
    (
        "34191",
        "36429",
        "36596",
        "36432",
        "34210",
        "34227",
        "34237",
        "34242",
        "34248",
        "34255",
        "34261",
        "34252",
        "34267",
        "34269",
    ),
    (
        "43634",
        "44123",
        "44136",
        "44124",
        "43651",
        "43668",
        "43675",
        "43677",
        "43682",
        "43689",
        "43695",
        "43686",
        "43701",
        "43703",
    ),
    (
        "48846",
        "54356",
        "54369",
        "54357",
        "48862",
        "53951",
        "53958",
        "53960",
        "53965",
        "53972",
        "53978",
        "53969",
        "53984",
        "53986",
    ),
    (
        "8896",
        "32763",
        "32776",
        "32764",
        "31588",
        "31605",
        "31612",
        "31614",
        "31619",
        "31627",
        "31637",
        "31623",
        "31655",
        "31666",
    ),
    (
        "31552",
        "34168",
        "34190",
        "34171",
        "32192",
        "32807",
        "32837",
        "32839",
        "32844",
        "32851",
        "32857",
        "32848",
        "32863",
        "32872",
    ),
    (
        "45123",
        "45610",
        "45623",
        "45611",
        "45139",
        "45156",
        "45163",
        "45165",
        "45170",
        "45177",
        "45183",
        "45174",
        "45189",
        "45191",
    ),
    (
        "40713",
        "41481",
        "41494",
        "41482",
        "40729",
        "40746",
        "40754",
        "40756",
        "40770",
        "40779",
        "40785",
        "40776",
        "40791",
        "40793",
    ),
    (
        "38732",
        "40000",
        "40018",
        "40001",
        "38748",
        "38765",
        "38772",
        "38774",
        "38779",
        "38786",
        "38792",
        "38783",
        "38798",
        "38800",
    ),
)
DDOS = (
    "0",
    "1660",
    "16917",
    "59266",
    "59274",
    "59370",
    "59378",
    "66587",
    "66635",
    "66683",
    "66731",
    "59386",
    "66579",
    "66627",
    "66675",
    "66723",
    "66411",
    "66419",
    "59482",
    "59474",
    "59314",
    "59322",
    "59330",
    "59426",
    "59434",
    "66443",
)


def validate_envelopes(root, meta):
    event = unique(root, "eventStruct", "43")
    frames = event.findall("diagramList/*")
    require(
        tuple(f.get("uid") for f in frames)
        == ("53", "8704", "8710") + tuple(row[0] for row in ROWS),
        "event diagram ordering changed",
    )
    specs = event.findall("EventNodeEvents/*")
    require(len(specs) == 26, "event registration count changed")
    for index, spec in enumerate(specs):
        require(
            spec.findtext("diagramIdx") == str(index)
            and spec.findtext("ddoUID") == DDOS[index]
            and spec.findtext("type") == ("1073741825" if index == 0 else "1073741826")
            and spec.findtext("source") == ("4" if index == 0 else "3")
            and spec.findtext("regFlags")
            == ("0" if index == 0 else "-2147483647" if index == 25 else "1")
            and spec.findtext("eFlags") == ("1" if index == 0 else "4"),
            "event registration target/type/flags changed",
        )
    for uid, seq, data, nets in (
        ("53", "10111", "74", ()),
        ("8704", "11069", "8720", (("8886", "11071"), ("8883", "11078"))),
        ("8710", "19041", "8749", (("8773", "19043"), ("8770", "19049"))),
    ):
        frame = unique(root, "diag", uid)
        operations(
            frame, [("sequence", seq), ("eventDataNode", data)], "event0..2 envelope"
        )
        exact_wires(frame, nets, "event0..2 envelope")
    for index, row in enumerate(ROWS, 3):
        (
            uid,
            label1,
            label2,
            literal,
            data,
            new,
            case_uid,
            selector,
            duration,
            false_uid,
            true_uid,
            inner,
            seq,
            seq_input,
        ) = row
        frame = unique(root, "diag", uid)
        operations(
            frame,
            [
                ("label", label1),
                ("label", label2),
                (None, literal),
                ("eventDataNode", data),
                ("select", case_uid),
            ],
            "procedure event envelope",
        )
        exact_wires(
            frame, ((literal, duration), (new, selector)), "procedure event envelope"
        )
        require(
            constant(frame, literal) == ("000003E8" if index == 3 else "00000096"),
            "procedure envelope duration literal changed",
        )
        case = _structure(
            root, "select", case_uid, (false_uid, true_uid), (selector, duration)
        )
        tunnel = case.findall("termList/*")[1].find("dco")
        require(
            tunnel.findtext("objFlags") == "2048"
            and tuple(t.get("uid") for t in tunnel.findall("termList/*"))[1:]
            == (inner, duration),
            "event duration Case tunnel changed",
        )
        false, true = case.findall("diagramList/*")
        operations(false, [], "procedure NewValFalse arm")
        exact_wires(false, (), "procedure NewValFalse arm")
        operations(true, [("sequence", seq)], "procedure NewValTrue arm")
        exact_wires(true, ((inner, seq_input),), "procedure NewValTrue arm")
        sequence = unique(root, "sequence", seq)
        require(
            tuple(t.get("uid") for t in sequence.findall("termList/*")) == (seq_input,),
            "procedure sequence entry tunnel changed",
        )
        node = unique(root, "eventDataNode", data)
        terms = node.findall("termList/*")
        require(
            node.findtext("objFlags") == "1376256"
            and len(terms) == 6
            and tuple(int(t.findtext("dco/i", "0")) for t in terms)
            == (0, 1, 2, 3, 5, 6)
            and terms[-1].get("uid") == new,
            "procedure event data field selection changed",
        )
        for term, name in ((terms[-2], "OldVal"), (terms[-1], "NewVal")):
            typ, _ = heap_type(meta, int(term.findtext("dco/typeDesc")[7:-1]))
            require(
                typ.get("Type") == "Boolean" and typ.get("Label") == name,
                "procedure OldVal/NewVal Boolean identity changed",
            )
    return "PASS: 72 event/gate diagrams / 73 nets / all23 NewValFalse/True envelopes"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_envelopes(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
