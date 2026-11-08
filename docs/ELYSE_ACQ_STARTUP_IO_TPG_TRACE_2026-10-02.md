# Acquisition initial exchange and TPG startup control logic

This report identifies what the remaining two frames of startup sequence
24603 request, which failures they propagate, and which software resets are
independent of initialization success. Both caller graphs now have separate
source proofs. The copied TPG initializer additionally has proofs for its
five outer states, nested serial-error cases and serial setup caller. This
does not close the TPG Driver Core protocol or the complete Acquisition
controller. Native screenshots are still required for the requested Word
walkthrough; no screenshot or Word revision is claimed here.

## Source identity and replay

The original root VI SHA256 is
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The [preceding startup report](ELYSE_ACQ_STARTUP_PUBLICATION_TRACE_2026-10-02.md)
pins the root XML archive and explains command and pilot-status publication.
The new validators independently check frames 25990 and 33052 rather than
substituting the similar runtime graph.

Copied vendor source is under
`C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\TPG300`:

| Source | SHA256 |
| --- | --- |
| Initialize.vi | A64EC13F3EBECEF4C47B7208B0F8B8F49E5E0F54F3D65C6604284C0EE9736481 |
| SubVI/TPG300-Serial Init.vi | 61712932DA9D07634CE5FDB49D69FE2BC048E597D3F8CC9C754CBA7C85F46082 |
| SubVI/TPG300-Driver Core.vi | 7A0ECCF170459E5B56F49E38AA613246B17D09E9E118ABC73BE2C0B019488F2B |

Raw resource extraction produced the archived XML without loading LabVIEW:
`legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip`, SHA256
`AE6CC7EE631BEE764738D09E1E9787916BC1AAC01B843A50DB669C60F5A2CDB1`.
Every XML file is independently hash-pinned by the vendor validator. Driver
Core was extracted for further review, not declared behaviorally closed.

Replay from the repository with Python 3.12:

```powershell
python tools/validate_acq_startup_io.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_startup_postinit.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_tpg300_startup.py legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip
python tools/validate_acq_tpg300_retry.py legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip
```

## Initial card exchange

Sequence frame 2, diagram 25990, contains 33 direct operations and 32 wire
nets. Twelve conversions connect saved homogeneous clusters to arrays or
arrays to clusters. Tasks and bank directions are checked through canonical
local identities and qualified subVI links, including unused connector slots.

| Step | Caller UID | Connected request and destination |
| --- | --- | --- |
| AI read | 19337 | C1/C2 tasks from locals 23/24; 1000 samples/channel; returned 64-field banks to locals 19/20 |
| DI and DO exchange | 19376 | Six tasks from local 22; DO locals 17/15/13 with sizes 40/32/40; DI banks 56/64/56 to locals 18/16/14 |
| AO write | 19408 | Four tasks from local 25; four ten-field command banks from locals 9/10/11/12 |
| Error consumer | 16070 | Final AO error to Simple Error Handler; mode unwired, outputs unused |

The error wire orders AI, DIO and AO helper calls. The first AI error input is
unwired, and the incoming raw pilot-error tunnel is not connected to this
graph. Readback assignments have no error-status gate. There is no retry,
rollback or stop-local write in this frame. This does not imply that DAQmx
acts after an error or that the handler necessarily returns promptly; these
remain external boundaries. Short-array padding is not inferred from the
cluster conversion node.

`record_initial_io` records the 13 external sites of the already traced
helpers with a source-distinct final handler. The shared mechanics preserve
the existing runtime interface; a runtime handler cannot be substituted for
the startup handler. Command snapshots remain explicit, non-atomic fixtures.

## Independent post-initialization branches

Frame 3, diagram 33052, contains 31 direct operations and 17 wire nets.
Three branches have independent, unwired initial error inputs:

| Branch | Caller UID | Input | Stored result | Error consumer |
| --- | --- | --- | --- | --- |
| NI6220 | 198078 | DBL rate from local 58; I32 sample count from local 57 | Task to local 56 | 49978 |
| TPG300 | 126853 | COM1; U16 selector 4 | VISA session to local 52 | 10951 |
| TPG300 | 123241 | COM2; U16 selector 4 | VISA session to local 51 | 73977 |

