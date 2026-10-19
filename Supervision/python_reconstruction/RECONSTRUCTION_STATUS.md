# SuperVision reconstruction status

## Bounded conclusion

The copied LabVIEW application now has a reproducible visual/evidence corpus and a
fail-closed catalog of Python stubs. This is not yet a behaviorally complete replacement.

- Application scope: 39 records: 38 VIs extracted from `SUPERVISION.llb` plus
  `Moteurs SdC GoTo.vi`.
  Current requested scope excludes `Error Code Database.vi`: 38 application
  VIs remain active. Exclusion does not qualify dependent database/error paths.
- Catalog scope: 126 code-bearing VI records: 39 application records plus 87
  dependency records treated as black-box adapter/contract boundaries. Five separate
  non-code evidence records cover four controls and diagramless `Global Variables.vi`.
- Per-VI catalog surface: 126 fail-closed modules; every catalog `reconstruct()`
  entry point raises `NotImplementedError`.
- Reviewed `domain.*` APIs are executable pure software models, not catalog stubs;
  they have no hardware/control adapter path.
- The corrected lvkit 0.8.6 checkout now parses all 39 original application VIs:
  38 hash-matched members recovered from the original `.llb`, plus the separately
  archived motor VI. Stored `supC/ddoList` identities replace front-panel-order
  guesses; omitted-zero and explicit `SelectDefaultCase` identities survive
  dataspace-table refinement where the selector type resolves. Faraday/Fentes
  enum types/default markers remain unresolved in the parser receipt; native
  Print supplies their explicit supported-case boundaries. Parsing is not full
  semantic reconstruction.
- Application model surface: all 39 VI-to-model links plus top-level event-intent
  refinements across 36 application/evidence Python modules, one shared immutable
  intent module and two target-side magnet modules that are not VI conversions.
- Top-level event semantics now include four additional pure, non-executable
  models: event 1 machine-frequency cluster fan-out; event 2 `AXE H`/`GAP H`
  slit-position arithmetic and `C9NI6703` patch intent; event 3 `Translateurs`
  `Arrêt` four-frame topology and Boolean loop-selector expression, with native
  stop/continue direction explicitly unresolved; and events 19/20
  direct/diverted setpoint arithmetic,
  clamping, controller-field routing, and observed 70/100 ms timing boundaries.
  These models expose no PSP, network, UI, sleep, controller, or hardware
  executor.
- `domain.diagnostic_events` adds four bounded main-VI event refinements:
  T1/T2/T3 selector constants and single-field `C9NI6703` patch/display fan-out
  in events 7/12/13, plus the `Init moy CxCy` True → 200 ms wait → False sequence
  in event 26. Together with the digital/UI, DPS-page and parameter/synchronisation
  models below and the remaining-event models, all 34 top-level event indices
  now have bounded pure intent refinements. Event 3 additionally covers
  Laser/T1/T2/T3 through `translator_selection`. These are not 34 fully converted
  events: scheduling, property/default/variant behavior and runtime contracts
  remain unqualified. The earlier fourteen diagnostic tests validate recorded values,
  graph wiring, hash identities, dual-context agreement, and failure boundaries.
  Both lvkit contexts misname locals and omit the visually proven `0, Default`
  case marker. Those mismatches are preserved, not accepted as correct output.
- `domain.timeout_events` adds event 0: 14 ordered/independent PSP read intents,
  counter-task selection/reset/publish, SOURCE-to-CALCULS property copy, date and
  motor selector, and 66 sparse UI refresh fields. Nested field indices and
  source types are checked against original XML/VCTP. H5/V5 shared readback,
  H5 reserve setpoint, VTA local reading `/VTS`, empty channel-3 motor array and
  reset/publication without helper-error gating remain explicit.
- `domain.journal` now projects exact byte concatenation: two independently
  supplied rendered timestamps, new-entry prepend, CRLF, cleared Message OUTPUT
  and a direct append=True/one-row file intent. Original constant payloads and
  stored writer signature/paramIdx resolve the former delimiter/order/append
  gaps. No 100-line trim or empty-path guard exists in the saved diagram.
  Timestamp rendering, text encoding, writer defaults/cancellation/errors and
  output-versus-I/O scheduling remain unqualified.
