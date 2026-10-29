Native XP main revision624: source audit and copy handoff
======================================================

The audit covers the main assembled through LabVIEW 2012 on XP and saved as
revision624. It establishes the saved source connections against the exact
untouched revision613 archive. Hardware execution, fresh-process opening,
transport operation, and the separately authored startup wrapper remain
unqualified. No VI was executed during this audit.

``source_audit.json`` contains portable endpoint and preservation evidence.
``manifest.json`` pins that receipt and the existing native archive. This proof
directory contains text receipts; the binary source remains the frozen
checkpoint below.

Native archive identity
----------------------

The checkpoint is::

    C:\dev\sup_vi_camera_20261027\individual_helpers_20261028\review_88fd4200\xp_main_checkpoint_20261029_0220\SUPERVISION.llb

Its SHA256 is
``87c73e3e3a1634461f27f1cafbbcb0f476d2cbc2663cf485079342a24f3d05c9``
(2,245,507 bytes). Its main member, ``0_SUP_ELYSE.vi``, has SHA256
``0fb75ecf887677adcf62506cfd5224dc29a786e1d315e8520c8904377b29bea0``
(1,154,839 bytes). The native source header is 12.0.0 release build4.

The untouched XP original is ``C:\PILOTAGE_ELYSE_SUP\SUPERVISION.llb``.
Its independently supplied archive copy has SHA256
``d427b2ba8544e4ffd6868f4e2ef74762363c7c713e30b2ff151e5f5ad168bcf4``
(2,232,683 bytes). The original member hash is
``b7b79636e77d7756a5896edd132f7e3b24301394a04893d9a73938073c210a7b``.
The original archive was re-read after the audit and retained the same hash.

Source result
-------------

* All 43 archive member names remain. Only ``0_SUP_ELYSE.vi`` changed;
  the other 42 members are byte-identical.
* Of 4,301 original directed source edges, 4,292 remain exact. The remaining
  nine pass through the intended image/error identity ports of the six
  SetupObserve calls and one FrameTap call. No original edge is missing after
  those identity substitutions.
* All 11,404 original typed terminals retain their DCO class, resolved type,
  ``paramIdx``, and ``parmIndex``. The original primitive, call, constant,
  local-reference, and structure signatures checked by the audit are unchanged.
  Original front-panel label/type identities and ordinal prefix are preserved.
* All six SetupObserve calls receive the actual channel argument of their
  respective original IMAQ Setup and the shared ``__Telemetry_RunStamp``.
  Error splices preserve every original consumer, including both consumers at
  original Setup21387. No direct error bypass remains.
* FrameTap260614 receives Grab image15749, FrameCount21792, and the error after
  FrameCount21789. Its image/error outputs feed Rotate14771/14755. Both original
  bypass edges are absent. This preserves the inline barrier before the original
  mutable-image writer; a parallel image-reference branch would not provide it.
* SyncTap285124 is inside periodic While5846 and outside Sequence9424.
  Native ``ce VI`` reference291529 feeds connector5. Connector0 feeds the private
  indicator with true label ``__Telemetry_SyncError``; its inherited caption is
  ``sortie d'erreur``.
* Begin73228 is in outer Sequence988 frame0 and writes the single RunStamp.
  End306228 is in frame4 and consumes that same RunStamp. Camera producer
  execution belongs to outer frame2, which must finish before frame4 begins.

These are static source findings. They do not demonstrate FGV persistence,
copy frequency, queue behavior, physical NI writes, or observed camera pixels.
Compiled caches and layout are outside the semantic comparison. Parser warnings
for DFDS variants and archive CONP/CPC2 sections are retained in the local audit
log; the source heaps, type pool, and link tables used here were decoded.

Native-copy handoff
-------------------

1. Keep the original ``C:\PILOTAGE_ELYSE_SUP`` tree untouched. Retain the frozen
   checkpoint and verify its SHA256 before any later byte-identical handoff.
2. Preserve the copied-main directory and helper packet name
   ``SUP_Telemetry_Helpers_88fd4200`` used in the saved native links. Main caller
   links include ``camera`` and ``sync_lifecycle\counter_only_candidate``.
   Any relocation requires native link review and a new saved-source receipt.
3. Complete the separate startup-wrapper review. Main has zero camera or sync
   transport-worker calls. Wrapper review must cover both queue-owner lifetimes,
   startup flushing, parallel workers, producer completion, End, stop signaling,
   actual worker return, and reference release. A timeout budget alone does not
   establish a bounded join.
4. Main retains inherited ``RunOnOpen=1`` and ``DefaultErrorHandling=1``.
   Obtain explicit confirmation before cold opening or launching it. The
   canceled Properties edit did not change these flags. The audited source
   reports ``BadSignal=BadNode=BadSubVI=BadCompile=HasInsaneItems=0``.
5. Verify actual XP helper bytes against the existing individual-helper packet
   before runtime approval. Saved link names and function signatures establish
   caller structure; this main-only checkpoint does not independently pin the
   helper files currently present on XP.

No automatic launcher, deployment action, VI resource writer, or execution
command is supplied by this receipt package. Git staging and commit remain
pending root review.
