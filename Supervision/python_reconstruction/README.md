# SuperVision Python reconstruction

This is an auditable reconstruction workspace, not an executable replacement for ELYSE SuperVision.

Current per-VI and semantic coverage is summarized in `RECONSTRUCTION_STATUS.md`.
The individual-VI understanding audit is
`../analysis/VI_UNDERSTANDING_AUDIT_r4.json`: 38 active application VIs,
one user-excluded protected error database, and 87 dependency contract boundaries.
Exclusion is not database implementation or qualification of dependent error paths.

Non-event models now include journal byte concatenation/append intent,
timed-monitoring snapshot projections, and cleanup/retired-formula inventory in
`domain.journal`, `domain.timed_monitoring`, and `domain.lifecycle_tail`.
Journal timestamps are supplied as already-rendered bytes; NI mean outputs are
supplied explicitly. Neither clocks, means, file writes nor resource release
are executed. The final `POUBELLE` frame's 15 zero-input/unconsumed formulas are
preserved as retired source text, not commissioned calibrations.

All 34 main Event Structure indices now have bounded pure Python models; this
does not mean 34 fully converted events or a complete application. See
`EVENT_MODEL_COVERAGE.json` and `../analysis/REMAINING_EVENT_TRANSFER.md` for
event-to-module links, original-source cross-checks and explicit runtime limits.
There are still zero independently verified complete VI replacements.

```powershell
$env:PYTHONPATH='src'
py -3.11 -m unittest tests.domain.test_remaining_event_logic tests.domain.test_video_load_events -v
py -3.11 tools/export_event_model_coverage.py
```

Each record in `src/supervision_reconstruction/catalog/catalog.json` identifies an exported LabVIEW VI section, records available LabVIEW/lvkit evidence, and links to one safe Python stub. A source SHA-256 is present only when copied or installed source resolution is unambiguous. Otherwise, `source_status` is `unresolved` and the identity is derived from hashed LabVIEW Print evidence. All stubs deliberately raise `NotImplementedError`; no generated code is accepted as an implementation until it has passed the documented cross-validation protocol.

`labview_hidden_frame_manifest.json` independently records all three authoritative LabVIEW HTML exports and their 1,305 PNG frames. Every HTML and PNG artifact has a SHA-256 and byte count; raster dimensions are recorded for PNG frames only. The catalog links each VI to its named exported sections. Some files named `.png` in the older GUI-screenshot set are JPEG bytes; the catalog reports the detected raster format rather than trusting the extension.

`application_scope` remains 39 records: the 38 root VIs extracted from `SUPERVISION.llb`, plus the directly called `Moteurs SdC GoTo.vi`. `dependency_scope` adds 87 code-bearing dependency VI sections printed in `root_and_dependencies_all_hidden.html` as black-box adapter/contract boundaries. The result is 126 fail-closed VI modules. Four `.ctl` sections and the diagramless `Global Variables.vi` are retained as five `non_vi_evidence` records without Python execution surfaces.

## Safety boundary

- No catalog stub invokes a VI, generated Python, driver, hardware, controller, or remote desktop session.
- Catalog stubs expose no hardware/control run path and raise `NotImplementedError`.
- Reviewed domain APIs are executable pure software functions; they do not invoke hardware/control adapters.
- `verified` is intentionally unused: no VI has both exhaustive visual coverage and independently tested, safe behavioral reconstruction.
- A `partial` record describes evidence progress, not deployable behavior. A `failed` record records a known lvkit mismatch/failure. An `open` record needs cross-validation.
- `Error Code Database.vi` remains `BLOCKED_VISUAL` in the preserved catalog and is excluded from current analysis at the user's request. Its behavior and dependent error paths remain unqualified.
- Each root VI preserves both `lvkit` contexts, `base` and `minimal_vilib`, with an explicit context-agreement or context-disagreement verdict. Neither verdict asserts behavioral correctness.
- Dependency boundaries are classified as `copied_vendor`, `labview_builtin`, or `unresolved_dependency`; none is an executable wrapper.

## Offline mixed-magnet registry

