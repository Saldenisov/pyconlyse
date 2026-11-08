"""Check the copied warning-code replacement graph without invoking the VI."""

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import connector_map
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import operations
from validate_acq_tpg300_startup import selectors

ARCHIVE_SHA256 = "98D236E7CFEC98086E9E81260CF9483AA7E6DA50B677F6C79122361B8ADAD92E"
HASHES = {
    "vi.xml": "392FD685DF3A01C97A3EDBB07E0CC0BC9D469E16B884B1BABA66ADDE491CCDC3",
    "vi_BDHb.xml": "E4786B64CBD6740927D20EDF68CC1461663C396008492FDB2622BDB905BF8836",
    "vi_FPHb.xml": "E88929D02C6CF6852FA67E353AFBD5F9A140CF0B22B72084DF65F3A51E2DA8A9",
}
NETS = {
    "84": (
        ("162", "146"),
        ("157", "149"),
        ("144", "91"),
        ("101", "171"),
        ("167", "96", "155"),
    ),
    "108": (("99", "104"),),
    "116": (("122", "105"),),
}


def checked_warning(path):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper() == ARCHIVE_SHA256,
        "warning helper archive changed",
    )
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 4, "warning helper archive count changed")
        roots = {}
        for name, expected in HASHES.items():
            data = archive.read(name)
            require(
                hashlib.sha256(data).hexdigest().upper() == expected,
                "warning helper XML changed",
            )
            roots[name] = ET.fromstring(data)
        return roots


def validate_warning(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(
        {n.get("uid") for n in bd.iter() if n.get("class") == "diag"} == set(NETS),
        "warning helper census changed",
    )
    ops = {
        "84": (
            (None, "171"),
            (None, "167"),
            (None, "162"),
            ("nMux", "153"),
            ("prim", "142"),
            ("select", "89"),
        ),
        "108": (),
        "116": ((None, "122"),),
    }
    for uid in NETS:
        frame = unique(bd, "diag", uid)
        exact_wires(frame, NETS[uid], "warning helper " + uid)
        operations(frame, ops[uid], "warning helper " + uid)
    require(
        connector_map(fp) == [(0, "44"), (1, "24")] and not call_names(meta),
        "warning helper connectors or subVI calls changed",
    )
    for port, control in (("167", "24"), ("171", "44")):
        require(
            unique(bd, "fPTerm", port).find("dco").get("uid") == control,
            "warning helper FP binding changed",
        )
    primitive(bd, "142", 1102, ("144", "146", "149"))
    unbundle = unique(bd, "nMux", "153")
    require(
        unbundle.findtext("objFlags") == "327680"
        and tuple(t.get("uid") for t in unbundle.findall("termList/*"))
        == ("155", "157")
        and unbundle.findtext("termList/*[@uid='157']/dco/i") == "1",
        "warning helper comparison no longer uses error.code",
    )
    case = unique(bd, "select", "89")
    selectors(case, ("108", "116"))
    for port, kind, flag, children in (
        ("91", "caseSel", "0", ("94", "95", "91")),
        ("96", "selTun", "2048", ("99", "100", "96")),
        ("101", "selTun", "2049", ("104", "105", "101")),
    ):
        dco = case.find(f"termList/*[@uid='{port}']/dco")
        require(
            dco.get("class") == kind
            and dco.findtext("objFlags", "0") == flag
            and tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
            "warning helper Boolean/error tunnel changed",
        )
    for uid, value in (("161", "3FFF0006"), ("123", "00000000000000000000")):
        node = next(
            n
            for n in bd.iter()
            if n.get("uid") == uid and n.find("ConstValue") is not None
        )
        require(node.findtext("ConstValue") == value, "warning helper literal changed")
    descriptor, flat = heap_type(meta, 19)
    require(
        descriptor.get("Type") == "Cluster"
        and [
            flat[int(t.get("TypeID"))].get("Type")
            for t in descriptor.findall("TypeDesc")
        ]
        == ["Boolean", "NumInt32", "String"],
        "warning helper zero-error type changed",
    )
    return (
        "Warning helper: three diagrams, seven nets; "
        "code=0x3FFF0006 replaces entire error cluster"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(validate_warning(checked_warning(parser.parse_args().archive)))


if __name__ == "__main__":
    main()
