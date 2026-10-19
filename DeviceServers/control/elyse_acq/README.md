# ELYSE ACQ Tango controller

Current source/runtime boundaries, known parity gaps and the software verification
lane are indexed in [ELYSE business logic migration status](../../../../docs/ELYSE_BUSINESS_LOGIC_STATUS.md).
The pure procedure controller below, read-only LabVIEW telemetry facade and
read-only Python-runtime facade are distinct. None is a complete commissioned
replacement. `business_logic_contract()` records these limits without authorizing
actuation; `runtime_health.py` separates bridge freshness from NI-source freshness.

This package is the server-side replacement boundary for the legacy
`0_ACQ_ELYSE.vi` application on `10.20.30.10`.

Data/control path:

```text
Pyconlyse web UI
    -> authenticated high-level Tango command
    -> DS_ElyseAcq single-flight procedure controller
    -> commissioned NI-DAQmx/serial adapter
    -> NI6071E, NI6602, NI6703, DIO96, NI6220 and focal supplies
    -> physical ELYSE equipment
```

The web UI must never issue raw pin writes. It submits one named procedure
intent with an idempotency key. The controller owns ordering, timing,
readback, cancellation, state, and audit trace.

Current state:

- all 23 legacy Value Change procedures (event cases 3..25) are represented;
- procedure execution is single-flight and idempotent by `intent_id`;
- a deterministic simulator supports offline tests and UI work;
- [`vi_simulation`](vi_simulation/README.md) translates all five verified
  card initializer helpers into separate Python files with in-memory external
  returns, source-node traces and fault-injection tests. Its 21 task slots
  span cards 1..11, but it does not implement the whole root initialization
  sequence or enable hardware access;
- `dps_bridge.py` resolves 23 Supervision DPS fields to the corresponding
  immutable ACQ plans, reproduces the first-true timeout scan for one snapshot,
  projects each implemented handler's local DPS-bit reset, and rejects
  the orphaned magnet PT field; it neither executes, publishes, nor
  acknowledges a request;
- `legacy_supervision_setpoints.py` reproduces verified, pure arithmetic for
  direct/deviated beam-line arrows, HT/HF setpoints, and one-hot Page Fluides
  Canon/Section temperature steps; it is not connected to
  the Tango facade, PSP transport, or the hardware adapter;
- `supervision_requests.py` projects all five identified fieldwise Supervision
  DPS request gates (Fluides, Modulator, HF, HT, and Alimentations) without
  publishing; their [gate matrix](../../../docs/ELYSE_SUP_DPS_REQUEST_GATE_MATRIX_2026-09-30.md)
  separates local serialization from hardware permission;
  `supervision_status.py` projects raw HT,
  radioprotection, and Fluides input displays plus five EPS-derived Modulateur
  OK indicators; `acq_status_projection.py`
  models cooling start/stop, timeout flow-trip, and General Modulator stop
  plus Impulsion, magnet, and HF-power local EPS/DPS assignments and an explicitly
  supplied remote EPS snapshot
  ingest without claiming physical readback or PSP timing;
- `acq_shutdown_projection.py` models the verified logical C9[0]
  controlled-stop HT-ramp iterations and records selected verified
  field/timing constants from the seven-phase stop path, including
  NI6602 poll exit, C4/C3
  pulses, magnet-command zeros, and local EPS/DPS assignments;
  it neither stops the equipment nor performs a card write. This
  outer-frame-3 path is distinct from `DPS[3]` General Modulator stop;
  see the [two-stop-path comparison](../../../docs/ELYSE_SUP_ACQ_DISTINCT_STOP_PATHS_2026-09-30.md);
- the Tango facade refuses production hardware mode;
- no real DAQ task is created and no hardware write is possible.

The beam-line calculator requires the selected numeric step explicitly because
the LabVIEW `X1/X10` Boolean-to-step polarity has not been verified. It rejects
non-adjustment actions rather than guessing their behavior. The field/PSP
crosswalk and source-image links are in
[`BEAM_LINE_ANALOG_COMMAND_CROSSWALK_2026-09-29.csv`](../../../Supervision/integration_analysis/BEAM_LINE_ANALOG_COMMAND_CROSSWALK_2026-09-29.csv)
and [`ELYSE_SUP_ACQ_BUSINESS_LOGIC_2026-09-28.md`](../../../docs/ELYSE_SUP_ACQ_BUSINESS_LOGIC_2026-09-28.md).

The saved ACQ cooling-stop event has an additional 150-ms wait in the Section
restore frame, omitted by the existing hardware-adapter-capable
`cooling.stop` plan. The simulation-only
[`cooling-stop trace`](../../../docs/ELYSE_ACQ_COOLING_STOP_COMPLETION_2026-09-30.md)
records this discrepancy; the executable plan has not been changed pending
timing and hardware review. The saved ACQ event loop and EPS PSP publisher are
parallel, so literal EPS `OK` flags can be published before the event loop's
next timeout flow check; see the
[`EPS publication trace`](../../../docs/ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md).
The ACQ Timeout path also reads the whole Supervision EPS PSP cluster back
into local EPS; see the
[`EPS writer audit`](../../../docs/ELYSE_ACQ_EPS_WHOLE_CLUSTER_INGEST_2026-09-30.md).

Production enablement requires an adapter that has passed polarity,
interlock, safe-default, readback, and failure-injection commissioning.
`Alimentation aimant = PT` is deliberately absent because the legacy DPS
dispatcher exposes the intent but ACQUISITION has no matching event handler.
The saved HF-power and pulse-stop events can assign both opposing local
Att/Déph `OK` flags True in sequence; see the
[status-overlap trace](../../../docs/ELYSE_ACQ_HF_PULSE_STATUS_COLLISION_2026-09-30.md).