- `domain.timed_monitoring` refines sequence 16409 frames 0..8: six raw counter
  deltas, True-late→0/False-late→1, seven supplied mean-output slots, strict
  monitoring thresholds, radioprotection caller values, seven vacuum-chart
  sources and the Guide HF sample intent. Measured video/acquisition-event
  deltas do not enter the monitoring AND; its video check is literal 2>1.
  The original owner is timeLoop 17671, omitted by the frozen netlist wrapper.
  Scheduling, baseline initialization/freshness, Mean PtByPt state and chart
  history remain unqualified. The module is not an accelerator interlock.
- `domain.lifecycle_tail` records independent PSP/IMAQ/CmdLib cleanup chains:
  13 PSP references, nine image buffers and one supplied motor address.
  PSP error state is uninitialized/retained; the image loop starts with an
  explicit no-error constant. AbortMotion→Shutdown error-wire order is not an
  all-axes safe-stop guarantee. Final frame 4 is `POUBELLE`: all 15 formula
  inputs are zero-wired and all outputs unconsumed. Expressions are preserved
  as retired text and are not promoted to live calibrations.
- `domain.video_events` and `domain.load_events` add events 21–25 and 31–33:
  tool-mask defaults, zoom/ROI/center, camera/error/busy sequences, loading/tree
  display and cancellation-aware TIFF plans. Native `zoom x3` writes 4; constant
  250 is an image center, not a wait. VALIDER LOAD discards all ten read results
  and applies no equipment settings. Optical-density's stored True branch is
  unreachable because its selector is literal False. Image UID 83225 is unresolved.
- `domain.motion_events` and `domain.autotune_events` add events 27–30: discovery,
  zero-axis intents, signed jog/poll/abort/error decisions, two eight-frame camera
  switches, four centroid stages, inclusive 249..251 convergence and Y-only outer
  termination. Unwired callee Boolean defaults, channel freshness, unlimited
  iteration and completion text emitted even after abort remain unqualified.
  No driver, timer, filesystem or camera operation is executed. See
  `../analysis/REMAINING_EVENT_TRANSFER.md` and `EVENT_MODEL_COVERAGE.json`.
- Additional lvkit loop-ownership correction preserves z-plane-only flat sequences
  beneath their actual event-30 loops rather than orphaning four at root.
  R2 export fingerprint: `FA1E6520BFBC81C4EB841B94F7B1D22749D5FCF17516073F092BC20D291D75C8`.
  Both before/after original-source netlists and a focused patch are frozen.
  Earlier parser receipts are unchanged. The focused converter suite passes 66
  tests; nine FP controls still remain unparsed. No generation or VI was executed.
  A later shared-checkout fingerprint differs due to subsequent codegen edits;
  archived export identities remain unchanged. The drift snapshot is retained
  in `../analysis/lvkit_eval/parser_working_tree_drift_20261004.json`.
- `domain.digital_command_events` adds six main-event refinements: Faraday tab
  navigation/Arrêt, slit-supply M/A, laser-mirror EN/HORS pulses and three
  Faraday position-button pulses. False position events and non-Arrêt tabs are
  empty. Frame groups preserve unordered wait/write/color/UI operations, and
  pure snapshot projection preserves unrelated fields in each writing frame.
  Twenty-three tests check all eight supplied EN-state combinations, exact
  field/error/UI wiring in original XML, and 48 native images. The frozen record
  pins 56 artifacts. Timing constants do not prove physical pulse width, and
  button reset is not readback. Remaining cases and all runtime effects stay blocked.
- `domain.page_command_events` adds events 17/18: 3 Alimentations and 11
  modulator selected NewVal fields. The whole 29-Boolean local DPS snapshot
  supplies the guard. Busy requests are discarded, not queued; idle requests
  describe unordered local/PSP fan-out and a dependent outside Wait(200), versus
  Wait(0) when busy. No Error retains stored TER; Error appends source to exact
  native prefix. Twenty-eight tests cover 2056 payload combinations, all busy
  flags, original XML wires and 20 pinned artifacts including 12 images. The
  original Alimentations field-index/FP-order shortcut is explicitly unqualified;
  inputs are selected named Booleans, not decoded binary page clusters. Thirteen
  main-event indices still lack pure semantic refinement. All runtime effects,
  acceptance/acknowledgement and current hardware ownership remain blocked.
