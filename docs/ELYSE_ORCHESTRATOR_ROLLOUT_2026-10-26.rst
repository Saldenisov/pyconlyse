Cold r17 dual-host rollout
=========================

Prepared state and boundary
---------------------------

This procedure installs source into two new versioned directories. It does
not replace or launch a running server, initialize a board, stop a VI, discover
processes, send a device command, or modify Windows registry, PATH or security.
The existing Acquisition directory
``C:\ACQ_Python_Control_20261022_v8`` remains intact.

The current VIs may continue operating during source installation. Initialize
is prohibited while either VI or another local NI client owns the relevant
boards. A cold server must not be launched on an endpoint already occupied by
the old application; the old application requires its own normal, explicitly
authorized shutdown before endpoint handover. The installer performs no such
handover and makes no claim that quiet telemetry proves resource release.

Host layout:

================  ========================  ================================================
Role              Fixed local API           New source directory
================  ========================  ================================================
Acquisition       10.20.30.10:8772           C:\ELYSE_Orchestrator_Acquisition_r17
SuperVision       10.20.30.2:8772            C:\ELYSE_Orchestrator_Supervision_r17
Portable runtime  separately installed      C:\Python34_ELYSE
Everest receiver  10.20.30.202:8767          existing Tango telemetry Device Server
================  ========================  ================================================

The role-specific bind address is validated from the staged configuration.
The installer does not enumerate adapters or verify that the local computer
actually owns that address. Correct RDP/host selection remains an operator
check. No hostname or IP is changed.

Staging contract
----------------

``tools/install_orchestrator_release.pyw`` uses only Python 3.4 standard
library. It can be run by the separately installed portable ``python.exe``;
it never executes the package entrypoints or portable ``pythonw.exe``.
The package directory and site directory must be separate from the installer:

::

    C:\ELYSE_r17_stage\
      install_orchestrator_release.pyw
      source\manifest.json
      source\... manifest-listed source files only ...
      acquisition_site\site_manifest.json
      acquisition_site\config.acquisition.json
      acquisition_site\config.acquisition.control.json
      acquisition_site\... two local key paths from those configurations ...
      supervision_site\site_manifest.json
      supervision_site\config.supervision.control.json
      supervision_site\... two local key basenames from that configuration ...

The common source package has release
``elyse-card-process-orchestrators-20261026-r17``, role ``xp_python34``,
27 standard banks and 25 named operations. Its manifest must explicitly state
``auto_initialize=false``, ``hardware_activated=false``,
``commands_default_enabled=false`` and ``federation_default_enabled=false``.
Both entrypoints and all three package configuration defaults are required.

Each site manifest has exactly this schema. SHA256 strings are lower-case:

::

    {
      "schema_version": 1,
      "role": "acquisition",
      "release": "elyse-card-process-orchestrators-20261026-r17",
      "files": [
        {"path": "config.acquisition.json", "sha256": "<64 hex characters>"},
        {"path": "config.acquisition.control.json", "sha256": "<64 hex characters>"},
        {"path": "read.key", "sha256": "<64 hex characters>"},
        {"path": "command.key", "sha256": "<64 hex characters>"}
      ]
    }

``supervision`` uses its single role configuration and two key files instead.
Acquisition key paths may use safe installation-local subdirectories such as
``runtime/acquisition.key``. SuperVision keys use local basenames. Both key
contents must be distinct and between 32 and 4096 stripped bytes. Keys stay
outside the common source package and version control.

An optional ``START.lnk`` may be included only as another externally pinned
site-manifest file. The installer treats it as opaque bytes and never opens
it. Staging must separately verify its TargetPath, Arguments and WorkingDirectory
before pinning. The intended target is
``C:\Python34_ELYSE\pythonw.exe``; arguments are ``-B`` followed by the exact
role entrypoint and ``--config`` role path. No shortcut is automatically placed
on Desktop or launched. ``START.cmd`` is generated inside the new directory
for an explicit later manual launch, with quoted fixed paths and the same
``-B`` arguments.

Manifest pins must come from the reviewed staging result, not be inferred from
an untrusted copied manifest. Both pins are mandatory command arguments.
The installer verifies every source/site file, rejects unlisted files,
duplicate Windows-case paths, traversal, device names, symbolic links and
reparse points, and checks the portable runtime receipt and ``pythonw.exe``
hash. Full runtime closure verification belongs to the separate portable
runtime installer; this source installer does not import NumPy, NI-DAQmx or
NI-IMAQ as a validation shortcut.

