"""Inventory every LabVIEW selector frame in the copied Acquisition LLB.

This reads offline ``lvkit describe`` JSON only. It never opens DAQ/VISA
resources, starts a VI, or writes to the XP computer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


DEFAULT_SOURCE = Path(r"C:\dev\ELYSE-ACQ-analysis\offline\lvkit_describe")
DEFAULT_OUTPUT = Path(
    r"C:\dev\pyconlyse\docs\ELYSE_ACQ_VI_FRAME_INVENTORY_2026-09-28.csv"
)

FIELDS = (
    "vi",
    "source_sha256",
    "path",
    "scope_uid",
    "scope_kind",
    "parser_selector_source_unverified",
    "frame_index",
    "frame_label",
    "enabled_by_diagram_disable",
    "direct_instance_count",
    "direct_child_scope_count",
    "direct_calls_and_effects",
    "direct_named_state",
)

EFFECT_TOKENS = (
    ".vi",
    "sharedVariableDynamic",
    "DAQmx",
    "System Exec",
    "Value (Signaling)",
    "Val(Signl)",
    "Property Node",
)


def selected_names(instances: list[dict], tokens: tuple[str, ...]) -> str:
    names = sorted(
        {
            str(node.get("name", ""))
            for node in instances
            if any(token.casefold() in str(node.get("name", "")).casefold() for token in tokens)
        }
    )
    return "; ".join(names)


def enumerate_frames(vi: str, digest: str, nodes: list[dict]):
    def walk(items: list[dict], parent: str, enabled: bool):
        for scope in items:
            if scope.get("kind") != "scope":
                continue
            uid = scope.get("uid")
            kind = str(scope.get("scope_kind", ""))
            selector = scope.get("selector") or {}
            if selector:
                source_node = str(selector.get("node") or "literal")
                occurrence = selector.get("occurrence")
                if occurrence is not None:
                    source_node += f"#{occurrence}"
                selector_source = f"{source_node}.{selector.get('terminal') or ''}"
            else:
                selector_source = ""
            for index, frame in enumerate(scope.get("frames", [])):
                label = str(frame.get("label", ""))
                active = enabled and not (
                    kind == "disabled" and label.casefold() in {"disabled", "désactivé"}
                )
                path = f"{parent}/{kind}:{uid}[{index}:{label}]"
                body = frame.get("body", [])
                instances = [node for node in body if node.get("kind") == "instance"]
                children = [node for node in body if node.get("kind") == "scope"]
                yield {
                    "vi": vi,
                    "source_sha256": digest,
                    "path": path,
                    "scope_uid": uid,
                    "scope_kind": kind,
                    "parser_selector_source_unverified": selector_source,
                    "frame_index": index,
                    "frame_label": label,
                    "enabled_by_diagram_disable": active,
                    "direct_instance_count": len(instances),
                    "direct_child_scope_count": len(children),
                    "direct_calls_and_effects": selected_names(instances, EFFECT_TOKENS),
                    "direct_named_state": selected_names(
                        instances,
                        (
                            "DPS", "EPS", "DPC", "EPC", "VAM", "VDM", "VAD",
                            "VDD", "VTA", "VTL", "VTS", "C1", "C2", "C3",
                            "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11",
                            "TPG300", "Pression", "stop", "Arrêt", "urgence",
                        ),
                    ),
                }
                yield from walk(body, path, active)

    yield from walk(nodes, vi, True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows: list[dict] = []
    for path in sorted(args.source.glob("*.json")):
        raw = path.read_bytes()
        data = json.loads(raw)
        rows.extend(enumerate_frames(path.stem, hashlib.sha256(raw).hexdigest(), data["body"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    by_vi = Counter(row["vi"] for row in rows)
    print(f"frame rows: {len(rows)}; diagram-enabled: {sum(row['enabled_by_diagram_disable'] for row in rows)}")
    for vi, count in sorted(by_vi.items()):
        print(f"{vi}: {count}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
