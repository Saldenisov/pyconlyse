# ELYSE Acquisition: XP source dependencies (2026-09-29)

Scope: read-only inspection and Explorer copies from `10.20.30.10`. Acquisition VI was running; no VI was run, stopped, or saved, and no hardware command was issued during this copy pass.

| XP source | Local evidence copy | Content / SHA-256 | Status |
|---|---|---|---|
| `C:\PILOTAGE_ELYSE_ACQ\ACQUISITION.llb` | `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\ACQUISITION.llb` | 1,359,540 bytes; `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A` | Captured 2026-09-22 per `source_manifest.json`; *not* re-copied or hash-compared with live XP file in this pass. |
| `C:\Program Files\National Instruments\LabVIEW 2012\instr.lib\chr62000` | `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\chr62000` | 18 files; `chr62000.llb` 1,925,890 bytes, SHA-256 `613571F23CBD2C19899C73806431E1D91EC26ABFDD1857EA507E63E577E218D7` | Copied 2026-09-29. Contains the CHROMA source library and DLL needed for native inspection of focal-supply calls. |
| `C:\PILOTAGE_ELYSE_ACQ\TPG300` | `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\TPG300` | 31 files, including 23 `.vi`; `Initialize.vi` SHA-256 `A64EC13F3EBECEF4C47B7208B0F8B8F49E5E0F54F3D65C6604284C0EE9736481` | Copied 2026-09-29. TPG300 serial driver source. |
| `C:\PILOTAGE_ELYSE_ACQ\Copie de ACQUISITION.llb` | `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\historical_archive_2014\Copie de ACQUISITION.llb` | 1,168,446 bytes; SHA-256 `CC4FED2E0446D2E81C6490F7060FD22D4DFC993CF398A5D98DBEE8A01A8708A0` | Copied inadvertently while selecting adjacent Explorer row. Historical archive, **not** the deployed source. Kept separate from primary evidence. |

The local LabVIEW 2020 32-bit open attempt showed a missing-VI prompt for `chr62000 Set Current Slew.vi`. A literal-string check confirms this exact member name inside the copied `chr62000.llb`, along with `chr62000 Initialize.vi` and `chr62000 Set Output.vi`. The copied driver should make source-level inspection possible, but the open attempt has **not** been completed or verified. It would be unsafe to infer behavior from a broken VI load. The active runtime logic is still not wire-verified for every nested frame/case, selector, error path, and side effect. See `ELYSE_ACQ_NATIVE_FRAME_COVERAGE_LEDGER_2026-09-28.md` and `ELYSE_ACQ_RADIOPROTECTION_REAUDIT_2026-09-29.md` for the exact coverage boundary.

Name audit: the earlier native-frame ledger transcribed focal-driver nodes as `chr6200d ...vi`. Raw `1_Focales ON.vi` and `1_Focales OFF.vi` members instead contain all six `chr62000` call names (`Initialize`, `Set Voltage`, `Set Current Slew`, `Set Current`, `Set Output`, `Close`) and the dependency path `<instrlib>\chr62000\chr62000.llb`. The copied vendor LLB contains the matching VI names. The ledger spelling has been corrected; vendor-driver behavior and exact runtime binary identity remain unverified.

The copied `TPG300-Get Pressure-Status.vi` contains a literal reference to `TPG300-Driver Core.vi`; both files are present in the copied TPG300 tree. This is dependency evidence, not a verified command/response trace.
