SuperVision startup and camera diagnosis: 2 November 2026
=======================================================

Scope and installed state
-------------------------

The operator confirmed that accelerator equipment was off and authorized normal
SuperVision VI stops/restarts and changes to the telemetry copy on 10.20.30.2.
Acquisition VI and the continuous archive were kept running. No Python Initialize,
General, water, heating, PREMA, Focales or HT command was issued.

The startup fix is installed in ``C:\SV_READY_20261030``. The only configuration
change is ``vi_passive_shadow: true -> false``; ownership markers and native-owner
guards remain intact. ``Supervision Server`` starts the same orchestrator alone;
``Supervision Telemetry`` first ensures that orchestrator and then opens the
existing LabVIEW wrapper. Neither launcher invokes Python Initialize.

The running orchestrator is IDLE/NATIVE_CAPABLE with zero local NI resources while
VI owns the camera and synchronization. Three GUI actions remain Initialize,
Deinitialize and Stop server. Native Initialize requires VI to release first.
The exact startup package is preserved in ``tools/supervision_startup_fix_20261102``.
Its hash-pinned payloads retain byte-for-byte line endings through .gitattributes.

Installed VI changes
--------------------

Only the telemetry copy was edited in native LabVIEW 2012 x86 on XP::

    C:\SUPERVISION_TELEMETRY_20261028\SUPERVISION.llb\0_SUP_ELYSE.vi

The original ``C:\PILOTAGE_ELYSE_SUP\SUPERVISION.llb`` was not edited.
The saved copy is preserved in
``legacy/labview/supervision_telemetry/camera_cadence_20261102``.

* Camera While 5841, sequence 18881, frame 9: unconditional Wait constant 25451
  changed from 30 to 0 ms; Wait primitive 26427 and its existing wiring remain.
* Allow debugging changed from enabled to disabled. Priority, execution system,
  non-reentrant behavior and synchronization values were preserved.
* The 500 ms camera error/reconfiguration wait in frame 8 was retained. It is not
  an unconditional per-frame delay. The separate channel reconfiguration
  handshake was also retained.

The read-only lvkit export compares 38601 diagram UID objects before and after.
The functional constant change is30->0; other diagram differences concern
compiled clump numbers, object flags, window bounds and wire drawing geometry.
No node or terminal identity was added or removed. Front-panel saved appearance
and graph display state also changed during native saves; binary identity is
therefore not claimed. The full comparison is stored with the local evidence.

Measured pipeline
-----------------

The actual path is::

    IMAQ Grab -> driver Frame Count -> FrameTap -> owned U8 FIFO
       |                                           |
       v                                           v
    legacy processing/display                separate transport loop
       |                                  TCP length+payload / local ACK
       +-> next Grab                               |
                                                   v
    XP typed ingress -> independent staging -> FIFO -> persistent sender
                                                   |
                                                   v
    Everest camera ingress/RAM -> Tango -> web latest-frame broker

The transport helper already has its own loop. Its100ms dequeue timeout waits
only when FIFO is empty; a queued frame has no fixed transport sleep. It writes
length and payload together. It still opens/closes local TCP per frame; this
has not been replaced with a persistent VI connection in this change.

The camera While is in main sequence 988/frame 5902, independently of the 80 ms
event timeout. However, the next Grab still waits for legacy interlace, image
processing, profiles and display in the same sequential camera loop. Removing
the explicit pause does not isolate capture from that remaining work.

The driver Frame Count is a source identifier, not an independent count of
successful Grab calls. Its 25/s progression alone does not prove 25 exported fps.

========================= ============ ============= ==============
Condition                 Window       XP accepted/s Everest ACK/s
========================= ============ ============= ==============
Initial production        30.188s       9.1096        9.0433
Wait0, debugging disabled 60.391s       24.4904       24.3083
========================= ============ ============= ==============

The second run transferred 86.1865 Mbit/s of camera protocol data. Its FIFO grew
from 36 to 46 and included stale arrivals. A later 256-observation window fell to
16.139Hz upstream of Python, while FIFO was 3 and Everest image age was 0.182 s.
Sustained 25 Hz and delivery of every hardware frame are not established.

