# Acquisition persisted stop values and runtime-reset boundary

## Question and result

Does the copied Acquisition VI contain known stop-control values, and do
those values establish startup or restart behavior? The saved data answers
the first question: four stop controls contain Boolean byte `00` (False).
It does not answer the second. A persisted source snapshot, a loaded control
value and an explicit diagram-local reset are distinct observations.

The proof reads the unchanged original VI in memory with corrected shared
lvkit, independently decodes its DCO table, and joins the four data slots to
original front-panel identities and the previously traced local references.
No VI, generated program or hardware adapter executes.

## Original source and independent table decode

Source: `C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs/0_ACQ_ELYSE.vi`.
SHA256: `6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
Decompressed DFDS: 56852 bytes, SHA256
`33C3D8AF2CE159F83C547013E8339964DF4E26520F6917A211CBEA83D78C03D5`.

The DSINIT descriptor `000a0064000000330073` specifies 51 I32 values.
Independent big-endian decoding of bytes 0–204 matches all 51 parsed values;
the interval hash is
`81BE850DD2F3A39EC4D1CA9A1E4E4C19899973DD63ECF72EBEA74EC0105CD45B`.
DSINIT field 6 records 69 DCOs; field 8 records TMI 4682. TM80's index shift
is 25, resolving that table to consolidated TypeID 4707.

The DCO repeated-block descriptor is `000a006400000045060e` (69 rows).
Its DFDS interval 49079–54323, end excluded, contains 69 × 76 = 5244 bytes,
SHA256 `6FBA7E6C07F987BFE62230046D5D257D8D0839C1967DC3F3756C336DCBEF262C`.
A separate `struct.Struct('>hHBBBbiiiiiBBBBiiiiiBBBBBBBBi4s4s4s')` decoder
matches all 32 fields in each row: 2208 field comparisons. DCO indices are
exactly 0..68. Field tags are checked separately against the parsed structure.

For each selected stop row, `defaultDataTMI` (field 8) is -1. The persisted
slot is instead reached through `flagTMI` (field 7), masked to its low 24 bits
and shifted by 25. This proof does not reinterpret that slot as a native
Default Value property. Each selected record has flags 4100 (`0x1004`),
selected client index 1, one Boolean value and matching exact label bytes.

## Four stop-control identities

| Local bank | Exact source label | Persisted TypeID | DFDS byte offset | Saved value | FP control UID | DDO UID | Heap type |
|---|---|---|---|---|---|---|---|
| 30 | stop | 3219 | 36659 | False (`00`) | 1732 | 1627 | 21 |
| 45 | TCP ED | 3327 | 41153 | False (`00`) | 44213 | 11783 | 15 |
| 46 | stop urgence | 3254 | 38492 | False (`00`) | 45855 | 45845 | 339 |
| 47 | Arrêt général | 3257 | 38493 | False (`00`) | 40749 | 40722 | 19 |

Original front-panel control descriptors, `stdBool` display objects and exact
labels match these rows. All 20 previously identified gRefs resolve to the
same Boolean labels and parameter indices: nine for bank 30, five for 45,
four for 46 and two for 47. This supplies an explicit identity bridge from
persisted data to diagram-local memory; it does not observe a running VI.
Label bytes are matched as Latin-1, including the accents in `Arrêt général`.
No global resource-string encoding change is introduced.

## Inert Python transfer and reset counterexample

[saved_stop_data.py](../DeviceServers/control/elyse_acq/vi_simulation/saved_stop_data.py)
adds only `saved_source_stop_snapshot()`, returning a fresh immutable
`StopMemory(False, False, False, False)`. The module has no transport,
hardware, adapter or file access. No startup, Tango or engine path calls it
implicitly. A caller must explicitly choose this source-data fixture.

Previously proved diagram-local writes remain unchanged:

| Completed phase | Literal assignments | Not reset by that phase |
|---|---|---|
| post_init | 45=False; 46=False | 30; 47 |
| controlled_complete | 46=True; 47=False | 30; 45 |
| final_cleanup | 30=False | 45; 46; 47 |

The discriminating restart fixture supplies stale memory
`StopMemory(True, True, True, True)`. Applying only `post_init` gives
`StopMemory(True, False, False, True)`, even if a separate saved-source
snapshot has been constructed. Thus the known saved False bytes do not
justify adding startup resets for banks 30 or 47. Native loading/restart
semantics or a separate explicit reset path would be needed to make that
claim. Selecting four False values is not a physical deenergization operation.

## Reproduction and verification

[validate_acq_saved_stop_data.py](../tools/validate_acq_saved_stop_data.py)
checks source/hash/record boundaries, independent tables, four typed slots,
front-panel identities and all 20 local references. Positive tests read
original full heaps; mutation tests project only checked metadata.

```powershell
$env:PYTHONPATH='C:\dev\ELYSE-ACQ-analysis\converter\lvkit\src;C:\dev\ELYSE-ACQ-analysis\converter\test-deps;C:\dev\pyconlyse\tools;C:\dev\pyconlyse'
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\python.exe' tools/validate_acq_saved_stop_data.py
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\python.exe' -m pytest -q -x -o addopts= --deny-network tests/scripts/test_elyse_acq_saved_stop_data.py tests/device_servers/control/test_elyse_acq_vi_saved_stop_data.py
```

The focused source/model lane passed 13 tests and 2315 subtests in 9.91 s,
with one pytest assertion-rewriting warning. Mutations cover all 2208 DCO
fields, all 51 DSINIT values, four persisted-byte flips, 24 typed-slot fields,
eight front-panel identity fields and 20 gRef indices. Six inert-model tests
check freshness/immutability, explicit source selection, post-init behavior,
stale-memory preservation and cleanup/reset boundaries.

The final broader source/qualification selection passed 76 tests and 2858
subtests in 86.03 s; isolated VI-model/register tests passed 344 tests and
1816 subtests in 6.70 s. Both denied external networking and reported one
assertion-rewriting warning. Shared lvkit's bounded recovery/parser/index
selection passed 158 tests in 1.34 s with an explicit network guard. The
verified shared-source fingerprint is
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.
Ten scoped new/affected Python files passed Ruff lint/format checks. All
17 original member hashes and the source LLB hash remain unchanged.

## Remaining Acquisition gates

All 533 original diagram identities already have bounded facets; this proof
adds no census identity or whole-VI closure. The four persisted values are
now proved; live initial values and native restart remain open. Omitted
Default cases, Diagram Disable activation, external property/error/default
returns and complete concurrent event/I/O/fault schedules remain separate
gates. No source-matched native screenshot or Word revision was added.
No Supervision review, VI run/save, XP/NI control, PSP/VISA/serial command
or hardware write occurred.
