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

## Failure policy

Any public-contract change, unexplained test regression, import cycle, unsafe side effect, or uncontrolled timeout blocks the package. Revert only the package commit; preserve unrelated dirty V0 work.
