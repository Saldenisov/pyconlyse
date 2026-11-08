# Acquisition default data decoding and selector cross checks

The original Acquisition VI now yields 829 parser-produced DFDS records with
exact-length reads across all 56852 bytes; not all records are semantically
validated. A correction in shared lvkit prepares lazy descriptors, removes
extra-byte reads for observed LV12.0.0f4 tagged references, and retries DFDS
after consolidated types have linked. Five numeric records independently match
the saved heap labels of nine cases containing 64 frames. This strengthens
source extraction; it does not establish loaded control values, omitted
Default-case behavior, native event schedules or full Acquisition coverage.

## Source and decoding mechanism

The source is `C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs/0_ACQ_ELYSE.vi`,
SHA256 `6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The decompressed DFDS payload has 56852 bytes and SHA256
`33C3D8AF2CE159F83C547013E8339964DF4E26520F6917A211CBEA83D78C03D5`.
The existing original XML archive remains unchanged and supplies independent
block-diagram labels for comparison.

Several distinct faults prevented reliable extraction. During the initial resource read,
a consolidated variant could be requested before VCTP linking completed;
DFDS then remained in raw fallback form. A direct later retry exposed a
second fault: pylabview treated the release stage as belonging to its
extra-byte version interval. The first 39-byte Variable-reference value at
DFDS offset 233 occupies 43 bytes including its length header and ends at 276.
The second length header starts immediately at 276. Consuming an extra byte
changes the second length from 39 to 10094 and shifts subsequent decoding.

The reference correction applies only when version fields equal 12.0.0,
release stage 4, build 4 and refnum subtype 21. `Variable` retains the initially
qualified correction; `VariableContainer` and `Task` take this path only inside
DFDS. Descriptor preparation and exact-length stream reads are also limited
to DFDS of this exact version. Other versions and reference kinds retain the
upstream reader. Truncated headers, values and scalar reads fail explicitly.
A failed DFDS read is retried once during resource integration,
after all blocks have parsed; unresolved types and unsuccessful retries retain
raw failure rather than fabricated defaults. VI-writing methods are unchanged
and must not be used with this read-only patch layer.

The shared checkout is `C:/dev/ELYSE-ACQ-analysis/converter/lvkit`, with the
existing parallel overlay preserved. The initial recovery fingerprint was
`3C36083C2983BA102C6E4928554C9A6291C37F3A3E9AFD7877F4AE935A83DBF1`.
The recovery candidate contains `_pylabview_dfds.py`, its hook in
`_pylabview_patches.py`, and synthetic tests in
`test_pylabview_dfds_recovery.py` and `test_dfds_lazy_descriptors.py`.
The separate case-count guard and its tests remain useful defensive validation.
No proprietary VI binary is needed in those synthetic tests. No commit,
push or pull request was created.

## Independent selector comparison

[The validator](../tools/validate_acq_dfds_recovery.py) pins the original VI,
whole DFDS payload, each record's byte interval and record hash. A separate
`struct` decoder reads big-endian numeric fields directly, including both
range flags and diagram index. It compares these rows with the original
`SelectRangeArray32` heap fields, then checks the restored lvkit XML parser.
No generated VI or full translated module executes.

| DFDS TypeID | Byte interval, end excluded | Cases with matching range content | Explicit selector mapping |
|---|---|---|---|
| 2938 | 8420–8468 | 81854 | 0→frame0; 3→frame1 |
| 2939 | 8468–8528 | 100523 | 0→frame0; 1→frame1; 3→frame2 |
| 2987 | 8900–9008 | 11808, 12392, 12976, 13572 | 0→2; 1→0; 2→1; 3..6→3; 7..8→2; 9..10→3; 11→4 |
| 2994 | 9380–9488 | 11557, 63039 | 0, 1, 16, 128, 256, 512, 1024→frames0..6 |
| 3005 | 9716–10040 | 8105 | 0..24→frames0..24 |

The heap's numeric text is decimal; `SelectDefaultCase` remains hexadecimal.
The source explicitly stores default `01` for 100523 and default `04` for the four
cases matching 2987. It omits this field for 81854, 11557, 63039 and 8105. The
validator preserves that distinction. Explicit table ranges do not identify
which arm receives an unlisted selector value.

These cases do not contain `tdOffset` links to the DFDS records. Matching
range content therefore confirms concordance between saved representations,
not unique table ownership. In particular, cases 11557 and 63039 share the
same range content. The proof does not use positional table correlation to
claim identity. Earlier candidate counts came from the misaligned parse
described below and are not current coverage results. Only the five numeric
records listed above have independent range/heap qualification. Other records and variant/string
meanings are not certified merely because the parser consumed the section.

### Tail alignment correction: the previous TypeID 3057 interpretation is superseded

The interval 27348–56852, SHA256
`38EB0C46CCEE574B985AB8409449C34D28DFCD5625BDD59049DC533115C765A9`,
was incorrectly attributed to TypeID 3057. Its apparent header `(0, 1, 2)`
was the beginning of the preceding repeated block, not a selector-table header.
Flat descriptor 1359 has bytes `000a0064000007cb0073`, specifying 1995 I32
values. The lazy descriptor still had `numRepeats=0` when its data-fill object
was constructed. TypeID 3056 therefore consumed no bytes, and the following
record interpreted its 7980 bytes as a different structure. Permissive
`int.from_bytes(b'')` reads then fabricated zeros for 300 subsequent records.
Reaching the section's end had not established correct record boundaries.

Preparing descriptors before constructing data fills and rejecting short
reads removes that failure mode. Independent `struct` decoding now matches:

| Actual record | Byte interval, end excluded | Independently checked content | SHA256 |
|---|---|---|---|
| 3056 | 27348–35328 | 1995 I32 values | `2674C849753CBE5C2EAA6C8135471F498593813D17E18747D51902A68F19852B` |
| 3057 | 35328–35376 | Header `(0, 2, 2)` and two Boolean-selector rows | `2979B45A45B351C794BA3FAD5D9961780CCE5E2C765A91E37130E7C8574C07DE` |

TypeID 3057 now passes the positive count/shape check. No unique diagram
ownership or additional native default behavior is inferred from that fact.
The source validator checks both corrected records and retains the historical
misaligned-region hash solely to explain the earlier failure.

The defensive correction in `parser/nodes/case.py` still requires a positive
declared range count equal to the number of range clusters. Its ten synthetic
tests cover inconsistent counts, valid retention and deduplication. Those
fixtures are not evidence that original TypeID 3057 is malformed. Existing
parallel case-parser edits are retained.

The earlier count-guard fingerprint
`B10918441CDF0888C5AF02A488754C112D733EA478F44D5106ACD9D66607FB55`
is historical. The current verified shared-source fingerprint is
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.

## Remaining behavioral questions

All 533 original diagram identities still have bounded facets; no additional
identity or whole-VI closure was claimed here. The subsequent
[saved stop-data proof](ELYSE_ACQ_SAVED_STOP_DATA_2026-10-04.md) independently
checks 69 DCO rows and four persisted False stop-control values. The inert
Python addition is an explicitly selected source snapshot, not an initializer
reset. Loaded initial controls, retained live memory and restart behavior
remain unproven. Hardware adapters are unchanged.

The local 32-bit LabVIEW diagram became visible. VI Properties showed the
original copied `ACQUISITION.llb` path, source version 12.0 and revision 200;
the LLB hash still matches
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
However, the window title has an unsaved-change marker. Those changes were
not inspected. The properties dialog is not independently targetable by
`computer-use`; one recovery attempt again returned
`failed to activate captured window`. UI input stopped and manual Cancel
was requested. No source-matched case-header screenshot was added.

Next native checks remain omitted Default metadata, Diagram Disable arm
activation, unchanged loaded-source identity and initial control values.
Full concurrency, property/event completions, I/O failures and restart also
remain outside the present proof. No VI Run/Save, XP/NI control, PSP command,
serial command or hardware write occurred.

## Reproduction and checks

Use the existing Python interpreter and shared source paths:

```powershell
$env:PYTHONPATH='C:\dev\ELYSE-ACQ-analysis\converter\lvkit\src;C:\dev\ELYSE-ACQ-analysis\converter\test-deps;C:\dev\pyconlyse\tools;C:\dev\pyconlyse'
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\python.exe' tools/validate_acq_dfds_recovery.py
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\python.exe' -m pytest -q -x -o addopts= --deny-network tests/scripts/test_elyse_acq_dfds_recovery.py
```

The initial, historical shared parser/extractor/index regression passed 108 tests in 0.93 s
with an explicit network guard. The new source proof and seven existing
bounded ACQ qualification selections passed 67 tests and 540 subtests in 85.92 s
with networking denied. All 360 heap range-field mutations are retained;
mutation tests project only checked metadata to avoid repeated copies of
full diagram bodies, while the positive source test still reads the full heap.
The isolated VI-model and source-facet register selection passed 338 tests
and 1816 subtests in 7.30 s. Each ACQ selection reported one pytest assertion
rewriting warning, not a source mismatch. Five scoped Python files pass Ruff
lint and format checks. All 17 original VI hashes and the LLB hash remain
unchanged. Historical qualification receipts retain their historical
converter fingerprints; these reruns do not silently relabel old receipts
as results from the corrected checkout.

After the count guard, the shared count/recovery/case/Supervision-parser/
extractor/index selection passed 138 tests in 1.61 s with networking denied.
This includes ten new count-guard tests and the previously separate parser
regressions. The updated source proof has eight tests rather than seven.
The new source proof and seven existing bounded qualification selections
passed 68 tests and 540 subtests in 79.72 s, with networking denied and one
pytest assertion-rewriting warning. The isolated VI-model/register selection
was separately rerun after this second correction: 338 tests and 1816 subtests
passed in 6.64 s with networking denied and one warning. Four scoped Python
files pass Ruff lint/format checks. All 17 original VI hashes and the LLB hash
still match; the final converter fingerprint is unchanged after verification.
No model or hardware-adapter source changed in that historical batch.

After the lazy-descriptor/exact-read correction, the shared recovery/count/
case/Supervision-parser/extractor/index selection passed **158 tests in 1.34 s**
with an explicit network guard. The updated DFDS source proof, saved-stop-data
proof and seven existing bounded qualification selections passed **76 tests
and 2858 subtests in 86.03 s**, with networking denied and one assertion-
rewriting warning. The isolated VI-model/register selection passed **344 tests
and 1816 subtests in 6.70 s**, with networking denied and the same warning.
The added six model tests cover the explicit source snapshot without
introducing an implicit restart reset. Ten scoped new/affected Python files
pass Ruff lint and format checks. All 17 original VI hashes and the LLB hash
remain unchanged. These are bounded regression results, not complete
Acquisition parity or a new native screenshot qualification.