- `domain.parameter_page_events` adds events 14/15/16: 20 adjustment rules and
  nine procedure flags. Busy DPS blocks procedures, not arrows: original wires
  prove the inner selector is arrow OR. Multiple arrows reach native empty
  Default. Numeric clamps, UI-base differences, pulse-timing property intents
  and TER persistence are reproduced. Native `>> Att HF` +1 and duplicated
  Fluides `> Canon` reset are retained, not silently repaired. HT pulse start
  enables four timing controls; stop disables them; simultaneous flags remain
  unordered conflicting intents. No server acceptance or safety policy follows.
- `domain.synchronisation_events` adds event 6: ordered 33-DBL change detection,
  all changed indices, selection-only fresh-local-page fan-out, whole-DPS busy
  discard, three-frame Wait(300)/property/message intent and explicit supplied
  final formatter/error projection. Zero changes still use stored flash index;
  index 32 change yields unclamped selection 33. Runtime error aggregation,
  formatting, GUI and counter/PSP execution remain blocked. Fifty new tests pin
  these two modules to 70 original/XML/descriptor/image artifacts. See
  `../analysis/PARAMETER_EVENT_TRANSFER.md` for source identities and limits.
- Beam-line routing remains fail-closed. The crosswalk records
  `Focale -> C7NI6703/05 Cmd I Solénoïde` as
  `LABEL_MISMATCH_VERIFY_MEANING` and
  `Correcteur H5 -> C6NI6703/08 Réserve` as
  `SCHEMA_RESERVE_UNVERIFIED_ACTUATOR`; neither route is adapter-approved.
- Current magnet ownership is mixed: migrated magnets use Device Servers/iTest
  and their former DAQmx control path is disconnected; other magnets retain
  legacy control. Reconstructed routes are historical evidence, not deployment
  ownership. The server must route per equipment with no fallback to retired
  DAQmx outputs; see
  `Supervision/integration_analysis/MAGNET_CONTROL_OWNERSHIP.md`.
- The new target-side `domain.magnet_registry` is not a VI conversion. Its
  offline inventory contains 21 magnet entries: 8 iTest candidates, 13 unknown
  current owners, and 6 excluded former DAQmx assignments. All default routes
  are unverified and all execution remains denied. Pure absolute-current and
  grouped plans are covered by 27 tests. No operating limits or telemetry are
  inferred from examples.
- The additional target-side `domain.magnet_readback` is also not a VI conversion.
  It separates measurement provenance, acquisition age, source quality, and
  post-dispatch current comparison. Its 32 synthetic tests bring the domain suite
  to 164 passing tests. Eight iTest measurement sources are candidates; 13
  sources remain unresolved. No default source is commissioned. A current match
  does not establish output state, safe shutdown, or complete command success.
- Source-integrity warning: the evidence corpus and catalog identify
  `0_SUP_ELYSE.vi` SHA-256
  `B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B`,
  while the current extracted working copy was modified on 2026-09-29 and now
  hashes to
  `2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B`.
  The new semantic models remain bound to the saved evidence/source-library
  identities and record this mismatch explicitly; no source or catalog artifact
  was overwritten to conceal the drift.
- An exhaustive current working-path check found 16/39 matching application
  sources, 21 changed files, and two missing recorded paths. The main-VI failure
  previously reported was only the first assertion, not the only affected file.
  All 38 original root members have now been recovered with hashes matching the
  archived evaluation; the original motor also matches. New parsing uses those
  originals in separate locations. Working copies and catalog hashes remain intact.
- `domain.radioprotection` corrects a prior manual-model error: invalid/zero EPC
  bitmasks retain the incoming state ordinate through native default-frame wire
  `245 -> 2016`, rather than forcing zero. An unsampled call now requires explicit
  `stored_output`, because the empty False frame does not write the output/local.
  Tests cover 512 state/transition/input-ordinate combinations. This graph-display
  model does not implement or establish a physical radioprotection interlock.
- Visual evidence: 198 named manual captures, 46 debug/transient captures, and
  1,794 LabVIEW Print references to 1,305 unique PNGs.