`domain.magnet_registry` models current ownership separately from archived VI
routing: eight candidate iTest bindings, 13 unresolved owners, and six excluded
former DAQmx assignments. No route is deployment-verified. All current-intent
plans are non-executable; candidate routes, unknown limits, revision mismatch,
and unavailable transport fail closed. Group planning retains per-equipment
results and never calls a server-wide magnet action.

The display export is shared with the static Alimentations view. Inspect it
without writing or contacting hardware:

```powershell
$env:PYTHONPATH = "src"
py -3.11 tools/export_magnet_registry.py
py -3.11 -m unittest tests.domain.test_magnet_registry -v
```

This is a target domain model, not evidence that another VI is fully converted.
See `../integration_analysis/MAGNET_CONTROL_OWNERSHIP.md` for remaining gates.

`domain.magnet_readback` adds independent measurement-source verification,
explicit acquisition/receive time and quality, ID-based sparse iTest array
selection, and an absolute-current comparison against a recorded post-dispatch
request. No hardware is read. Missing acquisition proof, cached/pre-command data,
stale/disconnected/invalid/simulated readings, or source/revision mismatch cannot
produce a physical-current match. Freshness and tolerance are caller-supplied;
there are no invented production defaults. Freshness is recalculated at each
comparison's explicit `now`; a cached projection cannot remain valid indefinitely.
Full command/stop success is never established by this current-only model.

```powershell
py -3.11 -m unittest tests.domain.test_magnet_readback -v
```

## Regenerate catalog

Do not regenerate the catalog merely to make the source-integrity test pass.
The current extracted `0_SUP_ELYSE.vi` differs from the source identity attached
to the archived evidence. Select and reconcile the authoritative source first;
otherwise fresh hashes would conceal the discrepancy rather than resolve it.

Run from this directory:

```powershell
py -3.11 tools/build_catalog.py
$env:PYTHONPATH = "src"
py -3.11 -m unittest discover -s tests\catalog
```

The generator only reads copied source and analysis artifacts. It refreshes source hashes, hidden-frame export hashes/dimensions, recursively parsed dependency/node inventories, both lvkit contexts, catalog JSON, and the one-stub-per-VI module set. The motor record also retains standalone motor SVG/generated-artifact evidence outside the root 38-VI batch.

## Acceptance rule

Before a stub may become executable, all relevant expanded LabVIEW diagrams/cases and connector panes must be captured, the same source hash must be parsed by lvkit, generated-code discrepancies must be resolved in favor of the LabVIEW graph where they differ, and software-only behavior tests must pass. Hardware behavior remains out of scope until separately authorized.

## Corrected parser and original-source recovery

The original library members have been recovered without replacing modified
working copies. The corrected lvkit checkout parses all 38 original roots plus
the original archived motor VI. It uses stored UID identities for locals,
preserves the corrected numeric default frames, and refuses generation when local-state
bindings have not been explicitly reviewed. Ten root-VI drafts are quarantined
text only; 27 root generations are refused and the protected error database is
blocked. The motor generation is also refused. No complete VI replacement is
certified by this batch.

Two enum selectors in events 4/5 still have unresolved parser type/default
metadata. Native Print proves their `Arrêt, Default` marker; the new pure models
accept only their explicitly evidenced selector values.

The radioprotection model now retains the incoming ordinate for invalid/zero
state bitmasks. Its unsampled branch needs a separate `stored_output` argument;
an unchanged indicator is not necessarily equal to the current graph input.
The earlier forced-zero default was a manual reconstruction error.

See `../analysis/lvkit_eval/CROSS_VALIDATION_STATUS.md` for source identities,
parser qualification, preserved failed attempts, and reproducibility.

## Digital/UI event reconstruction

`domain.digital_command_events` adds main-VI events 4/5/8/9/10/11. Faraday
position buttons have a True → dedicated 500 ms wait → False plan and reset
all three UI buttons; their False branches are empty. The laser mirror has
separate EN/HORS fields and a dedicated 1000 ms wait. Slit-supply tab selection
retains its requested M/A value; it is not a jaw-position or pulse command.
Faraday tabs 1/2/3 are navigation-only; Arrêt requests NOT each supplied EN
state, then clears command fields and UI buttons. Its waits share frames with
other operations, so write/wait ordering is deliberately not invented.

