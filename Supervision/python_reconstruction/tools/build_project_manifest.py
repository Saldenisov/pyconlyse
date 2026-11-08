from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SUPERVISION = PROJECT.parent
OUTPUT = PROJECT / "PROJECT_MANIFEST.json"
ANALYSIS_ARTIFACTS = (
    "build_vi_understanding_audit.py",
    "VI_UNDERSTANDING_AUDIT.json",
    "VI_UNDERSTANDING_AUDIT_r2.json",
    "VI_UNDERSTANDING_AUDIT_r3.json",
    "VI_UNDERSTANDING_AUDIT_r4.json",
    "build_non_event_logic_evidence.py",
    "non_event_logic_evidence_20261004.json",
    "inspect_non_event_logic.py",
    "build_lifecycle_tail_evidence.py",
    "lifecycle_tail_evidence_20261004.json",
    "REMAINING_EVENT_TRANSFER.md",
    "build_remaining_event_evidence.py",
    "remaining_event_evidence_20261004.json",
    "inspect_remaining_events.py",
    "freeze_main_netlist.py",
    "main_original_netlist_20261004.json",
    "main_original_netlist_20261004_r2.json",
    "build_loop_ownership_evidence.py",
    "loop_ownership_evidence_20261004.json",
    "lvkit_eval/supervision_loop_ownership_20261004.patch",
    "lvkit_eval/parser_working_tree_drift_20261004.json",
    "PARAMETER_EVENT_TRANSFER.md",
    "build_parameter_event_evidence.py",
    "parameter_event_evidence_20261004.json",  # superseded metadata, retained audit
    "parameter_event_evidence_20261004_r2.json",
    "PAGE_COMMAND_TRANSFER.md",
    "build_page_command_evidence.py",
    "page_command_evidence_20261003.json",
    "DIGITAL_EVENT_TRANSFER.md",
    "build_digital_event_evidence.py",
    "digital_event_evidence_20261003.json",
    "lvkit_eval/CROSS_VALIDATION_STATUS.md",
    "lvkit_eval/qualify_parser_identities.py",
    "lvkit_eval/supervision_parser_lvkit_release.patch",
    "lvkit_eval/parser_release_20261003/receipt.json",
    "lvkit_eval/parser_motor_release_20261003/receipt.json",
    "lvkit_eval/working_copy_integrity_20261003.json",
    "COMPLETENESS_AUDIT.md",
    "FRAME_MAPPING_LIMITS.md",
    "VI_COVERAGE_MATRIX.md",
    "expected_frame_ledger_summary.json",
    "expected_loop_body_ledger.csv",
    "expected_loop_body_ledger.jsonl",
    "expected_selector_frame_ledger.csv",
    "expected_selector_frame_ledger.jsonl",
    "order_candidate_visual_audit.jsonl",
    "vi_coverage_matrix.csv",
    "visual_evidence_manifest.jsonl",
    "visual_evidence_summary.csv",
    "visual_evidence_validation.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def artifact(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(SUPERVISION.parent).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    project_files = sorted(
        (
            path
            for path in PROJECT.rglob("*")
            if path.is_file()
            and path != OUTPUT
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in {".pyc", ".pyo"}
        ),
        key=lambda path: path.as_posix().casefold(),
    )
    analysis_files = [SUPERVISION / "analysis" / name for name in ANALYSIS_ARTIFACTS]
    understanding_audit = json.loads(
        (SUPERVISION / "analysis/VI_UNDERSTANDING_AUDIT_r4.json").read_text(
            encoding="utf-8"
        )
    )
    analysis_files.extend(
        SUPERVISION.parent / row["saved_descriptor"]["path"]
        for row in understanding_audit["records"]
        if row["saved_descriptor"]
    )
    analysis_files.extend(
        SUPERVISION.parent / row["path"]
        for row in understanding_audit[
            "journal_new_descriptor_and_native_observations"
        ]["evidence"]
    )
    # Include original source/XML artifacts actually referenced by the new
    # qualification receipts, not merely their existence/count summaries.
    root_receipt = json.loads(
        (
            SUPERVISION / "analysis/lvkit_eval/parser_release_20261003/receipt.json"
        ).read_text(encoding="utf-8")
    )
    receipt_paths = [Path(row["path"]) for row in root_receipt["rows"]]
    receipt_paths.append(
        SUPERVISION / "analysis/lvkit_eval/parser_motor_release_20261003/receipt.json"
    )
    for receipt_path in receipt_paths:
        analysis_files.append(receipt_path)
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        analysis_files.append(Path(data["source"]))
        analysis_files.extend(Path(row["path"]) for row in data["xml"])
        if data.get("draft_path"):
            analysis_files.append(Path(data["draft_path"]))
    digital_evidence = json.loads(
        (SUPERVISION / "analysis/digital_event_evidence_20261003.json").read_text(
            encoding="utf-8"
        )
    )
    analysis_files.extend(
        SUPERVISION / row["path"] for row in digital_evidence["artifacts"]
    )
    page_evidence = json.loads(
        (SUPERVISION / "analysis/page_command_evidence_20261003.json").read_text(
            encoding="utf-8"
        )
    )
    analysis_files.extend(
        SUPERVISION / row["path"] for row in page_evidence["artifacts"]
    )
    parameter_evidence = json.loads(
        (SUPERVISION / "analysis/parameter_event_evidence_20261004_r2.json").read_text(
            encoding="utf-8"
        )
    )
    analysis_files.extend(
        SUPERVISION / row["path"] for row in parameter_evidence["artifacts"]
    )
    for name in (
        "remaining_event_evidence_20261004.json",
        "loop_ownership_evidence_20261004.json",
        "non_event_logic_evidence_20261004.json",
        "lifecycle_tail_evidence_20261004.json",
    ):
        evidence = json.loads(
            (SUPERVISION / "analysis" / name).read_text(encoding="utf-8")
        )
        analysis_files.extend(
            SUPERVISION / row["path"] for row in evidence["artifacts"]
        )
    analysis_files.extend(
        SUPERVISION / "integration_analysis" / name
        for name in (
            "README.md",
            "SUPERVISION_UI_EVENT_MATRIX.csv",
            "ACQ_PROCEDURE_UI_TRACEABILITY.csv",
            "MAGNET_CONTROL_OWNERSHIP.md",
        )
    )
    analysis_files = list(dict.fromkeys(analysis_files))
    missing = [path for path in analysis_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing analysis artifacts: {missing!r}")
    records = [artifact(path) for path in project_files + analysis_files]
    manifest = {
        "schema_version": 1,
        "scope": (
            "SuperVision Python reconstruction plus authoritative analysis indexes"
        ),
        "file_count": len(records),
        "files": records,
    }
    OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "file_count": len(records),
                "sha256": sha256(OUTPUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
