SuperVision VI telemetry exporter: source-grounded authoring plan
=================================================================

Result and permitted boundary
------------------------------

The original SuperVision front panel contains all 27 names already read by
the Acquisition shared-state collector. The same native collector, latest-only
queue and XML transport can therefore be retained byte-for-byte as reference
helpers for a SuperVision producer. The required counter part is fields
16--31 of the 33-DBL ``C10-11 NI6602`` control; ``C12NI1409`` is a String.
Neither control is an independent hardware readback. Raw camera pixels need a
separate owned-byte export from the existing camera loop.

No new native exporter VI has been authored, compiled or executed by this
work. Existing builders assemble copies of previously native-authored VIs;
they are not an offline LabVIEW diagram compiler. The new Python typed ingress
does not, by itself, create a working LabVIEW producer.

Before 18:00 Europe/Paris on 2026-10-26, only offline inspection and preparation
are authorized. The earliest authorized SuperVision VI stop/rework window is
18:00 CET, 17:00 UTC, that day. This document and preparation script perform
no scheduled or automatic live action. No running VI, card, camera, clock,
client command or unrelated main LabVIEW/TRANCON work is touched. A later
native editing session must remain scoped to copied SuperVision sources and
their new telemetry helpers; originals and current property backups are kept.

Pinned source evidence
-----------------------

Root receipt:
``C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\parser_release_20261003\00.json``.
Its original ``0_SUP_ELYSE.vi`` SHA256 is
``B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B``.
The raw BD, FP and metadata XML hashes are, respectively:

* ``F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7``
* ``E221D536F9D3C69D6492487C2906915E1F0F07AD00E1952370E3C5535849FF06``
* ``C00E57C1E82FB2E8C00529F5B0856232622569BA688648DE9A169995284B8921``

The original NI6602 initializer is receipt ``01.json``, hash
``CE8BCA30E727C9B8C1EE9681263FBCE1D60247C2DBECDD0B73A37A385C88104F``.
The original writer is receipt ``03.json``, hash
``81F29F2C56C22DB6FB37CC8893D360362B2610B6488F9D95C8AFCE0CB21E0DCE``.
The separately modified ``Supervision/extracted`` helper is not the original
initializer and must not silently replace this evidence.

``tools/prepare_supervision_vi_export.py`` rechecks original VI/XML hashes,
including the root00, initializer01 and writer03 source receipts and each
receipt's original VI bytes plus all three XML resources. It checks
all 27 front-panel control identities, counter/String types and the critical
wires below. With ``--output NEW_DIRECTORY`` it stages only three existing
native passive reference helpers and ``export_plan.json``. The copied
Transport_Auto reference contains TCP network operations; it is copied and
hashed, never executed by this tool. It refuses an
existing output directory. No hardware main, hardware launcher or synthetic
fixture is copied. Its result explicitly retains
``new_native_vi_authored=false``, ``native_compile_verified=false`` and
``deployable=false``.

The preparation tool contains no network-protocol code and opens no LabVIEW or
NI API. Its filesystem paths are trusted caller inputs; UNC paths and mapped
drives can cause Windows filesystem network traffic. The reported offline
checks used the stated local corpus paths. This is not a general guarantee
that arbitrary supplied filesystem paths cannot contact a file server.

Binding the later authoring copy to the actual source
-----------------------------------------------------

The cached original source and offline reference stage do not prove which VI
is currently loaded on SuperVision. ``export_plan.json`` therefore explicitly
states ``live_canonical_source_bound=false`` and
``authoring_workspace_bound=false``. Neither a matching VI title nor the
offline helper hashes satisfy that binding.

Only after the authorized 18:00 stop window, identify the exact live/canonical
SuperVision main path, project/application context and dependency locations.
Record any unsaved in-memory changes; a disk hash alone does not attest a
modified loaded diagram. Normally stop the scoped VI before copying or editing.
Copy that exact canonical main, project and complete dependency closure into
a new authoring directory, retaining the originals. Do not use Save All or
modify unrelated LabVIEW/TRANCON sources.

Before the first edit, create a workspace receipt containing the canonical
absolute main/project paths and SHA256 values, every dependency's original
path/hash, the copied workspace's absolute paths/hashes and the explicit
canonical-to-copy mapping. Recheck canonical bytes after copying. The main
must match ROOT_HASH above, or a new reviewed extraction receipt and source
audit must qualify the changed canonical source before these wire anchors
are used. A changed source must not be accepted by substituting a new hash
without reviewing its diagram/types/dependencies. The current offline tool
pins the old original and intentionally refuses a changed root.

