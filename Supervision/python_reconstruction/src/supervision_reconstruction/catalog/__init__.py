"""Read-only access to the SuperVision VI evidence catalog."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def records() -> tuple[dict[str, Any], ...]:
    """Return immutable-by-convention catalog records; does not contact LabVIEW or hardware."""
    data = json.loads(files(__package__).joinpath("catalog.json").read_text(encoding="utf-8"))
    return tuple(data["records"])


def get(identity: str) -> dict[str, Any]:
    """Return one record by stable identity or raise KeyError."""
    for record in records():
        if record["identity"] == identity:
            return record
    raise KeyError(identity)


__all__ = ["get", "records"]