The pure `project_digital_frame` helper accepts an explicit fresh cluster
snapshot per writing frame and preserves unrelated fields. No command, wait,
UI assignment or readback is executed. Native images, original XML wires and
stored local names are checked by 23 tests against 56 pinned artifacts.
See `../analysis/DIGITAL_EVENT_TRANSFER.md` for rules and remaining limits.

## DPS page-command reconstruction

`domain.page_command_events` adds events 17/18: three Alimentations command
fields and eleven modulator command fields, selected from Event NewVal. The
guard ORs the entire 29-Boolean local DPS snapshot. Busy requests are discarded,
not queued; idle requests fan out to local DPS and PSP even when all selected
fields are False. Local and PSP writes are not ordered or success-gated. The
outside Wait receives 200 ms when idle and 0 when busy; neither is an
acknowledgement. Error writes exact prefix+source to TER; No Error retains
separately supplied stored TER. No UI reset or one-hot arbitration is invented.

The API requires complete DPS and selected NewVal field mappings, with exact
Boolean values and original names/whitespace. It returns immutable projections,
never a binary cluster decoder or executor. Twenty-eight tests check 2056
payload combinations, all 29 busy flags and 20 pinned source/XML/image artifacts.
Current per-magnet ownership remains unresolved by historical DPS requests;
migrated Device Server magnets must not fall back to retired DAQmx routes.
See `../analysis/PAGE_COMMAND_TRANSFER.md` for exact rules, wire evidence and
the original Alimentations field-index limitation.

## Synchronisation and parameter-page reconstruction

`domain.parameter_page_events` adds events 14/15/16: 20 Fluides/HT/HF arrow
rules and nine DPS procedure flags. Busy DPS blocks procedures but not arrows:
original wires prove the inner selector is arrow OR, not inverted DPS OR.
Multi-arrow masks reach native empty Default. HT/preamp/attenuator/phase limits
are reproduced; Fluides has no observed clamp. Native quirks are retained:
`>> Att HF` adds 1; section decrement resets `> Canon` twice, not `< Canon`.
Fluides UI uses a fresh local page base; HT/HF use Event NewVal. Wait(200) gates
arrow reset, not controller/PSP writes or physical acknowledgement. HT pulse
start enables four timing controls; stop disables them, with unordered conflicts
when both flags are True. Error projection retains native prefixes and TER state.

`domain.synchronisation_events` adds event 6: ordered 33-DBL difference detection,
all changed indices, selection-only fresh-local-page fan-out, busy discard,
dedicated Wait(300), final highlight and bounded TME/TER result projection.
Zero changes still require the stored flash index; changing selection itself can
produce selection 33. Runtime property behavior, error aggregation and formatting
are not invented; explicit hypothetical results are required.

Fifty new tests check these contracts against 70 frozen source/XML/image artifacts.
Both models remain offline and non-executable. Native behavior is evidence, not
approved modern safety policy. See `../analysis/PARAMETER_EVENT_TRANSFER.md`.
Bounded refinements cover 21/34 main-event indices, leaving 13 without pure
refinements. Event 3 remains partial; verified complete VI replacements remain 0.

## Diagnostic event reconstruction

`domain.diagnostic_events` reconstructs bounded logic inside `0_SUP_ELYSE.vi`,
not four separate VIs. Events 7/12/13 select the legacy constants `2.126`, `8.98`,
and `5.553` for T1/T2/T3. A single named `C9NI6703` field receives the unscaled
value; `Cmd pos T1/T2/T3` receives value ×10. Units, physical in/out meanings,
current actuator ownership, and limits remain unverified. The plan is not a
movement command or position readback. Unknown selectors fail closed rather
than invoking the native default position.

Event 26 describes `Init moy CxCy=True`, a 200 ms wait boundary, then
`Init moy CxCy=False`. Its event NewVal is not consumed by the observed graph.
The Python plan neither waits nor mutates a buffer, and the timing constant
does not prove another loop observed the reset pulse.

Both saved lvkit contexts agree on these four graphs, but both corrupt local
variable names and omit the visible `0, Default` marker in the position cases.
LabVIEW Print/manual labels take precedence. Source/diagram hashes and mismatch
records are attached to immutable plans. Formal PNG-to-UID reconciliation and
the existing working-copy source-hash drift remain unresolved. Detailed evidence
is recorded in `../analysis/lvkit_eval/CROSS_VALIDATION_STATUS.md`.

