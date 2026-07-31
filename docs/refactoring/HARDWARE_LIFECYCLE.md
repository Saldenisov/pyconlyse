# Hardware Lifecycle Contract

Every device server reports three independent facts. Clients must not infer one
from another.

| Layer | Source | Meaning |
| --- | --- | --- |
| Tango reachability | Dashboard `DeviceProxy.state()` and Astor | Is the server process/device proxy reachable? |
| Hardware connection | `hardware_connection_state` | Is the physical supply and transport available? |
| Initialisation | `initialization_state` | Has the connected hardware been made operational? |

## Hardware connection

`POWER_OFF` means a configured PDU output is confirmed off. No connection or
recovery attempt may be made. `POWER_STATUS_UNAVAILABLE` means the PDU itself
cannot be read. `DISCONNECTED` means power is available or unknown but the
hardware transport did not connect. `CONNECTED` means a passive transport
probe succeeded. `READY` means a device-specific operational initialisation
succeeded.

## Initialisation

`NOT_REQUESTED` means transport is known but no active device setup was
requested. `PENDING` means power was restored and the settle timer is active.
`IN_PROGRESS`, `SUCCEEDED`, and `FAILED` describe explicit or explicitly
configured automatic initialisation.

## Tango state compatibility

`DevState` remains a legacy control state, not the primary diagnostic source.
For example, a reachable server with an unpowered controller may report
`DevState.OFF` plus `POWER_OFF` and `NOT_REQUESTED`; this never means the Tango
server is missing. A device proxy failure is only reported by the dashboard as
`TANGO UNREACHABLE`.

## Migration requirements

1. Subclasses call `set_hardware_lifecycle` at power, connect, initialise, and
   recovery boundaries.
2. Passive probing and status polling must never energise hardware, initialise
   axes, or move equipment.
3. Dashboard diagnostics read lifecycle attributes lazily. It must not poll
   every attribute of every device.
4. New lifecycle transitions require tests for power off, transport failure,
   connected-but-not-initialised, and ready states.
