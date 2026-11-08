# Supervision DPS writer census and orphaned PT request

## Boundary

This is a static, hash-pinned read of the saved `0_SUP_ELYSE.vi` diagram
export. It does not inspect the running Supervision or PSP value, and it does
not operate a VI or card. The [reproducible validator](../tools/validate_sup_dps_writer_census.py)
enumerates all root local references to the 29-Boolean DPS cluster
(`gRef.paramIdx=176`) whose terminal is a writer.

## Observation

The saved root has **six** local DPS writers. One (`gRef 36152`) receives
the whole cluster from `sharedVariableDynamicRead 36097`; this is an
external-state ingress, not a fieldwise UI producer. Each of the other five
receives a `Bundle by Name` result and sends the resulting cluster to a
same-diagram dynamic PSP writer:

| Local writer | Bundle | Explicitly assigned DPS fields | PSP writer |
|---|---|---|---|
| 38203 | 38212 | 0, 1 | 38229 |
| 38967 | 38974 | 15–19 | 38989 |
| 55371 | 55382 | 13, 14 | 55466 |
| 47186 | 47198 | 20, 21, 23 | 32048 |
| 33453 | 33466 | 2–12 | 33792 |

The five bundle field sets cover `DPS[0..21]` and `DPS[23]` exactly.
`DPS[22]` (`X Alimentation aimant = PT`) and schema fields 24–28 are not
explicitly assigned by these five root UI writers. The separate
[source-control crosswalk](ELYSE_SUP_ACQ_CORRESPONDENCE_2026-09-29.md)
connects those fields to their page events. The root writer census therefore
supports **no normal fieldwise Supervision UI producer for DPS[22] in this
saved source**, not the stronger claim that DPS[22] cannot become True.
The whole-cluster PSP ingest may import a value set by another writer, and
the deployed code has not been byte-compared.

## Cross-host inference and limits

The saved Acquisition timeout dispatcher has an arm for `DPS[22]`, but its
target control is absent from the Event Structure registration table and
there is no handler-local request reset. See the
[ACQ registration audit](ELYSE_ACQ_DPS_EVENT_REGISTRATION_AUDIT_2026-09-29.md)
and [reset-order audit](ELYSE_ACQ_DPS_HANDLER_RESET_ORDER_2026-09-30.md).
Thus the orphaned arm is likely unreachable through the five identified
Supervision page producers, while still reachable from another PSP writer or
unexpected cluster state. If `DPS[22]` remains asserted, the lowest-True
dispatcher can select it ahead of `DPS[23]` repeatedly. This is a
**conditional liveness risk**, not an observed failure or a proven normal
operator path.

```powershell
python tools/validate_sup_dps_writer_census.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
```
