# NI6071E saved inputs and Acquisition pilot-read composition

## Result and boundary

The original NI6071E reader stores **1000 samples per channel**. The original
initializer stores **10 samples** and **5000 Hz**. These are controls in two
different VIs, not interchangeable values. Acquisition's pilot reader input
is unwired; the initializer's ten-sample literal does not connect to it.
The first I/O exchange later has its own explicit 1000-sample literal.

This continuation joins nine persisted parameters to their controls,
connector slots and independently decoded binary records. It also composes
the two returning pilot Read call nodes with the existing fallback projection
in a non-actuating Python model. Persisted error indicators do not replace
supplied read errors or prove the return of an unwritten public output.
Native control loading, existing in-memory values and restart are not proved.
No VI, driver, transport or hardware operation executes.

## Original source and binary checks

Both original members are read from
`C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs`.

| Member | Original VI SHA256 | DFDS extent / parsed records | DCO rows / fields |
|---|---|---:|---:|
| `1_ACQ_READ_NI6071E.vi` | `C26AEFFBFC6D48393B2424343877CBC0C0A68239431A0AE63606D5A52F207037` | 3713 bytes / 34 | 7 / 224 |
| `1_ACQ_INIT_NI6071E.vi` | `FEB881DB3A01B5402D5164C3B149195E83D8A0B089DDAEEA0D6A54D7C4E0F07C` | 5572 bytes / 57 | 8 / 256 |

The [source validator](../tools/validate_acq_saved_ni6071e_data.py) compares
all **15 DCO rows and 480 fields**, not only the nine selected controls.
DSINIT's 51 settings integers and each DCO table are independently decoded
with `struct`, then compared with current shared lvkit. Reparsed record spans
consume the complete DFDS payloads, with neither section reporting a parse
failure. The nine selected value spans total **74 bytes**.

Reader DFDS SHA256 is
`D0D41550A4CC9D064282788E18D35994421F992093A6223DE39285A639824E07`;
initializer DFDS SHA256 is
`11ACD5D93A980DB053C43B77DA60CCCFFE7D4B93109EEBA1714E2E30A612AE7D`.
The reader uses TM80 shift 7 and DCO record 144 at bytes `[2883,3415)`;
the initializer uses shift 10 and record 184 at `[4596,5204)`.
Each selected DCO has the expected connector slot, data-record link and
unused default-data link `-1`. Stored labels, typed clients and flags agree
with the original front panel, connector pane and error-cluster field order.

The original XML exports are hash-pinned by the existing reader and
initializer validators. XML alone is not used to guess saved numeric values.
No new diagram identity is added to the 533-identity bounded facet register.

## Nine saved parameters

`bank` below means the helper VI's local DCO index, not a root Acquisition
card bank. Byte intervals are half-open offsets in that member's DFDS.

| VI | Control | Bank / connector slot | Data record / byte interval | Persisted value |
|---|---|---|---|---|
| Reader | `Nb d'échantillons` | 5 / 9 | 130 / `[2853,2857)` | I32 `1000` |
| Reader | `error in` | 4 / 8 | 133 / `[2857,2866)` | `(False, 0, "")` |
| Reader | `error out` | 3 / 0 | 138 / `[2870,2879)` | `(False, 0, "")` |
| Initializer | `Trigger C2 (/2/PFI0)` | 0 / 1 | 18 / `[944,955)` | `/2/PFI0` |
| Initializer | `Trigger C1 (/1/PFI0)` | 1 / 0 | 20 / `[955,966)` | `/1/PFI0` |
| Initializer | `error in` | 3 / 3 | 22 / `[966,975)` | `(False, 0, "")` |
| Initializer | `Nb d'échantillons` | 4 / 4 | 25 / `[975,979)` | I32 `10` |
| Initializer | `Fréq. d'éch.` | 6 / 2 | 27 / `[979,987)` | DBL `5000.0` |
| Initializer | `error out` | 2 / 7 | 173 / `[4559,4568)` | `(False, 0, "")` |

The reader's raw I32 is `000003E8`; the initializer's is `0000000A`.
Each saved error cluster occupies nine zero bytes: Boolean status, I32 code,
and a U32 empty-string length. Stored task tags are not promoted into valid
NI task handles. Other persisted controls are outside this new nine-parameter
qualification, even though the complete DCO tables are checked.

## Pilot count and error routing

