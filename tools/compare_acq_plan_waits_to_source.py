"""Diagnostic multiset comparison of visible ACQ waits and Python plans.

Literal Wait(ms) rows come from the saved root VI's static instance inventory.
This is not a scheduling proof: waits inside loops execute repeatedly, waits
inside called VIs are not in this inventory, and concurrent I/O adds latency.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from DeviceServers.control.elyse_acq.contracts import Operation  # noqa: E402
from DeviceServers.control.elyse_acq.plans import PROCEDURE_PLANS  # noqa: E402


EVENT = re.compile(r"event:43\[(\d+):")
LITERAL_MS = re.compile(r"milliseconds_to_wait<-literal\.([0-9]+(?:\.[0-9]+)?)")


def main() -> None:
    source_by_event: dict[int, Counter[int]] = defaultdict(Counter)
    unresolved_by_event: dict[int, list[str]] = defaultdict(list)
    with (ROOT / "docs" / "ELYSE_ACQ_CONTROL_INSTANCE_INVENTORY_2026-09-28.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["name"] != "Wait (ms)":
                continue
            event_match = EVENT.search(row["path"])
            if event_match is None:
                continue
            event = int(event_match.group(1))
            if not 3 <= event <= 25:
                continue
            wait_match = LITERAL_MS.search(row["inputs"])
            if wait_match is None:
                unresolved_by_event[event].append(row["path"])
            else:
                source_by_event[event][round(float(wait_match.group(1)))] += 1

    mismatches = 0
    for plan in sorted(PROCEDURE_PLANS.values(), key=lambda item: item.legacy_event_case):
        event = plan.legacy_event_case
        modeled: Counter[int] = Counter()
        for step in plan.steps:
            if step.operation == Operation.WAIT:
                modeled[round(step.duration_s * 1000)] += 1
            elif step.operation == Operation.ANALOG_SWEEP:
                modeled[round(float(step.metadata["period_s"]) * 1000)] += 1
            elif step.operation == Operation.STOP_COUNTER_WHEN_DONE:
                modeled[round(float(step.metadata["poll_interval_s"]) * 1000)] += 1
        source = source_by_event[event]
        only_source = source - modeled
        only_plan = modeled - source
        if only_source or only_plan or unresolved_by_event[event]:
            mismatches += 1
            print(f"event {event} {plan.name}: source={dict(sorted(source.items()))} plan={dict(sorted(modeled.items()))}")
            if only_source:
                print(f"  SOURCE_ONLY: {dict(sorted(only_source.items()))}")
            if only_plan:
                print(f"  PLAN_ONLY: {dict(sorted(only_plan.items()))}")
            if unresolved_by_event[event]:
                print(f"  UNRESOLVED_SOURCE_WAITS: {len(unresolved_by_event[event])}")
    print(f"Wait multisets compared: 23 events; diagnostic differences: {mismatches}")


if __name__ == "__main__":
    main()
