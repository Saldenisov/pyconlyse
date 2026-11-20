# WinTopas4 / TOPAS Tango server

`DS_TOPAS` controls a Light Conversion OPA through the installed Topas4 Server
REST API. WinTopas4 remains usable alongside Tango. No USB driver replacement,
motor calibration change, laser power control, homing, or vendor interlock bypass
is involved.

## Identified Elysium2 installation

- Computer: `elysium2`, `10.20.30.204`.
- WinTopas4: `C:\Programs\WinTopas4\WinTopas4.exe`, version `1.153.2.0`.
- OPA configuration: `TOPAS-Prime T21082`, real-device configuration (`IsDemo=false`).
- API: `http://127.0.0.1:8004/T21082/v0/PublicAPI` on Elysium2.
- Initial readback on 2026-11-20: `600 nm`, `SH-SIG`, shutter closed,
  interlock closed, caller authorized, 12 motors.
- Verified Python: `C:\Users\ECX-3100\.conda\envs\pyconlyse312\python.exe`.

On this installation the normal GUI launch left the device server unavailable.
Launching the existing signed WinTopas4 application using **Run as administrator**
started its API server successfully in the interactive desktop session. The final
vendor server is a child of WinTopas4, not of the diagnostic SSH process.

The serial number in the API URL identifies the vendor's configured instance.
It is not an independently measured USB serial number. Vendor `Wavelength`
reports the requested target while tuning; consult `is_tuning` and
`waiting_for_user` before interpreting it as a completed setting.

## Start

1. Start WinTopas4 and its existing **T21082** Topas4 Server on Elysium2.
   The API process must remain running. Do not launch a second server for the
   same hardware. A GUI client alone does not provide the REST API.
2. Use the Python environment containing PyTango and `requests`.
3. Register once, from the repository root:

   ```powershell
   $env:TANGO_HOST = '10.20.30.202:10000'
   python -m DeviceServers.lasers.topas.add_ds_TOPAS --serial T21082
   ```

   The script refuses to overwrite an existing device. Review existing properties
   separately instead of registering over another instrument.
4. Run the Tango instance:

   ```powershell
   python -u -m DeviceServers.lasers.topas.DS_TOPAS T21082
   ```

   Astor can use `DeviceServers\DS_TOPAS.bat`; set `PYCONLYSE_PYTHON` to an
   absolute interpreter path. Registration and Tango startup never open a shutter
   or change wavelength. The vendor server must be started separately.

Default Tango device: `manip/laser/topas_t21082`.

| Property | Default | Meaning |
| --- | --- | --- |
| `api_host` | `127.0.0.1` | Vendor REST host |
| `api_port` | `8004` | Installed REST port, not discovery/web-help port |
| `topas_serial` | Required | Exact configured device serial |
| `timeout_s` | `2` | Connect and read timeout per HTTP request |
| `poll_interval_s` | `1` | Delay between completed snapshots |
| `stale_after_s` | `5` | Maximum accepted snapshot age |

## Controls and feedback

`wavelength_nm` and `shutter_open` are writable attributes. `SetWavelength`,
`OpenShutter` and `CloseShutter` provide equivalent commands.
`SetWavelengthWithInteraction` accepts, for example:

```json
{"wavelength_nm": 600, "interaction": "SH-SIG"}
```

Writes enqueue one request and return immediately. A command returns an operation
ID. Inspect `operation_json`: `queued`, `running`, `accepted`, or `failed`.
**Accepted means the vendor accepted the request; it does not mean motion has
finished.** Observe `is_tuning`, `waiting_for_user`, the reported wavelength and
`motors_json` for completion. A second pending request is rejected rather than
forming a long queue. Each write is sent at most once.

`interactions_json` contains the installed calibration ranges. The client rejects
out-of-range targets and unsupported interactions before a write. Vendor
separation checks and operator messages remain enabled.

`ConfirmUserActions` is only appropriate after the operator has completed the
instructions in `messages_json`. It sends `RestoreShutter=false`; the command
does not reopen the shutter. `Stop` requests the vendor's `Motors/StopAll`;
read motor feedback to verify physical stopping. Neither command homes motors.

`snapshot_json` retains last known data, timestamp, freshness, read errors and
command failures. Measurements from stale snapshots raise an error instead of
appearing current. State/status and cached reads never perform HTTP I/O.
`Refresh` requests another GET snapshot and does not initialize hardware.

A failed write with uncertain outcome latches `outcome_unknown` and keeps its
original operation in `snapshot_json.uncertain_operation`. It is never retried
automatically. Close-shutter and stop requests remain available. After verifying
an idle device with its shutter closed, `ClearError` acknowledges the uncertainty;
it sends no hardware command and does not replay the failed request.

## Validation

Software tests:

```powershell
python -m pytest --deny-network -q tests/unit/test_topas.py
```

Initial hardware validation should read status, calibration ranges and motors
before any change. A `200 OK` shutter response alone is insufficient: WinTopas4
can silently ignore an opening request for safety reasons. This client requires
matching shutter readback.

### Hardware checks on 2026-11-20

The committed implementation was tested with a real PyTango `DeviceTestContext`
both on Everest and on Elysium2. The Elysium2 copy was extracted into a separate
release directory and each source file was checked against a SHA-256 manifest.
The existing Elysium2 production checkout had unrelated motor/startup edits;
those files were retained.

Both runs returned `ON`, `600 nm`, interaction `SH-SIG`, 12 motors, authorized
caller, and shutter closed. Commands exercised an already-closed shutter and
the unchanged calibrated `600 nm` setting. No test opened the shutter or selected
a different wavelength or interaction. Queue-submission round trips were
`2.51 ms` from Everest and `1.97 ms` locally on Elysium2; these timings measure
command acceptance, not optical motion or tuning completion.

Open-shutter interlock rejection, manual-action confirmation, stale telemetry,
and uncertain write outcomes were exercised by software tests. The context
servers were temporary and did not register devices in the production Tango
database. Permanent Astor registration/startup remains a separate deployment
step using the commands above.

## Protocol references

- [Light Conversion API description](https://lightconupdater.blob.core.windows.net/documentation/WinTopas4/apis.html).
- [Official SDK and examples](https://github.com/DomasM/Topas4PublicAPI).
- [Existing MBI Tango implementation](https://github.com/MBI-Div-B/pytango-LightConversionTopas).

The existing Tango implementation was reviewed as a compatibility reference.
This implementation uses the documented endpoints with bounded requests,
background telemetry, nonblocking command submission, explicit operator
confirmation, and no automatic hardware writes on startup or shutdown.
