# Acquisition array arithmetic correction in the shared lvkit checkout

## Result and scope

The reviewed Acquisition VIs exposed a numeric-array generation error in the shared, modified lvkit checkout. NI6703 Add node `295`, output `620`, generated Python list concatenation instead of element-wise addition. The correction preserves ten-channel shape and the two C8 offsets. Four isolated scaling/offset fragments now agree with independently decoded original constants in 2068 bank fixtures, comprising 20680 scalar results. This is not qualification of the complete NI6703 writer or Acquisition application.

The working checkout is `C:\dev\ELYSE-ACQ-analysis\converter\lvkit`, based on upstream commit `d8058677e15c47094e725439bd72417fe9527754`. Existing ACQ, Supervision and TRANCON changes were retained. The final frozen qualification also includes the parallel Supervision task's extractor, local-reference and selector-default changes. No original VI was modified, run or saved; no hardware, driver or PSP command was issued.

## Original diagram and discriminating test

The pinned member is `1_ACQ_WRITE_NI6703.vi`, SHA-256 `5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D`. The independent [writer validator](C:/dev/pyconlyse/tools/validate_acq_ni6703_writer.py) checks the original archived diagrams, 40 slope constants, offset array `1246` and the Add wires `555 → 623` and `1246 → 626`. The parsed Add terminals are one-dimensional DBL arrays.

The pre-correction fragment was:

```python
sum_ = scaled + [0.0, -2.0, -2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

For two ten-element Python lists, this expression would produce twenty elements. The saved graph instead requires ten pairwise sums. The corrected emitter generates `_lv.add(...)`. For a zero logical bank, the isolated C8 scaling/offset output is `[0, -2, -2, 0, 0, 0, 0, 0, 0, 0]`. This vector precedes the nonlinear formulas at indices 3 and 4; it is not the final requested voltage vector.

The cause was a concatenation-preservation heuristic applied in two different contexts. A typed numeric primitive already identifies an arithmetic operation, so list literals must not suppress element-wise Add. The whole-function fallback still preserves Build Array and Replace Array Subset concatenation. Synthetic tests check numeric literals on either operand, unchanged concatenation, output shape and input preservation.

## Differential results

The [array qualifier](C:/dev/pyconlyse/tools/qualify_acq_ni6703_arrays.py) validates archived wires and representations, emits each fragment twice, checks identical output and accepts only a narrow arithmetic AST. Execution injects list fixtures and the three in-memory helpers `add`, `mul` and `neg`. Imports, loops, arbitrary calls and the historical plain `+` fragment are rejected. This gate is not a general Python security sandbox.

| Reviewed scope | Comparison | Result |
|---|---|---|
| Acquisition direct-line deviation helper | Independent tuple model | 234 fixtures pass |
| Acquisition deviated-line deviation helper | Independent tuple model | 230 fixtures pass |
| NI6602 nominal polling and timing fragments | Bounded fake task and clock | 23 polling traces and 4 timing fixtures pass |
| NI6602 DBL to I32 to U32 timing conversion | Independent Decimal and signed-byte oracle | 4143 paired fixtures and 8286 scalar conversions pass |
| NI6703 four scaling fragments and C8 offsets | Original archived DBL constants | 2068 bank fixtures and 20680 scalar results pass |
| Shared Supervision vacuum regression | Exhaustive Boolean oracle | 8192 combinations pass |
| Shared TRANCON logarithm regression | Independent NumPy oracle | 270 numeric values pass |

The final frozen build fingerprint is `4A0228B789D5AF0123C841667D30CA33F282BD9BB27F59F7114F4344A684FC27`. Qualification checks the fingerprint before and after execution. The [receipt and generated fragments](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_understood_acq_shared_parser/receipt.json) retain this identity. All reviewed ACQ fragment text is unchanged from the earlier post-array-correction build; the parser changes did not change these outputs. Ongoing shared-checkout edits must be requalified rather than assigned this receipt.

The [frozen test receipt](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_understood_acq_shared_parser/tests.json) records 90 project tests and 130 subtests passing with `--deny-network`, followed by 98 selected lvkit tests. The wrapper verifies the same converter fingerprint across both suites. One existing pytest assertion-rewrite warning remains.

Seven initially failing array-operation tests also failed with only `elementwise.py` restored to its upstream version in memory. Their test helper used separate globals and locals for `exec`, preventing comprehension free variables from resolving. The helper now uses one module namespace; no array-generation behavior was changed to accommodate these tests.

## Whole VI triage remains separate

The [all-member manifest](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_understood_acq_updated/corpus/manifest.json) belongs to the earlier build fingerprint `671E4DC3D005B9A5137C6B5E2747327619EF66271AA87BFFDEE414E3E323A233`, before the parallel parser changes. All 17 original members parsed; 10 produced quarantined, compilable soft-unresolved drafts and 7 failed generation. There were 60 unresolved diagnostics and no timeouts with a 90-second worker limit. Original member hashes and saved draft hashes were checked. These counts are not behavioral coverage and were not relabeled as results for the later build.

The seven failures comprise the main VI at `System Exec.vi`, three readers at `Mean.vi`, two focal helpers at `chr62000 Initialize.vi` and the NI6602 writer at `property error input is unresolved`. NI6703's whole draft still has unresolved DAQmx calls and an unsupported disable structure; it was never executed.

The NI6703 parser warning `Data type NumFloat64: unpack requires a buffer of 8 bytes` is retained in the manifest. The numeric qualifier uses independently pinned wired constants and explicit inputs, not inferred front-panel defaults. Nonlinear formulas, other array shapes, nonfinite inputs, driver errors, task lifecycle, concurrency and native execution equivalence remain outside this qualification. No hash-matched native Acquisition screenshot was added.

## Reproduction and proposed upstream changes

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe C:/dev/pyconlyse/tools/qualify_acq_ni6703_arrays.py
& C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest -q --deny-network -o addopts= tests/scripts/test_acq_ni6703_array_qualification.py
```

The [focused delta](C:/dev/pyconlyse/tools/acq_ni6703_array_lvkit_delta.patch) can be discussed as two upstream commits: the numeric-array literal correction with synthetic tests, and the independent array-test namespace correction. Application-specific original VI fixtures remain in pyconlyse. No commit, push or pull request was created.

The [complete shared snapshot](C:/dev/pyconlyse/tools/acq_shared_parser_lvkit_overlay.patch) includes earlier and parallel changes and corresponds to the frozen qualification fingerprint above. Both patches passed read-only application checks against the clean upstream index. Apply either the complete snapshot to clean upstream, or the focused delta to a compatible checkout; do not stack the complete snapshot on previous overlays. Snapshot applicability does not establish complete behavioral qualification of every included change.
