"""Complete direct graphs of VAM-A loop body and its first two frames.

Publication and its fault cases reuse the separate pressure proof. No
pressure threshold is present in the checked three-frame sequence. Short
array and global concurrent scheduling behavior remain outside this facet.
"""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_tpg300_pressure import validate_pressure_publication

NETS = {
    "20609": (("20618", "45904"), ("26440", "26415"), ("21066", "20621")),
    "45859": (
        ("88609", "96061"),
        ("45381", "56916"),
        ("46861", "56967"),
        ("46864", "56958"),
        ("46867", "56951"),
        ("102847", "56944"),
        ("102850", "56937"),
        ("45386", "56933"),
        ("100299", "45377"),
        ("55194", "101129"),
        ("74655", "72069"),
        ("53939", "72076"),
        ("45903", "21226", "22992"),
        ("9225", "11468"),
        ("9004", "11764"),
        ("21221", "30539"),
        ("14825", "21225"),
    ),
    "46898": (
        ("58712", "46951"),
        ("62390", "46954"),
        ("62393", "46958"),
        ("62396", "46961"),
        ("62399", "46964"),
        ("58717", "46948"),
        ("1427", "46945"),
        ("1415", "46942"),
        ("62369", "62382"),
        ("62379", "62387"),
        ("47025", "1409"),
        ("47017", "47029"),
        ("46911", "46939"),
        ("46935", "46920"),
        ("46930", "46938"),
    ),
}
OPS = {
    "20609": [
        ("sequence", "45836"),
        (None, "26440"),
        ("prim", "20416"),
        ("gRef", "21059"),
        (None, "20621"),
        (None, "20618"),
    ],
    "45859": [
        ("gRef", "88601"),
        ("demux", "45368"),
        ("prim", "44469"),
        ("gRef", "18306"),
        ("gRef", "53929"),
        ("gRef", "7630"),
        ("gRef", "8992"),
        ("gRef", "8997"),
        ("nMux", "21214"),
        ("gRef", "9174"),
        ("gRef", "30536"),
        ("gRef", "22982"),
    ],
    "46898": [
        ("demux", "62385"),
        ("prim", "62377"),
        ("gRef", "47100"),
        ("demux", "1399"),
        ("prim", "47023"),
        ("gRef", "47013"),
        ("nMux", "46933"),
        ("gRef", "46926"),
        ("gRef", "46917"),
        ("gRef", "46908"),
    ],
}


def checked_vam(path):
    root = checked_root(path)
    with ZipFile(path) as archive:
        meta = ET.fromstring(archive.read("vi.xml"))
    return root, meta


