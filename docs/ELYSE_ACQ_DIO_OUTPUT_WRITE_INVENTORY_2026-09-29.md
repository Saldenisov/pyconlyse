# Acquisition DIO output field-write inventory (2026-09-29)

## Scope and method

`tools/inventory_acq_dio_field_writes.py` traces write-side local references for the three output clusters (`paramIdx=13` C5, `15` C4, `17` C3) to bundle-by-name nodes in the saved root VI. Those identities come from direct PSP URI wires in `ELYSE_ACQ_LOCAL_PSP_WIRE_MAP_2026-09-29.csv`, not the parser's incorrect front-panel-order assumption. For each connected field assignment, the tool records the raw field index and wire source; field names come from the owning cluster's ordered VCTP type, **not** from often-stale literal captions. Source LLB SHA-256: `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.

The machine-readable result is `ELYSE_ACQ_DIO_OUTPUT_FIELD_WRITES_2026-09-29.csv`: **136** distinct, source-qualified field-assignment wire rows. C4 has **66** literal Boolean assignments across **15** distinct fields. C3 has **70** literal Boolean assignments across **22** fields. A first pass falsely counted 870 rows by treating sibling inputs of one fanned-out `nMux` wire as independent sources; those 734 duplicates were removed. The corrected CSV retains only an external source terminal for each field. It is **not** a census of all nonliteral assignments. C5 has **no** direct fieldwise bundle assignment in this pattern; the root initializes and exchanges that bank as a whole cluster, including PSP reads. Zero rows here do not mean the bank never changes.

## Resolved logical commands

The literal C4 rows identify exact logical output bits for low-level modulator start/reset, heating, premagnetization, HT relay, focal supply, attenuator/phase-shifter chassis, and modulator HT start/stop/reset. The relevant event number and ordered frame are encoded in each CSV `scope_path`. For example:

| Event / ordered frames | Logical field sequence |
|---|---|
| 12, heating start, 0–1 | `C4_OUT[3]` (`Marche Chauffage`) True → False |
| 13, premagnetization start, 0–1 | `C4_OUT[5]` (`Marche prémagnétisation`) True → False |
| 14, HT-relay start, 0–1 | `C4_OUT[16]` (`Marche relais HT 1`) True → False |
| 15, focal start, 0–1 | `C4_OUT[7]` (`Marche focale Klystron`) True → False |
| 20, modulator-HT start, 0–1 | `C4_OUT[18]` True → False |
| 21, modulator-HT stop, 0–1 | `C4_OUT[19]` **False → True** |
| 22, modulator-HT reset, 0–1 | `C4_OUT[20]` True → False |

The literal C3 rows confirm cooling start/stop commands and the magnet-supply selection groups. Event 16 asserts six triplet/quadrupole bits in frame 0, two dipole bits in frame 2, and ten injection/guide bits in frame 4; event 17 clears the same 18 named bits in its frame 3. Outer-frame-3 stop logic also clears those 18 bits. These are **software command values**; neither a terminal voltage nor magnet-current ramp has been inferred from the literals alone.

The [source-to-plan DIO comparison](../tools/compare_acq_plan_dio_to_source.py)
finds **0 mismatches across all 23 Acquisition procedure event cases** when
comparing the multiset of target-bank/index/Boolean assignments to the local
non-actuating Python `PROCEDURE_PLANS`. This checks field identity and value,
not operation order, delays, guard conditions, output-commit scheduling, or
physical writes.

## Remaining boundary

The CSV is a **literal field-write inventory**, not a complete business-logic specification. It omits whole-cluster assignments, reads, dynamic PSP commands, nested subVI effects, and nonliteral field sources. The acquisition DIO writer is in a concurrent loop, so ordered local assignments and nominal waits do not directly measure physical pulse width. Input/interlock polarity and deployed-source equality remain unverified. The source also contains copied captions on Boolean constants that contradict the actual selected fields; any port requires index/type-checked wiring rather than translating captions literally.
