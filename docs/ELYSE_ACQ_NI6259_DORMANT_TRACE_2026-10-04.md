# Acquisition NI6259 dormant initialization and reading

Both copied NI6259 VIs now have independently checked wire facets for all
six saved diagrams and49 direct nets. No saved IUVI link in the17 original
Acquisition members calls either VI. These helpers are therefore modeled
in isolation, not added to the running controller or its initialization.
Dormancy and source understanding are separate claims. Neither result
establishes complete Acquisition behavior or permission to control hardware.

## Original source and proof

The original binary directory is
`C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs`.
Modified review copies are not used. The pinned17-member XML archive is
`legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip`,
SHA256 `645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F`.

| Original VI | Binary SHA256 | Saved diagrams | Direct nets |
|---|---|---|---:|
| `1_ACQ_INIT_NI6259.vi` | `A8DE6D36566F3EF97F0B69B5C7E2AC6E8BCEAF8C48667D60A565DE05A09A323E` | `3`, `2798` | 30 |
| `1_ACQ_READ_NI6259.vi` | `89BC9BE30E5F216474E25F47DF562316F970E0AF118AD5E24FC1E9E0956B7963` | `3`, `869`, `875`, `639` | 19 |

[The independent validator](../tools/validate_acq_ni6259_dormant.py) checks
the archive and each XML hash, all direct operation populations and nets,
public/local connector identities, concrete polymorphic callee links,
connected constants, loop tunnel direction/indexing, typed DBL arrays,
unused ports and both Boolean scaling arms. Mutation tests require each
of the49 direct nets separately and reject altered settings or contracts.

## Initializer dataflow

The saved name is misleading if treated as a device specification. The
task-name literal is `C1_NI6220`, and the eight physical channels are
`11/ai0` through `11/ai7`. These strings are preserved, not corrected to
match the NI6259 filename. All eight connected ranges are -0.2 to+0.2 V;
the connected terminal-configuration code is `0x277A`, not NI6220's
`0x2763`. The64-channel range constants and `/11/20MHzTimebase` remain
visible saved objects but have no signal edges. They configure nothing.

| Step | Diagram and node UID | Saved request and dependency |
|---|---|---|
| Create | `3`, `2629` | Create Task `C1_NI6220`, auto cleanup True; error input unwired |
| Channel loop | `2798`, `2818`, iterations0..7 | AI Voltage Basic, selector `02`; each iteration receives the same Create Task and error returns through ordinary tunnels |
| Timing | `3`, `2393` | Last channel task/error feed Sample Clock, finite mode `0x27C2`, rising edge `0x2828`, source `OnboardClock`; rate and sample count come from separate caller/local reads |
| Trigger | `3`, `2454` | Concrete saved callee `DAQmx Start Trigger (None).vi`, selector `02`; only task/error input and output slots connected |
| Read properties | `3`, `2561` | RelativeTo code `0x28B9`, AutoStart True; task return written through local4 |

The loop contains no task/error shift registers or conditional termination.
An earlier channel's returned error does not seed the next channel. Only
the last channel's returns feed Timing, then Trigger, then the property
node. No explicit Start Task is present. Recording these requests does
not establish how DAQmx would act when an error is supplied.

Public error input and output are both unconnected. The final property
error output is also unconnected; it is not returned through a hidden
local write. The isolated Python model exposes this internal fixture
return separately and retains `UNASSIGNED` for the public output unless
an explicit indicator seed is supplied. The loaded LabVIEW indicator
value is unknown. An unwritten output cannot be reported as `NO_ERROR`.

## Reader dataflow

The Read node `1269` selects
`DAQmx Read (Analog 2D DBL NChan NSamp).vi`, selector `08`. Its timeout
literal is -1 s. Public sample count feeds Read only. In contrast to
NI6220, a separate literal8 feeds the channel-mean For count terminal.
Returned task and actual-sample-count outputs are unused. Read error
passes directly to public error output and does not gate the data branch.

