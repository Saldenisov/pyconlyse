# Acquisition initializer configuration and error contracts

## Result and boundary

The [2026-10-15 native continuation](ELYSE_ACQ_NATIVE_INITIALIZER_OBSERVATIONS_2026-10-15.json)
adds source-correlated images of all four NI6703 frames, the DIO96 diagram,
the Main error Cases and pilot fallback, dynamic discovery and five final
startup frames. NI6703's loaded path was read from Properties and matches
the byte-exact original review copy. DIO96's corresponding path readback
remains pending. These static20.0f1 imports were not run or saved and do not
establish original LV2012 execution equivalence.

The original DIO96, NI6071E, NI6220, NI6602 and NI6703 initializer
configuration/error paths now have saved-source wire checks. Their error
contracts differ substantially: DIO96 and NI6602 have continuous public
error chains; NI6220 ignores public error-in but returns the internal
chain; NI6071E does not return its internal errors through the public
connector; NI6703 discards Create Task errors and returns only the final
C9 channel-creation error. A single generic Python initializer wrapper
would therefore not reproduce the legacy controller.

This closes the initializer configuration/error facet and the root's
PSP discovery controller wires, not Acquisition as a whole. Custom serial initialization/caller arguments,
startup command projections, runtime field transformations, concurrency,
and complete fault/restart behavior remain separate review gates in the
[closure matrix](ELYSE_ACQ_CLOSURE_MATRIX_2026-10-01.md). A requested task
creation or task start is not a demonstrated physical result. Standard
DAQmx behavior is an abstract external boundary; no driver was executed.

## Original-source identity

Source LLB SHA256:
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
Original XML archive:
`legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip`,
SHA256 `645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F`.
All 17 VI hashes were checked before and after read-only binary-resource
extraction. The complete original census traverses all 533 raw diagram
UIDs, including flat-sequence cells; traversal is not behavioral closure.

| Original VI | VI SHA256 |
|---|---|
| `1_ACQ_INIT_DIO96.vi` | `F308D6A6E995A5C63D8EA57CC1FAB523AEA7DD3712FDD707C0B232B73AC308CA` |
| `1_ACQ_INIT_NI6071E.vi` | `FEB881DB3A01B5402D5164C3B149195E83D8A0B089DDAEEA0D6A54D7C4E0F07C` |
| `1_ACQ_INIT_NI6220.vi` | `58532480F5234E0FFF36417C5A0A0513B5B7267D4451BF42D0B7A0BDE271F3CA` |
| `1_ACQ_INIT_NI6602.vi` | `3341C22226FA587F488C78027FF60B9E3E990462763C6F1C7E322C3634994442` |
| `1_ACQ_INIT_NI6703.vi` | `2F9489A0F1E04DF0F052A8F25FFF8CA3AD813D27A112B989C5CB483C792B6205` |

## DIO96: six serially connected task specifications

Observed in root diagram UID 3:

```text
public error-in 583
  -> C3 input Create Task -> Digital Input
  -> C4 input Create Task -> Digital Input
  -> C5 input Create Task -> Digital Input
  -> C3 output Create Task -> Digital Output
  -> C4 output Create Task -> Digital Output
  -> C5 output Create Task -> Digital Output
  -> public error-out 1282
```

| Task name | Physical-channel literal | Task output field | Native line count |
|---|---|---:|---:|
| `C3_IN_DIO` | `3/port0:6` | 0 | 56 |
| `C4_IN_DIO` | `4/port0:7` | 1 | 64 |
| `C5_IN_DIO` | `5/port0:6` | 2 | 56 |
| `C3_OUT_DIO` | `3/port7:11` | 3 | 40 |
| `C4_OUT_DIO` | `4/port8:11` | 4 | 32 |
| `C5_OUT_DIO` | `5/port7:11` | 5 | 40 |

All six Create Task calls receive auto-cleanup=True. The output cluster
retains the six returned task references in the listed field order.
There is no output-write, Start Task, Stop Task or Clear Task call in
this helper, and no Case/loop/retry. The downstream controller may use
the returned error; it must not infer task success from call presence.
The root's separate error-clearing behavior is already checked in the
[lifecycle audit](ELYSE_ACQ_LIFECYCLE_LOOP_AUDIT_2026-09-28.md).

Native evidence:
[six-task diagram](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-DIO96-six-tasks.png).
The screenshot title contains a modification asterisk; the hash-pinned
original export, not an assumed byte-identity of the loaded window,
is the terminal-level reference.

## NI6703: channel configuration is not initial output voltage

Sequence UID 784 has exactly four ordered frames:

| Frame/diagram | For/body | Task | Physical channels | Task-cluster field |
|---|---|---|---|---:|
| 0 / 1241 | 714 / 773 | `C6_NI6703` | `6/ao0..9` | 0 |
| 1 / 2744 | 4638 / 4666 | `C7_NI6703` | `7/ao0..9` | 1 |
| 2 / 1824 | 1920 / 1976 | `C8_NI6703` | `8/ao0..9` | 2 |
| 3 / 355 | 789 / 862 | `C9_NI6703` | `9/ao0..9` | 3 |

Each frame requests a task with auto-cleanup=True, then iterates ten
auto-indexed physical-channel tags. AO Voltage receives range -10 to
+10 V, units Volts and output terminal configuration Default
(`FFFFFFFF`). The original ring label is `output terminal configuration`,
not DAC reference; this corrects the previous caption interpretation.
Task reference input is an ordinary tunnel, not a shift register.
The returned task and error are non-indexed loop outputs. There is no
DAQmx Write call in this VI; initial logical AO values and physical
write requests belong to later parent/helper paths.

Observed error path:

```text
public error-in -> C6 Create Task error-in
                  Create Task error-out -> UNWIRED
each C6 channel error-in -> UNWIRED
C6 channel-For last error -> C7 Create Task error-in
                            Create Task error-out -> UNWIRED
each C7 channel error-in -> UNWIRED
C7 channel-For last error -> C8 Create Task error-in
                            Create Task error-out -> UNWIRED
each C8 channel error-in -> UNWIRED
C8 channel-For last error -> C9 Create Task error-in
                            Create Task error-out -> UNWIRED
each C9 channel error-in -> UNWIRED
C9 channel-For last error -> public error-out
```

Sequence locals 1916, 1970 and 2000 carry the C6, C7 and C8 loop errors
to the next frame. Channel loops have no error shift register, and the
four channel-call error inputs are unwired. Thus the returned error
does not accumulate all initialization errors. For supplied external
returns with an earlier channel error and a successful final C9
channel, the public error output follows the latter, not an OR of all
errors. This is a controller-dataflow inference, not an observed fault
on NI hardware or a claim about an unwired DAQmx input's implementation.

The visible Vmin/Vmax/Pente/Offset arrays below the main wire path are
unconnected in this initializer. Their captions and values must not be
substituted for the connected +/-10 V channel range. Later AO conversion
requires independent inspection of `1_ACQ_WRITE_NI6703.vi`.

Native evidence:
[C6](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6703-frame0-C6.png),
[C7](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6703-frame1-C7.png),
[C8](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6703-frame2-C8.png),
[C9](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6703-frame3-C9.png).
These are retained native screenshots, not new GUI captures in this pass.

## NI6602: complete eight-frame parameter and error flow

Sequence UID 3868 requests OUT0 through OUT7 in order. Each frame has
this task/error flow:

```text
Create Task -> CO Pulse Ticks -> Start Digital Edge trigger
            -> Start.Retriggerable=True
            -> CO.Pulse.IdleState=Low / CO.CtrTimebaseActiveEdge=Rising
            -> implicit Timing (finite, one pulse)
            -> optional Start Task
            -> corresponding task-cluster field / next error sequence local
```

The error input is public terminal 13028, through sequence tunnel
16834/16802; final error returns through 13565/13569 to public terminal
13111. Seven sequence locals link the frame errors without a Clear
Errors, handler, retry or rollback branch. Each output task is returned
in its matching cluster field 0..7. There are two property nodes in
each frame: 16 total, not eight.

| Counter/frame | Diagram UID | High ticks | Low ticks | Trigger PFI | Trigger edge | Start call |
|---:|---:|---:|---:|---:|---|---|
| 0 | 9978 | 20 | 31 | 34 | Rising | Yes |
| 1 | 8666 | 3620000 | 200 | 34 | Rising | Yes |
| 2 | 6900 | 200 | 43558 | 30 | Rising | Yes |
| 3 | 9448 | 60 | 43658 | 34 | Rising | No |
| 4 | 7229 | 60 | 43500 | 30 | Rising | No |
| 5 | 6943 | 2000 | 101600 | 30 | Rising | Yes |
| 6 | 9487 | 56 | 43500 | 30 | Rising | Yes |
| 7 | 7856 | 100000 | 20 | 10 | Falling | Yes |

Every physical counter is `10/ctrN`; all use timebase `/10/PFI11`,
auto-cleanup=True and connected initial-delay literal zero. The native
20-MHz annotation implies 0.05 microseconds/tick only if that external
timebase is actually supplied. It is not a measured frequency or an
initializer rate-setting call. The unwired summary table is not the
parameter source: for example, frame 3 wires low ticks 43658 even though
the lower summary table displays 43444.

