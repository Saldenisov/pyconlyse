ELYSE unified XP server: local handover and journal acknowledgment
================================================================

Scope and current deployment boundary
-------------------------------------

The requested application is one dual-mode control-capable XP server. Before
explicit local Initialize it forwards the VI's 27 banks; after initialization
it publishes its own input/command-memory banks and admits only commissioned
named commands. VI silence never starts cards. The same application owns both
sources; no standalone telemetry-only launcher is included in the release.

Development used synthetic process lists, temporary SQLite files, mocked GUI
collaborators and loopback receivers. The subsequent separately approved live
rollout is recorded below. No VI, NI card or instrument operation was performed.

Prepared package::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-23\unified_v8_r5
    release: acq-unified-handover-journal-20261023-v8-r5
    build_id: 7ed69ea72b8dc263a295f078112c714e37c0494cbec790c8e8a9799cdd1d1f82
    manifest SHA256: d776e6896dbe7d88920ddb48f44fc5ce0470750585bc60d9d72d90891c29e98b

Why the old state persisted
--------------------------

The existing three-button window disabled Initialize for RECOVERY_REQUIRED,
but supplied no production recovery checker or usable recovery action. A prior
marker therefore blocked NI ownership indefinitely. That marker is separate
from the alarm journal and cannot be cleared by acknowledging a journal notice.

The journal deliberately retained a previous writer's uncertainty. Its durable
reconciliation API had no route from this window. A normally functioning new
writer could therefore display the old notice indefinitely. Historical gaps
and current write failures must remain distinct; elapsed time proves neither
missing events nor successful task cleanup.

A separate startup defect could also create misleading writer state: journal
construction preceded fixed-port binding. A duplicate GUI or an old bridge on
8766 could touch SQLite before its own startup failed. This is a verified code
path, not proof that it caused the original live incident.

Explicit local handover through the existing Initialize button
--------------------------------------------------------------

Initialize becomes locally available for a cold prior-owner recovery state,
but remains disabled while recent valid VI snapshots are seen. The modal
requires explicit confirmation that Acquisition VI stopped normally, external
NI tasks were released and the installation is physically OFF. It also states
the fixed counter/AO/DO initialization effects that follow accepted handover.

The verifier reads only an XP x86 Toolhelp PROCESS snapshot. It rejects a live
or reused prior PID, any other Python/native worker, known MAX/DAQ clients,
malformed/partial/stale inventory and absent/expired/wrong-thread consent.
LabVIEW.exe may remain open only because the local operator explicitly attests
that its VI stopped and its tasks were released. This is not independent NI
task-handle inspection, electrical OFF measurement or universal exclusion of
unknown DAQ applications. Proof metadata retains these limits explicitly.

The exact prior marker bytes and qualification are persisted before removal.
That audit is labelled REVIEW_PREPARED, not completed cleanup. A second process
check and unchanged-marker check precede removal; Initialize repeats the VI
admission fence afterward. Resumed VI traffic cannot be followed by our backend
construction. Current native ownership, pending shutdown and uncertain cleanup
cannot use this recovery path. No remote recovery/Initialize operation exists.

Historical journal notice
-------------------------

The red history notice opens one local review confirmation; a cold window may
offer this review once after the writer is ready. It adds no fourth button.
The acknowledgment is revision-bound, queued on the existing journal worker
and cleared only after an atomic durable audit commit. It does not reconstruct
lost events, delete history, clear incidents, alter countdowns or hide current
disk failures. Durable acknowledgment metadata survives clean restart; a new
unclean writer session generates a new notice.

Start permits now distinguish current writer health/readiness from historical
uncertainty. Active circulation incidents and actual storage failures retain
their existing start gates. This does not change VI procedures, trip deadlines,
stop sequencing or hardware commissioning flags.

Single application startup
-------------------------

The config-scoped OS instance guard is acquired before journal construction.
Ports 8772 and 8766 are owned using a RAM-only cooling policy before its owned
SQLite writer is attached. Failed duplicate/old-bridge startup does not open
another writer. The guard is released only after NI, publisher/network, journal
and application-view shutdown are confirmed; failed joins retain it.

