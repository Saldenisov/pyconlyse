# Refactoring Test Matrix

Every work package runs focused checks before full checks. Hardware remains off unless the user separately approves a manual test.

## Static checks

```bash
conda run -n pyconlyse39 python -m compileall DeviceServers web/backend scripts/refactor tests
conda run -n pyconlyse39 ruff check DeviceServers web/backend scripts/refactor tests
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
| Treatment | File discovery, ZIP/H5/HIS handling, OD calculation, selectors, export |
| Pump-probe | Emulator acquisition, delay sequence, background/reference/signal grouping, persistence |
| Concurrency | Duplicate polling prevention, cancellation, timeout, bounded worker count |
| Paths | Local path, remote SMB path, missing folder, permission error |

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

Focused coverage command, run from repository root:

```bash
conda run -n pyconlyse39 python -m coverage erase
conda run -n pyconlyse39 python -m coverage run --rcfile=.coveragerc -m pytest --strict-config
conda run -n pyconlyse39 python -m coverage report --rcfile=.coveragerc --fail-under=60
conda run -n pyconlyse39 python -m coverage json --rcfile=.coveragerc -o .coverage-refactor.json
conda run -n pyconlyse39 python scripts/refactor/verify_coverage.py --json .coverage-refactor.json
```

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
| Combined focused modules | 60% |

Frontend Jest coverage is restricted to `src/api/treatmentClient.js` and
`src/utils/deviceFamily.js`. The full gate requires 90% statements, 75%
branches, 90% functions, and 90% lines across those named modules.

## Failure policy

Any public-contract change, unexplained test regression, import cycle, unsafe side effect, or uncontrolled timeout blocks the package. Revert only the package commit; preserve unrelated dirty V0 work.