Native evidence, one retained image per frame:
[0](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame0.png),
[1](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame1.png),
[2](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame2.png),
[3](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame3.png),
[4](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame4.png),
[5](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame5.png),
[6](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame6.png),
[7](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6602-frame7.png).

## NI6220 and NI6071E contrast

NI6220 creates sixteen RSE voltage channels `11/ai0..15`, with +/-10 V
at ai4..7 and +/-0.2 V elsewhere. Array Size of the physical-channel
constant feeds channel-For N. The sample clock is OnboardClock, rising,
finite; rate/count come from caller locals 58/57. Its separate trigger
is rising `/11/PFI0`. Read RelativeTo is Current Read Position and
AutoStart=True; no explicit Start Task is present. The public error
input is not used, whereas the internal final property error is assigned
to public error-out through local index 0. Its channel loop has ordinary
error tunnels, not accumulation across iterations.

Native evidence:
[NI6220 full diagram](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6220-full.png).
The displayed extra grey channel row is not an additional configured
entry: the original connected array contains exactly sixteen strings.
The reader's mean-array sample-count bound and separate stop input are
covered in the [NI6220 trace](ELYSE_ACQ_FINAL_CLEANUP_TRACE_2026-10-01.md#ni6220-error-contract-and-mean-loop-correction).

NI6071E differs: its internal C1-to-C2 error chain ends in Simple Error
Handler, whose output is unwired; neither public error connector has a
wire or matching local alias. Its complete channel/range/timing/trigger
proof is retained in the [NI6071E audit](ELYSE_ACQ_LIFECYCLE_LOOP_AUDIT_2026-09-28.md#ni6071e-internal-initializer-checked-on-2026-10-01).

## Root PSP discovery: final error is not consumed

Root initialization sequence 201, frame 4 (diagram 21518), enumerates
`ni.var.psp://10.20.30.2/SUPERVISION`. The connected filter constants
are raw `000000` and `0000000000`; the retained native screenshot
displays the two access filters as Allowed. The duplicate URI constant
82435 above the active path is unwired.

The returned child references auto-index into For 74267. Its explicit
N input is unwired, so the controller iteration count follows the
returned child array, not a fixed list of 27 expected names. Body 74296
reads each Variable PSP Data Type and passes the reference/type outputs
to dynamic-open node 74325. A separate connected Wait(1 ms) shares the
iteration; it has no ordering wire before or after the property/open.

Enumerator error 74195 seeds shift-register input 74293. Within the
body, the previous error feeds the property, the property error feeds
dynamic Open, and its error feeds the next iteration. However, the
exterior final error terminal 74285 is unwired. This stage contains no
retry, error handler, stop assignment, expected-name/count/type check,
or conditional abort. An external boundary that never returns could
still prevent stage completion; the absence of a guard is not proof
that execution cannot block.

The auto-indexed open results write local parameter 61 (`Refnum SVE 2`
in the native image). A full root `gRef` census finds exactly one
reference to parameter 61: this writer, with no later local read.
Final cleanup uses a separate fixed 27-tag constant, not this discovered
array. This establishes controller reference-flow asymmetry, not a
resource leak: whether a URI-tag close releases a dynamic-open resource
is an external PSP implementation question outside the current proof.

Native evidence:
[dynamic discovery diagram](C:/dev/ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0006-init-dynamic-psp-discovery.png).
The saved wire validator and 13 source/mutation tests cover this stage,
including the error shift-register pairing, reference indexing, dynamic
terminal IDs, wait, and the parameter-61 writer/reader census. No
network enumeration or PSP Open call was issued.

## Reproduction and remaining work

```powershell
python tools/validate_acq_output_initializers.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip
python tools/validate_acq_ni6602_initializer.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip
python tools/validate_acq_ni6220_read_error_contract.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_psp_discovery.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest discover -s tests/scripts -p 'test_elyse_acq_*.py'
```

DIO96/NI6703 have 22 source/mutation tests. NI6602 has 22 test methods,
including parameterized checks for all eight high/low-tick arguments,
error entries and retriggerable flags. NI6220 has 28 tests covering its
initializer, reader, parent wires and bounded mean projection. Test
passing proves consistency with these explicit contracts, not complete
whole-program parity or hardware readiness.

The next Acquisition gate is root startup state and custom
driver call arguments, followed by complete runtime projection and
fault/restart transitions. No live hardware integration or Supervision
transition was performed. The existing Word document has not yet been
regenerated with this supplement; these corrections must accompany it
until its next rendered-and-verified revision.
