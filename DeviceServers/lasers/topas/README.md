# WinTopas4 / TOPAS Tango server

`DS_TOPAS` controls a Light Conversion OPA through the installed Topas4 Server
REST API. The WinTopas4 GUI can stay closed; its Topas4 Server process must remain
running. No USB driver replacement,
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
vendor server was started by WinTopas4 in the interactive desktop session and
remained running after the GUI closed. It is independent of diagnostic SSH
sessions. This does not establish automatic vendor-server startup after reboot.

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

### Elysium2 permanent Tango instance

The instance was registered on 2026-11-20 as `DS_TOPAS/T21082`, host `elysium2`,
mode 1, level 1. `tango/admin/elysium2` starts
`C:\dev\pyconlyse\DeviceServers\DS_TOPAS.exe`. This small launcher reads
`DS_TOPAS.runtime.json` beside the executable:

```json
{
  "python": "C:\\Users\\ECX-3100\\.conda\\envs\\pyconlyse312\\python.exe",
  "root": "C:\\dev\\pyconlyse-releases\\topas-718157345",
  "tango_host": "10.20.30.202:10000"
}
```

Compile `DS_TOPAS_launcher.cs` with the Windows .NET Framework C# compiler and
`/reference:System.Web.Extensions.dll`. The launcher owns the Python process in
a Windows job with `KILL_ON_JOB_CLOSE`, redirects logs to `DS_TOPAS.log`, and
does not start or stop the vendor server. A Starter stop/start was checked:
the old launcher and Python child both exited, then the replacement returned
fresh `ON` telemetry while the same vendor server stayed running.

## Web Equipment panel

Open **Equipment → Electronics → TOPAS** (`/topas`). TOPAS is also linked from
the Electronics Controllers page. The panel provides wavelength and
interaction selection, shutter control, output information, operator messages,
and all installed motor readbacks with manual targets in physical units or
steps. A target must satisfy configured travel and forbidden ranges; accepted
motor commands require matching target readback within one hardware quantum.
No homing or calibration editing is added.

Saved wavelengths are local browser drafts, not complete motor-calibration
presets. Loading one does not move hardware; Set or Enter submits it. Draft
edits survive telemetry refresh. Stale data are marked and disable motion.

The panel uses the existing Web device API and its hardware-approval transport.
`SubmitOperation` receives a unique request ID and an allowlisted command. The
Tango monitor deduplicates IDs, so a retry in the generic Web transport does not
repeat a hardware write. Background reads never enqueue writes.

The frontend is deployed with new hashed assets and an updated index; existing
hashed assets remain available to open tabs. No Web backend change or Web
restart is needed for this panel.

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
The vendor acknowledges shutter commands before feedback necessarily changes.
After one PUT, the client polls GET feedback for up to two seconds; it never
repeats that PUT. Missing, invalid, or persistently mismatched feedback marks
the command outcome uncertain instead of claiming successful motion.

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
database. The subsequent permanent instance and Web path use the same driver;
the release was independently extracted and SHA-256 checked on Elysium2.

At the Web-panel update, driver tests passed `34/34` and focused frontend tests
passed `10/10`. The production frontend compiled with existing warnings in
unrelated components. The deployment checks hashes of the complete live
frontend input set before installing the bundle, retaining concurrent edits.

Initial browser validation followed Equipment's TOPAS card, read all 12 installed
motors, retained an edited wavelength draft across Refresh, and submitted the
unchanged `600 nm / SH-SIG` setting using both Enter and Set. Both submissions
reached `accepted`, followed by fresh idle readback at `600 nm`, with the shutter
still closed. This checks the Web-to-Tango path without testing a new optical
setting or opening the laser shutter.

## Protocol references

- [Light Conversion API description](https://lightconupdater.blob.core.windows.net/documentation/WinTopas4/apis.html).
- [Official SDK and examples](https://github.com/DomasM/Topas4PublicAPI).
- [Existing MBI Tango implementation](https://github.com/MBI-Div-B/pytango-LightConversionTopas).

The existing Tango implementation was reviewed as a compatibility reference.
This implementation uses the documented endpoints with bounded requests,
background telemetry, nonblocking command submission, explicit operator
confirmation, and no automatic hardware writes on startup or shutdown.
