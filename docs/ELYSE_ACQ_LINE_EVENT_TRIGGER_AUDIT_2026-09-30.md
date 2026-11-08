# Acquisition beam-line event trigger audit (2026-09-30)

## Question and boundary

Does Supervision's `Voie directe`/`Voie déviée` PSP publication explicitly fire
Acquisition's identically named local Value Change events? This audit reads
only the copied ACQ root `0_ACQ_ELYSE.vi` from `ACQUISITION.llb` (LLB SHA-256
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`)
and its BDHb XML (SHA-256
`36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB`).
It is not a trace of the running program, external VI Server clients, or PSP
delivery. No VI or hardware was operated.

## Observation

- Event Structure `43` registers case 1 (`Voie directe`) as a Value Change
  for front-panel `ddoUID=1660`; case 2 (`Voie déviée`) targets
  `ddoUID=16917`.
- All **24** explicit `Val(Sgnl)` property nodes in this saved root target
  DPS procedure controls, including orphaned magnet-PT. None targets either
  beam-line control. Each beam-line control has one `ctlRefConst` reference
  in the BDHb graph, located within its *own* event case. The
  [read-only validator](../tools/validate_acq_line_event_triggers.py) checks
  these counts, targets, containment, event registrations, and pinned source
  hash; it passes on the saved XML.
- The ACQ timeout DPS dispatcher has 24 request arms: 23 registered procedure
  events (cases 3–25) plus orphaned magnet-PT. It has no arm for line events
  1/2; see the [raw DPS dispatch map](ELYSE_ACQ_DPS_DISPATCH_MAP_2026-09-29.csv).
- ACQ line events themselves contain the same `OldVal`/`NewVal` row-mask
  chain found in Supervision: event 1 uses `And 11320` with literal 1937,
  `Array Max & Min 11355`, and `Greater Or Equal? 14212` with literal 128;
  event 2 uses `And 62802`, `Array Max & Min 62837`, and
  `Greater Or Equal? 64642` with the same literals. The [instance inventory](ELYSE_ACQ_CONTROL_INSTANCE_INVENTORY_2026-09-28.csv)
  records those input wires. This establishes source-level similarity of
  local UI branch selection, not a cross-computer event bridge.

## Bounded inference and remaining test

The saved ACQ root has **no explicit internal signaling-property path** from
the Supervision PSP bank update to its local beam-line event cases. The
confirmed cross-host path remains Supervision C6–C9 PSP writes → Acquisition
timeout C6–C9 PSP reads → Acquisition NI6703 output-bank writer. That route
does not require local events 1/2. It remains possible that another VI or an
external client triggers those controls, or that the deployed executable
differs from this copy. A future passive review can search other saved VIs
for VI Server references and compare deployed source hashes; no live command
is needed to retain this boundary.
