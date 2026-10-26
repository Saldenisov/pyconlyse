SuperVision VI telemetry wire: next candidate
===========================================

Status and scope
----------------

This is an offline Python receiver/publisher contract. The native LabVIEW
producer has not been authored or qualified. Installed r16 packages are frozen;
this change does not modify, launch or replace either running VI or XP server.
No NI operation is performed by either ingress handler.

This is the r17 candidate. Its cold installer uses new directories
``C:\ELYSE_Orchestrator_Acquisition_r17`` and
``C:\ELYSE_Orchestrator_Supervision_r17``; installed r16 directories remain
untouched. The r17 installer accepts an explicitly pinned Acquisition wire
mode (``legacy_27`` or ``federated_owner``) and a separately pinned SuperVision
publisher enable flag. Installation only copies files; it does not start a
publisher, activate DS federation, stop a VI or initialize a card.

Initial rollout defaults still preserve the active Acquisition VI stream and
leave the SuperVision publisher disabled. The later authoring session must
record its explicit mode/configuration changes and activate the one DS only
after both source routes have been checked. Candidate packages are staged at
``F:\ELYSE_Orchestrators\r17_candidate_20261026``. Native helper qualification
is still outstanding.

One ``SupervisionTelemetryPublisher`` inside the existing SuperVision server
owns two loopback listeners and one bounded authenticated publisher to Everest:

* ``127.0.0.1:8766``: existing 27-control XML helpers, unchanged wire format.
* ``127.0.0.1:8768``: typed local counter observations and raw camera images.

Python native ownership and VI ingress are mutually exclusive. Any retained
local card owner, Initialize/Deinitialize transition, pending operation or
shutdown closes VI admission. Accepted or otherwise valid recent VI traffic
blocks local Initialize for two seconds. Silence still does not prove that
LabVIEW released NI resources; the existing explicit local confirmation remains.

Existing XML path
-----------------

The existing four-byte unsigned big-endian length prefix, bounded XML body,
encoding and local acknowledgement remain compatible with the existing
Collector/Queue/Transport helpers. The receiver validates all 27 bank names and
order, then forwards only SuperVision authority:

* ``C1011NI6602[16:32]``: sixteen observed SuperVision counter-control values.
* ``C1011NI6602[32]``: selector; only explicit ``-1`` means no pending selector.
* ``C12NI1409``: original opaque String, never raw image pixels.

Counter values are observed control memory, not physical timing readback or
proof that a native counter call succeeded. XML timing begins at local receipt;
this legacy wire does not identify the main VI run or prove it is still active.
The native wrapper must be coupled to the actual main-VI lifecycle. Polling
controls of a stopped VI is not a qualified producer.

Typed request on port 8768
--------------------------

Each TCP connection carries one request and one reply. Prefix each UTF-8 JSON
body with its unsigned 32-bit byte count in network/big-endian order. Request
limit is 921600 bytes; total frame-read/write deadline is two seconds; at most
four handler threads are admitted. Only IPv4 loopback is accepted. There is no
network command or hardware-write operation on this port.

JSON fields are exact; duplicate keys, nonfinite numbers and unknown fields are
rejected. ``counter_part`` and ``video_frame`` are independently optional, but at
least one must be non-null::

  {
    "schema_version": 1,
    "publication": "ELYSE_SUPERVISION_VI_OBSERVATION",
    "source_session_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "sequence": 1,
    "source_running": true,
    "counter_part": {
      "values": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
      "source_age_seconds": 0.1,
      "source": "observed_labview_control_memory",
      "selector": -1,
      "pending_selector": false
    },
    "video_frame": null
  }

The example values are synthetic protocol examples, not accelerator settings.
``source_session_id`` is a lowercase 32-hex identifier regenerated for every
main-VI/source-producer run. ``sequence`` is an integer in 1..9007199254740991.
``source_running`` must be true and qualified by the native producer's main-VI
lifecycle; Python cannot infer that lifecycle from a local connection.

