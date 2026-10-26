SuperVision native synchronization and camera: observed rollout
===============================================================

Two independent card owners now run under the SuperVision Python orchestrator
on ``10.20.30.2``. The NI6602 initialization returned for all eight configured
and started tasks; NI1409 returned changing raw U8 frames. The same existing
Everest Tango Device Server receives the SuperVision sidecar while preserving
all 27 Acquisition banks. These observations establish software startup and
image transport. They do not establish external clock frequency, electrical
pulse timing, optical alignment, or presence of a laser spot.

Source and ownership transition
-------------------------------

The user explicitly authorized the SuperVision takeover before 18:00. Its
normal STOP froze the front-panel clock at 17:30:11 Europe/Paris. The main VI
and then the local LabVIEW application were closed normally. Acquisition VI,
Acquisition NI owners, General, water, Chroma and HT were not controlled by
this rollout.

The read-only canonical folder backup contains 58 source/dependency files,
2,973,581 bytes. The main, NI6602 initializer and timing writer embedded in
``C:\PILOTAGE_ELYSE_SUP\SUPERVISION.llb`` match the pinned original VI bytes.
``ELYSE_SUPERVISION_CANONICAL_SOURCE_AUDIT_2026-10-26.rst`` records the hashes,
saved project dependency-path ambiguity and limits of that comparison.

The direct SuperVision front-panel values matched the original initializer.
The conflicting Acquisition mirror was not used as a takeover profile.
``initial_sync_values_us`` was omitted. The source counter delay/width pairs
were retained, with InitialDelay=0, PFI10 rising start trigger, PFI11 rising
external timebase, retriggering, low idle and one finite sample. The factor
20 ticks per nominal microsecond is a source conversion, not a frequency
measurement.

The first native run used r17. NI6602 held eight tasks and NI1409 held one
interface plus one session. A normal local Deinitialize completed; the signed
API returned ``IDLE``, resource count 0, no retained local card endpoints and
no unreleased ownership marker. No blanket driver reset or marker deletion
was used. Successful close/join is a software cleanup observation, not a
physical output-off acknowledgement or a machine-wide ownership certificate.

The final SuperVision installation is
``C:\ELYSE_Orchestrator_Supervision_r18``. Launch its ``START.lnk``;
the local interface retains Initialize, Deinitialize and Stop server. The
three-button interface remains the only initialization path. The native
sampling logic is unchanged from the first run; r18 also corrects the GUI
delivery status that had displayed DISABLED despite valid ACKs.

Final source build identity:
``8b7f4562653ba220ac973f48a487485862cff028ff4b787dac20bc3a66a008b5``.
Observed session:
``0a357d810e4d452489eaa8d18a1fdfdf``.

Observed final state
---------------------

At 17:06:51.890053--17:07:02.206312 UTC (18:06--18:07 Europe/Paris),
ten bounded observations found:

* Runtime RUNNING throughout; both card owners READY; no reported NI or
  publisher errors and no owner-generation change.
* NI6602 child PID 4624: counters 0--7 reported started.
* NI1409 child PID 4044: raw 768x576 U8 frames, channel 2; the source white
  and black references are 0.9 V and 0.1 V.
* Tango video available in 10/10 observations; frame sequence 1629 to 1669.
* All 27 Acquisition banks current and all their source sequences advancing.
* The separate, nonblocking signed raw-image API returned an available image
  in 8/10 observations. Two reads returned unavailable/VIDEO_NOT_CURRENT;
  the runtime and Tango stream remained current. This interface may omit a
  contended RAM read and does not guarantee every captured frame.

The earlier independently saved frames had different byte hashes and pixel
ranges 0--23 out of 255. The image was visually almost dark. Camera capture
and transport are confirmed; a visible laser spot is not confirmed. No laser
shutter, motor, mirror, General or HT command was issued to create an optical
signal. The raw image precedes the legacy rotate/interlace/BCG/profile chain;
calibrated centroid and beam profiles are not claimed.

Receiver and web
-----------------

The existing ``elyse/acquisition/telemetry`` DS now uses explicit
``supervision_migration_config_file`` and an empty ``federation_config_file``.
It accepts the unchanged Acquisition legacy27 stream and the independently
authenticated SuperVision sidecar on the same port 8767. Public bank authority
remains Acquisition; no mixed-source replacement of C1011/C12 occurs.
SuperVision commands are disabled in this migration mode. Its owner state
and video are read through the same DS. Acquisition command policy is unchanged.

The first DS restart exposed a real initialization-order defect: mode flags
were read before Tango loaded device properties. Reading them after the base
initializer corrected startup. Regression tests simulate delayed property
hydration for migration, full federation and default modes. The initial
verification failure and both receiver restarts remain in the deployment
receipts; their short receiver gaps are not presented as continuous recording.

Pyconlyse displays the current raw image under ``/elyse`` -> ``Caméra NI1409``.
The read-only browser path is fixed GET
``/api/elyse/acquisition/telemetry/video`` -> the existing DS ``video_json``;
the browser does not contact XP or NI. The viewer polls at most once per
second, tracks identity/age and removes unavailable/stale pixels. The normal
27-bank web endpoint remained FRESH after activation.

The live main checkout contained substantial pre-existing web changes. Only
camera-specific additions were ported; original files and the entire former
build are preserved. ``deployment/ELYSE_SUPERVISION_LIVE_WEB_2026-10-26.patch``
records that additive delta against its actual saved baseline, rather than
committing unrelated dirty changes as part of this rollout.

Evidence and validation
------------------------

Durable operational artifacts, source packages, installation results, source
hashes, raw image examples, receiver rollback data and web activation receipts
are under ``F:\ELYSE_Orchestrators\supervision_takeover_20261026``. Keys are
installation-local and excluded from Git. The old web build is preserved at
``C:\dev\pyconlyse\web\frontend\build.rollback-20261026T170037Z``.

The final selected backend/transport/packaging regression run passed 166 tests
on Python 3.12 with external networking denied. Actual CPython 3.4.4 x86 ran
60 selected tests: 57 passed and 3 modern-only tests skipped. The live web
port passed 116 React tests and 24 backend tests; its production build compiled.
RAM tests and live observations are separate evidence: only the explicit
native startup exercised the installed XP drivers.

The SuperVision VI passive raw-image exporter remains unauthored/unqualified.
The verified current SuperVision path is native Python ownership. Acquisition
continues to forward its running VI through its separate r16 orchestrator.
