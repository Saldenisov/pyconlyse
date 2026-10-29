Full-frame camera transport: prepared on Everest, not active on XP
================================================================

The active XP session was returned to the original SuperVision at the user's
request. The sampled telemetry VI was normally stopped at 08:13:39 Paris on
2026-10-29. Its ten modified project/helper items were saved with native
LabVIEW, every test window was closed, and the original desktop SUPERVISION
shortcut was opened. Original clock, green synchronization status and camera
profiles progressed at 08:25:46 and again at 08:34:06. No camera or counter
Python Initialize was called. Old SuperVision has no added telemetry hooks;
fresh SuperVision camera/synchronization data on Everest is therefore not
expected while that original VI is in use. Acquisition's 27 banks remain live.

Desktop shortcut
----------------

The original desktop SUPERVISION shortcut was copied in XP Explorer, renamed
``Supervision Telemetry``, and its target changed to::

  "C:\Program Files\National Instruments\LabVIEW 2012\LabVIEW.exe" "C:\SUPERVISION_TELEMETRY_20261028\Supervision Telemetry.vi"

The copied shortcut retains the original icon and working directory. Its
target and label were checked in Properties. It was not launched during the
restored original session. Native Save All may have updated copied VI caches;
the pre-run artifact hashes are historical pins, not a new post-save readback.

What currently discards frames
-----------------------------

* The observer's native source gate requires 1000 ms between copies.
* ``ELYSE_SUP_CAMERA_RAW_LATEST_V1`` has capacity 1 and replaces old snapshots.
* The Python owner publisher has a one-second camera budget. r21 fixes ACK
  starvation but deliberately preserves this sampled budget.
* Web retrieval is a sampled latest-image viewer. It now retains the last valid
  canvas through stale/unavailable responses, with an explicit growing age.

These observations do not show that a queue blocks the NI Grab loop. The
existing producer is lossy by design. Removing only the Python budget cannot
recover frames already skipped by the observer or replaced in the VI queue.

Prepared binary transport
-------------------------

``legacy/xp_acq_control/elyse_agent/camera_stream.py`` provides an independent
CPython3.4 stdlib camera FIFO, persistent sender and authenticated receiver.
Construction does not open sockets or start threads. It has no NI, Tango,
telemetry publisher, SQLite or PostgreSQL imports. It is not wired into the
current application or deployed to XP. Explicit caller wiring remains required.

The intended path is::

  IMAQ Grab
    -> synchronous owned U8 copy before mutable image processing
    -> bounded native frame FIFO, enqueue timeout 0
    -> independent native consumer -> local Python frame ingress
    -> independent Python frame FIFO
    -> compression + persistent binary TCP worker
    -> Everest authenticated receiver -> latest-image RAM cache -> web

  Synchronization control-memory observations
    -> existing telemetry channel -> durable spool -> PostgreSQL

The Python queue holds at most 128 frames and 64 MiB of raw pixels. Pixels
must already be owned immutable bytes. Enqueue performs no compression or
network calls. It rejects a new frame and increments ``rejected_new`` when
either limit is reached; it never silently replaces an older frame. At
768x576 U8, the frame-count limit covers about 5.12 seconds at 25 frames/s.
No finite RAM queue can guarantee every frame during an indefinite outage.

The sender compresses losslessly with zlib level 1 outside the queue lock,
uses binary pixels instead of base64, and reuses one TCP connection. Successful
sends have no rate-limit sleep. HMAC-SHA256 covers bounded metadata and compressed
pixels. Receiver authenticates before decompression and caps decompressed bytes.
Only an authenticated ACK matching stream, message and nonce removes the head.
Connection loss retains that head. A duplicate retry within the same receiver
process is ACKed without a second consume callback. ACK means RAM admission,
not disk recording or physical hardware acknowledgement.

