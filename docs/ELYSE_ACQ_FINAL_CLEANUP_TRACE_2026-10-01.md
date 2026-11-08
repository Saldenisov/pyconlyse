# Acquisition final cleanup and NI6220 read boundary

## Finding and scope

Final cleanup does not itself stop or zero the NI cards. After the
preceding outer frames complete, frame 4 issues PSP connection-close
requests for 27 fixed URI-tag references, independently requests closure
of two TPG300 VISA sessions, and resets `stop=False`. These branches have
no mutual ordering wire. The copied TPG300 Close VI directly wraps VISA
Close without custom cases, retry loops or serial commands.

This is a saved-controller dataflow result, not confirmation that any
resource closed successfully. The review does not require knowledge of
DAQmx's internal implementation: each external call is a boundary with
supplied results/errors. No running VI, XP session or hardware was used.

## Source identity

Root source LLB SHA256:
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
The [root export](../legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip)
is hash-pinned by the existing validators.

Copied source `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\TPG300\Close.vi`
SHA256: `308FA6A146F3F105D6D5A0CFD925F00ED1BCDD76EAA537E4B0B87569985C7B0D`.
Its hash was unchanged before/after read-only extraction. The
[TPG Close export](../legacy/xp_acq_agent/data/source_exports/TPG300_Close_XML_sha308f.zip)
SHA256 is `D0140C8A69938D3957566F5D8B5FD51021F445C6D5EE54CD0ABD878CB6688CDC`.
The validator also pins its three XML members.

The retained [native outer-frame-4 screenshot](C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0014-cleanup-psp-tpg300.png)
was reviewed at original resolution. It shows the constant URI-tag array,
the three error handlers, and the two named TPG sessions. No new native
image was captured in this pass.

## Final frame dataflow

Outer sequence `359`, frame 4, diagram `246` contains these independent
branches. Diagram position does not establish execution order.

| Branch | Wire trace | Controller result |
|---|---|---|
| PSP close | Constant `18438` → auto-index tunnel `1772/1768` → Close Variable Connection `536`, reference input `2610` | Exactly 27 fixed reference tags, rather than the dynamically enumerated local reference array |
| PSP errors | Uninitialized left error shift-register port `2050` → close input `1626`; close output `542` → right port `2044`; final exterior `2048` → handler input `2225` | Carries the returned error between For iterations; exterior seed `2051` is unwired |
| TPG section | Local index 51, terminal `61785` → Close `61121`, slot 11 `61161`; error slot 0 `61128` → handler `68680`, input `69347` | Requests VISA-session closure and reports its returned error |
| TPG chamber | Local index 52, terminal `62410` → Close `66474`, slot 11 `66580`; error slot 0 `66492` → handler `67965`, input `68059` | Separate closure/report branch, not serialized after the section branch |
| Stop reset | False constant `13250` → local index 30, terminal `12987` | `stop=False`; no dependency on either closure result |

The For N input `2469` is unwired; its input array is auto-indexed.
The 27 constant entries, in order, are:

```text
C1NI6071E, C2NI6071E, C3_IN_DIO96, C3_OUT_DIO96,
C4_IN_DIO96, C4_OUT_DIO96, C5_IN_DIO96, C5_OUT_DIO96,
C6NI6703, C7NI6703, C8NI6703, C9NI6703, C1011NI6602,
C12NI1409, DPC, DPS, EPC, EPS, VAM-A, VAD, VAM-S, VDD,
VDM-A, VDM-S, VTA, VTL, VTS
```

Every tag has prefix `ni.var.psp://10.20.30.2/SUPERVISION/`. A fixed
reference-tag list and a runtime-discovered reference array are different
data sources. This does not establish that the listed close operations
fail or that other connections leak; it establishes which source the
controller supplies.

**Observation:** the error shift register is uninitialized externally.
**Inference:** a replay cannot assume an explicit fresh no-error seed
from this frame. Its starting value must be supplied as a runtime state
input; no stale error was observed on equipment. The returned error also
does not prove that later external close calls were attempted physically.

No DAQmx Stop Task, Clear Task or output-zero call occurs in this frame.
Whether DAQ tasks are implicitly released is a separate external-boundary
question, not an additional controller branch hidden in this frame.

## TPG300 Close internal contract

The saved `TPG 300.lvlib:Close.vi` connector has error-out slot 0 (FP
control `5`), error-in slot 8 (`3`), and VISA-session slot 11 (`9`). Its
only executable node is VISA Close, primitive `104`, resource `1922`:

```text
Public VISA session 116 -> VISA Close input 129
Public error-in      111 -> VISA Close input 125
VISA Close output    124 -> Public error-out 109
```

