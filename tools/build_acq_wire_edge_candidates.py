"""Index candidate LabVIEW dataflow edges from the copied Acquisition LLB.

The lvkit-normalized names are known to misassociate some tunnels and local
variables. An exact output-net match is therefore a *candidate* edge, never a
verified LabVIEW wire. The CSV is an audit queue for native-diagram inspection,
not an executable controller specification.

This tool only reads existing JSON and writes local CSV/JSON reports. It never
loads a VI or touches DAQmx, PSP, VISA, or the equipment.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE = Path(r"C:\dev\ELYSE-ACQ-analysis\offline\lvkit_describe")
DEFAULT_OUTPUT = Path(
    r"C:\dev\pyconlyse\docs\ELYSE_ACQ_WIRE_EDGE_CANDIDATES_2026-09-29.csv"
)


@dataclass(frozen=True)
class Instance:
    vi: str
    path: str
    uid: str
    name: str
    inputs: tuple[dict, ...]
    outputs: tuple[dict, ...]


def walk(nodes: list[dict], vi: str, path: str):
    for node in nodes:
        if node.get("kind") == "instance":
            yield Instance(
                vi,
                path,
                str(node.get("uid", "")),
                str(node.get("name", "")),
                tuple(node.get("inputs") or ()),
                tuple(node.get("outputs") or ()),
            )
        elif node.get("kind") == "scope":
            scope = f"{node.get('scope_kind', '')}:{node.get('uid', '')}"
            for index, frame in enumerate(node.get("frames") or ()):
                label = frame.get("label", "")
                child_path = f"{path}/{scope}[{index}:{label}]"
                yield from walk(frame.get("body") or [], vi, child_path)


def net_key(net: dict | None) -> tuple[str, str, str] | None:
    if not net or not net.get("node"):
        return None
    return (
        str(net.get("node", "")),
        str(net.get("occurrence", "")),
        str(net.get("terminal", "")),
    )


def describe_net(net: dict | None) -> str:
    if not net:
        return ""
    if not net.get("node"):
        return f"literal:{net.get('terminal', '')}"
    node, occurrence, terminal = net_key(net) or ("", "", "")
    return f"{node}#{occurrence}.{terminal}"


def index_vi(source: Path):
    document = json.loads(source.read_text(encoding="utf-8"))
    vi = source.stem
    instances = list(walk(document.get("body") or [], vi, vi))
    producers: dict[tuple[str, str, str], dict[str, Instance]] = defaultdict(dict)
    for instance in instances:
        for output in instance.outputs:
            key = net_key(output)
            if key is not None:
                producers[key][instance.uid] = instance

    rows = []
    for instance in instances:
        for input_ in instance.inputs:
            net = input_.get("net")
            key = net_key(net)
            matches = list(producers.get(key, {}).values()) if key else []
            if key is None:
                status = "literal_or_unresolved"
            elif not matches:
                if re.search(
                    r"(?:Sequence|Loop|Structure)$", str(net.get("node", ""))
                ):
                    status = "scope_boundary_unresolved"
                else:
                    status = "producer_not_indexed"
            elif len(matches) > 1:
                status = "ambiguous_producer"
            elif matches[0].path == instance.path:
                status = "candidate_same_frame"
            else:
                status = "candidate_cross_frame_or_scope"
            rows.append(
                {
                    "vi": vi,
                    "consumer_path": instance.path,
                    "consumer_uid": instance.uid,
                    "consumer_name": instance.name,
                    "input_terminal": input_.get("terminal", ""),
                    "input_net": describe_net(net),
                    "producer_status": status,
                    "producer_path": " | ".join(m.path for m in matches),
                    "producer_uid": " | ".join(m.uid for m in matches),
                    "producer_name": " | ".join(m.name for m in matches),
                }
            )
    return instances, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    all_rows = []
    instance_count = 0
    for source in sorted(args.source.glob("*.json")):
        instances, rows = index_vi(source)
        instance_count += len(instances)
        all_rows.extend(rows)
    if not all_rows:
        raise SystemExit(f"No parsed inputs found in {args.source}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    counts = Counter(row["producer_status"] for row in all_rows)
    print(f"VIs={len(list(args.source.glob('*.json')))} instances={instance_count} inputs={len(all_rows)}")
    for status, count in sorted(counts.items()):
        print(f"{status}={count}")
    print(args.output)


if __name__ == "__main__":
    main()
