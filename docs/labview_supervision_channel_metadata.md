# SuperVision camera channel metadata

Camera telemetry preserves the observed channel as an unsigned 32-bit integer:
`0..4294967295`. This is the existing wire representation. Hardware configuration
and command validation retain their existing policies.

## Source evidence and limits

Read-only inspection used the frozen, natively saved LabVIEW 2020 main with
SHA256 `c81835ad9e32618ff4e04569149de537c59f7dff6d76767c6116017b8549bd91`.

- Front-panel control UID `19558`, `Voies NI1409`, is a `stdRing` with underlying
  `NumUInt16`. Its four labels are `Translateur 1`, `MUX/LASER 2`, `LASER 1`, and
  `Translateur 2`. The saved index/default is `2`.
- Five setup-channel wires, `54577`, `63403`, `187636`, `70755`, and `71941`, start
  at local reads with parameter index `111` and type label `Voies NI1409`.
- Initial setup wire `38489` starts at the `Channel` I32 zero constant.
- The ring records `StdNumMin=0` and `StdNumMax=65535`. Four ordinary UI choices
  support indices `0..3`; this bounded trace establishes no hard numeric or
  physical channel-domain restriction. Widening the observed U16 to U32 preserves
  its value. No clamp or remapping is applied.

The unchanged observer
`SUP_Camera_Observe_U8_UNCOMPILED.vi`, SHA256
`c6387a4d2d5f41ded7829ed154c89c89faa840b2aa844c1f0803d76b04c235e9`,
carries channel input terminal `959` through signal `6458`, case tunnel `6457`,
accepted branch terminal `6456`, and signal `6489` to metadata bundle terminal
`2940`. The source audit found no other channel consumer or comparison there.
This trace provides no physical calibration, exposure timestamp, waveform
measurement, or successful-write acknowledgement.

## Admission change

The native binary header and shared video-frame metadata validator admit the
full U32 value. JSON still requires an exact integer; negative values, overflow,
Booleans, strings, and nonintegral numbers are rejected. No schema version,
transport endpoint, queue, configuration command, or hardware operation changes.

Existing packet limits remain:

| Field | Limit |
|---|---:|
| Native header | 95 bytes |
| Owned U8 pixels | 524288 bytes |
| Native binary packet | 524383 bytes |
| VI JSON observation | 921600 bytes |

`tests/unit/test_supervision_camera_channel_wire.py` verifies exact channel
roundtrips for `0`, `3`, `4`, `65535`, and `4294967295`, downstream owner-frame
validation, invalid JSON values, maximum payload size, and unchanged geometry
and byte-count rejection. The earlier native-shape test no longer treats channel
`4` as malformed.

Validation: actual Python 3.4 ran 35 tests, with 32 passing and 3 modern-only
skips. Python 3.12 passed 44 tests covering the new channel cases, existing
SuperVision ingress, and federated video. These are RAM-only protocol tests;
LabVIEW execution, hardware access, and XP deployment were not performed.