Bind every later native edit, export/readback and compile receipt to that exact
authoring workspace path and its pre-edit source receipt. Final hashes identify
the actual edited copy and helper closure, not only a similarly named cached
VI. Until this canonical/workspace binding is complete, the offline stage is
reference evidence rather than a ready SuperVision deployment source.

The native reference folder is:
``C:\dev\ELYSE-ACQ-telemetry\2026-10-14\auto_verified_readback_20261014\ELYSE_ACQ_TELEMETRY_AUTO_20261017``.
Reference hashes:

* ``ACQ_SharedState_Collect_Local.vi``:
  ``A63BAAAB3EB8D60B37FD5EC624C8A27446F4D513FAAA4472E719F3331DB1B472``
* ``ACQ_SharedState_Queue_Latest.vi``:
  ``1FF9B3E0AAC58DBEA98EE9A2175EF70CBCCCB268D4604B3899B7DD16CC5D69F2``
* ``ACQ_SharedState_Transport_Auto.vi``:
  ``6DDE82167C284A73318E5E130F32703445D9626375F56425CCA5A5857D6C1A9F``

The collector uses generic VI Control Value:Get, not a driver or PSP read.
The validated earlier diagrams identify invoke method ``Ctrl Val.Get`` code
1052. Its required VI reference must refer to the actual copied SuperVision
main in the same project/application context. Merely opening a similarly named
stopped VI can read plausible saved values and is not an acceptable live-source
qualification. Never reuse ``START_Acquisition_Telemetry.vi`` on SuperVision:
that launcher calls the Acquisition hardware main.

Counter and descriptor integration points
------------------------------------------

``C10-11 NI6602`` is FP control UID30286, local parameter index170. Its source
type is 33 ordered DBL fields. Indices0--15 belong to Acquisition C10,
indices16--31 to SuperVision C11, and index32 is the requested selector.
Use the original numeric values without averaging, unit conversion or
inventing a completed driver operation. A selector other than the explicitly
observed -1 remains pending, including a fractional selector. A read control
value is classified as ``observed_labview_control_memory``.

Critical original wires, in terminal UID order:

* Diagram49696, wire54417: ``52990 -> 52020`` supplies the prior local cluster
  to shared-variable dynamic read51964.
* Diagram49696, wire57569: ``52027 -> 56484, 58818`` transfers the read cluster
  to local write56477 and the following bundle/update logic.
* Diagram70866, wire66465: ``61627 -> 59739, 70293, 70267`` transfers the
  Page Synchronisation bundle to locals and shared-variable write70253.
  This diagram is inside runtime event structure5909, not initialization.
* The native timing writer call67590 is in diagram55043. Delay input67626
  comes from54780 on wire57366; width67629 comes from68149 on wire57388.
  Task-reference output67620 is connected to53308 on wire56778.
* The actual local NI6602 initializer call66132 is in diagram23159, outside
  the main event loop. It starts its eight source tasks. Its source profile
  and initialDelay=0 behavior are documented separately in
  ``ELYSE_SUPERVISION_CARD_ADAPTERS_2026-10-26.rst``.

A passive export hook branches existing data/control observations. It does not
call the timing writer, request PulseDone, start/stop a task or add a DAQmx
read. A source main-loop observation sequence and source-running qualification
must distinguish fresh observations from reading a stopped VI's controls.
Telemetry errors remain in their own diagnostic path and must not gate or
clear the original SuperVision hardware error chain.

``C12NI1409`` is FP UID38202 with a String type. Its original contents can be
exported unchanged through the existing XML collector, subject to the current
4096-character String limit. The String does not establish a pixel format,
frame timestamp, image lifetime or acquisition success. An oversized or
uninterpretable String is unavailable with an explicit error; it is not
silently truncated, converted to pixels or replaced by a fabricated descriptor.

Raw camera integration points and memory ownership
---------------------------------------------------

The original NI1409 camera uses ``img0`` on SuperVision; NI6602 is ``Dev1``.
IMAQ Init18953, property15292 and Grab Setup18912 are in initialization
diagram12058. Original channel defaults are2, white0.9V and black0.1V. The
exporter must use the existing session/image and must not open another img0
session, change channel/reference values, call Grab Setup or issue a new grab.
Basler IMAQdx cam0/cam1 are outside this export scope.

Capture-generation tracking must cover every existing successful Grab Setup,
not only initial setup18912. Other original setup call/diagram pairs are
``36531/16577``, ``92441/92401``, ``38132/35649``, ``71781/71755`` and
``21387/21965``. Their existing matching Init calls are36570, 92484, 57265,
71884 and22472. These are observation-hook candidates on existing paths;
the exporter must not invoke them. Native authoring must retain the existing
error-success order before declaring a new capture generation.

