"""Export bounded main-event coverage, never elevate catalog verification."""

from __future__ import annotations

import json
from pathlib import Path

from supervision_reconstruction.domain.supervision_orchestrator import (
    EVENT_CASES,
    ORCHESTRATION_BLOCKED,
)

PROJECT = Path(__file__).resolve().parents[1]


def main():
    records = [
        {
            "event_index": item.index,
            "label": item.selector_label,
            "bounded_models": list(item.bounded_models),
            "boundary": item.boundary,
            "coverage": "BOUNDED_PURE_MODEL",
            "complete_event_qualification": False,
            "runtime_execution_allowed": False,
        }
        for item in EVENT_CASES
    ]
    if len(records) != 34 or any(not r["bounded_models"] for r in records):
        raise ValueError("Incomplete bounded-model inventory")
    result = {
        "event_structure_uid": 5909,
        "bounded_event_indices": 34,
        "main_event_indices": 34,
        "verified_whole_vi_replacements": 0,
        "implementation_allowed": ORCHESTRATION_BLOCKED.implementation_allowed,
        "events": records,
    }
    output = PROJECT / "EVENT_MODEL_COVERAGE.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "bounded_event_indices": 34,
                "verified_whole_vi_replacements": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
