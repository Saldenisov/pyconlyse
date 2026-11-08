# Acquisition Timeout command reads and stop flag interaction

Acquisition receives twelve command/status clusters from Supervision in
Timeout frame10115. Their error terminals form one dependency chain;
each returned data cluster is written to its corresponding local bank
without a caller error gate. The final returned error selects a branch
that assigns **False** to both stop bank30 and TCP ED bank45. This is a
verified legacy assignment, not a recommended safety policy.

## Source scope and verification

The copied root is `0_ACQ_ELYSE.vi`, SHA256
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
It is verified through the same pinned root archive as the
[NI6220 runtime trace](ELYSE_ACQ_NI6220_RUNTIME_TRACE_2026-10-03.md).
`tools/validate_acq_timeout_reads.py` checks six complete direct graphs
and 53 nets: main runtime frame367, dispatcher While body110, Timeout
event53, read frame10115, and both final-error Case arms40237/40224.
This extends the earlier stop-ingress proof from selected edges to the
entire receiving frame and its local data/default destinations.

```powershell
& C:/Users/elyse/miniconda3/envs/pyconlyse312/python.exe tools/validate_acq_timeout_reads.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& C:/Users/elyse/miniconda3/envs/pyconlyse312/python.exe -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_timeout_reads.py tests/device_servers/control/test_elyse_acq_vi_timeout_reads.py
```

## Read dependency and whole cluster assignments

Every reader has a fixed `ni.var.psp://10.20.30.2/SUPERVISION/` URI,
current local data wired to its default-data port, and returned data wired
to a whole-cluster local write. The first reader's error input is unwired;
each later reader receives the preceding returned error. This establishes
argument dependencies, not whether NI performs a network read after an
upstream error. NI's returned data/error values remain explicit boundaries.

| Error-chain order | PSP tag | Call UID | Local bank | Saved cluster |
|---:|---|---|---:|---|
| 0 | C6NI6703 | 10310 | 9 | 10 DBL |
| 1 | C7NI6703 | 10333 | 10 | 10 DBL |
| 2 | C8NI6703 | 10369 | 11 | 10 DBL |
| 3 | C9NI6703 | 10449 | 12 | 10 DBL |
| 4 | C1011NI6602 | 22278 | 39 | 33 DBL |
| 5 | C3_OUT_DIO96 | 25403 | 17 | 40 Boolean |
| 6 | C4_OUT_DIO96 | 25426 | 15 | 32 Boolean |
| 7 | C5_OUT_DIO96 | 25449 | 13 | 40 Boolean |
| 8 | DPS | 19950 | 36 | 29 Boolean |
| 9 | DPC | 19974 | 37 | 5 Boolean |
| 10 | EPS | 19997 | 44 | 77 Boolean |
| 11 | EPC | 22840 | 38 | 12 Boolean |

Read node22840 supplies the final error to selector40205. False selects
empty diagram40237. True selects40224, where literal44039 is False and
fans out to the two local writers. There is no error handler, conditional
data-write gate, readiness aggregation or stale-data detector in this
checked frame. No readback quality or hardware permission follows from a
successful cluster copy.

The twelve local writes are not themselves chained by error wires. All
complete before the next stacked-sequence frame can begin, but they are
not an atomic update and their relative completion order is not pinned.
Nor do the twelve default-data reads represent a single synchronized epoch.

## Command setpoint displays in the next frame

Frame10526 contains16 operations and29 direct nets, without cases or
external calls. It reads C6/C7/C8 command banks9/10/11 and replaces only
Consigne in the nested direct-line bank28 and deviated-line bank33.
`tools/validate_acq_timeout_setpoint_display.py` checks all nodes/nets,
all saved Bundle/Unbundle By Name indices and nested field types.

Each device cell contains eleven fields: five Boolean states, DBL Consigne,
DBL Lecture, and four Boolean step controls. The bundle's saved index
counts each intermediate device cluster as well as its eleven leaves.
Consequently Consigne for device position r has flat index12r+6, not r.
The checked type structure resolves this flattening; Python writes only
cell field5 and preserves all ten other fields, including Lecture and M/A.

