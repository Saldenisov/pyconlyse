SuperVision Telemetry: native XP assembly, 29 October 2026
=======================================================

This directory preserves the exact files assembled and saved through LabVIEW
2012 on SuperVision XP (10.20.30.2), together with read-only source audits.
The original C:\PILOTAGE_ELYSE_SUP\SUPERVISION.llb was not modified.

Current qualification
---------------------

Saved-source checks passed. The copied main retains all 43 archive members;
42 members are byte-identical to the original. Its original hardware logic,
typed terminals, front-panel identities, and directed signal connections remain
after contraction of the intended image/error identity taps. The entry contains
parallel camera/XML workers and an explicit queue-owner startup/shutdown flow.
All 14 primitive error outputs in the entry and all 12 in the XML worker are
wired. The XML derivative includes three diagnostic indicators and one native
polymorphic type-cache correction documented in xml_error_sinks/source_audit.json.

These are source findings. No new VI has been run since the original SuperVision
was stopped on 28 October at 23:05:14 Europe/Paris. Fresh-process loading,
actual camera frames, synchronization observations, receiver admission, web
freshness, and runtime shutdown remain unverified. The runtime package r20 is
staged separately; staging is not installation or activation.

Exact delivery mapping
----------------------

The artifacts directory contains byte-identical copies of the frozen XP
readbacks. Copying an artifact does not rewrite its binary resources.

* artifacts/Supervision Telemetry.vi ->
  C:\SUPERVISION_TELEMETRY_20261028\Supervision Telemetry.vi
* artifacts/SUPERVISION.llb ->
  C:\SUPERVISION_TELEMETRY_20261028\SUPERVISION.llb
* artifacts/ACQ_SharedState_Transport_Auto.vi ->
  C:\SUP_Telemetry_Helpers_88fd4200\sync_lifecycle\ACQ_SharedState_Transport_Auto.vi

The remaining ten helper VI files retain the bytes recorded in the historical
individual_helpers packet at commit 88fd4200. The XML artifact above is an
explicit override of that packet's f24df3 reference; the reference packet and
its historical receipts remain unchanged. Preserve those XP directories: the
saved relative callee links depend on them. This directory alone is not a
self-contained runnable installation.

The entry has RunOnOpen=1. Opening it executes the copied SuperVision logic,
including the original camera and synchronization initialization. Do not open
the artifact merely to inspect it. Its stopped precursor remains on XP as
START_Supervision_Telemetry_Camera_NATIVE_HELPERS_UNCOMPILED.vi.

Telemetry path
--------------

Camera copies are queued after IMAQ Grab/FrameCount and before the original
image mutation. Six setup observations bind actual original channels to one
run stamp. A periodic tap observes the existing C10-11 NI6602 software control;
it does not create or interrogate a second NI task. Observed settings do not
establish a physical waveform or successful hardware-write acknowledgement.

The XML and camera workers send to 127.0.0.1:8766 and 127.0.0.1:8768 on the
SuperVision computer. The passive Python orchestrator forwards validated,
authenticated telemetry to Everest 10.20.30.202:8767 and its Tango Device Server.
Loopback is intentional; the VI payload is not the authenticated federation
protocol accepted by Everest. Existing Acquisition telemetry is independent
and was stale at the last readiness check.

The wrapper joins the native branches before releasing queue references.
No hard shutdown deadline was demonstrated. Bounded TCP operations alone do
not prove a bounded worker join. Stop enqueue errors/timeouts are diagnostic;
no automatic recovery policy has been added.

Evidence
--------

revision624/ records the copied main and preservation audit. entrypoint/
records the final entry, queue/error flow, and the XP LabVIEW 2012 executable
readback identity (PE32/I386, version 12.0.1f2). xml_error_sinks/ records the
native XML derivative. Their text-only manifests retain the auditor's own
scope; the parent artifact inventory separately records the copied binaries.
LabVIEW.exe is not distributed in this repository.

release_manifest.json binds the artifacts, receipt manifests, helper closure,
XP target paths, and pending runtime status. It is an inventory, not an
automatic installer, launch authorization, or claim of live data delivery.
