ELYSE: Python 3.4 bootstrap regression and LabVIEW telemetry restoration
======================================================================

Incident boundary
-----------------

The Python Initialize attempt timed out before the call trace contained any
Task construction. The final persisted boundary was ``ENTER import nidaqmx``.
An earlier stack in Enum construction was only a point-in-time observation,
not evidence of a blocked NI driver call. The retained-resource value 1 was an
UNKNOWN ownership sentinel, not a measured count of one NI task.

All eleven cards had separately configured and released successfully in the
operator-approved per-card probe. That probe did not start counters, read
inputs or write startup AO/DO. It did not validate the combined startup path.

Development-host discrimination, actual CPython 3.4.4 x86:

* Plain ``import nidaqmx`` returned in 1.500 s; unbuffered mode also returned
  in 1.406 s. Neither test constructed Task objects.
* An import-only child with a blocked background stdin reader timed out at
  6 s; the otherwise identical child without that reader returned in 1.454 s.
* Loading NumPy before starting the stdin reader restored completion at
  1.422 s. Replacing the reader with a direct Windows ReadFile call did not
  resolve the hang. The evidence identifies an import/read-order interaction;
  it does not establish a particular CRT lock or GIL mechanism.
* The full old isolated-worker path also timed out in an import-only fixture.
  Its stack was inside NumPy's native ``multiarray`` loader, before any NI Task.

The import-only reproduction is isolated from live XP and contains no card
factory or NI operations. Its timeout cleanup can terminate only that private
test child. Production owner timeouts still retain ownership.

Implemented correction, not deployed to XP
------------------------------------------

The child consumes the exact, explicitly confirmed first Initialize request
on its main thread. Egress and stack metadata remain separate, but the blocking
stdin pump starts only after NumPy/nidaqmx dependency preparation. The real
CardBackend bootstrap imports libraries only: it never creates, configures,
starts, reads, writes or closes a Task. Injected offline factories remain cold.

A private ``initialize_ready`` / ``activate_initialize`` handshake separates
dependency preparation from native initialization. Cancellation queued during
imports is consumed on the child main thread before native activation. EOF,
malformed activation or a missing parent acceptance cannot start cards.
This is not a second public command or remote Initialize endpoint.

The source-derived card ordering, startup images, counter starts and other VI
procedures are unchanged. The three GUI buttons and 27-bank contract remain.
Stack diagnostics read bounded frame metadata only, without linecache/source
file reads. ENTER/RETURNED startup traces remain diagnostics, not electrical
acknowledgement or continuous inspection of native resources.

An import exception with a returned zero-resource backend can report failure,
accept explicit close and certify child exit. A test verifies that the runtime
then releases its own marker and can shut down without a reboot. A missing
response, native timeout, partial cleanup or abnormal exit does not acquire
that certificate. No automatic NI restart, force-kill or VI fallback was added.

Live telemetry restoration
--------------------------

The operator explicitly authorized termination of the hung Python processes
and restoration of the previous receive-only bridge, while keeping LabVIEW
running. XP Task Manager confirmed and terminated child PID2400 first, then
the window-associated parent PID2912. LabVIEW was not stopped or edited; no
Initialize, NI cleanup, card probe or equipment command was issued during
this restoration. Termination was not recorded as successful NI cleanup and
the installation ownership marker was preserved.

The existing bridge was opened and started from::

    C:\ACQ_SharedState_Python34_20261014\shared_state_receiver.pyw

It accepted all 27 banks locally, but the Everest unified-source filter refused
its legacy packets because they lack the unified publisher's source_site tag.
The telemetry-only Tango receiver was reinitialized at
2026-10-23T10:42:46.402522+00:00 with explicit properties::

    producer_kind_filter = copied_acquisition
    commands_enabled = false

Receiver PID27072 and PostgreSQL archive configuration were retained; the
receiver session/counters restarted. No hardware device server was restarted.
The prior filter was ``unified_acquisition``; xp_control_port remains 8772.

Read-only acceptance from 10:43:07 to 10:43:17 UTC (12:43 Europe/Paris) found:

* Tango receiver counts 51 -> 65 -> 77 in one new receiver session.
* All 27 banks had values and no bank errors. Every bank advanced its sequence
  in both consecutive five-second comparisons. Analog values also changed;
  stable digital states were not mistaken for a stalled stream.
* Web quality FRESH at all three observations, 27 populated banks, no missing,
  stale or error banks. Maximum Tango bank age: 0.375 / 0.328 / 0.484 s.
* PostgreSQL remained RUNNING, committed count 50 -> 64 -> 76 for this receiver
  session, last_error empty. Existing archive contents were not replaced.

A later finite check at 10:58:18--10:58:51 UTC passed 16/16 observations on
both Tango and the web. Every bank advanced at each interval; receiver count
2405 -> 2475. Maximum age was 0.673 s through Tango and 0.703 s through the
web, with no missing/error/stale banks or read errors. PostgreSQL remained
RUNNING with empty last_error.

The detailed local restoration record is outside the repository::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-23\labview_bridge_restore.json

Verification and rollout limits
--------------------------------

