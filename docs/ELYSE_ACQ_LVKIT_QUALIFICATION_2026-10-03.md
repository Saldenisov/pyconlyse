# Acquisition converter qualification

The local adaptation of [lvkit](https://github.com/pragmatest-dev/lvkit) now generates two original Acquisition comparison helpers whose results agree with an independent literal Python model over 464 synthetic input cases. This establishes a first usable conversion test, not whole-Acquisition coverage or LabVIEW runtime equivalence. Neither the VIs nor hardware-facing generated code were executed.

## Source identity and reproducibility

The downloaded checkout is `C:\dev\ELYSE-ACQ-analysis\converter\lvkit`, version `0.8.6`, upstream commit `d8058677e15c47094e725439bd72417fe9527754`. The previous `lvkit 0.8.4` installation remains unchanged. Python 3.11.9 supplies dependencies `pylabview 0.1.2`, `networkx 3.6.1` and `pydantic 2.13.5`; imported converter code comes from the separate GitHub checkout, not that installed distribution.

The reproducible local changes are saved in [acq_lvkit_overlay.patch](C:/dev/pyconlyse/tools/acq_lvkit_overlay.patch). Its SHA256 is `B45CC53D03742CCEA705ABDDD82214188C96414EDE2A97E2DFAA1CC42147E14D`. Reverse application was checked without applying it. No changes were pushed upstream. Original Acquisition source hashes match the member manifest for 17/17 VIs; the LLB hash remains `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.

| Original Acquisition member | Source SHA256 | Differential cases |
| --- | --- | ---: |
| `2_SUP_Ecart_lu_ecr_VDirecte.vi` | `5C9E6C4E20FB9CC5B023C9DC56DC58C4D17EB4C63504722A0D6B8D19CF499AD5` | 234 |
| `2_SUP_Ecart_lu_ecr_VDéviée.vi` | `80B5B1F9BD5802093D8898A2965BA36E252B9E191F87253AAF531AB3B98AC63F` | 230 |

Despite their `2_SUP` names, these inputs were taken from the original `ACQUISITION.llb` member set, not substituted Supervision VIs.

## Converter changes and behavioral checks

The unmodified converter produced nested-field access with incorrect flat tuple indices, overwrote unrelated fields named `orange`, and returned `None` instead of the output cluster. The patch resolves depth-first cluster indices to nested tuple paths and applies by-value updates. Sequential local reads and writes are emitted only after every local node receives an explicit reviewed control-terminal binding with a compatible type shape. FP display order is not used to infer these bindings in the qualification profile. This is a reviewed binding mechanism, not an automatic solution for all Acquisition local variables.

Both helpers contain two sequence frames. Frame 0 copies the input cluster to the output local. Frame 1 calculates command/readback differences and changes only the orange indicators. Direct-line channel 2, `Phase HF / Laser`, has its orange input wired to literal `False`; its calculated comparison does not drive that indicator. The generic deviation utility previously considered during Supervision reconstruction does not encode this exception and is not used as the qualification oracle.

[validate_acq_deviation_helpers.py](C:/dev/pyconlyse/tools/validate_acq_deviation_helpers.py) checks the original archived XML independently of lvkit: three diagram identities per VI, sequence order, local read/write direction and bank index, cluster lane indices, arithmetic opcode counts, operand wires, shared threshold and the hardwired phase flag. The independent [deviation_helpers.py](C:/dev/pyconlyse/DeviceServers/control/elyse_acq/vi_simulation/deviation_helpers.py) model preserves untouched fields. Differential cases include equality at the threshold, adjacent floating-point values, both difference signs, individually distinguishable channels, deterministic randomized clusters, NaN and infinities. Negative thresholds are supplied literally, not clamped or promoted to invented equipment faults.

Generated artifacts are [direct.py](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003/direct.py), [deviated.py](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003/deviated.py) and [summary.json](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003/summary.json). They remain outside production device servers. The execution gate accepts only a small pure-Python grammar, removes imports before evaluation and injects inspected arithmetic/tuple helpers. It rejects hardware/network/process imports, arbitrary calls, loops, placeholders and unresolved `None` outputs. This is not a general-purpose sandbox.

## Test results

| Check | Result |
| --- | --- |
| Project qualification, source mutations, pure helper and existing readback/counter models | 43 passed, 26 subtests passed, 1 pytest assertion-rewrite warning |
| Complete existing Acquisition controller and pure-model test lane, including the new helper tests | 272 passed, 1 pytest assertion-rewrite warning |
| Original NI6602 writer wire proof and mutation tests | 13 passed, 1 pytest assertion-rewrite warning |
| Upstream builder/context/sequence/new-codegen regression | 140 passed, 1 skipped |
| Upstream error/in-place/end-to-end regression | 42 passed, 27 skipped |
| Original source preservation | 17/17 member hashes and LLB hash match |

The test runs used network denial. Skipped upstream cases are not counted as validated corpus conversions.

Repeat the project checks from `C:\dev\pyconlyse`:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps'
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest --deny-network -q -o addopts= tests/scripts/test_acq_lvkit_qualification.py tests/device_servers/control/test_elyse_acq_vi_deviation_helpers.py tests/device_servers/control/test_elyse_acq_vi_line_readback.py tests/device_servers/control/test_elyse_acq_vi_counter_writer.py
```

[qualify_acq_lvkit.py](C:/dev/pyconlyse/tools/qualify_acq_lvkit.py) also emits a reproducible JSON bundle containing the generated sources and receipts. Its `--output` argument labels the intended artifact directory; the command itself does not write or overwrite artifacts.

## Rejected conversion and remaining limits

Subsequent iteration: [Acquisition loop and property upgrade](C:/dev/pyconlyse/docs/ELYSE_ACQ_LVKIT_COUNTER_UPGRADE_2026-10-03.md) fixes isolated NI6602 counter/property mechanisms and records a frozen 17-member triage run. Full-writer error handling and numeric coercion remain unqualified; the earlier rejected output below is preserved as historical evidence.

`1_ACQ_WRITE_NI6602.vi` still generates incorrect Python: the iteration comparison becomes `0 > 20`, the done comparison uses a task-like object, Stop is invoked on the done-property value, and Start on the initial-delay property value. Its raw output is preserved as [rejected_ni6602.py.txt](C:/dev/pyconlyse/legacy/xp_acq_agent/data/converter_qualification/20261003/rejected_ni6602.py.txt), not imported or executed. The existing manually verified NI6602 model remains the reference for the next converter test, including polling, error clearing and task/property routing.

The native screenshots inspected this session show the corresponding Supervision helper diagrams, not hash-matched original Acquisition captures. They corroborate the topology but do not close the original native-evidence requirement. Defaults for unwired cluster inputs, floating-point runtime equivalence in LabVIEW, concurrent locals, restart/fault scheduling, DAQmx boundary semantics and the complete root VI remain unqualified. The two accepted helper functions describe display comparison logic, not physical overvoltage protection. No XP access, PSP commands, serial/NI calls, hardware writes, VI execution or VI saving occurred.
