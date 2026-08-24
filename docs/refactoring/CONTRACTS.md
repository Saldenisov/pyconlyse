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
- Enforced fallback routes must bind the exact `command_variant` to policy and
  approval; changing command selection requires policy migration. Parameter
  batch writes bind the complete deterministic ordered write plan.
- Restart is never an implicit `HardKillServer` action. Server control must
  bind its explicit action and trusted Starter target.

### Web security and WebSocket

- Production startup requires non-empty `JWT_SECRET_KEY` and
  `PYCONLYSE_AUTH_USERS`; the latter is JSON mapping usernames to Werkzeug
  `scrypt` or `pbkdf2` password hashes. Plaintext passwords are invalid.
- Production startup sets `PYCONLYSE_PRODUCTION=true` and mandates
  `PYCONLYSE_ENFORCE_DEVICE_AUTH=true`, `PYCONLYSE_JWT_COOKIE_SECURE=true`,
  and `PYCONLYSE_JWT_COOKIE_CSRF_PROTECT=true`.
- Device authentication, secure cookies, and CSRF protection are mandatory in
  production. Same-origin CORS is the default; cross-origin access requires an
  explicit configured allowlist.
- The authenticated production browser UI is same-origin. An explicit CORS
  allowlist alone does not make cookie-plus-CSRF authentication valid
  cross-origin; any cross-origin deployment requires a separately reviewed
  authentication design.
- Local development may disable authentication, secure-cookie, and CSRF checks
  only when the local launcher explicitly sets the applicable enforcement
  variables to `false`; those settings are not production defaults.
- Production `JWT_SECRET_KEY` must contain at least 32 UTF-8 bytes. Startup must
  reject an occupied, invalid, or unbindable `PYCONLYSE_WEB_HOST` /
  `PYCONLYSE_WEB_PORT` before starting the device snapshot monitor; it must not
  terminate an existing process to claim the port.
- Login throttling defaults to 5 failures per 900 seconds and 10,000
  process-local IP keys. Limits are configured by
  `PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS`,
  `PYCONLYSE_LOGIN_RATE_LIMIT_WINDOW_SECONDS`, and
  `PYCONLYSE_LOGIN_RATE_LIMIT_MAX_KEYS`; exhausted limits return HTTP 429 and
  `Retry-After`. State is single-process, resets on restart, may aggregate
  clients behind NAT, and trusts `request.remote_addr` unless a reviewed proxy
  policy is added.
- In production, and with explicit local opt-in, every non-safe method in the
  device, treatment, VD2, and V0 APIs requires JWT authentication. Device
  debug-monitor GET is passive; the explicit monitor-start POST requires
  mutation authentication.
- `treatmentClient`, VD2 callers, and shared V0 helpers attach CSRF headers to
  mutation requests. Protected V0 frontend files are not modified by this
  package.
- Treatment mutations intentionally use CSRF-only transport and preserve any
  armed hardware nonce for the next eligible mutation.
- Universal frontend hardware approval is operator-driven: only an exact
  lowercase 64-hex nonce may be armed. Transport composes `X-CSRF-TOKEN` with
  `X-PYCONLYSE-HARDWARE-APPROVAL`, strips caller-supplied approval headers, and
  consumes the nonce before one same-origin unsafe fetch attempt, including
  rejected or synchronously thrown attempts. Safe/cross-origin requests do
  not attach or consume it. The browser never generates a nonce; armed,
  consumed, cleared, and invalid status is visible. Login POST intentionally
  excludes hardware approval.
- Wrapped clients cover cameras, DAQmx, dashboard, VD2, shared V0
  helpers, generic device control, iTest/DS iTest PSU, Netio PDU, Standa
  motors, Andor Newton, Andor spectrograph, and camera controls. Direct
  server/data mutation fetches in protected `web/frontend/src/PumpProbeV0.js`
  remain a deployment blocker.
- VD2 automatic, Refresh-button, and post-action refreshes use passive GET
  loaders; only explicit Read hardware uses Refresh Status POST.
  `CamerasClients` and shared-helper Promise.all fan-out fail closed before any
  fetch when a same-turn operation would reuse one nonce; stale approval is
  consumed, fresh approval works later, and requests never retry after dispatch
  ambiguity/failure. Protected `PumpProbeV0.js` raw direct mutations reach the
  backend without an approval header and rely on backend fail-closed rejection;
  they remain deploy-blocked.
  Future WebSocket `execute_command` requires a
  separate `approval_nonce` transport; the HTTP header does not apply.
