"""Complete both saved Diagram Disable arms and every cooling-trip frame.

The XML does not expose explicit activeDiag/defaultDiag for this structure.
This validator does not infer the active arm from a selected UI case index.
"""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_publication import local, operations
from validate_acq_timeout_dispatch import _fields, _structure
from validate_acq_vam_status import checked_vam

NETS = {
    "42045": (),
    "21070": (
        ("52234", "44205"),
        ("47316", "52237"),
        ("40060", "52240"),
        ("42289", "47330"),
        ("42286", "47325"),
        ("8395", "42283"),
        ("10214", "51370"),
        ("51373", "40066"),
        ("53472", "40063"),
    ),
    "21403": (),
    "44189": (),
    "44195": (),
    "10221": (
        ("41643", "12623"),
        ("10256", "10444"),
        ("10241", "10425"),
        ("10417", "10299"),
        ("10435", "10423"),
    ),
    "13119": (("13135", "13379"), ("13265", "13255"), ("13518", "13375")),
    "14187": (("15485", "20044"),),
    "20056": (
        ("44092", "25634"),
        ("20067", "21048"),
        ("20649", "20632"),
        ("22863", "21045"),
    ),
    "30644": (("30742", "30959"), ("30863", "30834"), ("31006", "30901")),
    "31857": (
        ("38646", "39309"),
        ("39316", "39308"),
        ("39305", "39298"),
        ("32862", "39285"),
        ("32391", "39282"),
        ("38895", "38741"),
        ("32179", "38971"),
        ("32022", "38924"),
        ("39292", "38904"),
    ),
    "39347": (
        ("39447", "39576"),
        ("39366", "39452"),
        ("39469", "39760"),
        ("39353", "39440"),
    ),
}
OPS = {
    "42045": [("commentNode", "14478"), ("label", "25062")],
    "21070": [
        ("prim", "52228"),
        ("cpdArith", "47240"),
        ("nMux", "42277"),
        ("gRef", "7436"),
        ("select", "11044"),
        ("prim", "12948"),
        ("nMux", "39336"),
        ("gRef", "10202"),
    ],
    "21403": [],
    "44189": [],
    "44195": [("sequence", "8256")],
    "10221": [
        (None, "41643"),
        ("prim", "10523"),
        ("label", "12760"),
        (None, "10256"),
        ("gRef", "10440"),
        ("label", "12766"),
        (None, "10241"),
        ("gRef", "10431"),
        ("nMux", "10308"),
        ("gRef", "10289"),
    ],
    "13119": [
        ("label", "13535"),
        ("label", "13536"),
        (None, "13135"),
        ("gRef", "13466"),
        ("nMux", "13262"),
        ("gRef", "13246"),
    ],
    "14187": [("label", "20050"), (None, "15485"), ("prim", "19557")],
    "20056": [
        (None, "44092"),
        ("prim", "24555"),
        ("label", "25664"),
        ("label", "25667"),
        (None, "20067"),
        ("gRef", "22661"),
        ("nMux", "20645"),
        ("gRef", "20160"),
    ],
    "30644": [
        ("label", "31796"),
        ("label", "31807"),
        (None, "30742"),
        ("gRef", "30986"),
        ("nMux", "30840"),
        ("gRef", "30817"),
    ],
    "31857": [
        (None, "38646"),
        ("gRef", "39313"),
        ("nMux", "39303"),
        ("gRef", "39295"),
        (None, "32862"),
        ("label", "39319"),
        (None, "32391"),
        (None, "32179"),
        (None, "32022"),
        ("gRef", "39289"),
        ("nMux", "38770"),
        ("gRef", "38731"),
    ],
    "39347": [
        ("iUse", "39603"),
        ("sharedVariableDynamicWrite", "39450"),
        (None, "39366"),
        ("gRef", "39444"),
        ("label", "39767"),
        ("label", "39768"),
        (None, "39353"),
        ("prim", "39428"),
    ],
}
LOCALS = (
    ("7436", "8395", 18, False),
    ("10202", "10214", 16, False),
    ("10440", "10444", 35, True),
    ("10431", "10435", 17, False),
    ("10289", "10299", 17, True),
    ("13466", "13518", 17, False),
    ("13246", "13255", 17, True),
    ("22661", "22863", 17, False),
    ("20160", "20632", 17, True),
    ("30986", "31006", 17, False),
    ("30817", "30834", 17, True),
    ("39295", "39298", 36, True),
    ("39289", "39292", 44, False),
    ("38731", "38741", 44, True),
    ("39444", "39447", 36, False),
)
MUXES = (
    ("42277", "327680", ("42283", "42286", "42289"), (0, 0, 6)),
    ("39336", "327680", ("51370", "51373", "53472"), (0, 19, 38)),
    ("10308", "262144", ("10417", "10423", "10425"), (0, 0, 1)),
    ("13262", "262144", ("13265", "13375", "13379"), (0, 0, 1)),
    ("20645", "262144", ("20649", "21045", "21048"), (0, 0, 4)),
    ("30840", "262144", ("30863", "30901", "30959"), (0, 0, 4)),
    ("39303", "262144", ("39305", "39308", "39309"), (0, 0, 1)),
    (
        "38770",
        "262144",
        ("38895", "38904", "38924", "38971", "39282", "39285"),
        (0, 0, 3, 2, 5, 1),
    ),
)
LITERALS = (
    ("10221", "10241", "0000"),
    ("10221", "10256", "01"),
    ("10221", "41643", "00000096"),
    ("13119", "13135", "01"),
    ("14187", "15485", "00000190"),
    ("20056", "20067", "0000"),
    ("20056", "44092", "00000096"),
    ("30644", "30742", "01"),
    ("31857", "32022", "0000"),
    ("31857", "32179", "0000"),
    ("31857", "32391", "01"),
    ("31857", "32862", "01"),
    ("31857", "38646", "0000"),
    ("39347", "39353", "00000064"),
)


