# Acquisition saved WCM state and measurement publication

The original Acquisition VI stores four empty measurement arrays, not arrays
filled with four zeros. Its WCM counter and display selector are stored as zero.
This distinction changes the admissible first-iteration fixtures and exposes
three separate short-array conversion boundaries in VAM-A. The Python
projection now preserves those empty arrays instead of rejecting them or
inventing initialization writes. Stored values remain separate from the values
actually loaded or retained by a native LabVIEW invocation.

## Original source evidence

The source is `0_ACQ_ELYSE.vi`, SHA256
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The decompressed DFDS has 56852 bytes, SHA256
`33C3D8AF2CE159F83C547013E8339964DF4E26520F6917A211CBEA83D78C03D5`.
The [saved stop proof](ELYSE_ACQ_SAVED_STOP_DATA_2026-10-04.md) already checks
the DSINIT population and all 69 DCO rows against independent binary decoding.
Its shared control-table reader/checker is now reused without changing the
four stop-value contracts.

The [measurement validator](../tools/validate_acq_saved_measurement_data.py)
joins seven DCO indices to their typed DFDS records. It measures the consumed
record intervals through an exact-length, in-memory reparse, then independently
unpacks the original bytes at fixed offsets. No serializer, generated VI code
or expected-size estimate supplies these offsets. The reparse consumes all
56852 bytes; that does not certify the semantics of every DFDS record.

Each DCO row has `defaultDataTMI=-1`; its other data reference resolves through
the checked type-map shift 25 to the record below. Absence of a separate
default-data reference is therefore not absence of stored data. Exact cluster
descriptors, client index 1, labels, scalar types and one-dimensional DBL array
types are checked against the source and original front-panel identities.

| Local bank | Exact saved label | Typed record | DFDS interval, end excluded | Saved value | Front-panel control and DDO |
|---:|---|---:|---|---|---|
| 59 | `C1_NI6259_0:3,7,9` | 3345 | 41202..41206 | Array dimension 0, no elements | 100281 / 44443 |
| 62 | `B6220` | 3351 | 41218..41222 | I32 0 | 62058 / 57884 |
| 63 | `Voies:` | 3279 | 39009..39011 | U16 0 | 276502 / 276473 |
| 65 | `C1_NI6259_4:7` | 3355 | 41230..41234 | Array dimension 0, no elements | 80694 / 80662 |
| 66 | `C1_NI6259_4:7 Max` | 3357 | 41234..41238 | Array dimension 0, no elements | 148174 / 148142 |
| 67 | `C1_NI6259_4:7 Min` | 3359 | 41238..41242 | Array dimension 0, no elements | 185695 / 185663 |
| 68 | `Iteration WCM` | 3361 | 41242..41246 | U32 0 | 52015 / 52000 |

These are 26 independently decoded bytes: four array-dimension words and three
scalar values. The array entries are absent, not hidden DBL zero entries. The
legacy NI6259 labels do not identify the active card: the previously qualified
runtime caller invokes `1_ACQ_READ_NI6220.vi`.

## Assignment ownership

The same validator checks all 21 root `gRef` sites belonging to these banks,
including each terminal, saved read/write flags, type, label and containing
diagram. All sites belong to runtime acquisition or VAM-A publication; there
are no additional initializer or final-cleanup `gRef` writers in this population.
This is a whole-root local-reference census, not exclusion of primary-terminal,
UI, property, VI Server or additional-invocation effects.

| Bank | Direct local assignments | Direct local reads |
|---:|---|---|
| 59 | Six point-mean results in frame 48574 | VAM-A frame 45859 |
| 62 | NI6220 loop iteration in body 47487 | VAM-A frame 46898 |
| 63 | None | Display selection in frame 48574 |
| 65 | Current four-entry WCM array in both change arms | Prior mean and old-baseline tunnel in frame 47080, flags 5 retained |
| 66 | Current WCM array only in counter-3 arms 100569 and 81868 | VAM-A frame 46898 |
| 67 | Old bank65 array in True change arm 206856 | VAM-A frame 46898 |
| 68 | Two increment arms and two zero-reset capture arms | Two case selectors and two independent increment reads |

The [runtime wire proof](ELYSE_ACQ_NI6220_RUNTIME_TRACE_2026-10-03.md) already
establishes the individual assignments and exact nets. This continuation adds
their saved data associations and completes the local census for banks
59/62/63/66/67, rather than reclassifying existing diagrams as newly covered.

## Conditional first iteration