- Shared V0 nonhardware POSTs to `/config`, `/hardware-config`,
  `/hardware/preflight`, `/faraday`, `/crystal/move`, `/reset`, `/run=false`,
  and `/realtime=false` are CSRF-only. Approval paths are `/hardware/initialize`,
  `/run=true`, `/realtime=true`, and stage/sample move/stop.
- Browser requests send `X-CSRF-TOKEN` from the separate, non-HttpOnly
  `csrf_access_token` cookie. Browser code never reads the HttpOnly access-token
  cookie.
- WebSocket connections authenticate by decoding the access-token cookie before
  accepting commands. Commands are authorized per authenticated client.
  Subscriptions are tracked per Socket.IO SID, including last-subscriber
  cleanup, with locking around shared subscription/device state.

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
- Coverage gates measure named refactored lifecycle/backend Python modules and
  pure frontend request/classification modules, then enforce committed
  baselines. Whole-tree legacy coverage is informational only.
- WebSocket commands use exact device/command/argument allowlists and
  authenticated per-client authorization. CI/dependency reproducibility
  remains deferred and requires a separate approved package.
- Production server mode is unresolved: `websocket_handler.py` forces
  `async_mode='threading'`, while the launcher claims eventlet and eventlet is
  not a direct dependency. Deployment is blocked until one mode is selected,
  pinned, and covered by software-only tests.
- Hardware mutations require roles, strict device/command/argument allowlists,
  and one-shot human approval bound to user, action, device, arguments, and
  expiry. JWT authentication alone is insufficient.

### T11 hardware authorization

- Policy is loaded only from a trusted external JSON path; policy and approval
  directories are outside the repository and require restrictive ACLs.
- JWT subject and role are server-derived. Authorization identifies explicit
  `route_id`, action, ordered targets, device, command, and canonicalized args.
- Canonical args reject unknown, duplicate, missing, wildcard, and non-finite
  values and are bounded by closed policy schemas. Approval timestamps use an
  exact UTC offset (`+00:00`/`Z`), expiry is UTC and
  may not exceed 300 seconds; nonce is exactly 256-bit lowercase hex.
- Policy and approval inputs are external read-only files. Service startup
  rejects repository-local paths, symlinks, and unsafe permissions; consumed
  markers use a separate service-writable directory. POSIX uses atomic `O_EXCL`
  creation followed by marker and parent-directory `fsync`. Windows uses atomic
  `CreateFileW(CREATE_NEW)` with write-through, `WriteFile`, and
  `FlushFileBuffers`; Windows has no portable parent-directory `fsync`
  equivalent. Both create the marker before any side effect and fail closed on
  every marker I/O error; policy/approval reads reject symlinks with
  `O_NOFOLLOW` where available.
- Starter control uses a trusted policy `starter_servers` mapping. The service
  never discovers or substitutes a Tango Starter target before approval.
- Approval is one-shot and consumed with an atomic `O_EXCL` marker before any
  proxy/Tango side effect. No approval-generation API or tool exists.
- HTTP semantics: 401 missing/invalid authentication, 403 policy denial, 428
  missing approval, 409 malformed, expired, mismatched, or replayed approval.
- Production configuration fails closed. Local opt-out remains valid only when
  explicitly configured. V0 safe reads remain compatible; protected V0 UI
  mutations remain deploy-blocked.
- V0 initialization and other active sequences return 403 under enforced auth
  without a valid policy role and one-shot approval. Background monitor and VD2
  preview reads remain passive and use only the read-frame command; active V0
  polling is limited to an approved sequence.
- Enforced iTest increment/decrement derived-value actions return 403 until an
  exact ordered plan is represented in policy and approval; iTest set remains
  behind the existing authorization gate.
- Enforced VD2 initialize/deinitialize return 403 because conditional
  recovery/PDU plans are not yet bound as exact approved plans. Enforced V0
  Tango run/realtime start returns 403 because repeated cycles and complete
  argument plans are not yet fully bound. Explicit local opt-out preserves
  legacy behavior. These UI and policy migrations remain deployment blockers;
  no high-level workflow is treated as authorized by implication.

### Web route import safety

- Importing `web/backend/routes.py` is offline: no Tango `Database`,
  `DeviceProxy`, remote/default `TANGO_HOST`, or network contact.
- Tango database lookup is lazy and occurs only from an explicit runtime check.
- Explicit `PYCONLYSE_TANGO_HOST` is preserved and mapped to `TANGO_HOST`;
  there is no implicit remote host default.
