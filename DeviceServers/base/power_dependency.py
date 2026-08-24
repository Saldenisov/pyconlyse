"""Read-only Netio power dependency helpers for Tango device servers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class PowerDependencyState:
    """Configured PDU output state without issuing any PDU command."""

    configured: bool
    powered: Optional[bool]
    detail: str

    def __iter__(self):
        """Keep compatibility with legacy ``powered, detail = ...`` readers."""
        yield self.powered
        yield self.detail


def read_power_dependency_state(
    device_name: str,
    output_id: int,
    proxy_factory: Callable[[str], object],
    *,
    timeout_ms: int = 3000,
) -> PowerDependencyState:
    """Return one Netio output state using only Tango attribute reads."""
    name = str(device_name or "").strip()
    try:
        output = int(output_id or 0)
    except (TypeError, ValueError):
        output = 0

    if not name or output <= 0:
        return PowerDependencyState(False, None, "power dependency is not configured")

    try:
        proxy = proxy_factory(name)
        set_timeout = getattr(proxy, "set_timeout_millis", None)
        if callable(set_timeout):
            set_timeout(int(timeout_ms))
        output_ids = list(proxy.read_attribute("ids").value)
        output_states = list(proxy.read_attribute("states").value)
        index = [int(value) for value in output_ids].index(output)
        is_on = bool(int(output_states[index]))
    except (IndexError, TypeError, ValueError) as error:
        return PowerDependencyState(
            True,
            None,
            f"power PDU {name} does not provide output {output}: {error}",
        )
    except Exception as error:
        return PowerDependencyState(
            True,
            None,
            f"cannot read power PDU {name} output {output}: {error}",
        )

    return PowerDependencyState(True, is_on, f"power PDU {name} output {output}")
