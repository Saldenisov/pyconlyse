"""Compare pure Python procedure DO assignments to saved ACQ raw DIO wires.

Comparison is a multiset of field/value writes, not a proof of ordering,
timing, error handling, or actual card writes. It never executes a plan.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from DeviceServers.control.elyse_acq.contracts import Operation  # noqa: E402
from DeviceServers.control.elyse_acq.plans import PROCEDURE_PLANS  # noqa: E402


def main() -> None:
    with (ROOT / "docs" / "ELYSE_ACQ_DIO_OUTPUT_FIELD_WRITES_2026-09-29.csv").open(newline="", encoding="utf-8") as stream:
        source_rows = list(csv.DictReader(stream))
    mismatches = 0
    for event_case in range(3, 26):
        source = Counter()
        for row in source_rows:
            if f"eventStruct:43[{event_case}]" not in row["scope_path"]:
                continue
            if row["literal_value"] not in ("True", "False"):
                raise RuntimeError(f"Nonliteral source row in event {event_case}")
            source[(row["bank"], int(row["field_idx"]), row["literal_value"] == "True")] += 1
        plans = [plan for plan in PROCEDURE_PLANS.values() if plan.legacy_event_case == event_case]
        if len(plans) != 1:
            raise RuntimeError(f"Expected one plan for event {event_case}")
        plan = plans[0]
        modeled = Counter()
        for step in plan.steps:
            if step.operation not in (Operation.WRITE_DIGITAL, Operation.WRITE_DIGITAL_GROUP):
                continue
            for target in step.targets:
                match = re.fullmatch(r"(C[345]_OUT_DIO96)\.(\d{2})", target)
                if match is None or type(step.value) is not bool:
                    raise RuntimeError(f"Unparseable plan digital step: {target}, {step.value}")
                modeled[(match.group(1), int(match.group(2)), step.value)] += 1
        missing = source - modeled
        extra = modeled - source
        if missing or extra:
            mismatches += 1
            print(f"event {event_case} {plan.name}: source={sum(source.values())} plan={sum(modeled.values())}")
            for item, count in sorted(missing.items()):
                print(f"  SOURCE_ONLY x{count}: {item}")
            for item, count in sorted(extra.items()):
                print(f"  PLAN_ONLY   x{count}: {item}")
    print(f"DIO event cases compared: 23; mismatched: {mismatches}")
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
