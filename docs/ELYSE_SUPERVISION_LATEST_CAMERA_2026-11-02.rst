SuperVision live images: latest frame per channel
================================================

Live delivery policy
--------------------

The operator requested newest-first delivery after variable 12--24 frames/s
was measured. A stack alone would send obsolete frames after the producer
becomes idle and could regress source frame IDs. The new ``latest`` policy
instead replaces waiting images and never drains discarded older images.
It reduces queue latency; it does not increase the camera's capture rate.

The existing site configuration selects ``camera_stream.delivery_policy``
``latest``. Omitting this optional field retains the original FIFO behavior
for existing benchmarks and other configurations. The signed binary protocol,
compression setting, source/capture/channel IDs and source timestamps remain
unchanged. Images remain outside the Acquisition telemetry database.

The live path is::

    IMAQ Grab -> owned U8 copy -> native lossy queue, capacity 1
        -> separate VI transport loop -> Python latest staging per channel
        -> latest waiting image per channel + immutable in-flight frame
        -> existing persistent authenticated TCP -> Everest RAM latest view
        -> web latest view

Python staging and the sender each retain one waiting image per admitted
channel, up to the existing configured channel bound. The sender additionally
pins one in-flight image until a matching signed ACK arrives. The existing
total byte bound includes this in-flight image. Replacements are counted as
``replaced_pending`` separately from rejected-new frames and network errors.
Transport IDs are assigned when a frame becomes in flight, so dropping waiting
source images does not create transport sequence gaps. A lost ACK retries the
same immutable image before the current latest waiting image is sent.

Producer locks protect bounded memory operations only. Compression, sockets
and ACK waiting remain outside those locks and run on separate workers. An
empty worker waits on its event; a successful send adds no fixed pause.

Native VI restoration
---------------------

Inspection of the installed wrapper found camera queue capacity already 1
at constant UID 2404. Its installed producer still used ordinary Enqueue
Element with timeout 0, rejecting a new frame when that queue was full.
The update restores the existing native 12.0 Lossy Enqueue helper::

    legacy/labview/supervision_telemetry/individual_helpers/camera/observer_v3/SUP_Camera_Queue_Latest.vi

SHA256::

    bef72a8c0a4b7cc269e1694668464ba5c75164519687fee3b428552e7bd49bb7

The read-only graph comparison verified the same connector/front-panel ABI,
callee links and structure. The only behavioral restoration is the producer's
128 -> 1 Obtain Queue bound and ordinary -> Lossy Enqueue operation, with
the corresponding native terminal/wire mapping. The existing named queue is
created first by the unchanged capacity-1 wrapper. Python did not serialize
or edit any VI binary. Original SuperVision VI, synchronization logic, the
camera acquisition/processing loop and its error-recovery waits were not edited.

Deployment and tests
--------------------

``tools/build_supervision_camera_latest.py`` builds a hash-pinned package.
``tools/install_supervision_camera_latest.pyw`` requires the cold existing
Python server and absent LabVIEW process, verifies source hashes, creates local
backups and changes only ``camera_stream.delivery_policy`` in configuration.
It preserves ownership markers, commissioning gates and authentication files.
The original wrapper hash is checked before and after installation.

Actual Python 3.4.4 x86: 88 distinct cases checked, 85 passed and 3 skipped.
Python 3.12: all 88 cases passed. After the initial 87-case suite, the seven-case
native-owner subset was rerun on both interpreters with the added latest-mode
card-process regression. Coverage includes a 1000-frame burst,
per-channel replacement, bounded bytes including in-flight data, lost ACKs,
contiguous transport IDs after replacements, a deliberately stalled receiver,
existing FIFO behavior, VI/native source wiring and configuration preservation.
Payload Python modules and installer also compiled under Python 3.4.

Installed on SuperVision XP at 21:02 Paris. Backup::

    C:\SV_READY_20261030\latest_camera_backup_20261102T200215Z

RDP attempts to operate normal Stop did not stop the old run. Input/capture
problems prevent attributing this observation to a VI logic failure. The run was
aborted through LabVIEW at approximately 20:47 Paris; after Quit/close attempts did not exit,
the stopped LabVIEW process was ended through XP Task Manager. No new Python
Initialize or General/power command was issued. The cold Python server was
closed with its normal Stop server button. The updated server then opened in
IDLE/resources 0 and the unchanged telemetry wrapper started in LabVIEW 2012
at 21:04:44.991 Paris.

At 21:07:55 Paris, the running server reported ``delivery_policy=latest``,
17 replaced waiting images, zero rejected-new images, zero staging errors,
one in-flight image and no waiting staging descriptor. The Everest camera
was available with age 0.135 s. All 16 observed synchronization control values
matched the pre-stop baseline; this checks VI control memory, not physical
timing pulses. All 27 Acquisition banks were fresh and PostgreSQL was RUNNING
with no archive error. Sustained 25 Hz remains unqualified.

The subsequent 61.156 s web/API observation accepted 16.0573 frames/s and
transferred 56.8929 Mbit/s. All 13 samples had an available image, fresh unchanged
synchronization memory and 27 fresh Acquisition banks. All bank sequences
advanced; stale-frame and ingress-error counters did not increase. Web metadata
age ranged from 0.159 to 0.760 s; its metadata cache is sampled once per second,
separately from the image broker. At 21:12:58 Paris, 228 waiting Python images
had been replaced, with zero rejected-new images, zero staging errors, an empty
staging queue, one in-flight image and no sender error. The direct Everest image
age was 0.276 s. PostgreSQL remained RUNNING with 62616 commits and no error.

Local installation and measurement receipts are in::

    C:\dev\SuperVision_Telemetry\latest_20261102

The native VI client still opens TCP per observation. Its persistent-client
refactoring remains separate work; this update does not claim to remove that
connection churn or guarantee delivery of every captured image.
