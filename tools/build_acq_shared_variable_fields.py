"""Build a read-only field census of the ACQ shared-variable panel.

Inputs are copied/offline evidence only. This never connects to LabVIEW, PSP, or DAQ.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


CARD_COUNTS = {
    "C1NI6071E": 64,
    "C2NI6071E": 64,
    "C3_IN_DIO96": 56,
    "C3_OUT_DIO96": 40,
    "C4_IN_DIO96": 64,
    "C4_OUT_DIO96": 32,
    "C5_IN_DIO96": 56,
    "C5_OUT_DIO96": 40,
    "C6NI6703": 10,
    "C7NI6703": 10,
    "C8NI6703": 10,
    "C9NI6703": 10,
    "C10-11 NI6602": 32,
}

OTHER_COUNTS = {
    "DPS": 29,
    "DPC": 5,
    "EPS": 77,
    "EPC": 12,
    "VDM-A": 80,
    "VDM-S": 80,
    "VDD": 80,
    "VAM-A": 64,
    "VAM-S": 64,
    "VAD": 64,
}


def visual_kind(bank: str) -> str:
    if bank in ("DPS", "DPC", "EPS", "EPC", "VDM-A", "VDM-S", "VDD"):
        return "boolean"
    if bank.startswith("C3_") or bank.startswith("C4_") or bank.startswith("C5_"):
        return "boolean"
    if bank in ("VTA", "VTS", "VTL"):
        return "string_array"
    if bank == "C12NI1409":
        return "string"
    return "numeric"


def build_rows(describe_path: Path, channel_map_path: Path) -> list[dict[str, str | int]]:
    describe = json.loads(describe_path.read_text(encoding="utf-8"))
    terminals = {
        terminal["name"]: terminal
        for terminal in describe["connector_pane"]["terminals"]
    }
    rows: list[dict[str, str | int]] = []

    with channel_map_path.open(encoding="utf-8-sig", newline="") as stream:
        channel_rows = list(csv.DictReader(stream))
    for bank, expected in CARD_COUNTS.items():
        group = [item for item in channel_rows if item["group"] == bank]
        if len(group) != expected:
            raise ValueError(f"{bank}: expected {expected} channel rows, found {len(group)}")
        for item in group:
            rows.append(
                {
                    "bank": bank,
                    "bank_index": int(item["index"]),
                    "field_label": " ".join(
                        part for part in (
                            item["logical_code"], item["connector_pin"], item["description"]
                        ) if part
                    ),
                    "visual_kind": visual_kind(bank),
                    "physical_channel": item["physical_channel"],
                    "source": "channel_map.csv",
                }
            )

    for bank, expected in OTHER_COUNTS.items():
        terminal_type = terminals[bank]["type"]
        if not terminal_type.startswith("cluster{") or not terminal_type.endswith("}"):
            raise ValueError(f"{bank}: expected connector cluster")
        labels = terminal_type[len("cluster{") : -1].split(", ")
        if len(labels) != expected:
            raise ValueError(f"{bank}: expected {expected} labels, found {len(labels)}")
        for index, label in enumerate(labels):
            rows.append(
                {
                    "bank": bank,
                    "bank_index": index,
                    "field_label": label,
                    "visual_kind": visual_kind(bank),
                    "physical_channel": "",
                    "source": "0_ACQ_ELYSE.json connector pane",
                }
            )

    # The counter bank has 32 timing fields and one local selector/display.
    counter_labels = terminals["C10-11 NI6602"]["type"]
    if not counter_labels.endswith(", N° du compteur}"):
        raise ValueError("NI6602 counter selector not found")
    rows.append(
        {
            "bank": "C10-11 NI6602",
            "bank_index": 32,
            "field_label": "N° du compteur",
            "visual_kind": "numeric_local_selector",
            "physical_channel": "",
            "source": "0_ACQ_ELYSE.json connector pane",
        }
    )

    for bank in ("VTA", "VTS", "VTL", "C12NI1409"):
        terminal_type = terminals[bank]["type"]
        expected_type = "String" if bank == "C12NI1409" else "[String]"
        if terminal_type != expected_type:
            raise ValueError(f"{bank}: expected {expected_type}, found {terminal_type}")
        rows.append(
            {
                "bank": bank,
                "bank_index": "",
                "field_label": "<array length unknown>" if bank != "C12NI1409" else "<scalar>",
                "visual_kind": visual_kind(bank),
                "physical_channel": "",
                "source": "0_ACQ_ELYSE.json connector pane",
            }
        )

    if len(rows) != 1048:
        raise ValueError(f"expected 1048 inventory rows, found {len(rows)}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", type=Path, required=True)
    parser.add_argument("--channel-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = build_rows(args.describe, args.channel_map)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} field/array records across {len(set(row['bank'] for row in rows))} banks")


if __name__ == "__main__":
    main()
