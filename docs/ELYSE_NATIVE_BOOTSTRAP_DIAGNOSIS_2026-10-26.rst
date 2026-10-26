Native initialization trace and r10 candidate, 26 October 2026
===========================================================

Observed XP boundary
--------------------

The operator exported the read-only initialization trace for retained child
PID 2808. The file is
``C:\ACQ_Python_Control_20261022_v8\runtime\initialize_2808_885e1150.jsonl``.
It contains 15 entries (1634 bytes). Times below are UTC; Paris is UTC+01.

* NumPy import returned at 08:44:10.765625.
* nidaqmx import returned at 08:44:12.468750.
* Parent activation returned at 08:44:12.515625.
* ``C10_NI6602_CO_0.Task`` entered at 08:44:12.578125 without a return entry.

This identifies the first Task constructor as the unresolved Python boundary.
It does not identify which native subcall hung. No later channel setup,
counter start or startup AO/DO write appears in this trace. The parent
resource count of one is an uncertainty sentinel, not a counted NI task.
The parent remains FAULT/OWNERSHIP_UNCERTAIN; no retry, process termination,
marker reset, reboot or General command was performed during this diagnosis.

Mechanism and discriminating change
----------------------------------

The installed legacy nidaqmx Task constructor first resolves ``task_handle``
and ``windll.DAQmxCreateTask``. Importing nidaqmx alone does not perform these
lazy operations. ``task_handle`` can query NI driver-version metadata, and
``windll`` loads nicaiu. The previous worker started its blocking stdin
reader between module imports and this first native initialization.
The successful card-by-card tool did not have that same pipe-reader order.

The r10 candidate resolves the NI library, TaskHandle metadata and CreateTask
symbol before starting the stdin reader. It does not invoke CreateTask in
this preparation phase. Each boundary is traced. Metadata preparation is
inside the explicitly requested Initialize lifecycle, never cold GUI startup.
Parent activation still precedes Task creation, channel setup and writes.

This removes a plausible lazy-loader/pipe interaction. It is not proof that
this interaction caused the XP stall. Only a new trace on XP can establish
whether preparation and Task creation now return. The retained old child must
first be released through the operator-controlled recovery/reboot workflow.

Command transport
-----------------

The live XP configuration has ``remote_control_enabled=false``. The Everest
device has ``commands_enabled=false`` and no command key configured. Thus
telemetry ACKs cannot establish command readiness. The current fault also
contains no valid native measurements.

``configure_acq_command_transport.py`` prepares explicit cold XP transport
activation with a command key distinct from the telemetry key. It preserves
the complete hardware configuration, commissioning flags, ownership evidence,
cooling policy and journal. Source and configuration changes have backups;
failed configuration writes restore the preceding control file and manifest.
The supplied installer never initializes cards or launches the server.

The DS still requires a matching command key and enabled transport. Trusted
caller restrictions remain a separate deployment requirement. Access-control
registration alone is insufficient: the read-only service lookup returned no
``AccessControl/*`` service. No commissioning flag was changed to bypass an
unqualified command gate. The r10 transport candidate is staged, not live.

Deployment state
----------------

XP currently runs the r9 source build
``703e150b66e809d8c9e644cb1fb3a10c32832181f66769ce9f11b9cd127262e0``.
The cold r10 package contains 68 source/data files and build
``d0a3a64d67c173ed6aca727666784f4ac2c0678602bb096bf9d927b9b3a4436b``.
The existing one-app, three-button, 27-bank and 24-operation contracts remain.
No existing journal or ownership marker is deleted by the source installer.

Earlier this session, Everest received the matching r9 command validator and
counter-timing dependency; only its telemetry Device Server was restarted.
The original modules and launch diagnostics are backed up under
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\command_contract_r9_20261026T084628Z``.
The device now reports the actual XP fault rather than a capability mismatch.
Its command properties and archive configuration remain unchanged.

Validation
----------

The actual CPython 3.4.4 x86 environment passed 45 bootstrap/isolation,
cold updater and command-transport tests in 14.982 seconds. The opt-in integration tests import
real NumPy/nidaqmx and prepare real NI library/version metadata in a dedicated
development-host child. They create no Task and address no card. They do not
prove behavior of the XP driver installation. Python 3.12 network-denied tests
passed 57 tests with two opt-in skips before the final two updater regressions;
the subsequent updater/package/control run passed all 22 tests. Actual Python
3.4 parsed all 62 Python package sources and three installation utilities.

The operator-facing rollout is staged beside the previously used read-trace
shortcut as ``INSTALL_R10.lnk`` and ``START_SERVER.lnk``. The installer uses
direct ``C:\Python34\pythonw.exe`` invocation rather than the pyw association
launcher. It does not terminate the retained production worker. Installation,
new-session telemetry, remote admission and native initialization remain
unverified until the operator performs the cold rollout.
