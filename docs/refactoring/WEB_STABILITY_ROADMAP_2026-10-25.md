# PyConlyse Web Stability Refactoring Roadmap

Date: 2026-10-25  
Status: proposed future work; implementation and deployment not started  
Inspection baseline: local HEAD `31c899dc` plus existing uncommitted changes

## 1. Decision and scope

Refactor the existing web application incrementally into a modular monolith.
Preserve Flask/Socket.IO, React, HTTP contracts, Tango identities, scientific
data semantics, and hardware authorization while improving failure isolation,
resource bounds, recovery visibility, and reproducible deployment.

Stability means that a slow device, interrupted data conversion, failed network
share, or disconnected browser does not freeze unrelated pages, lose durable
work silently, or cause a hardware command to be replayed.

This roadmap supplements [PLAN.md](PLAN.md), [CONTRACTS.md](CONTRACTS.md),
[TEST_MATRIX.md](TEST_MATRIX.md), and [WORK_PACKAGES.md](WORK_PACKAGES.md).
Existing completed extractions should be retained, not reimplemented. Future
implementation packages must be assigned through the existing scope manifest;
this document does not grant ownership of protected or dirty files.

This review inspected local source and documentation only. No server, Tango,
hardware, active HDF5 file, or laboratory network was queried. No application
tests were run, so historical test counts are not a current passing baseline.
The acquisition monitor remains paused.

## 2. Evidence and limits

### Existing foundations to preserve

- `web/backend/tango_gateway.py` is an import-inert Tango construction boundary.
- `device_snapshot_service.py` and `device_catalog_service.py` already separate
  read-only discovery from parts of `device_api.py`.
- `acq_control_api.py` already persists a dispatch fence and explicitly forbids
  automatic retries of uncertain commands.
- `experiment_lifecycle.py` provides a separate lifecycle journal; treatment
  state and queue persistence already have repository boundaries.
- `useAcquisitionTelemetry.js` already implements latest-only polling with
  cancellation and timer cleanup. It is a useful model, not missing work.
- `tests/conftest.py` supports `--deny-network` before collection; software,
  manual, integration, and legacy lanes are separated in `pytest.ini`.
- Existing authorization, CSRF, audit, safe shutdown, and scientific-data tests
  provide regression contracts that must survive extraction.

### Current concentration of responsibilities

Physical source-line counts from this local working tree, including blank lines:

| File | Lines | Refactoring boundary |
| --- | ---: | --- |
| `web/backend/treatment_api.py` | 4,538 | HTTP, session/queue state, jobs, file conversion |
| `web/backend/device_api.py` | 3,609 | Discovery, proxy/cache ownership, multiple device families, commands |
| `web/backend/treatment_service.py` | 2,610 | Numerical processing, data loading, export |
| `web/backend/pump_probe_v0_api.py` | 2,622 | V0 routes and experiment orchestration |
| `web/backend/pump_probe_vd2_api.py` | 1,853 | VD2 routes and experiment orchestration |
| `web/frontend/src/TabsControl.js` | 3,544 | Treatment state, files, jobs, plots, persistence |
| `web/frontend/src/components/LaserPointingController.js` | 2,135 | Control state, requests, rendering |
| `web/frontend/src/PumpProbeV0.js` | 1,624 | V0 requests, lifecycle, data and views |
| `web/frontend/src/PumpProbeVD2.js` | 1,392 | VD2 state, protocol, preview and views |

File size identifies change concentration, not a demonstrated runtime defect.
The following source-level risks provide more specific priorities:

| Observation | Failure mechanism to test | Planned response |
| --- | --- | --- |
| `app.py` constructs the app, registers all blueprints and initializes Socket.IO at module scope; treatment stores are also constructed at import | Imports and startup couple otherwise independent subsystems; cleanup ownership is difficult to test | Explicit app factory and service lifecycle |
| Snapshot refresh has a per-key one-flight marker, but a cold `get_snapshot()` calls `collect()` directly; its monitor loops indefinitely without an exposed stop method | Concurrent cold reads may duplicate discovery; lifecycle changes may leave an unowned monitor | Characterize cold-start concurrency, bounded refresh and explicit shutdown |
| VD2 protocol polling uses a 1,200 ms interval without the request-active guard used by its state/preview polling | Slow responses can overlap and arrive out of order | Shared latest-only read lifecycle, deadline and generation checks |
| Compression and folder-set routes keep job status in module dictionaries and start daemon threads; CPU conversion already uses spawned process pools | Job status can disappear on web restart; concurrent submissions need an application-wide admission budget | Durable job metadata, bounded scheduling, explicit interrupted state |
| Socket.IO monitoring uses module-global registries and a thread per monitored device | Resource ownership and capacity depend on subscriptions and process count | Preserve existing per-SID locking and cleanup; add limits and lifecycle tests |
| Package scripts use `react-scripts`, while a separate Vite config points at `10.20.30.202:5001`; backend requirements differ from the Poetry dependency definition | Different launch paths can produce different builds or environments | Select and document one active build/dependency/launcher path |
| `web/PRODUCTION_DEPLOYMENT.md` explicitly records an unresolved Windows Socket.IO hosting blocker | Security configuration alone does not qualify the serving topology | Separate hosting decision and software-only load qualification |

