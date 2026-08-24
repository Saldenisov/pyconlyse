#!/usr/bin/env python3
"""Enforce coverage floors for critical refactored Python modules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE_JSON = PROJECT_ROOT / ".coverage-refactor.json"
MINIMUM_MODULE_COVERAGE = {
    "DeviceServers/base/camera.py": 75.0,
    "DeviceServers/base/general.py": 70.0,
    "DeviceServers/base/motor.py": 70.0,
    "DeviceServers/motion/owis/DS_OWIS_delay_line.py": 65.0,
    "DeviceServers/cameras/avantes/DS_AVANTES_CCD.py": 40.0,
    "DeviceServers/cameras/basler/DS_Basler_camera.py": 30.0,
    "web/backend/device_api.py": 40.0,
    "web/backend/folder_api.py": 75.0,
    "web/backend/treatment_api.py": 65.0,
    "web/backend/treatment_file_cache.py": 80.0,
    "web/backend/treatment_network_path.py": 55.0,
    "web/backend/treatment_service.py": 80.0,
    "web/backend/vd2_measurement_protocol.py": 80.0,
    "web/backend/websocket_handler.py": 45.0,
    "web/backend/app.py": 50.0,
    "web/backend/auth.py": 80.0,
    "web/backend/mutation_auth.py": 90.0,
    "web/backend/hardware_authorization.py": 60.0,
    "web/start_production.py": 50.0,
}
MINIMUM_TOTAL_COVERAGE = 60.0


class CoverageGateError(RuntimeError):
    """Raised when the focused coverage report violates a committed floor."""


def _normalized_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute():
        try:
            path = path.relative_to(PROJECT_ROOT)
        except ValueError:
            pass
    return path.as_posix()


def _percent(summary: Mapping[str, object]) -> float:
    covered = float(summary["covered_lines"])
    statements = float(summary["num_statements"])
    return 100.0 if statements == 0 else 100.0 * covered / statements


def coverage_percentages(payload: Mapping[str, object]) -> dict[str, float]:
    files = payload.get("files")
    if not isinstance(files, dict):
        raise CoverageGateError("Coverage JSON does not contain a files mapping.")

    results = {}
    for raw_path, data in files.items():
        if not isinstance(data, dict) or not isinstance(data.get("summary"), dict):
            continue
        results[_normalized_path(str(raw_path))] = _percent(data["summary"])
    return results


def check_coverage_payload(payload: Mapping[str, object]) -> dict[str, float]:
    percentages = coverage_percentages(payload)
    missing = sorted(set(MINIMUM_MODULE_COVERAGE) - set(percentages))
    if missing:
        raise CoverageGateError("Coverage report omitted: " + ", ".join(missing))

    failures = [
        f"{path}: {percentages[path]:.1f}% < {minimum:.1f}%"
        for path, minimum in MINIMUM_MODULE_COVERAGE.items()
        if percentages[path] < minimum
    ]
    total = payload.get("totals")
    if not isinstance(total, dict):
        raise CoverageGateError("Coverage JSON does not contain totals.")
    total_percent = _percent(total)
    if total_percent < MINIMUM_TOTAL_COVERAGE:
        failures.append(
            f"total: {total_percent:.1f}% < {MINIMUM_TOTAL_COVERAGE:.1f}%"
        )
    if failures:
        raise CoverageGateError("Coverage floor failed: " + "; ".join(failures))
    return percentages


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_COVERAGE_JSON)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = json.loads(args.json.read_text(encoding="utf-8"))
        percentages = check_coverage_payload(payload)
    except (OSError, json.JSONDecodeError, CoverageGateError) as exc:
        print(f"Coverage gate failed: {exc}")
        return 1

    print(
        "Coverage gate passed: "
        + ", ".join(f"{path}={percentages[path]:.1f}%" for path in MINIMUM_MODULE_COVERAGE)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
