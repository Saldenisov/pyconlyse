"""Reproduce a bounded controller scheduling proof; never execute a VI or I/O."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from DeviceServers.control.elyse_acq.vi_simulation.fault_window import (  # noqa: E402
    exhaustive_fault_window,
)
from validate_acq_controlled_stop_ht_ramp import (
    validate as validate_outer,  # noqa: E402
)
from validate_acq_final_cleanup import validate_cleanup_tree  # noqa: E402
from validate_acq_ht_command_ownership import validate_phase_ownership  # noqa: E402
from validate_acq_stop_state_memory import validate_memory  # noqa: E402
from validate_acq_vam_status import checked_vam  # noqa: E402


def audit():
    archive = (
        REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )
    root, metadata = checked_vam(archive)
    source_result = validate_memory(root, metadata)
    outer_result = validate_outer(archive)
    cleanup_result = validate_cleanup_tree(root, metadata)
    phase_result = validate_phase_ownership(root)
    outcomes = exhaustive_fault_window(stop_before=False, tcp_before=False)
    register = json.loads(
        (REPO / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
            encoding="utf-8"
        )
    )
    identities = {
        (group["vi"], uid)
        for group in register["groups"]
        for uid in group["diagram_uids"]
    }
    return {
        "scope": "One entered, returning runtime fault window; not whole Acquisition",
        "source_main_sha256": (
            "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
        ),
        "source_stop_memory_validation": source_result,
        "source_outer_tcp_and_general_selectors_validation": outer_result,
        "source_cleanup_validation": cleanup_result,
        "source_c9_phase_join_validation": phase_result,
        "original_members_with_registered_facets": len({vi for vi, _ in identities}),
        "original_diagrams_with_registered_facets": len(identities),
        "whole_acquisition_closed": False,
        "native_evidence_complete": False,
        "entered_error_selector_uids": ["28682", "40346", "40205"],
        "window_actions": 11,
        "orders": sum(row.order_count for row in outcomes),
        "joint_outcomes": len(outcomes),
        "joined_outcomes": [asdict(row) for row in outcomes if row.entered_outer_frame],
        "all_outcomes": [asdict(row) for row in outcomes],
        "counts_are_probabilities": False,
        "hardware_executed": False,
        "psp_or_network_used": False,
        "assumptions": [
            "All three saved error arms entered; their six assignments complete",
            "All five runtime loop conditions sample stop exactly once",
            "All already-entered body calls, waits and handlers return",
            "No other local/UI/VI-Server writer intervenes",
            "Initial stop=False and TCP=False are explicit supplied seeds",
        ],
        "limits": [
            "Not a native scheduler, fairness or finite-latency proof",
            "No next-iteration, full event queue or whole-cluster epoch enumeration",
            "TCP=True selects outer stop loops; General47 separately selects "
            "the staged stop",
            "No apparatus safety or physical output-state conclusion",
            "Original defaults, disabled arms and full restart remain separately "
            "unqualified",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "all_outcomes"},
            ensure_ascii=False,
            indent=2,
        )
    )