These are observations and testable risk hypotheses, not a claim that every
listed mechanism has caused a production incident.

The 2026-10-23 acquisition observations included NI initialization timeout,
uncertain retained ownership, and changing LabVIEW/Python sources. Their exact
native root cause was not established. Web refactoring can improve diagnosis and
containment; it cannot by itself prove that NI initialization or ownership
recovery has been repaired. Native-driver investigation is a separate workstream.

## 3. Non-negotiable boundaries

1. No hardware power, motion, shutter, timing, initialization, cleanup, or service
   restart is authorized by this plan. Deployment and live verification require
   a separate explicit operator gate.
2. Retain one authoritative hardware owner and all existing uncertain-outcome
   fences. Browser cancellation means stop waiting, not proof of hardware stop.
3. Never automatically retry a hardware mutation after timeout, reconnect,
   reload, or process restart. Reconciliation is read-only unless a new exact
   operator-approved action is admitted.
4. Keep transport health, data freshness, acquisition state, command outcome,
   and physical acknowledgement separate. Fresh LabVIEW data is not evidence
   of a successful Python acquisition run.
5. Preserve original alarm causes, timestamps, source identity and quality.
   Missing data is UNKNOWN/STALE, not normal, zero, OFF, or proof of water loss.
6. Preserve current JWT/CSRF, exact-target hardware approval, audit and shared
   resource protections. A refactor must not silently broaden a command policy.
7. Preserve data orientation, units, calibration precision, lineage and atomic
   export behavior. Use synthetic or closed copied fixtures, never active files.
8. Do not combine framework migration, dependency upgrades, numerical changes,
   and hardware policy changes with structural extraction commits.

## 4. Target boundaries

Retain current import paths as compatibility facades while moving internals:

```text
React feature pages
  -> shared read clients / polling / source-aware state
  -> explicit operator command clients

Flask route adapters
  -> domain services: devices, acquisition, preparation, treatment
  -> repositories: sessions, jobs, command receipts, audit
  -> adapters: Tango gateway, file/SMB access, numerical workers

App-owned runtime
  -> start/stop hooks, bounded scheduling, subscription ownership, diagnostics
```

Reads and commands remain different interfaces. A generic retry wrapper must
never turn a command into an automatically retried read. Numerical workers may
process data; they must not acquire ownership of laboratory hardware.

Do not add multiple web workers before process-local command locks, lifecycle
ownership, subscriptions and job state have been audited. A modular monolith
does not require microservices or distributed coordination immediately.

## 5. Ordered work packages

Effort estimates are provisional engineering days for one implementation owner,
including focused tests and review. They exclude hardware debugging, operator
availability and live deployment windows. Re-estimate after W0.

| Package | Priority | Effort | Main deliverable | Acceptance gate |
| --- | --- | ---: | --- | --- |
| W0 — freeze contracts and reproduce the environment | P0 | 2–3 days | Baseline inventory, test results, dependency/launcher decision, failure fixtures | Existing failures recorded; clean isolated build reproducible; no laboratory I/O |
| W1 — application lifecycle and failure visibility | P0 | 3–4 days | App factory, explicit service ownership, passive health, structured diagnostics | Offline boot works; repeated create/close leaks no workers; dependency failure stays localized |
| W2 — read/polling and subscription reliability | P0 | 3–4 days | Shared read client/hooks, bounded snapshots, cancellation and subscription budgets | No overlapping same-resource polls; late generations discarded; resources released on unmount/disconnect |
| W3 — durable background work and command reconciliation | P0 | 4–6 days | Durable treatment job metadata, bounded admission, explicit interruption; retained command fences | Restart loses no admitted job identity and replays no hardware action; overload is explicit |
| W4 — backend domain extraction | P1 | 4–6 days | Thin HTTP adapters over existing device/treatment/experiment services | Route/payload/auth parity; injected failure remains within its domain |
| W5 — frontend feature extraction | P1 | 4–6 days | Small page shells, domain state/hooks, isolated plots/files/controls | Reload and navigation preserve intended state without replay; render failure is contained |
| W6 — release and endurance qualification | P0 release gate | 2–3 days plus soak | Automated software gate, candidate release, rollback and hosting evidence | Fault matrix and 24-hour synthetic soak pass; operator approves any deployment separately |

