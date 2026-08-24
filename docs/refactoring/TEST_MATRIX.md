# Refactoring Test Matrix

Every work package runs focused checks before full checks. Hardware remains off unless the user separately approves a manual test.

## Static checks

```bash
conda run -n pyconlyse39 python -m compileall DeviceServers gui/controllers/openers utilities/dataio web/backend scripts/refactor tests
conda run -n pyconlyse39 ruff check --select F <changed-python-files>
git diff --check
git diff --cached --check
```

Frontend:

```bash
cd web/frontend
npm ci --legacy-peer-deps
npm test -- --watchAll=false
npm run build
```

## DeviceServer checks

| Area | Required checks |
|---|---|
| Import/startup | Import module; construct device with fake transport; verify no hardware connection at import time |
| Tango contract | Device names, commands, attributes, properties, types, and state mapping |
| Transport | Timeout, reconnect backoff, connection reset, malformed response, cancellation |
| Lifecycle | Init, start, stop, restart, repeated stop, dependency unavailable |
| Motion | Limits, readback, cancel, stop, simulated movement, no implicit movement on polling |
| Acquisition | Busy/idle transitions, stale buffer, save failure, RemoteEx disconnect |
| Safety | No power, motor, shutter, HPD-TA, or deployment side effects in tests |

## Backend checks

| Area | Required checks |
|---|---|
| Device API | Snapshot caching, stale data, refresh, server control errors |
| Contracts | Existing route methods, payloads, status codes, and error envelopes |
| Treatment | File discovery, ZIP/H5/HIS handling, current and legacy DAT orientation, OD calculation, selectors, export |
| Pump-probe | Emulator acquisition, delay sequence, background/reference/signal grouping, persistence |
| Concurrency | Duplicate polling prevention, cancellation, timeout, bounded worker count |
| Paths | Local path, remote SMB path, missing folder, permission error |
| Web security | Production env validation; Werkzeug scrypt/pbkdf2 user hashes; secure device/auth cookies; CSRF header/cookie pairing; same-origin CORS and explicit allowlist; explicit local-dev opt-outs |
| WebSocket security | Access-cookie decode/authentication; command authorization; per-SID subscriptions; last-subscriber cleanup; lock/timeout behavior |
| T10 startup/auth | 32-byte UTF-8 JWT secret; bind preflight before snapshot monitor; no process termination; bounded login rate limits; 429/`Retry-After`; mutation auth for device/treatment/VD2/V0; passive debug-monitor GET and authenticated monitor-start POST |

T10 backend coverage measurements and floors:

| Module | Measured | Floor |
|---|---:|---:|
| `web/backend/app.py` | 55.0% | 50.0% |
| `web/backend/auth.py` | 87.0% | 80.0% |
| `web/backend/mutation_auth.py` | 100.0% | 90.0% |
| `web/start_production.py` | 58.7% | 50.0% |

## Frontend checks

| Area | Required checks |
|---|---|
| Dashboard | Snapshot visible during refresh, error persistence, retry, server state update |
| V0 | Start/stop, emulator, delay selector, heatmap selectors, kinetics/spectrum, files |
| VD2 | Connect/disconnect, RemoteEx status, HPD-TA state, live/freeze, LUT, ROI |
| Hardware | Manual-gate disabled states, clear errors, copy and dismiss controls |
| Polling | Timer cleanup, no duplicate requests, no updates after unmount |

## Full verification gate

1. Focused tests pass.
2. `python scripts/refactor/verify_refactor.py --apply --full` passes.
3. Frontend tests and build pass.
4. `git diff --check` passes.
5. `git diff --cached --check` passes.
6. Sol completes read-only contract, safety, and integration review.
7. User explicitly approves any Everest or Elysium 2 deployment or restart.
8. Everest runs the exact SHA in a detached temporary worktree with the same
   complete software-only pytest suite and frontend production build before
   its production checkout fast-forwards.
