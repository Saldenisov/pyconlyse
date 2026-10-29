Independent camera ingress in the existing Everest Device Server
================================================================

This code is prepared for an Everest-only deployment. No XP source, original
SuperVision VI, running service, Tango property or hardware configuration was
changed by this integration work. An absent/empty ``camera_stream_config_file``
property keeps the independent listener disabled and preserves legacy video.

Files required in the Device Server's source closure
----------------------------------------------------

* Changed ``DeviceServers/control/elyse_acq/DS_AcqTelemetry.py``.
* New ``DeviceServers/control/elyse_acq/camera_ingress.py``.
* New-to-the-live-closure ``legacy/xp_acq_control/elyse_agent/camera_stream.py``.

The latter is CPython3.4-compatible; ingress/facade execute on Everest Python3.12.
It requires the already present protocol, telemetry_relay and supervision_wire
stdlib helpers. No NI, image archive or additional Python service is required.
An old source-closure pin must not be bypassed to deploy these new modules.

Explicit local configuration
----------------------------

An enabled production configuration has this shape (path/key and port must
be qualified by the deployment owner; this document does not create it)::

  {
    "schema_version": 1,
    "enabled": true,
    "listen_host": "10.20.30.202",
    "listen_port": 8769,
    "key_file": "camera-stream.key",
    "permitted_peers": ["10.20.30.2"],
    "source_mode": "LABVIEW_BRIDGE",
    "channels": [],
    "max_channels": 2,
    "transaction_timeout_seconds": 2,
    "max_clients": 2
  }

The key file resolves relative to the configuration, or can be an explicit
absolute local path. Key bytes never appear in public metadata. The explicit
alternative source mode is ``PYTHON_NATIVE``; no automatic source switch occurs.
Production listener binds only10.20.30.202 and accepts only10.20.30.2. A
127.0.0.1/127.0.0.1 configuration exists only for software fixtures.

An empty channel allowlist learns at most the configured number of actual
unsigned channel IDs. It does not assign physical camera names. An explicit
list restricts admissible observed IDs; neither route switches NI inputs.
The current camera wire requires the actual ``source_session_id`` in addition
to capture_session_id/sequence/channel. A transport stream UUID is not a native
VI run identity. The existing sampled XP producer has not been connected to
this new path; tomorrow's native/Python handoff must preserve this field.

Passive Tango interface
-----------------------

``camera_stream_json`` contains metadata only: enabled/transport, actual
``channel_ids``, ``selected_channel``, per-channel ``channels`` objects,
observed_hz/age/source identities, source sequence gaps and network counters.
No frame or pixel data is included in this attribute. Network metrics include
received_bytes, sent_ack_bytes and ingress_mbit_s_window over at most2 seconds.
The short-window estimate is not a sustained LAN throughput qualification.

``ReadCameraFrame("2")`` returns the actual observed channel2's latest image;
``ReadCameraFrame("")`` selects the most recently admitted channel. It is a
passive RAM getter, never an XP command client or camera-channel setter. Its
projection matches the existing video_json fields and adds::

  transport = "independent_binary_camera_v2"
  frame_identity = "<source_run>:<capture>:<channel>:<sequence>"
  transport_session_id = "<binary_sender_stream>"
  transport_message_id = integer
  images_archived = false

The outer and frame identities, channel, geometry and sequence agree. The
existing exact frame schema is preserved: LabVIEW carries source_session_id
inside the frame; Python mode carries that identity in the outer/session
projection. LabVIEW/native source strings remain distinct. Frame
sample_elapsed_seconds is0 with outer sample_elapsed_seconds_known=false
because this transport does not measure IMAQ copy duration. No physical
calibration or timing readback is claimed.

When disabled, the getter exposes only the actual legacy video's channel.
Requesting a different channel returns CHANNEL_NOT_OBSERVED and no pixels;
one camera is never duplicated under two labels. ``video_json`` preserves
the old path when disabled and selects the last real channel when enabled.