Receiver session state is bounded to 64 streams and lives in RAM. A restarted
receiver resumes at the sender's retained pending head. Its signed receiver
epoch changes and the sender counts that change; the receiver reports an
unknown prior ACK prefix when the first message exceeds1. This is explicit
uncertainty about preceding RAM delivery, not a claim of durable exactly-once
recording across restart. No automatic queue reset or silent loss is implemented.
Unpaced compression on actual XP and NI copy time remain unmeasured.

Required native integration before another live test
----------------------------------------------------

1. Work in a new copy; retain the original and current sampled release.
2. Remove the 1000 ms observer copy gate, keeping unique Grab/frame identity,
   current run/capture epoch, source error and full unsigned channel metadata.
   Preserve the synchronous owned-copy edge before Rotate/mutable processing.
3. Replace the capacity1 lossy queue with a versioned bounded frame FIFO.
   Wrapper owner, producer and consumer must use the same new name/type/bound.
   Use enqueue timeout0 with visible overflow and last-failed-frame counters.
   Never enqueue the mutable IMAQ image reference as if it were owned pixels.
4. Let a dedicated consumer wait for data. Do not insert a fixed wait after a
   successful send. Preserve explicit stop signaling, worker join and final
   queue release; report a failed join without pretending it completed.
5. Connect accepted native frames to the separate Python FIFO, not to the
   owner's replaceable telemetry outbox. Keep counter observations independent.
   Wire the receiver's RAM callback into DS video projection, with separate
   source ages, queue/drop metrics and explicit reconnect lifecycle.
6. Qualify stopped native20 sources and native12 exports, then obtain a live
   25 Hz count/sequence comparison on XP during an authorized test window.
   Current old SuperVision must stay running until that window is agreed.

Offline tests and bandwidth limits
---------------------------------

Eleven transport tests passed under actual CPython3.4.4 x86 and CPython3.12.14.
They cover full-size lossless bytes, authentication before decompression,
bounded decompression, immutable input, count/byte overflow, ordered persistent
delivery, lost-ACK retry, wrong-ACK rejection and a deliberately blocked receiver
without blocking producer enqueue, plus receiver restart with explicit unknown
ACK-history reporting. These are loopback/fixture tests, not NI tests.

The standalone bench feeds 125 synthetic 768x576 U8 frames at 25 Hz, separately
for a repetitive ramp and 8-bit entropy. Both fixtures were delivered and ACKed
in order with zero rejects on Everest under both interpreters. Portable receipts
are ``camera_stream_benchmark_py34.json`` and ``camera_stream_benchmark_py312.json``.
They measure Everest loopback only, not XP CPU, IMAQ copying or LAN throughput.

The incompressible fixture needs approximately 88.58 Mbit/s including this
binary frame envelope at 25 Hz. Original raw pixels alone need 88.47 Mbit/s;
the previous base64 pixels alone need 117.96 Mbit/s. A single real dark frame
previously compressed to 178403 bytes, about 35.68 Mbit/s at 25 Hz, but that
ratio cannot be generalized to other images. No live 25 Hz result is claimed.

Telemetry database policy now active on Everest
-----------------------------------------------

Only ``telemetry_archive.py`` was replaced, with backup and unchanged Tango
properties. At 08:35:45 Paris the replacement DS was ON, all 27 bank sequences
progressed in the original Acquisition source session, and the archive was
RUNNING with ``image_policy=metadata_only_no_pixels``. Its older backlog was
82746 records and still draining; catch-up was not complete.

New ingress strips camera pixels before durable spooling. Database delivery
also strips pixels from legacy queued records. A metadata allowlist excludes
unknown future image payload fields. The original signed identity digest is
retained for idempotent retries. Live authenticated input and RAM image bytes
are unchanged. Existing PostgreSQL historical rows are not rewritten/deleted.

The real SuperVision observation at 08:12:54.269030 Paris was read from the
already-authenticated spool and idempotently delivered to PostgreSQL. Its
16 control-memory values, source identity and source age were read back exactly;
the archived record contains no image pixels. No spool row was deleted by this
bounded verification. Ordered background draining recognizes the same UID.
These values remain software observations, not independently measured timing.