The2D DBL return enters the auto-indexed tunnel `276` of For loop `612`.
Diagram `639` sends each1D row to the standard `Mean (DBL)` call `359`;
only its DBL result is consumed. Mean error is unused. The output tunnel
`1152` collects one result per iteration, up to8. For loops with an explicit
count and auto-indexed input execute the smaller count, so fewer returned
rows produce fewer means. No iteration occurs for zero returned rows.
These loop rules predate LabVIEW2012. [NI archived User Manual, printed pages6-11 and8-4 to8-5](https://download.ni.com/support/manuals/320999e.pdf).

Array Size node `1181` sends its dimension-array result only to a display;
it does not determine the mean-loop bound. The saved Boolean literal is
False. Diagram `869` passes means unchanged through `999 -> 1014`.
Diagram `875` is the inactive True arm: Multiply `651` applies64 saved
slopes, then Add `675` applies64 offsets. Their coefficients equal the
original NI6071E C1 arrays, but this arm does not enable calibration in
the saved VI. With at most8 means, only the first8 coefficients participate.
Elementwise array arithmetic uses common input length rather than padding.
[NI archived User Manual, printed pageB-3](https://download.ni.com/support/manuals/320999e.pdf).

## Inert Python and shared lvkit agreement

[ni6259_dormant.py](../DeviceServers/control/elyse_acq/vi_simulation/ni6259_dormant.py)
adds an isolated12-call initializer recorder and a reader recorder with
one Read plus zero to8 Mean calls. No root, live adapter, CLI deployment,
socket or NI interface imports this new module. Mean results are supplied
independently of sample rows; their arithmetic or native hidden state is
not replaced by an assumed Python average.

Missing Read data remain `UNSUPPLIED`: neither loop count nor result bank
is invented. Returned empty data yield zero Mean calls and an empty bank.
Empty sample rows still reach supplied Mean boundaries. Returned read
errors do not erase supplied data; returned Mean errors do not become the
public Read error or prevent later Mean calls. Missing individual Mean
results retain an unknown bank without skipping other iterations.

[The qualification runner](../tools/qualify_acq_ni6259_dormant.py) generates
only the two arithmetic nodes in diagram875 using the current shared
lvkit checkout. The raw arm is the independently proved direct passthrough.
An audited AST permits only assignments, numeric coefficient lists and
in-memory `_lv.mul`/`_lv.add` helpers. No generated full VI or external
call executes. Both arms agree with the independent projection on584
array cases:292 per arm, lengths0..8, seeded random values, signed zero,
NaN and infinities. Equality uses canonical DBL strings; NaN payload
and native floating exception behavior are not claimed.

The [qualification receipt](../legacy/xp_acq_agent/data/converter_qualification/20261004_ni6259_dormant_shared/receipt.json)
retains generated fragments, proof results and the corpus SHA256
`338CB56DA72FD596ECEA62C09A6FF6B34CF6EA2971CC5A23194E28C8C6442287`.
The shared converter fingerprint was
`B2DA5EEF6B26C9B1C8741BF35B8C13F56C4933B4EAA3B996E9DD968238D1BBAC`.
No converter modification was required for this path.

## Reproduction and remaining boundaries

Use the existing local analysis Python with `tools`, repository root and
the shared lvkit `src` on `PYTHONPATH`. Tests deny outbound networking.

```powershell
python tools/validate_acq_ni6259_dormant.py
python -m pytest -q -o addopts= --deny-network tests/scripts/test_elyse_acq_ni6259_dormant.py tests/scripts/test_elyse_acq_ni6259_qualification.py tests/device_servers/control/test_elyse_acq_vi_ni6259_dormant.py
```

The new source/model lane initially passed25 tests with one warning and
121 subtests in3.08 s. The separate qualification lane passed3 tests with
one warning and15 subtests in1.98 s. These are not the previous747-test
Acquisition source regression. The final combined VI-model, new-source,
qualification and register selection passed351 tests with one warning
and1906 subtests in11.32 s, with networking denied. All eight scoped
Python files pass Ruff lint and format checks. The saved JSON receipt
matches a fresh qualification after JSON normalization, and all17
original binary hashes still match. Register and qualification JSON
files are currently Git-ignored; they are saved locally, not committed.

The register now gives bounded facets to all533 original diagram identities
across17 members, including these six dormant diagrams. The census itself
still says `UNREVIEWED`: facets are not complete behavioral coverage.
Acquisition remains open for omitted numeric defaults, Diagram Disable
activation, loaded control/indicator seeds, native property/error returns,
complete concurrent/event fault schedules and native restart behavior.

Local32-bit LabVIEW capture returned another app, and the one activation
recovery failed with `failed to activate captured window`. No native
NI6259 screenshot was added. VI Run/Save, XP control, PSP commands and
hardware writes were not performed. A static IUVI exclusion also cannot
exclude arbitrary external VI Server callers. These gaps remain explicit;
the isolated NI6259 work does not close reachable ACQ runtime behavior.