The canonical Startup launcher starts acquisition_control_server.pyw and exits.
It no longer leaves a resident Python supervisor that would be indistinguishable
from a retained native worker to the local handover check. This provides login
autostart only, NOT crash restart. A crash requires manual launch or login; a
different OS-level restart mechanism is outside this change and must never
automatically initialize cards. Compatibility aliases invoke the same unified
implementation and do not constitute an additional telemetry server.

Rollout installer
-----------------

The payload uses an explicit 67-file closure, excluding runtime history and
unreviewed repair/standalone telemetry launchers. The installer changes exactly
nine modules plus manifest against verified installed hashes, backs up known
originals and preserves config, keys, SQLite history and ownership bytes. It
does not launch software, recover ownership or call NI.

The exact old C:\ACQ_SharedState_Python34_20261014\shared_state_receiver.pyw is
retired to a recoverable adjacent backup only if its known SHA256 matches.
The folder and read key remain. A differing file is retained with a warning.
Only an existing marked ELYSE_Acquisition_Server.pyw Startup file is migrated,
with an exact-byte backup; absent or unmarked entries are not created/overwritten.
Other Windows shortcuts/tasks are outside this installer and are not claimed
to have been exhaustively audited.

Verification
------------

Actual CPython 3.4.4 x86 core suite: 165 tests, 164 passed and one optional
development-only NI dependency import test skipped, in 19.491 s. Installer:
11 additional tests passed. Combined scope: 175 passed, one optional skip.
Modern Python 3.12 receiver/web/dual-mode/recovery/journal suite: 138 passed,
12 warnings, in 9.01 s.

Packaged Python 3.4 cold acceptance passed all source hashes, 27-bank signed
loopback delivery, VI exclusion before Initialize, independent command admission
and non-waiting telemetry projection. Native-library loading was prohibited.
These checks do not certify live NI initialization, calibration, cooling or HT
safety. No hardware or live process inventory was used in the tests.

Approved live rollout and acceptance
-----------------------------------

The operator explicitly approved installing r5, acknowledging the old journal
notice durably and retiring the old bridge entrypoint with a backup, while
leaving VI running and forbidding recovery/Initialize. Authenticated preflight
confirmed r4 had zero local resources and native worker NOT_SPAWNED. It was
closed normally before the hash-checked source update.

The installer reported verified source backup, exact-hash legacy entrypoint
retirement and migration of the existing marked current-user Startup file,
with exact-byte backups. Configuration, read key and prior ownership marker
were preserved. Arbitrary Windows shortcuts/tasks were not exhaustively audited.

The canonical application was opened without Initialize. The old history
notice was explicitly acknowledged through its new local review modal. At
2026-10-23T13:01:17.606875+00:00 (15:01 Paris), SQLite committed acknowledgment
c117d21adf3f4d0f8091bbb4892c8c4c. An authenticated runtime read confirmed:

* Expected build 7ed69ea72b8dc263a295f078112c714e37c0494cbec790c8e8a9799cdd1d1f82;
  session 4d7b3dd31aeb48aa8f160bf4e1605af2.
* LABVIEW_BRIDGE, zero local NI resources, native worker NOT_SPAWNED and
  commands disabled. No local handover, process verifier or Initialize ran.
* journal_history_acknowledged=true, empty warning/current errors,
  journal_durable=true, pending=0, committed=1. Missing events were not reconstructed.
* RECOVERY_REQUIRED remains intentionally retained; local_handover_available
  is true, but recent VI traffic still excludes Initialize.

Acceptance from 13:01:52.480474 to 13:02:16.073196 UTC (15:01--15:02 Paris)
passed 12/12 observations. All 27 populated banks advanced sequence at every
interval through both Tango and web, with no error/missing/stale bank. Web
remained FRESH. Receiver count advanced 7743 -> 7810 in the existing receiver
session; no Tango receiver reinitialization was needed. Maximum bank ages were
0.624 s through Tango and 0.640 s through web. C1NI6071E, C2NI6071E and VAM-A
also changed values. PostgreSQL remained RUNNING with empty last_error;
committed count advanced 7743 -> 7808, pending 0 -> 2.

The local detailed record is outside the repository::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-23\unified_v8_r5_deployment.json

This does not establish a lossless or uninterrupted archive across software
replacement. Live NI startup and the local XP verifier remain unexecuted.
