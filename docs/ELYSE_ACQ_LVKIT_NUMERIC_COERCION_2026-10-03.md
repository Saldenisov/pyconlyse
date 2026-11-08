# Acquisition counter numeric conversion in lvkit

Date: 2026-10-03. Scope: the saved NI6602 writer's finite scalar DBL timing path, translated into non-actuating Python.

The original Acquisition VI converts each microsecond input to I32 before supplying U32 timing properties. The previous manual simulation bypassed the I32 stage, and lvkit omitted the signed-to-unsigned coercion at the property input. The current change preserves both stages. Generated code and the corrected manual model agree with an independent implementation of NI's documented rules for 4143 paired fixtures, comprising 8286 scalar conversions. No VI, NI task or hardware operation was executed; complete writer behavior remains unqualified.

## Source and numeric mechanism

The source is the original `1_ACQ_WRITE_NI6602.vi`, SHA-256 `4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211`, not a similarly named Supervision copy. The qualification checks its hash and the pinned original XML archive before generating code. Existing validators check the complete wire census, primitive 1142 identities, both 20.0 constants, and timing-property row order. Independent archived type descriptors establish I32 conversion outputs and U32 property inputs; parsed terminal types additionally confirm DBL multiply/conversion inputs.

| Path | Saved node and terminal identities | Numeric operation |
| --- | --- | --- |
| Delay | Input 13127, multiplier 13352, conversion 157 output 163 | DBL microseconds × 20.0 → I32 |
| Width | Input 13077, multiplier 13369, conversion 183 output 201 | DBL microseconds × 20.0 → I32 |
| Initial delay | Property node 3083, input 3097 | Delay I32 → U32 |
| Low ticks | Property node 3083, input 3103 | Same delay I32 → U32 |
| High ticks | Property node 3083, input 3109 | Width I32 → U32 |

For a finite DBL product, the documented numeric contract is:

```text
product = microseconds * 20.0                  [DBL]
signed  = clamp(round_ties_to_even(product), -2147483648, 2147483647)
ticks   = unsigned interpretation of signed's 32-bit pattern
```