The camera acquisition call is ``IMAQ Grab Acquire.vi`` UID15740 in diagram
20537 inside camera while5841. Existing wire19409 connects terminal15749 to
14771 of ``IMAQ Rotate`` UID14726. This is the candidate branch before the
legacy rotate/interlace/BCG/profile processing. The saved parser represents
these Vision terminals as Void, so their installed native connector/image
contract must be verified in LabVIEW before wiring a new helper. The wire
anchor is proved; an executable typed image connector is not yet qualified.

Frame Count property21773 has output21792. Wire15281 connects the grab error
output15743 to property error input21786. Wire19471 connects session references
``52862 -> 15797, 21780``. A camera observation may be exported only after a
successful existing grab and a new source frame observation; a new telemetry
heartbeat alone is insufficient.

IMAQ images are mutable reference-backed memory. Queueing the existing image
reference and converting it asynchronously can read the next grab or a later
processing result. Before the source changes that memory, the helper must
obtain an owned bounded byte copy or a separately owned image copy with proved
lifetime. It then queues only immutable bytes plus metadata. Copying/conversion
can cost time even without network I/O; the native non-hardware fixture must
measure that cost and confirm that original camera processing still advances.

The first typed format is U8, raw row-major, at most512KiB decoded pixels,
exactly ``width*height`` bytes with native row padding removed. A different
native image type/geometry is explicitly unavailable; no implicit rescaling,
downcast, display screenshot or BCG transformation is introduced. The web
image will therefore represent the declared raw pre-processing frame, not
the legacy processed display or an independently calibrated beam profile.

Two transports within the same SuperVision orchestrator
--------------------------------------------------------

The compatible metadata path remains:

::

    SuperVision main control observations
      -> native read-only collector -> capacity-one lossy queue
      -> native XML transport -> 127.0.0.1:8766
      -> SuperVision orchestrator (counter16part + opaque C12 String)

The existing transport uses four big-endian length bytes followed by
LabVIEW Variant XML, explicitly decoded as cp1252 on French XP. Maximum XML
size is262144 bytes. Empty-queue timeout is100ms; TCP timeout is1000ms per
operation, not an aggregate end-to-end guarantee. No TCP operation belongs
in the main VI/control/camera loop. Queue replacement is permitted and counted;
this is a latest-state stream, not a guarantee that every original update is
delivered. Sequential control reads are not an atomic inter-bank snapshot.

The new optional path uses the same orchestrator process, not another Python
telemetry server:

::

    existing camera observation -> owned raw bytes + capture identity
      -> independent capacity-one video queue -> native typed serializer
      -> 127.0.0.1:8768 -> SuperVision orchestrator
      -> authenticated owner telemetry -> Everest Tango Device Server -> web

``supervision_vi_telemetry.py`` defines the exact typed8768 parser. The wire is
u32 big-endian byte length, then strict UTF-8 JSON, maximum900KiB. Root fields
are exactly:

::

    schema_version: 1
    publication: "ELYSE_SUPERVISION_VI_OBSERVATION"
    source_session_id: <32 lower-case hex; source VI run identity>
    sequence: <positive integer, at most 2^53-1>
    source_running: true
    counter_part: null or <typed counter record>
    video_frame: null or <typed video record>

At least one component is non-null. The counter record fields are exactly
``values`` (16 finite numbers), ``source_age_seconds``, ``source`` equal to
``observed_labview_control_memory``, ``selector`` and ``pending_selector``.
``pending_selector=false`` requires selector=-1. The exported source marker
does not prove a successful hardware configuration.

The video record follows ``federation_wire.validate_video_frame`` with source
``labview_supervision_ni1409`` and an additional ``source_session_id`` matching
the enclosing source run. Required metadata includes its independently scoped
``capture_session_id``, positive frame sequence, geometry, channel, source age,
sample elapsed time and UTC observation text ending+00:00. Encoding is
``base64_raw_row_major``, pixel type ``U8``, processing
``raw_grab_before_legacy_interlace_bcg_profiles``; simulated and
hardware_acknowledged are false. The interpretation string remains
``software grab observation, not hardware frame counter``. The strict parser
is authoritative for all field names and bounds; native authoring must pin its
matching schema version rather than constructing an approximate JSON object.

A local reply uses the same length framing and reports
``acknowledged_on=xp_ram_not_everest``. Local acceptance proves only a bounded
RAM ingest; it is not evidence of Everest delivery, database durability or
physical state. Source sequence/session changes and rejected observations must
remain visible. Existing frame bytes may not be relabeled as a Python-native
grab merely to satisfy an older receiver's source-mode restriction.

LabVIEW2012 compatibility and remaining authoring work
------------------------------------------------------

