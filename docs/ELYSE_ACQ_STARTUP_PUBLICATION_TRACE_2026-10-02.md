# Acquisition startup command and pilot status publication

This analysis determines which logical commands Acquisition assigns during
startup and what its final `Pilote présent ?` indication actually reports.
Three saved frames have complete direct operation and wire censuses: command
assignment, command publication, and final status publication. The indication
is the inverse of the **original NI6071E pilot-read error status**, not an
aggregate success flag for all cards or instruments. Neither this source
result nor the isolated Python model establishes hardware readiness.

## Source and review boundary

The source is `0_ACQ_ELYSE.vi`, SHA256
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The validator reads the pinned root XML archive
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`, SHA256
`6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`.
Heap descriptors are resolved through the original DTHP slice, not inferred
from copied captions. No VI was run or saved. No new native screenshot is
claimed; source identifiers below allow comparison with the native diagram.

| Sequence 24603 frame | Diagram UID | Direct operations | Wire nets | Evidence closed here |
| --- | --- | --- | --- | --- |
| 0 | 14803 | 14 | 6 | Seven command-bank assignments and all 152 logical fields |
| 1 | 24611 | 23 | 21 | Seven PSP writes and final error-handler input |
| 2 | 25990 | 33 | 32 | Independently checked in the subsequent startup integration report |
| 3 | 33052 | 31 | 17 | Independently checked in the subsequent startup integration report |
| 4 | 17881 | 16 | 13 | Raw pilot-status calculation, three PSP writes and independent 100-ms Wait |

The saved sequence order is enforced by the validator. Frames 2 and 3 have
their own proofs in the [startup integration report](ELYSE_ACQ_STARTUP_IO_TPG_TRACE_2026-10-02.md).
The complete initialization, driver protocol and scheduling are not inferred
from the five caller graphs.

## Initial command banks

Frame 14803 writes these values to canonical local-variable indices. All
unlisted elements are zero for analog commands and False for digital commands.
Indices are zero-based.

| Bank | Local index | Size | Nonzero or True logical elements |
| --- | --- | --- | --- |
| C6NI6703 | 9 | 10 | None |
| C7NI6703 | 10 | 10 | None |
| C8NI6703 | 11 | 10 | [1] = 21; [2] = 27.9; [6] = 360 |
| C9NI6703 | 12 | 10 | [0] = 6.5; [2] = [3] = 4.755; [4] = [5] = [6] = 2.126 |
| C3_OUT_DIO96 | 17 | 40 | [1], [4] |
| C4_OUT_DIO96 | 15 | 32 | [1], [4], [6], [8], [17], [19] |
| C5_OUT_DIO96 | 13 | 40 | [33] |

Literal 17752 fans out to both C6 and C7. Its original 81-byte representation,
including a trailing zero byte, is checked exactly; other analog clusters
contain 80 bytes. Six literal outputs therefore produce seven bank writes.
The assignment frame contains no error gate or hardware-readback input.
Independent local writes do not form an atomic shared-state transaction.

Copied literal captions are misleading: literal 20833 has a C5 caption/type
label but writes **C3 local 17**; literal 22493 has a C3 label but writes
**C5 local 13**. The destination wires and canonical local indices determine
the bank, not the caption. Analog values are logical requests, not measured
volts; the NI6703 writer applies the separately traced conversions described
in [the NI6703 writer report](ELYSE_ACQ_NI6703_WRITER_TRACE_2026-10-02.md).

## Command publication and its error boundary

Frame 24611 publishes local snapshots in this error-wire order:

```text
C6NI6703 -> C7NI6703 -> C8NI6703 -> C9NI6703
          -> C3_OUT_DIO96 -> C4_OUT_DIO96 -> C5_OUT_DIO96
          -> Simple Error Handler.vi
```

Each URI is the literal `ni.var.psp://10.20.30.2/SUPERVISION/` followed by
the bank name. The first writer's error input is unwired. Each returned
error feeds the next write; the last error reaches handler 26161, port
26191, connector slot 9. The handler's mode input is unwired and its outputs
are unused. This records request/error flow, not successful PSP delivery.

