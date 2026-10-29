Prepared source wiring in the one SuperVision host
=================================================

Update 2026-10-29: the native FIFO patch is now prepared separately in
``../../realtime_fifo_20261029``. It removes the copy gate and changes all three
camera queue size inputs to 128, with ordinary Enqueue/timeout0. Its stopped
entry requires complete LabVIEW 2012 dependency loading/compilation before Run.
No XP installation or 25 Hz qualification has been performed. The paragraphs
below describe the existing Python preparation and deployed-source boundary.

This is source/package preparation on Everest, not an XP deployment. The
running original SuperVision and NI ownership were not changed. The optional
camera source path is now wired into accepted typed VI observations; it is no
longer only an unused FIFO/transport library. Removing the native1-second copy
gate and replacing the native capacity1/latest-only queue still require the
future VI copy/package update and live qualification.

Existing startup, optional configuration
----------------------------------------

The same ``supervision_control_server.pyw`` entry and three buttons remain.
``config.supervision.control.json`` may contain this explicit optional block::

  "camera_stream": {
    "enabled": true,
    "source_mode": "LABVIEW_BRIDGE",
    "host": "10.20.30.202",
    "port": 8769,
    "every_n": 1,
    "capacity": 128,
    "max_bytes": 67108864,
    "max_channels": 2,
    "timeout_seconds": 2,
    "retry_seconds": 0.1
  }

Omitting the block or using ``{"enabled": false}`` preserves the sampled r21
behavior. Enabling it requires the existing unified telemetry publisher to be
enabled. Destination is explicitly Everest, on a configured independent port
other than8767. Root must bind that port/key to the reviewed same-DS receiver
configuration; no port or property is automatically changed by this code.
The existing SuperVision read key authenticates this passive image stream.

Only LABVIEW_BRIDGE source mode is accepted by this prepared typed-VI path.
Requesting PYTHON_NATIVE is rejected rather than falsely promising a native
25Hz camera hook. Existing native Python owner video behavior remains unchanged
in its legacy owner path. A future independent native card-service callback
needs separate wiring and qualification. Web25/12.5Hz display selection does
not alter this source configuration or NI settings.

Dataflow and lock boundary
-------------------------

The enabled path is::

  native typed VI observation on existing loopback8768
    -> strict decode/actual source-run and capture/sequence admission
    -> bounded immutable video-descriptor staging FIFO
    -> independent staging worker: decode bytes, age, full/half admission
    -> bounded raw-byte FIFO
    -> independent sender: compression/HMAC/persistent TCP
    -> existing Everest DS independent receiver -> per-channel RAM -> web

Canonical observation hashing happens before the runtime/publisher admission
locks. The locked accepted-observation path only appends a shallow owned dict
of immutable schema fields into bounded staging. It neither decodes raw bytes,
compresses nor performs network I/O there. The typed local ACK remains a local
RAM receipt. ``independent_camera_staged`` reports whether a new unique image
entered staging; false means its bounded staging rejected it and increments
an explicit counter. It is not an Everest ACK. Duplicate images return no
new staging admission. Source transfer failures cannot turn a valid counter
observation into a command or physical acknowledgement.

Each actual channel has independent source/capture replay state, so alternating
camera captures do not retire one another. Original source_session_id,
capture_session_id, frame sequence, channel, observation UTC and source age
survive into the independent FIFO. Queuing age is accumulated before forwarding.
Source controls/NI calls never run on these image workers.

When enabled, typed VI images are omitted from the replaceable owner telemetry
outbox entirely; its1-second image budget cannot throttle this new path.
XML/27-bank decoding, C12 opaque String and synchronization control-memory
observations keep their existing semantics, admission and age. Native Python
video still follows the unchanged legacy owner behavior. Delivery status
explicitly distinguishes accepted_typed_labview_only from that native path.

Limits, lifecycle and source sampling
-------------------------------------

Staging is bounded independently by descriptor count and base64-character
bytes, with no replacement. The raw FIFO has its own configured count/byte
bound. Each can be up to64MiB; this is not a combined64MiB process-memory limit.
Queue overflow and intentional half-rate admission have separate counters.
Neither queue is durable across process exit. No source packet is labeled
delivered merely because its local VI ACK was sent.

The staging and sender workers start only through the existing publisher's
explicit lifecycle, and open no NI tasks. A cold constructor starts no thread,
listener or network connection. The sender connects only after raw frames are
available. Closing the publisher stops/join-checks the typed ingress and both
image workers; an unconfirmed close remains an explicit ownership failure.
No worker, process or device is automatically restarted.

every_n1 preserves every admitted unique source observation; every_n2 admits
alternate unique observations per channel/source/capture. Duplicate or replayed
observations do not consume phase. Original identities are not renumbered.
Source sampling and frame-count loss are visible separately from FIFO errors.
The present single-ADC NI1409 shares its acquisition cadence between alternating
inputs. If total cadence is25Hz, ideal per-camera cadence is12.5Hz before
switching overhead. No2x25Hz physical exposure claim is made.

Future package closure
----------------------

New module: ``elyse_agent/camera_stream_publisher.py``.
Required existing prepared module: ``elyse_agent/camera_stream.py``.
Changed startup/integration modules: ``supervision_vi_telemetry.py``,
``supervision_gui.py`` and ``acquisition_control_runtime.py``. The source
identity closure now includes both stream modules, so future build identity
changes normally. The already deployed Everest camera_stream.py and DS files
were not modified by this source-wiring preparation.

Tests use private RAM fixtures and disabled network/NI startup. They verify
rapid unique frame forwarding without the owner1Hz cap, actual per-channel
epochs, half-rate identities, duplicate suppression, staging/raw overflow
metrics, independent processing while publisher/runtime locks are held,
unchanged default/disabled wire behavior, configuration gates and three buttons.