An invalid optional camera configuration or unavailable camera port is
reported as CAMERA_STREAM_START_FAILED without tearing down Acquisition's
27-bank listener. A configured failing source never silently substitutes
legacy pixels. The existing telemetry source, controls, synchronization
database policy and archive are untouched.

Admission, freshness and shutdown
---------------------------------

HMAC authentication and packet bounds precede decompression. Peer filtering
precedes packet decode/thread admission. Persistent handlers are limited to
max_clients; excess connections are rejected with a metric. Every packet has
an absolute transaction deadline; idle connections close rather than retaining
unbounded handlers. No successful-frame sleep or1 Hz limit is inserted.

Each admitted channel retains one immutable U8/base64 snapshot. Duplicate
identities cannot refresh age; changed pixels under the same identity, regressed
sequences, retired captures and older-capture replacement are rejected. At most
64 retired capture identities are retained per channel, with explicit refusal
when that bound is reached. Source age uses the greater of reported monotonic
source age and observed UTC-label age; observations more than5 seconds ahead
of Everest's clock are rejected. At2 seconds age the image is explicitly stale
and the getter returns frame:null. A browser can retain its prior canvas with
the growing source age. No image pixels enter SQLite or PostgreSQL.

The binary stream admits all correctly ordered sender messages; the RAM view
holds only latest images. Source sequence gaps are explicit and include
upstream skipping or intentional25-to12.5 Hz decimation; they are not labeled
hardware loss. The transfer itself has no frame-rate limiter. Source sampling
policy and browser25/12.5 Hz display are separate decisions.

Explicit prepared source half-rate admission
--------------------------------------------

``CameraFrameAdmission(queue,every_n=1|2)`` is a pure source-side component for
the future XP stream. It admits all unique observations, or the first/third/etc
unique observation independently for each actual channel and source/capture.
It preserves the original sequence and observation time; duplicates, regressed
sequences and retired captures do not advance the half-rate phase. State is
bounded by channel/capture limits. Counters distinguish intentional_decimated,
queue_rejected, duplicates/replays and errors. It performs no sleeps or network
I/O and does not change camera or NI settings. This component is not wired to
the current sampled XP producer. The web's displayfps selector is not a source
control command.

An actual25Hz source becomes approximately12.5Hz with every_n2. On the present
single-ADC NI1409 path, two alternating channels share the total acquisition
rate: a25Hz aggregate would give about12.5Hz each in the ideal case, before
switching/settling overhead. every_n1 should preserve that native alternating
flow; blindly halving each channel again would yield about6.25Hz. This code
does not claim two simultaneous independent25Hz camera exposures.

Because admission here receives already-owned pixels, it reduces wire/queue
load but cannot save the native ImageToArray copy work. A native pre-copy gate
would be needed to reduce that cost. Actual source cadence, measured latency
and queue age must determine any future explicit sampling setting; no arbitrary
network threshold or automatic source-rate mutation is implemented.

Software-only measured boundary
-------------------------------

The synthetic8-bit-entropy768x576 loopback test requested25Hz on each of TWO
channels (50Hz aggregate). All250 frames were ACKed with0 rejects, but draining
took6.047s for about5s of production, and peak queued frames reached44. This
test did not sustain worst-case aggregate50Hz in real time on the concurrently
loaded Everest. It measures neither XP CPU nor LAN capacity.

The explicit every_n2 test on the same250 observations admitted126 frames
and intentionally skipped124. All126 admitted frames were ACKed,0 were rejected,
the test finished in5.000s, and peak pending frames was2. Last original source
sequence125 was retained on both channels. This validates a software transfer
fallback, not a camera exposure or IMAQ throughput claim. Receipts are
camera_ingress_two_channels_py312.json and
camera_ingress_half_rate_py312.json. No pixels were written to SQL in either test.

Device deletion first stops the camera listener and shuts down connected
sockets. If bounded joining fails, the reference stays owned and replacement
is refused. The camera worker never owns Acquisition or NI locks. Tests cover
blocked reads, rejected peers/authentication/capacity, duplicate/stale/source
guards and the unchanged existing Tango27-bank facade.
