"""Complete the 73-net named-open sibling, without selecting or running it.

Every local connection is a READ feeding dynamic-open type terminal 0A,
not a publication or hardware write. Activation metadata is checked by the
separate parent validator; native execution/activation is not inferred here.
"""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from DeviceServers.control.elyse_acq.vi_simulation.psp_discovery import NAMED_OPEN_TYPES
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_initializer_caller_frame import (
    desc,
    error_type,
    validate_disabled_parent,
)
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_publication import operations
from validate_acq_vam_status import checked_vam

# Node, six ordered ports, URI literal, URI suffix, local alias, local port, bank.
ROWS = (
    (
        "432",
        ("1685", "1688", "1738", "1741", "2508", "2520"),
        "1344",
        "C1NI6071E",
        "8216",
        "8226",
        19,
    ),
    (
        "1076",
        ("4007", "4010", "4013", "4016", "4019", "4022"),
        "1700",
        "C2NI6071E",
        "8243",
        "8253",
        20,
    ),
    (
        "346",
        ("4051", "4054", "4057", "4060", "4063", "4067"),
        "1749",
        "C3_IN_DIO96",
        "8271",
        "8281",
        18,
    ),
    (
        "568",
        ("1158", "1161", "1326", "1329", "1332", "1335"),
        "1897",
        "C3_OUT_DIO96",
        "8300",
        "8310",
        17,
    ),
    (
        "1168",
        ("1367", "4128", "4131", "4134", "4137", "4140"),
        "1990",
        "C4_IN_DIO96",
        "8346",
        "8356",
        16,
    ),
    (
        "1177",
        ("1374", "1379", "4171", "4174", "4177", "4180"),
        "4074",
        "C4_OUT_DIO96",
        "8377",
        "8387",
        15,
    ),
    (
        "186",
        ("316", "4209", "4212", "4215", "4218", "4221"),
        "2162",
        "C5_IN_DIO96",
        "8409",
        "8419",
        14,
    ),
    (
        "97",
        ("362", "384", "10344", "10347", "10350", "10353"),
        "4156",
        "C5_OUT_DIO96",
        "8442",
        "8452",
        13,
    ),
    (
        "46",
        ("318", "322", "327", "330", "577", "4248"),
        "1909",
        "C6NI6703",
        "92",
        "300",
        9,
    ),
    (
        "4282",
        ("4288", "4291", "4294", "4297", "4300", "4303"),
        "2481",
        "C7NI6703",
        "157",
        "376",
        10,
    ),
    (
        "128",
        ("340", "7396", "7399", "7402", "7405", "7408"),
        "4069",
        "C8NI6703",
        "537",
        "572",
        11,
    ),
    (
        "150",
        ("387", "417", "7447", "7450", "7453", "7456"),
        "4101",
        "C9NI6703",
        "1074",
        "1269",
        12,
    ),
    (
        "21763",
        ("21765", "21770", "21774", "21780", "21783", "21786"),
        "22595",
        "C1011NI6602",
        "21534",
        "21537",
        39,
    ),
    (
        "21790",
        ("21792", "21796", "21801", "21805", "21809", "21812"),
        "22577",
        "C12NI1409",
        "21542",
        "21546",
        8,
    ),
    (
        "21816",
        ("21819", "21823", "21829", "21835", "21838", "21841"),
        "22559",
        "DPC",
        "21551",
        "21555",
        37,
    ),
    (
        "21847",
        ("21849", "21854", "21863", "21871", "21877", "21881"),
        "22535",
        "DPS",
        "21570",
        "21574",
        36,
    ),
    (
        "21917",
        ("21920", "21929", "21938", "21947", "21956", "21960"),
        "22424",
        "EPC",
        "21579",
        "21591",
        38,
    ),
    (
        "21963",
        ("21965", "21968", "21971", "21974", "21977", "21980"),
        "22318",
        "EPS",
        "21596",
        "21600",
        44,
    ),
    (
        "21983",
        ("21985", "21988", "21991", "21994", "21997", "22001"),
        "22381",
        "VAD",
        "21606",
        "21616",
        3,
    ),
    (
        "22005",
        ("22007", "22013", "22022", "22032", "22035", "22038"),
        "22265",
        "VAM-A",
        "21653",
        "21657",
        41,
    ),
    (
        "22041",
        ("22043", "22046", "22049", "22052", "22055", "22058"),
        "22235",
        "VDM-A",
        "21691",
        "21696",
        7,
    ),
    (
        "22061",
        ("22063", "22066", "22073", "22076", "22079", "22082"),
        "22202",
        "VTA",
        "21716",
        "21724",
        2,
    ),
    (
        "22085",
        ("22087", "22090", "22093", "22096", "22099", "22102"),
        "22184",
        "VTL",
        "21731",
        "21735",
        0,
    ),
    (
        "22105",
        ("22107", "22110", "22113", "22116", "22119", "22122"),
        "22166",
        "VTS",
        "21754",
        "21757",
        1,
    ),
)