XP diagnostics use a bounded 256-sample deque and nonblocking diagnostic locks;
no pixels or disk writes are added. Representative ingress means were 2.0--2.2 ms
receive, 3.6--3.8 ms admission and 0.56--0.59 ms reply. Source copies took 0--1 ms and
arrived within 0--15.625 ms of their source timestamp. These observations locate
the slow/variable cadence before local Python admission, rather than a 100 ms
queue wait. Approximately 1--2% of observations were rejected by the existing
busy-owner admission guard; that guard was not bypassed.

Everest receiver optimization and approved rollout
--------------------------------------------------

A 20 s external nonblocking profile of the live DS collected 832 samples with 11
sampling errors. 346 samples ended inside recursive copying called from
``TelemetrySinkStore._commit_packet`` line 165, plus 25 at line 166. Before the
fix, every expanded bank copied the complete 27-bank envelope and immediately
replaced its packet with that bank. This repeated large recursive work 27 times
under the RAM lock and competed with image ingress for the Python GIL.

The fix shallow-copies validated scalar envelope fields and retains the existing
owned deep copies produced by snapshot expansion. Non-snapshot packet copying,
authentication, replay guards, age calculation, archive ordering and cooling
observation are unchanged. A regression test mutates both the caller's nested
bank payloads and returned snapshots and verifies isolation of all 27 banks,
receipt identifiers, staleness and duplicate ACK behavior.

An offline 14313-byte fixture benchmark, 90 receipts per version, gave median
64.938 ms before and 11.619 ms after: 5.589x faster. All 27 output banks were identical.
This is an offline CPU benchmark, not a measured production speedup.

The live module matched the pre-fix Git version, SHA256::

    45ae4a2e88143eda134ce39b2f56518f1462734e5a204a3e0d9d0e1ea0c06288

The operator explicitly approved applying the update. The guarded one-module
rollout ran from 18:07:49 UTC to verification at 18:08:05 UTC (19:08 Paris). The old
process 2696 exited normally; replacement 24600 resumed all 27 fresh banks and
PostgreSQL commits. No Acquisition VI stop or hardware command was performed.
Backup and deployment receipts are at::

    F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\sink_copy_20261102T180749Z

The installed module SHA256 is::

    a611c1872086112a0113123ae8bb1b30ee0dc5fdb1bcedab61eb89bc26e897fd

A 180.203 s run after the restart admitted 16.4648 frames/s on XP and accepted
16.4703 frames/s on Everest, transferring 58.3565 Mbit/s. The apparent small excess
reflects boundary/in-flight timing, not generated frames. FIFO stayed 0--3 frames,
ending at 1; no new stale-frame count increase occurred within this measurement.
At its first sample, the XP FIFO already recorded 138 rejected-new frames after
the maintenance interval; the count stayed 138 throughout the run. No claim of
lossless image delivery across the restart is made. DS CPU time averaged 63.35%
of one core during this run; the earlier 84% sample had different camera load
and is not a controlled production CPU comparison. The remaining first cadence
reduction is upstream of XP admission, despite the improved receiver path.

A later independent two-sample check verified increasing sequences in all 27 banks,
maximum age 0.188 s, PostgreSQL RUNNING with 8911 commits, two pending records and
no archive error. Acquisition and its image-free telemetry archive remained
operational after the approved brief ingress interruption.

Verification and remaining work
-------------------------------

* Actual Python 3.4.4 x86: 9 launcher tests passed; the 55-case camera/publisher
  suite completed with 52 passed and 3 skipped.
* Python 3.12: 104 receiver/federation/Tango/pipeline/camera tests passed, plus 10
  durable archive tests. These tests use fixtures/private loopback, not NI.
* At 17:34:51 UTC all 27 Acquisition banks were fresh, same source sequence 52271,
  no bank errors. PostgreSQL writer was RUNNING with 47546 committed records,
  five pending and no last error. Image policy remained metadata-only/no-pixels.
