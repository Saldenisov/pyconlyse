# New Focus 8742 through Tango

`DS_Picomotor8742` provides one controller device for four integer-step axes.
It sends documented ASCII commands over Ethernet and needs Python plus PyTango;
it does not depend on LabVIEW, CmdLib.dll, Python.NET, or the New Focus application.
No hardware connection, Tango registration, or physical movement was performed
during implementation. The transport and device lifecycle were tested offline.

## Evidence and support boundary

- [Newport 8742 manual, Rev. G](https://www.newport.com.cn/medias/sys_master/npresources/hbe/h52/9954515550238/8742%20User%20Manual/8742-User-Manual.pdf):
  Ethernet/socket support, CR commands and CRLF responses (sections 5.4, 6.1),
  slave address prefixes (6.1.1), four axes, PR/PA/TP?/MD?/ST/AB/TE?.
- The copied vendor `NpEthernet.dll` 1.0.4.0 independently contains TCP port 23,
  ASCII transmission ending in byte 13, and CRLF response handling.
- [Tango catalogue NewFocusPico8742](https://www.tango-controls.org/developers/dsc/ds/185/)
  is an existing Python/TCP alternative (Release_1_1, GPL, Unix-like platform).
  Its code was not copied into this package. Windows compatibility and current
  deployment were not verified.
- Historical New Focus logs contain `10.20.30.200:23` in 2017 and
  `DeviceKey = 10.20.30.201` in 2021. These are candidate addresses, not confirmed
  present endpoints. The DS host property intentionally has no default address.
- The local hash-matched SUP copy shows missing New Focus subVIs in LabVIEW's
  Error list. This is a dependency-resolution observation, not a hardware fault.

Only model 8742 is accepted. USB and 8743-CL are not implemented. Newport's
published Python USB samples use .NET wrapper DLLs and the Newport USB driver;
using those samples alone does not remove the Windows dependency chain.

The manufacturer's PicomotorApp 2.1.5 bundle was downloaded and inspected on
2026-10-06. Its `x64/NewportUSBDriver64/USBDriverSetup64.msi` contains a native
AMD64/PE32+ `usbdll.dll` 5.0.7.0. The INF declares the Picomotor family
`USB\VID_104D&PID_4000` for AMD64 and uses WinUSB. The DLL imports WinUSB and
VC90 runtime libraries (`MSVCP90.dll`, `MSVCR90.dll`), replacing the copied XP
Jungo dependency chain. Native API access can use ctypes without the .NET wrapper.
Python x86 is therefore not required by this controller's DLL bitness.

The selected x64 DLL, header, and INF variants are staged under
`Supervision/source/picomotor_vendor_215_20261006/selected_x64`;
`X64_FINDINGS.json` in its parent directory pins the source archive, MSI payloads,
imports, exports, and architecture decision. No installer, driver installation,
vendor DLL loading, or controller I/O was performed. A USB transport is still
unimplemented; driver association, VC90 x64 dependencies, timing, and physical
operation need qualification before deployment. The existing Ethernet DS stays
on the current Python 3.12 x64 runtime.

`TP?` is a software step counter. It cannot prove mirror displacement or encoder
position; no micrometre conversion or physical travel limits are inferred.
Reset/power-cycle may reset the counter. `DH`, `MC`, reset, discovery scans,
EEPROM writes, and automatic coordinate-zeroing are absent from the Tango API.

## Properties

| Property | Default | Meaning |
|---|---|---|
| host | empty | Confirmed controller IP or hostname |
| tcp_port | 23 | Controller TCP port |
| controller_address | 0 | Direct master; 1..31 for an already configured slave |
| expected_identification | empty | Optional exact `*IDN?` result to pin controller identity |
| io_timeout_s | 1.0 | Bounded socket query timeout |
| poll_interval_s | 0.25 | Delay between background status snapshots |
| motion_timeout_s | 30.0 | Deadline for a DS-owned operation |
| motion_enabled | false | Reading and Stop/Abort available; motion requires configuration |
| step_limits | empty | Eight signed integers: min/max for axes 1,2,3,4 |

Step limits are application limits in counter coordinates, not hardware end stops.
Configure them from the commissioned coordinate system before enabling motion.
Assign this DS sole control of the controller; stop the previous VI/application's
motor command path before ownership transfer. No fallback to an old VI is used.

## Prepare and register

From the repository root in the existing `pyconlyse312` environment:

```powershell
# Read-only diagnostic after confirming controller endpoint.
python -m DeviceServers.motion.picomotor.probe --host CONFIRMED_IP

# Print registration plan only: no database writes or controller access.
python -m DeviceServers.motion.picomotor.add_ds_Picomotor8742 --device elyse/motion/picomotor --instance pico1 --controller-host CONFIRMED_IP --server-host CONFIRMED_DS_HOST
```

The device name and instance above are proposed names, not commissioned ones.
Add `--apply` to the reviewed registration command to create a new database entry.
Existing registered/exported devices are refused. Configure `step_limits` and
optional `expected_identification` in Tango. Enable `motion_enabled` only after
controller identity, axis mapping, coordinates, and ownership are established.

For a registered instance:

```powershell
python -m DeviceServers.motion.picomotor.DS_Picomotor8742 pico1
# Astor/Starter wrapper:
C:\dev\pyconlyse\DeviceServers\DS_Picomotor8742.bat pico1
# Read-only Tango client:
python -m DeviceServers.motion.picomotor.DS_Picomotor8742_client elyse/motion/picomotor status
```

The wrapper uses the repository's shared Python-runtime and logging launcher.
Automatic main-app widget dispatch is not registered; the standalone CLI supplies
the Tango control interface without changes to shared UI files.

## Commands and measurements

| API | Argument | Controller operation |
|---|---|---|
| MoveRelative | [axis, signed_steps] | PR; asynchronous completion |
| MoveAbsolute | [axis, counter_target] | PA; asynchronous completion |
| Stop | axis | ST deceleration request |
| Abort | none | AB for all axes on selected controller |
| Reconnect | none | Explicit session replacement and passive resynchronization |
| positions_steps | read | Four fresh TP? step counters |
| motion_done | read | Four fresh MD? flags |
| sample_time | read | UTC Unix timestamp of latest complete snapshot |
| identification, last_error | read | Device identity and latched fault |

Move validates integral axis/steps, signed 32-bit range, application limits, and
idle status of all four axes. It returns after command acceptance; the monitor
confirms idle, checks TE?, and compares the final counter to the requested target.
Stop/Abort remain requests until a subsequent snapshot reports every axis idle.

No write is retried automatically. A timeout/disconnection can leave execution
unknown. Faults stay latched and counter reads raise instead of reporting stale
values as fresh. Explicit Reconnect does not replay moves or reset coordinates.
Known active operations must be stopped before Reconnect; unresolved failed
operations can be resynchronized through reads.

Deadline expiry attempts one Abort and reports FAULT; it does not claim verified
physical stopping. Loss of transport can prevent Abort from reaching hardware.
Stop latency includes the bounded in-progress snapshot/socket operation. Remote
controller acceptance and physical behavior remain commissioning checks.

## Offline validation

```powershell
python -m pytest --deny-network tests/device_servers/motion/test_picomotor_transport.py tests/device_servers/motion/test_picomotor_ds.py
```

The fake-socket and fake-controller tests exercise wire framing, model/address
validation, lost command outcomes, read validity, busy/limit gates, Stop/Abort,
deadlines, and reconnect. They do not certify the physical axes or deployed VI.

2026-10-06 qualification: 77 tests passed (54 transport, 23 DS/registration),
with one existing pytest module-rewrite warning. Ruff passed. Real PyTango
10.0.4 exported the schema and accepted typed commands through a loopback-only
DeviceTestContext with fake hardware and no Tango database. A missing legacy
notifd event supplier notice did not prevent those command/attribute checks.

The machine-readable follow-up is
`Supervision/integration_analysis/orchestrator/picomotor_ds_20261006/PICOMOTOR_DS_FINDINGS.json`.
This follow-up does not establish full legacy autotune parity. The saved SUP
helper maps camera 1 to motors 3/4 and camera 2/default to motors 1/2; physical
axis mapping remains a separate check. Legacy SetZeroPosition is not applied
automatically by this DS; preserving its coordinate convention requires an
explicit migration decision.