Cold site policy
----------------

Acquisition requires ``native_isolation_mode=per_card``. Its telemetry remains
enabled with explicit ``wire_mode=legacy_27`` and the current Everest receiver.
While the VIs run, this preserves the existing forwarded 27-bank packet,
including fields currently produced by SuperVision. Commissioning flags and
existing cooling protection are supplied by the reviewed site configuration;
installation does not change their meaning or activate an output.

SuperVision requires source camera defaults channel 2, white reference 0.9 V
and black reference 0.1 V, with ``remote_control_enabled=false`` and
``counter_timing_controls_verified=false``. Its telemetry is configured for
``wire=federated_owner`` but ``enabled=false``. Its cold local read API can be
prepared without emitting an incomplete second packet into the old receiver.
No SuperVision pixel array is substituted for the legacy ``C12NI1409`` String.

The Device Server federation switch is deliberately not part of cold rollout.
Enabling it while only Acquisition's new owner packet is available would make
SuperVision fields unavailable. Activation requires the separately matched
Device Server release, both authenticated owner routes, explicit source/role
selection, freshness checks and an agreed native qualification. This is a
staged activation limit, not a claim that both native sources have been tested.

Installation commands
---------------------

Run on the indicated host after the portable runtime has been separately
verified. Replace each placeholder with its reviewed 64-character SHA256 pin.
These commands install files only:

Acquisition 10.20.30.10:

::

    "C:\Python34_ELYSE\python.exe" -B "C:\ELYSE_r17_stage\install_orchestrator_release.pyw" --package "C:\ELYSE_r17_stage\source" --site "C:\ELYSE_r17_stage\acquisition_site" --role acquisition --manifest-sha256 <SOURCE_MANIFEST_SHA256> --site-manifest-sha256 <ACQUISITION_SITE_MANIFEST_SHA256>

SuperVision 10.20.30.2:

::

    "C:\Python34_ELYSE\python.exe" -B "C:\ELYSE_r17_stage\install_orchestrator_release.pyw" --package "C:\ELYSE_r17_stage\source" --site "C:\ELYSE_r17_stage\supervision_site" --role supervision --manifest-sha256 <SOURCE_MANIFEST_SHA256> --site-manifest-sha256 <SUPERVISION_SITE_MANIFEST_SHA256>

The result is ``INSTALLED`` or ``ALREADY_INSTALLED`` with
``hardware_commands_sent=false``. Files are copied into an invocation-owned
sibling temporary directory, verified, then renamed into the previously absent
target. A concurrent target, unrelated existing directory or modified matched
installation is refused. Cleanup is restricted to this invocation's marked
temporary tree; an existing target is never deleted or repaired.

For a reviewed installer shortcut using portable ``pythonw.exe``, add
``--gui`` to the exact installation arguments. This displays a Tk success or
error dialog and writes ``installation_result.acquisition.json`` or
``installation_result.supervision.json`` into the site folder. The separate
bounded result contains no key/configuration bytes and is outside the pinned
payload. A repeat recognizes only this tool's matching role/result kind;
an unrelated result is preserved. ``--gui`` never opens a server window or
initializes a card. Console mode retains JSON stdout and performs no GUI call.

All package default configurations are retained under ``package_defaults/``.
The exact original package manifest becomes ``source_manifest.json``; the
exact site manifest becomes ``site_manifest.json``. Active configurations and
keys come from the separately pinned site. ``orchestrator_installation.json``
records the pins, role, runtime identity and complete installed file hashes.
A repeat succeeds only when the requested pins and installed closure match
exactly. Runtime-created journals, locks or later edits make that exact-repeat
check fail; rerunning the installer is not a repair mechanism.

After authorized normal shutdown of the old Python application, a later cold
launch can use ``START.lnk``, ``START.cmd`` or the quoted portable Python
entrypoint command. Opening the application remains IDLE and creates no NI
tasks. VIs need not be stopped merely to copy files or open an uninitialized
host on free endpoints. Initialize is a separate hardware-affecting action.

Rollback conditions and procedure
---------------------------------

Rollback is an explicit normal handover, not automatic restart after a crash.
If the new application is still cold IDLE with zero owned NI resources and
no initialized helpers, normally stop only that application and confirm its
HTTP/telemetry listeners and application workers have closed. No NI operation
or electrical-state change is needed to roll back this cold application.

