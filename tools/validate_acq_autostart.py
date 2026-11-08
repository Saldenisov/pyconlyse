"""Offline, hash-pinned audit of the XP single-entry telemetry lifecycle.

Native LabVIEW authored these VIs. The saved diagrams and separate native
non-hardware tests are evidence; this audit executes no VI or network call.
The launcher deliberately calls the unchanged hardware main: it is NOT a
read-only acquisition implementation. Only the telemetry branch is read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_shared_state_helpers import (
    Export,
    check_execution,
    const_bytes,
    const_string,
    digest,
    node,
    require,
)
from validate_acq_shared_state_transport import WIRES as TRANSPORT_WIRES

NATIVE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-14/auto_verified_readback_20261014")
FOLDER = "ELYSE_ACQ_TELEMETRY_AUTO_20261017"
START = "START_Acquisition_Telemetry"
WORKER = "ACQ_SharedState_Transport_Auto"
TEST = "TEST_Telemetry_Lifecycle_NO_HARDWARE"
FIXTURE = "ACQ_Telemetry_Lifecycle_Fixture"
SOURCE_HASHES = {
    START: "52162ABE279D2CBDE8C5B5E26996AAF25E4C5E66434A415B2197E9421DE79061",
    WORKER: "6DDE82167C284A73318E5E130F32703445D9626375F56425CCA5A5857D6C1A9F",
    TEST: "408AD49A797A38FD43374DC2E12B1FF9A41D3F5C294769C859611EFD7BA9B209",
    FIXTURE: "81B2583986D0953A24C2093869EFA54AE1AA731430F65EB34E1865F23662199D",
}
# Parsed full-resource fingerprints freeze all nesting, types, calls, wires,
# constants, case polarity, default tunnel values and connector contracts.
# They are deliberately stricter than the explicit critical-path checks below.
RESOURCE_HASHES = {
    START: (
        "D83A4C5A7FB988D9ADE4E83972668954AEE5D02EE22B15E5634DDF7F6C36BC4A",
        "B6D3B5D6BDD18A203BA1024BB1A12744E5E75624D4AA0F55C03022F5E46F11EC",
        "4169EC8520C59B11570036873F103668DB110BAAAF8936ED63978EF1F1151C3F",
    ),
    WORKER: (
        "9ED71CA8EB6C0EE3EF1B27869A798F7E4D1059BE2554D8A8E90F7428002694A5",
        "0167EABCF1E3AB4D627228EDF0927D169F2CB8653A9D29E5DDE6D3C2BF4E2F02",
        "0F12E3CBA3B6C2CDBA4FFA948A33D0E241E316E841CEFB28C5A4B0CD983DC5B8",
    ),
    TEST: (
        "3875EAD4798596C416E43FF4B648E687EFB2E998B9BB02A51AAC12B30DAF70EC",
        "22CB1DC32BFF64AACBAB84C383B4F34075DBA62BC7E4E1258EF6761715F68398",
        "A57EAA6974202AC32311F3E113F48AB8BDB0F48A2CAB5E56D55BEA219660EA84",
    ),
    FIXTURE: (
        "442B08BDEFC4748DE8C3F5578C9853D51DE5CFA084BEADEEFF9314CA9DC46DE1",
        "758F760A7B38ECB54085EAE4A29F33A4A5F7CF36A02CBC4F3A93F89FFFEFCDAE",
        "5CDA23E63F774F4702D1F320A8381924BA8B1BFD85904A52D94444D00A104415",
    ),
}


class NativeExport(Export):
    def __init__(self, name, native=NATIVE):
        self.name = name
        self.directory = Path(native) / "export" / name
        self.bd = ET.parse(self.directory / (name + "_BDHb.xml")).getroot()
        self.fp = ET.parse(self.directory / (name + "_FPHb.xml")).getroot()
        self.metadata = ET.parse(self.directory / (name + ".xml")).getroot()
        self.calls = call_names(self.metadata)


def nets(export, diagram):
    return [
        tuple(t.get("uid") for t in s.findall("termList/*"))
        for s in node(export.bd, "diag", diagram).findall("signalList/*")
    ]


def constant(export, uid, expected):
    require(
        const_bytes(export, uid).hex().upper() == expected, "constant changed: " + uid
    )


def validate(export):
    check_execution(export)
    name = export.name
    if name in (START, TEST):
        expected = (
            {"1031": "0_ACQ_ELYSE.vi", "1049": WORKER + ".vi"}
            if name == START
            else {"378": FIXTURE + ".vi", "1049": WORKER + ".vi"}
        )
        require(export.calls == expected, "unreviewed launcher call")
        constant(export, "1244", "01")  # Must send True, never False.
        constant(export, "1159", "0000000000")  # Native I32 zero + padding.
        constant(export, "179", "00000001")
        constant(export, "345", "00000001")
        require(
            const_string(export, "193") == "ELYSE_ACQ_SHARED_STATE_LATEST_V1",
            "telemetry queue name changed",
        )
        require(
            const_string(export, "357") == "ELYSE_ACQ_TELEMETRY_STOP_V1",
            "stop queue name changed",
        )
        require(
            ("1246", "1104") in nets(export, "1016"),
            "True must reach stop Enqueue.element",
        )
        require(
            ("1161", "1107") in nets(export, "1016"),
            "stop Enqueue timeout must be zero",
        )
        require(
            ("335", "523") in nets(export, "55"),
            "stop queue must be flushed before runtime",
        )
        require(
            ("529", "976") in nets(export, "55"),
            "flushed stop owner must reach runtime",
        )
        if name == START:
            require(
                node(export.bd, "iUse", "1031").findtext("objFlags") == "8389248",
                "main front panel must open on call",
            )
    elif name == WORKER:
        require(not export.calls, "worker must call no subVI")
        constant(export, "759", "0000000000")
        constant(export, "1228", "00000064")
        constant(export, "538", "00000001")
        constant(export, "1099", "00000001")
        require(
            const_string(export, "554") == "ELYSE_ACQ_TELEMETRY_STOP_V1",
            "worker stop queue name changed",
        )
        require(
            ("739", "902") in nets(export, "297"),
            "stop Dequeue.element must reach stop OR",
        )
        require(
            ("899", "311") in nets(export, "297"), "combined stop must reach While.stop"
        )
        for diagram in ("1688", "1694"):
            require(
                nets(export, diagram) == list(TRANSPORT_WIRES[diagram]),
                "reviewed idle/TCP wire topology changed",
            )
    elif name == FIXTURE:
        require(
            export.calls == {"43": "ACQ_SharedState_Collect_Local.vi"},
            "fixture must not run acquisition",
        )
        primitives = sorted(
            n.findtext("primResID")
            for n in export.bd.iter()
            if n.get("class") == "prim"
        )
        require(
            primitives == ["1302", "8010", "8011"],
            "fixture permits only Wait/OpenVIRef/CloseVIRef",
        )
        constant(export, "484", "000003E8")
        constant(export, "654", "00000014")
    else:
        raise AssertionError("unknown lifecycle VI")
    actual = tuple(
        hashlib.sha256(ET.tostring(t)).hexdigest().upper()
        for t in (export.bd, export.fp, export.metadata)
    )
    require(actual == RESOURCE_HASHES[name], "reviewed native resource changed")
    return {"name": name, "offline_audit_passed": True, "executed_by_audit": False}


def audit(native=NATIVE):
    native = Path(native)
    for name, expected in SOURCE_HASHES.items():
        require(
            digest(native / FOLDER / (name + ".vi")) == expected,
            "native VI hash changed: " + name,
        )
    return [validate(NativeExport(name, native)) for name in SOURCE_HASHES]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, default=NATIVE)
    print(json.dumps(audit(parser.parse_args().native), indent=2))