def validate_tree(root, metadata):
    require(
        tuple((row[3], row[6]) for row in ROWS) == NAMED_OPEN_TYPES,
        "inert named-open type-anchor plan differs from pinned source",
    )
    validate_disabled_parent(root, metadata)
    frame = unique(root, "diag", "76558")
    expected = [("iUse", "22125")]
    nets = []
    prior = "76736"
    literals = {
        t.get("uid"): t
        for t in frame.findall("nodeList/*/termList/*")
        if t.find("dco/ConstValue") is not None
    }
    require(
        set(literals) == {row[2] for row in ROWS},
        "named-open literal population changed",
    )
    for uid, ports, literal, name, alias, bank_port, bank in ROWS:
        expected += [
            ("sharedVariableDynamicOpen", uid),
            (None, literal),
            ("gRef", alias),
        ]
        node = unique(frame, "sharedVariableDynamicOpen", uid)
        require(
            node.findtext("SharedVariableDynamicResID") == "5CE3"
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and [
                t.findtext("dco/terminal_ID", "00") for t in node.findall("termList/*")
            ]
            == ["0B", "03", "08", "00", "0A", "06"]
            and [t.findtext("dco/objFlags") for t in node.findall("termList/*")]
            == ["128", "513", "512", "513", "128", "512"],
            "named-open port contract changed",
        )
        uri = ("ni.var.psp://10.20.30.2/SUPERVISION/" + name).encode("ascii")
        require(
            bytes.fromhex(constant(frame, literal))
            == len(uri).to_bytes(4, "big") + uri,
            "named-open URI changed",
        )
        for term in (literals[literal], *node.findall("termList/*")[:2]):
            uri_type = desc(metadata, term)
            require(
                uri_type.get("Type") == "Refnum"
                and uri_type.get("Ident") == "Variable"
                and uri_type.get("TypeName") == "Variable",
                "named-open URI/reference type changed",
            )
        alias_node = unique(frame, "gRef", alias)
        source = alias_node.find("termList/*")
        require(
            len(alias_node.findall("termList/*")) == 1
            and source.get("uid") == bank_port
            and source.findtext("dco/paramIdx", "0") == str(bank)
            and source.findtext("objFlags") == "4096"
            and source.findtext("dco/objFlags") == "1",
            "named-open local READ identity/direction changed",
        )
        require(
            desc(metadata, source).attrib
            == desc(metadata, node.findall("termList/*")[4]).attrib
            and [c.attrib for c in desc(metadata, source)]
            == [c.attrib for c in desc(metadata, node.findall("termList/*")[4])],
            "named-open type anchor changed",
        )
        for term in node.findall("termList/*")[2:4]:
            error_type(metadata, term)
        nets += [(literal, ports[0]), (bank_port, ports[4]), (prior, ports[2])]
        prior = ports[3]
    nets.append((prior, "22163"))
    operations(frame, expected, "complete named-open arm")
    exact_wires(frame, nets, "complete named-open arm")
    handler = unique(frame, "iUse", "22125")
    require(
        call_names(metadata).get("22125") == "Simple Error Handler.vi",
        "named-open error handler identity changed",
    )
    ports = (
        "22128",
        "22132",
        "22137",
        "22145",
        "22148",
        "22151",
        "22154",
        "22157",
        "22160",
        "22163",
    )
    require(
        tuple(t.get("uid") for t in handler.findall("termList/*")) == ports,
        "named-open handler ports changed",
    )
    require(
        [t.findtext("dco/objFlags") for t in handler.findall("termList/*")]
        == ["513", "513", None, None, None, "513", "513", "513", "512", "512"],
        "named-open handler connector directions changed",
    )
    for i, port in enumerate(ports):
        public_term(handler, port, i)
    error_type(metadata, handler.find("termList/*[@uid='22163']"))
    return (
        "24 named opens; 24 READ-only type anchors; 73 complete nets; "
        "all returned reference/access ports unwired; "
        "activation remains a separate gate"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    print(validate_tree(*checked_vam(parser.parse_args().root_archive)))


if __name__ == "__main__":
    main()
