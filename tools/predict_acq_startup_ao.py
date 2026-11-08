"""Compute requested startup NI6703 voltages from saved logical vectors.

This is a static software calculation using the recovered calibration map,
not a card write, physical measurement, or safe-operating-state assertion.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legacy.xp_acq_agent.elyse_agent.transforms import attenuator_voltage, dephaser_voltage


def predict(startup_csv: Path, calibration_csv: Path) -> list[dict[str, str | int]]:
    with startup_csv.open(newline="", encoding="utf-8") as stream:
        startup = list(csv.DictReader(stream))
    with calibration_csv.open(newline="", encoding="utf-8") as stream:
        calibration = {
            (row["group"], int(row["index"])): row
            for row in csv.DictReader(stream)
            if row["group"] in {"C6NI6703", "C7NI6703", "C8NI6703", "C9NI6703"}
        }
    ao = [row for row in startup if row["kind"] == "AO"]
    if len(ao) != 40 or len(calibration) != 40:
        raise RuntimeError(f"Expected 40 AO startup and calibration rows; got {len(ao)}, {len(calibration)}")
    rows = []
    for row in ao:
        bank = row["bank"]
        idx = int(row["field_idx"])
        logical = float(row["logical_value"])
        cal = calibration[(bank, idx)]
        if cal["status"] != "ACTIVE":
            raise RuntimeError(f"Inactive calibration {bank}[{idx}]")
        if (bank, idx) == ("C8NI6703", 3):
            requested = dephaser_voltage(logical)
            method = "dephaser_polynomial"
        elif (bank, idx) == ("C8NI6703", 4):
            requested = attenuator_voltage(logical)
            method = "attenuator_acos_polynomial"
        else:
            if cal["transform"] != "y=x*scale+offset":
                raise RuntimeError(f"Unexpected transform {bank}[{idx}]: {cal['transform']}")
            requested = logical * float(cal["scale"]) + float(cal["offset"])
            method = "linear"
        lower = float(cal["range_min_v"])
        upper = float(cal["range_max_v"])
        rows.append({
            "bank": bank,
            "field_idx": idx,
            "logical_value": row["logical_value"],
            "field_label": row["field_label"],
            "physical_channel": cal["physical_channel"],
            "method": method,
            "requested_volts": repr(requested),
            "task_min_volts": cal["range_min_v"],
            "task_max_volts": cal["range_max_v"],
            "within_configured_range": str(lower <= requested <= upper),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("startup_csv", type=Path)
    parser.add_argument("calibration_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    rows = predict(args.startup_csv, args.calibration_csv)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Predicted {len(rows)} requested AO voltages -> {args.output_csv}")
    for row in rows:
        if float(row["requested_volts"]) != 0:
            print(f"{row['bank']}[{row['field_idx']}] {row['logical_value']} -> {row['requested_volts']} V ({row['method']})")
    print(f"Configured-range violations: {sum(row['within_configured_range'] != 'True' for row in rows)}")


if __name__ == "__main__":
    main()
