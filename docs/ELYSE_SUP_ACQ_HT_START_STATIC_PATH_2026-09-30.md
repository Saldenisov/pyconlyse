# HT-start request: static Supervision → Acquisition path

This note follows one saved-code path, `Page HT.Marche HT` to Acquisition
event 20. It does not establish permission to energize HT or describe the
deployed machines' current state. Neither VI, PSP server, nor card was run.

## Observations

1. In saved `0_SUP_ELYSE.vi` event 15, `Page HT[10] Marche HT` connects to
   `DPS[15] X Marche alimentation HT` in the shared-variable write branch.
   That branch is selected only when the 29-field local DPS cluster and
   eight Page HT adjustment controls are all false. The complete gate and
   five-field write mapping are checked by the
   [Supervision validator](../tools/validate_sup_ht_request_gate.py).
2. Acquisition timeout sequence UID 10111 reads PSP-backed local
   `paramIdx=36` (`DPS`) in frame 0. The DPS-to-URI identity is independently
   grounded by the [local PSP-wire map](ELYSE_ACQ_LOCAL_REFERENCE_MAPPING_AUDIT_2026-09-29.md).
   In frame 2, that local feeds `Cluster To Array` → `Search 1D Array(True)`
   → `Increment` → selector UID 8105. Selector arm 16 corresponds to
   zero-based DPS field 15. It writes literal True to `Value` and
   `Val(Sgnl)` on control DDO UID 59314.
3. Runtime Event Structure UID 43 registers that DDO UID as event case 20.
   Its event-data Boolean drives a two-arm case: false arm UID 53972 is
   empty; true arm UID 53978 contains five ordered procedure frames. The
   [existing procedure trace](ELYSE_ACQ_MODULATOR_HT_COMMAND_TRACE_2026-09-29.md)
   identifies the command as `C4_OUT_DIO96[18]` True → False with a nominal
   150 ms intervening wait, then sets EPS command-status fields, clears
   `DPS[15]`, publishes banks, and waits 100 ms. Those EPS `OK` fields are
   software assignments, not measured hardware acknowledgement.
4. The Acquisition timeout dispatch frame's local references are indices
   21, 35, 36, 39, and 43. Event 20's local references are 15, 35, 36, and
   44. Neither frame contains `paramIdx=16` (`C4_IN_DIO96`). The upstream
   Supervision Page HT event likewise contains no direct C4 input or Page
   Radioprotection local reference. Thus these *specific* request, dispatch,
   and command-event branches have no direct C4 input check. This does not
   exclude checks elsewhere, electrical interlocks, changed deployment,
   stale PSP state, or a later card-write failure.

## Python transfer

The [pure Page HT projection](../DeviceServers/control/elyse_acq/supervision_requests.py)
now returns either the projected 29-field DPS snapshot or `None` if the
saved branch is not selected. It never publishes the snapshot. The existing
[`dps_bridge.py`](../DeviceServers/control/elyse_acq/dps_bridge.py) maps a
single 24-field procedure snapshot to the first asserted ACQ procedure; a
start-HT projection selects case 20. Neither function schedules an event,
checks hardware permission, clears an actual request, or writes a card.

## Reproduction and limits

The Acquisition source is the copied `ACQUISITION.llb`, SHA-256
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
Its extracted `0_ACQ_ELYSE.vi` member is SHA-256
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The [stable XML archive](../legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip)
is SHA-256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`.
Its `vi_BDHb.xml` is SHA-256
`36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB`;
`vi.xml` is SHA-256
`71E0929301A628DB3DB814C1ADF8C679C6AEF1C10416BFAFD139EED636C59AAC`.
The XML was extracted by offline parser; its warnings and the absence of a
deployed-copy hash check prevent a claim of operational parity.

```powershell
python tools/validate_sup_ht_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python tools/validate_acq_ht_request_ingress.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
```

The Acquisition validator pins source-export hashes, field schema, timeout
read/dispatch wires, first-True case range, property target and value, event
registration, true/false event arms, and local-reference sets. It cannot
prove that a PSP update is observed on a particular poll, that the physical
HT contact changes, or that an external interlock accepts the command.