| Line and device position | Device label | Source bank and field |
|---|---|---|
| Direct 0 | Dipole 1 | 10[8] |
| Direct 1 | Focale | 10[5] |
| Direct 2 | Phase HF / Laser | 11[5] |
| Direct 3 | Correcteur H1 | 9[0] |
| Direct 4 | Correcteur V1 | 9[1] |
| Direct 5 | Correcteur H2 | 9[2] |
| Direct 6 | Correcteur V2 | 9[3] |
| Direct 7 | Triplet 1-1 | 10[0] |
| Direct 8 | Triplet 1-2 | 10[1] |
| Direct 9 | Correcteur H3 | 9[4] |
| Direct 10 | Correcteur V3 | 9[5] |
| Deviated 0 | Quadrupole 1 | 10[6] |
| Deviated 1 | Quadrupole 2 | 10[7] |
| Deviated 2 | Triplet 2-1 | 10[3] |
| Deviated 3 | Triplet 2-2 | 10[4] |
| Deviated 4 | Correcteur H4 | 9[6] |
| Deviated 5 | Correcteur V4 | 9[7] |
| Deviated 6 | Dipole 2 | 10[9] |
| Deviated 7 | Correcteur H5 | 9[8] |
| Deviated 8 | Correcteur V5 | 9[9] |

The source type labels C6 field8 as Reserve, yet its wire enters Correcteur
H5 Consigne. The wire is retained; the label is not used to remove a
purportedly unused channel. These copies do not change physical outputs,
establish electrical units, or create permission to operate the equipment.
Repeated bank9/10 local reads in the two display branches are not one
shared snapshot wire; the two Python functions accept them independently.

## Runtime scheduling and competing stop writers

Main phase367 contains exactly five While loops, with no direct nets
ordering them: NI6220 acquisition47483, pressure acquisition59483,
VAM-A publication20601, I/O/publication203, and event dispatcher102.
The copied graph therefore permits their execution concurrently. Stop
bank30 is shared; a local assignment is not a broadcast cancellation token
with guaranteed observation order.

Dispatcher body110 writes its iteration to bank31, requests an independent
75-ms Wait, and supplies20 ms to the Event structure Timeout input. It also
reads stop bank30 into a Stop-if-True condition. None of these independent
body operations orders that stop read after the Timeout frame. A busy
event handler or blocking external return can delay completion. Neither
75 ms nor20 ms is a verified emergency-response bound.

The previously verified publication error branches write True to banks30
and45. The receiving frame can write False to the same banks when its
final read error is True. Both writers can be reachable in independent
runtime loops. This proves competing assignments, not a deterministic
race outcome: some loops may observe True and exit before the reset;
others may read False. A whole-program stop trace must retain both
possibilities rather than converting every network fault into a guaranteed
global stop. A later safety redesign would be a separate, explicit change.

## Python trace and remaining business logic

`vi_simulation/timeout_reads.py` accepts twelve independent default-data
snapshots and twelve supplied data/error returns. It preserves error
propagation and writes the supplied returned data even on a returned
fault. It does not invent zero substitution or hold-last-value behavior.
Only the final supplied error status selects the False stop/TCP assignments;
an earlier fault cleared by a later supplied boundary return does not
select that final error branch.

The result represents the assignments of a completed frame, not an atomic
publication or operating permission. It does not import PSP, NI, VISA,
Tango, a socket, clock or hardware adapter. No VI was run/saved and no
new native screenshot was captured.

The following Timeout frames now have separate complete direct graph
proofs: [procedure/counter ingress22247](ELYSE_ACQ_TIMEOUT_DISPATCH_TRACE_2026-10-03.md)
and [conditional cooling trip42045](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md).
Numeric unmatched dispatch, enabled-arm metadata, all downstream event
guards and permission/interlock correlations remain open. These proofs
do not certify radioprotection,
HT startup, normal/fault stop or restart. Acquisition remains the only
active coverage target; Supervision review is not declared complete.