9. Any Tango restart has a human-created, external, exact-SHA approval TOML.
10. Device-server changes are deployed to Elysium 2 (`ssh elysium2`,
    `C:\dev\pyconlyse`) at the exact reviewed SHA.
11. Only affected Elysium 2 server instances restart, sequentially. For each
    instance, capture pre/post Tango state, startup logs, API or GUI
    connectivity, and a bounded stability observation.
12. Elysium 2 deployment is blocked when its checkout is dirty, cannot
    fast-forward, or contains an unreviewed commit range.

## Software-only collection and coverage

Default collection is the automated lane. The following paths are preserved as
explicit, opt-in lanes and are never selected by the full gate:

| Lane | Invocation | Reason |
|---|---|---|
| Manual probes | `python tests/manual/<probe>.py` | Operator-approved hardware, GUI, or timing diagnostics |
| Integration | `pytest -o addopts='' tests/integration` | Cross-component/runtime dependencies |
| Legacy | `pytest -o addopts='' tests/legacy` | Historical compatibility characterization |
| Main app / utilities | `pytest -o addopts='' tests/main_app tests/utilities` | GUI or standalone scripts |

Host-data opener characterization is a narrower integration lane:

```bash
conda run -n pyconlyse39 python -m pytest -o addopts='' tests/integration/data
```

It may scan mounted experiment data and is intentionally excluded from the
software-only gate; failures remain visible when that lane is invoked.

Focused coverage command, run from repository root:

```bash
conda run -n pyconlyse39 python -m coverage erase
conda run -n pyconlyse39 python -m coverage run --rcfile=.coveragerc -m pytest --strict-config --deny-network
conda run -n pyconlyse39 python -m coverage report --rcfile=.coveragerc --fail-under=60
conda run -n pyconlyse39 python -m coverage json --rcfile=.coveragerc -o .coverage-refactor.json
conda run -n pyconlyse39 python scripts/refactor/verify_coverage.py --json .coverage-refactor.json
```

T9 software-only focused checks:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_auth_security.py tests/web/test_websocket_handler_contracts.py
cd web/frontend && npm test -- --watchAll=false --runInBand
cd ../..
conda run -n pyconlyse39 python scripts/refactor/verify_refactor.py --apply --full
```

T12 shared data I/O focused checks:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/unit/test_dataio_boundary.py \
  tests/unit/test_openers_orientation.py \
  tests/unit/test_treatment_service.py \
  tests/unit/test_vd2_acquisition.py
```

Required cases: web treatment imports `utilities.dataio` without importing the
GUI opener namespace; legacy package and direct-submodule imports are identity
re-exports of the shared symbols; current and legacy DAT layouts return the
canonical `(wavelengths, timedelays)` data shape.

The full named-module coverage report enforces statement floors of 75%, 55%,
70%, 55%, and 75% for `utilities/dataio/__init__.py`, `ascii_opener.py`,
`h5_opener.py`, `hamamatsu_file_opener.py`, and `opener.py`, respectively. A
new shared reader without an explicit floor fails the gate.

T10 software-only focused checks:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_auth_security.py \
  tests/web/test_login_rate_limit.py \
  tests/web/test_production_startup_security.py \
  tests/web/test_production_mutation_auth.py
```

T10 does not modify protected V0 frontend files. CSRF coverage for
treatmentClient, VD2, and shared V0 helpers is provided by the focused frontend
suites below.
T10 focused frontend checks:

```bash
cd web/frontend
npm test -- --watchAll=false --runInBand \
  src/api/treatmentClient.test.js \
  src/PumpProbeVD2.test.js \
  src/pump-probe-v0/shared.test.js