def validate_cooling(root, meta):
    for uid, nets in NETS.items():
        frame = unique(root, "diag", uid)
        exact_wires(frame, nets, "cooling trip " + uid)
        operations(frame, OPS[uid], "cooling trip " + uid)
    disabled = unique(root, "commentNode", "14478")
    require(
        disabled.findtext("commentMode") == "True"
        and disabled.find("activeDiag") is None
        and disabled.find("defaultDiag") is None
        and [x.get("uid") for x in disabled.findall("diagramList/*")]
        == ["21070", "21403"]
        and len(disabled.find("termList")) == 0,
        "cooling Diagram Disable arm/activation metadata changed",
    )
    _structure(root, "select", "11044", ("44189", "44195"), ("44205",))
    _structure(
        root,
        "sequence",
        "8256",
        ("10221", "13119", "14187", "20056", "30644", "31857", "39347"),
        (),
    )
    for args in LOCALS:
        local(root, *args)
    special = unique(root, "gRef", "39313").find("termList/*")
    require(
        special.get("uid") == "39316"
        and special.findtext("dco/paramIdx") == "36"
        and special.findtext("dco/objFlags") == "5",
        "cooling special DPS local snapshot flags changed",
    )
    for uid, size in (
        ("7436", 56),
        ("10202", 64),
        ("10431", 40),
        ("39289", 77),
        ("39313", 29),
    ):
        _fields(root, meta, uid, size, "Boolean")
    for uid, flags, ports, fields in MUXES:
        node = unique(root, "nMux", uid)
        require(
            node.findtext("objFlags") == flags
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and tuple(int(t.findtext("dco/i", "0")) for t in node.findall("termList/*"))
            == fields,
            "cooling bundle/unbundle fields changed",
        )
    primitive(root, "52228", 1061, ("52234", "52237", "52240"))
    primitive(root, "12948", 1062, ("40060", "40063", "40066"))
    for uid, ports in (
        ("10523", ("11765", "12623")),
        ("19557", ("19919", "20044")),
        ("24555", ("25595", "25634")),
        ("39428", ("39437", "39440")),
    ):
        primitive(root, uid, 1302, ports)
    compound = unique(root, "cpdArith", "47240")
    require(
        compound.findtext("objFlags") == "720896"
        and tuple(t.get("uid") for t in compound.findall("termList/*"))
        == ("47316", "47325", "47330")
        and [t.findtext("dco/objFlags") for t in compound.findall("termList/*")]
        == ["131073", "327680", "327680"],
        "cooling compound OR/inverted inputs changed",
    )
    for uid, port, value in LITERALS:
        require(
            constant(unique(root, "diag", uid), port) == value,
            "cooling pulse/wait/status literal changed",
        )
    uri = b"ni.var.psp://10.20.30.2/SUPERVISION/DPS"
    require(
        bytes.fromhex(constant(unique(root, "diag", "39347"), "39366"))
        == len(uri).to_bytes(4, "big") + uri,
        "cooling DPS publication URI changed",
    )
    writer = unique(root, "sharedVariableDynamicWrite", "39450")
    require(
        tuple(t.get("uid") for t in writer.findall("termList/*"))
        == ("39452", "39456", "39459", "39469", "39576")
        and [t.findtext("dco/terminal_ID", "") for t in writer.findall("termList/*")]
        == ["0B", "03", "08", "", "0A"],
        "cooling PSP writer connector changed",
    )
    handler = unique(root, "iUse", "39603")
    ports = (
        "39612",
        "39621",
        "39714",
        "39729",
        "39734",
        "39737",
        "39750",
        "39753",
        "39757",
        "39760",
    )
    require(
        call_names(meta)["39603"] == "Simple Error Handler.vi"
        and tuple(t.get("uid") for t in handler.findall("termList/*")) == ports,
        "cooling publication error handler changed",
    )
    for i, port in enumerate(ports):
        public_term(handler, port, i)
    return "PASS: cooling Timeout 12 diagrams / 38 nets / all seven trip frames"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_cooling(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
