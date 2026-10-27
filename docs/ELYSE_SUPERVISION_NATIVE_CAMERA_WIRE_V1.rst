SuperVision native camera observation, version 1
===============================================

The SuperVision orchestrator accepts a native camera cluster on IPv4 loopback
``127.0.0.1:8768``, alongside the existing strict JSON protocol. The existing
27-control XML connection on port 8766 remains unchanged. Each connection sends
one U32 big-endian body length followed by its body and receives the existing
framed acknowledgement. An acknowledgement confirms local admission, not
durable storage on Everest.

The producer must copy owned pixels after the existing successful IMAQ Grab
and FrameCount observation, before Rotate can modify the image buffer. It
passes the original image reference and business error through unchanged.
Telemetry errors use separate diagnostics. The camera loop enqueues a String
into a capacity-one latest queue; a separate worker performs TCP operations.
The producer must not open another camera session or perform an additional grab.

Native cluster layout
---------------------

LabVIEW 2012 ``Flatten To String`` must use big-endian byte order, include
String and array sizes, and send its data-string output without a type
descriptor. The cluster has the following fixed order, without padding:

=================  ======  ===============================================
Field              Offset  Representation
=================  ======  ===============================================
magic              0       String: U32 length 17, ASCII ELYSE_SUP_CAM_BIN
version            21      U16, value 1
run_start          23      Timestamp128: I64 seconds since 1904, U64 fraction
capture_start      39      Timestamp128, same representation
observed           55      Timestamp128, same representation
FrameCount         71      U32, existing successful property observation
channel            75      U32, actual successful setup channel, 0 through 3
copy_elapsed_ms    79      U32, measured owned-copy duration
observed_tick_ms   83      U32, native Tick Count immediately before copying
pixels             87      2D U8: I32 rows, I32 columns, row-major pixel bytes
=================  ======  ===============================================

Pixels start at byte 95. Dimensions must be positive, with at most 524288
pixels. Exact body size is ``95 + rows * columns``; the maximum is 524383
bytes. Default DBL constants are incompatible with the declared integer fields.
The receiver validates the fixed header before reading the pixel payload.

Identity and freshness
----------------------

``run_start`` is captured once per actual main Run. ``capture_start`` changes
only after each successful existing Grab Setup or reacquisition. All six
original setup paths must be covered, including the path using constant
channel 0. Current front-panel channel alone does not identify every setup.
The required order is ``run_start <= capture_start <= observed``. Zero markers
are rejected. Source and capture identities preserve the exact sixteen native
timestamp bytes as lowercase hexadecimal; receipt time does not create epochs.

The normalizer derives observation sequence from microseconds since run start,
and frame sequence from ``FrameCount + 1``. Repeated FrameCount cannot refresh
pixels; retired epochs and regressed frame counts are rejected. Timestamp
identities do not assert cryptographic uniqueness.

VI and Python run on the same XP computer. Both wall-clock age and unsigned
U32 elapsed tick age must be in ``[0, 2)`` seconds; published age is their
maximum. Copy duration must not exceed source age. This includes queueing and
loopback transfer and prevents wall-clock rollback from refreshing an old
queued frame. Native Tick Count must first be qualified against the local
Win32 GetTickCount clock; no guessed offset or receipt-time fallback is used.

Qualification boundary
----------------------

The decoder and replay protections have offline Python 3.4 regressions. That
does not qualify a native producer. Before live use, a LabVIEW 2012 generated
fixture must match every byte of the declared layout, including Timestamp128
and two-dimensional array ordering. The U8 fixture
``[[0, 1, 2], [253, 254, 255]]`` must end in bytes
``00 01 02 FD FE FF`` and normalize to base64 ``AAEC/f7/``.

Native compilation, connector readback, copy-before-Rotate ordering, explicit
run/setup resets, clock agreement and bounded worker cleanup require separate
verification. Resource-repacked VIs with stale compiled code must not run.
Synthetic fixtures must never be published as actual camera observations.
