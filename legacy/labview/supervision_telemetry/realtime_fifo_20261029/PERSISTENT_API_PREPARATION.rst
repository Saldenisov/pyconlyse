Persistent VI-to-Python API preparation, 30 October 2026
======================================================

Status: Python source and offline tests only. No XP deployment, native VI edit,
NI initialization, synchronization change or live service restart is performed
by this preparation. The frozen package manifest and XP qualification history
continue to describe their original artifacts. This document is an addendum.

Current queue location
----------------------

The existing main SuperVision camera While loop has sequence 18881. Its frame 0
calls SUP_Camera_FrameTap.vi after Grab/FrameCount. That invokes
SUP_Camera_Observe_U8_UNCOMPILED.vi to materialize an owned U8 observation and
SUP_Camera_Queue_Latest.vi to enqueue its Variant packet into the named FIFO
ELYSE_SUP_CAMERA_RAW_LATEST_V1. The ordinary Enqueue Element has timeout 0 and
capacity 128. The historical name does not imply a lossy latest-only queue.
The original 30ms Wait is in frame 9 of that same camera loop.

SUP_Camera_Transport.vi runs its own While loop from the parallel FIFO entry.
It obtains the same named queue, then Dequeue Element removes its oldest packet.
The Dequeue timeout of 100ms only waits while the queue is empty. There is no
80ms Event Structure enclosing this transport. Before this API preparation,
the transport connected, wrote one frame, read one ACK and closed for each
packet. That VI remains unchanged until the native XP work session.

An IMAQ Image reference is not an immutable frame copy. Do not replace the
owned observation with the one shared Image reference overwritten by Grab.
No queue capacity, buffering policy, pixel format or 30ms Wait is changed here.

Backward-compatible Python API
------------------------------

The fixed 127.0.0.1:8768 listener now accepts repeated four-byte big-endian
length plus payload frames over a single connection. Payload schema, native
cluster layout, maximum lengths, native geometry checks, replay identities,
freshness rules and ordered ACK schema are unchanged. JSON and native camera
observations can share the stream. Legacy clients can still close after one ACK.

One handler processes frames sequentially, so each ACK belongs to the preceding
submitted packet. The existing maximum of four concurrent handlers remains.
The accepted socket uses TCP_NODELAY for short ACKs. No additional image queue
or new service is introduced.

* Waiting for the next frame has a two-second idle limit. Clean EOF or idle
  expiry between frames releases the connection without counting a rejected
  observation. A paused camera reconnects when it has another frame.
* Once the first bytes arrive, the complete remaining frame and ACK share a
  fresh absolute two-second transaction deadline. It renews per frame, never
  per recv. Slow trickling cannot retain a handler indefinitely. Socket deadlines
  do not preempt Python processing inside ingest_observation.
* Invalid lengths/native geometry or truncated payloads close the connection;
  unread payload bytes must not be treated as another message length.
* A fully consumed but rejected observation returns ok=false. Its next frame
  boundary is known, so a subsequent complete observation can still be accepted.
* ACK write failure ends the handler. Shutdown prevents further frame admission
  and retains the existing bounded handler-join lifecycle.

The ACK remains acknowledgement of local XP RAM admission, not Everest delivery
or database durability. Native observation identity/freshness checks are not
weakened by connection reuse.

Native VI change for the XP session
----------------------------------

Modify the existing transport, not the autotune IMAQ initialization frames:

  initial connection state: disconnected
  While transport active:
    Dequeue next packet
    if disconnected: TCP Open
    TCP Write length-prefixed packet
    TCP Read exactly 4 bytes ACK length
    validate bounded length; read exactly that ACK body
    validate ACK id/ok and receipt identity, expose a refusal
    retain connection on success
    on error/idle disconnect: Close, clear connection state, reconnect
  exit: TCP Close any owned connection

Keep socket ownership in this single consumer. Preserve FIFO capacity, producer
copy ownership, stop notification and join-before-release order. No busy loop is
needed on an empty FIFO. Retain source_session_id/capture/frame identity on an
ambiguous retry so a duplicate cannot freshen an old image. A dequeued frame is
not a delivery guarantee: refusal/overflow and ambiguous disconnect must remain
observable. Do not silently claim a dropped frame reached Everest.

The native candidate must be saved/compiled in LabVIEW 2012 before the live
test. Verify framing on a persistent connection, multiple ACKs, reconnect after
an idle/remote close, stop while waiting for a frame, and stop during socket I/O.
Compare Grab/FIFO/admission/ACK counts by growing frame identity. At 25Hz a
120-second stream supplies about 3000 frames only if capture actually maintains
that rate; this source change does not qualify 25Hz on XP.

Offline tests
-------------

tests/unit/test_supervision_vi_persistent_ingress.py uses private ephemeral
loopback ports, synthetic native/JSON frames and no outbound relay. It covers
multiple frames per connection, fragmented/coalesced writes, backward-compatible
one-frame clients, a connection lifetime longer than one transaction deadline,
idle release, partial/trickled payload deadlines, semantic rejection followed by
a valid frame, framing failure without unsafe resynchronization, handler bounds
and shutdown/join. test_supervision_passive_shadow.py additionally exercises two
observations through the actual passive publisher on the same connection.

Validation: the persistent ingress, VI telemetry, passive shadow, camera stream
publisher, per-channel wire and nonblocking integration suites ran 92 tests on
Python 3.4 (three modern-Everest-only skips) and 92 on Python 3.12 (all passed).
The Python 3.4 run took 53.529s; Python 3.12 took 20.595s. These offline results
do not measure XP camera throughput or qualify the unchanged native transport.
