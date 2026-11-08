# Acquisition beam line command transfer to Python

This analysis determines which command-bank fields the two beam-line events update, which values they publish, and where the final wait occurs. Ten complete diagrams in frames 1 through 3 are checked against the original saved source. The Python implementation is an inert projection of those frames; frame 0, event delivery, concurrent reads and external-call completion remain outside its scope. Neither complete Acquisition coverage nor readiness for hardware control follows from this result.

## Source and execution boundary

The source is `C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs/0_ACQ_ELYSE.vi`, SHA-256 `6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`. Its independent XML archive is `legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`, SHA-256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`; the checked BDHb XML has SHA-256 `36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB`. The validator reads these saved files without launching or saving a VI.

| Event | Sequence | Frame 0 remains open | Frame 1 | False arm | True arm | Frame 2 publication | Frame 3 wait |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1, direct line | 11069 | 11087 | 14333 | 14348 | 14354 | 14553 | 15917 |
| 2, deviated line | 19041 | 19057 | 64765 | 64780 | 64786 | 64942 | 14963 |

The earlier event-envelope proof connects the two saved Value Change registrations to these sequences. The new proof checks their four-frame order and the Boolean sequence-local connection into frame 1. Its supplemental parent check identifies primitive 1103, a `>=` comparison between a supplied U32 input and the saved U32 constant 128. The upstream production and interpretation of that input are not reconstructed here. In particular, the Boolean must not be relabeled as an interlock permission or equated with `NewVal`.

## Conditional command copies

Both False arms are empty. A True arm reads the current beam-line cluster and separate command-bank snapshots, replaces the specified fields, and assigns each resulting whole bank to its local variable. The source has no dependency ordering between the resulting bank writes. Every device cell contains eleven fields: five Booleans, `Consigne` and `Lecture` as DBL, then four Booleans. The `Consigne` leaf is positional field 5; its flattened Bundle/Unbundle index is `12 × device_position + 6`, because the nested container also occupies an index.

| Direct source cell | Device position | Saved flattened source index | Destination bank | Destination field |
| --- | --- | --- | --- | --- |
| Correcteur H1 | 3 | 42 | C6, local 9 | 0 |
| Correcteur V1 | 4 | 54 | C6, local 9 | 1 |
| Correcteur H2 | 5 | 66 | C6, local 9 | 2 |
| Correcteur V2 | 6 | 78 | C6, local 9 | 3 |
| Correcteur H3 | 9 | 114 | C6, local 9 | 4 |
| Correcteur V3 | 10 | 126 | C6, local 9 | 5 |
| Dipôle 1 | 0 | 6 | C7, local 10 | 8 |
| Focale | 1 | 18 | C7, local 10 | 5 |
| Triplet 1-1 | 7 | 90 | C7, local 10 | 0 |
| Triplet 1-2 | 8 | 102 | C7, local 10 | 1 |
| Phase HF / Laser | 2 | 30 | C8, local 11 | 5 |

| Deviated source cell | Device position | Saved flattened source index | Destination bank | Destination field |
| --- | --- | --- | --- | --- |
| Correcteur H4 | 4 | 54 | C6, local 9 | 6 |
| Correcteur V4 | 5 | 66 | C6, local 9 | 7 |
| Correcteur V5 | 8 | 102 | C6, local 9 | 9 |
| Correcteur H5 | 7 | 90 | C6, local 9 | 8 |
| Dipôle 2 | 6 | 78 | C7, local 10 | 9 |
| Quadrupôle 1 | 0 | 6 | C7, local 10 | 6 |
| Quadrupôle 2 | 1 | 18 | C7, local 10 | 7 |
| Triplet 2-1 | 2 | 30 | C7, local 10 | 3 |
| Triplet 2-2 | 3 | 42 | C7, local 10 | 4 |

The saved label for C6 field 8 is a reserve channel, yet the wire from Correcteur H5 reaches that field. The projection preserves this discrepancy rather than correcting it by name. These copies describe command intent, not measured output voltage. They neither apply a voltage conversion nor establish electrical polarity.

Read-modify-write preservation is relative to each supplied read snapshot. If another loop changes an untouched field after that read, the saved whole-cluster write can overwrite the intervening change. The Python projection deliberately does not merge into a later global state or claim that the bank reads form an atomic transaction.

## Independent publication and final wait

Frame 2 executes after either frame-1 arm. Each event reads all four command banks again: local indices 9, 10, 11 and 12, corresponding to C6, C7, C8 and C9. Each complete ten-DBL cluster feeds its own dynamic writer at `ni.var.psp://10.20.30.2/SUPERVISION/CnNI6703`. Consequently, C9 is published although neither True arm changes it, and publication still occurs after an empty False arm.

All four writer error inputs are unwired. Each error output goes only to a separate `Simple Error Handler.vi`; all other handler terminals and the writer URL outputs are unused. There is no error-chain edge from one writer to the next. A failure on C6 therefore supplies no dataflow gate suppressing the C7 through C9 requests. This statement concerns the saved graph, not network delivery or the timing of modal error-handler UI.