Total planning range: 22–32 engineering days, approximately 5–7 working weeks
at full allocation. Packages can be released incrementally. This is an effort
range, not a calendar commitment or a guarantee that native acquisition is fixed.

### W0 — establish the baseline

- Identify owners of existing dirty files. Record exact source/build hashes and
  preserve current work before an implementation branch is started.
- Record HTTP paths, payloads, status codes, authentication, error presentation,
  source/freshness semantics and command receipts for the main workflows.
- Run the existing software-only gate in an isolated checkout/environment with
  synthetic fixtures. Record actual results, including failures and skips.
- Resolve Python 3.12 versus the verifier's historical `pyconlyse39` default;
  do not substitute environments silently.
- Treat Poetry plus its lock and the frontend lockfile as candidate canonical
  inputs. Classify the alternate requirements/Vite/launcher files as active,
  compatibility-only, or obsolete before changing them.
- Build replay fixtures for stale telemetry, source/session change, failed
  dependency, uncertain command, locked SQLite, interrupted job and lost SMB.

### W1 — own startup, shutdown and diagnostics

- Introduce `create_app(config, services)` while preserving `app`/`socketio`
  compatibility imports and HTTP behavior.
- Move repository construction and worker startup out of module import.
  Explicitly track which application owns each resource.
- Add cooperative stop events and bounded joins for software monitors. Cleanup
  must not call hardware stop, power-off, task-clear, or initialization.
- Separate process liveness from dependency readiness and data quality. A live
  health check must not initiate Tango discovery or native operations.
- Add request, session, job and command correlation IDs; expose backend build,
  frontend build and acquisition-agent identity separately. Record diagnostic
  capture age so cached stacks cannot be presented as live evidence.
- Keep secrets and large scientific arrays out of logs. Bound log retention and
  retain the existing mutation audit semantics.

### W2 — make read traffic bounded

- Reuse the existing latest-only acquisition pattern across VD2, V0, dashboard
  and device clients without changing acquisition timing or operator intent.
- Standardize read deadlines, cancellation, credentials, error parsing and
  last-good-data presentation. Preserve timestamps while showing stale data.
- Discard responses from obsolete source/session/generation identities. Define
  handling of revision/sequence reset explicitly.
- Characterize snapshot cold misses, manual refresh and background refresh
  together; prevent duplicate collection for the same key.
- Introduce finite proxy/cache retention, subscription and refresh concurrency
  limits where measurements show a need. Report saturation rather than hiding it.
- Keep device reads read-only. Retry/backoff is permitted only for classified
  safe reads; reconnect must not replay any hardware action.

### W3 — survive interruption without inventing success

- Preserve existing lifecycle, command receipt and treatment repositories.
  Extend missing job metadata persistence instead of replacing all journals.
- Move compression/folder-set metadata behind a job repository with session
  ownership, progress, result/error, retention and schema migration rules.
- Add application-wide admission and CPU/memory budgets around existing
  spawned numerical workers; per-job worker limits alone are not a global cap.
- Mark previously active work INTERRUPTED/UNKNOWN after restart unless durable
  evidence establishes completion. Resume pure computation only through an
  explicit validated checkpoint policy; never generalize this to hardware.
- Test duplicate submissions, queue-full rejection, locked/full storage, worker
  failure, cancellation and competing writes to the same output.
- Retain atomic output commit and existing lineage. Failure must leave a
  readable prior output or an identifiable incomplete temporary artifact.

### W4 — extract backend domains in small increments

1. Device reads/discovery/catalogs, retaining current service extractions.
2. Device-family command adapters, retaining exact authorization and lock order.
3. Treatment session/queue/job orchestration, then conversion/export adapters.
4. V0/VD2 orchestration only under dedicated assigned scopes and regression gates.

Routes parse/validate input, authorize, call one application operation, and map
the result. Domain services own transitions; repositories own persistence;
adapters own bounded external I/O. Keep numerical algorithms unchanged during
these moves. Avoid extracting new wrappers that retain all shared mutable globals.

