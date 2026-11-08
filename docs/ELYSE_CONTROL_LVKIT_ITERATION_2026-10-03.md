# Supervision and TRANCON: lvkit qualification iteration

Date: 2026-10-03. Scope: static translation and non-actuating Python checks.

Two small fixtures now agree with independently checked wires and Python oracles: the Supervision vacuum status helper (8192 Boolean combinations) and the TRANCON DBL logarithm helper (270 numeric values). The converter changes are packaged as a reproducible overlay. This does **not** establish complete Supervision, TRANCON, or Acquisition equivalence, and no generated control program is deployable.

## Converter and reproducibility

The upstream is [pragmatest-dev/lvkit](https://github.com/pragmatest-dev/lvkit), version 0.8.6, Apache-2.0, commit `d8058677e15c47094e725439bd72417fe9527754`. The working checkout is `C:\dev\ELYSE-ACQ-analysis\converter\lvkit`.

The [complete current overlay](C:/dev/pyconlyse/tools/control_lvkit_overlay.patch) contains eight tracked-file changes and four new source files, including the preceding ACQ fixes. Apply it to the pinned upstream, **not** on top of the earlier ACQ overlay.

| Identifier | SHA-256 |
| --- | --- |
| control_lvkit_overlay.patch | CE604F5FECF8DFDF451C01827705897A188927107293DFE0627A3D6C58DE62A9 |
| Converter source-tree fingerprint | F97E33EAAE00228F5BD9089F7335487B35319EF1FF03D91B0BA09DFC27CDC249 |
| Earlier acq_lvkit_overlay.patch, preserved | B45CC53D03742CCEA705ABDDD82214188C96414EDE2A97E2DFAA1CC42147E14D |

The fingerprint includes all Python and JSON files under the converter's `src`, including untracked overlay files. Reverse-application validation passed against the current checkout. The old evaluation virtual environment was not replaced; test dependencies were installed in separate target directories.

### Generic changes

- Preserve anonymous nested-cluster positional paths and copy changed branches rather than mutating input clusters.
- Require explicit, type-checked local-variable UID-to-control UID bindings for the reviewed sequential adapter. Front-panel order is not evidence of a binding.
- Clear reviewed bindings when a graph is reset.
- Emit DBL scalar/array `log10`, including zero, negative, infinity and NaN cases. This is deliberately limited to NumFloat64; SGL, extended precision, complex and cluster variants remain unsupported.
- Emit DBL division through an IEEE-style helper instead of raising Python `ZeroDivisionError`.
- Generate valid NamedTuple field names when a LabVIEW label normalizes to a leading underscore; reject duplicate normalized names.
- Do not annotate an error-only VI with an undefined result class.
- Reject reviewed local writes nested in case/event/loop structures until persistent state and conditional writes have an explicit model.

NI documents zero input to logarithm as negative infinity and negative real input as NaN; floating-point division by zero can produce infinity. These references support the edge-case rules, not whole-VI runtime equivalence. See [NI logarithm reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/logarithm-base-10.html) and [NI division-by-zero guidance](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z0000019Q96SAE).

## Evidence-backed fixtures

The [qualification tool](C:/dev/pyconlyse/tools/qualify_control_lvkit.py) checks source hashes, validates raw XML wires, generates twice, requires identical output, applies a narrow AST whitelist, and only then executes the two pure functions. The AST gate is not a general Python security sandbox.

### Supervision vacuum statuses

Source: `C:\dev\pyconlyse\Supervision\extracted\PILOTAGE_ELYSE_SUP\SUPERVISION_VIs\2_SUP_marche_defaut_VIDE.vi`.

Observation: six status pairs feed NOT and AND primitives. Each output is `fault AND NOT running`; preparation status passes through directly. The independent wire validator checks the associated terminals and cluster indices.

Test: all 8192 combinations of the 13 relevant Boolean inputs pass. Generated code is [supervision_vacuum.py](C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/qualification_20261003/supervision_vacuum.py).

The [archived diagram](C:/dev/pyconlyse/Supervision/analysis/screenshots/2_SUP_marche_defaut_VIDE_block_diagram_full.png) corroborates this topology. Its capture-time VI hash was not recorded. The current VI hash differs from the earlier evaluation, so the earlier hash was not silently reused:

| Artifact | SHA-256 |
| --- | --- |
| Current VI | FB7C3BE5A95B7701B8FB20DE81B6BD9CACCA108B07766F9052BAF08BA4C083B1 |
| Earlier evaluated VI | E1D2BB8D8E6D5EEB2541A06E286BADE5610B5409037D5F918923E9B270D110AF |
| Generated Python | 37CD1BD23043A997B54E802FF1E3F236D676241038D6D7B1A7F36F24EF6F47C0 |

Conclusion: static wire and Python-oracle agreement for this helper. No claim of native execution equivalence or installation-level vacuum interlock coverage.

### TRANCON logarithm

Source: `C:\dev\TRANCON\dependecies\-log bis_SD.vi`. A byte-identical, renamed parse copy avoids the leading-dash sidecar limitation.

Observation: diagram 3, division primitive UID 63 and logarithm primitive UID 202 implement `log10(1 / Transmission)`. The validator checks the 1.0 constant and numerator/denominator wire orientation, not just primitive names.

Test: 270 numeric values across ten vectors agree with independent NumPy division and logarithm calculations, including signed zero, negative inputs, infinities, NaN and extreme magnitudes. Input arrays remain unchanged; an unwired/None array yields an empty result. Generated code is [trancon_log.py](C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/qualification_20261003/trancon_log.py).

| Artifact | SHA-256 |
| --- | --- |
| Source VI | 2E1313A6D2064BB92E3371E1DF3B80A848542EFD72C4E9300C0266B95A638FA1 |
| Generated Python | B3CFA7867C8B456F606F007FF48670286004D90BCD56F03BF0064EC3AD9230D1 |

No hash-matched native diagram screenshot is available for this helper. Static proof and numerical agreement are recorded in [summary.json](C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/qualification_20261003/summary.json); native equivalence and deployment remain false.

## Untreated-VI triage

The [inventory tool](C:/dev/pyconlyse/tools/inventory_control_lvkit.py) selects 38 Supervision roots and 334 entries from the TRANCON client audit. Of the TRANCON entries, 303 lack a wire record in that audit and 31 have static wire records. These are audit classifications, not a complete coverage ledger. The 334 entries are a subset of the 1422 TRANCON VI files previously inventoried.

Each batch worker has a timeout. Successful generation is followed by Python syntax/compilation checks without importing or running the generated module. Output is quarantined as `.py.txt`, with unresolved markers and errors retained.

| Run | Selected | Generated | Failed | Timeout | Behaviorally qualified |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial Supervision, no dependency loading | 38 | 18 | 19 | 1 | 0 |
| Initial TRANCON, no dependency loading | 334 | 24 | 310 | 0 | 0 |
| Initial combined | 372 | 42 | 329 | 1 | 0 |
| Frozen TRANCON Control-Client pilot, minimal dependency loading | 12 | 6 | 6 | 0 | 0 |

The initial 329 failures comprise 177 TypeResolutionNeeded, 149 TerminalResolutionNeeded and three CodeGenError results. The Supervision root timed out after 30 seconds. These failures do not show that the original LabVIEW programs are invalid or untranslatable.

The initial manifest records 22 Supervision source hashes differing from the earlier evaluation; all 334 TRANCON source hashes match the audit ledger. Minor converter changes occurred during that first diagnostic batch, before per-worker fingerprint recording was added. Therefore the [initial manifest](C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/control_corpus_20261003/manifest.json) is a triage snapshot, not a qualification run against one immutable final build.

The [frozen pilot](C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/control_minimal_frozen_20261003/manifest.json) records the same current converter fingerprint for all 12 workers. Those same 12 entries all failed in the initial no-dependency-loading run; six now generate with minimal loading. Since both converter changes and loading mode differ between runs, that comparison does not isolate a single causal change.

Minimal loading resolves dependency interfaces/types; it does not qualify all called subVIs or execute them. Six pilot VIs generate: `Add graph.vi`, `AllConnect Status update.vi`, `BG correction.vi`, `Change FromToWave_or_Time.vi`, `Clean exp.vi`, and `Create Exp_tmp_reference.vi`. Five remaining failures require terminal resolution; `Copy from XYgraph.vi` has a code-generation error.

Marker-free generation is not a correctness criterion. For example, unreviewed local bindings can still yield plausible but incorrect arithmetic.

## Screenshot reconciliation: radioprotection graph

Source: `2_SUP_Graph _Radioprot.vi`, SHA-256 `8C3FFAB277E9A2E5346B6B4F5A657BCC8105853F26ED658B33211790C773815F`.

The [detailed findings](C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/qualification_20261003/open_findings.json) retain observations and limits.

| Native diagram observation | Converter/manual-model discrepancy | Status |
| --- | --- | --- |
| Numeric selector shows 0, Default; incoming graph ordinate passes through | Parser guesses final frame 8 as default; existing manual model instead assigns default ordinate 0 | Open |
| Outer False has no output local/indicator write | Generated result previously referenced a local defined only in True | Reviewed adapter now rejects conditional writes |
| Local UID 520 has DBL BTIM type | FP-order heuristic aliases it to a graph cluster | Explicit reviewed bindings required |
| Transition True receives previous ordinate | Generated transition uses current case output | Tunnel aliasing remains open |

Screenshots: [0, Default frame](C:/dev/pyconlyse/Supervision/analysis/screenshots/2_SUP_Graph_Radioprot_outer_true_state_0_default_lower_true_full.png) and [outer False](C:/dev/pyconlyse/Supervision/analysis/screenshots/2_SUP_Graph_Radioprot_outer_false_full.png).

Reviewed bindings are `520 -> 518`, `382 -> 2097`, and `46 -> 2403`. Correcting these bindings alone does not fix default selection, tunnel provenance or persistent state. An empty False frame retains the stored indicator value; it is not necessarily identical to the current graph input.

The existing hand-written `domain/radioprotection.py` was left unchanged because the default behavior needs reconciliation before it can serve as an oracle. Screenshot capture-time source hashes are absent, so source identity remains bounded. This graph display is not itself a hardware safety interlock.

## Verification

- Project qualification/regression suite with network denial: **54 passed, 38 subtests passed**, one assertion-rewrite warning; final run 7.14 seconds.
- Selected upstream context, code-generation, case-parser, graph, error and in-place tests: **142 passed, 32 skipped**, final run 1.51 seconds. Skips do not count as VI coverage.
- Ruff checks passed for the three new project files and two new converter node modules.
- Overlay reverse-application check passed.
- No NI, XP, PSP, serial or hardware access; no VI execution or saving. Arbitrary quarantined generated modules were not executed.

The preceding [ACQ qualification](C:/dev/pyconlyse/docs/ELYSE_ACQ_LVKIT_QUALIFICATION_2026-10-03.md) remains a separate bounded result. Its differential helper tests still pass; this iteration does not close ACQ business-logic coverage.

## Reproduction

The commands assume the pinned checkout plus overlay and the existing Python 3.11.9 evaluation interpreter. Dependencies are loaded from a separate target, not installed into the old evaluation environment.

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps'
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/qualify_control_lvkit.py

& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/inventory_control_lvkit.py --load-mode minimal --source-filter 'Control-Client' --limit 12 --output Supervision/analysis/lvkit_eval/control_minimal_REPRO_NEW

& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest -q --deny-network -o addopts= tests/scripts/test_control_lvkit_qualification.py tests/scripts/test_acq_lvkit_qualification.py tests/device_servers/control/test_elyse_acq_vi_deviation_helpers.py tests/device_servers/control/test_elyse_acq_vi_line_readback.py tests/device_servers/control/test_elyse_acq_vi_counter_writer.py
```

The inventory command refuses an existing output directory. Use a fresh run name rather than replacing evidence.

## Next qualification gates

1. Decode numeric default-frame metadata without guessing the final frame; check against a native screenshot of the exact hashed VI.
2. Resolve tunnel provenance and conditional local-write persistence, then compare every radioprotection frame against a corrected independent oracle.
3. Resolve dependency terminal identities rather than substituting unresolved calls or front-panel order.
4. Add SGL-specific arithmetic and coercion rules. TRANCON `Classes\Detector\calcOD.vi` uses NumFloat32 arrays; DBL support must not be substituted silently.
5. Extend the frozen batch to the remaining audited VIs, then the unaudited corpus. Generated text only becomes qualified after wire proof, caller/state contracts and differential tests.

**Bounded conclusion:** the iteration establishes two pure helper contracts and exposes concrete parser/state-model failures. It provides an executable qualification loop and quarantined drafts, not a complete translation of the control software.