Actual CPython 3.4.4 x86, dependency-free suite::

    C:\dev\pyconlyse\tools\xp_python34_extracted\python.exe -m unittest \
        tests.unit.test_acq_dependency_bootstrap \
        tests.unit.test_acq_isolated_backend tests.unit.test_acq_card_probe \
        tests.unit.test_acq_application_view tests.unit.test_acq_control_release \
        tests.unit.test_acq_modular_server tests.unit.test_acq_nonblocking_integration

Result: 87 tests, one optional import integration skipped, no failures,
24.596 s. The optional real dependency test passed separately in 3.561 s in
the development Python 3.4 environment with ACQ_IMPORT_ONLY_INTEGRATION=1.
It used the full worker, created no Tasks and confirmed zero-resource close
and child exit. A further import-only run reported bootstrap 1.563 s.

The modern receiver/telemetry/web regression passed 129 tests with one optional
import integration skipped and four warnings on Python 3.12.14, in 36.06 s.

The corrected source has not been installed or initialized on XP. The restored
old bridge remains the active live path. Returning to the unified source must
be a separate supervised handover, including source-filter selection and
all-bank acceptance, not an automatic response to a native fault. These tests
do not qualify electrical startup, calibration, cooling or HT protection.

Prepared unified v8-r4 handover
------------------------------

The requested target remains ONE dual-mode control-capable server, not a new
telemetry-only application. Before local Initialize, that server forwards the
VI's 27 banks. After separately confirmed ownership acquisition it publishes
its own card-derived banks and admits only commissioned named commands.
Silence from VI never triggers automatic Initialize.

A fresh process blocked by a prior ownership marker can now forward VI data
without clearing that marker or changing RECOVERY_REQUIRED. The exception is
a boot-time RAM fact, allowed only with no backend, pending operation, shutdown
or uncertain current cleanup. Accepting Initialize revokes it permanently.
Current-session native faults and retained resources still cannot fall back to
VI. The marker and command-admission gates remain effective.

Prepared deployment (installed after the approval recorded below)::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-23\unified_v8_r4

    release: acq-v8-unified-bootstrap-r4-20261023
    build_id: 104dde2a018601d45130df4c410d7f22cb037cf8200b12ef053a6319e661d7e1
    manifest SHA256: 22b1bb03cf2d55f3557d7efeced4c42006e5ee07adee28f5b1fa4cb59bf098aa

The delta replaces exactly five modules: hardware_tasks, acquisition_backend,
isolated_worker, isolated_backend and acquisition_control_runtime, plus the
manifest. It is based on the installed r3 source, not on all dirty worktree
files. Pending journal/start-permit edits, recovery utilities, configuration,
keys, alarm journal and ownership history are excluded. Source hashes must
match before replacement; originals are backed up and the ownership image is
checked unchanged. The updater neither starts software nor calls NI.

Current acceptance: 97 unique tests passed on CPython 3.4.4 x86, including the
separately enabled import-only integration; 69 receiver/dual-mode/web tests
passed on Python 3.12.14 (four warnings). The packaged Python 3.4 cold acceptance
passed signed loopback delivery, all 27 banks, Initialize exclusion during VI
traffic, independent command admission, non-waiting telemetry projection and
all manifest hashes. Native-library loading was forbidden during that check.

Completed supervised handover
----------------------------

The operator explicitly approved installing and launching unified v8-r4 with
LabVIEW still running, no Initialize and the prior ownership marker retained.
The installer backed up the five original modules and manifest to::

    C:\ACQ_Python_Control_20261022_v8\runtime\source_before_unified_bootstrap_20261023T121758Z

The old Python bridge was stopped through its own stop button, observed
Stopped and closed. The existing acquisition_control_server.pyw then opened
the unified server. An authenticated read confirmed the expected build_id,
session 1d12a45c43a04f4d8ba1fe294ba2ad16, LABVIEW_BRIDGE, commands disabled and
native worker NOT_SPAWNED. Runtime state is deliberately RECOVERY_REQUIRED,
not an invented NI-ready IDLE: the prior marker remains and no recovery or
native initialization was attempted. The three buttons remain present.

At 2026-10-23T12:19:32.849629+00:00, the existing telemetry-only Tango receiver
was reinitialized with producer_kind_filter=unified_acquisition and commands
still false. PID27072 and the PostgreSQL archive were retained; receiver
session and counters restarted. No hardware Device Server was reinitialized.

Acceptance from 12:21:40.397352 to 12:22:04.955204 UTC (14:21--14:22 Paris)
passed 12/12 observations on both Tango and web. All 27 banks were populated,
error-free, tagged xp_unified_labview_bridge_27_banks and advanced sequence
at every interval. Receiver count advanced 386 -> 453 in one session; web
remained FRESH. Maximum bank ages were 1.094 s through Tango and 0.797 s
through the web. C1NI6071E, C2NI6071E and VAM-A also changed values.

PostgreSQL remained RUNNING with empty last_error; committed_this_process
advanced 567 -> 577 at 12:22:48--12:22:51 UTC, pending=1 at both observations.
The detailed local deployment record is outside the repository::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-23\unified_v8_r4_deployment.json

This finite check does not prove lossless delivery or uninterrupted history
during handover. Native bootstrap remains offline-qualified only. No VI/card
operation, Initialize, General, Chroma or other equipment command was sent.
