# Acquisition fixtures for lvkit loop and property translation

Date: 2026-10-03. Scope: original Acquisition VI files, static wires, and isolated non-actuating Python fragments.

The NI6602 writer exposed two generic converter defects: the While Loop iteration terminal became constant zero, and Property Nodes consumed reference/error terminals as property values. The current overlay fixes those mechanisms. Twenty-three polling traces and four timing vectors agree with the bounded component contract. The complete writer remains rejected because its error wire is unresolved; no hardware-facing program is qualified for deployment.

## Source and converter identity

The input is the original ACQUISITION.llb member set, not similarly named Supervision copies. All 17 member hashes match the pinned extraction manifest. The LLB SHA-256 remains EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A.

| Artifact | SHA-256 |
| --- | --- |
| 1_ACQ_WRITE_NI6602.vi | 4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211 |
| Original member manifest | 1DCE49EAD711CBDD7AB75578D5655AACEFA6A47C6B445D8FED2C4D402A0A37E0 |
| Converter source fingerprint | C77D2D71CC03E68ABFA0A9E0565F92DDD8A8CD5DEA08311AF7DC7F47C2D05AC6 |
| acq_counter_lvkit_overlay.patch | C3B325801D74B203CA64BF3ACEB5488129084874ED2974437E18A3BD00B5EB27 |

The [complete overlay](C:/dev/pyconlyse/tools/acq_counter_lvkit_overlay.patch) applies to lvkit upstream commit d8058677e15c47094e725439bd72417fe9527754. It includes earlier ACQ/Supervision/TRANCON fixes plus this iteration: ten modified source files, one modified upstream test fixture, and four new source files. Apply it to that clean upstream commit, not on top of either earlier overlay. Reverse-application and whitespace checks passed. The earlier overlays and evidence were preserved.

## While Loop iteration

The archived wire validator checks the actual NI6602 writer, including loop UID 3129, iteration terminal 3155, Stop-if-True polarity, and the predicate Done == True OR i > 20. The prior converter emitted 0 > 20, making the bounded exit unreachable when Done stayed false.