Counter values are exactly sixteen finite numbers in the original SuperVision
order. Selector is finite; ``pending_selector=false`` requires explicit ``-1``.
Source age is finite, nonnegative elapsed time since that observation, including
time waiting in the VI-side queue. A new image cannot renew counter age.

Raw camera object
-----------------

``video_frame`` uses ``federation_wire.validate_video_frame`` with these exact
fields::

  {
    "source": "labview_supervision_ni1409",
    "source_session_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "simulated": false,
    "sequence": 1,
    "sequence_interpretation": "software grab observation, not hardware frame counter",
    "capture_session_id": "99999999999999999999999999999999",
    "observed_utc": "2026-10-26T12:00:00.000001+00:00",
    "sample_elapsed_seconds": 0.01,
    "width": 2,
    "height": 2,
    "pixel_type": "U8",
    "encoding": "base64_raw_row_major",
    "data": "AAECAw==",
    "channel": 2,
    "processing": "raw_grab_before_legacy_interlace_bcg_profiles",
    "hardware_acknowledged": false,
    "source_age_seconds": 0.1
  }

The 2x2 image is a synthetic byte-layout example, not a claimed camera format.
Width and height must be positive integers whose product equals decoded byte
count, at most 524288 bytes. Channel is an integer in 0..3. No JPEG, resizing,
rotation, brightness/contrast/gamma operation or profile extraction is applied.

Copy immutable bytes from the owned raw acquisition buffer before legacy
processing and before buffer reuse. ``capture_session_id`` changes after each
successful GrabSetup/reacquisition/channel-generation change and is distinct
from the main-VI run identity. Frame sequence advances only for a newly observed
copied frame; a ring-buffer index alone is insufficient. Preserve observation
UTC and elapsed acquisition duration; neither is Python receipt time.

Replies, retry and freshness
----------------------------

A successful local acknowledgement has the same length prefix::

  {"id":"supervision-vi","ok":true,"result":{
    "accepted":true,"duplicate":false,
    "source_session_id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "source_sequence":1,"sequence":1,"hardware_writes":false,
    "acknowledged_on":"xp_ram_not_everest"}}

Failure replies use ``ok=false`` and
``error={"code":"snapshot_rejected","message":"..."}``. A local RAM ACK is
neither Everest durability nor proof that any hardware command succeeded.

Retry the same source session/sequence with identical component values and
identities; source ages may increase. Such retries do not republish or renew
component age. Changed bytes under an existing image identity, regressed source
or frame sequences, and retired source/capture sessions are rejected. A new
source run must first supply an independently current observation (age below
two seconds). A fresh XML counter observation cannot renew raw image age.

Camera publication is latest-only and bounded to at most one new image per
second. Pending images may be replaced; immutable in-flight signed messages are
retained until their matching ACK. This is not an every-frame archive guarantee.

Everest receives the same owner-scoped signed envelope, with
``source_mode=LABVIEW_BRIDGE``. Optional ``source_identity`` preserves the last
typed-side-channel run and message sequence; it does not assert atomicity with
separately observed XML components. Raw images retain their own run, capture
generation, frame sequence and age. ``video_json`` exposes images while current
(age below two seconds); the 27-bank JSON contains metadata only. All remote
SuperVision commands remain disabled in VI bridge mode.

Canonical executable anchors
----------------------------

* ``elyse_agent/supervision_vi_telemetry.py``:
  ``validate_vi_observation``, ``decode_vi_observation``,
  ``SupervisionTelemetryPublisher``.
* ``elyse_agent/federation_wire.py``: ``validate_video_frame``.
* ``tests/unit/test_supervision_vi_telemetry.py``: synthetic Python 3.4 and
  modern-host store contract cases, with no socket or NI access.

Native LabVIEW JSON/base64 construction, source lifecycle hooks, image connector
types and installed Vision APIs still require verification after the operator's
agreed access time. No ready native helper binary is claimed by this contract.
