Everest camera and centroid handoff, 2026-10-29
=============================================

Deployment boundary
-------------------

Everest now runs the revised existing Tango Device Server and web backend.
The DS remains the one receiver for Acquisition's27 banks and the independent
SuperVision camera stream. The camera listener belongs to that same DS process;
there is no new standalone telemetry server. Web fanout, image analysis and
numeric PostgreSQL writing have separate workers. No camera pixels enter the
Acquisition PostgreSQL archive. The existing archive policy remains
``metadata_only_no_pixels``.

The original SuperVision on10.20.30.2 was left running. No XP files or VI were
changed by this deployment. Its present original VI does not emit images to
the new listener. Empty camera status is expected until the prepared source
package and VI copy are updated. Actual XP-to-Everest25Hz operation is therefore
not qualified. This is a prepared/deployed Everest path, not a live-frame claim.

Prepared source path
--------------------

The existing typed VI ingress can now stage every accepted unique image into
an independent bounded FIFO, with decoding, lossless compression and persistent
authenticated transfer outside publisher/NI locks. It preserves actual source,
capture, channel, sequence and timestamps. ``SOURCE_CAMERA_STREAM.rst`` documents
the explicit optional startup block. Default r21 configuration is unchanged.
The current native Python-owned camera path is preserved; its independent25Hz
hook has not been implemented or qualified by this VI-source change.

The native camera acquisition loop has a30ms wait. The added observer currently
has a1000ms ImageToArray/copy gate, capacity1 latest-only queue and sampled Python
owner publication. The new independent typed-source path removes the owner
publication bottleneck. Tomorrow's VI-copy edit must still remove the observer's
1000ms gate and replace its latest-only queue. Network transfer must run in a
separate consumer loop; acquisition must not wait for a slow socket or SQL.
No receiver can reconstruct frames that the VI never exported.

Full and half source admission are explicit: ``every_n=1`` or``every_n=2``.
Intentional skipping, overflow, replay/duplicate rejection and transport ACKs
have different counters. Browser25/12.5Hz display choice changes rendering,
not NI acquisition or source transfer policy. No automatic rate mutation occurs.

Measured scale and limits
-------------------------

One768x576 U8 image contains442,368 bytes. At25Hz raw payload is11.0592 MB/s
(88.4736 Mbit/s), before protocol overhead. At12.5Hz it is44.2368 Mbit/s.
Lossless compression ratio depends on actual images and cannot be inferred
from a dark preview or a synthetic entropy fixture.

Synthetic125-frame full-size centroid analysis on Everest took10.79ms mean,
13.75ms p95 and15.80ms maximum per image; observe() performed no SQL calls.
The worst-case two-channel50Hz aggregate transfer test ACKed250/250 but took
6.047s for approximately5s of production and queued up to44 images. The explicit
half-rate test ACKed126 admitted frames, intentionally skipped124, rejected0,
finished in5.000s and queued at most2. These are loopback/software measurements,
not XP CPU, physical exposure timing or LAN throughput qualification.

NI1409's video multiplexer routes one selected input to one ADC. The present
native code has one img0 session. It stops/closes/reopens acquisition and waits
500ms when changing source. Thus two continuously simultaneous25Hz exposures
are not available through this implementation. Even ideal alternating capture
shares aggregate cadence; actual switching/resynchronization can reduce it.

NI documentation, video multiplexer and hardware diagram, pages3-2/3-3:
https://download.ni.com/support/manuals/322811b.pdf

Native labels include Translateur1, Translateur2, LASER1 and MUX/LASER2. Only
raw channel2 to LASER1 is independently consistent in the saved front-panel
and block-diagram evidence. Other physical label/channel bindings require
checking on XP. The UI consequently labels raw channels and never duplicates
one frame under two physical camera names or switches the NI input itself.

Web and numeric persistence
---------------------------

``Caméra NI1409`` opens Centroïde, Profils X Y, Diag, WCM and Beam profile.
Diag retains three independent subtab groups: laser/translators, Faraday and
slit. Two views retain separate last images and explicit source ages. A stale
view keeps its last canvas but clears current centroid/offset validity.

``Enregistrer le centre`` below the image freezes the server-computed centroid
of that actual recently displayed frame, not browser-supplied coordinates.
Yellow cross and tolerance circle show the latest committed reference. Cyan
dot shows the current centroid, with offset and in-circle state. Reference
history is append-only; revision conflict refuses an older browser overwrite.

Separate PostgreSQL tables on the existing F: database are sup_camera_state,
sup_camera_references, sup_camera_modes and sup_camera_observations. They store
numeric positions, geometry, identities, quality and timestamps; no image blobs,
base64 or pixel/profile arrays. Queue overflow and DB failure are visible and
cannot block the live image worker. The numeric RAM queue is not crash-durable.

The new estimator uses the displayed raw pixels, edge-background subtraction
and a noise floor, with no time averaging. Native SuperVision's estimator uses
rotation/BCG/interlace, thresholding and particle filtering. Their coordinate
spaces and numerical centroids must not be treated as identical. ROI/SOI and
ellipse fitting are deferred as requested.

Automatic correction boundary
-----------------------------

Auto/Manual is a durable per-camera preference. The correction planner and
fake-actuator-tested controller support bounded moves, stale/replay rejection,
identity/revision fencing and uncertain-result refusal. No physical actuator
adapter is enabled on Everest. Motor commands require the actual controller,
axis mapping, sign and pixel-to-step matrix for the displayed coordinate space.
Native selector1 maps motors3/4 and selector2/default maps1/2; camera names alone
do not establish a valid mapping. The old unbounded autotune loop is not copied.

Tomorrow's completion checks
---------------------------

1. Preserve original VI and running configuration; update only the telemetry
   copy/source package when authorized.
2. Add native acquisition-to-FIFO export without1000ms gating and a separate
   network consumer. Keep accelerator synchronization logic unchanged.
3. Compare captured, enqueued, intentionally skipped, ACKed and rejected counts,
   source cadence, oldest queue age, CPU and actual received Mbit/s at25Hz.
   Use explicit12.5Hz source policy if the sustained path cannot keep up.
4. Verify each physical camera/channel and switching overhead; do not infer
   simultaneous capture from two retained web images.
5. With a real beam, save a centre, reload the page, verify the persisted cross
   and radius, current offsets, circle membership and scalar observation rows.
6. Qualify Picomotor route/sign/matrix and bounded manual moves before enabling
   real continuous correction. Auto preference alone is not motor motion.

Validation evidence
-------------------

Modern backend/transport suite:153 PASS. Web suites:193 PASS across7 suites.
Prepared XP source/runtime regression
on CPython3.4.4x86:74 PASS and3 modern-only SKIP. PostgreSQL fixtures verified
latest-reference revision, stale-revision refusal, mode persistence and absence
of image columns in an isolated schema; that fixture schema was removed and
production fixture rows remained0. See postgres_diagnostics_receipt.json,
everest_final_receipt.json and the synthetic benchmark receipts in this folder.
