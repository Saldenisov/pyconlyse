# Acquisition runtime I/O, publication and counter reconfiguration

## Decision and evidence boundary

The saved controller graph now has reproducible source proofs for the
NI6071E reader, DIO96 exchange, NI6703 writer, NI6602 reconfiguration,
runtime line readbacks, publication, and the disabled final comparison
frame. These proofs close named facets, not complete Acquisition behavior.
External calls record arguments and consume supplied returns in an isolated
Python simulation. No NI, PSP, VISA, serial, XP or hardware operation occurs.

The subsequent [startup publication review](ELYSE_ACQ_STARTUP_PUBLICATION_TRACE_2026-10-02.md)
adds three named source facets. It distinguishes initial logical command
vectors from the raw pilot-error indication; it does not close full startup.
The facet register now contains 30 diagram identities. Historical runtime
test counts below remain records of the earlier batch, not the current total.

Original sources are the 17 manifest-matching members from
`C:\dev\ELYSE-ACQ-analysis\offline\extracted\ACQUISITION_VIs`.
The original LLB SHA256 is
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
Their durable XML archive is
`legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip`,
SHA256 `645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F`.
Root/caller proofs use `0_ACQ_ELYSE_XML_sha6fe8.zip`, SHA256
`6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`.
Each helper proof additionally checks its three XML hashes and connector pane.
Parser-assigned local names are not evidence: saved front-panel order,
parameter indices and direct wires establish identity.

| Original VI | SHA256 | Proof | Isolated Python translation |
|---|---|---|---|
| `1_ACQ_READ_NI6071E.vi` | `C26AEFFBFC6D48393B2424343877CBC0C0A68239431A0AE63606D5A52F207037` | [reader validator](../tools/validate_acq_ni6071e_read.py) | [read_ni6071e.py](../DeviceServers/control/elyse_acq/vi_simulation/read_ni6071e.py) |
| `1_ACQ_RW_DIO96.vi` | `6F46D4E9551442DC32C0BA3C769341B6AB8D0A467372B5154485078A4606F5BC` | [exchange validator](../tools/validate_acq_dio96_exchange.py) | [rw_dio96.py](../DeviceServers/control/elyse_acq/vi_simulation/rw_dio96.py) |
| `1_ACQ_WRITE_NI6703.vi` | `5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D` | [writer evidence](ELYSE_ACQ_NI6703_WRITER_TRACE_2026-10-02.md) | [write_ni6703.py](../DeviceServers/control/elyse_acq/vi_simulation/write_ni6703.py) |
| `1_ACQ_WRITE_NI6602.vi` | `4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211` | [counter validator](../tools/validate_acq_ni6602_writer.py) | [write_ni6602.py](../DeviceServers/control/elyse_acq/vi_simulation/write_ni6602.py) |
| `0_ACQ_ELYSE.vi` | `6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF` | [readback](../tools/validate_acq_runtime_line_readback.py), [publication/loop](../tools/validate_acq_runtime_publication.py) | [line_readback.py](../DeviceServers/control/elyse_acq/vi_simulation/line_readback.py), [runtime_publication.py](../DeviceServers/control/elyse_acq/vi_simulation/runtime_publication.py) |

## Runtime frame zero conversion and helper integration

The [frame validator](../tools/validate_acq_runtime_io_frame.py) checks all
**33 operations and 32 wire nets** of diagram `7386`. Twelve conversion
nodes connect command clusters to helper arrays and returned arrays to
local input clusters. Their sizes are not uniformly 64.

| Bank | Local parameter | Conversion node | Saved cluster size | Element type |
|---|---:|---:|---:|---|
| C1 AI | 19 | 7485 | 64 | DBL |
| C2 AI | 20 | 7599 | 64 | DBL |
| C3 DI | 18 | 7655 | 56 | Boolean |
| C4 DI | 16 | 7748 | 64 | Boolean |
| C5 DI | 14 | 7836 | 56 | Boolean |
| C3 DO | 17 | 7937 | 40 | Boolean |
| C4 DO | 15 | 8025 | 32 | Boolean |
| C5 DO | 13 | 8127 | 40 | Boolean |
| C6 AO | 9 | 7588 | 10 | DBL |
| C7 AO | 10 | 8669 | 10 | DBL |
| C8 AO | 11 | 8677 | 10 | DBL |
| C9 AO | 12 | 7611 | 10 | DBL |

