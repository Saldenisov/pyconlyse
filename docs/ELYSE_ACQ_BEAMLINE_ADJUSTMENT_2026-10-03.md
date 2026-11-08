# Acquisition beam line adjustment and change detection

The two beam-line events first identify a changed device, adjust its displayed setpoint for an explicit arrow-button case, reset four button fields and write the resulting cell through its `Value` property. This analysis checks all 52 saved frame-0 diagrams and 424 direct wire nets. The independent Python projection reproduces the explicit cases without operating a UI or hardware. Missing native default evidence, property failure returns and concurrent read epochs prevent a claim of complete event behavior.

## Source and checked diagrams

The original source is `C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs/0_ACQ_ELYSE.vi`, SHA-256 `6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`. The independent root archive is `legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`, SHA-256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`; its BDHb XML has SHA-256 `36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB`.

| Event | Frame 0 | Difference For body | Main numeric selector | Flat wait frame | Diagrams | Direct nets |
| --- | --- | --- | --- | --- | --- | --- |
| 1 direct line | 11087 | 11283 | 11557 | 14167 | 30 | 248 |
| 2 deviated line | 19057 | 62765 | 63039 | 64597 | 22 | 176 |

`tools/validate_acq_beamline_adjustment.py` checks every direct operation and wire fanout in these subtrees. The proof includes the six explicit outer pass-through diagrams, eight button diagrams, 24 scalar adjustment diagrams, eight nested default diagrams, two For bodies, two flat wait frames and two parent diagrams. These identities are source-graph facets, not substitutes for source-matched LabVIEW screenshots or native execution evidence.

## Change selection precedes adjustment

Each device cell contains five Boolean fields, two DBL fields and four Boolean button fields. `Not Equal?` uses elementwise comparison of `OldVal` and `NewVal`. The nested result is converted to an array of per-device Boolean clusters; an auto-indexed For loop converts each cluster to a Boolean array and then to a U32 bit number. Bitwise AND with the saved constant `0x791` retains only fields 0, 4 and 7 through 10:

| Field | Meaning | Retained mask |
| --- | --- | --- |
| 0 | M/A | 1 |
| 4 | X1/X10 | 16 |
| 7 | << | 128 |
| 8 | < | 256 |
| 9 | > | 512 |
| 10 | >> | 1024 |

Status fields 1 through 3, `Consigne` at field 5 and `Lecture` at field 6 are excluded. Consequently, a change only to the numeric setpoint produces no retained change bit in this event. This does not establish how other command paths handle a setpoint change.

`Array Max & Min` supplies the maximum mask to the main selector and its first index to both the device selector and `Controls[]` indexing. Different devices' masks are not OR-ed together. If two devices have the same maximum, the first index is selected; a maximum of zero selects index 0. Changes on button release also count as differences: this path does not test only a rising edge.

The U32 comparison `maximum >= 128` feeds the Boolean sequence local consumed by frame 1. This is a change-class gate, not an interlock permission. For example, device masks 128 and 1024 select the latter device and case 1024, whereas mask 129 from simultaneous M/A and `<<` changes is not one of the explicit main cases.

## Explicit cases and adjustment bounds

Explicit main cases 0, 1 and 16 pass seven retained fields unchanged. Cases 128 and 256 subtract a selected step; cases 512 and 1024 add it. The Boolean `X1/X10` selects the small step when False and the large step when True. Each arithmetic result passes through `In Range and Coerce`; only its coerced DBL output is connected. The separate in-range Boolean is unused.

| Event and source device positions | Bounds | Small and large steps for << or >> | Small and large steps for < or > |
| --- | --- | --- | --- |
| Direct 1, Focale | 0 to 120 | 1, 10 | 0.1, 1 |
| Direct 2, Phase HF / Laser | 0 to 180 | 5, 50 | 1, 5 |
| Direct 0, 7, 8 | -16 to 16 | 0.1, 1 | 0.01, 0.1 |
| Direct 3 to 6, 9, 10 | -5 to 5 | 0.1, 1 | 0.01, 0.1 |
| Deviated 0 to 3, 6 | -16 to 16 | 0.1, 1 | 0.01, 0.1 |
| Deviated 4, 5, 7, 8 | -5 to 5 | 0.1, 1 | 0.01, 0.1 |

These are saved software values. Physical units, electrical scaling and safe operating limits are not inferred from these constants. The scalar calculation is `requested = current ± step`, followed by clipping to the corresponding bounds. All 80 device/button combinations are tied to the original nested selector ranges and wired literals. Nested selectors explicitly identify their default diagrams as 04 for the direct line and 02 for the deviated line; those diagrams pass `Consigne` unchanged, without clipping.

The main selectors differ: both omit `SelectDefaultCase`. The current shared lvkit parser interprets an omitted scalar default index as zero, supported by earlier native evidence from other selectors. That converter interpretation is not independent native confirmation for these two ACQ selectors. The simulation therefore raises `UnverifiedOuterDefaultError` for combined masks such as 129 or 384 instead of silently executing an inferred default. An exact source-matched native view of the default case would discriminate this interpretation without running the VI.

## Property snapshot and sequence dependencies

The selected line reference is downcast to a cluster reference. Its `Controls[]` property yields an array of control references; `Index Array` selects the reference at the maximum-mask index. The selected control's `Value` property is read and passed through `Variant To Data` with an eleven-field typed constant. This is a separate read epoch from the event's `OldVal` and `NewVal`. The projection therefore requires `current_selected_cell` explicitly and does not substitute `NewVal`.

Seven unbundled fields enter the main selector. Six are preserved across the adjustment cases; only `Consigne` is recalculated. A separate single-frame flat sequence passes the resulting setpoint, supplies False to all four button fields and requests `Wait(ms)` with argument 70. The subsequent Bundle uses the typed zero cell as its base, replaces all eleven fields and feeds the selected control's plain `Value` property, not `Value (Signaling)`.

The write depends on the flat frame's outputs, so that frame must complete before the assembled value reaches the property write. Operations inside the frame remain unordered. The 70 ms argument is a wait request, not measured settling time, a scheduler deadline or a guarantee about hardware response.

The cast, property reads, variant conversion and property write have unwired error outputs and no error dependency gating this path. Native failure outputs are not assumed successful or reconstructed here; the fixture represents an explicitly supplied typed conversion result. Event scheduling, property reentrancy and actual UI effects remain outside the model.

After frame 0, frame 1 conditionally copies setpoints into command-bank locals using its own later snapshots. Frame 2 independently rereads and publishes C6 through C9 after either frame-1 arm, followed by the separate 100 ms terminal wait request. Those already checked graphs are documented in [the beam-line command transfer analysis](ELYSE_ACQ_BEAMLINE_COMMANDS_2026-10-03.md). The frame-0 property snapshot, frame-1 line/bank reads and frame-2 publication reads are not collapsed into an atomic transaction.

## Converter comparison and reproduction

`beamline_adjustment.py` contains the finite-DBL projection. `tools/qualify_acq_beamline_adjustment.py` generates only the 24 reviewed `Select` → `Add` or `Subtract` → `In Range and Coerce` fragments from the updated shared checkout. Original XML supplies constants and terminal bindings independently. A strict AST allowlist permits only scalar assignments, fixture-selected conditional expressions, addition/subtraction and two-argument `min`/`max`; imports, attribute access, unresolved names, loops, other calls and input reassignment are rejected before execution.

All 9,600 finite scalar fixtures matched hexadecimal DBL results, including both scale modes, bounds, over-range inputs, clipping transitions and adjacent representable values. No lvkit correction was required for these 24 chains. The tested converter fingerprint is `7C33FBFE65696D162E7826588EA6692F833C0920ADF556061A3520AB43C80533`; it remained unchanged during qualification. The fixture digest is `FC32599973F4F6B8F8609ACD7F43D71FCE10B158338E42F3254419F8C4F6F96D`. Generated fragments and these metadata are saved in `legacy/xp_acq_agent/data/converter_qualification/20261003_beamline_adjustment_shared/receipt.json`.

The main-VI loader retains the previously documented DFDS/STR warnings about variant data without a linked type descriptor. No result here qualifies those sections or infers default data from them. Only reviewed scalar graph fragments execute, using supplied fixtures; NaN/Inf, full generated events and property-node execution are excluded. Network connections are denied in the qualification test.

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_beamline_adjustment.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/qualify_acq_beamline_adjustment.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest -q tests/device_servers/control/test_elyse_acq_vi_beamline_adjustment.py tests/scripts/test_elyse_acq_beamline_adjustment_wires.py tests/scripts/test_acq_beamline_adjustment_qualification.py tests/scripts/test_elyse_acq_source_facet_register.py
```

