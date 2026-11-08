# Acquisition startup error routing and task ownership

## Result and boundary

The saved Acquisition startup does not calculate aggregate card readiness.
Three separate error clusters carry the final initializer error, the pilot
fallback result, and the original pilot-read error. Only the original read
status determines `VDM-A[0]` (`Pilote présent ?`). Later discovery, first card
exchange, NI6220, serial initialization and publication have distinct error
paths. Consequently, a cleared fallback does not establish pilot presence,
and pilot presence does not establish successful initialization of every card.

This continuation adds a whole-source census of those three sequence locals
and a non-actuating Python composition of previously checked startup facets.
It qualifies returning fixture traces, not a runnable replacement Acquisition
server. Full controller behavior, native defaults, property/error returns,
concurrent actors and restart remain open. No VI, transport or driver runs.

## Original source

The reference is `0_ACQ_ELYSE.vi`, SHA256
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`,
in `C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs`.
The checked root export is
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`.
The original LLB remains SHA256
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
All 17 original member hashes match the pinned manifest.

The new [source validator](../tools/validate_acq_startup_error_lanes.py)
combines existing independent graph proofs with a new complete port census.
No new original diagram identity is registered: all 533 identities already
have bounded facets, not complete behavioral closure. Shared lvkit remains
unchanged at fingerprint
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.
No demonstrated converter defect required an update in this path.

## Three errors with different consumers

Sequence `201` contains six ordered frames: `20362`, `227`, `133`, `1356`,
`21518`, `7580`. Its complete sequence-local population is `1063`, `306`,
`25655`, each with six frame ports and a typed Boolean/I32/String error
cluster. The validator checks every signal list in the original root,
including all currently unused ports, not only the expected consumers.

| Sequence local | Defining frame | Exact signal peers | Downstream meaning |
|---|---|---|---|
| `1063` | `227`, index 1 | `227`: `562`, `1131`; `133`: `1195`, `2639` | Final NI6703 error gate result becomes the pilot reader error input. |
| `306` | `133`, index 2 | `133`: `2112`, `1320`; `1356`: `1371`, `76738` | Pilot fallback result feeds the Diagram Disable input, not a startup readiness selector. |
| `25655` | `133`, index 2 | `133`: `1309`, `2107`, `25688`; `7580`: `25691`, `28003` | Original pilot reader error is retained separately and reaches the final status calculation. |

These are six complete signal occurrences across 18 sequence-local ports.
Extra peers, additional consumers, changed type/direction/defining frame,
aliased ports and a substituted cleared-error source are rejected. The saved
Diagram Disable node `76550` explicitly has `activeDiag/defaultDiag=01` and
selected empty arm `76564`; native activation remains a separate check.
Its inactive 24-open sibling is not silently executed by the composition.

The resulting separation is:

```text
Four initializers -> error gates -> local1063 -> pilot reader
                                               |
                      original read error -----+-> local25655 -> NOT status -> VDM-A[0]
                                               |
                      selected fallback -------+-> local306 -> saved empty disable arm

Discovery final error -> unused exterior output
Startup command PSP chain -> its handler
Initial AI -> DIO -> AO error chain -> its handler
NI6220 / COM1 / COM2 -> three independent handlers
Final DPS -> EPS -> VDM-A PSP chain -> unused final error
```

Each initializer error status selects Clear Errors, not program cancellation.
The task-bank assignments lie outside those Cases. A supplied Clear Errors
return may itself retain status=True; the model does not manufacture success.
The NI6071E public error remains an explicitly supplied value because its
helper has no proved public-output writer. Call-node presence is not evidence
that a standard NI helper performs work after an incoming error.

## Task ownership through the first exchange

Frame `227` assigns counter bank `21` (eight references), AI banks `23`/`24`,
DIO bank `22` (six references) and AO bank `25` (four references). Any original
pilot error status=True selects the one saved clear/reinitialize path,
regardless of error code. The replacement AI references overwrite `23`/`24`
before first I/O; counter, DIO and AO references remain from their respective
initializers. Token validity is not inferred from their storage.

The fallback changes its AI trigger arguments from `/1/PFI0`, `/2/PFI0` to
`/1/20MHzTimebase`, `/2/20MHzTimebase`, retaining 5000 Hz and ten samples in
the initializer calls. The pilot reader's own sample-count port is unwired;
its native default is not supplied by those initializer literals. The later
[saved-input proof](ELYSE_ACQ_NI6071E_SAVED_INPUTS_2026-10-04.md) establishes
the reader's persisted count1000, independently of the initializer's10.
Native loading of that stored value remains a separate gate.

The nested startup sequence `24603` orders five frames:

| Frame | Saved responsibility | Composition boundary |
|---|---|---|
| `14803` | Assign seven startup command banks | Independent local writes; no atomic bank commit claimed. |
| `24611` | Publish those seven commands and handle their error | Eight returning in-memory call nodes. |
| `25990` | First AI, DIO, AO exchange and handler | Thirteen call nodes with current task tokens; no raw-pilot gate. |
| `33052` | NI6220, two TPG initializers, software resets, UI disabling | Twenty-five call nodes; the three branches are independent. |
| `17881` | Update pilot presence and publish DPS, EPS, VDM-A | Three call nodes; original pilot status, not aggregate success. |

The first exchange retains initial C9 command `6.5`; the checked writer
conversion requests `3.25 V` at channel zero. A pilot, discovery, publication
or later instrument error does not add a C9 zero assignment. This is a
requested value in an inert trace, not observed voltage or permission to
energize hardware. NI/PSP helpers may skip work, fail or block; their actual
behavior is not replaced by the recorder.

Frame `33052` writes DPS (29 False fields), EPS (77 False fields), TCP45=False
and Emergency46=False independently of those returned errors. It does not
reset Stop30 or General47 through a direct local reference. These resets are
software postconditions, not instrument acknowledgments. Final publication
preserves the other 79 supplied VDM-A fields. Its returned PSP error has no
saved stop/TCP assignment or handler consumer in that frame.

## Python transfer and discriminating tests

The new [startup composition](../DeviceServers/control/elyse_acq/vi_simulation/startup_integration.py)
accepts explicit initializer, Clear Errors, pilot/fallback and discovery
outcomes, NI6220 clock values, VDM-A memory and stop memory. Prefix calls are
projected from supplied outcomes, not executed. All suffix calls return;
NI6220 then COM1 then COM2 is one allowed fixture schedule, not a source
total order. No intervening UI, VI Server or other local changes are assumed.

Its 49 recorded call nodes comprise `8 + 13 + 25 + 3`. This count excludes
native prefix execution and does not count successful physical operations.
Missing suffix external returns follow the existing recorder's NO_ERROR
fixture convention, never a claim that unwired native error inputs succeed.

The [business tests](../tests/device_servers/control/test_elyse_acq_vi_startup_integration.py)
distinguish two otherwise easily conflated interpretations. With original
pilot status=True and a successful supplied retry, first I/O receives the
replacement AI tokens, but final VDM-A[0] remains False. With original pilot
status=False and a supplied later AO, NI6220, TPG or PSP fault, final VDM-A[0]
remains True. A Python aggregate-readiness rewrite would fail these tests.

The tests also exercise all 81 initializer/selected-clear status patterns,
all eight initial fallback clear-return status patterns, fault injection
at each of the 49 suffix call sites, failed discovery with a
retained returned token, stale Stop30/General47, retained VDM-A tail fields,
initial C9 conversion, and rejection of malformed snapshots before recording
any requests. The [source mutation tests](../tests/scripts/test_elyse_acq_startup_error_lanes.py)
exercise every one of the 18 used or unused sequence-local ports.

## Verification and remaining gates

The initial new source/model selection passed **50 tests in 20.07 s**.
The nine-file startup source/model regression then passed **136 tests in
171.79 s**. After adding the eight-pattern fallback acceptance test, the
complete isolated VI-model/register suite passed **429 tests and 1942
subtests in 8.11 s**. The final new-source/model rerun passed **51 tests in
36.91 s**. These runs denied network access and reported one
existing pytest assertion-rewriting warning. Four scoped Python files pass
Ruff lint and format checks. The source validator also passed as a standalone
command. Test counts are not controller coverage percentages.

Reproduce the graph check from `C:/dev/pyconlyse` with the configured tools
on `PYTHONPATH`:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_startup_error_lanes.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest -q -x -o addopts= --deny-network tests/device_servers/control/test_elyse_acq_vi_startup_integration.py tests/scripts/test_elyse_acq_startup_error_lanes.py
```

No VI Run/Save, XP control, PSP/VISA/serial command, hardware write, original
VI change, commit or converter modification occurred. No new native screenshot
was obtained. Repository documentation, not a cloud Page, retains the graph
evidence and explicit fixture assumptions.

Remaining startup gates include native loading of the now-qualified
persisted pilot-reader count1000,
NI6071E public-error value, Diagram Disable activation, default control loading,
error-handler blocking/cancellation, indirect local writers and restart.
Complete concurrent event/I/O fault schedules, numeric selector defaults,
short Array To Cluster behavior and source-matched native figures also remain
in the [full Acquisition closure matrix](ELYSE_ACQ_CLOSURE_MATRIX_2026-10-01.md).
The startup composition does not resolve or conceal these boundaries.