Saved heap type IDs first resolve through `DTHP/TypeDescSlice`:
`consolidated_ID = 6033 + heap_ID - 1`. The corresponding VCTP top-level
entry selects a flat descriptor. References inside that descriptor are
flat indices, not another application of the consolidated mapping. Both
incorrect shortcuts produce plausible-looking but unrelated types. The
validator checks terminal IDs, cluster sizes, every member's scalar type
and array rank. Mutation tests independently change the slice offset,
element representation, each size, each conversion and frame wiring.

The error wire orders `AI helper 647 → DIO helper 686 → AO helper 278 →
Simple Error Handler 11701`. AI receives an unwired error input and literal
1000 samples per channel; task locals are 23/24, 22 and 25 respectively.
No error-status Case gates the five input-cluster assignment wires. The
handler mode is unwired, and its outputs have no consumers in this frame.
Its exact default dialog behavior remains an external boundary; this frame
does not itself assign a stop flag.

[runtime_io.py](../DeviceServers/control/elyse_acq/vi_simulation/runtime_io.py)
composes the three proved helpers and an abstract error-handler request,
with 13 external call sites in one admissible trace. Complete supplied
arrays reproduce saved index order. Arrays longer than the destination
provide only its corresponding prefix, consistent with the
[NI Array To Cluster contract](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/array-to-cluster.html).
The documented contract does not establish this legacy installation's
short-array padding. A short or empty supplied array retains its known
prefix, but the full cluster remains `UNSUPPLIED`; absent external data
stays unknown instead of becoming an all-zero/all-False measurement.
This is an explicit incompleteness, not a claim that LabVIEW returns an
unknown sentinel.

Root command snapshots require 40/32/40 DO elements and four ten-element
AO banks. These Python representation guards are not additional legacy
interlocks. Tests inject faults at all 13 call sites and retain downstream
request nodes, distinguish independent AI branches, preserve data returned
with faults, and allow supplied late success to replace a prior error.
No physical output action or successful shutdown follows from a recorded
request. Explicit local snapshots also do not establish atomic sampling
or assignment order relative to concurrent loops.

The enclosing sequence `1244` orders frame 0 before publication frame 1
and has no sequence-local or tunnel channel joining their error paths.
Publication's first error input is separately proved unwired. Consequently,
**a supplied card fault is not automatically an input to the PSP stop Case**.
If the error handler returns and all PSP writes return success, publication
produces no stop/TCP assignment despite that card fault. A composed 21-call
test checks this distinction with supplied complete readback arrays.
This does not establish the behavior of a blocking error dialog, another
concurrent stop writer, or a physical safety chain; those remain separate
paths. PSP success must not be treated as proof of successful card I/O.

## NI6071E: data and errors are independent outputs

Root diagram `3` has two independent DAQmx Read sites: node `1269` reads
C1, node `269` reads C2. Both receive the same public error input, separate
task references and the same requested sample count. Their error wires
do not chain C1 into C2. The selected Read instance is analog, 2D DBL,
multiple channels/multiple samples; both timeout literals are **1.0 s**.
Returned task references and returned sample counts are unused.

Each card feeds an auto-indexed channel loop with explicit **N=64**, then
`Mean.vi` for each channel row. Output length is bounded by 64 and the
returned number of channel rows, not by the requested samples per channel.
`Mean.vi` error outputs are unused. The saved calibration selector is a
literal `True`, not an operator setting: each mean is multiplied by its
channel slope and added to its offset. All **256 connected coefficients**
(64 slopes and 64 offsets per card) are compared directly to the Python
arrays. The saved `False` arm passes the two raw mean arrays through.
Testing that arm does not establish that the saved caller selects it.

`Merge Errors` node `584` receives C1 first, C2 second. The simulation
selects the first supplied true error; absent a true error, it selects
the first nonzero-code warning; otherwise `NO_ERROR`. This follows the
standard [NI Merge Errors contract](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/merge-errors.html),
not an assumption that a failed read returned valid data. Data projection
still occurs when the separately supplied error is true.