There is no custom close guard, retry, serial write or error-clearing
branch. Parent error-in slots on both calls are unwired. Their output
clusters go to separate Simple Error Handler calls; handler outputs are
unwired. Dialog/handler return behavior remains an abstract external
boundary. The software graph does not wait for an operator safety
acknowledgement wired back from a handler.

Twenty-three [source/mutation tests](../tests/scripts/test_elyse_acq_final_cleanup.py)
passed in **23.047 s**: two original-source tests and 21 rejecting
mutations of the URI list, indexing, shift register, stop reset,
session/error wires, qualified dependency, connector slots and TPG
primitive/body.

## NI6220 error contract and mean-loop correction

The original NI6220 initializer and reader were freshly extracted without
opening LabVIEW, together with all 17 original LLB members. Their
[51-file XML archive](../legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip)
SHA256 is `645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F`.

The NI6220 initializer's public error terminals themselves are unwired,
but this is **not** the NI6071E error contract. Its CPMp mapping assigns
public error-out slot 7 to local parameter 0. Read-property error output
`2593` writes local parameter 0 through terminal `2832`, so the internal
final error is assigned to the public output. Public error-in slot 3 maps
to local parameter 1; no corresponding local read or public-terminal wire
exists. The channel For still has ordinary error tunnels, not an error
shift register. A terminal-only check would have missed this output alias.

**Correction to the earlier native-review summary:** NI6220 Read's mean
For N is not unwired. Signal connects public sample-count terminal `763`
to both DAQ read sample input `1293` and For N `2442`. The returned
channel-array input and mean-array output are auto-indexed. Therefore,
under ordinary For semantics and nonnegative integer N,

```text
number of output channel means = min(supplied sample count N,
                                     returned channel count)
```

There is neither a fixed eight-channel limit nor an unconditional
16-element output guarantee. For example, N=10 with 16 returned rows
produces 10 means; N=1000 with 16 rows produces 16. These are supplied-input
examples, not observations of current configured sample count.

The scaling selector `1160` is a fixed False constant; its arm passes
means unchanged. Both Case arms and their wires are retained in the
validator, without attributing runtime execution to the unreachable True
arm. Public errors directly enter/leave DAQ Read. Its timeout literal is
DBL hex `BFF0000000000000`, i.e. −1; no driver timeout outcome was tested.

The parent startup call uses local parameter 57 for sample count, 58 for
frequency and writes returned task reference to parameter 56. The
[native startup screenshot](C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0010-startup-vacuum-ni6220-ui-gates.png)
labels these `Nb d'éch. NI6220`, `Fréq. d'éch. NI6220` and `C11_NI6220`.
The runtime read independently reads task parameter 56 and sample-count
parameter 57. Caller values therefore must not be replaced by the
initializer's displayed defaults.

Runtime loop `47483` reads `stop` for its Stop-if-True terminal, while the
reader call receives no cancellation flag. Its error output goes to a
handler. **Conditional inference:** if the supplied external read never
returns, setting `stop=True` cannot by itself complete that iteration or
advance the outer sequence to cleanup. This is software scheduling
analysis, not an observed hang or a guaranteed real-time stop delay.

The [bounded Python projection](../DeviceServers/control/elyse_acq/ni6220_projection.py)
implements only channel means and the N/array bound. It is not connected
to a live acquisition or server route. Noninteger/negative N and empty
sample rows are rejected as Python-only input guards; LabVIEW behavior
for those cases and bitwise floating-point parity are not claimed.

Twenty-one [NI6220 tests](../tests/scripts/test_elyse_acq_ni6220_read_contract.py)
passed in **4.471 s**: three source checks, eleven rejecting mutations,
and seven bounded projection tests. These close the explicit error,
mean-bound and stop-input traces, not complete NI6220 configuration or
all downstream WCM projections.

**Subsequent configuration completion (2026-10-01):** the same pinned
export now also verifies all connected NI6220 channel ranges, RSE,
Array Size to For N, sample-clock/trigger arguments and Read properties.
The NI6220 suite has 28 tests, passed in 4.934 s. See the
[initializer supplement](ELYSE_ACQ_INITIALIZER_ERROR_CONTRACTS_2026-10-01.md).
Downstream WCM projections remain open; these seven additional tests
do not assert their parity.

## Reproduction

```powershell
python tools/validate_acq_final_cleanup.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip legacy/xp_acq_agent/data/source_exports/TPG300_Close_XML_sha308f.zip
python tools/validate_acq_ni6220_read_error_contract.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tests/scripts/test_elyse_acq_final_cleanup.py
python tests/scripts/test_elyse_acq_ni6220_read_contract.py
```
