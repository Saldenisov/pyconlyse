"""Pin Timeout command-read frame and its final error/stop assignments."""

import argparse
from pathlib import Path

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

# Call, URI constant, tag, old-local node/port, write-local node/port,
# local bank, cluster length, element type, seven saved reader terminals.
SITES = (
    (
        "10310",
        "10121",
        "C6NI6703",
        "10193",
        "10196",
        "10392",
        "10395",
        9,
        10,
        "NumFloat64",
        ("10312", "10315", "10318", "10321", "10324", "10327", "10330"),
    ),
    (
        "10333",
        "10139",
        "C7NI6703",
        "10232",
        "10235",
        "10398",
        "10401",
        10,
        10,
        "NumFloat64",
        ("10335", "10338", "10341", "10357", "10360", "10363", "10366"),
    ),
    (
        "10369",
        "10157",
        "C8NI6703",
        "10271",
        "10274",
        "10404",
        "10407",
        11,
        10,
        "NumFloat64",
        ("10371", "10374", "10377", "10380", "10383", "10386", "10389"),
    ),
    (
        "10449",
        "10175",
        "C9NI6703",
        "10410",
        "10413",
        "10472",
        "10475",
        12,
        10,
        "NumFloat64",
        ("10451", "10454", "10457", "10460", "10463", "10466", "10469"),
    ),
    (
        "22278",
        "22634",
        "C1011NI6602",
        "22254",
        "22257",
        "22552",
        "22555",
        39,
        33,
        "NumFloat64",
        ("22280", "22283", "22286", "22289", "22292", "22295", "22300"),
    ),
    (
        "25403",
        "25232",
        "C3_OUT_DIO96",
        "25286",
        "25289",
        "25472",
        "25475",
        17,
        40,
        "Boolean",
        ("25405", "25408", "25411", "25414", "25417", "25420", "25423"),
    ),
    (
        "25426",
        "25250",
        "C4_OUT_DIO96",
        "25325",
        "25328",
        "25478",
        "25481",
        15,
        32,
        "Boolean",
        ("25428", "25431", "25434", "25437", "25440", "25443", "25446"),
    ),
    (
        "25449",
        "25268",
        "C5_OUT_DIO96",
        "25364",
        "25367",
        "25484",
        "25487",
        13,
        40,
        "Boolean",
        ("25451", "25454", "25457", "25460", "25463", "25466", "25469"),
    ),
    (
        "19950",
        "20123",
        "DPS",
        "19926",
        "19929",
        "87",
        "1819",
        36,
        29,
        "Boolean",
        ("19953", "19956", "19959", "19962", "19965", "19968", "19971"),
    ),
    (
        "19974",
        "20105",
        "DPC",
        "19934",
        "19937",
        "17599",
        "17608",
        37,
        5,
        "Boolean",
        ("19976", "19979", "19982", "19985", "19988", "19991", "19994"),
    ),
    (
        "19997",
        "20078",
        "EPS",
        "19942",
        "19945",
        "18021",
        "18028",
        44,
        77,
        "Boolean",
        ("19999", "20002", "20005", "20009", "20012", "20015", "20018"),
    ),
    (
        "22840",
        "22822",
        "EPC",
        "22805",
        "22812",
        "18267",
        "18274",
        38,
        12,
        "Boolean",
        ("22842", "22845", "22848", "22851", "22854", "22857", "22860"),
    ),
)
NETS = {
    "367": (),
    "110": (("18825", "18652"), ("119", "8393"), ("7921", "122"), ("290", "70")),
    "53": (),
    "10115": (
        ("22851", "40253"),
        ("22289", "25411"),
        ("19962", "19982"),
        ("19985", "20005"),
        ("20009", "22848"),
        ("22857", "18274"),
        ("22822", "22842"),
        ("22812", "22854"),
        ("25414", "25434"),
        ("25460", "19959"),
        ("25437", "25457"),
        ("19968", "1819"),
        ("19929", "19965"),
        ("20123", "19953"),
        ("20078", "19999"),
        ("20015", "18028"),
        ("19945", "20012"),
        ("19991", "17608"),
        ("19937", "19988"),
        ("20105", "19976"),
        ("25367", "25463"),
        ("25268", "25451"),
        ("25232", "25405"),
        ("25289", "25417"),
        ("25328", "25440"),
        ("25250", "25428"),
        ("25420", "25475"),
        ("25443", "25481"),
        ("25466", "25487"),
        ("10460", "22286"),
        ("22634", "22280"),
        ("22257", "22292"),
        ("22295", "22555"),
        ("10380", "10457"),
        ("10357", "10377"),
        ("10321", "10341"),
        ("10413", "10463"),
        ("10175", "10451"),
        ("10466", "10475"),
        ("10386", "10407"),
        ("10363", "10401"),
        ("10327", "10395"),
        ("10139", "10335"),
        ("10235", "10360"),
        ("10196", "10324"),
        ("10121", "10312"),
        ("10157", "10371"),
        ("10274", "10383"),
    ),
    "40237": (),
    "40224": (("44039", "68238", "85111"),),
}


