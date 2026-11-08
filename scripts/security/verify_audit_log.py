"""Verify the hash chain of a PYCONLYSE SQLite audit journal."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def verify(path: Path) -> int:
    previous_hash = "0" * 64
    count = 0
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(audit_event)")
        }
        versioned = "entry_version" in columns
        select = """
            SELECT sequence, event_id, recorded_at, subject, roles_json,
                   source_ip, method, route_id, path, request_json, status_code,
        """
        if versioned:
            select += """
                   completed_at, duration_ms, outcome, response_json, error_json,
                   device, command, entry_version,
            """
        select += """ previous_hash, entry_hash
            FROM audit_event ORDER BY sequence
        """
        rows = connection.execute(select)
        for row in rows:
            base = row[:11]
            (
                sequence,
                event_id,
                recorded_at,
                subject,
                roles_json,
                source_ip,
                method,
                route_id,
                request_path,
                request_json,
                status_code,
            ) = base
            if versioned:
                (
                    completed_at,
                    duration_ms,
                    outcome,
                    response_json,
                    error_json,
                    device,
                    command,
                    entry_version,
                    stored_previous_hash,
                    stored_entry_hash,
                ) = row[11:]
            else:
                entry_version = 1
                stored_previous_hash, stored_entry_hash = row[11:]
            if stored_previous_hash != previous_hash:
                raise RuntimeError(f"Broken audit chain before sequence {sequence}")
            payload = {
                "event_id": event_id,
                "recorded_at": recorded_at,
                "subject": subject,
                "roles": json.loads(roles_json),
                "source_ip": source_ip,
                "method": method,
                "route_id": route_id,
                "path": request_path,
                "request_json": request_json,
                "status_code": status_code,
            }
            if entry_version >= 2:
                payload.update(
                    {
                        "completed_at": completed_at,
                        "duration_ms": duration_ms,
                        "outcome": outcome,
                        "response_json": response_json,
                        "error_json": error_json,
                        "device": device,
                        "command": command,
                        "entry_version": entry_version,
                    }
                )
            payload["previous_hash"] = stored_previous_hash
            calculated = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
            if calculated != stored_entry_hash:
                raise RuntimeError(f"Audit event {sequence} has been modified")
            previous_hash = stored_entry_hash
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    count = verify(args.path)
    print(f"Audit chain valid: {count} event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
