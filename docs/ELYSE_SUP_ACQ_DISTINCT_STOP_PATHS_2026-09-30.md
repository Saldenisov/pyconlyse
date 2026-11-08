# ELYSE: two distinct saved-code stop paths

## Question and evidence boundary

Does the Supervision `Arrêt MOD` control initiate Acquisition's
outer-frame-3 seven-phase controlled stop? The saved graphs establish
**two different paths**, not that equivalence. This note compares copied
VIs only. Neither deployed version, PSP delivery, physical output, nor
operator safety procedure was tested.

| Path | Supervision producer | Acquisition branch | Proven local effect | Not established |
|---|---|---|---|---|
| Normal Modulator General stop | Event 18, `Arrêt MOD` → `DPS[3]` (`X Arrêt GENERAL Mod.`) | Timeout first-True DPS dispatch → event 6, `Arrêt GENERAL Mod.` | Event-6 frame 15 clears `EPS[8,14,20,26,32]`, sets stop-OK `EPS[11,17,23,29,35]`, clears `EPS[9]` and `DPS[3]`. Its other ordered frames belong to that procedure. | Request delivery, card output outcome, and whole event-6 procedure parity. |
| Outer controlled/general stop | No Supervision action has been traced to its local selectors. | After five runtime loops exit: `TCP ED=True` selects outer frame 3; `Arrêt général=True` selects seven ordered phases. | Command ramp, NI6602 task-stop attempts, HT-supply command, C6/C7 zero commands, C4/C3 stop pulses, status assignments, and `stop urgence` exit flag are statically traced in the [phase audit](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md). | Who sets `Arrêt général=True`, whether this path is reachable during ordinary Supervision operation, physical result, and fault recovery. |

The `DPS[3]` bridge is checked by
[`validate_dps_crosswalk.py`](../Supervision/integration_analysis/validate_dps_crosswalk.py)
against saved Supervision and Acquisition exports. Event-6 final status
wires are checked by
[`validate_acq_general_stop_status.py`](../tools/validate_acq_general_stop_status.py).
The [two-path raw-wire comparison](../tools/validate_acq_two_stop_paths.py)
finds a deeper shared/different structure: both paths issue the same
logical C4 stop-output pairs on fields `8,17,6,4,1` in that order. Normal
event 6 additionally calls `1_Focales OFF.vi` (its error output feeds
`Clear Errors.vi`) before those pulses, updates five Modulator stage-OK
and stop-OK EPS fields, and has a direct DPS PSP writer in its last
frame. The seven-phase outer stop has **no** `1_Focales OFF.vi` call or
direct PSP writer within its sequence; its only local EPS assignments
there are the duplicated cooling statuses in phase 5. This is a
saved-code difference, not proof that focal supplies stay on or that
Supervision actually sees stale status: other controllers and the sibling
EPS publisher may affect observed state.
`Arrêt général` (`paramIdx=47`) has no root-diagram local True writer in
the copied ACQ source, according to the
[hash-pinned raw-local census](../tools/validate_acq_stop_ingress.py) and
[`ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md`](ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md).
The root control may be changed through its front panel or another
external mechanism; neither is proven here. No cross-computer command
should be invented for it in Python.

Two ACQ PSP-*write* error branches set both `stop=True` and `TCP ED=True`.
The checked PSP-*read* error branch sets both False. The first assignment
selects outer frame 3 after the runtime loops exit, but it does not itself
set `Arrêt général=True`. If that control remains False and `stop
urgence` remains False, the saved outer stop loops have no in-diagram
exit established by the audited branches. This is a **conditional
liveness gap**, not evidence that the installed equipment hangs or
that radioprotection is absent. Hardwired protection and other software
paths remain outside this proof.

## Python transfer rule

Keep `DPS[3]` event-6 General Modulator stop separate from the
outer-frame-3 seven-phase procedure. The simulator may replay each as a
distinct, non-actuating transition only when its respective trigger is
supplied explicitly. Do not alias `Arrêt MOD` to `Arrêt général`, infer
successful stop from EPS literals, or expose either as a verified safe
shutdown operation.