All three I/O call sites explicitly request **1000 samples/channel**:
startup node `19337`, runtime `647`, controlled-stop exchange `55456`.
They receive task locals 23/24 and assign C1/C2 results to locals 19/20.
Their reader error inputs are unwired. The separate initialization probe
call `287` has an unwired sample-count input; its implicit default is not
proved by the three explicit I/O literals.

Python uses an immutable `SampleMatrix` fixture. Empty outer channel arrays
project to empty arrays; missing returns remain `UNSUPPLIED`. Empty channel
rows, nonfinite numbers and arithmetic overflow are Python-only rejected
inputs. Exact floating-point reduction order and malformed LabVIEW-array
behavior remain unverified; no bitwise numerical parity is claimed.

## DIO96: six ordered boundary requests

The helper contains an empty first sequence frame `9110`, followed by
body `1684`. The saved error chain is:

```text
public error input
  -> Read C3 (232) -> Read C4 (667) -> Read C5 (1028)
  -> Write C3 (2840) -> Write C4 (38) -> Write C5 (742)
  -> public error output
```

Read selection `0F` and Write selection `0E` represent 1D Boolean data,
one channel/one sample. Writes have literal `autoStart=True`. Timeout ports
are unwired; their driver defaults are not invented. Returned tasks and
write counts are unused. Read data assignments are not gated on error
status. Every graph call site remains present when a supplied true error
is forwarded; whether a real external function skips an action belongs
to that boundary, not the controller proof.

The task-cluster order is C3/C4/C5 DI, then C3/C4/C5 DO. At all three root
I/O sites, output banks are locals 17/15/13, input banks 18/16/14, and
the task bank is local 22. Reader public error feeds DIO input; DIO public
error feeds the NI6703 writer. Missing DI values remain `UNSUPPLIED`, never
invented `False` states. The simulator does not assign hardware polarity.

## Root seven-frame I/O sequence

While `203` contains sequence `1244` in body `211`.

| Index | Diagram UID | Saved function | Proof boundary |
|---:|---|---|---|
| 0 | `7386` | AI read → DIO exchange → AO write → error handler and data assignments | Complete operation/net census, 12 saved conversion shapes and supplied-return integration; short-array padding remains open |
| 1 | `7392` | Eight ordered PSP writes, then error-dependent stop/TCP assignments | Complete direct operation/net census and both error Case arms |
| 2 | `2010` | 20 C3 DI fields → direct-line cluster | Exact field identities, directions and all 23 nets |
| 3 | `8695` | 18 C3 DI fields → deviated-line cluster | Exact field identities, directions and all 21 nets |
| 4 | `1283` | 11 C1 AI fields → direct-line cluster | Exact field identities, directions and all 14 nets |
| 5 | `18156` | 9 C1 AI fields → deviated-line cluster | Exact field identities, directions and all 12 nets |
| 6 | `1619` | Command/readback comparison Case | Saved selector `False`; empty active arm; full inactive caller wiring retained, helper internals not yet closed |

The **58 readback field copies** have no intervening inversion, threshold
or permission gate. Each frame reads and rewrites a whole local cluster;
untargeted fields are retained from that frame's supplied snapshot.

| Frame | Source fields, in wire order | Target fields, in wire order |
|---:|---|---|
| 2, C3 DI → direct | `31,32,28,29,35,36,37,38,39,40,41,42,12,13,14,15,43,44,45,46` | `2,4,14,16,38,40,50,52,62,64,74,76,86,88,98,100,110,112,122,124` |
| 3, C3 DI → deviated | `24,25,26,27,20,21,47,38,39,48,33,34,51,52,53,54,18,19` | `2,4,14,16,38,40,50,52,62,64,74,76,86,88,98,100,26,28` |
| 4, C1 AI → direct | `28,20,38,29,22,30,23,16,24,31,32` | `7,19,31,43,55,67,79,91,103,115,127` |
| 5, C1 AI → deviated | `19,27,25,18,40,33,21,34,34` | `7,19,31,43,55,67,79,91,103` |

Deviated targets **91 and 103 both receive C1[34]** in the saved source.
The validator rejects silently changing one to C1[35]. This establishes
software wiring, not a hardware-channel defect or an authorized correction.
Field names and physical meanings must be correlated separately.

