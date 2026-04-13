# Andor PyLabLib Stack

Date:
- 2026-04-13

## Implemented Direction

The Andor stack in PyConlyse is now being migrated to a unified `pylablib` backend:

- `DS_ANDOR_CCD`
  - Newton / other SDK2-era CCD cameras
  - uses `pylablib.devices.Andor.AndorSDK2Camera`
- `DS_ANDOR_SPECTROGRAPH`
  - Shamrock / Kymera spectrographs
  - uses `pylablib.devices.Andor.ShamrockSpectrograph`
- `DS_SPECTROSCOPY_client`
  - combined desktop client window for CCD + spectrographs

## Key Practical Choices

### 1. Camera orders are now frame-group based

The old Andor server logic effectively counted individual rows, which breaks multi-track payloads like:

- `2 x 1064`
- `5 groups of (2 x 1064)`

The new logic treats each acquisition frame as a unit and appends the whole multi-track frame to the order.

## 2. Wavelength axis is no longer cast away

The old base camera flow cast ordered payloads to `uint16`, which destroys floating-point wavelength calibration.

The Andor CCD server now returns order payloads as `float32`:

- row `0`: wavelength axis
- following rows: spectral tracks grouped frame-by-frame

## 3. Newton can be linked to a spectrograph in software

The CCD server keeps a `linked_spectrograph_ds` property.

If that property points to an Andor spectrograph Tango DS, the CCD server tries to use its `calibration` attribute as the live wavelength axis.

Fallback order:

1. linked spectrograph calibration
2. static `wavelengths` device property
3. pixel index axis

## 4. Web UI must treat Newton as spectra, not RGB image

The old browser camera client expects 3-channel image data.

For Newton TRAPS operation that is the wrong abstraction, so a dedicated spectroscopy page is preferable:

- plot track 1 / track 2 directly
- expose CCD trigger and exposure controls
- expose Shamrock / Kymera center wavelength, grating, slit control

## Deployment Notes

To run the new stack on the control PC:

1. install `pylablib` into the active PyConlyse environment
2. ensure Andor SDK2 DLL path is reachable
3. ensure Shamrock DLL path is reachable for spectrographs
4. set Tango device properties:
   - camera `dll_path`
   - camera `linked_spectrograph_ds` when applicable
   - spectrograph `dll_path`
   - spectrograph `shamrock_dll_path`
   - spectrograph `pixel_number`
   - spectrograph `pixel_width_um`

## Runtime Caveat

The pyLabLib documentation notes that for some Shamrock/Kymera setups it is recommended to open the camera connection before the spectrograph connection, especially when the spectrograph communication goes through the Andor camera path.

This means the final deployment still needs one hardware validation pass on the Windows host with the real Newton + Shamrock/Kymera chain.
