# Acquisition NI6703 requested-voltage and error-wire trace

## Result and boundary

The original `1_ACQ_WRITE_NI6703.vi` now has a reproducible source-wire
validator and an isolated Python request simulation. The closed facets are
four ten-channel conversion banks, the two nonlinear C8 channels, the four
DAQmx Write call sites, public task/error selection, and the corresponding
input/error edges at all three root call sites. This does not close their
parent initialization, runtime or controlled-stop frames, permission gates,
concurrent bank ownership, or the entire Acquisition controller.

The simulation records supplied-data requests only. It cannot reach an NI
driver, hardware adapter, transport, XP session or callback. No VI was run
or saved; no physical voltage or contact state was measured or changed.
Standard DAQmx calls remain external boundaries rather than inspected
driver implementations.

## Source identity and public interface

Original VI SHA256:
`5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D`.
The source is the manifest-matching original member, not an edited
`ACQUISITION_VIs_verified` working copy.

The validator reads
`legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip`,
SHA256 `645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F`.
Writer XML hashes are:

| File | SHA256 |
|---|---|
| `vi.xml` | `8188B80D33E0943F4F093E2C9BE058E1EAFBE438EF1DF1EB96A57867F6FD1FAE` |
| `vi_BDHb.xml` | `2432B10879A5EC011A84356E0A2192A461E8C436391648A48D8693787C693B7D` |
| `vi_FPHb.xml` | `A4AE50E63C16C359F1D503CD51C1A4A5EB6655AE2962397C796827C84474A668` |

Connector mapping is established by FPHb, CPMp and connected public
terminals together. Node order or a copied caption is insufficient.

| Connector slot | Public control | BD terminal UID | Meaning |
|---:|---:|---:|---|
| 0 | 630 | 743 | C6 logical array |
| 1 | 60 | 62 | C6/C7/C8/C9 task-reference cluster |
| 5 | 773 | 859 | C7 logical array |
| 7 | 903 | 976 | C8 logical array |
| 9 | 1004 | 1087 | C9 logical array |
| 11 | 1074 | 1076 | Public error input |
| 15 | 1280 | 1282 | Public error output |

Root diagram UID `3` contains 42 wire nets. Diagram Disable node `1070`
has an old cluster-based arm `1093` with 11 nets and an empty arm `1100`.
Saved `commentMode=True`, `activeDiag=01`, `defaultDiag=01`, absent tunnels
and the earlier saved review identify the old implementation as
inactive. Its alternative `/36` and `/40` divisions are not substituted
into the active array implementation. No new native screenshot was captured
in this pass; the user-requested native-image register remains separate.

## Logical values to requested voltages

Array indices are zero-based. Let `L6` through `L9` be input logical banks
and `V6` through `V9` be requested-voltage arrays, not measurements.

| Bank | Connected slope array, indices 0..9 |
|---|---|
| C6 | `(1, 1, .5, .5, 1, .5, 1, .5, 1, .5)` |
| C7 | `(.25, .25, .25, .25, .25, .0416666, .25, .25, .25, .25)` |
| C8 | `(1, .2, .2, 1, 1, .0277777777, .025, .1111111111, .1111111111, 1)` |
| C9 | `(.5, .25, 1, 1, 1, 1, 1, 1, 1, 1)` |

C6, C7 and C9 use elementwise multiplication. C8 first uses elementwise
multiplication, then adds `(0, -2, -2, 0, 0, 0, 0, 0, 0, 0)`. Saved
truncated literals are retained exactly, not rounded to `1/24`, `1/36`
or `1/9`. For example, C7[5] input `240` produces `9.999984 V`, not exactly
`10 V`.

Index node `1210` extracts C8's adjusted indices 3 and 4. Replace node
`991` substitutes only their converted results back into that same adjusted
array. Slopes at these two indices are 1 and offsets are 0 in this source.

```text
C8[3] -> Formula 1158 -> Replace index 3:
V = (8*10**-9)*x**4 - (7*10**-7)*x**3
    - (3*10**-5)*x**2 - 0.0181*x + 2.1775

C8[4] -> Formula 748 -> Formula 568 -> Replace index 4:
angle = 57.3*acos(10**(-x/20))
V = (-4*10**-6)*angle**3 + 0.0006*angle**2
    - 0.0624*angle + 3.8587
```

The cubic receives the preceding `acos` result, not the original C8[4]
logical input. Zero logical inputs therefore request `2.1775 V` on C8[3]
and `3.8587 V` on C8[4]. An all-zero logical C8 bank also requests `-2 V`
at indices 1 and 2; the actual startup bank is not all zero. Its documented
temperature inputs 21 and 27.9 instead request approximately `2.2 V` and
`3.58 V`. All 40 previously retained startup predictions are regression
checked against the new projection.

