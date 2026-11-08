# Supervision Page HT status projection (2026-09-30)

## Question and source boundary

Do the main `Page HT` status indicators display Acquisition procedure `EPS`
success bits, or digital-input observations? This audit reads the saved
`0_SUP_ELYSE.vi` exports only. No VI, PSP variable, or NI card was run or
changed.

The stable [source-export archive](../Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip)
has SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`.
Its raw block-diagram member `vi_BDHb.xml` has SHA-256
`36FC7E7C93FBA9A533D6B44609F9ED0F58FB3AA911E4F88B8A8648CD55124A93`;
its main `vi.xml` type export has SHA-256
`9EB636BC9FBD8596938A5F518DE06BA1C23D21FEF2556D13B1D44D46E54E2FA6`.
The copied VI has SHA-256
`2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B`.

## Observation: seven direct source-to-display wires

In sequence UID `36869`, frame 17 (diagram UID `48064`), `gRef 48083`
(`paramIdx=29`) supplies the `C4_IN_DIO96` cluster to `nMux 48101`. `nMux
48263` updates the `Page HT` cluster, using `gRef 48226` as its base and
`gRef 48677` as its destination (`paramIdx=168`). The seven terminal pairs
below are direct signals, with no Boolean inversion between source and
destination. Names and zero-based indices come from the exported VCTP
cluster types, not front-panel-order inference.

| C4 input index and label | Page HT index and label |
|---|---|
| 35 `V alimentation HT` | 4 `V HT` |
| 36 `I alimentation HT` | 5 `I HT` |
| 46 `Radioprotection 1, coupure HT` | 6 `Radioprotection` |
| 37 `Relais 1 ouvert` | 8 `Relais 1 HT` |
| 32 `Relais 2 ouvert` | 7 `Relais 2 HT` |
| 48 `Alimentation HT en marche` | 27 `HT en marche` |
| 49 `Alimentation HT en défaut` | 26 `HT en défaut` |

The [read-only validator](../tools/validate_sup_ht_status_projection.py)
pins both export hashes, frame and node UIDs, field indices, terminal pairs,
and destination labels. To reproduce against the saved exports:

```powershell
python tools/validate_sup_ht_status_projection.py 'Supervision\analysis\source_exports\0_SUP_ELYSE_XML_sha2257.zip'
```

## Bounded inference and Python transfer

These seven `Page HT` indicators are a display projection of `C4_IN_DIO96`
bits. In particular, `HT en marche` and `HT en défaut` are not sourced from
`EPS[55] Arret impulsion mod OK` in this frame. The [Acquisition EPS write
audit](ELYSE_ACQ_STATUS_FIELD_WRITE_AUDIT_2026-09-29.md) therefore identifies
a source inconsistency in a *procedure-status field*, not by itself a wrong
wire for these two HT indicators. This does not establish that `EPS[55]` is
unused elsewhere.

The pure [Python projection](../DeviceServers/control/elyse_acq/supervision_status.py)
copies exactly those seven raw booleans from a 64-field snapshot. Its
[one-hot tests](../tests/device_servers/control/test_elyse_supervision_status.py)
check each pair and reject malformed snapshots. It issues no commands and
does not decide whether HT is safe or permitted.

## Unresolved

- The electrical meaning of `True` for `coupure HT`, `relais ouvert`, and
  `défaut` is not established by these display wires. A green UI state is not
  proof of closed interlocks or permission to energize.
- The source, freshness, error propagation, and readback validity of the
  C4 input bank require separate Acquisition-to-Supervision tracing.
- Other `Page HT` fields, radioprotection composites, and any `EPS[55]`
  consumers remain outside this seven-wire audit.