If either host has initialized any card or helper, first obtain explicit
confirmation that the affected accelerator equipment is electrically OFF
and its synchronization/camera outputs may be stopped. Use normal Deinitialize
for every owned card/helper. Confirm successful native cleanup, completed
dispatcher/child joins and release of this session's ownership marker before
stopping the application. A failed, timed-out or unknown cleanup retains
ownership; it does not authorize opening the previous server. A disappeared
process, an empty parent PID list or quiet telemetry is not proof that NI
resources or native children have been released. Qualified recovery is a
separate action when normal cleanup cannot establish release.

The previous server remains stopped until the new application's processes and
ports are confirmed released and NI ownership is confirmed released wherever
initialization occurred. Never run the old and new owners together as a
rollback probe. The preserved old source directory is then selected together
with its matching saved Device Server properties/configuration. Restore the
previous source selection and Device Server property backup as one reviewed
rollback; do not combine an old source owner with unmatched new routing.
During the cold phase, federation remains disabled and the previous
Acquisition ``legacy_27`` source/receiver selection is retained. A later
federation activation requires its own saved property backup and corresponding
coordinated source rollback.

Rollback does not delete a dirty marker, discard retained helpers, infer
resource release from a crash or replay an uncertain hardware command. No
automatic crash restart is required or attempted when NI ownership is unknown.
The new versioned directory and installation receipts remain available for
diagnosis; the source installer does not overwrite them with the old release.

Required native follow-up
-------------------------

The two SuperVision boards initialize independently. Healthy synchronization
may already be emitting its source pulses while the camera initializer fails;
there is no global prepare/commit barrier. Full-host readiness is then false.
The local SuperVision runtime can still admit a commissioned counter timing
update if the sync owner itself remains known/current, even in FAULT. The
matched Device Server and web apply the additional top-level
``card_health.all_required_ready`` gate, so their route is disabled when the
camera is unavailable. These are distinct policy layers. No failed operation
or card startup is automatically replayed.

The following checks remain explicit follow-up actions after normal VI release
and operator permission. The cold installer does not perform them:

1. Verify the exact portable CPython 3.4.4 x86 environment and installed
   NI-DAQmx/NI-IMAQ compatibility on each XP computer. Source/RAM tests do not
   qualify those installed native DLLs.
2. Confirm both local NI ownership scopes are released. Initialize each host
   locally; inspect every Acquisition board process and the two SuperVision
   board processes. A successful initializer is software acknowledgment, not
   independent proof of electrical state.
3. Check all eight SuperVision NI6602 source tasks, routes, retriggering,
   finite one-sample settings and starts. Compare saved timing pairs against
   ``0.35/0.35, 2176/100, 2008.30/10, 2175/10, 2175/100, 500/500,
   0.30/10, 2175/100`` microseconds. Source initialization uses InitialDelay=0;
   later timing writes change InitialDelay and LowTicks together. Agreement
   with UI numbers does not verify physical PFI11 clock frequency or phase.
4. Qualify NI1409 ``img0`` open/setup/grab/stop/close, channel/reference settings,
   U8 geometry, row stride, frame age and bounded transport. Basler ``cam0`` and
   ``cam1`` are separate IMAQdx devices and are not opened by this adapter.
5. Confirm other board input streams stay current during a deliberate
   synchronization timing update. Check changed session/generation, stale
   owner, partial write and uncertain native return suppress command admission
   and never replay a command automatically. A failed child cannot be replaced
   solely because its PID disappeared; clean closure/join and ownership
   qualification remain necessary.
6. Activate the matched federated Device Server only with the selected owner
   sources available. Verify independent source ages and bank provenance,
   stale SuperVision contribution behavior, authenticated command routing,
   and video identity ``owner_session + capture_session_id + sequence``.
   Repeated heartbeat of an old image must not reset frame age.

NI1409 output is raw frame capture before the legacy Vision interlace, BCG,
centroid/profile and display pipeline. Those nine legacy processing buffers
are excluded from this implementation. This rollout does not claim processed
camera equivalence, independent pulse calibration or completed native testing.

Installer verification
-----------------------

Twelve tests use random temporary directories and synthetic source/runtime
bytes which are never executed. Actual CPython 3.4 x86 and Python 3.12 with
external networking denied pass both role installations, exact idempotence,
preservation of the old directory, source/site pin and payload mismatch,
copy failure, final-rename race, modified-target refusal, Windows-path/case
checks, key separation, explicit publisher modes without automatic startup and runtime-binary
hash mismatch. No live target, XP process, NI resource or network endpoint is
accessed by these tests.
