"""Named, fixed targets for manually approved Tango server restarts.

Targets live here rather than in command-line flags so an approval cannot be
accidentally applied to an arbitrary host.  This module is configuration only:
it does not open network connections or import Tango.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.refactor.verify_refactor import RefactorToolError


@dataclass(frozen=True)
class TangoRestartTarget:
    """Connection and runtime settings for one known Tango host."""

    name: str
    ssh_host: str
    repository: str
    environment: str
    starter_device: str


TANGO_RESTART_TARGETS: dict[str, TangoRestartTarget] = {
    "everest": TangoRestartTarget(
        name="everest",
        ssh_host="elyse@10.20.30.202",
        repository=r"C:\dev\pyconlyse",
        environment="pyconlyse39",
        starter_device="tango/admin/everest",
    ),
    "elysium2": TangoRestartTarget(
        name="elysium2",
        ssh_host="elysium2",
        repository=r"C:\dev\pyconlyse",
        environment="pyconlyse39",
        starter_device="tango/admin/elysium2",
    ),
}


def resolve_tango_restart_target(name: str) -> TangoRestartTarget:
    """Return one fixed target; reject aliases and arbitrary hostnames."""
    try:
        return TANGO_RESTART_TARGETS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(TANGO_RESTART_TARGETS))
        raise RefactorToolError(
            f"Unknown Tango restart target {name!r}. Choose one of: {choices}."
        ) from exc