[NI's To Long Integer reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/to-long-integer.html) specifies nearest-integer rounding with ties to even. The [archived NI Function and VI Reference Manual](https://download.ni.com/support/manuals/321526a.pdf), printed pages 2-4 and 4-10, distinguishes floating-to-integer saturation from integer-to-integer bit preservation. The [coercion documentation](https://www.ni.com/docs/en-US/bundle/labview/page/coercion-dots.html) illustrates a negative signed value becoming a large unsigned value rather than zero. These rules support the numeric interpretation; they do not establish driver acceptance of the resulting ticks.

## Converter and manual model changes

The lvkit Property Node emitter now inspects the actual incoming terminal representation when its target is scalar U32. A scalar I32 source produces an explicit 32-bit mask. A matching U32 source remains unchanged. Missing, ambiguous or other mismatched wired source representations fail generation. Direct component-fixture bindings without an incoming wire continue to represent explicitly supplied target values; they are not evidence of wire coercion.

The existing finite DBL To Long Integer template already performs ties-to-even rounding and I32 saturation and was not changed. Its integer-input behavior and other polymorphic representations remain unqualified; this iteration does not claim general numeric conversion support.

The manual writer now calls `labview_i32_to_u32_ticks`. The historical `labview_u32_ticks` and `exact_u32_ticks` APIs remain available for their previous restricted contracts, but neither defines the complete saved writer path. The writer trace accepts finite negative products as numeric data and records their unsigned bit pattern. This is not permission to send such values to equipment, and the trace has no hardware adapter.

| Microseconds | Corrected U32 ticks | Difference from previous shortcut |
| ---: | ---: | --- |
| 0.025 | 0 | Half tick rounds to even zero |
| 0.075 | 2 | 1.5 ticks rounds to even two |
| -0.05 | 4294967295 | I32 -1 preserves its bits; old helper rejected negative input |
| 107374182.4 | 2147483647 | Product 2147483648 first saturates to I32 maximum; old direct-U32 helper returned 2147483648 |
| -10000000000 | 2147483648 | Finite product saturates to I32 minimum before unsigned interpretation |

NaN, infinity, overflowing DBL products, Boolean arguments and nonnumeric inputs are rejected by a Python-only simulation guard. No specific native LabVIEW result is claimed for those inputs.

## Qualification and regression

The [qualification tool](C:/dev/pyconlyse/tools/qualify_acq_counter_numeric.py) emits only the two conversions and three property assignments from the pinned graph. Its execution gate permits five assignments, scalar arithmetic, four known conversion builtins and stores to an in-memory fake property sink. Imports, hardware methods, property reads, arbitrary names, loops and extra assignments are rejected. This constrained fixture runner is not a general Python sandbox.

The independent reference uses Decimal rounding on the already-rounded DBL product, followed by signed-byte encoding and unsigned-byte interpretation. Fixtures include positive/negative half ticks, both sides of I32 saturation, adjacent representable DBL values, large finite values, and 4096 deterministic random values. Delay and width are paired in reverse order to expose crossed output wiring. Generated output and manual simulation agree for all 4143 pairs. The fixture-vector SHA-256 is `84B34E0D9A04D87E6812B5C88AE97727DD1DCDB424EC5D5AECEDE223A7836929`.

Mutation checks demonstrate that removing the U32 mask changes the negative-input result and that unsupported source representations are rejected. A writer-trace regression checks that the corrected values actually reach the recorded initial-delay/low/high arguments. Nine new upstream tests use synthetic typed graph fixtures, without redistributing the laboratory VIs.

| Test lane | Result |
| --- | --- |
| Targeted ACQ/Supervision/TRANCON converter and model regression | 98 passed, 71 subtests passed, one assertion-rewrite warning |
| Entire existing Acquisition controller and pure-model lane | 273 passed, 593 subtests passed, one assertion-rewrite warning |
| Selected upstream lvkit regression including new synthetic coercion tests | 294 passed, 33 skipped |

These lanes overlap and must not be summed as unique tests. The upstream run installed the outbound-network guard before invoking pytest; loading that helper as a pytest plugin alone does not install the guard. Ruff checks passed for the new qualification tool, tests, converter emitter and edited writer model. Overlay reverse-application and tracked whitespace checks passed.

## Reproducible artifacts

| Artifact | SHA-256 |
| --- | --- |
| Current converter source fingerprint | DCA90181D1B5FD720C83333370D6350922AF74B84205C5AA3E6723EEC9A44D84 |
| Complete acq_numeric_lvkit_overlay.patch | 2C80AD96C6A8C5EA545A96FDBEB95C33B64378CA2628D3FEB21290BB3FB27874 |
| Isolated numeric.py.txt | D68D12449DB091E94151D462F0D8D12A48366F6FAC579C7A1AD7090A56B33E01 |

The [complete overlay](C:/dev/pyconlyse/tools/acq_numeric_lvkit_overlay.patch) targets clean upstream lvkit commit `d8058677e15c47094e725439bd72417fe9527754`. It includes earlier fixes plus this iteration and the new synthetic upstream tests: eleven modified tracked files and five new files. Do not stack it on earlier overlays. Earlier patches and frozen receipts are retained.

The [numeric receipt](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_numeric/receipt.json) records source identity, archived and parsed types, converter identity, fixture identity and qualification limits. The [generated fragment](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_numeric/numeric.py.txt) remains quarantined text. No generated hardware-facing module was imported or executed.

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse'
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/qualify_acq_counter_numeric.py
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest -q --deny-network -o addopts= tests/scripts/test_acq_counter_numeric_qualification.py tests/scripts/test_acq_counter_lvkit_qualification.py tests/device_servers/control/test_elyse_acq_vi_counter_writer.py
```

Run same-VI extraction and qualification serially; the previously observed Windows extraction-cache race remains unfixed.

## Remaining gates and upstream proposal

The [fresh whole-writer probe](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003_counter_numeric_writer_probe/manifest.json), with this converter fingerprint, parsed the original VI and rejected generation with `property error input is unresolved`. Numeric agreement does not establish Property Node error gating, driver-returned errors, row short-circuit behavior, task replacement or Stop/Clear/Start semantics. Native LabVIEW execution comparisons and hash-matched Acquisition screenshots are still absent. The previous all-17-member batch belongs to the earlier overlay and was not relabeled as a current run.

For upstream discussion, the new bounded proposal is a synthetic-test-backed scalar I32-to-U32 Property Node coercion fix. It should remain in the deferred Property Node series until error semantics and compatibility are reviewed. The existing candidates for loop counters, positional clusters, DBL arithmetic and result annotations remain separate proposals. No branch, commit, push or pull request was created, and no proprietary VI redistribution was authorized.

The next critical boundary is explicit Property Node error handling. Resolving that boundary requires a defined error-cluster contract, not an invented nominal input or removal of the current rejection. Full Acquisition and Supervision business-logic coverage remains incomplete.
