# Acquisition DPS/EPS direct status writes (2026-09-29)

The [110-row raw-wire inventory](ELYSE_ACQ_STATUS_FIELD_WRITES_2026-09-29.csv)
was generated with
`tools/inventory_acq_dio_field_writes.py --bank-group status` against the
saved root VI. `gRef.paramIdx` identities come from direct PSP URI wires:
`36=DPS`, `37=DPC`, `38=EPC`, `44=EPS`. Field names come from the target
front-panel VCTP type, not literal captions. All 110 captured assignments
have Boolean literals: 26 DPS writes across 23 fields, 84 EPS writes across
39 fields. No DPC/EPC *direct fieldwise literal* assignment matched this
pattern; that is not evidence these clusters are unused. Whole-cluster,
nonliteral, and remote assignments are excluded.

The 23 registered DPS procedure handlers each clear their own request bit
to `False` on their True event arm. `DPS[22]` (magnet PT) is the sole
unregistered request in the 24-arm timeout dispatcher and has no analogous
local fieldwise reset; see the [dispatcher audit](ELYSE_ACQ_DPS_EVENT_REGISTRATION_AUDIT_2026-09-29.md).

A likely source-level status inconsistency is confirmed in event case 24,
`Arrêt impulsion modulateur`: its ordered status frame sets
`EPS[42] Arret Att Déph OK=True`, `EPS[52] Marche impulsion mod OK=False`,
and `DPS[19] X Arret impulsion mod=False`. Event 23 (pulse start) sets
`EPS[55] Arret impulsion mod OK=False`; event 24 does **not** set that
same stop-OK field in its direct literal frame. `EPS[42]` is the HF
attenuator/phase-shifter stop-OK field, also set by event 19. The raw
target field indices and source literals agree with the earlier static
description, so this is not merely a caption association error. It may be a
copy/paste defect in the saved VI; intent and deployed behavior remain
unproven. A Python parity model must record the actual write, while any
correction to the operator-visible status requires a separate decision.
The saved Supervision [Page HT projection](ELYSE_SUP_HT_STATUS_INPUT_PROJECTION_2026-09-30.md)
drives its seven audited HT indicators directly from `C4_IN_DIO96`; it does
not route `EPS[55]` into those indicators. This does not establish whether
other UI fields consume `EPS[55]`.

Another cross-procedure write merits review: event 3,
`Marche refroidissement`, sets `EPS[8] Marche GENERAL Mod. OK=True` while
also setting its cooling statuses. Event 5, `Marche GENERAL Mod.`, sets
the same general-OK field `True`; event 6 clears it. This means the saved
cooling-start code can mark the general modulator stage OK without passing
through event 5. Whether this is intentional, a copied field, or harmless
because of upstream sequencing is unresolved. It is not an observed
interlock bypass or hardware-ready proof.

No EPS `OK` assignment alone proves hardware acknowledgment. These fields
are set by procedure code; card readback and failure propagation need
separate tests. No VI or hardware was run for this audit.
