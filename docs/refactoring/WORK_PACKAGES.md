# Refactoring Work Packages

Only one agent may write a given file in a work package. Read-only agents may inspect any file. Packages may run in parallel only when file scopes do not overlap.

Machine-readable scopes live in `docs/refactoring/work-packages.toml`. The manifest is authoritative for allowed paths and protected V0 paths.

Each writing agent must use a separate worktree. Before committing, validate the complete worktree, including unstaged, staged, and untracked files:

```bash
conda run -n pyconlyse39 python scripts/refactor/validate_scope.py --package T3
```

Use `--package L1` for Luna packages. A protected or out-of-scope path returns exit code `1`; an invalid package or Git/manifest error returns `2`.

For unit tests, pass files directly with repeatable `--file` arguments. This bypasses Git discovery and keeps the validator testable without a repository:

```bash
python scripts/refactor/validate_scope.py --package L1 \
  --file DeviceServers/instruments/dg645/driver.py
```

## Terra semantic packages

### T1: Shared Tango foundation

Scope:

- `DeviceServers/base/general.py`
- `DeviceServers/base/camera.py`
- `DeviceServers/base/motor.py`
- related base tests

Deliver: state model, lifecycle boundaries, validated config, transport/error contracts, regression tests.

### T2: Motion safety

Scope:

- `DeviceServers/motion/owis/DS_OWIS_PS90.py`
- OWIS tests and directly required adapters

Deliver: command cancellation, limits, readback, timeout behavior, and stable Tango facade.

### T3: Hamamatsu transport

Scope:

- `DeviceServers/cameras/hamamatsu_streak/DS_HAMAMATSU_STREAK.py`
- `remoteex_client.py`
- `hamamatsu_streak_controller.py`

Deliver: bounded socket operations, reconnect policy, async acquisition state, and error mapping.

### T4: Backend device API

Scope:

- `web/backend/device_api.py`
- directly related backend tests

Deliver: services for discovery, snapshots, Astor, PDU, camera, spectrograph, DAQmx, and generic devices.

### T5: Treatment domain

Scope:

- `web/backend/treatment_api.py`
- `web/backend/treatment_service.py`
- `web/backend/pump_probe_vd2_api.py`

Deliver: route/domain separation, explicit session state, file/storage boundaries, and contract tests.

V0 backend remains protected until a dedicated V0 package is explicitly approved in the manifest.

### T6: V0/VD2 frontend behavior

Scope only after explicit assignment:

- `web/frontend/src/PumpProbeV0.js`
- `web/frontend/src/PumpProbeVD2.js`
- `web/frontend/src/TabsControl.js`

Current dirty V0 files are protected and must not be modified by an unrelated package.

### T8: Software-only verification gate

Scope:

- `pytest.ini`, `.coveragerc`, `tests/conftest.py`, `tests/manual/**`
- `scripts/refactor/verify_refactor.py`, `scripts/refactor/verify_coverage.py`
- gate, coverage, and isolation regression tests
- refactoring test documentation

Deliver: order-independent Tango/Taurus test doubles; explicit automated,
manual, integration, legacy, main-app, and utilities lanes; focused lifecycle,
backend, and pure frontend coverage floors; and an executable local `--full`
gate. This package does not operate Tango, hardware, PDU, motion, shutters, or
deploy tooling.

### T9: Conservative web security and WebSocket contracts

Scope:

- `web/backend/app.py`
- `web/backend/auth.py`
- `web/backend/websocket_handler.py`
- `web/backend/device_api.py`
- `web/start_production.py`
- `tests/web/test_auth_security.py`
- `tests/web/test_websocket_handler_contracts.py`
- `web/frontend/src/api/csrfRequest.js`
- `web/frontend/src/api/csrfRequest.test.js`
- `web/frontend/src/CamerasClients.js`
- `web/frontend/src/DAQmxClients.js`
- `web/frontend/src/Dashboard.js`
- `web/frontend/src/PumpProbeVD2.js`
- `scripts/refactor/verify_refactor.py`
- `tests/unit/test_refactor_tooling.py`
- non-protected frontend callers changed by the frontend owner and required to
  attach CSRF headers or establish authenticated WebSocket sessions
