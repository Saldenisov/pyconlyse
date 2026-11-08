# ACQ EPS publication relative to cooling events and timeout guard (2026-09-30)

## Question and evidence boundary

When can a local EPS `OK` assignment reach Supervision relative to ACQ's
cooling-start handler and timeout flow guard? This is a static LabVIEW
dataflow/topology question. It does not measure runtime latency, PSP
reliability, physical water flow, or deployed-binary parity. No VI, PSP
variable, XP host, or NI card was operated.

The source is
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`
(SHA-256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`).
The [validator](../tools/validate_acq_eps_publish_parallel.py) pins that
archive and checks loop topology, EPS local-reference index, direct data and
PSP-URI wires, and the wait node.

## Direct observations

Outer sequence `359`, runtime frame 2 (`367`), contains two *sibling* While
loops as direct diagram nodes:

- While `102` contains Event Structure `43`: event 3 cooling start, event 4
  cooling stop, and event 0 `Timeout`, whose ordered frame 3 includes the
  [cooling-flow guard](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md).
- While `203` contains seven-frame sequence `1244`. Frame 1 (`7392`) wires
  local EPS `paramIdx=44`, terminal `18639`, to shared-variable writer
  `18665` data terminal `18680`; URI terminal `18802` directly feeds writer
  URL terminal `18667`, targeting
  `ni.var.psp://10.20.30.2/SUPERVISION/EPS`. The While body also contains
  an **80 ms** `Wait (ms)` node. That wait is not a measured loop period:
  card reads/writes, PSP transfers, error paths, and scheduling add time.

The [cooling-start trace](ELYSE_ACQ_COOLING_START_COMPLETION_2026-09-30.md)
places literal EPS[2] (`Marche refroidissement OK=True`) and EPS[8]
(`Marche GENERAL Mod. OK=True`) assignments in event 3 frame 10, followed
by frame 11's DPS PSP write and **5000 ms** wait. EPS itself is not published
by event 3; the sibling read/write loop is its visible publisher. The
[cooling-stop trace](ELYSE_ACQ_COOLING_STOP_COMPLETION_2026-09-30.md)
assigns its EPS fields in event 4 frame 5, likewise leaving their publication
to the separate loop.
In the copied Supervision VI, [EPS ingest wires](../tools/validate_sup_eps_ingest.py)
read `ni.var.psp://localhost/SUPERVISION/EPS` in sequence `9257` frame 2
(`26343`), then write the 77-field result to local reference `paramIdx=175`.
This establishes a saved-program cross-computer **publish/read path**, not
successful delivery, freshness, or eventual visible UI behavior.
The ACQ [Timeout writer audit](ELYSE_ACQ_EPS_WHOLE_CLUSTER_INGEST_2026-09-30.md)
also finds a remote EPS read back into ACQ's local cluster. The path is
therefore bidirectional at the ACQ local-state boundary; publish/read
ordering can change the next local snapshot.
The [five Modulateur OK wires](ELYSE_SUP_MODULATOR_OK_FROM_EPS_2026-09-30.md)
do, however, show a direct local projection of EPS[8,14,20,26,32] after
ingest. That resolves the source of those indicators in the saved VI,
without verifying actual front-panel state or independent hardware status.

## Bounded control-flow inference

Within one Event Structure execution, event 3's ordered frames must finish
before the same Event Structure can handle another `Timeout` event. Thus its
own timeout flow guard cannot execute during event 3's final 5000-ms wait.
The sibling read/write loop is not nested inside that event handler and is
eligible to read/publish the newly assigned EPS flags during the wait.
Therefore **an early remote EPS `OK` state is possible in the saved software
topology before the next timeout flow-guard evaluation**. It is not guaranteed:
the writer may be delayed, fail, publish an earlier snapshot, or be affected
by shared-variable scheduling. Nor does this establish that the UI treats
those EPS flags as a measured water-flow permissive. The separate [Page
Fluides display](ELYSE_SUP_FLUIDES_DISPLAY_FLOW_CORRESPONDENCE_2026-09-30.md)
copies raw C3/C4 input bits rather than replacing them with EPS `OK` flags.

The Python projections intentionally distinguish the two domains:
`acq_status_projection.py` models literal EPS assignments, while
`supervision_status.py` models raw input displays. Neither authorizes
hardware operation or models real PSP timing. A faithful future simulator
should model the event loop and I/O publisher as distinct schedulers and
include freshness/failure states; a single synchronous `start → OK → flow
check` function would erase the relevant ordering.

Reproduce offline:

```powershell
python tools/validate_acq_eps_publish_parallel.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_sup_eps_ingest.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
```

## Open points

- Measured EPS publish latency, write-error behavior, and whether the
  deployed program has this topology.
- Supervision's use of EPS[2] outside the five mapped Modulateur indicators,
  actual display refresh timing, and stale-data indication.
- Independent physical interlock timing and actual input polarity.