Frames 2–5 are ordered relative to each other, but not atomic relative to
sibling loops. A concurrent write between a frame's local read and whole-
cluster write can be overwritten by the older snapshot. A deterministic
test demonstrates that admissible schedule; it does not claim an observed
live race. Frame 1 publishes raw input banks and EPS/EPC/VTA, not these
newly projected direct/deviated clusters.

### Publication and stop observation

The exact error-wire order is
`C1NI6071E → C2NI6071E → EPS → EPC → VTA → C3_IN_DIO96 → C4_IN_DIO96 → C5_IN_DIO96`.
All destinations have the prefix
`ni.var.psp://10.20.30.2/SUPERVISION/`. The first error input and all
returned URL outputs are unwired. The last error output feeds Case `40346`:
False arm `49991` is empty; True arm `50030` assigns local 30 (`stop`)
and local 45 (`TCP ED`) to `True`. No False reset occurs in this Case.
A warning with false status does not enter the True arm.

The simulator records all eight calls and literal assignments. It neither
delivers PSP data nor assumes that earlier errors survive external calls:
a supplied later successful return can mask them. No synchronous stop,
hardware-safe state or upper latency bound follows from the error Case.

Body `211` independently wires an **80 ms** Wait node, local 30 to the
Stop-if-True terminal, and iteration index `i` to local 32. There is no
dependency forcing the stop read to occur after sequence frame 1. A read
before its new `stop=True` assignment can therefore leave another iteration
eligible. The wait, sequence and stop sample are not a guaranteed fixed
period or an interruptible safety transaction. Full sibling-loop cancellation
and the outer stop path remain separate completion gates.

### Saved disabled comparison

Frame 6 wires literal `False` to Case `8602`. Active arm `8613` has no
operations or wires. Inactive arm `8619` would independently call
`2_SUP_Ecart_lu_ecr_VDirecte.vi` and `2_SUP_Ecart_lu_ecr_VDéviée.vi`, reading
locals 28/33 and shared input local 29, then writing their returned line
clusters to 28/33. Neither helper is invoked by this saved frame. Its two
helper bodies remain review targets; inactive code is retained, not
misrepresented as a runtime interlock.

## NI6602: polling is not an error-gated wait

While `3129`, body `3149`, reads `CO.Pulse.Done` through property `6414`
at node `3202`. The exact exit predicate is:

```text
Done == True OR i > 20
```

The zero-based loop can make **22 poll requests**, unless `Done=True`
ends it sooner. Each iteration also has an independent **1 ms** Wait.
This is not a guaranteed 22-ms deadline: the external read and scheduling
can add unbounded time. Error status is not part of the exit predicate.
The loop has ordinary task/error tunnels, not shift registers; every poll
receives the original task/error inputs. Intermediate returned errors and
tasks do not feed the next poll. Last returned values feed Stop Task.

Post-loop saved order is
`Stop Task (2976) → Clear Errors (309) → timing property (3083) → Start Task (3032)`.
Supplied task/error returns flow along that chain. Default simulation
fixtures pass errors through; an explicit `Clear Errors` return is required
to model clearing. The standard helper body is not silently implemented.

Both `InitialDelayTicks` and `LowTicks` receive `U32(20.0 × delay)`;
`HighTicks` receives `U32(20.0 × width)`. For finite, in-range values the
projection rounds nearest, ties to even, matching the standard
[NI unsigned-long conversion](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/to-unsigned-long-integer.html).
Examples at products 0.5/1.5/2.5/3.5 are 0/2/2/4. Negative, nonfinite,
overflow and saturation/wrap behavior are outside this Python guard domain,
not assigned an invented legacy policy.

Unknown `Done` before the iteration bound produces an incomplete trace
and an unassigned result; the simulation does not invent an exit. At
`i=21` the bound alone establishes exit. The root caller's error input
is unwired, returned error reaches Simple Error Handler, and the next
sequence frame resets the request to `-1`; that reset is an attempted
command acknowledgment, not proof that the physical counter changed.
Complete caller selection/arithmetic integration remains open.

## Verification and remaining work

