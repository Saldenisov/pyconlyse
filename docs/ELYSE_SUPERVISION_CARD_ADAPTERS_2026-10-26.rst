SuperVision card source profiles and deferred adapters
=====================================================

Scope and provenance
--------------------

Two local NI boards are represented: NI6602 ``Dev1`` and NI1409 ``img0``.
The parent investigation independently observed these entries in read-only
NI MAX on 10.20.30.2. No board was reserved or initialized by this work.

``tools.validate_supervision_card_sources`` validates original extraction
receipts, original VI bytes, raw block-diagram XML and front-panel defaults.
It rejects the separately modified ``Supervision/extracted`` helper copy.
Pinned sources:

* Original root VI:
  ``B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B``.
* Original root BD XML:
  ``F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7``.
* Original ``1_SUP_INIT_NI6602.vi``:
  ``CE8BCA30E727C9B8C1EE9681263FBCE1D60247C2DBECDD0B73A37A385C88104F``.
* Counter initializer BD XML:
  ``3E4A29FF2DBBD54CD79EF3AF6123E5A0A68C8B035AFC585443DAE93BA8E01378``.

NI6602
------

``synchronization_profiles.supervision_counter_profile()`` returns all eight
source configurations. All eight source frames start their own task before
the next frame. They differ from Acquisition's six startup counters; these
plans must not be applied to Acquisition device 10.

All counters use rising ``/Dev1/PFI10`` start trigger, retriggering, low idle,
rising ``/Dev1/PFI11`` counter timebase, finite implicit timing of one sample,
and initial delay 0. Low/high ticks are, in counter order:

``(7,7), (43520,2000), (40166,200), (43500,200), (43500,2000),
(10000,10000), (6,200), (43500,2000)``.

At the source conversion of 20 ticks per microsecond these are the saved/live
UI delay-width pairs 0.35/0.35, 2176/100, 2008.30/10, 2175/10, 2175/100,
500/500, 0.30/10 and 2175/100 microseconds. The initializer's InitialDelay=0
must not be replaced with the displayed LowTicks-derived delay. The runtime
writer, in contrast, writes a requested delay to both InitialDelay and LowTicks.
Neither software agreement proves the actual external clock frequency or
electrical pulse timing.

``SupervisionCounterCard`` is cold at construction. Explicit local release and
start confirmations precede driver loading. Initialization starts counters in
source frame order. Partial construction/configuration retains every returned
handle; an unreturned constructor outcome retains an uncertainty sentinel.
Closing attempts all owned tasks but never clears another client's task.

The saved counter-2 frame first attempts Stop/Clear of the named SUPCOUNT2 task
and crosses Clear Errors. This Python owner deliberately does not erase an
unknown named task owned by another client. Fresh-owned normal setup matches
source settings; this is not native error-cluster/dialog equivalence.

Runtime timing updates require a known owned counter and positive finite,
unsaturated I32 tick encodings. PulseDone polling retains source 1-ms waits;
an explicit Python wall-clock deadline replaces the source's unbounded wait.
A timeout performs no stop/write/start. After any possible partial write,
the counter remains uncertain and cannot be automatically replayed/restarted.

NI1409
------

Original root diagram 12058 calls IMAQ Init uid18953 with ``img0``, writes
White Reference and Black Reference properties at uid15292, reads acquisition
dimensions, and enters IMAQ Grab Setup uid18912 with the fresh local channel.
Camera-loop acquisition is IMAQ Grab Acquire uid15740. Original saved defaults
decode to channel 2, white reference 0.9 V and black reference 0.1 V; they are
source defaults rather than a fresh readback from a running VI.

``SupervisionVideoCard`` requires those three explicit configuration fields.
``CtypesIMAQ`` defers the installed 32-bit ``imaq.dll`` load until explicit
initialization. Function prototypes and attribute IDs are checked against the
installed NI-IMAQ ``niimaq.h`` (not NI-IMAQdx). Standard functions use stdcall;
variadic ``imgSetAttribute2`` uses cdecl with typed U32/double arguments.

The native path is interface open, session open, white/black/channel attributes,
bounded frame-wait attribute, and explicit high-level Grab Setup. Each raw grab
checks current U8 geometry, row stride and NI buffer size before copying; row
padding is removed and no borrowed native pointer crosses IPC. Maximum raw
frame is 524288 bytes, allowing its base64 representation inside the existing
1-MiB private IPC envelope. The frame sequence and UTC timestamp identify a
software grab observation, not a hardware exposure counter or timestamp.

