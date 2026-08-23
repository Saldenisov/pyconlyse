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
  and V0 APIs, plus device debug-monitor GET, in production and when local
  enforcement is explicitly enabled.
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

- WebSocket command allowlist and role/RBAC policy.
- CI workflow and adding pytest/coverage/eventlet to locked project dependencies.
- Production server mode remains blocked: `websocket_handler.py` forces
  `async_mode='threading'`, `start_production.py` claims eventlet, and eventlet
  is not a direct dependency. Select, pin, and test one mode before deployment.
- Cross-process login throttling, restart persistence, NAT aggregation policy,
  and trusted-proxy client-IP handling. Current limiter is single-process and
  uses `request.remote_addr`; multiple workers/restarts reset state and NAT can
  aggregate clients.

### T11: First-tomorrow hardware mutation gate

Before deployment, add roles plus strict device, command, and argument
allowlists, and require one-shot human approval bound to user, action, device,
arguments, and expiry. JWT authentication alone is insufficient for hardware
mutations. Eventlet/threading mode mismatch remains a separate blocker.

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

## Sol review packages

### R1: Contract review

Read-only review of Tango names, commands, attributes, HTTP routes, payloads, and config compatibility.

### R2: Safety review

Read-only review that no code path powers hardware, moves motors, opens shutters, starts HPD-TA, or deploys without a manual gate.

### R3: Integration review

Read-only review of import cycles, test coverage, packaging, Windows wrappers, Everest readiness, and rollback.

## Handoff format

Every agent returns changed paths, tests run, contract changes, risks, and recommended rollback commit. A package is incomplete until Sol reviews it.
