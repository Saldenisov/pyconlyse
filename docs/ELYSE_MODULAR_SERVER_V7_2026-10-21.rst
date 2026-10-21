Modular unified Acquisition server: v7 candidate
===============================================

Scope and deployment boundary
-----------------------------

The candidate retains one Python 3.4 process on XP and the existing telemetry
Tango device on Everest. No second telemetry Python service is required. The
three local buttons remain Initialize, Deinitialize and Stop server. This
refactor was tested offline; the running v6 installation, LabVIEW, NI cards,
Tango processes, web process and recorder were not inspected or changed.

In IDLE, with no NI ownership, the same process accepts the existing loopback
VI transport and forwards its 27 banks. After LabVIEW releases the cards and
the operator explicitly confirms Initialize, that process produces native
telemetry and admits commissioned commands from Everest. VI silence does not
automatically initialize cards. Fresh VI traffic still blocks Initialize;
faults or retained native ownership never trigger fallback to VI. Deinitialize
requires the existing release conditions and waits for a new VI image rather
than reviving a pre-initialization snapshot.

Modules and execution ownership
-------------------------------

* ``command_protocol.py``: exact request fields, named allowlist and signatures.
* ``command_broker.py``: unchanged session/revision/lease fences and command
  ledger. Its extracted class and protocol functions retain their original AST.
* ``command_dispatch.py``: one dedicated admission worker, at most one active
  admission and one pending request by default; no automatic command retry.
* ``command_http.py``: authenticated HTTP adapter; hands admission to that
  worker instead of invoking the broker on a request handler.
* ``standard_banks.py``: unchanged codec, bank order and type descriptors; all
  six extracted codec functions retain their original AST.
* ``telemetry_view.py``: RAM-only projection using a non-waiting owner-lock
  attempt; excludes command ledger, capability projection and journal/marker I/O.
* ``telemetry_publisher.py``: independent publication worker and signed relay
  worker, with the existing bounded latest-only outbox.
* ``dual_mode_telemetry.py``: source arbitration, VI ingress and publication
  ordering. A private publication lock does not wait for command admission.
* Existing ``acquisition_runtime.py``: sole owner of NI initialization, reads,
  writes, procedures and resource cleanup. No additional native reader exists.

The original ``acquisition_remote.py`` and ``native_telemetry.py`` imports remain
compatibility facades. They do not create processes or start workers on import.
New modules participate in the installed-source fingerprint and both package
import closures. No legacy deployed service is deleted by importing this code.

Failure semantics
-----------------

A busy command/lifecycle lock no longer blocks publication. Instead, the
publisher emits an unavailable boundary with null bank values, marks the owner
view non-current and preserves elapsed source age. It never labels cached
measurements current. VI ingress rejects promptly when the owner lock is busy;
seen VI traffic still conservatively fences Initialize. Concurrent old polls
cannot overwrite a newly accepted VI image or roll back the cached source epoch.

Network acknowledgement delays affect only the relay worker. One immutable
in-flight packet and one replaceable pending packet preserve source identity
and age. This is latest-only forwarding, not lossless logging or atomic sampling.
The 27-bank schema is unchanged: native mode can populate the same 12 confirmed
banks; the remaining 15 stay explicitly unavailable, not fabricated zeroes.

Admission waits up to one second for a reply by default. A pending request that
expires or is cancelled during shutdown is not submitted to the broker. An
already started admission that outlives the reply deadline has an explicitly
unknown outcome: no cancellation or automatic retry is claimed. The existing
command ID ledger retains at-most-once admission within the boot session.
Closing the HTTP service cancels pending requests, joins admission and refuses
to release its socket while that worker remains owned. The window retains the
shutdown error and retries orderly close rather than hiding a live worker.

A long native procedure still serializes NI access. Telemetry publication and
transport remain separate, but fresh card reads cannot be promised while that
same NI owner is executing a procedure. EXECUTING values remain unavailable.
Python thread scheduling, the GIL, vendor DLLs, process failure and operating
system suspension prevent a hard real-time guarantee. The existing HTTP
handler limit is shared by status and command requests; independent pushed
telemetry does not depend on those handler slots. This refactor does not promise
HTTP fairness under request flooding.

Hardware gates, credentials, startup outputs, cooling protection and electrical
shutdown logic were not relaxed. Remote initialization, deinitialization,
server exit and arbitrary raw writes remain unavailable.

Offline verification
--------------------

The combined backend/protocol/receiver/recorder/web regression passed 139 tests.
Actual CPython 3.4.4 passed 28 policy/concurrency tests; the 14 concurrency tests
also passed five consecutive runs. Event-controlled tests cover blocked command
admission with signed telemetry ACKs, blocked network ACK with command admission,
bounded queue pressure, expiry without later execution, unknown outcomes,
duplicate IDs, socket ownership during shutdown, source-change races and a long
fake native command with all backend calls confined to one owner thread.

Reproduce the Python 3.4-compatible policy/concurrency gate from the repository::

    python -m unittest tests.unit.test_acq_control_release tests.unit.test_acq_modular_server

Generate new, non-overwriting release directories and check the XP package::

    python -m tools.package_acq_web_control NEW_XP_DIRECTORY
    python -m tools.package_acq_web_control NEW_EVEREST_DIRECTORY --everest
    PYTHON34 tools/check_standard_telemetry_python34.py NEW_XP_DIRECTORY

The cold checker forbids native-library loading and uses loopback fixtures only.
It verifies manifest hashes, signed telemetry ACKs, 27-bank forwarding, recent-VI
Initialize exclusion, non-waiting telemetry and the command-admission thread.
These results do not establish live VI delivery on XP. That transport inspection
remains deferred at the operator's request; absence of VI snapshots must not be
reported as healthy current telemetry or silently replaced by native card reads.

Checked, undeployed artifacts
-----------------------------

XP: ``C:\dev\pyconlyse\.tmp\acq-modular-xp-20261021-v7-r2.zip``
(60 source files plus manifest), SHA256::

    85B2530E219A2ADD0773BEB0E3033993AC1B6B2788D71BA170EA181A86DA6B1C

Everest: ``C:\dev\pyconlyse\.tmp\acq-modular-everest-20261021-v7-r2.zip``
(41 source files plus manifest), SHA256::

    8BB23B975DDA03D8B40ACEA9D950261E85CC6F77E53253C744D96CC3B6118DCE

The actual Python 3.4.4 cold checker passed against that XP artifact. Its
installed-source build ID is::

    5da19eccd3429ef6c5bcfeac6abc246786810dcb6d75fd32a7e32dcf44363287

Both original v6 artifacts and the earlier v7 draft bundles remain unchanged.
No package was copied to XP, no startup shortcut was changed, and no live
source or process was switched by this refactor.