* Synchronization memory was fresh, selector -1, and all 16 values were unchanged:
  0.35,0.35,2176,100,2008.4,10,2175,10,2175,100,500,500,0.3,10,2175,100.
  This verifies observed VI control memory, not physical timing pulses.

Later observations and the next discriminating test
--------------------------------------------------

At approximately 18:51--18:56 Paris the XP orchestrator GUI intermittently displayed
``WinError 10048`` while its ACK count continued growing. The VI camera helper
still opens/closes TCP for every frame, and measured connection totals equal
completed observation totals. Ephemeral-port pressure is therefore an additional
specific hypothesis for the delayed rate reduction and transient relay failures;
legacy processing alone is not established as the explanation.

Microsoft documents a default maximum ephemeral port number 5000 in the relevant
older Windows versions and an IPv4 TIME_WAIT default 120 s specifically for XP.
The frequently quoted 240 s default belongs to Windows 2000 or XP IPv6, so it must
not be assumed for this machine. Explicit registry overrides and the actual TCP
table have not yet been read. References:

* https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/connect-tcp-greater-than-5000-error-wsaenobufs-10055
* https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/tcpip-and-nbt-configuration-parameters

``tools/read_supervision_xp_tcp.pyw`` is a read-only three-snapshot probe of
GetTcpTable and existing MaxUserPort/TcpTimedWaitDelay values. The operator
cleared its Open File Security Warning, and it ran at 18:06:52--54 UTC on XP.
It changed no registry, network setting, service or NI state. The snapshots
showed 1998--2001 camera-client TIME_WAIT entries, 146--148 relay-client TIME_WAIT
entries, and 2301--2302 distinct occupied local ports in 1025..5000. Total TIME_WAIT
rows were 4469--4475, including both ends of local loopback connections; that total
is not a count of unique ephemeral ports. MaxUserPort and TcpTimedWaitDelay were
absent as explicit overrides. The table establishes substantial connection churn
but does not demonstrate that the entire ephemeral-port pool was exhausted.

Separately, ten passive camera metadata reads estimated XP's wall clock ahead of
Everest by 4.77--4.95 s, near the receiver's 5 s future-timestamp rejection limit.
This is a metadata/monotonic-age estimate, not an NTP measurement. SuperVision VI
was stopped normally at approximately 19:12:56 Paris. The existing
``C:\dev\sup_fifo_deploy_20261029\ALIGN_XP_TIME.pyw`` utility then aligned XP to
Everest at 18:21:34 UTC (19:21:34 Paris). Its HTTP-Date-based estimate changed from
-5.054 s correction to -0.046 s residual; HTTP-Date second resolution prevents a
claim of millisecond clock accuracy. The utility reported CLOCK_ALIGNED_TO_EVEREST.
VI needs a fresh run afterward; its restart was requested from the operator
because recovered RDP input failed with ``Input Capture Window, not target window``.

The transport still needs a persistent client: retain the TCP connection in the independent
consumer loop, reconnect only on error, and close once on every normal stop.
Keep a rejected/in-flight owned frame distinct from the FIFO head, validate ACK
length/acceptance, and avoid retry sleeps on the healthy path. Do not modify OS
port/time-wait settings as a substitute for removing per-frame connection churn.
Python's typed ingress already accepts multiple framed observations per TCP
connection; the native VI client still requires editing and qualification.

If cadence remains variable after connection reuse, discriminate legacy image
work from acquisition waiting with per-iteration Grab/processing timing before
isolating capture. The producer must retain exclusive IMAQ-session ownership
and enqueue owned pixels; a reused mutable image reference is insufficient.
Preserve the existing channel-switch handshake, error recovery and stop/release
ordering. Sustained 25 Hz remains unverified.

Local evidence
--------------

``C:\dev\SuperVision_Telemetry\camera_probe_20261102`` contains the exact XP
pre-change archive, saved modified LLB, native XML comparison, phase metrics,
rate samples, LabVIEW profiler transcription, external DS profile, offline
benchmark source/result, read-only health snapshot and pending DS rollout plan.
``startup_fix_20261102`` beside it contains the deployed launcher package and
active-work checkpoint. No authentication key is included in these artifacts.
