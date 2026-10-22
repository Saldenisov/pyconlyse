v7 live telemetry recovery and bounded contention correction
==========================================================

Observed deployment and recovery
-------------------------------

The cold v6 Python window was stopped and v7-r2 opened on XP after the user's
action-time approval. Its installed-source fingerprint matched
``5da19eccd3429ef6c5bcfeac6abc246786810dcb6d75fd32a7e32dcf44363287``;
session ``1242280fd36448418052b791e19c456a`` remained IDLE, with zero NI tasks,
state revision zero and remote commands disabled. Acquisition was not restarted,
and no card initialization or hardware command occurred. Everest's existing
Tango receiver, web process and recorder were not restarted. The live HDF5 file
was not opened. Startup configuration was not changed.

Initially, the ingress accepted zero VI snapshots. The loaded Auto transport
had debugging enabled, but a passive probe on Dequeue.timed_out observed no
executions. This does not establish why the Auto worker was inactive. Temporary
probes were removed without saving a VI or pausing the acquisition hierarchy.

The previously installed, standalone ``ACQ_SharedState_Transport.vi`` was read
back from ``C:\ELYSE_ACQ_TELEMETRY_20261012``. Its SHA256 matched the complete
offline-audited read-only queue/TCP implementation::

    873D1484E7368077F823100570EFCC9B8E6B51051B43125FAF1B05D46930BC5A

Starting only that existing passive VI restored incoming live snapshots. No
additional Python telemetry process was started. Between 07:23:36.102346 and
07:23:42.385093 UTC on 2026-10-22, VI acceptances increased 417 to 492 and
Everest receipts increased 199 to 231. Tango and the web both contained exactly
the expected 27 bank names. A matched sequence, 609, had 27 non-null banks,
zero reported bank errors, FRESH web quality and maximum age 0.188 s. These are
delivery observations, not proof of hardware safety or inter-bank atomicity.
Host observation times are used; XP's clock was not corrected.

Remaining v7-r2 defect and prepared correction
-------------------------------------------

Other samples contained 27 OWNER_STATE_BUSY null records despite continuing VI
traffic. The ingress itself briefly owns the runtime lock; a concurrent polling
capture can therefore appear busy and overwrite a recently admitted VI image.
Ingress rejections also increased 21 to 28 during the interval. They retain the
existing conservative ownership fence, not a guarantee of lossless delivery.

The correction suppresses only busy bridge polls within the existing two-second
Initialize quiet interval following a successfully admitted VI image. It sends
nothing: the receiver's original packet continues aging without replay, a new
timestamp, sequence or freshness extension. At the quiet boundary, unavailable
packets resume. Confirmed native/lifecycle epochs and native busy behavior remain
unchanged. Recent or rejected VI traffic still blocks Initialize. No hardware,
command, cooling, shutdown or commissioning gate is relaxed.

Regression coverage includes unchanged packet identity with increasing age,
the exact two-second boundary, a confirmed native epoch, cold contention, source
ordering and fast ingress rejection. The combined backend/receiver/recorder/web
suite passed 142 tests. Actual CPython 3.4.4 passed 31 policy/concurrency tests;
the cold packaged-source checker also passed with native loading forbidden,
signed loopback ACKs and manifest verification.

The new, undeployed XP artifact is::

    C:\dev\pyconlyse\.tmp\acq-modular-xp-20261022-v7-r3.zip
    SHA256 848B4F5105D81857C6F154A6865FAD1429D3E005065C6E3CCEFB96BCD7E1CBE8
    build_id 4da741d6ab733645fc309131c6327c39a1ec1863fda13a06fe05e973a7166708

Only v7-r2 is running. Launching this corrected build still requires action-time
approval. End-to-end acceptance of the corrected build remains pending. The
original Auto worker's startup path also remains unresolved; restarting its
hardware launcher was excluded by the user's operating constraints.
