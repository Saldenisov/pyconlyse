"""Check saved ACQ EPS PSP writer and concurrent runtime-loop topology.

Usage: python tools/validate_acq_eps_publish_parallel.py SOURCE_EXPORT_ZIP
This is read-only; it does not run a VI or access PSP/NI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import (
    checked_root,
    literal,
    peers,
    require,
    unique,
    wire,
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    outer = unique(root, "sequence", "359")
    outer_frames = outer.find("diagramList")
    require(outer_frames is not None and len(outer_frames) == 5,
            "ACQ outer sequence changed")
    runtime_frame = outer_frames[2]
    require(runtime_frame.get("uid") == "367", "ACQ runtime frame moved")
    direct_uids = {node.get("uid") for node in runtime_frame.findall("nodeList/*")}
    require({"102", "203"} <= direct_uids,
            "event and read/write loops are no longer siblings")
    event_loop = unique(root, "whileLoop", "102")
    io_loop = unique(root, "whileLoop", "203")
    require(event_loop in runtime_frame.iter() and io_loop in runtime_frame.iter(),
            "runtime loops moved out of outer frame 2")
    event_body = event_loop.find("diagramList")[0]
    require(event_body.get("uid") == "110"
            and unique(root, "eventStruct", "43") in event_body.iter(),
            "cooling event/timeout Event Structure moved")
    io_body = io_loop.find("diagramList")[0]
    require(io_body.get("uid") == "211", "read/write loop body moved")
    wait = unique(root, "prim", "24889")
    require(wait in io_body.iter() and wait.findtext("primResID") == "1302",
            "read/write loop wait moved")
    literal(io_body, "24741", "00000050")  # 80-ms minimum wait node
    sequence = unique(root, "sequence", "1244")
    require(sequence in io_body.iter(), "read/write sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 7,
            "read/write ordered frames changed")
    publication = frames[1]
    require(publication.get("uid") == "7392", "PSP publication frame moved")
    eps_local = unique(root, "gRef", "18634")
    writer = unique(root, "sharedVariableDynamicWrite", "18665")
    require(eps_local in publication.iter() and writer in publication.iter()
            and eps_local.findtext("termList/*/dco/paramIdx") == "44",
            "EPS publication source/writer moved")
    signals = peers(publication)
    wire(signals, "18639", "18680")  # EPS local -> writer data
    wire(signals, "18802", "18667")  # literal URI -> writer URL
    uri = publication.find(".//*[@uid='18802']/dco/ConstValue")
    require(uri is not None and uri.text is not None
            and bytes.fromhex(uri.text)[4:].decode("ascii") ==
            "ni.var.psp://10.20.30.2/SUPERVISION/EPS",
            "EPS PSP destination changed")
    return [
        "ACQ runtime frame 2 has sibling Event Structure loop 102 and "
        "read/write loop 203",
        "Read/write loop frame 1 wires local EPS paramIdx=44 directly to "
        "SUPERVISION/EPS PSP writer",
        "Read/write loop contains an 80-ms wait node; this is not a "
        "measured publication period",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ EPS publication topology and raw wires")


if __name__ == "__main__":
    main()
