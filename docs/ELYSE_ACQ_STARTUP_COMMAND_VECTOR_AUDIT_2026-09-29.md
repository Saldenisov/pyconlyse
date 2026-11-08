# Acquisition startup AO/DO logical command vectors (2026-09-29)

## Result and evidence boundary

The startup constants feeding seven target banks in initialization frame `1/5/0` were decoded from the
saved `0_ACQ_ELYSE.vi` raw BDHb and VCTP/FPHb types. The
[152-row field table](ELYSE_ACQ_STARTUP_LOGICAL_CONSTANTS_2026-09-29.csv)
records every value, field label, source terminal, and target local reference;
the [read-only decoder](../tools/decode_acq_startup_bank_constants.py) can
regenerate it. Source LLB SHA-256:
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
No VI or hardware was run. These are *logical command cluster values*, not
measured analog volts or observed contact states.

The source constants are connected to local banks by wire and `gRef.paramIdx`;
those identities were separately fixed by direct PSP URI wires. Literal
captions are demonstrably unreliable: the constant labelled `C5_OUT_DIO96`
feeds `C3_OUT_DIO96`, and the one labelled `C3_OUT_DIO96` feeds
`C5_OUT_DIO96`. The `C6NI6703` zero constant feeds both C6 and C7; the C8 and
C9 literals also retain a `C6NI6703` caption. Field names therefore come
from each *target* front-panel cluster's ordered type, not from the constant's
own copied display caption/type.

## Nonzero/True values

| Target bank | Initial logical values differing from zero/False |
|---|---|
| `C6NI6703`, `C7NI6703` | None; ten zero-valued AO fields each. |
| `C8NI6703` | `[1]=21.0` Canon temperature command; `[2]=27.9` Section temperature command; `[6]=360.0` HF preamplifier-amplitude command. |
| `C9NI6703` | `[0]=6.5` HT supply command; `[2]=[3]=4.755` HG/HD slit-position commands; `[4]=[5]=[6]=2.126` screen-translator positions. |
| `C3_OUT_DIO96` | `[1]=True` stop Canon cooling; `[4]=True` stop Section cooling. |
| `C4_OUT_DIO96` | `[1]=True` low-level-modulator stop; `[4]=True` heating stop; `[6]=True` premagnetization stop; `[8]=True` focal supply stop; `[17]=True` HT-relay stop; `[19]=True` modulator-HT supply stop. |
| `C5_OUT_DIO96` | `[33]=True` laser stop. |

All other 134 values in the seven clusters are zero/False. The earlier
frame-coverage ledger transposed C3 and C5 initial True-bit summaries by
trusting the copied literal captions. This table corrects that transcription.
The acquisition startup subsequently publishes these banks through PSP and
calls the DIO96/NI6703 writer, so initialization is potentially actuating.
Actual card output voltage/contact polarity, write outcomes,
deployed-source equality, and physical safety are not proven.

## Software-predicted requested AO voltages

The [40-row requested-voltage calculation](ELYSE_ACQ_STARTUP_REQUESTED_AO_2026-09-29.csv)
applies the recovered `1_ACQ_WRITE_NI6703.vi` calibration map
([repository copy](../legacy/xp_acq_agent/data/calibration_map.csv)) and its
two C8 nonlinear functions ([calculator](../tools/predict_acq_startup_ao.py))
to the seven target-bank startup vectors. This is a *conditional software
prediction*: it assumes the custom writer receives those exact startup
clusters and its recovered formulas execute normally. It is not an NI card
voltage measurement or proof of a safe physical state.

The most important distinction is `C8NI6703[3]` and `[4]`: both logical
inputs are `0.0`, but the active dephaser/attenuator formulas request
`2.1775 V` and `3.8587 V`, respectively. The other nonzero C8 requests are
`[1]=2.2 V`, `[2]=3.58 V`, `[6]=9.0 V`. C9 requests `[0]=3.25 V`,
`[2]=[3]=4.755 V`, and `[4]=[5]=[6]=2.126 V`. C6/C7 and all other C8/C9
channels calculate to zero. All 40 predicted requests are within the
configured ±10 V task range. Readback, write errors, and installed VI
equality remain unverified.

The [source-to-Python validator](../tools/validate_acq_source_transfer.py)
checks the 152 startup values, the 40 calculated AO requests, the 24 DPS
dispatch mappings, and the 23 per-handler request clears against the current
non-actuating Python bridge. It passed on these copied artifacts; it does not
test live equipment or execute a procedure.

The inert [XP Python hardware plan](../legacy/xp_acq_agent/elyse_agent/hardware_plan.py)
previously carried the same C3/C5 transposition (`C3[33]`, `C5[1,4]`). Its
local `STARTUP_DO_TRUE_BITS` is now corrected to `C3[1,4]`, `C5[33]`; the
corresponding pure-plan tests were updated. This repository change was **not
deployed** to the acquisition computer. The manual hardware adapter remains
gated and is not reachable from the TCP service. No startup output was sent.
