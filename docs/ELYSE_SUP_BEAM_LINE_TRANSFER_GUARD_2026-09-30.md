# Supervision beam-line transfer guard (2026-09-30)

## Boundary

Static read of saved `0_SUP_ELYSE.vi` (SHA-256
`2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B`),
using its extracted `0_SUP_ELYSE_BDHb.xml` (SHA-256
`36FC7E7C93FBA9A533D6B44609F9ED0F58FB3AA911E4F88B8A8648CD55124A93`).
No VI, PSP command, or card was run. This resolves the frame-1 *local setpoint
transfer* guard in events 19/20; it does not establish a hardware interlock.

## Observed source chain

| Event | Sequence | Old/New comparison | Per-row conversion and mask | Aggregate test | Frame-1 guarded case |
|---|---:|---|---|---|---:|
| 19, `Voie directe` | `14098` | `Not Equal? 7720` | loop `7742`: Cluster To Array `7791` → Boolean Array To Number `7783` → And `7799` with `0x791=1937` | Array Max & Min `7836` → Greater Or Equal? `8425`, constant `0x80=128` | `11830`, True transfers setpoints |
| 20, `Voie déviée` | `33504` | `Not Equal? 33658` | loop `33677`: Cluster To Array `33747` → Boolean Array To Number `33739` → And `33755` with `0x791=1937` | Array Max & Min `33815` → Greater Or Equal? `46437`, constant `0x80=128` | `46564`, True transfers setpoints |

Both comparisons consume the event data node's `OldVal` and `NewVal`; the
11-field row is converted to a bitmask. Bits `{0,4,7,8,9,10}` survive
`1937 = 0b11110010001`; only bits `{7,8,9,10}` can meet the `>=128` test.
Those are the four arrow-button fields in the saved row. A changed `M/A` or
`X1/X10` field alone does not enter the frame-1 True branch. The [native
event-19](../Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_19_full.png)
and [event-20](../Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_20_full.png)
screenshots show the same mask, threshold, and guarded transfer branch.

The guard is **not** a guard on the following PSP publication. Event 19
sequence frame 2 and event 20 sequence frame 2 each contain four direct PSP
writes, with no enclosing guard in those frames. The [native frame-2 prints](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd350.png)
and [deviated counterpart](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd378.png)
identify the banks as `C6NI6703`–`C9NI6703`. Thus a non-arrow UI change can
republish the pre-existing local bank values without transferring new
setpoints from the beam-line UI cluster. This is a source-level sequence, not
evidence that PSP delivery or NI output succeeded.

## Reproducible transfer check

`DeviceServers/control/elyse_acq/legacy_supervision_setpoints.py` now exposes
`beam_line_transfer_guard(line, changed_row_masks)`. It applies the exact
per-row `& 1937`, maximum, and `>=128` operation; it never publishes a bank.
The targeted test checks both lines, all four arrow bits, non-arrow bits,
multiple positions, and malformed inputs. The read-only
[`validate_sup_beam_transfer_guard.py`](../tools/validate_sup_beam_transfer_guard.py)
checks both raw terminal chains, literal mask/threshold wires, guarded
frame-1 branches, and four direct frame-2 PSP-write nodes against the pinned
BDHb SHA-256. Run it with the extracted BDHb XML path; it printed `PASS` on
2026-09-30. The standard-library test
`python -m unittest -v tests.device_servers.control.test_elyse_supervision_beam_transfer_guard`
passed 2/2 checks with Python 3.11 on the same date.

Unresolved: actual event delivery, concurrent UI/PSP writers, X1/X10 polarity
in each adjustment branch, PSP write error handling, and physical readback.
