"""Check saved ACQ source ledgers against the non-actuating Python contract.

Reads generated CSV evidence and pure Python metadata only. Does not open a
VI, connect to XP, create NI tasks, or write hardware.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from DeviceServers.control.elyse_acq.dps_bridge import DPS_ACQ_EVENT_CASES  # noqa: E402
from legacy.xp_acq_agent.elyse_agent.hardware_plan import (  # noqa: E402
    STARTUP_AO_LOGICAL,
    STARTUP_DO_TRUE_BITS,
    analog_startup_voltage_image,
)


def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / "docs" / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def validate() -> None:
    dispatch = read_csv("ELYSE_ACQ_DPS_DISPATCH_MAP_2026-09-29.csv")
    if len(dispatch) != 24 or len(DPS_ACQ_EVENT_CASES) != 24:
        raise AssertionError("DPS dispatch length mismatch")
    for index, row in enumerate(dispatch):
        expected_case = DPS_ACQ_EVENT_CASES[index]
        raw_case = int(row["event_case_indices"]) if row["event_case_indices"] else None
        assert int(row["case_idx"]) == index + 1
        assert int(row["dps_field_idx"]) == index
        assert row["property_names"] == "Value+Val(Sgnl)"
        assert raw_case == expected_case, (index, raw_case, expected_case)

    status = read_csv("ELYSE_ACQ_STATUS_FIELD_WRITES_2026-09-29.csv")
    for index, event_case in enumerate(DPS_ACQ_EVENT_CASES):
        matching_clears = [
            row for row in status
            if row["bank"] == "DPS" and int(row["field_idx"]) == index
            and row["literal_value"] == "False"
            and event_case is not None
            and f"eventStruct:43[{event_case}]" in row["scope_path"]
        ]
        assert len(matching_clears) == (0 if event_case is None else 1), index
    assert not any(row["bank"] == "DPS" and row["field_idx"] == "22" for row in status)
    pulse_stop = [
        row for row in status
        if row["bank"] == "EPS" and "eventStruct:43[24]" in row["scope_path"]
    ]
    assert {(int(row["field_idx"]), row["literal_value"]) for row in pulse_stop} == {
        (42, "True"), (52, "False")
    }

    startup = read_csv("ELYSE_ACQ_STARTUP_LOGICAL_CONSTANTS_2026-09-29.csv")
    assert len(startup) == 152
    counts = {bank: sum(row["bank"] == bank for row in startup) for bank in {row["bank"] for row in startup}}
    assert counts == {
        "C3_OUT_DIO96": 40,
        "C4_OUT_DIO96": 32,
        "C5_OUT_DIO96": 40,
        "C6NI6703": 10,
        "C7NI6703": 10,
        "C8NI6703": 10,
        "C9NI6703": 10,
    }
    true_bits = {
        bank: {int(row["field_idx"]) for row in startup if row["bank"] == bank and row["logical_value"] == "True"}
        for bank in ("C3_OUT_DIO96", "C4_OUT_DIO96", "C5_OUT_DIO96")
    }
    assert true_bits == {
        "C3_OUT_DIO96": {1, 4},
        "C4_OUT_DIO96": {1, 4, 6, 8, 17, 19},
        "C5_OUT_DIO96": {33},
    }
    for source_bank, python_bank in (
        ("C3_OUT_DIO96", "C3_DIO96_DO"),
        ("C4_OUT_DIO96", "C4_DIO96_DO"),
        ("C5_OUT_DIO96", "C5_DIO96_DO"),
    ):
        assert true_bits[source_bank] == set(STARTUP_DO_TRUE_BITS[python_bank])
    for bank, values in STARTUP_AO_LOGICAL.items():
        source_values = [
            float(row["logical_value"]) for row in startup if row["bank"] == bank
        ]
        assert tuple(source_values) == tuple(values), bank
    captions = {row["bank"]: row["literal_caption"] for row in startup}
    assert captions["C3_OUT_DIO96"] == "C5_OUT_DIO96"
    assert captions["C5_OUT_DIO96"] == "C3_OUT_DIO96"

    requested = read_csv("ELYSE_ACQ_STARTUP_REQUESTED_AO_2026-09-29.csv")
    assert len(requested) == 40
    ao = {(row["bank"], int(row["field_idx"])): float(row["requested_volts"]) for row in requested}
    python_volts = analog_startup_voltage_image()
    for (bank, index), volts in ao.items():
        assert math.isclose(volts, python_volts[bank][index], rel_tol=0, abs_tol=1e-12)
    for key, volts in {
        ("C8NI6703", 1): 2.2,
        ("C8NI6703", 2): 3.58,
        ("C8NI6703", 3): 2.1775,
        ("C8NI6703", 4): 3.8587,
        ("C8NI6703", 6): 9.0,
        ("C9NI6703", 0): 3.25,
    }.items():
        assert math.isclose(ao[key], volts, rel_tol=0, abs_tol=1e-12), key
    assert all(row["within_configured_range"] == "True" for row in requested)
    print("PASS: raw DPS 24/23+orphan, 23 request clears, startup 152 fields, AO 40 predictions")


if __name__ == "__main__":
    validate()
