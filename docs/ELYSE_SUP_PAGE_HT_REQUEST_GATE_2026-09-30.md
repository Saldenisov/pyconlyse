# Supervision Page HT request gate: saved-code trace

Scope: `0_SUP_ELYSE.vi`, root Event Structure UID 5909, event frame 15
(UID 38707). This is a static trace of the copied VI. It does not operate
the supervision PC, Acquisition PC, PSP variables, or NI cards.

## Observed wires

The event's `Page HT` NewVal cluster enters nMux UID 40816. Its eight arrow
fields (indices 15, 13, 14, 16, 21, 19, 20, 22) feed Build Array UID 40916
and `Or Array Elements` UID 40970. Local request cluster reference
`paramIdx=176` enters `Cluster To Array` UID 40765 and another
`Or Array Elements` UID 40791. Their Boolean results enter `Or` UID 40877.
The final result drives case selector UID 38758. The selector's saved range
table maps **0 to frame UID 38901** and **1 to frame UID 39038**.

Frame 38901 (selector 0) contains the dynamic shared-variable write and
five direct Page HT → DPS wires:

| Page HT index | Button | DPS index | Request field |
|---:|---|---:|---|
| 10 | Marche HT | 15 | X Marche alimentation HT |
| 11 | Arrêt HT | 17 | X Arrêt alimentation HT |
| 9 | Reset HT | 16 | X Reset alimentation HT |
| 25 | Marche pulse MOD | 18 | X Marche impulsion mod |
| 24 | Arrêt pulse MOD | 19 | X Arret impulsion mod |

The false-frame nMux UID 38974 starts from the same local `paramIdx=176`
cluster. Its output is connected to shared-variable write UID 38989. The
29-field `DPS` schema and 28-field `Page HT` schema are checked against
the saved VCTP type export.

## Inference implemented in simulation

The five-command DPS-write branch is selected only when **all 29 current
local DPS request flags are false** and **all eight listed Page HT arrow
states are false**. This is request serialization inside the Page HT UI
event, not a safety interlock. A Boolean-only model is implemented in
[`supervision_requests.py`](../DeviceServers/control/elyse_acq/supervision_requests.py).
It reports selection of this saved branch; it never writes DPS.
The same module also projects the five button values into a new immutable
29-field DPS snapshot, or returns `None` when this branch is not selected.
That projection does not publish the snapshot.

The event frame's local references have parameter indices 24, 25, 168,
176, and 184. No direct `C4_IN_DIO96` reference or Page Radioprotection
reference occurs in this frame. Therefore this *specific* UI request gate
does not directly test those input clusters. That observation does **not**
establish whether ACQ dispatch, equipment wiring, stale PSP values, or
other VI paths prevent HT energization. The ACQ event-20 pulse trace is
separate in [`ELYSE_ACQ_MODULATOR_HT_COMMAND_TRACE_2026-09-29.md`](ELYSE_ACQ_MODULATOR_HT_COMMAND_TRACE_2026-09-29.md).

## Reproduction

Source archive:
[`0_SUP_ELYSE_XML_sha2257.zip`](../Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip),
SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`.
It contains saved `vi_BDHb.xml` (diagram export SHA-256
`36FC7E7C93FBA9A533D6B44609F9ED0F58FB3AA911E4F88B8A8648CD55124A93`)
and `vi.xml` (type export SHA-256
`9EB636BC9FBD8596938A5F518DE06BA1C23D21FEF2556D13B1D44D46E54E2FA6`).
The export is a stable copy of parser output from the saved VI, not a
LabVIEW run or save.

```powershell
python tools/validate_sup_ht_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
```

The validator pins archive/member hashes, event and case UIDs, primitive
IDs, case range, source/destination field indices, direct signal peers,
PSP write connection, and absence of direct C4/radioprotection references.
This is structural evidence about the copied VI, not runtime behavioral
verification.