cd ../..
```

## Package A frontend approval transport

Focused Jest command covering hardwareApprovalRequest, treatmentClient, shared
V0, PumpProbeVD2, HardwareApprovalControl, and standalone transport: 6
suites/70 tests passed. Current full Python deny-network gate: tooling 38
passed; Python 581 passed, 1 skipped; frontend 10 suites/83 tests; frontend
coverage 96.66% statements, 90.08% branches, 97.87% functions, and 96.61%
lines. Production build passed with existing hook/bundle warnings. Coverage
verifies exact lowercase 64-hex input,
CSRF-plus-approval composition, caller-header stripping, one-shot consumption
before successful, rejected, or thrown same-origin unsafe fetch attempts,
non-consumption for safe/cross-origin requests, no nonce generation, and
visible consumed status. Login POST is intentionally excluded. Shared V0
helper flows are covered; direct server/data mutations in protected
`web/frontend/src/PumpProbeV0.js` remain a blocker.

Executed test scope includes the public transport, standalone tests, Flask-served
camera/PSU/PDU/OWIS pages, and VD2 tests. It checks passive VD2 refresh loaders
versus explicit Refresh Status POST, same-turn bulk-map rejection before any fetch,
protected V0 Promise.all/direct fetch limitations, and separate future
WebSocket `approval_nonce` transport. Measured frontend collect coverage remains
restricted to `src/api/csrfRequest.js`, `src/api/treatmentClient.js`, and
`src/utils/deviceFamily.js`.

T11 additionally requires roles, strict device/command/args allowlists, and
one-shot approval bound to user/action/device/args/expiry; JWT alone is
insufficient. Protected `PumpProbeV0.js` remains untouched and cannot attach
approval nonces, so its production UI workflows stay blocked.

Production blocker: Socket.IO threading mode is selected and pinned, but a
supported server/runtime must still be selected and load-validated for Windows.

## T11 hardware authorization

Focused software-only commands:

```bash
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  conda run --no-capture-output -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_hardware_authorization.py \
  tests/web/test_hardware_authorization_routes.py \
  tests/web/test_hardware_authorization_websocket.py \
  tests/web/test_hardware_authorization_device_mutations.py \
  tests/web/test_hardware_authorization_vd2.py \
  tests/web/test_routes_import_safety.py \
  tests/unit/test_pytest_module_isolation.py
```

Coverage command (named modules only):

```bash
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  conda run --no-capture-output -n pyconlyse39 python -m coverage erase
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  conda run --no-capture-output -n pyconlyse39 python -m coverage run --branch --rcfile=.coveragerc -m pytest --strict-config --deny-network <focused-tests>
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  conda run --no-capture-output -n pyconlyse39 python -m coverage json --rcfile=.coveragerc -o .coverage-refactor.json
conda run -n pyconlyse39 python scripts/refactor/verify_coverage.py --json .coverage-refactor.json
```

Required cases: server-derived subject/role; external policy and approval
directories; canonical args; strict unknown/duplicate/missing/non-finite and
wildcard rejection; exact-UTC timestamps and expiry; lowercase 256-bit nonce;
atomic one-shot consumption before proxy access; POSIX marker/directory fsync
and mocked Windows `CREATE_NEW`/write-through/flush failure paths;
401/403/428/409 semantics; route and ordered
target binding; WebSocket command authorization; V0 safe-read regression; and
production fail-closed configuration. No test may contact Tango or equipment.

Earlier T11 focused measurement: the listed suite collected and passed 159 tests in
both forward and reverse order, with one warning, under OS-level network
denial. Full named-module statement coverage was 68.0%;
`web/backend/hardware_authorization.py` measured 71.2% statements (380/534),
above its committed 60.0% floor. Dedicated focused branch coverage measured
65.4% for that module (379/534 covered lines; 143/264 branches). Full
`web/backend/device_api.py` statement coverage was 54.3%. The 49.3% total for
selected changed monoliths is informational and is not the gate baseline.

Current full Python deny-network evidence: tooling 38 passed; Python 581
passed, 1 skipped, 18 warnings; named-module coverage 68.4%; frontend 10
suites/83 tests with 96.66% statements, 90.08% branches,
97.87% functions, and 96.61% lines; production build passed with existing
hook/bundle warnings.

Fail-closed contract cases: enforced iTest increment/decrement derived-value
actions must return 403 without an exact ordered plan; iTest set remains
behind its existing gate. Enforced VD2 initialize/deinitialize and V0 Tango
run/realtime start must return 403 while their conditional/repeated plans are
not fully bound. Local opt-out compatibility is tested separately. UI and
policy migrations remain deployment blockers.

Rollback unit: verify an authorization failure or consumed approval occurs
before the first proxy/Tango call, and that rollback first disables hardware
mutation access or isolates the web service, preserves authorization evidence,
and confirms a hardware-safe service state through an operator-approved
process. A rollback must deploy only a previously secure release or replacement
authorization gate; it must never restore JWT-only mutation access. This test
matrix prescribes no equipment, Tango, PDU, motion, shutter, power, deploy, or
restart commands.

T11 route import isolation:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_routes_import_safety.py
```