Final verification of this batch: **254 Acquisition source/mutation tests
passed in 385.24 s**, **233 ELYSE controller/projection tests passed in
3.36 s**, and **108 isolated VI-model tests passed on Python 3.11 in
0.402 s**. Pytest used `--deny-network`; Ruff check passed and 21 scoped
files passed format checking. These counts include prior proofs and
regression tests, not 254 newly reviewed diagrams. All 17 original VI
members, the original LLB and the existing Word evidence document remained
hash-identical. A preceding full run failed one register test because the
overlay changed from 26 to 27 after its old test was loaded; the final run
used stable files and passed. The
[machine-readable checkpoint](ELYSE_ACQ_STATIC_CLOSURE_CHECK_2026-10-02.json)
retains both results and explicit open gates.

### Focal ON/OFF continuation

The [focal-helper proof](../tools/validate_acq_focal_helpers.py) checks both
original helper roots: each has **45 diagram operations and 55 wire nets**,
with no nested frame, loop or Case. Three independent branches each order
`Initialize → Set Voltage → Set Current Slew → Set Current → Set Output → Close`.
The sole public connector is error-out; resource controls are private,
with saved F3/F2/F1 defaults COM10/COM11/COM12. Each Initialize has
`ID Query=False`, `Reset=True` and an unwired error input. This also applies
to `OFF`; it is not an isolated unconditional output-disable function.

| Focal | Voltage literal | Current-slew literal | Current literal |
|---:|---:|---:|---:|
| 3 | 70.0 | 0.02 | 15.1 |
| 2 | 80.0 | 0.02 | 20.9 |
| 1 | 80.0 | 0.02 | 13.73 |

These are connected controller arguments, not confirmed physical values
or slew units. Both `ON` and `OFF` reset and request these settings before
passing True/False respectively to Set Output. Error/session returns chain
within each branch; no errors chain between branches. Close errors merge
in priority F3, F2, F1. There is no retry, separate unconditional cleanup
or special fault override of OFF in either helper. The vendor wrappers
remain external boundaries; the earlier [vendor trace](ELYSE_ACQ_VENDOR_VI_TRACE_2026-09-29.md)
documents Set Output's error-in bypass. A true error reaching that boundary
does not establish that an output-disable command was sent.

The visible **9600** baud constants have no wires. They are not requests
made by these saved callers; vendor initialization defaults are not derived
from their proximity on the diagram.

[focal_helpers.py](../DeviceServers/control/elyse_acq/vi_simulation/focal_helpers.py)
records 18 calls per helper with explicit resource snapshots and a supplied
branch schedule. Alternative branch orders preserve the saved merge
priority. Tests inject errors at all **36 ON/OFF call sites**, forward
opaque supplied session tokens, and distinguish attempted calls from device
action. No serial port, driver or transport is imported. Source hashes are
registered in the facet overlay; root event callers and custom vendor
internals are not closed by these two helper proofs.

Source mutation tests change individual wires, selectors, fields, literals,
port direction, connector slots and operation censuses. Model tests cover
supplied errors, unknown returns, early/bounded poll exits, U32 rounding,
all 256 calibration coefficients, 58 readback copies, concurrent snapshot
loss, and publication faults at each of eight call sites. The
[facet overlay](ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json) cross-indexes these
proofs for 27 identified diagrams into the original 533-diagram census without editing its historical
`UNREVIEWED` rows or assigning a full-coverage percentage.

No accepted native evidence screenshots or Word revision were added. Local LabVIEW's
unaddressable modal caused a typed path to become an **unsaved diagram
label**; user was asked to close the modal and Undo only that label.
The latest observation again shows that label and an existing modified
diagram. A view-menu click did not expose usable navigation, so no further
diagram input was attempted. No VI was run or saved. Prior user changes
must be retained; the window must not be saved as evidence of original source.

Next critical paths: unresolved short-array defaults, remaining
event/timing calculations, focal caller and custom serial
paths, every nested stop/fault/restart branch, full shared-state ownership,
and native screenshots correlated with original diagram UIDs. The current
isolated translations do not replace the live Acquisition server.

Reproduce from the repository, offline:

```powershell
python tools/validate_acq_dio96_exchange.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_ni6071e_read.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_ni6602_writer.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_runtime_line_readback.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_runtime_publication.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_runtime_io_frame.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_focal_helpers.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip
python -m unittest discover -s tests/device_servers/control -p 'test_elyse_acq_vi*.py'
```