The frame has no conditional branch that selects or suppresses subsequent
sequence frames and no stop/TCP local assignment. If the handler returns,
the sequence proceeds to the initial I/O frame. Whether a handler blocks or
an external writer performs a write when receiving an error is outside this
proof. The Python fixture does not substitute a claim about those effects.

## What the pilot indication means

The original error is retained independently of the fallback result:

```text
NI6071E READ 287: error out 1309
  +-> fallback Case selector 2107
  +-> sequence local 25655, frame-2 port 25688
        -> frame-5 port 25691
        -> sequence 24603 external input 28003
        -> frame-4 input 27992
        -> unbundle 28019: error.status
        -> NOT 24445
        -> bundle 31306: VDM-A[0]
        +-> write VDM-A local 7
        +-> publish VDM-A
```

The fallback result instead leaves Case 2105 through port 2112 and enters
sequence local **306**, port 1320. Replacing the raw-error connection with
that cleared fallback result changes the meaning of the indication and is
explicitly rejected by mutation tests. The prior fallback proof remains
applicable: this frame does not test-read again after reinitialization.

Only the Boolean `status` is used. An original error produces False even if
a later fallback succeeds; an original warning with `status=False` produces
True regardless of its code. `VDM-A[0]` is `Pilote présent ?`. The remaining
79 fields retain the supplied VDM-A snapshot; the model does not invent or
clear their states.

The final publication chain is **DPS -> EPS -> VDM-A**. DPS and EPS are
29- and 77-Boolean clusters respectively; VDM-A contains 80 Booleans.
The first error input is again unwired, so a previous command-publication
error is not this chain's initial error. The final VDM-A error output is
unused in this frame. An independent Wait receives 100 ms; no wire orders
that Wait after the writes or establishes a total startup deadline.

## Isolated Python projection and discriminating checks

`vi_simulation/startup_publication.py` provides `publish_commands` and
`publish_status`. Both accept only the in-memory `ScriptedBoundary`. They
record URI strings and fixture returns without importing a transport or
hardware adapter. The status function requires explicit raw pilot error
and frame-4 snapshots; it does not execute missing startup frames. Its
100-ms Wait is metadata, not a sleep. The command trace assumes no other
writer changes the locals between assignment and publication.

Source tests mutate literals, heap descriptors, field indices, primitive
identities, frame order, PSP ports, URI constants and the raw-error tunnel.
Projection tests inject faults at all seven command writes, the handler,
and all three final status writes. A composed 11-request trace distinguishes
a command PSP error from the raw pilot error. A supplied later successful
PSP return can clear the publication error but cannot replace the original
pilot error or change its Boolean calculation. These tests are causal
counterexamples, not evidence of device or network behavior.

```powershell
& 'C:\Users\elyse\miniconda3\envs\pyconlyse312\python.exe' tools/validate_acq_startup_publication.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& 'C:\Users\elyse\miniconda3\envs\pyconlyse312\python.exe' -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_startup_publication.py tests/device_servers/control/test_elyse_acq_vi_startup_publication.py
```

## Remaining acquisition coverage

Full root initialization still requires frames 25990 and 33052, their
custom serial callees, argument provenance, independent error paths,
cancellation and restart. Whole-controller coverage additionally requires
remaining event/calculation branches and concurrent state ownership.
Native screenshots must confirm the source review before any claim of
complete native coverage. Supervision was not reviewed in this continuation;
no actuator-capable procedure, Tango adapter or existing Word evidence
document was changed.

## Verification results

The final stable run passed **261 Acquisition source/mutation tests** in
441.84 s with network access denied. The existing ELYSE controller and
projection regression suite passed **241 tests** in 2.84 s; this regression
includes existing Supervision projections but adds no Supervision review.
Python 3.11 passed **116 isolated VI-model tests** in 0.326 s. The focused
startup run passed 15 tests in 76.44 s. Ruff check passed, and 22 scoped
Python files passed format checking. Pytest emitted the previously recorded
nonfatal assertion-rewrite warning for `scripts.refactor.pytest_module_isolation`.

All 17 original VI hashes matched the extraction manifest. The original LLB
retained SHA256
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
The unchanged Word evidence document retained SHA256
`E4E9C63C0360042A64E16BE57C9831CAA2BA3B6E8D335425985883B771698D8B`.
These counts describe reproducible checks, not a percentage of controller
coverage or authorization for hardware actuation.
