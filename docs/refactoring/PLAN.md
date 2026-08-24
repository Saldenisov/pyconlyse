# PyConlyse Refactoring Plan

## Objective

Reduce production monoliths in `DeviceServers`, `web/backend`, and `web/frontend` while preserving Tango names, commands, attributes, HTTP routes, JSON payloads, experiment safety, and current V0 work.

This document is an execution plan, not permission to operate laboratory equipment.

## Non-negotiable safety rules

- Agents never power hardware.
- Agents never move motors or translation stages.
- Agents never open shutters or Faraday devices.
- Agents never start HPD-TA, RemoteEx, cameras, generators, or other acquisition hardware.
- Agents never deploy or restart Everest services autonomously.
- Any hardware action, remote restart, or deployment requires an explicit manual gate from the user after tests and review pass.
- Existing dirty V0 files remain protected: `web/frontend/src/PumpProbeV0.js`, `web/frontend/src/css/PumpProbeV0.css`, `web/frontend/src/pump-probe-v0/components.js`, and unrelated `tmp/` content.

## Operating model

`Sol` coordinates and reviews. `Terra` performs semantic refactoring and lifecycle work. `Luna` performs mechanical extraction only. `Sol` is read-only during review. Exactly one writing agent owns each file in each phase.

Each phase must produce:

1. Focused tests and static checks.
2. A reviewable commit.
3. A contract and rollback note.
4. A manual approval request before any remote or hardware action.

## Phases

### Phase 0: Baseline and contracts

- Inventory imports, duplicate legacy trees, generated files, wrappers, and configuration sources.
- Record current Tango and HTTP contracts in `CONTRACTS.md`.
- Add characterization tests without changing behavior.
- Establish test commands and expected failures in `TEST_MATRIX.md`.
- Freeze dirty V0 files from unrelated work.

### Phase 0.5: Software-only test gate

Owner: Terra, with Sol read-only review.

- **T8a — test isolation:** restore `sys.modules` after every test-module
  import; Tango/Taurus stubs are local to collection or one test only.
- **T8b — collection hygiene:** default pytest collection contains only
  automated software tests. Manual probes, legacy, integration, main-app, and
  utilities remain preserved in explicit lanes.
- **T8c — focused coverage:** measure named refactored DeviceServer lifecycle
  and backend modules plus pure frontend API/classification modules, enforce
  explicit floors, and do not use whole-tree legacy coverage as a release
  metric.
- **T8d — lifecycle contracts:** verify software-only init, polling, stop,
  timeout, and readback behavior without Tango server control or hardware I/O.
- **T9 — conservative web security/WebSocket contracts:** require production
  JWT and Werkzeug scrypt/pbkdf2-hashed users; enforce secure device auth,
  cookies, CSRF, same-origin CORS (or explicit allowlist), and authenticated
  WebSocket commands/subscriptions with per-SID locking. Local development may
  opt out only explicitly. Browser code never reads the HttpOnly access cookie.

### Phase 1: DeviceServer stability foundation

Owner: Terra.

- Split shared lifecycle, state, configuration, error, archive, health, and retry concerns from `DeviceServers/base`.
- Replace unsafe dynamic configuration evaluation with validated JSON/config loading.
- Define independent server, transport, hardware, and operation states.
- Standardize bounded timeouts, backoff, reconnect, cancellation, and structured errors.
- Ensure polling cannot implicitly power equipment or start motion.

### Phase 2: DeviceServer extraction

One device family per commit, with Luna handling mechanical moves and Terra reviewing behavior:

1. OWIS motion and aggregator.
2. Hamamatsu RemoteEx transport and Tango adapter.
3. Andor CCD/spectrograph.
4. DG645 and DAQmx.
5. Archive and remaining camera/power servers.

Target structure per server:

```text
device_family/
  config.py
  driver.py
  controller.py
  tango_device.py
  registration.py
```

### Phase 3: Backend boundaries

- Split `device_api.py` into discovery/snapshots, Astor control, PDU, cameras, spectrographs, DAQmx, and generic device services.
- Split treatment routes from file access, cache, conversion, OD calculation, selection, and export.
- Split V0/VD2 acquisition orchestration from Flask route handlers.
- Preserve route paths and payloads until an explicit versioned migration exists.

### Phase 4: Frontend boundaries

- Split `TabsControl.js` by equipment and treatment capability.
- Split V0 and VD2 into API hooks, reducers/state machines, hardware controls, files, plots, selectors, and error presentation.
- Split Plotly/heatmap/kinetics adapters from view components.
- Keep current V0 dirty files excluded until their owner explicitly assigns them.

### Phase 5: Cleanup and deployment readiness

- Quarantine backups, generated registration scripts, vendor code, and duplicate legacy trees.
- Remove compatibility shims only after import and runtime usage scans pass.
- Build reproducible Windows wrappers and validate Astor metadata.
- Run local tests and Everest software-only smoke tests.
- Deploy or restart only after manual approval.

### Phase 5.5: T11 hardware mutation gate

- Add role-based, fail-closed authorization for every hardware mutation route
  and WebSocket command.
- Bind one-shot external approvals to server-derived user/role, route/action,
  ordered targets, device/command, canonical args, UTC expiry, and a unique
  lowercase 256-bit nonce.
- Consume approvals atomically before any proxy/Tango side effect. Keep policy,
  approvals, consumed markers, and ACLs outside the repository.
- Preserve explicit local auth opt-outs only; no approval-generation endpoint.
- Keep V0 safe reads covered and protected V0 UI mutations deploy-blocked.
- Treat eventlet/threading mismatch as an independent deployment blocker.
- Keep policy/approval JSON schemas closed and bounded; reject unknown,
  duplicate, wildcard, non-finite, and over-sized values. Policy and approval
  files are read-only service inputs; consumed markers are writable only by the
  service account; policy/approval reads reject symlinks with `O_NOFOLLOW`,
  while consumed markers use atomic `O_EXCL` plus file and parent-directory
  fsync.
- Verify collection under a network-denied sandbox and restore Tango/Taurus
  modules and environment between test modules.

## Completion criteria

- No production file remains a monolith solely for historical reasons.
- Public Tango and HTTP contracts are covered by tests.
- Hardware I/O has explicit timeout, cancellation, readback, and error mapping.
- No implicit power-up or motion occurs during polling or status refresh.
- Every phase has a commit, test record, reviewer result, and rollback point.
- `verify_refactor.py --apply --full` is a reproducible local software-only
  gate: collection, focused coverage, static checks, and frontend checks.