The emitter now binds the terminal to a loop-specific counter initialized to zero. It evaluates the stop predicate before incrementing and saturates at I32 maximum rather than rolling over. Zero-based counting and saturation are documented by [NI](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z000001DcZJSA0&l=en-US). The [LabVIEW loop documentation](https://www.ni.com/en/support/documentation/supplemental/08/labview-for-loops-and-while-loops-explained.html) confirms that the body executes before the condition is evaluated.

The [qualification tool](C:/dev/pyconlyse/tools/qualify_acq_counter_components.py) tests Done first becoming true at each index 0–21, plus a trace where it never becomes true. It compares the isolated emitted fragment against the existing scripted-boundary model:

| Supplied Done sequence | Polls | Final i |
| --- | ---: | ---: |
| True at index 0 | 1 | 0 |
| True at index 20 | 21 | 20 |
| True at index 21 | 22 | 21 |
| False throughout | 22 | 21 |

All 23 traces agree. A separate test executes only the generated counter-tail statement at 2147483646 and 2147483647, checking saturation without running billions of iterations. Wait(1 ms) is recorded by a fake clock, not performed or measured.

## Property Node terminal identities

The parser already records the structural distinction between growable property rows (dcoList) and fixed reference/error terminals (permDCOList). The old emitter ignored that information and selected the first wired output/input for each property. Consequently, the pulse-Done comparison used a task-like reference, and downstream task operations could receive a Boolean or property value.

The emitter now correlates properties with their recorded value-terminal IDs, preserves row order, and treats reference/error flow-through separately.

| Node UID | Role | Value terminal UIDs |
| --- | --- | --- |
| 3202 | Read CO pulse Done | 3216 |
| 3083 | Write initial-delay, low, high ticks | 3097, 3103, 3109 |

Four already-integer timing vectors verify assignment order and values: delay feeds both initial-delay and low ticks; width feeds high ticks. These tests operate only on an in-memory fake task. Reference outputs remain bound to task; nominal error outputs remain bound to the explicitly supplied error object, never to a property value.

Additional tests cover mixed read/write rows, repeated ordered access to the same property, a Refnum-valued property, missing/duplicate row identities, normalized-name collisions, unwired writes, unresolved errors, implicit references and rejected hardware/import/dunder calls. Missing evidence causes a generation error instead of a guessed access.

This is a nominal wiring contract, not a DAQmx error implementation. Error gating, errors raised by individual rows, driver-returned task changes and Clear Errors behavior are not qualified. The full NI6602 writer now fails with “property error input is unresolved”; the old incorrect module is not promoted to executable code.

## Numeric coercion discrepancy

The archived XML heap-to-consolidated-to-flat type chain identifies both conversion outputs as NumInt32, while timing property inputs are NumUInt32:

| Terminal UID | Heap TypeID | Consolidated TypeID | Flat type | Representation |
| --- | ---: | ---: | ---: | --- |
| 201 | 104 | 201 | 19 | NumInt32 |
| 163 | 106 | 203 | 19 | NumInt32 |
| 3097 | 61 | 158 | 112 | NumUInt32 |
| 3103 | 64 | 161 | 113 | NumUInt32 |
| 3109 | 67 | 164 | 114 | NumUInt32 |

The new independent validator checks this chain against the pinned archive; a mutated representation is rejected. The earlier validator's concluding label “U32 conversions” was corrected to name primitive 1142 and leave property-input coercion separate.

The existing manual labview_u32_ticks model directly converts the product to U32. That shortcut does not establish the intermediate I32 conversion or subsequent I32-to-U32 coercion, particularly outside the common finite nonnegative I32 range. The manual model was not silently rewritten. The timing-fragment vectors start from supplied ticks and do not test numeric conversion. Integer saturation, negative values and nonfinite inputs require a separate qualification profile.

## All original Acquisition members

The [inventory tool](C:/dev/pyconlyse/tools/inventory_control_lvkit.py) now accepts --corpus acquisition. It verifies the pinned manifest and all member hashes, refuses changed Acquisition inputs, and probes each member in a subprocess with a 30-second timeout. Generated modules are compiled for syntax checks but never imported or executed.

The [frozen batch manifest](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_corpus_final/manifest.json) records:

| Outcome | Members |
| --- | ---: |
| Generated quarantined Python text | 10 |
| Generation failed | 7 |
| Timed out | 0 |
| Behaviorally qualified by this batch | 0 |

All 17 members parsed successfully and all 17 completed workers record the same current converter fingerprint. All 17 source hashes remain unchanged. The ten drafts retain 56 unresolved diagnostics in aggregate. No reviewed local-variable bindings were supplied in this batch, including for the two comparison helpers that have separate qualification profiles.

The three AI reader VIs fail terminal resolution for Mean.vi. Both focal helpers fail resolution for chr62000 Initialize.vi. NI6602 writing fails the unresolved error-input gate. The root 0_ACQ_ELYSE.vi parsed in the final run but failed terminal resolution for System Exec.vi. An earlier run timed out at 30 seconds; that earlier manifest is preserved separately. These are review priorities, not evidence that the original LabVIEW software is invalid.

## Verification and evidence

- Targeted converter, source-mutation and pure-model tests: 85 passed, 43 subtests passed, one assertion-rewrite warning.
- Entire existing Acquisition controller/pure-model test lane: 272 passed, 593 subtests passed, one assertion-rewrite warning.
- Selected upstream builder, loop, sequence, context, case, graph, error and in-place regression: 285 passed, 33 skipped.
- Ruff checks passed for the edited/new qualification tools, tests and two converter emitters.
- Earlier ACQ comparison-helper, Supervision vacuum and TRANCON logarithm qualification tests still pass under this overlay.

The upstream property test fixture now declares one structurally identified property/value terminal; the previous fixture described three properties without their row identities. This adjustment is included in the overlay, not hidden from the regression record.

The [component receipt](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_components/receipt.json) retains source/fingerprint, wire proof, numeric type chain, bindings and all polling traces. Generated fragments are [poll.py.txt](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_components/poll.py.txt) and [timing.py.txt](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_components/timing.py.txt). Their SHA-256 values are 041086098B7822B44497F995A8E00D6669750AC431EE9CC95D207B1266666C61 and FBE3CF4AA1B286AE89A32084067ECF33CD3963B1A395D50A87BB21E652A7E199.

The execution gate rejects imports, arbitrary calls and unsupported syntax; it injects only bounded fake-task/clock objects. It is not a general Python sandbox. No NI, XP, PSP, serial or hardware access occurred, and no VI was run or saved.

Concurrent checks of the same VI exposed an extraction-cache collision on Windows (WinError 5 during XML replacement). The standalone component qualification was then rerun serially and passed. Run these commands sequentially; cache concurrency itself is not fixed by this overlay.

An archived Supervision NI6602 screenshot was inspected, but its predicate differs from the pinned Acquisition writer. It is not counted as native evidence for the Acquisition iteration limit. Hash-matched native Acquisition captures remain missing.

## Reproduction and next gates

Run from C:\dev\pyconlyse with the pinned checkout plus overlay. Existing evidence directories are not overwritten.

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse'
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/qualify_acq_counter_components.py
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/inventory_control_lvkit.py --corpus acquisition --timeout 30 --output legacy/xp_acq_agent/data/converter_qualification/ACQ_REPRO_NEW
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest -q --deny-network -o addopts= tests/scripts/test_acq_counter_lvkit_qualification.py tests/scripts/test_elyse_acq_ni6602_writer.py tests/scripts/test_acq_lvkit_qualification.py tests/scripts/test_control_lvkit_qualification.py
```

Next: define explicit property/driver error contracts, qualify I32-to-U32 coercion, resolve Mean and focal-driver interfaces, provide proven initializer-local bindings, and isolate root-VI branches before increasing whole-root parsing time.

The upgrade fixes two identified translation mechanisms and provides reproducible Acquisition fixtures. It does not establish complete Acquisition business-logic coverage or safe hardware replacement.

## Subsequent numeric qualification

The [numeric-coercion follow-up](C:/dev/pyconlyse/docs/ELYSE_ACQ_LVKIT_NUMERIC_COERCION_2026-10-03.md) qualifies the finite DBL → I32 → U32 component contract, adds scalar property-wire coercion to lvkit, and corrects the manual writer model. This report's fingerprints, batches and receipts remain historical; they are not rewritten as evidence from the newer overlay.