The stacked sequence places a `Wait(ms)` request of 100 after the entire publication frame completes. A blocked writer or error handler can prevent that completion. The wait is not a fixed upper bound on event duration, and it is not evidence that hardware has settled within 100 ms. The Python API returns the wait argument; it does not sleep or assume external completion.

## Python implementation and converter comparison

`DeviceServers/control/elyse_acq/vi_simulation/beamline_commands.py` provides three separate operations:

- `project_setpoint_frame`: an explicit Boolean chooses the empty arm or returns whole-bank write records from typed snapshots.
- `project_publication_frame`: fresh C6 through C9 snapshots produce four independent request records, without transport or implicit use of the earlier projected writes.
- `terminal_wait_ms`: returns the saved wait argument; scheduling it after the preceding frame completes remains the caller's responsibility. It does not implement or validate completion.

The shared updated converter at `C:/dev/ELYSE-ACQ-analysis/converter/lvkit` generated only the reviewed Bundle/Unbundle fragments. Parsed terminal identities, directions and flattened field indices are first compared with the independent XML proof. Executable syntax is restricted to local assignments, tuple indexing and the audited pure `replace_fields` helper; imports, attribute access, unresolved names, loops, arithmetic and fixture reassignment are rejected before execution. Whole-VI generation and execution are excluded.

Loading the main VI also produced DFDS and STR parser warnings:

```text
Warning: Block b'DFDS' section 0 parse exception: LVVariant has no linked TD  but is supposed to have DataFill.
Warning: Block b'DFDS' section 0 size is 56852 and does not match parsed size 0
Warning: Block b'STR ' section 32 parse exception: LVVariant has no linked TD  but is supposed to have DataFill.
Warning: Block b'STR ' section 32 size is 209 and does not match parsed size 139
```

The reviewed graph nodes still loaded, and their tested port identities and field indices matched the independent XML. All executed fragment inputs are supplied fixtures rather than defaults recovered from DFDS. The comparison therefore qualifies these copies without qualifying the warned sections or the whole parser output.

For converter fingerprint `7C33FBFE65696D162E7826588EA6692F833C0920ADF556061A3520AB43C80533`, all 520 event fixtures matched the independent projection: 1,300 bank results and 13,000 DBL values. Comparison uses hexadecimal float representations, retaining the distinction between positive and negative zero. Fixtures include positive and negative zero, ±1e200, and deterministic random values. Input snapshots remained unchanged, and the converter fingerprint was unchanged throughout qualification. No converter correction was required for these fragments. The saved receipt is `legacy/xp_acq_agent/data/converter_qualification/20261003_beamline_tail_shared/receipt.json`; its fingerprint identifies the tested snapshot, not an assertion that a concurrently edited checkout will remain unchanged.

## Reproduction and limits

The broader offline regression run passed 285 tests in 67.70 s, covering all `test_elyse_acq_vi_*.py` modules plus the new wire/converter gates, source-facet register and translation-source checks. Ruff checks passed for all seven changed Python files. The single pytest warning was `PytestAssertRewriteWarning: Module already imported so cannot be rewritten; scripts.refactor.pytest_module_isolation`; it is distinct from the converter's DFDS/STR warnings above. Mutation tests reject changed local directions/indices, Consigne fields, Boolean selection, extra operations, error edges, connector slots and wait literals. The converter test denies socket connections.

Run in the existing Python 3.11 evaluation environment with the shared converter, test dependencies, repository and `tools` directories on `PYTHONPATH`:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_beamline_commands.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/qualify_acq_beamline_fragments.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest -q tests/device_servers/control/test_elyse_acq_vi_beamline_commands.py tests/scripts/test_elyse_acq_beamline_command_wires.py tests/scripts/test_acq_beamline_fragment_qualification.py tests/scripts/test_elyse_acq_source_facet_register.py
```

The source-facet register adds only the ten complete tail diagrams, increasing named identities from 371 to 381 within the 533-diagram original census. There are 152 diagrams without a cross-indexed facet: 109 in the main VI and 43 in helpers. These are accounting counts, not a behavioral coverage percentage; some earlier helper evidence remains outside the register. The partial comparator check does not register either frame 0 as complete.

The separate [frame-0 adjustment analysis](ELYSE_ACQ_BEAMLINE_ADJUSTMENT_2026-10-03.md) now checks both difference conversions, property-node graphs, numeric cases and increment/decrement bounds:52 diagrams and424 nets. That bounded model retains unverified outer-default and property-failure behavior. Source-matched native screenshots, event scheduling, asynchronous state integration, external failure completion, normal/fault shutdown and restart remain separate obligations. No new screenshots or Word rendering were produced in either step, and no XP, NI, PSP, VISA or serial action was performed.