The adapter deliberately publishes raw frames before the source Vision
interlace, BCG, centroid/profile and display operations. It does not pretend
that the nine legacy Vision processing buffers are implemented. Native frame
lifetime, installed XP DLL compatibility and actual geometry require the first
explicit hardware qualification; RAM tests are not that qualification.

``C12NI1409`` in the standard 27-bank schema is a String variant, not pixels.
Raw image frames require a separate bounded image stream/attribute. Neither
NI-IMAQdx ``cam0/cam1`` nor the Basler cameras are opened by this NI1409 adapter.

Validation
----------

Actual CPython 3.4.4 x86 and Python 3.12 with external networking denied each
passed 21 adapter/runtime tests. Tests cover cold construction, all source ticks and
per-frame starts, partial construction/property failures, no replay, bounded
PulseDone wait, explicit camera initialization order, malformed/oversized
frames, padded native rows, retained failed-close handles, and IPC size bounds.
The read-only source validator passes original hash/wire/default checks.

Independent local SuperVision host
---------------------------------

``supervision_control_server.pyw`` starts one cold local application. Its
only buttons are Initialize, Deinitialize and Stop server. Construction,
HTTP startup and a disconnected Everest link create no NI tasks. Initialize
requires local confirmation that SuperVision VI and other NI clients have
released both boards. It starts one retained private process per board:

* ``sync`` uses ``SupervisionSyncService`` and owns eight SUPCOUNT tasks.
* ``video`` uses ``SupervisionVideoService`` and owns img0 interface/session.

Both use the common ``CardProcessEndpoint`` bounded private request channel.
Each endpoint polls its own child independently. One lifecycle/command thread
serializes local changes; application-view capture, GUI, authenticated HTTP,
video input and counter input have distinct workers. A slow counter command
does not stop video polling. A failed camera input remains visibly unavailable
while the synchronization owner continues; neither child is replaced or
replayed automatically. A hung native call remains an unknown retained owner.

The configuration file is installation-local
``config.supervision.control.json``. Its exact version-1 fields are returned by
``default_supervision_configuration()``. The listener is fixed to
``10.20.30.2:8772``; telemetry destination is ``10.20.30.202:8767``. The read
key and command key are distinct local files, at least 32 bytes each. Unknown
configuration fields, arbitrary factory paths and remote endpoint overrides
are rejected. GUI startup holds the common file-instance lock and an
installation-local ownership marker. A prior or uncertain marker is preserved;
normal cleanup removes only this session's exact marker after both child
resources and process joins are confirmed. It is cooperative exclusion,
not proof that an independent VI has released NI resources.

Remote control and synchronization commissioning default to false. All 25
common command names remain in the protocol. Only ``counter_timing.set`` is
owned by this host, and only after explicit commissioning with a current known
sync owner, all eight retained resources, and the selected running counter.
Command admission uses the common session/revision fence, short lease and
bounded at-most-once command ledger. The typed request is queued; an HTTP
receipt is not a physical pulse acknowledgment. The other 24 operations never
execute on this host. Initialize and Deinitialize remain local actions.

The public RAM snapshot has ``host_role=supervision`` and
``server_variant=supervision_control_vnext``. It exposes per-card age and
health without inventing Acquisition/HT banks. Raw image data is absent from
all HTTP/control snapshots. ``video_frame_snapshot()`` is a separate in-memory
publisher accessor containing the bounded raw frame, actual sample age,
owner session and the camera worker generation as ``capture_session_id``.
``counter_memory_part()`` publishes 16 last-successful-command values with
source age; a pending command or old pre-command sample is unavailable. Those
values are software memory, not independent physical timing measurements.

Federated owner publishing is explicitly disabled by default until the new
Everest Device Server is configured. Only
``telemetry.enabled=true`` with ``telemetry.wire=federated_owner`` constructs
``OwnerTelemetryPublisher``. ``legacy_27`` is recognized as a migration choice
but cannot be enabled for this independent host: a second owner must not replace
the Acquisition banks in the old receiver. Canonical build identity delegates
to the package-wide source closure shared by both host roles; boot sessions
remain distinct. No deployment, VI shutdown or real initialization was performed.
