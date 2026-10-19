"""Safety guard shared by generated catalog stubs."""

from __future__ import annotations


def unverified_behavior(identity: str, state: str) -> None:
    """Prevent accidental execution of reconstructed or generated behavior."""
    raise NotImplementedError(
        f"{identity} is catalogued as {state!r}; its behavior is not an approved Python implementation. "
        "Consult catalog.json and original LabVIEW evidence."
    )
