# Acquisition cooling start: command sequence and status assignment (2026-09-30)

## Question, source, and limit

This note follows a `DPS[0]` cooling-start request through the saved ACQ
event 3, asking what the *software* commands and what it calls complete. It
does not establish a physical water-flow truth table, relay polarity,
electrical pulse width, or that the deployed executable matches this copy.
No VI, PSP variable, XP host, or NI card was operated.

Source: `legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`
(SHA-256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`),
the saved [event 3 screenshot](../../ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0024-event03-start-cooling.png),
the [DPS dispatch map](ELYSE_ACQ_DPS_DISPATCH_MAP_2026-09-29.csv), and the
[raw-wire validator](../tools/validate_acq_cooling_start_completion.py).
The validator checks the source hash, case polarity, all eight Boolean
command-to-bundle wires, local bank references, completion fields, and the
final DPS PSP destination.

## Direct observations

The ACQ timeout dispatcher maps `DPS[0]` to `Val(Sgnl)=True` on event 3's
`Marche refroidissement` control. Event Structure `43`, frame 3 (`19818`),
uses the event `NewVal` Boolean as the sole selector of Case `19197`. Its
False arm is empty; True arm contains ordered sequence `18783`, **12 frames**
numbered 0–11. Event 3 has direct local references only for C3 output
(`paramIdx=17`), C4 output (`15`), a graph (`35`), DPS (`36`), and EPS (`44`):
there is no *direct* C3/C4 input-bank reference in this handler. That does
not exclude other loops, subVIs, or hardware interlocks.

| Frame | Saved VI's local command or wait | Evidence |
|---:|---|---|
| 0 | `C3_OUT_DIO96[0]=True`; 1000 ms wait; graph flag | bundle `21228`, constant `01`, root literal `0x3E8` |
| 1 | `C3_OUT_DIO96[0]=False` | bundle `23018`, constant `0000` |
| 2 | 800 ms wait | `Wait (ms) 20441`, `0x320` |
| 3 | `C3_OUT_DIO96[3]=True`; 1000 ms wait | bundle `25003`, constant `01` |
| 4 | `C3_OUT_DIO96[3]=False` | bundle `31643`, constant `0000` |
| 5 | `C4_OUT_DIO96[0]=True`; 1000 ms wait | bundle `23543`, constant `01` |
| 6 | `C4_OUT_DIO96[0]=False` | bundle `26151`, constant `0000` |
| 7 | 500 ms wait | `Wait (ms) 18515`, `0x1F4` |
| 8 | `C4_OUT_DIO96[2]=True`; 1000 ms wait | bundle `28120`, constant `01` |
| 9 | `C4_OUT_DIO96[2]=False` | bundle `21883`, constant `0000` |
| 10 | Set EPS and DPS local status fields | bundles `18625`, `23709` |
| 11 | Write DPS to `ni.var.psp://10.20.30.2/SUPERVISION/DPS`; 5000 ms wait | writer `5681`, URI literal `2549`, `0x1388` |

The [saved field inventory](ELYSE_ACQ_SHARED_VARIABLE_FIELDS_2026-09-28.csv)
labels C3 outputs 0 and 3 as Canon/Section cooling start, C4 output 0 as
low-level modulator start, and C4 output 2 as low-level modulator reset. The
four `True→False` pairs are therefore a *coupled command sequence*: asking
Supervision to start cooling also sends two modulator-related commands.
The aggregate literal wait budget is **10.3 s**, excluding scheduling and
card-write-loop latency. A wait and a local field assignment in the *same*
sequence frame are not dataflow-ordered against one another, so the saved
graph does not establish the exact electrical pulse duration.

Frame 10 directly assigns:

| Local bank | Index | Value | Field label |
|---|---:|---|---|
| EPS | 0 | False | `Marche refroidissement` |
| EPS | 1 | False | `Marche refroidissement ED` |
| EPS | 2 | True | `Marche refroidissement OK` |
| EPS | 5 | False | `Arret refroidissement OK` |
| EPS | 8 | True | `Marche GENERAL Mod. OK` |
| DPS | 0 | False | `Marche refroidissement X` |

The `OK` flags are set by **literal constants in the procedure**, not by a
readback wire in this frame. Frame 11 publishes DPS, not EPS, to the listed
Supervision PSP endpoint. A [sibling I/O loop](ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md)
contains the separate EPS PSP publisher; its actual delivery timing and
error outcome remain unmeasured.

## Inference, interaction, and Python boundary

Since event 3 and the [cooling-flow safety check](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md)
reside in the *same* Event Structure `43` (event 3 versus `Timeout` event 0),
that Event Structure cannot enter another timeout handler while its ordered
event-3 sequence is still executing. This is a software event-loop scheduling
constraint, **not** a claim that the apparatus lacks an independent hardware
interlock or another monitor. In particular, the final 5000 ms wait is after
the local `OK` assignments and lies inside event 3.

The existing declarative `cooling.start` plan in
`DeviceServers/control/elyse_acq/plans.py` has the four output targets and
wait literals in this order. Its serialized write-then-wait representation is
an *approximation* of LabVIEW frame-level concurrency, not an electrical
timing guarantee. The new pure
`project_cooling_start_local_completion` function in
`DeviceServers/control/elyse_acq/acq_status_projection.py` projects exactly
the six local status assignments without executing the plan, publishing
PSP, or accessing hardware. Tests verify the assignments, preservation of
other fields, shape validation, and the existing plan's targets/timing.

Reproduce without a VI:

```powershell
python tools/validate_acq_cooling_start_completion.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_acq_status_projection
```

## Still unresolved

- Whether the saved event 3 is the deployed one; delivery/acknowledgement of
  the DPS request and shared-variable writes.
- NI output-loop schedule, electrical polarity, measured contact response,
  water-flow threshold, and any independent hardware interlock.
- When the sibling loop delivers EPS and when the UI sees `OK`; whether a
  subsequent flow trip can clear both cooling and modulator `OK` flags.
