# VD2 Tango device servers

VD2 uses three instruments and two Hamamatsu interfaces. The C13410 streak head controls the sweep, gain, gate and shutter. The C13440-20CU ORCA-Flash4.0 V3 reads the image from the streak phosphor. DG645 supplies experiment timing, and Kymera 328i sets the spectrograph geometry. [Hamamatsu C13410 system configuration](https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/sys/SHSS0021E_C13410.pdf)

| Instrument | PyConlyse device server | Interface |
| --- | --- | --- |
| Hamamatsu C13410 streak head | [DS_HAMAMATSU_STREAK](cameras/hamamatsu_streak/DS_HAMAMATSU_STREAK.py) | HPD-TA RemoteEx. The command and data connections belong to one session. |
| Hamamatsu C13440-20CU readout | [DS_HAMAMATSU_DCAM](cameras/hamamatsu_streak/DS_HAMAMATSU_DCAM.py) | Standalone PyTango prototype over pyLabLib and DCAM. Raw frames retain unsigned 16-bit pixels. |
| SRS DG645 | [DS_DG645](instruments/dg645/DS_DG645.py) | Vendor `srsinst.dg645` or raw SCPI. Exposes delay, trigger and burst operations. |
| Andor Kymera 328i / Shamrock | [DS_ANDOR_SPECTROGRAPH](spectrographs/andor/DS_ANDOR_SPECTROGRAPH.py) | Andor SDK through `pylablib.devices.Andor.ShamrockSpectrograph`. Exposes grating, slit, wavelength and calibration axis. |

## Public implementations evaluated

- **C13410 head.** The reviewed Tango catalogue and public repositories yielded no direct C13410 head driver. Hamamatsu documents HPD-TA as the device control layer and RemoteEx as its TCP interface. `DS_HAMAMATSU_STREAK` follows that path. Sweep, MCP gain, gate and shutter control remain in this server pending a documented direct interface. [Hamamatsu HPD-TA](https://www.hamamatsu.com/us/en/product/photometry-systems/streak-camera/hpd-ta-software/U13313-01.html) · [Hamamatsu RemoteEx description](https://www.hamamatsu.com.cn/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/sys/SHSS0020E_HPD_TA.pdf)
- **C13440-20CU readout.** The GPL-3.0 ESRF Lima Hamamatsu plugin uses DCAM and has a SOLEIL C++ Tango frontend. Lima's documented Hamamatsu configuration uses the ORCA-Flash4.0 V2 C11440-22CU V2. The GPL-3.0 `tiagocoutinho/hamamatsu` Python project also offers Lima Tango integration and reports testing C11440-36U. Hamamatsu lists the C13440-20CU in its Windows driver compatibility note. Compatibility of the upstream Tango integrations with this exact sensor remains unverified. The local prototype reuses the direct DCAM path already exercised by the PyConlyse dark-readout probe. [Lima plugin and license](https://github.com/esrf-bliss/Lima-camera-hamamatsu) · [Lima hardware documentation](https://lima1.readthedocs.io/en/v1.9.8/camera/hamamatsu/doc/) · [Lima Tango device](https://lima-tango-cpp.readthedocs.io/en/master/Hamamatsu/hamamatsu.html) · [Python Hamamatsu project](https://github.com/tiagocoutinho/hamamatsu) · [Hamamatsu Windows compatibility](https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/static/sys/dcam-api-for-windows/compatibility-note/DCAM-API%20for%20Windows%20%2825.4.6953%29%20Compatibility%20Note.pdf)
- **DG645.** The Tango catalogue lists `StanfordDG645` (GPL, C++, Ethernet), `DelGen645` (GPL, C++, GPIB), and `DG645` (C++, Data Socket, licence unspecified in the catalogue). `StanfordDG645` splits the controller and the output channels into separate device classes. PyConlyse already uses the MIT-licensed SRS transport library and exposes the instrument through one device. Keeping that server preserves the existing timing and readback API. [StanfordDG645](https://www.tango-controls.org/developers/dsc/ds/2320/) · [DelGen645](https://www.tango-controls.org/developers/dsc/ds/337/) · [DG645](https://www.tango-controls.org/developers/dsc/ds/1054/) · [SRS instrument driver](https://github.com/thinkSRS/srsinst.dg645)
- **Kymera.** The GPL `AndorpySpectrometer` catalogue entry covers Shamrock USB through `andorpy` on Unix-like systems. Its catalogue lists Shamrock. Andor documents a shared Kymera and Shamrock SDK, and pyLabLib reports testing Kymera 328i through a Newton camera. The existing PyConlyse server uses that SDK family and supplies the optical revision and calibration axis expected by VD2. The catalogue entry provides a comparison point. [AndorpySpectrometer](https://www.tango-controls.org/developers/dsc/ds/2297/) · [Kymera 328i hardware guide](https://andor.oxinst.com/downloads/uploads/Kymera_328i_Hardware_Guide.pdf) · [pyLabLib Shamrock driver](https://pylablib.readthedocs.io/en/latest/devices/AndorShamrock.html)

## Standalone DCAM usage

Install the Windows Hamamatsu DCAM runtime on the camera host. Use a Python environment with PyTango, NumPy, psutil and pyLabLib. Set `TANGO_HOST` to the intended Tango database. Register the device with Jive under class `DS_HAMAMATSU_DCAM`, server `DS_HAMAMATSU_DCAM/test` and device `vd2/camera/dcam`. From the repository root, launch the registered server. [Hamamatsu DCAM runtime](https://www.hamamatsu.com/us/en/product/cameras/software/driver-software/dcam-api-for-windows.html) · [PyTango server registration](https://tango-controls.readthedocs.io/projects/pytango/en/v9.3.1/quicktour.html)

```powershell
python -m DeviceServers.cameras.hamamatsu_streak.DS_HAMAMATSU_DCAM test
```

The device starts closed. Use one C13440-20CU. Close HPD-TA and RemoteEx, and release PyConlyse Web's DCAM session with Unprepare before opening the Tango device. A test client can then run `OpenReadout`, `StartLive`, read `RawFrame` after the first sensor frame, and run `StopLive`, `CloseReadout`. `StartLive` uses the sensor's internal trigger and the existing exposure. Its ring buffer serves the newest frame, so successive reads can repeat or skip a sensor frame. `FrameStamp` and `FrameTimestampUs` describe the last successful `RawFrame` read. A single reader should use these metadata attributes if it needs frame association.

Native calls share one worker. An SDK call that exceeds 5 s reports a fault. While the native call is unresolved, the server rejects further SDK calls. Retry `CloseReadout` after the native call returns before opening a fresh session. Tango device deletion and reinitialization wait for the handle to close. The standalone interface has been exercised against fake camera data. The prior hardware validation covered PyConlyse's direct DCAM readout path.

For DG645, Kymera and the C13410 head, reuse the existing Tango registrations and [server launcher setup](../bin/windows_startup/README_WINDOWS_STARTUP.md). Read the device state and identity before issuing instrument-specific commands. The standalone DCAM server uses a separate registration from the VD2 production setup.

## Software tests

```powershell
python -m pytest --deny-network -q tests/unit/test_hamamatsu_dcam_tango.py tests/unit/test_hamamatsu_streak.py tests/device_servers/instruments/test_dg645_recovery.py tests/unit/test_kymera_vd2_grating.py
```
