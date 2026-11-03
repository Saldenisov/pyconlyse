Persistent telemetry and automatic reconnection
==============================================

Result and boundary
-------------------

The Acquisition and SuperVision Python publishers now retain one TCP
connection to Everest :8767. Each publication still has its existing length
prefix, signature, nonce, relay ID and monotonic message ID. A successful ACK
keeps the socket open. EOF, timeout, invalid ACK or socket error closes it;
the independent forwarding worker retries without an attempt limit, with the
existing bounded transaction timeout (2 s) and retry interval (1 s).

The frame currently awaiting an authenticated ACK is immutable. New pending
snapshots replace older pending snapshots; retrying an old snapshot preserves
its increasing source age. Neither reconnecting nor changing a receiver
process turns cached measurements into fresh measurements. Hardware commands
are outside this mechanism: no automatic command replay, Initialize or NI
recovery was added.

The Everest receiver accepts successive authenticated frames on the same
socket and remains compatible with existing one-frame clients. Idle time does
not consume the next frame's 2 s transaction deadline. Peer admission and eight
connection slots bound handler ownership. Shutdown wakes idle connections and
waits at most 3 s for handlers before allowing the store to close. A Winsock
partial read can finish only when its transaction deadline expires.

Runtime telemetry exposes connection attempts, successful opens, failures,
worker liveness and time since the last authenticated ACK. ``connected`` means
a retained socket, not proof that the remote receiver or measurements remain
current. Existing source ages and stale flags retain that distinction.

Camera and VI paths
-------------------

The separate Python camera worker already retained one persistent connection
to Everest :8769. It now exposes the same reconnect diagnostics and enables
SO_KEEPALIVE. Its framed ACK timeout, not the operating system's potentially
long keepalive interval, detects a stalled transaction. A real-socket test
starts its receiver late, restarts that receiver, and confirms recovery without
restarting the sender or resetting transport IDs.

The typed SuperVision camera ingress :8768 already supports persistent framed
connections. The XML ingress :8766 now does so as well, for both local roles.
It accepts older one-frame VI senders, preserves all 27 Acquisition banks, and
can accept a new connection after an abandoned partial frame. A complete bad
XML observation receives a negative reply without losing the next boundary;
malformed or partial framing ends that connection.

The deployed native camera/XML transport VIs have NOT been rewritten by this
change. Their existing loops still open and close TCP for each observation.
The camera source audit confirms that the healthy frame's Close primitive is
inside the sending branch. Therefore, deploying Python alone does not remove
the local VI -> Python connection churn. The original VI, synchronization
logic and hardware configuration remain unchanged.

Native work remaining
---------------------

Both transport helpers need a native LabVIEW edit:

* Carry the TCP reference and connected state in initialized loop registers.
* Open only for the first queued observation or after a failed connection.
* Keep the length prefix, payload and complete bounded ACK read in order.
* Retain the healthy reference after an ACK; close/reset it on a transport or
  framing error and retry from the independent telemetry worker.
* Keep transport errors private. Do not feed them into the hardware business
  logic or retain an error cluster that prevents the next reconnect attempt.
* Close the retained reference after Stop, before releasing queue ownership.
  Keep the existing latest-frame queue, capture and synchronization logic.

No unsupported VI resource writer was used. Native editing is currently
blocked: two computer-use selections of local LabVIEW2020x86 window12519588
returned another application's image and
``Accessibility state unavailable for window 12519588``. App input stopped;
the user was asked to expose the actual LabVIEW window. The copies in the local
preparation folder are unchanged source copies, not qualified new VIs.

Validation
----------

Actual CPython3.4.4 x86 executed the signed transport, native-camera and VI
ingress tests. Coverage includes 1001 publications through one connection,
receiver initially offline, receiver restart, lost ACK/deduplication, silent
receiver timeout, authenticated incorrect ACK, legacy one-shot compatibility,
camera recovery, idle/partial-frame shutdown, bank preservation, connection
limits, and source-swap rollback without changing configuration/keys/journals.

Recorded runs:

* Python3.4 camera/publisher/VI/reconnect group: 98 cases, 5 skipped; all others
  passed. The subsequently added camera recovery test passed in the 11-case
  reconnect group (2 modern-receiver cases skipped).
* Python3.4 reconnect/XML/nonblocking/persistent-ingress group: 40 cases,
  2 modern-receiver cases skipped; all others passed.
* Python3.4 installer rollback/preservation group: 3 passed.
* Python3.12 receiver/source-arbitration/nonblocking group: 106 passed.
* Python3.12 camera/publisher/federation/reconnect group: 124 passed.
* Python3.12 installer group: 3 passed.

The historical ``tools/check_standard_telemetry_python34.py`` acceptance script
stops at its obsolete ``len(OPERATIONS) == 24`` assertion; the current contract
has 25 named operations. This predates the transport phase of that script and
is not used as a passing qualification result. The script remains unchanged.

Deployment
----------

Everest's existing Tango DS was updated on 3 November 2026, 07:20 Paris.
PID24600 stopped normally; replacement PID37832 resumed all 27 fresh banks,
camera delivery and PostgreSQL commits without restarting XP/VI or issuing
hardware commands. Installed receiver SHA256 is
``a38753eb87f1121c327c26164ae89628afde9f87887fe227c6de1cb0a659090d``;
DS entrypoint SHA256 is
``f7700f74dd4a9e619b156de70231b7ebba78a2bca1973299117185dc0445e2bd``.
Rollback files and local before/after readbacks are at
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\persistent_tcp_20261103T061952Z``.

The following 60.828 s read-only web check observed all 27 banks fresh and
advancing, camera available in all 13 samples, unchanged fresh synchronization
settings, and zero new stale-camera or ingress-error counts. Camera delivery
averaged 16.358 frames/s and 57.957 Mbit/s; sustained25Hz remains unqualified.

XP Python modules are prepared, NOT installed. They require normal closure of
only the cold Python orchestrator, then its existing launcher. This update
does not stop or start a VI. The current old XP publishers remain compatible
with the updated receiver and still use one connection per :8767 publication.

The first Acquisition installation attempt at08:43:22Z was refused before any
file swap: the installer incorrectly expected bind_host/port in its separate
active control configuration. The existing server reopened automatically and
continued delivering 27 fresh banks. Endpoint validation now follows the GUI:
Acquisition reads the sibling config.acquisition.json, while SuperVision reads
its single configuration. Eight installer/endpoint tests pass on both Python3.4
and Python3.12, including wrong-role/host rejection and configuration preservation.
The same shared-folder apply_xp.py has been rebuilt; module payload hashes are
unchanged. This correction does not claim that the pending XP update ran.

Build a self-contained source-only update folder::

    python tools/build_telemetry_reconnect.py --output C:/dev/SuperVision_Telemetry/persistent_20261103/release

Copy that folder intact to XP. The generated installer requires Python3.4x86,
the correct local role/bind address, closed Python API/ingress ports, the
existing application's configuration lock, and pinned pre-update module hashes.
It backs up and swaps only two Acquisition modules or four SuperVision modules;
it changes no site configuration, key, ownership evidence, journal, NI or VI.
It deliberately does not launch or initialize the server.

Example for the verified SuperVision layout, once its cold Python server is
normally closed::

    C:\Python34_ELYSE\python.exe C:\ELYSE_TCP_UPDATE\apply_xp.py --role supervision --runtime C:\SV_READY_20261030\runtime --config C:\SV_READY_20261030\runtime\config.supervision.active.json

For Acquisition, supply its actual active runtime and config paths; do not
guess a historical installation directory. Native VI replacement and a live
Python-only reconnect test remain pending access to the correct UI.