- LabVIEW Print coverage: 38/38 extracted root VI sections plus the standalone motor
  VI; 701 block-diagram images, 39 front panels, and 39 connector panes for the 39
  scoped VIs.
- Static selector census: 252 selector structures and 732 frames across the root set
  and motor VI. The expected-key ledger contains all 732 unique rows, including frame
  indices needed for duplicate labels. Independent visual review disproved the
  162-row order-based candidate heuristic, so all 732 rows remain explicitly
  unmapped. The candidate audit found 73 visual matches, 85 mismatches, and four
  ambiguous sibling cases; outcomes are retained separately and cannot count as
  authoritative mappings.
- Manual cross-check anchors: 130 expected frame rows reference 131 named LabVIEW
  captures; every path and SHA-256 is checked against the evidence manifest.
- Current verification on 2026-10-04: `compileall` and scoped Ruff checks pass;
  all `374/374` domain and `32/32` service tests pass; full suite passes `423/424`.
  Current per-VI audit adds five checks; journal/monitoring/lifecycle add 34
  further tests. These checks do not certify whole-VI understanding.
  The additional 54 reconstruction tests and 66 converter tests are detailed
  in `../analysis/REMAINING_EVENT_TRANSFER.md`.
  The sole full-suite failure is the
  catalog/source-integrity assertion exposing the `0_SUP_ELYSE.vi` hash drift
  recorded above.
- The local `service` package completes an offline web-preview/journal phase:
  the familiar layout receives candidate metadata, per-equipment blocked plans,
  coherent durable history, catalog coverage, and source-integrity status. The
  server binds only loopback, never imports a hardware adapter, and exposes no
  dispatch endpoint. This is not an additional VI conversion. All current
  readouts remain unavailable and all 19 hardware buttons remain disabled.
- Loop-body census: 17 For-loop and 24 While-loop bodies have their own 41-row
  expected-key ledger; direct image reconciliation remains open.
- User-excluded VI: `Error Code Database.vi`; its diagram remains protected.
  Existing opaque evidence is retained. Local LabVIEW was occupied by an
  Acquisition VI with unsaved changes, so its windows were left untouched;
  no supplied password was attempted and no protection was removed.

## Reviewed Python models

