"""Check the saved XP fixture sender, without executing VI or generated code.

Run using modern local Python after lvkit's in-process resource extraction.
This is a hash-pinned, narrow wire audit, not a production integration gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


SOURCE_SHA256 = "E77397ECC3B23DD144C2685CC1C49FC40C32626CF61AFC0203467ACA6D22D092"
EXPORT_SHA256 = {
    "vi.xml": "6A8A83838DC63204B1382D0117894446AE29165783A14B6B851606264F8D1DB0",
    "vi_BDHb.xml": "67FE52B947DC80EB29E2FFBF150750523DA2D0E3739115BBDE43E0D728E7106E",
}
# Native UID -> resource ID. Names are grounded in the inspected XP diagram.
PRIMITIVES = {
    "43": ("1715", "TCP Open"),
    "75": ("1714", "TCP Write"),
    "105": ("1713", "TCP Close"),
    "221": ("1716", "TCP Read: four-byte header"),
    "254": ("1502", "String Length"),
    "310": ("1164", "Flatten To String"),
    "459": ("1716", "TCP Read: bounded body"),
    "492": ("1166", "Type Cast"),
    "551": ("1127", "In Range and Coerce"),
}
WIRES = {
    ("557", "930"), ("111", "864"), ("468", "760"),
    ("701", "63", "93", "242", "480"),
    ("465", "117"), ("471", "123"), ("560", "483"),
    ("635", "563"), ("600", "569"), ("504", "566"),
    ("227", "477"), ("233", "486"), ("230", "498"),
    ("440", "245", "501"), ("81", "239"), ("87", "248"),
    ("357", "96"), ("283", "363", "263"), ("322", "360"),
    ("260", "334"), ("51", "90"), ("54", "99"),
    ("178", "66"), ("143", "69"),
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def validate_diagram(diagram, metadata):
    require(len(diagram.findall(".//*[@class='diag']")) == 1,
            "fixture sender must have one diagram and no nested loops/cases")
    require(not diagram.findall(".//*[@class='iUse']"), "unexpected subVI call")
    nodes = diagram.findall("root/zPlaneList/*[@class]")
    require({(n.get("class"), n.get("uid")) for n in nodes}
            == {("prim", uid) for uid in PRIMITIVES} | {("concat", "351")},
            "unexpected executable node")
    for node in nodes:
        if node.get("class") == "prim":
            require(node.findtext("primResID") == PRIMITIVES[node.get("uid")][0],
                    "primitive identity changed")
    wires = diagram.findall("root/signalList/*")
    endpoints = {tuple(t.get("uid") for t in w.findall("termList/*")) for w in wires}
    require(endpoints == WIRES and len(wires) == len(WIRES), "saved wire topology changed")
    defaults = metadata.find("DFDS/Section")
    require(defaults is not None, "saved default data absent")
    expected = {"10": ("String", "127.0.0.1"), "11": ("U16", "8766"),
                "13": ("I32", "4"), "14": ("I32", "65536"),
                "15": ("I32", "1"), "16": ("I32", "1000")}
    for type_id, (tag, value) in expected.items():
        require(defaults.findtext(f"DataFill[@TypeID='{type_id}']/{tag}") == value,
                f"saved constant changed: TypeID {type_id}")
    execution = metadata.find("LVSR/Section/Execution")
    require(execution is not None and execution.get("RunOnOpen") == "0",
            "RunOnOpen must be disabled")


def validate(source, export):
    require(digest(source) == SOURCE_SHA256, "saved sender source hash changed")
    for name, expected in EXPORT_SHA256.items():
        require(digest(export / name) == expected, f"unreviewed export: {name}")
    diagram = ET.parse(export / "vi_BDHb.xml").getroot()
    metadata = ET.parse(export / "vi.xml").getroot()
    validate_diagram(diagram, metadata)
    return {
        "source": str(source.resolve()), "source_sha256": SOURCE_SHA256,
        "export_sha256": EXPORT_SHA256, "primitive_count": len(PRIMITIVES),
        "concat_count": 1, "wire_count": len(WIRES), "diagram_count": 1,
        "subvi_call_count": 0, "destination": "127.0.0.1:8766",
        "tcp_timeout_per_call_ms": 1000,
        "error_chain": ["Open", "Write", "Read header", "Read body", "Close", "indicator"],
        "connection_chain": ["Open", "Write", "Read header", "Read body", "Close"],
        "request": "four-byte I32 big-endian byte length + pre-serialized ASCII JSON",
        "ack": "raw JSON string; not semantically validated by VI",
        "ack_length": "In Range and Coerce feeds read count; not a rejection branch",
        "live_acquisition_hook": False, "hardware_access": False,
        "commands_toward_labview": False,
        "limitations": [
            "No request-size guard or general UTF-8 JSON serializer",
            "No strict rejection of invalid ACK length or verification of id/ok/accepted",
            "No bounded queue, worker loop, connector-pane integration or live-data tap",
            "Timeout is per call, not a measured total transaction deadline",
            "Static audit and synthetic XP test do not certify whole Acquisition or plant safety",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(args.source, args.export)
    serialized = json.dumps(report, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    print(serialized, end="")


if __name__ == "__main__":
    main()