The copied reference helpers are native LabVIEW2012 files; their existing
XML/queue/TCP operations were separately authored and read back in that version.
No proven offline tool in this repository creates and compiles the required
new SuperVision producer, lifecycle or typed raw-image serializer.
``stage_acq_auto_start_project.py`` explicitly stages a work-in-progress native
editing workspace, while ``validate_acq_autostart.py`` audits already authored
resources. Editing generated BD XML is not equivalent to compiling a VI.

After the permitted time, native authoring must resolve these concrete points:

1. Create a copied SuperVision source/project with a read-only producer and
   worker lifecycle in the same application context. Preserve original main,
   hardware helpers, routes and parameters. Qualify source-running state and
   normal telemetry stop independently from a hardware main launcher.
   Native-authored clones need dedicated SuperVision metadata/video/stop queue
   names, for example ``ELYSE_SUP_SHARED_STATE_LATEST_V1``,
   ``ELYSE_SUP_VIDEO_LATEST_V1`` and ``ELYSE_SUP_TELEMETRY_STOP_V1``. These names
   are proposed integration constants, not changes already made to the copied
   Acq references. Queue ownership/start-stop remains in the telemetry wrapper;
   the main producer never creates/replaces an owner or waits for a consumer.
2. First test the counter/String collector against a stopped copied front
   panel with distinctive synthetic values and individual read errors. Never
   run the actual hardware main merely to test framing or a VI reference.
3. Verify the installed Vision connector types, owned image conversion and
   buffer lifetime with a synthetic image. Do not grab a camera for this test.
   A new export buffer is telemetry-owned and must be disposed after the
   telemetry worker has stopped; it cannot outlive a borrowed source image.
4. Author and test strict JSON/base64 assembly in LabVIEW2012. Availability of
   a newer native JSON API is not assumed. Decimal formatting on French XP
   must emit a JSON decimal point independently of locale; NaN, infinities,
   malformed base64, invalid UTF-8 and inconsistent byte counts are rejected.
   Use fixtures that round-trip DBL values and non-ASCII metadata explicitly.
5. Preserve bounded lossy queues and keep all socket waits in workers.
   Disconnect/timeout must affect telemetry diagnostics, not hardware error
   propagation, clock tasks or the original image-processing chain.
6. Export/read back the newly saved VIs, pin bytes plus BD/FP/type resources,
   and audit that no unintended write, NI initialization, reset, System Exec
   or hardware launcher has entered the telemetry helpers.

Freshness and activation
-------------------------

Source-run identity belongs to the VI producer lifecycle, not the Python
orchestrator boot or a TCP connection. A new SuperVision run gets a new source
session. Camera capture identity changes separately after Grab Setup,
reacquisition or channel generation; new software frame sequence is assigned
only to a newly copied observation. Repeated XML controls, video-only packets
and socket reconnects must not refresh other components' ages. Repeating an
old frame identity must preserve the previous image age.

The owner wire may retain optional ``source_identity`` metadata with
``source=labview_supervision_typed_local``, the last typed VI-run session and
its observation sequence. This identifies the last typed side-channel
observation, including a counter-only message. It does not atomically attribute
separately received legacy XML counter/C12 controls to that VI epoch, and an
XML heartbeat alone does not establish a main-run identity.

Producer age, native copy/serialization duration, receiver elapsed time and
subsequent queue age remain explicit. Python receipt UTC is not a hardware
exposure timestamp. A shared monotonic clock origin between LabVIEW Tick Count
and Python is not assumed without qualification. Reading a stopped VI's saved
controls or replaying a queued old frame cannot establish current machinery.

During preparation, Acquisition continues forwarding the existing27-bank
``legacy_27`` packet, and SuperVision outbound federation stays disabled.
Installing a new receiver or enabling a half-populated federated mode must not
discard current SuperVision fields already present in the Acquisition stream.
Activation requires both selected owner sources, distinct authenticated host
keys, independent age/provenance checks, matched Device Server/web schema and
a saved coordinated rollback selection. Raw-image display can be qualified
with software fixtures first; a real web camera claim requires the actual
native VI producer and fresh frames end-to-end.

Offline verification performed
-------------------------------

The plan builder passed original root/initializer/writer VI/XML hashes, all27 FP identities,
33-DBL/String types and the listed critical wire anchors. Five tests passed
under Python3.12 with external networking denied: exact control catalog,
changed/ambiguous source rejection, source audit limitations and staging only
the three byte-identical native references. Changed helper VI bytes, malformed
helper receipts, changed XML receipt hashes and changed XML bytes are rejected.
Tests execute no LabVIEW, card,
camera or network request. The modern preparation tool is not part of the
Python3.4 native runtime and is not a native LabVIEW compilation test.