No voltage clamp, radiation-protection predicate, water-flow guard or HT
authorization branch occurs within this helper. In particular, C9[0]
logical `12.7` converts to a `6.35 V` request, but that conversion does not
establish permission to issue the command. Permission and bank writers
must be traced in the caller/event logic. Absence of a gate here does not
prove absence of a gate elsewhere.

## Ordered calls and errors

Task-cluster fields 0..3 independently supply C6..C9 tasks. Returned task
references and samples-written outputs have no consumer. The error wire,
not screen position, fixes the call order:

```text
public error input
    -> C6 Write 592
    -> C7 Write 1696
    -> C8 Write 1989
    -> C9 Write 1200
    -> public error output
```

Every node selects analog 1D DBL, multiple channels, one sample; `autoStart`
is connected True and timeout is connected `20.0 s`. The helper contains
no Case/loop-based retry, rollback, count check, error latch or separate
stop branch. This is a statement about controller wiring. Whether an
external DAQmx node performs, skips or fails a physical write given an
incoming error is boundary behavior, not established by this graph.

The simulation visits all four call sites and passes each supplied returned
error to the next site. A pass-through fixture propagates a fault or warning
unchanged. A later supplied clear can remove an earlier fault because no
controller-side latch is added. This does not assert that a real DAQmx call
would clear that fault. Calls already made are not retrospectively undone.

## Root integration edges

All three original root calls receive C6..C9 local banks 9..12 through
Cluster To Array primitives, the task cluster from local 25, and the error
returned by `1_ACQ_RW_DIO96.vi`. Each writer's final error feeds
`Simple Error Handler.vi`.

| Root writer UID | Enclosing diagram | Position | Closed facet |
|---:|---:|---|---|
| 19408 | 25990 | Outer frame 1, init frame 5, nested frame 2 | Bank/task/error input and final error-consumer edges |
| 278 | 7386 | Outer frame 2, While 203, seven-frame sequence 1244 frame 0 | Same edges |
| 55532 | 41713 | Outer frame 3, conditional controlled-stop branch, While 41705 | Same edges |

These edges disprove the alternative interpretation that startup/runtime/
stop use unrelated AO bank orders. They do not prove bank values at an
arbitrary iteration, all entry gates, the entire DIO helper, error-handler
UI behavior, loop termination, or concurrent update ordering.

## Python mapping and validation

- [Source-wire validator](../tools/validate_acq_ni6703_writer.py): hash-pinned
  original exports, public mapping, full active wire set, arithmetic ports,
  50 slope/offset elements, nonlinear indices/formulas, task selection,
  timeout/autoStart, unused outputs, disabled-arm mode and three root facets.
- [Python projection and recorder](../DeviceServers/control/elyse_acq/vi_simulation/write_ni6703.py):
  immutable input banks and synthetic task tokens, with in-memory external
  returns supplied through `ScriptedBoundary`.
- [Source/mutation tests](../tests/scripts/test_elyse_acq_ni6703_writer.py):
  individual coefficient mutation, formula/index/error-edge changes,
  selector/port/task-field changes, added guard/retry, enabled old arm,
  connector bank swap, caller bank/error mutation and extra root call.
- [Projection tests](../tests/device_servers/control/test_elyse_acq_vi_writer.py):
  all 40 startup requests, nonzero nonlinear inputs, literal truncation,
  absence of invented clamp/HT permission, fault injection at all four
  call sites, warning/clear behavior and independent input task selection.

The supported Python domain is exactly four immutable ten-element finite
numeric banks. Shape, finite-value, overflow and real-`acos` checks are
explicit Python-only guards. They occur before any request is recorded;
their timing is not claimed equivalent to LabVIEW's parallel dataflow.
Negative attenuation/domain faults, NaN/Inf and malformed-array behavior
in LabVIEW remain unresolved. Numerical regression is software evidence,
not an execution comparison with the LabVIEW runtime or equipment.

Reproduce from `C:\dev\pyconlyse`:

```powershell
python tools/validate_acq_ni6703_writer.py legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_ni6703_writer.py tests/device_servers/control/test_elyse_acq_vi_writer.py
```

Focused verification: **31 passed in 22.21 s**; controller suite:
**170 passed in 1.86 s**, with network access denied. The 14 new projection
tests also passed on Python 3.11. The full Acquisition source/mutation suite
passed **192 tests in 155.03 s**, also with network access denied. Both
pytest suites emitted one nonfatal `PytestAssertRewriteWarning` for the
already imported module-isolation plugin. All 17 original VI hashes and
the original LLB hash were rechecked without drift. These counts are regression results, not
a whole-Acquisition coverage percentage. The existing Word document was
not revised or re-rendered in this pass.

Next critical boundary: prove the complete preceding DIO96 read/write
helper and the rest of root sequence 1244, then join the verified I/O
requests to event/stop gates and concurrent bank writers. Supervision
remains deferred under the [Acquisition closure matrix](ELYSE_ACQ_CLOSURE_MATRIX_2026-10-01.md).