def validate_reads(root, meta):
    for uid, nets in NETS.items():
        exact_wires(unique(root, "diag", uid), nets, "Timeout reads " + uid)
    operations(
        unique(root, "diag", "367"),
        [("whileLoop", uid) for uid in ("47483", "59483", "20601", "203", "102")],
        "all five independent runtime loops",
    )
    operations(
        unique(root, "diag", "110"),
        [
            (None, "18825"),
            ("prim", "18643"),
            ("gRef", "2036"),
            ("gRef", "1888"),
            (None, "290"),
            ("eventStruct", "43"),
            (None, "122"),
            (None, "119"),
        ],
        "dispatcher loop body",
    )
    operations(
        unique(root, "diag", "53"),
        [("sequence", "10111"), ("eventDataNode", "74")],
        "Timeout event",
    )
    frame = unique(root, "diag", "10115")
    ops = [("label", "28692"), ("select", "40205")]
    for (
        call,
        literal,
        tag,
        read,
        read_port,
        write,
        write_port,
        bank,
        size,
        element,
        ports,
    ) in SITES:
        ops += [
            ("sharedVariableDynamicRead", call),
            (None, literal),
            ("gRef", read),
            ("gRef", write),
        ]
        node = unique(root, "sharedVariableDynamicRead", call)
        require(
            node.findtext("SharedVariableDynamicResID") == "5CE5"
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
            "Timeout reader kind/terminal ordering changed",
        )
        data = bytes.fromhex(constant(frame, literal))
        expected = ("ni.var.psp://10.20.30.2/SUPERVISION/" + tag).encode("ascii")
        require(
            data == len(expected).to_bytes(4, "big") + expected,
            "Timeout command-read URI changed",
        )
        local(root, read, read_port, bank)
        local(root, write, write_port, bank, True)
        for port in ports[4:6]:
            desc = node.findtext(f"termList/*[@uid='{port}']/dco/typeDesc")
            value, flat = heap_type(meta, int(desc[7:-1]))
            require(
                value.get("Type") == "Cluster"
                and len(value.findall("TypeDesc")) == size
                and all(
                    flat[int(t.get("TypeID"))].get("Type") == element
                    for t in value.findall("TypeDesc")
                ),
                "Timeout default/returned cluster shape changed",
            )
    operations(frame, ops, "all Timeout reads")
    operations(unique(root, "diag", "40237"), [], "read-error False arm")
    operations(
        unique(root, "diag", "40224"),
        [("gRef", "85095"), ("gRef", "68231"), (None, "44039")],
        "read-error True arm",
    )
    local(root, "85095", "85111", 30, True)
    local(root, "68231", "68238", 45, True)
    require(
        constant(unique(root, "diag", "40224"), "44039") == "0000",
        "read fault no longer assigns False",
    )
    branch = unique(root, "select", "40205")
    require(
        [
            (d.findtext("start"), d.findtext("diagramIdx"))
            for d in branch.findall("SelectRangeArray32/*")
        ]
        == [("0", "0"), ("1", "1")]
        and [d.get("uid") for d in branch.findall("diagramList/*")]
        == ["40237", "40224"]
        and len(branch.find("tunnelList")) == 0,
        "Timeout final error case polarity/arm/tunnel changed",
    )
    sequence = unique(root, "sequence", "10111")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")]
        == ["10115", "10526", "22247", "42045"],
        "Timeout frame order changed",
    )
    local(root, "2036", "8393", 31, True)
    local(root, "1888", "7921", 30)
    loop = unique(root, "whileLoop", "102")
    require(
        loop.find("diagramList/*").get("uid") == "110"
        and loop.findtext("loopTestDCO/objFlags") == "65537"
        and loop.find("loopTestDCO/termList/*").get("uid") == "122"
        and loop.find("loopIndexDCO/termList/*").get("uid") == "119",
        "dispatcher loop Stop-if-True/iteration binding changed",
    )
    primitive(root, "18643", 1302, ("18649", "18652"))
    require(
        constant(unique(root, "diag", "110"), "18825") == "0000004B"
        and constant(unique(root, "diag", "110"), "290") == "00000014",
        "dispatcher Wait75/event timeout20 changed",
    )
    event = unique(root, "eventStruct", "43")
    require(
        event.find("termList/*[@uid='70']/dco").get("class") == "eventTimeOut"
        and event.find("timeOutDCO").get("uid") == "67",
        "dispatcher event timeout input changed",
    )
    spec = event.find("EventNodeEvents/*")
    require(
        event.find("diagramList/*").get("uid") == "53"
        and tuple(
            spec.findtext(key) for key in ("diagramIdx", "source", "type", "ddoUID")
        )
        == ("0", "4", "1073741825", "0"),
        "dispatcher Timeout event binding changed",
    )
    return (
        "PASS: Timeout reads 6 diagrams / 53 direct nets; "
        "12 error-chained readers; final error clears stop/TCP ED"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_reads(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
