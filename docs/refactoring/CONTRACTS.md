# Public Contracts

Refactoring must preserve these contracts unless a separately approved migration is created.

## Tango

- Device names and exported server names remain unchanged.
- Command names, argument types, return types, attributes, properties, and polling behavior remain compatible.
- `ON`, `OFF`, `FAULT`, `UNKNOWN`, and `INIT` semantics must not be repurposed silently.
- Connection failures must be represented as bounded, diagnosable errors, not endless reconnect loops.
- Hardware commands require explicit readback where the device supports it.

## Hardware safety

- Status reads and dashboard polling must not power devices, move motors, open shutters, start HPD-TA, or start RemoteEx.
- Initialization may validate configuration and connectivity only until a human approves hardware action.
- Stop, close, and power-off operations must be idempotent.
- Timeouts and cancellation must leave hardware in a known safe state or report that state as unknown.

## RemoteEx and acquisition

- TCP command framing, response parsing, timeout, reconnect, and busy/idle behavior must remain explicit.
- Long acquisition and file-save operations must not block unrelated status reads indefinitely.
- Buffer reads must declare ownership, freshness, and completion state.
- RemoteEx disconnects must not be reported as Tango server shutdown.

## HTTP backend

- Existing route paths and methods remain unchanged during extraction.
- Existing JSON keys, value types, error envelopes, and status codes remain unchanged.
- Snapshot/cache behavior must remain observable and bounded by a documented TTL.
- Server-control actions require explicit user invocation and must return operation status.

## Frontend

- Existing user workflows remain available: refresh, connect/disconnect, start/stop, hardware refresh, files, selectors, live data, and error copying.
- Polling must be cancellable and must not create duplicate timers after navigation or refresh.
- Last known snapshot may remain visible while a refresh is pending, with age and error state distinguishable.
- Persistent error messages must remain copyable and dismissible.

## Configuration and deployment

- Configuration is validated before use and has one documented source of truth per device.
- No dynamic code execution is allowed for configuration.
- Windows `.exe`/wrapper entrypoints and Astor metadata are compatibility surfaces.
- Deployment and service restart are manual-gated operations, never agent defaults.
- Elysium 2 is the mandatory runtime target for device-server changes:
  SSH alias `elysium2`, host `10.20.30.204`, repository
  `C:\dev\pyconlyse`, environment `pyconlyse39`.
- A device-server change is not complete after local source and unit checks.
  The exact reviewed commit must be deployed to Elysium 2, followed by
  sequential restart of only the affected server instances.
- Elysium 2 validation must inspect restart logs, Tango state/status and
  command/attribute access through the applicable API or GUI. Servers must
  remain stable during a bounded post-restart observation period.
- Deployment must stop if the remote worktree is dirty, the branch cannot be
  fast-forwarded to the exact commit, the affected server set is ambiguous,
  or hardware-safe restart approval is missing.

## Software-only test gate

- Default pytest collection contains automated software tests only.
  `tests/manual`, `tests/integration`, `tests/legacy`, `tests/main_app`, and
  `tests/utilities` are preserved but excluded from the default lane.
- Tango and Taurus doubles are process-local to one collected test module or
  one test. A test may not leave fake protocol modules in `sys.modules` for a
  later file.
- The full gate may import production code and use fakes, but may not create a
  Tango server, contact a Tango database, connect to equipment, or issue
  motion, shutter, power, PDU, or RemoteEx commands.
- Coverage gates measure named refactored modules and enforce their committed
  baselines. Whole-tree legacy coverage is informational only.