- this refactoring documentation and manifest entries

Deliver: production JWT and password-hash requirements; secure device auth,
cookies, and CSRF; same-origin CORS by default with an explicit allowlist;
explicit local-development auth/secure-cookie/CSRF opt-outs; browser CSRF
helper that reads only the non-HttpOnly `csrf_access_token` cookie and never
reads the HttpOnly access cookie; and authenticated WebSocket command,
subscription, per-SID last-subscriber, and locking contracts. Provisioning,
tests, and gate commands remain software-only; no hardware or deployment
actions are included.

### T10: Production startup and mutation authentication

Scope:

- `web/backend/app.py`
- `web/backend/auth.py`
- `web/backend/device_api.py`
- `web/backend/treatment_api.py`
- `web/backend/pump_probe_vd2_api.py`
- `web/backend/pump_probe_v0_api.py`
- `web/backend/mutation_auth.py`
- `web/start_production.py`
- `tests/web/test_auth_security.py`
- `tests/web/test_login_rate_limit.py`
- `tests/web/test_production_startup_security.py`
- `tests/web/test_production_mutation_auth.py`
- `web/frontend/src/api/treatmentClient.js`
- `web/frontend/src/api/treatmentClient.test.js`
- `web/frontend/src/PumpProbeVD2.js`
- `web/frontend/src/PumpProbeVD2.test.js`
- `web/frontend/src/pump-probe-v0/shared.js`
- `web/frontend/src/pump-probe-v0/shared.test.js`
- this refactoring documentation and manifest entries

Deliver:

- Production JWT secret validation: at least 32 UTF-8 bytes.
- Startup bind/port preflight before snapshot-monitor startup; occupied or
  invalid bind fails closed and never terminates unrelated processes.
- Login throttling defaults to 5 failures per 900 seconds, 10,000 process-local
  IP keys, HTTP 429, and `Retry-After`.
- Validate `PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS` (1–1000),
  `PYCONLYSE_LOGIN_RATE_LIMIT_WINDOW_SECONDS` (1–86400), and
  `PYCONLYSE_LOGIN_RATE_LIMIT_MAX_KEYS` (1–100000).
- Require authentication for every non-safe method in device, treatment, VD2,
  and V0 APIs in production and when local enforcement is explicitly enabled.
  Debug-monitor GET is passive; the explicit monitor-start POST is protected
  as a mutation.
- Preserve local-development auth opt-out when enforcement is explicitly
  disabled; production remains fail-closed.
- Ensure `treatmentClient`, VD2 callers, and shared V0 helpers attach CSRF
  headers. Protected V0 frontend files remain outside this package.
- Coverage measurement from 356 passed, 8 skipped software-only tests:

  | Module | Measured | Floor | Headroom |
  |---|---:|---:|---:|
  | `web/backend/app.py` | 55.0% | 50.0% | 5.0 pp |
  | `web/backend/auth.py` | 87.0% | 80.0% | 7.0 pp |
  | `web/backend/mutation_auth.py` | 100.0% | 90.0% | 10.0 pp |
  | `web/start_production.py` | 58.7% | 50.0% | 8.7 pp |

  T10 full gate/lane uses `.coveragerc`, `verify_coverage.py`, and the full
  software-only pytest lane; no hardware or deployment actions.

Deferred:

- CI workflow remains deferred pending reproducible native-dependency bootstrap
  and equivalent OS-level network denial. Socket.IO threading mode is selected
  and pinned; select and load-validate a supported server/runtime for Windows.
- Cross-process login throttling, restart persistence, NAT aggregation policy,
  and trusted-proxy client-IP handling. Current limiter is single-process and
  uses `request.remote_addr`; multiple workers/restarts reset state and NAT can
  aggregate clients.