The source builds four current values from reader indices 4, 5, 6 and 7.
Missing indexed entries return DBL 0.0, but the previous array passed to Mean
is still independently sampled bank65; an empty bank65 is not replaced by four
zeros. Both NI Mean returns remain explicit external boundaries.

The following consequences hold only when the saved snapshot is explicitly
selected as the prior state and the listed helper returns are supplied:

| Supplied previous Mean return | Comparison and counter state | Completed frame consequence |
|---|---|---|
| NaN | `current_mean > NaN + 0.03` is False; selector 0 | Current four-entry array replaces bank65; bank66 and bank67 remain empty; counter is not written |
| Finite value satisfying `current_mean > previous_mean + 0.03` | True; selector 0 | Counter receives the supplied Increment return; old empty bank65 is copied into bank67; bank66 remains empty |
| Either return, selector 3 supplied independently | Either explicit capture arm | Current four-entry array replaces bank66 and counter becomes 0 |
| Finite rising comparison, selector 1 | True, unmatched numeric selector | Counter arm/result remains unresolved; no guessed Default or capture |

The first two rows are competing boundary fixtures, not assertions about the
native result of `Mean(empty)`. The next returning iteration can use the newly
written four-entry bank65. Neither this fact nor a stored zero counter establishes
native loading, clear-on-call behavior or restart reset.

The prior Python requirement that banks65/66/67 always contain four entries
was too narrow. `ni6220_runtime.counter_frame` now accepts any immutable DBL
array length for those explicitly supplied snapshots. Its current Build Array
still has exactly four entries. No Mean implementation, initialization reset,
counter default, transport or hardware adapter was added.

## VAM-A conversion and independent sampling

The saved VAM-A code has three separate Array To Cluster sites:

| Primitive UID | Local array | Required conversion result | Published fields |
|---:|---:|---:|---|
| 44469 | 59 | Eight DBLs | VAM-A 12..18; eighth cluster entry unused |
| 47023 | 66 | Four DBLs | VAM-A 32..35 |
| 62377 | 67 | Four DBLs | VAM-A 36..39 |

The first conversion was already an explicit boundary for the six-element
point-mean producer. Saved empty bank59 also fits that boundary before any
chosen update. The two WCM conversions now have the corresponding
`vam_status.second_frame_from_conversions` entry point. Each requires its own
supplied cluster return and checks all existing source entries. Missing entries
are neither zero-filled nor copied from an assumed previous cluster.

A supplied fixture may therefore publish a newly captured bank66 alongside an
older empty bank67. Their local reads, and the separate bank62 iteration read,
do not certify one coherent measurement epoch. Ordered VAM-A frames preserve
the preceding pressure assignments; they do not order the separate NI6220
writer loop against both WCM reads. No same-time physical measurement or
atomic multi-bank snapshot is inferred.

The conversion consistency check also accepts independently created NaNs and
preserves infinity and signed-zero distinctions. It does not certify native
NaN payload bits. Explicit padded boundary values remain supplied fixtures,
not reconstructed measurements or proved NI short-array behavior.

## Reproduce and remaining limits

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/validate_acq_saved_measurement_data.py
& C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest --deny-network -q -x -o addopts= tests/scripts/test_elyse_acq_saved_measurement_data.py tests/scripts/test_elyse_acq_saved_stop_data.py tests/scripts/test_elyse_acq_ni6220_runtime.py tests/scripts/test_elyse_acq_runtime_local_registers.py tests/scripts/test_elyse_acq_vam_status.py tests/device_servers/control/test_elyse_acq_vi_saved_measurement_data.py tests/device_servers/control/test_elyse_acq_vi_ni6220_runtime.py tests/device_servers/control/test_elyse_acq_vi_vam_status.py
```

The final complete VI-model/register selection passed 410 tests and 1942
subtests in 7.81 s. The final focused source/model selection above passed
64 tests and 2560 subtests in 89.19 s. Both runs denied network access and
reported one existing assertion-rewriting warning. A misplaced validation
loop in a new test was corrected before these final runs; controller logic
was not changed to accommodate that test-only NameError.

Eight scoped Python files pass Ruff lint checks. All 17 original VI hashes and
the source LLB still match. Shared lvkit was not changed; its fingerprint remains
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.
No native screenshot, VI Run/Save, XP/NI control, PSP/VISA/serial command,
hardware write, commit or deployment occurred.

Open boundaries remain native `Mean(empty)`, point-mean state/default inputs,
short Array To Cluster returns, unmatched True-counter dispatch, live control
loading and restart retention. Full cross-loop scheduling and indirect actors
are not certified by these fixtures. The original 533 diagram identities retain
their bounded source facets; whole Acquisition is not declared complete.