The test installs a fake Tango module before import, clears host variables,
and verifies zero database/proxy calls. It separately verifies explicit
`PYCONLYSE_TANGO_HOST` mapping and lazy database construction only after an
explicit check. The full gate must run this audit and the Python network-denied
runtime lane; it may not use whole-tree legacy coverage as a release metric.

Baseline floors use statement coverage and apply only to named refactored
lifecycle and backend modules:

| Module | Baseline floor |
|---|---:|
| `DeviceServers/base/camera.py` | 75% |
| `DeviceServers/base/general.py` | 70% |
| `DeviceServers/base/motor.py` | 70% |
| `DeviceServers/motion/owis/DS_OWIS_delay_line.py` | 65% |
| `DeviceServers/cameras/avantes/DS_AVANTES_CCD.py` | 40% |
| `DeviceServers/cameras/basler/DS_Basler_camera.py` | 30% |
| `web/backend/device_api.py` | 40% |
| `web/backend/folder_api.py` | 75% |
| `web/backend/treatment_api.py` | 65% |
| `web/backend/treatment_file_cache.py` | 80% |
| `web/backend/treatment_network_path.py` | 55% |
| `web/backend/treatment_service.py` | 80% |
| `web/backend/vd2_measurement_protocol.py` | 80% |
| `web/backend/websocket_handler.py` | 45% |
| `web/backend/app.py` | 50.0% |
| `web/backend/auth.py` | 80.0% |
| `web/backend/mutation_auth.py` | 90.0% |
| `web/backend/hardware_authorization.py` | 60.0% |
| `web/start_production.py` | 50.0% |
| Combined focused modules | 60% |

Frontend Jest coverage is restricted to `src/api/csrfRequest.js`,
`src/api/treatmentClient.js`, and `src/utils/deviceFamily.js`. The full gate
requires 90% statements, 75% branches, 90% functions, and 90% lines across
those named modules.

## Package B runtime and reproducibility

Focused evidence: 31 tests passed; `poetry check --lock`, dependency compile,
Ruff, and diff checks passed. Socket.IO threading mode is constant and uses
direct `simple-websocket==1.1.0`; direct development pins are `pytest==8.4.2`
and `coverage==7.10.7`. The lock already contained simple-websocket; the
update adds direct pins, their transitive packages, coverage, pytest,
`iniconfig`, and resolver metadata without existing package-version upgrades.
Production deployment remains
blocked until a supported server/runtime is selected and load-validated for
the Windows target; the secured single-process Werkzeug launcher is not that
deployment. CI remains deferred pending reproducible native-dependency
bootstrap and OS-equivalent network denial.

## Failure policy

Any public-contract change, unexplained test regression, import cycle, unsafe side effect, or uncontrolled timeout blocks the package. Revert only the package commit; preserve unrelated dirty V0 work.