In root initialization frame `133`, reader call `287` has count input `2642`,
connector slot 9, with no signal attached. In the reader diagram, public
count terminal `763` feeds both DAQmx Read count ports `422` and `1293`.
The existing [reader graph proof](../tools/validate_acq_ni6071e_read.py)
checks all five helper diagrams, independent C1/C2 errors, the one-second
timeout literal, error merge and calibrated data paths. The existing
[caller proof](../tools/validate_acq_initializer_caller_frame.py) checks the
entire pilot frame and its exact nets; its data outputs are unused there.

The new [Python module](../DeviceServers/control/elyse_acq/vi_simulation/saved_ni6071e_data.py)
requires explicit opt-in to `saved_source_ni6071e_snapshot()`.
`record_pilot_test` requests 1000 samples in each Read call description,
preserves the supplied initializer error from sequence local `1063`, and
passes the merged supplied read error into `project_ai_test_frame`.
It does not replace that error with the reader's saved `error out=False`.
Recorded timeout arguments do not establish an actual one-second completion
deadline for the helper or the whole initialization sequence.

Any original read status=True selects the existing clear/reinitialize
projection. Replacement AI references are supplied outcomes, not tasks
created by this model. The original read error remains available separately
from the cleared fallback error. Subsequent startup VDM-A[0] therefore keeps
the [previously proved raw-pilot status contract](ELYSE_ACQ_STARTUP_ERROR_LANES_2026-10-04.md).
The wrapper does not assign pilot data to root readback banks 19/20.

The NI6071E initializer's public error output has no proved diagram writer.
The stored False/0/empty indicator is now a source-qualified value, but its
native return is still unproved. Existing `initialize` retains `UNASSIGNED`
unless a caller explicitly supplies `public_error_out_seed`. A discriminating
test supplies the saved zero seed and an internal final fault: the internal
fault remains inspectable while the public output retains that explicit seed.
This is a conditional fixture, not a claim that a native faulty initializer
returns success.

## Transfer tests and verification

The [source tests](../tests/scripts/test_elyse_acq_saved_ni6071e_data.py)
reject a mutation at every selected saved byte, every one of the 480 parsed
DCO fields, each selected metadata field, connector/control substitutions,
malformed raw scalar/tag/error data and a wire added to the pilot count input.
They reject substituting the initializer's 10 for the reader's 1000.

The [model tests](../tests/device_servers/control/test_elyse_acq_vi_saved_ni6071e_data.py)
exercise all four C1/C2 read-error status combinations, preserved incoming
warnings, supplied finite sample calibration, explicit output seeding and
pilot-to-startup task ownership. A supplied C2 fault plus successful fallback
uses replacement AI references in first I/O but leaves VDM-A[0]=False.
The retained initial C9 command describes `3.25 V`; no voltage is applied.
Pilot and first-I/O phases use separate inert recorders because they reuse
the same helper-node identities. Their 2 and 49 call descriptions are not
physical-operation counts or a new execution scheduler.

The final focused source/model selection passed **33 tests in 6.06 s**.
The complete isolated VI-model/register selection passed **445 tests and
1942 subtests in 8.32 s**. Both denied network access and reported one
existing pytest assertion-rewriting warning. The ten-file affected
source/model regression passed **210 tests and 363 subtests in 87.85 s**,
also with network denied and the same warning. Four scoped Python files
pass Ruff lint and format checks. The source validator also passed as a
standalone command. Test counts do not measure full controller coverage.

Reproduce from `C:/dev/pyconlyse`:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_saved_ni6071e_data.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest -q -x -o addopts= --deny-network tests/scripts/test_elyse_acq_saved_ni6071e_data.py tests/device_servers/control/test_elyse_acq_vi_saved_ni6071e_data.py
```

All 17 original member hashes still match the pinned manifest; original LLB
SHA256 remains
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
Shared lvkit remains at fingerprint
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.
No demonstrated parser defect required a converter change. Source VIs,
LLB, hardware interfaces and unrelated work remain unchanged; no commit,
VI Run/Save, XP control or new native screenshot occurred.

## Remaining closure gates

Saved value identity is now established for these nine parameters. The
actual use of saved values by an unwired native call, in-memory control
retention, NI6071E's unwritten output return and restart still require
non-actuating native confirmation. Returning external outcomes and absent
intervening local mutation remain explicit composition assumptions.

Native property/error behavior, Diagram Disable activation, Mean(empty),
short Array To Cluster behavior, omitted numeric selectors, indirect actors
and complete concurrent event/I/O/fault schedules remain in the
[Acquisition closure matrix](ELYSE_ACQ_CLOSURE_MATRIX_2026-10-01.md).
This result narrows the saved-input gap; it does not declare Acquisition or
Supervision complete or authorize deployment to hardware.
