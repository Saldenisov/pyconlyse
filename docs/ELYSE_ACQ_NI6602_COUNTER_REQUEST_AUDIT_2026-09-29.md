# Acquisition NI6602 counter-request routing (saved VI, 2026-09-29)

## Scope and evidence

This is a read-only trace of `0_ACQ_ELYSE.vi` from the copied `ACQUISITION.llb` (SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`). It does not verify the running XP copy or actuate a card. Raw terminal incidences can be reproduced with `tools/trace_acq_counter_request.py` and the saved `0_ACQ_ELYSE_BDHb.xml`; the `lvkit`-assigned **names** of root local variables were not trusted because its `paramIdx` mapping is demonstrably wrong.

The Timeout event's subframe 2 unbundles field 32 (`N° du compteur`) from the PSP-backed `C10-11 NI6602` local (`gRef paramIdx=39`, selector `23199`, parent diagram `22247`). Its guard is `n > 0 AND n < 17`; false has no counter-write call. In true frame 0 (`sequence 23633`, diagram `23641`), the raw graph is:

```
q = floor((n - 1) / 2)                     # Decrement 15887; Quotient & Remainder 26175
task = ClusterToArray(gRef paramIdx=21)[q] # 29080 -> Index Array 21122 -> subVI input 7
k = 2*q                                   # Multiply 22328
delay = ClusterToArray(C10-11 bank)[k]     # 20986 -> Index Array 21053 -> subVI input 9
width = ClusterToArray(C10-11 bank)[k+1]   # Increment 22884 -> same Index Array -> input 10
1_ACQ_WRITE_NI6602(task, delay, width)
```

`gRef paramIdx=21` is grounded independently: in initialization diagram `227`, the same reference receives connector output **1** of `1_ACQ_INIT_NI6602.vi`; that connector is named `ID_NI6602_DAQmx` and contains `ID_NI6602_out0..out7`. Therefore `q=0..7` selects the eight initialized `/10/ctr0..7` task references. The subVI connector names inputs 7, 9, and 10 as `ID_out?_DAQmx`, `Delais`, and `Largeur`. Both divisor and multiplier are literal `2.0` in the saved diagram. The quotient's remainder output is unwired.

| Accepted integer `n` | `q` | Task | Delay field | Width field |
|---|---:|---|---|---|
| 1 or 2 | 0 | `out0` | `C10 Délais` [0] | `C10 Largeur` [1] |
| 3 or 4 | 1 | `out1` | `C10 Délais` [2] | `C10 Largeur` [3] |
| 5 or 6 | 2 | `out2` | `C10 Délais` [4] | `C10 Largeur` [5] |
| 7 or 8 | 3 | `out3` | `C10 Délais` [6] | `C10 Largeur` [7] |
| 9 or 10 | 4 | `out4` | `C10 Délais` [8] | `C10 Largeur` [9] |
| 11 or 12 | 5 | `out5` | `C10 Délais` [10] | `C10 Largeur` [11] |
| 13 or 14 | 6 | `out6` | `C10 Délais` [12] | `C10 Largeur` [13] |
| 15 or 16 | 7 | `out7` | `C10 Délais` [14] | `C10 Largeur` [15] |

Consequently, **for integer requests in the admitted range**, each adjacent pair selects the same task and same C10 values. C11 timing fields [16..31] are present in the shared-variable schema but have no index path into **this Acquisition call**. The separate saved Supervision VI handles selector values above 16 with its own `Dev1/ctr0..7` tasks and C11 timing fields; see `ELYSE_SUP_ACQ_NI6602_OWNERSHIP_2026-09-30.md`. A noninteger value is admitted by the visible Acquisition comparisons if the bank type can carry one; exact coercion/index behavior for that case is not established.

After the call and Simple Error Handler, true frame 1 writes `N° du compteur = -1`; frame 2 publishes the C10-11 cluster to PSP. This reset does not prove that the reconfiguration succeeded: the subVI stops and restarts the DAQmx task, and its own error handling must be modeled separately.