| Legacy VI | Python model | Proven boundary |
|---|---|---|
| `0_SUP_ELYSE.vi` | `domain.supervision_orchestrator`, 15 main-event modules in `EVENT_MODEL_COVERAGE.json`, `domain.timed_monitoring` and `domain.lifecycle_tail` | all 34 event indices have bounded models; monitoring has counter/guard/graph projections and supplied-mean plans; cleanup resource/error chains and 15 retired unconsumed formulas are recorded; startup, concurrent/retained state, property/default/coercion, PSP and hardware contracts remain unqualified; no complete VI qualification follows |
| `1_SUP_INIT_NI6602.vi` | `domain.ni6602` | Eight immutable configurations with initial delay 0, wired low/high ticks, rising edges, and idle low; timebase rate remains `None` |
| `1_SUP_WRITE_NI6602.vi` | `domain.ni6602` | neutral legacy-value ×20 conversion with explicitly chosen nearest-even/I32-saturation policy; software-only write plan, not claimed LabVIEW coercion equivalence |
| `1_SUP_PROFILS XY.vi` | `domain.profiles` | row/column filtering, circular-buffer replacement, averaging |
| `2_SUP_Ecart_lu_ecr_VDirecte.vi` | `domain.deviation` | direct-channel inventory and strict deviation predicate |
| `2_SUP_Ecart_lu_ecr_VDéviée.vi` | `domain.deviation` | deviated-channel inventory and strict deviation predicate |
| `2_SUP_Graph _Radioprot.vi` | `domain.radioprotection` | cadence, one-hot mapping, invalid-state incoming-ordinate retention, explicit unsampled stored-output state, and transition sentinel; no physical interlock claim |
| `2_SUP_Journal_des _erreurs.vi` | `domain.journal` | exact byte prepend/CRLF/message clearing and caller append=True/1D-row intent; timestamp strings supplied independently; no 100-line trim or empty-path guard; clock rendering, encoding and file-writer runtime remain unqualified |
| `2_SUP_marche_defaut_VIDE.vi` | `domain.vacuum` | chamber pass-through and `fault AND NOT running` truth table |
| `3_SUP_en_défaut_alims.vi` | `domain.power_supplies` | fault truth table; H4-to-H5 legacy anomaly is an explicit selectable mode |
| `Add Item.vi` | `domain.tree_plans` | immutable file-then-folder enumeration/tree-invoke plan; filesystem, path, tree-control, and error semantics remain blocked |
| `BuildHelpPath.vi` | `domain.help_paths` | immutable `GetHelpDir` then append-help-filename operation plan; runtime VI-library and LabVIEW path semantics remain blocked |
| `Check Special Tags.vi` | `domain.message_text` | exact ASCII-case `<ERR>`/`<APPEND>` recognition, ERR priority, and wired enum values; arbitrary regex dialect remains blocked |
| `Convert property node font to graphics font.vi` | `domain.font_ui` | U16/U32 field remap with discarded Color and forced Outline/Shadow false; U16→I16 size coercion above 32767 and rendering remain blocked |
| `Details Display Dialog.vi` | `domain.application_plans` | exact six-value dialog enum, type==1 initial button visibility, and four ordered sequence phases; modal UI/event/property/geometry semantics remain blocked |
| `Directory to Tree.vi` | `domain.tree_plans` | immutable Initialize/Validate/Add-Item worklist and Working-lifecycle plan; disconnected `Files found` and local `Parent Tag` are explicit; no filesystem or GUI execution |
| `Error Code Database.vi` | `domain.error_code_database` | excluded from current analysis by user; opaque fail-closed boundary retained, without inventing lookup behavior or qualifying dependent error paths |
| `Find Tag.vi` | `domain.message_text` | evidenced open/close-tag removal loop and indexing-tunnel arrays; unknown regex dialect, zero-length expressions, and non-ASCII byte offsets fail closed |
| `Format Message String.vi` | `domain.message_text` | ASCII-only CRLF composition, `<B>` removal, and ordered immutable value-then-bold effect plans; no GUI access |
| `FW102x Close.vi` | `domain.fw102x_operations` | ungated concurrent close/delete and dependent converter call plan; runtime VI-name/path, driver/session results, and execution blocked |
| `FW102x Error Message.vi` | `domain.fw102x_errors` | immutable external-call and zero-buffer-size plan; U32→I32 size coercion above I32_MAX, driver, DLL, and hardware calls blocked |
| `FW102x Get Position.vi` | `domain.fw102x_operations` | exact error-status gate and extFunc/converter terminal plan; driver result and error-frame position remain blocked |
| `FW102x Initialize.vi` | `domain.fw102x_operations` | exact error-status gate, Boolean coercions, extFunc/session/converter ordering plan; execution denied |
| `FW102x IVI Error Converter.vi` | `domain.fw102x_errors` | exact outer conversion gate and four observed 256-byte preparations; external IVI conversion remains blocked |
| `FW102x Set Position.vi` | `domain.fw102x_operations` | exact error-status gate and extFunc/converter terminal plan; no movement or driver call |
| `GetHelpDir.vi` | `domain.help_paths` | immutable VI-Library → Strip-Path → `help` operation plan; no filesystem/path execution |
| `General Error Handler CORE.vi` | `domain.dialog_error` | incoming/local error selection, action-1 suppression gate, no-error/error branch plans; database, property, Help, Stop, and dialog effects blocked |
| `General Error Handler.vi` | `domain.dialog_error` | exact wrapper remap `0,1,2,3,4 → 0,1,2,4,5`; CORE effects remain blocked |
| `Initialize.vi` | `domain.file_dialog` | single-path array and nonexecuting `Working` Visible/Blinking effect plan |
| `Init_Open_Close.vi` | `domain.application_plans` | ordered `Delete Tree Items(True) → Directory to Tree → Open/Close All(False)` plan; traversal/refnum/error semantics blocked |
| `Longest Line Length in Pixels.vi` | `domain.font_ui` | `max(0, right-left)` over supplied I16 rectangles with overflow fail-closed; text enumeration and platform font metrics remain blocked |
| `Moteurs SdC GoTo.vi` | `domain.motor_planner` | selector/mask/axis/direction/signed-step planning and fail-closed invalid masks; no CmdLib |
| `Not Found Dialog.vi` | `domain.dialog_error` | exact dialog-type grouping and evidenced Help/center-stop/auto-dialog routing; modal/event/shortcut effects blocked |
| `Search and Replace Pattern.vi` | `domain.message_text` | evidenced offset-feedback replacement topology; arbitrary Python regex requires explicit opt-in and non-ASCII byte offsets fail closed |
| `Set Bold Text.vi` | `domain.font_ui` | immutable initialization and nonzero-length selection-effect plan with checked I32 arithmetic; refnum/property/error/rendering semantics remain blocked |
| `sous vi LigneCentroide2.vi` | `domain.application_plans` | exact ±10 line geometry after an already resolved I32 centroid; floating conversion remains blocked |
| `Three Button Dialog CORE.vi` | `domain.dialog_error` | immutable initialization/default-center-OK/sequence plan and connector choice inventory; event/Escape/Panel Close semantics blocked |
| `Three Button Dialog.vi` | `domain.dialog_error` | direct non-executing wrapper plan around CORE; modal/UI behavior blocked |
| `Validate.vi` | `domain.file_dialog` | explicit path-ref validity input and exact `.LNK`/`.lnk` leaf-suffix exclusion, without filesystem access |