```python
from supervision_reconstruction.domain import (
    DiagnosticStation, plan_diagnostic_position_change, plan_centroid_average_reset,
)

position = plan_diagnostic_position_change(DiagnosticStation.T2, 1)
assert position.patch == ("05 OUT05 b21 Cmd position translateur Ecran 2", 8.98)
assert abs(position.display_value - 89.8) < 1e-12
assert position.execution_allowed is False

reset = plan_centroid_average_reset()
assert reset.steps[1].observed_wait_ms == 200
assert reset.establishes_consumer_reset is False
```

```powershell
$env:PYTHONPATH = "src"
py -3.11 -m unittest tests.domain.test_diagnostic_events -v
```

## Local offline web service

The `service` package composes the candidate magnet registry, strict current
preview schema, SQLite shadow journal, and familiar web prototype. It is an
executable analysis tool, not executable SuperVision or an Acquisition adapter.
No Tango/PSP/DAQmx modules are imported, no device connection is opened, and no
API exists for raw writes or physical dispatch. Readback remains unavailable.

From this directory:

```powershell
$env:PYTHONPATH = "src"
py -3.11 -m supervision_reconstruction.service --port 8766
```

Open `http://127.0.0.1:8766/`. Select **Alimentations**, then **Diag** for a current
preview and **Messages** for its journal. **Monitoring** shows catalog coverage,
source identity, and unresolved gates. The service binds only `127.0.0.1`; there
is deliberately no LAN or hardware-enable flag. A production web deployment
still requires authentication, authority/interlock contracts, and adapters.

The default journal is `Supervision/offline_state/shadow.sqlite3`.
`--journal <path>` selects another explicit journal. Existing foreign, empty,
or integrity-failing files are not silently initialized or reset. A journal
entry always has `execution_allowed=false`, `physical_status=NOT_EXECUTED`, and
`establishes_command_success=false`. A zero-current preview is not an accelerator
stop. Even a synthetic fully verified fixture can only resolve a plan.

The same idempotency key and canonical equipment/current request return the
same persisted record; a changed request with that key returns HTTP 409. Retries
and process restarts never replay hardware. The browser retains the retry key
while its page remains open; rechecking the service does not discard it. A page
reload starts a new preview session and does not resume an unknown request.
The chain detects accidental/mid-chain edits but is not a signed audit log:
a privileged editor can recompute it or remove its tail. Actor metadata denotes
local analysis, not an authenticated operator. History shows the last 20 entries;
the count and hash chain cover the complete retained journal.

Endpoints:

| Method | Path | Meaning |
|---|---|---|
| GET | `/api/supervision/snapshot` | Display registry, readback candidates, coherent journal snapshot, catalog coverage, and main-VI SHA-256 |
| GET | `/api/shadow/history` | Last 20 verified local analysis records |
| POST | `/api/shadow/current-preview` | Validate and journal a non-executable absolute-current intent or group |

POST accepts only `idempotency_key`, `expected_revision`, and a bounded
`requests` array of `{equipment_id, current_a}`. Aliases resolve to canonical
equipment IDs. Duplicate physical magnets, arbitrary device/slot/field targets,
unknown IDs, Boolean/string/non-finite currents, duplicate JSON keys, and bodies
over 16 KiB are rejected. Unverified routes/limits/owners, revision mismatch,
and absent transport block each plan without falling back to retired outputs.
Loopback Host and same-origin checks reject cross-site/DNS-rebinding requests.
These checks do not constitute production authentication.

Verification on 2026-10-04: 286/286 domain tests and 32/32 service tests pass;
`compileall` passes. The full suite passes 330/331: the sole failing test is
`test_sources_are_hashed_only_when_unambiguous_and_unresolved_entries_are_evidence_identified`,
which correctly exposes the main-VI hash drift. No VI is a verified replacement.

```powershell
$env:PYTHONPATH = "src"
py -3.11 -m unittest discover -s tests/domain -q
py -3.11 -m unittest discover -s tests/service -q
py -3.11 -m unittest discover -s tests -q
py -3.11 -m compileall -q src tools tests
```
