# NI6602 selector and card ownership across Supervision and Acquisition

## Boundary and sources

Read-only comparison of saved `0_SUP_ELYSE.vi` (SHA-256 `2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B`) and the copied Acquisition LLB (SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`). Neither running deployment was checked for byte equality. No VI was run and no counter task was created.

| Selector `N° du compteur` (integer path) | Consumer in saved code | Task namespace | Timing fields passed to writer | Reset/publication |
|---|---|---|---|---|
| 1–16 | Acquisition Timeout subframe 2, guard `n>0 AND n<17` | Acquisition `1_ACQ_INIT_NI6602.vi` outputs `/10/ctr0..7` | C10 fields 0–15, pair `2q,2q+1`, `q=floor((n−1)/2)` | ACQ sets selector `−1`, then writes C10–11 PSP cluster. |
| 17–32 | Supervision Timeout frame, guard `n>16` (no upper bound visible at this branch) | Supervision `1_SUP_INIT_NI6602.vi` outputs `Dev1/ctr0..7` on **the Supervision computer** | C11 fields 16–31, pair `16+2q,17+2q`, `q=floor((n−17)/2)` | SUP sets selector `−1`, then writes `ni.var.psp://localhost/SUPERVISION/C1011NI6602`. |

Each adjacent selector pair refers to the same task and delay/width pair; the quotient's remainder is not used at either writer call. This resolves why one shared command cluster contains two sets of eight timing pairs: the code routes them to **different computers'** NI6602 cards. It does not mean C11 is unused globally. The ACQ-side proof is in `ELYSE_ACQ_NI6602_COUNTER_REQUEST_AUDIT_2026-09-29.md`.

## Supervision terminal proof

In `0_SUP_ELYSE_BDHb.xml`, diagram `49696` reads field 32 (`N° du compteur`) from the PSP-backed local `gRef paramIdx=170` and compares it to literal `16` via Greater? UID `61153`. The false arm of case `59979` is empty. The true arm's frame 0 (`sequence 55018`, diagram `55043`) subtracts literal `17` from `n` (Subtract `57991`), divides by literal `2` (Quotient & Remainder `54423`), then:

- Converts `gRef paramIdx=210` to an array (`16797`) and selects element `q` (`53299`) for connector input 7 of `1_SUP_WRITE_NI6602.vi`.
- Converts `gRef paramIdx=163` to an array (`51246`) and selects elements `16+2q` and `17+2q` (`54763`, Add `51049`, Increment `51247`) for connector inputs 9 `Delais` and 10 `Largeur`.

`gRef paramIdx=210` is grounded by a direct initialization wire: in diagram `23159`, connector output 1 of `1_SUP_INIT_NI6602.vi` feeds that same local. The initializer configures eight `Dev1/ctr0..7` tasks. `gRef paramIdx=163` is a separate Supervision local timing cluster; other diagrams copy it to the PSP-backed `paramIdx=170` and publish it. The writer call itself reads `paramIdx=163`, **not** a fresh PSP read. Frame 1 (`56403`) sets `paramIdx=170` field 32 to `−1`; frame 2 (`17908`) writes it to the localhost PSP URI above.

Two producer sites have already been located in the Supervision event loop. Event frame 1 (diagram `70866`) wires its event value into timing field 3, wires literal selector **4** into field 32, and writes the resulting cluster to the shared variable. On Acquisition that selector reaches task `out1` and reads C10 fields 2/3. Event frame 6 compares two event-data values: Subtract `35269` → Cluster To Array `38013` → Array Size/For Loop `42544`. For each loop element whose difference is nonzero (`Not Equal? 38725`), the true arm (`select 28747`, diagram `28797`) writes selector `loop index + 1` plus the local timing cluster to PSP. Thus a UI event that changes several timing fields may produce **several successive PSP writes**, while the selector itself is one shared numeric field. Whether Acquisition/Supervision observe every intermediate selector is not guaranteed by this static graph and requires a scheduling test. The `Page Synchronisation` cluster has **33** numeric fields: 32 timing fields plus selector field 32. If the selector field itself changes in this event value, the same loop would issue command **33**, outside the established eight-task map; whether that field can change through the normal UI event is unresolved.

The Supervision `n>16` guard has no visible `n<33` condition at this branch. Thus the integer mapping table is established only for 17–32; behavior for values above 32, nonintegers, and array-index failure requires separate analysis. The two saved VIs' write/read scheduling and competing PSP updates are also not yet a proven atomic protocol. In particular, a selector reset to `−1` records attempted handling, not confirmed DAQmx success.

The front-panel numeric `N° de la sélection (1 à 32):` (FPHb UID `56286`) has `StdNumMin=-inf` and `StdNumMax=inf`. Its caption describes a range; the saved control itself does **not** enforce it. Whether a normal operator can edit that particular control, and whether such an edit fires the page event, remain unverified. Python's pure decoders deliberately reject requests outside 1–32 instead of copying this unchecked array-index path.

The two writer subVIs are **not identical at the wait boundary**. The saved `1_SUP_WRITE_NI6602.vi` (raw diagram `3149`) polls `CO.GénImpTerminée` with a 1 ms Wait and exits its While loop when the property equals True; there is **no explicit iteration-limit branch** in that loop. The Acquisition writer has a 1 ms poll but also exits when its loop index exceeds 20 (see the Acquisition native-frame ledger). Both then stop, rewrite pulse timing, and restart a task. Consequently, an indefinitely incomplete Supervision counter can stall this event path in the saved graph, whereas Acquisition can proceed after its bounded poll. This is a control-flow statement, not a claim about actual DAQmx fault behavior.

## Consequence for Python

Model one shared selector with two **owner-specific** dispatchers and separate eight-task banks. Do not route all 32 fields to Acquisition, and do not infer that Supervision can directly write `/10/ctr*`. Use physical-task adapters only after the simulator reproduces the source-side data and acknowledgement ordering and the deployed copies are checked.

The pure Python transfer is `DeviceServers/control/elyse_acq/counter_dispatch.py`: integer-only decoders for the two owners plus a non-actuating Supervision field-delta selector. `tools/validate_ni6602_ownership.py` checked the saved raw task-reference, selector, constant, and writer-input wires in both VIs; `tests/device_servers/control/test_elyse_acq_counter_dispatch.py` passed **10** standard-library tests. These checks prove correspondence to the saved graphs at the specified terminals, not deployment parity or physical pulse behavior.
