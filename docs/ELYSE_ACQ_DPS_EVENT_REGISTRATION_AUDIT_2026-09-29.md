# Acquisition DPS dispatcher: raw-wire/event-registration audit (2026-09-29)

## Scope and result

This is static analysis of the saved `0_ACQ_ELYSE.vi` in the copied
`ACQUISITION.llb` (SHA-256
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`).
No VI or hardware was run. The [24-row raw crosswalk](ELYSE_ACQ_DPS_DISPATCH_MAP_2026-09-29.csv)
and [read-only extractor](../tools/map_acq_dps_dispatch.py) join three independent
identities: `DPS` VCTP field order, timeout selector `8105` property targets,
and the runtime Event Structure `43` `EventNodeEvents.ddoUID` table. This does
not rely on the incorrect front-panel-order `gRef.paramIdx` shortcut.

The `DPS` cluster contains 29 Boolean fields. The saved timeout subframe 2
converts it to an array, searches for `True`, increments the resulting index,
and selects one of 25 diagrams: `0` default plus `1..24`. Thus the first
asserted bit among `DPS[0..23]` chooses one local control. Each numbered arm
feeds literal Boolean `True` to both `Value` and `Val(Sgnl)` on a single
property node. The map identifies the actual property target by its `ddo`
UID, then matches that UID against the event registration table. `DPS[24..28]`
have no numbered selector arm in this structure; when none of the lower bits is
asserted, the selector falls to the default arm (`ACTION=False`). Exact PSP
poll timing, race with request reset, queue behavior, and multi-request loss
are not established by this static graph.

## Registration result

- **23/24** numbered request arms target a control registered in Event
  Structure `43`. The event case indices are not the same as the DPS field or
  selector indices: e.g. `DPS[15]` selects arm 16 and registered event 20
  (`Marche alimentation HT`), while `DPS[16]` selects arm 17 and event 22
  (`Reset alimentation HT`).
- **One arm is orphaned:** `DPS[22]` (`X Alimentation aimant = PT`) selects arm
  23 and writes `Value=True` and `Val(Sgnl)=True` on local control `ddoUID`
  `66459`. That UID is absent from all 26
  `EventNodeEvents` entries. The saved ACQ event structure therefore has no
  handler for this request. A property write is not an actuator procedure.
- Event cases 0, 1, and 2 are respectively timeout and separate direct/deviated
  line controls; the remaining 23 registered cases correspond to the 23
  mapped procedure requests. This is a structural correspondence, not proof
  that every event reaches a card write or that readback confirms success.
- The [raw status-field write inventory](ELYSE_ACQ_STATUS_FIELD_WRITES_2026-09-29.csv)
  independently finds a literal `False` assignment to the matching `DPS`
  request bit in **all 23 registered procedure event cases**. It finds no
  analogous fieldwise reset for `DPS[22]`, consistent with its absent handler.
  This inventory omits whole-cluster and remote bank writes, so it does not
  prove that the PT bit can *never* be cleared by another actor.

If `DPS[22]` remains `True` across timeout polls, the first-True selector
will choose its unhandled arm repeatedly. A simultaneous or later
`DPS[23]` magnet-stop request has a higher index and can be starved until
the PT bit is cleared externally. This is a static **conditional risk**, not
an observed failure: remote Supervision updates, queue timing, and deployed
source equality have not been verified.

## Python-transfer constraint

Do not implement `Alimentation aimant = PT` by extrapolating from magnet-start
or zero-setpoint procedures. Treat it as unsupported until another source
establishes its intended behavior. Preserve the first-True selection and
explicitly handle simultaneous requests and the five non-dispatched trailing
bits in any simulator; do not silently claim queued execution. Before
hardware replacement, validate command clearing, read/write bank ownership,
event scheduling, and the physical readback path separately.
