# Electronics controllers

The Equipment Control Center exposes a dedicated **Electronics** page at
`/electronics-clients`. It discovers Tango devices by class and currently
supports:

- `DS_KEYSIGHT_33509B` — Keysight/Agilent 33509B waveform generator.
- `DS_DG645` — Stanford Research Systems DG645 digital delay generator.

The page deliberately starts passively. Selecting and loading a controller
does not power equipment and does not call `turn_on`. Each card separates:

- PDU power, when a `power_dependency_device` and output are configured;
- physical transport state;
- operational initialization state;
- the Tango device state.

The operator must press **Initialize device** before settings are enabled.
DG645 initialization is also blocked until its PDU readback is ON. The web page
does not automatically change PDU outputs; it links to the existing PDU client.

## Keysight controls

The controller provides output and burst toggles plus waveform, frequency,
amplitude (Vpp), and DC offset. Each setting has its own explicit **Set** action
and displays the value read back by Tango.

## DG645 controls

The controller provides trigger source, internal trigger rate, burst mode,
burst count, burst period, and a constrained delay editor for channels A-H.
Trigger source labels follow the DG645 programming manual (`TSRC` values 0-6).
The normal UI intentionally does not expose arbitrary SCPI commands.

`DS_DG645.delays_json` reads channels A-H into one JSON attribute for a compact
readback table. Restart `DS_DG645/1_DG645` after deploying this code to publish
the new attribute. The existing `set_delay` command remains the write path.

## Registered laboratory devices

The current Tango database contains:

- `manip/awg/keysight33509b_laser` (`DS_KEYSIGHT_33509B/MAIN`)
- `manip/sync/DG645` (`DS_DG645/1_DG645`)

DG645 is registered with the read-only power dependency
`manip/SD2/PDU_SD2`, output 2. The controller never powers that output by
itself, so merely opening the page cannot energize the instrument.

## Artwork

The Electronics card uses `web/frontend/public/images/electronics.png`, created
with the built-in image generator in a Tibetan folk-art-inspired ornamental
style. The image contains no logos, text, people, or religious figures.