These modules perform no hardware, network, DAQmx, CmdLib, Tango, PSP, file-write, or
remote-desktop operation.

## Catalog state

`conversion_state` describes the lvkit/evidence state, not whether the Python project
itself compiled. The following counts apply to the 39 application records only:

- `partial`: 32
- `open`: 1
- `failed`: 6
- `verified`: 0

`failed` primarily means generated lvkit Python contradicted the LabVIEW graph or the
generation command failed. Generated output is retained as comparison evidence and is
never executed as application code.

Additional dependency VI sections are `open` by design. They retain a source SHA-256
only when source resolution is unambiguous. Otherwise `source_status=unresolved` and a
hashed LabVIEW Print section identity is used; no source hash is invented. `.ctl`
sections and `Global Variables.vi` are non-VI evidence inventory, not Python stubs.

## Acceptance gates before replacement

1. Complete the structure/frame-to-PNG reconciliation ledger or record an explicit
   review waiver based on LabVIEW Print's hidden-frame semantics.
2. `Error Code Database.vi` is excluded from current analysis. A complete
   deployed error-handler replacement would still require an authorized source
   or an explicit replacement contract; exclusion does not supply its behavior.
3. Reconstruct remaining application semantics and explicitly approve any required
   dependency adapter contracts; dependency Print presence is not an implementation.
4. Confirm controller field ownership, PSP update/stale-data policy, NI6602 timebase
   and trigger/reset behavior, FW102x behavior, motor limits, and emergency-stop rules.
5. Add golden, contract, fault-injection, startup, shutdown, and partial-initialization
   tests before any hardware adapter can be enabled.
6. Put every future Tango/HTTP/DAQmx/CmdLib or other effectful command behind one
   deny-by-default manual approval gate. No such adapter exists in this project now.
7. Create a repository checkpoint for `Supervision/` before integration. The directory
   is currently untracked in this checkout, so Git alone cannot provide rollback or
   file-level authorship evidence yet.
8. Resolve the `0_SUP_ELYSE.vi` source-hash drift by recovering or explicitly
   approving an immutable source copy before regenerating the catalog or lvkit
   evidence. Do not silently rebind the existing evidence corpus to the modified
   extracted bytes.

Catalog and ledger generators are single-writer tools. They do not provide locking or
atomic multi-file publication; never run two generators concurrently.

## Reproducible checks

```powershell
cd C:\dev\pyconlyse\Supervision\analysis
py -3.11 build_visual_evidence_manifest.py
py -3.11 build_expected_frame_ledger.py
py -3.11 validate_visual_evidence.py
py -3.11 build_vi_coverage_matrix.py

cd C:\dev\pyconlyse\Supervision\python_reconstruction
py -3.11 tools\build_catalog.py
$env:PYTHONPATH = "src"
py -3.11 -m compileall -q src tools tests
py -3.11 -m unittest discover -s tests -v
```