The targeted run passed 20 tests. The broader offline regression run passed 301 tests in 116.02 s, covering every `test_elyse_acq_vi_*.py` module plus translation-source checks, the register and both beam-line wire/converter gates. The single warning was `PytestAssertRewriteWarning: Module already imported so cannot be rewritten; scripts.refactor.pytest_module_isolation`. Mutation checks reject altered arithmetic, elementwise comparison, nested default/ranges, For indexing, property identity/direction, Bundle fields, the change mask, the wait constant and wire endpoints. Ruff checks passed for the seven changed Python files. All 17 original VI hashes remained unchanged.

## Remaining Acquisition obligations

The register now contains 433 unique named source-graph identities within the original 533-diagram census. The 100 identities without a registered facet comprise 57 main-VI diagrams and 43 helper diagrams; earlier evidence for some helpers has not yet been cross-indexed. These are accounting counts, not a behavioral coverage percentage. `whole_acquisition_closed` and `native_evidence_complete` remain False.

For these beam-line events, the immediate gaps are source-matched native default evidence, property/cast/variant failure returns, nonfinite inputs and event/concurrency integration. The broader remaining work includes lifecycle coordination, normal/fault-stop completion and restart. No new native screenshots or Word renderings were produced; no XP, NI, PSP, VISA, serial or hardware action was performed. This result advances an offline simulation and does not authorize deployment.