def validate_vam(root, meta):
    for uid, nets in NETS.items():
        frame = unique(root, "diag", uid)
        operations(frame, OPS[uid], "VAM status " + uid)
        exact_wires(frame, nets, "VAM status " + uid)
    sequence = unique(root, "sequence", "45836")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")]
        == ["45859", "46898", "77141"],
        "VAM frame order changed",
    )
    term = unique(root, "sRN", "45865").find("termList/*[@uid='45903']/dco")
    require(term.get("uid") == "45901", "VAM frame input counter tunnel changed")
    tunnel = sequence.find("termList/*[@uid='45904']/dco")
    require(
        tunnel.get("class") == "seqTun"
        and tunnel.get("uid") == "45901"
        and tunnel.findtext("objFlags") == "2048"
        and tuple(t.get("uid") for t in tunnel.findall("termList/*"))
        == ("45903", "46905", "77148", "45904"),
        "VAM sequence iteration tunnel mapping changed",
    )
    loop = unique(root, "whileLoop", "20601")
    require(
        loop.find("diagramList/*").get("uid") == "20609"
        and loop.find("loopIndexDCO").get("uid") == "20616"
        and loop.find("loopIndexDCO/termList/*").get("uid") == "20618"
        and loop.findtext("loopTestDCO/objFlags") == "65537"
        and loop.find("loopTestDCO/termList/*").get("uid") == "20621",
        "VAM loop iteration/Stop-if-True binding changed",
    )
    require(
        constant(unique(root, "diag", "20609"), "26440") == "00000050",
        "VAM independent 80-ms Wait changed",
    )
    primitive(root, "20416", 1302, ("26403", "26415"))
    for uid, port, bank, write in (
        ("21059", "21066", 30, False),
        ("88601", "88609", 60, False),
        ("18306", "55194", 59, False),
        ("53929", "53939", 54, False),
        ("7630", "74655", 53, False),
        ("8992", "9004", 32, False),
        ("8997", "9225", 31, False),
        ("9174", "14825", 41, False),
        ("30536", "30539", 41, True),
        ("22982", "22992", 40, True),
        ("47100", "62369", 67, False),
        ("47013", "47017", 66, False),
        ("46926", "46930", 41, False),
        ("46917", "46920", 41, True),
        ("46908", "46911", 62, False),
    ):
        local(root, uid, port, bank, write)
    for uid, ports, size in (
        ("44469", ("100299", "101129"), 8),
        ("62377", ("62379", "62382"), 4),
        ("47023", ("47025", "47029"), 4),
    ):
        primitive(root, uid, 1168, ports)
        for port, expected in zip(ports, ("Cluster", "Array")):
            descriptor = unique(root, "prim", uid).findtext(
                f"termList/*[@uid='{port}']/dco/typeDesc"
            )
            value, flat = heap_type(meta, int(descriptor[7:-1]))
            require(
                value.get("Type") == expected
                and len(value.findall("TypeDesc"))
                == (size if expected == "Cluster" else 1)
                and all(
                    flat[int(t.get("TypeID"))].get("Type") == "NumFloat64"
                    for t in value.findall("TypeDesc")
                ),
                "VAM array/cluster representation changed",
            )
    for uid, ports in (
        (
            "45368",
            (
                "45377",
                "45381",
                "45386",
                "102850",
                "102847",
                "46867",
                "46864",
                "46861",
                "46858",
            ),
        ),
        ("62385", ("62387", "62390", "62393", "62396", "62399")),
        ("1399", ("1409", "1415", "1427", "58717", "58712")),
    ):
        require(
            tuple(
                t.get("uid") for t in unique(root, "demux", uid).findall("termList/*")
            )
            == ports,
            "VAM unbundle field order changed",
        )
        unbundle = unique(root, "demux", uid)
        require(
            tuple(t.get("uid") for t in unbundle.findall("dcoList/*"))
            == tuple(
                t.find("dco").get("uid") for t in unbundle.findall("termList/*")[1:]
            ),
            "VAM unbundle DCO element ordering changed",
        )
    for uid, pairs in (
        (
            "21214",
            (
                ("21226", 0),
                ("11764", 1),
                ("11468", 2),
                ("72069", 10),
                ("72076", 11),
                ("56916", 12),
                ("56933", 13),
                ("56937", 14),
                ("56944", 15),
                ("56951", 16),
                ("56958", 17),
                ("56967", 18),
                ("96061", 20),
            ),
        ),
        (
            "46933",
            (
                ("46939", 63),
                ("46942", 32),
                ("46945", 33),
                ("46948", 34),
                ("46951", 35),
                ("46954", 36),
                ("46958", 37),
                ("46961", 38),
                ("46964", 39),
            ),
        ),
    ):
        bundle = unique(root, "nMux", uid)
        require(bundle.findtext("objFlags") == "262144", "VAM bundle mode changed")
        for port, field in pairs:
            require(
                bundle.findtext(f"termList/*[@uid='{port}']/dco/i", "0") == str(field),
                "VAM destination field changed",
            )
    validate_pressure_publication(root)
    descriptor = unique(root, "gRef", "9174").findtext("termList/*/dco/typeDesc")
    value, flat = heap_type(meta, int(descriptor[7:-1]))
    require(
        value.get("Type") == "Cluster"
        and len(value.findall("TypeDesc")) == 64
        and all(
            flat[int(t.get("TypeID"))].get("Type") == "NumFloat64"
            for t in value.findall("TypeDesc")
        ),
        "VAM64 DBL shape changed",
    )
    return "VAM status: body and all three frames plus both fault cases; 39 direct nets"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(validate_vam(*checked_vam(parser.parse_args().archive)))


if __name__ == "__main__":
    main()
