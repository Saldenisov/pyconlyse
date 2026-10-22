ELYSE acquisition v8: isolated execution and bounded application paths
===================================================================

Scope and boundary
------------------

This release refactors the Python 3.4 XP application, not the LabVIEW sources,
NI configuration, commissioning evidence, Chroma port assignment or physical
interlocks. Initialize, Deinitialize and Stop server remain the only three
local buttons. The standard telemetry schema still has 27 banks: the VI bridge
copies all 27; native Python populates the same 12 confirmed banks and leaves
the other 15 explicitly unavailable. Output images are last successful software
commands, not independent physical readback.

The application remains cold on startup. Remote control and every commissioning
flag default to false. No card operation, device command, LabVIEW restart or
experiment restart was performed by the offline work described below.

Implementation stages
---------------------

* ``3552c9bf``: same-owner cooperative checkpoints during explicitly noncritical
  VI-derived waits. Tests preserve source effect order and nominal aggregate
  dwell. Asserted/uncertain pulse spans, critical counter transitions and native
  calls remain indivisible. Observer failures cannot skip pulse restoration or
  best-effort stop. Reentrant procedure/cleanup calls from observers are refused.
* ``0b1ff258``: one cold child NI owner, bounded private JSON pipes, RAM-cached
  parent attributes, asynchronous local lifecycle and read-only application
  snapshots. SQLite has one asynchronous, non-daemon writer and explicit commit
  acknowledgements. Persisted incident recovery precedes new state persistence.
  An unclean journal history is separately latched; only a qualified local,
  revision-fenced, audited reconciliation can clear it after commit ACK.
* ``d03c4daa``: four-slot VI ingress, tracked handler completion on Python 3.4,
  a reserved General-stop admission slot, and integration acceptance. Remote
  leases bind session, state revision, lifecycle epoch, exact cache generation
  and its absolute freshness deadline. Delayed HTTP handling cannot extend
  that deadline. A queued local lifecycle request revokes old remote leases.

Ownership and failure semantics
-------------------------------

The parent owns GUI, HTTP, VI ingress and signed telemetry forwarding. A single
child process owns all NI calls. Only an explicitly confirmed Initialize may
create that child. A pythonw parent selects hidden sibling python.exe for its
private framed pipes; no second public telemetry service is introduced.

Timeout, crash or transport loss is an unknown outcome, not cancellation or
physical OFF. Ownership remains latched; no native process is automatically
killed, replaced or restarted. Parent transport disappearance during an active
call leaves the surviving native owner in quarantine. The installation-local
ownership marker is released only after confirmed cleanup and child exit. Its
existing scope remains configuration-path-local, not machine-wide exclusion.

The application view reads a detached RAM snapshot, never calls driver/policy
or disk paths on a GUI/HTTP reader, and exposes age and metadata quality.
Lifecycle validation and resource joins run off Tk. Shutdown is not completed
until the NI owner, cooling watchdog, VI handlers, command admission, relay,
application workers and journal writer have actually finished. Startup failure
also drains the journal; a retained worker keeps a visible failure window.

Queues are bounded. Telemetry retains one immutable in-flight packet and one
replaceable latest pending packet. Journal overflow is an explicit error, not
silent durable logging. Command timeout never triggers automatic retry.

Limits deliberately retained
----------------------------

Python, Windows XP and vendor drivers do not provide hard real-time guarantees.
Separating processes prevents a native stall from holding the GUI/network
interpreter, but cannot force an electrical stop through a stuck native call.
The production child uses ``safe_sample_budget_seconds=None``: source-wait
checkpoints report progress only. Additional NI sampling inside a source wait
requires a separately qualified aggregate read budget. Progress/heartbeats do
not refresh measurement age or establish physical acknowledgement.

Telemetry remains latest-only and RAM-buffered. Sequential bank capture is not
atomic. HMAC authenticates unencrypted LAN TCP/HTTP; this release adds no TLS.
The existing HDF5 recorder is external to XP and is not restarted by packaging.
Its active file must never be opened in parallel, including read-only/SWMR on
Windows. A server replacement can create a source gap; no continuity is claimed.

Offline verification
--------------------

Actual CPython 3.4.4, 32-bit::

    C:\dev\pyconlyse\tools\xp_python34_extracted\python.exe -m unittest \
        tests.unit.test_acq_control_release tests.unit.test_acq_modular_server \
        tests.unit.test_acq_application_view tests.unit.test_acq_async_alarm_journal \
        tests.unit.test_acq_cooperative_execution tests.unit.test_acq_isolated_backend \
        tests.unit.test_acq_priority_admission tests.unit.test_acq_nonblocking_integration -q

Result: 111 tests passed in 11.511 seconds. Tests use injected RAM backends,
temporary SQLite databases and loopback/private subprocess pipes only.

The combined modern unit/protocol/receiver/recorder/web regression passed
222 tests in 24.36 seconds on CPython 3.12.14, with four warnings. It includes
bank/source-switching, HTTP authorization, HDF5 recorder fixtures and the
existing Tango/web pipeline fixtures; it does not operate live hardware.

Read-only independent review identified and closed stale-lease, callback
reentrancy, child-disconnect, startup cleanup and shutdown-join defects. New
source modules participate in the installed build fingerprint; mutation tests
cover all six new execution/application modules.

Artifacts and rollout boundary
------------------------------

Clean source release: ``d03c4daa`` on ``codex/acq-unified-telemetry-v6``.
All three implementation commits were pushed to origin.

XP artifact (66 source/configuration files plus manifest)::

    C:\dev\pyconlyse\.tmp\acq-isolated-xp-20261022-v8.zip
    SHA256 4FE1C3F3003F97504C83566050792E45874B23D34353477ED7C8506628AAC41B

Installed source build_id::

    65daa410237c6ef9a974c6645671e07639e68c3f27373de89b73e39f96ca796a

The actual Python 3.4 cold checker passed with native library loading forbidden,
manifest hashes verified, signed loopback ACKs, 27 banks and no card factory call.
It also passed the separate staged directory::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-22\transfer\ACQ_Python_Control_20261022_v8

Its sole site override is the existing XP read-key path; no credential bytes
are included. The staged configuration and manifest agree on SHA256::

    0164249BC89956C99441CE4F34143FEAB9E9F8C4B0886BECDF7C0361D50B110D

XP rollout has not yet been performed by this document. Action-time approval
was requested for replacing only the cold v7-r3 window with v8 in IDLE.
Before replacement, signed status must again confirm IDLE, zero NI resources,
disabled commands and no native initialization. Acquisition VI and its passive
transport must remain running. Everest servers, recorder and Windows startup
must remain unchanged. After replacement, a finite read-only acceptance must
prove all 27 VI banks advance through Tango and the web, inspect recorder status
without opening its archive, and record the actual handover gap.