There is no connecting error wire between these branches. NI6220, COM1 and
COM2 are therefore not proven to execute in that total order. A serial fault
does not suppress the independently wired software assignments:

| Local | Assignment |
| --- | --- |
| 46, emergency-stop flag | False |
| 45, TCP ED flag | False |
| 44, EPS | 77 Boolean False fields |
| 36, DPS | 29 Boolean False fields |

Five property nodes write `DisabledEnum=2`. Saved enum labels identify 2 as
`Disabled and Grayed Out`; saved DDO targets are 79089, 40722, 70708, 8957 and
11783. These refer to software controls, not hardware outputs. Native visual
comparison remains open. Neither reset values nor a stored opaque session
constitute aggregate readiness. The preceding report's pilot indication
remains `NOT original pilot error.status`.

`record_postinit` records one admissible schedule: 20 NI6220 external sites,
three error handlers and two supplied TPG initializer boundaries. All 25
sites are retained under returning fault fixtures. Missing serial sessions
stay `UNSUPPLIED`; no valid VISA session is fabricated. There is no serial
client or adapter in this model.

## TPG initializer state transitions

The initializer has nine saved diagrams and 85 direct nets. The proof covers
both nested serial-error cases, all five outer states, case tunnels, enum
values, operation census, primitive slots, qualified helper calls and FP
bindings. Select resource 1516 uses slots `output/f/selector/t`, not
`output/t/selector/f`; NI confirms that a True selector returns t. [NI Select
reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/select.html).
Increment and quotient/remainder resources implement the cyclic search;
the remainder is `x-y*floor(x/y)`. [NI quotient and remainder reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/quotient-remainder.html).

| State and diagram | Observed requests and transitions |
| --- | --- |
| 0 Init and Test, 117 | Serial setup at current local Baud Rate. Serial error selects nested diagram 130 and next state 4 without PNR. Otherwise diagram 198 requests PNR with 700-ms timeout. PNR error selects state 1; success selects state 3 if current=requested, otherwise state 2. |
| 1 Next Baud Rate, 173 | Increment current selector, wrap by remainder modulo Max Value+1, write current local. If the result equals the Def.Value snapshot, select state 4; otherwise state 0. |
| 2 Set Default, 182 | Request BAU command assembled from the Def.Value snapshot and saved code array. Write/Read=True. The returned error is not a transition guard: next state is 3. |
| 3 Communication OK, 394 | Write requested selector to current Baud Rate; configure serial again at requested speed; request PNR with 700-ms timeout; exit regardless of the final returned error. |
| 4 Error Box, 410 | Exit with literal error status=True, code=0, source=Init Error. The preceding communication fault is replaced by this literal. |

The while loop continues on True. Both history elements are initialized to
state 0. The second history element is wired to an outer-case input, but none
of its five inner ports participates in the checked state nets. It is not an
additional transition guard.

Error and VISA inputs are ordinary loop tunnels, not feedback shift
registers. A state output error is not automatically the next state's input.
The final PNR output is returned on state-3 exit; the name Communication OK
alone cannot establish success. Driver Core's internal error handling and
protocol determine the supplied result. Their byte-loop facets are now
traced in the [protocol report](ELYSE_ACQ_TPG_PROTOCOL_TRACE_2026-10-02.md);
external VISA behavior remains a separate review gate.

Saved Max Value=4 constrains the normal five-rate search. The serial helper
contains seven rates, but that does not make the initializer search all seven.
For the root's requested selector 4 and a Def.Value snapshot of 4, failed
probes search selectors `4,0,1,2,3`, corresponding to
`9600,300,1200,2400,4800` baud. Increment back to 4 selects Error Box before
another probe. A successful different-rate probe proceeds through Set Default;
selector 4 produces `BAU,9` before reconfiguration and the final PNR.

The requested input also writes Def.Value at the root, while the loop receives
the same input independently. No error/data wire waits for that local write
before every read. Its saved default is 1, not 4. The pure `transition`
projection therefore requires an explicit Def.Value snapshot; it does not
silently impose a global local-variable schedule. Selectors outside 0..4,
changed Max Value, malformed arrays and numeric faults are deliberately
outside this bounded Python projection.

