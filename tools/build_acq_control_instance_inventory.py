"""Index normalized LabVIEW nodes for software-control dataflow review.

This is an offline reader of the copied LLB's ``lvkit describe`` JSON. It
does not load LabVIEW, DAQmx, PSP, VISA, or any hardware resource.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DEFAULT_SOURCE = Path(
    r"C:\dev\ELYSE-ACQ-analysis\offline\lvkit_describe\0_ACQ_ELYSE.json"
)
DEFAULT_OUTPUT = Path(
    r"C:\dev\pyconlyse\docs\ELYSE_ACQ_CONTROL_INSTANCE_INVENTORY_2026-09-28.csv"
)

FIELDS = (
    "phase",
    "runtime_loop_uid",
    "event_case",
    "path",
    "uid",
    "name",
    "qualified_name",
    "operation",
    "object",
    "method",
    "input_count",
    "output_count",
    "inputs",
    "outputs",
)


def describe_net(net: dict | None) -> str:
    if not net:
        return ""
    node = net.get("node") or "literal"
    terminal = net.get("terminal") or ""
    occurrence = net.get("occurrence")
    suffix = f"#{occurrence}" if occurrence is not None else ""
    return f"{node}{suffix}.{terminal}"


def instances(nodes: list[dict], *, path: str = "0_ACQ_ELYSE"):
    for node in nodes:
        if node.get("kind") == "instance":
            parts = path.split("/")
            phase = next(
                (part for part in parts if part.startswith("sequence:359[")), ""
            )
            runtime_loop_uid = next(
                (
                    part.split(":", 1)[1].split("[", 1)[0]
                    for part in parts
                    if part.startswith("while:") and phase == "sequence:359[2:2]"
                ),
                "",
            )
            event_case = next(
                (part for part in parts if part.startswith("event:43[")), ""
            )
            inputs = node.get("inputs", [])
            outputs = node.get("outputs", [])
            yield {
                "phase": phase,
                "runtime_loop_uid": runtime_loop_uid,
                "event_case": event_case,
                "path": path,
                "uid": node.get("uid", ""),
                "name": node.get("name", ""),
                "qualified_name": node.get("qualified_name", ""),
                "operation": node.get("operation", ""),
                "object": node.get("object", ""),
                "method": node.get("method", ""),
                "input_count": len(inputs),
                "output_count": len(outputs),
                "inputs": "; ".join(
                    f"{item.get('terminal', '')}<-{describe_net(item.get('net'))}"
                    for item in inputs
                ),
                "outputs": "; ".join(describe_net(item) for item in outputs),
            }
        elif node.get("kind") == "scope":
            kind = node.get("scope_kind", "")
            uid = node.get("uid", "")
            for index, frame in enumerate(node.get("frames", [])):
                label = str(frame.get("label", ""))
                frame_path = f"{path}/{kind}:{uid}[{index}:{label}]"
                yield from instances(frame.get("body", []), path=frame_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    body = json.loads(args.source.read_bytes())["body"]
    rows = list(instances(body))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"indexed {len(rows)} root-VI instance nodes: {args.output}")


if __name__ == "__main__":
    main()