### T11: First-tomorrow hardware mutation gate

Before deployment, add roles plus strict device, command, and argument
allowlists, and require one-shot human approval bound to user, action, device,
arguments, and expiry. JWT authentication alone is insufficient for hardware
mutations. Supported-server selection and Windows load validation remain
separate deployment blockers.

## Luna mechanical packages

### L1: DG645 extraction

Scope:

- `DeviceServers/instruments/dg645/DS_DG645.py`
- `DeviceServers/instruments/dg645/dg645_recall_configurator.py`
- `DeviceServers/instruments/dg645/add_ds_DG645.py`

Target modules: `driver.py`, `recall_config.py`, `tango_device.py`, `registration.py`.

### L2: DAQmx client/UI extraction

Scope:

- `DeviceServers/control/daqmx/DS_DAQmx_Widget.py`
- `DS_DAQmx_client.py`
- `DS_DAQmx_zmq.py`
- `DS_DAQmx_zmq_client.py`
- `DS_DAQmx_zmq_widget.py`

`DS_DAQmx.py` remains Terra-owned because it contains hardware behavior.

### L3: Treatment helpers

Scope:

- `web/backend/treatment_network_path.py`
- `web/backend/treatment_file_cache.py`
- `web/backend/folder_api.py`

Do not modify `treatment_api.py` or `treatment_service.py` in this package.

### L4: Existing web components

Scope only within:

- `web/frontend/src/components/`
- `web/frontend/src/tabs/`
- `web/frontend/src/utils/`

Do not touch current V0 files.

### T11: Hardware mutation authorization

Scope is limited to the paths listed in `work-packages.toml` under `[packages.T11]`.
The package adds a shared authorization gate and route/WebSocket integration.
It must use a trusted external JSON policy path, external approval and consumed
directories, server-derived JWT subject/role, explicit route ID/action/ordered
targets/device/command, normalized canonical arguments, UTC expiry, and a
256-bit lowercase hexadecimal nonce. Reject wildcards, duplicate/unknown/
missing fields, non-finite values, and values outside bounded closed schemas.
Approval lifetime is at most 300 seconds. Consume approvals atomically with
an `O_EXCL` marker before any proxy or Tango side effect; approval reads and
policy reads reject symlinks (`O_NOFOLLOW`). No approval-generation API or tool
is allowed.

Production validates configuration and fails closed. Existing explicit local
opt-outs remain available only when explicitly configured. Return semantics are
401 unauthenticated, 403 policy denial, 428 missing approval, and 409 invalid
or replayed approval. Approval and policy directories must be outside the
repository with restrictive ACLs. V0 safe-read behavior remains covered; the
protected V0 UI remains deploy-blocked. Supported-server selection and Windows
load validation remain separate deployment blockers.

T11 also owns the `routes.py` import-safety regression. Importing web routes
must not construct a Tango `Database`, create a `DeviceProxy`, set a remote
default `TANGO_HOST`, or contact a lab endpoint. Tango lookup is lazy and only
occurs after an explicit runtime check. An explicitly supplied
`PYCONLYSE_TANGO_HOST` remains mapped to `TANGO_HOST`.

T11 collection evidence: under OS-level network denial, the focused listed
suite collected and passed 159 tests in both forward and reverse order, with
one warning. Final full offline deny-network gate passed tooling 26; Python
551 passed, 8 skipped; frontend 10 suites/83 tests with 96.66% statements,
90.08% branches, 97.87% functions, and 96.61% lines. Manual probes, legacy, integration, main-app, and utilities stay
explicit opt-in lanes. T11 covers device mutation, VD2, WebSocket, import
safety, and module-isolation regressions. V0 initialization is rejected with
403 when enforcement is enabled unless an exact approval is supplied; the
protected V0 UI remains a deployment blocker because it cannot yet provide
that approval.

