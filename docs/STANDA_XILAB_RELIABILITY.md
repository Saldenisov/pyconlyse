# Standa DS reliability and XILab transport model

Date: 2026-09-02

## Outcome

The Standa Tango device server now follows the transport behavior documented
for XILab/libximc more closely. The update does not move an axis at startup and
does not reopen automatically after a connection loss during motion.

The important changes are:

- use the maintained official `libximc==3.0.4` package by default, with the old
  bundled 2.10.5 library retained as an explicit rollback fallback;
- lock access per controller serial number instead of placing all controllers
  behind one command lock;
- perform one host-wide USB discovery and share its result with all Standa Tango
  processes for 30 seconds;
- wait up to 15 seconds for that single discovery instead of letting every
  server fail after 0.1 seconds and immediately try again;
- enumerate local USB/COM devices only by default (no irrelevant network scan);
- read controller serial numbers directly from the enumeration result and free
  the result after every scan;
- verify the configured serial number every time a cached URI is opened;
- on a generic transmission error, call `reset_locks()` and retry an idempotent
  read once; motion and write commands are never retried automatically;
- use the vendor-recommended 10 ms refresh interval while waiting for movement
  to stop instead of 5 ms;
- safely reopen a previously initialized, stationary controller after a loss,
  validating status and position without issuing move or stop;
- expose the loaded backend/version and persistent transport error counters as
  Tango attributes.

## Why the previous DS was unstable

Live Astor logs on `elysium2` showed repeated messages of this form:

```text
STANDA discovery deferred: Standa USB transport is busy for 0.1s
Hardware power is ON but safe probe failed: hardware did not respond after power was restored
```

There are 25 independent `DS_Standa_Motor` processes on that host. Each process
was trying to enumerate the complete bus, was allowed only 0.1 seconds to obtain
one global lock, and then repeated recovery. Some devices had hundreds of
recovery attempts. This creates a thundering-herd problem: healthy controllers
are subjected to unnecessary probes while most servers time out waiting.

The old discovery code also opened every enumerated controller to obtain its
serial number and did not free the enumeration object. Network enumeration of
`10.20.30.204` was enabled even though all currently discovered controllers use
`xi-com:` URIs. These are software defects independent of the mechanical axes.

XILab itself uses libximc. Standa documents that libximc is thread-safe but that
one physical controller is opened exclusively by one program. XILab probes the
bus to build a list, then opens selected/free controllers; it does not require
all different controllers to share one command lock.

## Safety behavior

- Server startup remains passive: discovery may set `STANDBY`, but the motor
  handle is not kept open and no movement command is issued.
- Explicit initialization opens the cached URI, verifies the physical serial,
  then performs the existing stop/read initialization sequence.
- A loss while the axis is not moving may reopen the same verified controller.
  Reopening sends no move or stop command.
- A loss detected while state is `MOVING` sets `FAULT`, disables automatic
  recovery, and requires operator inspection.
- Only read-only calls (`get_status`, `get_position`) receive one automatic
  retry. Move, stop, zero, and other mutations are not replayed.

## New Tango properties

| Property | Default | Purpose |
| --- | ---: | --- |
| `usb_discovery_lock_timeout_s` | 15 | Time allowed to wait for the one host probe |
| `usb_discovery_cache_ttl_s` | 30 | Lifetime of the shared serial-to-URI result |
| `usb_read_retry_count` | 1 | Idempotent read retries after `reset_locks()` |
| `usb_read_retry_delay_s` | 0.05 | Delay before the retry |
| `resume_connection_after_loss` | 1 | Reopen a previously initialized stationary axis |
| `enumerate_network_devices` | 0 | Keep USB discovery local unless explicitly needed |
| `wait_time` | 10 | Movement status refresh interval in milliseconds |

Apply these to existing Tango devices with:

```powershell
python DeviceServers/motion/standa/add_ds_STANDA.py --reliability-properties-only
```

## New diagnostic attributes

- `libximc_backend`: expected value after migration is `official-pypi`;
- `libximc_runtime_version`: expected value is `3.0.4`;
- `libximc_backend_error`: reason the official backend could not load, if the
  server fell back to the legacy bundled library;
- `transport_error_count`: total failed transport results since server start;
- `transport_retry_success_count`: reads recovered by the safe retry;
- `last_transport_error` and `last_transport_error_at_utc`.

These counters are intentionally not cleared after five seconds like the normal
transient status message, so they can be archived and compared between axes.

## Staged deployment on Elysium2

Do not restart every Standa server simultaneously for the first deployment.

1. Close XILab on Elysium2. A controller opened in XILab is unavailable to the
   Tango process because libximc uses exclusive access.
2. Update the code checkout used by Astor.
3. In the Python environment used by the Standa servers, install the pinned
   runtime:

   ```powershell
   C:\Users\elyse\.conda\envs\pyconlyse39\python.exe -m pip install libximc==3.0.4
   ```

4. Verify the loaded DLL without touching hardware:

   ```powershell
   C:\Users\elyse\.conda\envs\pyconlyse39\python.exe -c "from DeviceServers.motion.standa.ximc import XIMC_BACKEND,runtime_version; print(XIMC_BACKEND, runtime_version())"
   ```

   Expected output: `official-pypi 3.0.4`.
5. Register the reliability properties using the command above.
6. Restart one non-critical Standa server in Astor. It should start passively.
7. Confirm the diagnostic attributes, explicitly initialize the axis, perform a
   small known-safe move, and observe it for at least 30 minutes.
8. If stable, restart the remaining servers in small groups rather than all at
   once. The shared discovery cache will prevent repeated full-bus scans.

For a temporary rollback, set `PYCONLYSE_LIBXIMC_BACKEND=bundled` in the Standa
server environment and restart that server. This selects the legacy library;
it should only be used to isolate a compatibility issue.

## Vendor references

- [libximc documentation](https://libximc.xisupport.com/doc-en/)
- [libximc API reference](https://libximc.xisupport.com/doc-en/ximc_8h.html)
- [XILab start and device detection](https://dev.doc.xisupport.com/en/8smc5-usb/8SMCn-USB/XILab_application_Users_guide/Main_windows_of_the_XILab_application/XILab_Start_window.html)
- [Official libximc source](https://github.com/Standa-Optomechanics/libximc)
- [libximc logging (`XILOG`)](https://libximc.xisupport.com/doc-en/howtouse_sec.html)

For a difficult remaining case, launch only that one DS with a unique `XILOG`
file path. libximc will then record port opens/closes and transmitted/received
data. Never point multiple DS processes to the same log file.
