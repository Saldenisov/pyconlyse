# ELYSE acquisition server architecture

## Current implementation boundary

The port-8765 procedure transport described below is a simulator. It is distinct
from `acquisition_server.pyw`, the prepared XP GUI/default port-8771 server that
can initialize real NI tasks, write startup outputs and perform locally
confirmed General procedures. Its HTTP routes are read-only; local initialization
is not. Its six input banks are not the LabVIEW bridge's 27-bank schema.

The current cross-layer audit, source evidence, deployment limits and unresolved
parity are in [ELYSE business logic migration status](ELYSE_BUSINESS_LOGIC_STATUS.md).
Neither server is a complete, qualified replacement for the original VI.

## Actual system boundary

The legacy ACQUISITION application is not primarily an operator UI. It is the
hardware-control server on `10.20.30.10`. It mediates between:

- SuperVision on `10.20.30.2`, which submits operator intent;
- NI6071E, NI6602, NI6703, DIO96, and NI6220 cards;
- serial focal and vacuum equipment;
- the physical ELYSE machine.

The Python replacement therefore belongs on the server side. Pyconlyse is the
client/operator surface, not a raw NI writer. The current XP/Python 3.4 bridge
extends the existing length-prefixed TCP agent on port 8765 with authenticated
named-procedure RPC; the previously proposed Tango controller
remains a separate modern-host model, not an XP deployment requirement.

```text
operator
  -> Pyconlyse web UI
  -> authenticated web backend
  -> HMAC-signed named intent (tcp://10.20.30.10:8765)
  -> original Python 3.4 ELYSE ACQ agent + simulation procedure controller
  -> logical memory image + durable SQLite phase journal
  -> signed acknowledgement/history
  -> Pyconlyse web UI
```

This port-8765 simulator path does not reach NI/serial adapters or physical hardware. Physical
readback, interlock validation, and commissioned output execution require a
future hardware adapter and independent qualification; they are not implied by
an authenticated transport or a successful simulation.

## Responsibility split

### Web application

- displays state, alarms, readbacks, active procedure, and audit trail;
- asks for one high-level action such as `cooling.start`;
- supplies one idempotency key and one externally authorized intent;
- never addresses a raw card, port, pin, or voltage channel.

### ELYSE ACQ procedure controller

- permits one procedure at a time;
- validates command identity and atomically compares session/revision;
- owns reviewed plan step order and software waits;
- deduplicates durable intent IDs, including after restart;
- records phase-level audit information;
- retains unresolved outcomes without automatic retry;
- currently executes logical simulation values only; no hardware readback,
  commissioned interlock, physical setpoint submission, or physical shutdown claim.

### Hardware adapters

- map stable logical IDs to commissioned DAQmx/serial resources;
- enforce range, polarity, and safe defaults;
- implement analog input/output, digital input/output, and counter output;
- expose readback without embedding operator workflow.

## Deployment invariant

The existing generic `DS_DAQmx` can supply adapter patterns, but the web layer
must not compose a safety-critical procedure from generic raw writes. The
procedure controller is the sole public mutation boundary for ACQUISITION.

The port-8765 implementation is simulator-only; it has no hardware activation
option. `legacy/xp_acq_agent/main.py --supervision` runs on stdlib Python 3.4;
`web/backend/elyse_acq_transport.py` links it to the durable web business layer.
The original agent, named procedures, status and PSP-compatible snapshots share
one listener and logical state. Raw simulation setters are blocked while the
procedure extension owns outputs. The old `supervision_server.py` entry point
is only a compatibility wrapper to `main.py`, not a second HTTP server.
See `legacy/xp_acq_agent/SUPERVISION.md` for the actual wire/deployment
contract and restart semantics.

The portable bundle simulates all 23 plans / 158 steps, including three explicit
magnet stubs. Their physical ownership remains unresolved; no legacy DAQmx
fallback is enabled. All 20 recovered setpoint arrows use a distinct named
simulation command lane. An arrow can overlap a normal procedure without
changing its run or DPS; UNKNOWN outcomes block both lanes. Values require an
explicit first simulation base and are persisted in the same logical image.
Immutable IDs and atomic session/revision/base checks prevent double adjustment
and stale overwrites. Six logical fields and selected-intent phases are restored
to Supervision. Native arithmetic and clamps are not physical safety limits.
Plan parity is not full VI parity
(including the documented additional 150 ms `cooling.stop` wait).
Production activation requires resolution of the 13 material
LabVIEW/Pyconlyse label conflicts, terminal polarity, interlock authority,
readback criteria, and failure recovery.

Two additional named lifecycle commands now reuse that same procedure lane:
`acq.initialize` and `acq.stop`. Initializer/resource/pilot/loop returns are
explicit synthetic stubs; original startup constants and seven controlled-stop
phases are checked against the recovered source facets by the package builder.
This is not a real acquisition scheduler, native initializer/error-handler
emulation, or physical safe-stop implementation. Existing sessions stay
UNMANAGED until an explicit initialization. Managed cycles exclude arrows during
transitions, reject repeated startup, retain phase/state/error across reload,
and retain UNKNOWN without replay after mid-cycle loss. Individual simulated
stop failures do not prevent remaining cleanup attempts, but they prevent a
successful STOPPED claim. General stop remains distinct from event6 shutdown;
native cleanup does not imply output zeroing or clearing all NI tasks.

Local qualification runs on Everest: the original Python 3.4 agent binds
`127.0.0.1:8765`; a separate, loopback-only development web backend serves
`http://127.0.0.1:5059/elyse`. This harness neither restarts the lab web service
on port 5000 nor accesses `10.20.30.10` or physical device routes.