## Serial setup caller and remaining protocol

Serial Init has three saved diagrams and 18 direct nets. Selector 4 indexes
the seven-element rate array to 9600. Enable Termination Char is explicitly
False. Buffer defaults to 5000. Buffer=0 passes VISA/error through; any
nonzero value selects the default case that requests VISA Set I/O Buffer
Size. The buffer case selector is numeric, not an error-status condition.
Unwired VISA Configure Serial Port arguments retain the standard VI boundary;
they are not silently converted into connected constants.

## Driver Core outer retry and error replacement

Three named facets of Driver Core now have operation and net proofs: root
135, outer loop body 191 and final sequence frame 155. These contain 18
direct operations and 25 direct nets, including the nested sequence as one
operation. The subsequent [protocol report](ELYSE_ACQ_TPG_PROTOCOL_TRACE_2026-10-02.md)
adds checks for all 27 inner direct graphs, case mappings and byte-loop guards.

The default Retry control is I32 value 3. Loop 2067 continues on True, and
its actual iteration terminal feeds the saved greater-than comparison:

```text
phase_status = local_1542_from_frame_2 OR local_1521_from_frame_2
continue = phase_status AND (Retry > i)
```

Consequently, returning failed phases can execute attempts with indices
0,1,2,3: four attempts, not three. Retry=0 or a negative value cannot suppress
the first while-loop iteration. These are attempt-count bounds, not latency
bounds; a phase that does not return prevents evaluation of the predicate.

The final Bundle by Name node 798 writes `phase_status` into error field 0.
It does not OR the pre-existing error.status into that Boolean. The incoming
cluster's code/source are preserved at this node, and the resulting error
flows to the separate `TPG300 suppress warning.vi` boundary. The pure
`tpg300_retry.retry_postprocess` therefore keeps the phase flags and the
incoming cluster as distinct inputs. Supplied False/False flags can produce
status=False while preserving a nonzero code; this projection does not
establish which combinations are reachable through the inner protocol.
The subsequent protocol report proves the suppress-warning helper's code-only
gate and whole-cluster replacement; the external VISA returns remain supplied.

The subsequent protocol report closes the named inner ACK/NAK/ENQ, framing,
timeout, loop-exit and suppress-warning facets. Its 30 saved diagrams now
have direct net/operation checks; this is not universal runtime equivalence.
Complete initialization still requires full parent-frame and shared-state
scheduling. Event writers, normal/emergency stop and restart
remain Acquisition gates. Supervision is not reviewed in this pass.

The original facet register now names 32 VI/diagram identities, not 32 fully
understood diagrams or a coverage percentage. The vendor graphs are outside
the original 533-diagram census and are not added to its denominator. All
new Python transfers are non-actuating and disconnected from Tango, PSP,
VISA, sockets and the adapter-capable procedure engine.

## Verification and source preservation

The frozen pre-retry source/mutation selection passed 270 tests in 508.35 s.
The separately added outer-retry source module then passed all four tests
in 0.68 s. The updated full existing ELYSE controller/projection selection
passed 259 tests in 3.00 s; 134 isolated VI-model tests passed on Python 3.11
in 0.347 s. These existing tests include historical Supervision projections;
no new Supervision review or implementation occurred. All pytest runs used
`--deny-network`. Ruff check passed and all 35 scoped Python files passed
format checking.

The focused startup/TPG run passed 23 tests; the retry source/model run passed
eight. Earlier unsuccessful runs exposed two ineffective mutation-test
edits, not accepted source discrepancies: wrong local flag level and an
unchanged Select slot. Both discriminators were corrected and passed stable
reruns. Full history is retained in the closure checkpoint.

All 17 original Acquisition members, original LLB, three copied vendor VI
sources and the existing Word document retain their pinned hashes. There
was no VI run/save, hardware write, PSP or serial command, or remote control.
Test counts establish these bounded checks, not complete Acquisition coverage
or permission to operate equipment.