### W5 — extract frontend behavior, not just JSX

- Migrate one feature at a time: VD2 polling, treatment job/session state,
  `TabsControl` file/processing/plot panels, then V0 and laser-pointing controls.
- Separate server observations, local display preferences, unsent drafts and
  command receipts. Do not persist live telemetry or executable commands as UI state.
- Use explicit reducers/state transitions for lifecycle and job states where
  multiple effects currently coordinate them.
- Add route/panel error boundaries, consistent asynchronous errors and bounded
  scientific plot history. Dispose plot resources when panels are removed.
- Add slow-response, rapid-navigation, double-click, reload, reconnect and
  multi-tab tests. Retain all numerical and calibration rendering contracts.
- Consider route-level bundle splitting only after baseline measurements;
  framework replacement and broad TypeScript conversion are separate decisions.

### W6 — qualify releases separately from hardware

- Automate the existing verification commands on the chosen CI host and Windows
  qualification environment. Preserve network-denied software lanes.
- Publish reproducible frontend/backend artifacts with build identity and a
  compatibility record; avoid building directly into the live serving directory.
- Select a supported Windows-compatible Socket.IO serving topology using current
  official documentation and an offline load test. Do not remove the documented
  deployment blocker merely by changing a launcher label or worker count.
- Use explicit stop/start ownership for the web service only after operator
  approval. No web restart may imply a hardware restart or command replay.
- Define rollback for both artifacts and SQLite migrations. Restore a backup
  only after determining whether doing so would lose post-migration receipts.
  Never reset ownership or audit state as a convenience rollback.

## 6. Proposed acceptance targets

These are future qualification targets, not measured results. W0 must specify
the test machine, payload sizes and dependency simulator before they are frozen.

| Property | Proposed gate |
| --- | --- |
| Polling concurrency | At most one in-flight read per resource/session/poller; no catch-up burst |
| Mutation replay | Zero automatic command replays across timeout, reload, reconnect or web restart |
| Data honesty | Every stale/missing/source-switch fixture preserves source, age and original faults |
| Offline availability | App shell and passive liveness available without Tango/XP/SMB |
| Read isolation | Cached status p95 <= 250 ms with two browsers and 50 simulated devices, including one stalled dependency |
| Job isolation | Status/liveness remain responsive during a saturated synthetic treatment queue; excess jobs rejected explicitly |
| Worker cleanup | Subscriptions/timers/software workers return to baseline within their declared shutdown deadlines |
| Endurance | 24-hour synthetic run; no unexplained monotonic worker growth; post-warm-up memory growth <= 10% under fixed bounded data |
| Persistence | Admitted job/command identities remain queryable after injected process loss; incomplete outcomes stay explicit |
| Data correctness | Existing shape/unit/precision/lineage fixtures pass; floating-point tolerances remain explicit and unchanged |
| Release safety | Exact artifact identity, test record and rollback procedure attached to every candidate |

The Python socket guard is not an OS-level barrier for arbitrary native C
transports. Qualification must use injected adapters and absent native hardware
drivers; add OS-level denial when the test scenario requires stronger isolation.

## 7. Verification and change discipline

Each implementation increment must include characterization tests, focused
failure tests, a reviewable diff, contract impact, and a rollback note. Keep
mechanical moves separate from behavioral fixes. Do not use line-count targets
as a substitute for a demonstrated responsibility boundary.

Candidate software-only commands, after W0 confirms `pyconlyse312` exists and
matches the reviewed dependency lock:

```powershell
python scripts/refactor/verify_refactor.py --environment pyconlyse312 --full
# Inspect the dry run first; execute only in the isolated software test checkout:
python scripts/refactor/verify_refactor.py --environment pyconlyse312 --apply --full
git diff --check
```

The full verifier includes dependency installation, tests and a frontend build;
it is intentionally not run against the current live/dirty checkout for this plan.
It does not authorize deployment or laboratory operations.

## 8. First implementation slice

Start with W0, then one VD2 protocol polling characterization test: a response
slower than the 1,200 ms interval, followed by navigation and a late response.
The implementation slice should introduce bounded latest-only read behavior
without touching prepare/unprepare commands or hardware sequencing.

In parallel scheduling terms, lifecycle, job and domain extractions are separate
future packages, not permission to launch agents or edit overlapping files now.
Prioritize evidence from this first slice before expanding the refactor.