Enforced fallback routes must bind the exact selected `command_variant` to the
policy and one-shot approval; changing command selection requires policy
migration. Parameter-batch writes bind the complete deterministic ordered
write plan. Restart never implies `HardKillServer`; explicit restart action
and trusted Starter target are required. VD2 preview remains a passive
read-frame operation.

Fail-closed gaps remain explicit: enforced iTest increment/decrement
derived-value actions return 403 until exact ordered plans are represented;
iTest set remains behind its existing gate. Enforced VD2
initialize/deinitialize return 403 because conditional recovery/PDU plans are
not exact. Enforced V0 Tango run/realtime start returns 403 because repeated
cycles and complete argument plans are not fully bound. Local opt-out
preserves legacy behavior. UI and policy migrations are deployment blockers;
no high-level workflow is implicitly authorized.

T11 rollback contract: disable hardware mutation access or isolate the web
service before any release change, preserve authorization evidence, and use an
operator-approved process to confirm a hardware-safe service state. A rollback
must deploy only a previously secure release or replacement authorization
gate; it must never restore JWT-only mutation access. This package prescribes
no equipment, Tango, PDU, motion, shutter, power, deploy, or restart commands.

## Sol review packages

### Package B: Runtime and dependency reproducibility

Scope is limited to exact paths listed under `[packages.B]` in
`work-packages.toml`. It selects constant Socket.IO threading mode, pins
simple-websocket and direct development test/coverage dependencies, and
documents the controlled single-process Werkzeug launcher limitation. Official
threaded production guidance, Unix-only Gunicorn constraints, Windows server
selection, and load-validation blockers remain explicit. CI is deferred until
native/proprietary dependencies, conda assumptions, and equivalent OS network
denial are reproducibly bootstrapped.

### Package A: Universal frontend approval transport

Scope is limited to exact paths listed under `[packages.A]` in
`work-packages.toml`. It adds operator paste/arm UI and one-shot
`X-PYCONLYSE-HARDWARE-APPROVAL` transport composed with CSRF for same-origin
unsafe mutations. Input is exact lowercase 64-hex; approval is consumed before
the single fetch attempt, including reject/throw, and is never generated.
Safe/cross-origin requests do not consume it; caller headers are stripped and
status is visible. Login POST is excluded. Shared V0 helper flows are covered.
Treatment mutations use CSRF-only transport and preserve armed approval.
Hardware fan-out fails closed before fetch, consumes stale approval, and never
retries after dispatch ambiguity/failure; cameras bulk maps and protected V0
Promise.all therefore require one nonce per mutation or an exact-plan backend
batch. Shared V0 nonhardware POSTs are CSRF-only for `/config`,
`/hardware-config`, `/hardware/preflight`, `/faraday`, `/crystal/move`, `/reset`,
`/run=false`, and `/realtime=false`; approval covers initialize, true run/
realtime, and stage/sample move/stop.
Protected `PumpProbeV0.js` direct server/data mutation fetches remain outside
scope and block deployment.

Package A also covers public transport used by Flask-served pages and
standalone tests. VD2 automatic/button/post-action refresh is passive GET;
explicit Read hardware is the only Refresh Status POST. Same-turn bulk camera
maps reject before any fetch. Protected V0 raw direct fetches cannot attach an
approval header and rely on backend fail-closed rejection. Future
WebSocket `execute_command` needs separate `approval_nonce` transport.

### R1: Contract review

Read-only review of Tango names, commands, attributes, HTTP routes, payloads, and config compatibility.

### R2: Safety review

Read-only review that no code path powers hardware, moves motors, opens shutters, starts HPD-TA, or deploys without a manual gate.

### R3: Integration review

Read-only review of import cycles, test coverage, packaging, Windows wrappers, Everest readiness, and rollback.

## Handoff format

Every agent returns changed paths, tests run, contract changes, risks, and recommended rollback commit. A package is incomplete until Sol reviews it.
