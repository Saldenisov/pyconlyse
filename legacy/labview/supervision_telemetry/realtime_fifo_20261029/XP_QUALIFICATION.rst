SuperVision FIFO: XP integration record, 29 October 2026
======================================================

The frozen preparation manifest describes the pre-deployment artifacts. This
record describes their subsequent integration on SuperVision XP 10.20.30.2.

Native integration
------------------

The three camera helpers were installed with byte-verified backups. The new
entry was loaded in LabVIEW 2012 SP1, its three relocated dependencies were
resolved, and the entry was saved natively. The full dependency closure had
an unbroken Run arrow and an empty error list before execution. The copied
SuperVision initialized and ran its existing camera and synchronization logic.
No Python Initialize or independent hardware command was issued.

The installed Telemetry archive SHA256 was
``109fa5f8412d71ac0232163efe02779126cca215050b103c272bbabd70523897``.
Read-only comparison against the frozen archive found identical nodes,
constants, calls, wires and front-panel labels/types in the main VI. All other
42 LLB members were byte-identical. The two differing installed camera helpers
also had identical constants, primitives, calls and wires to their preparation
baselines. Their existing native layout/cache bytes were backed up before
replacement.

The original ``C:\PILOTAGE_ELYSE_SUP\SUPERVISION.llb`` remained at SHA256
``d427b2ba8544e4ffd6868f4e2ef74762363c7c713e30b2ff151e5f5ad168bcf4``.

Clock and initial throughput findings
------------------------------------

XP's HTTP clock was 45.99 seconds ahead of Everest. Camera ingress correctly
rejected observations more than five seconds in the future. Retrying the FIFO
head then accumulated old frames; accepting those frames later did not make
them fresh. The VI was stopped normally before correcting XP's wall clock.
The one-shot correction used three bounded HTTP Date observations from the
existing Everest web service and selected the lowest-roundtrip midpoint.
The post-correction sample differed by approximately 0.09 seconds. This is
alignment to Everest, not independent UTC calibration. The existing XP NTP
configuration for ``canon.inria.fr`` reported an unreachable peer.

After clock alignment, a 120-second test received 497 frames, or 4.14 frames/s,
at 768x576 U8. Frames still accumulated approximately 2.5 seconds of age. Thus
removing the VI's 1000ms limiter alone did not qualify 25Hz operation.

Python admission correction
----------------------------

Profiling the Python3.4 admission path with 50 synthetic 768x576 frames exposed
a full 27-bank packet build on every camera receipt, although image transport
was independent of those banks. Native pixels also passed through Base64,
JSON serialization/hashing and decoding before entering the binary sender.

Independent camera receipts now retain validated immutable pixel bytes. The
native fixed-header, geometry, source/capture identity, wall-clock and Win32
tick-age checks remain synchronous. The public legacy JSON decoder retains its
schema. Equivalent native/JSON observations share the same replay digest;
duplicate receipts cannot renew frame age. Compression, network transmission
and Everest acknowledgement remain on their existing separate workers.

Pure camera receipts no longer rebuild the 27-bank packet. The existing owner
publisher handles changed generations separately; first-source and counter
observations retain synchronous metadata publication. Queue capacities, byte
bounds and explicit rejection counters remain unchanged. Images remain outside
Acquisition's telemetry database.

The same local profiled workload decreased from 5.150 to 0.267 seconds. It
excludes NI, native VI scheduling, compression and sockets, and does not prove
any live XP frame rate. Python3.4: 64 tests, 3 modern-only skips. Python3.12:
the same 64 tests plus 10 camera-ingress/two-orchestrator integration tests
passed.

The first live correction received 1232 frames in 120 seconds (10.27 frames/s),
at approximately 14.9--16.3 Mbit/s of compressed payload. The sender FIFO still
contained approximately 124 frames and observations arrived 11.6--12.2 seconds
old. These were stale frames, not qualified real-time delivery. The native
staging worker reported no processing errors; the downstream FIFO explicitly
counted rejected new frames at its capacity. A bounded FIFO alone cannot make
an overloaded sender lossless or fresh.

Second transport candidate
--------------------------

The independent-image bridge now constructs its existing owner-scoped C12 bank
and synchronization-counter wire directly. It no longer builds and validates
an empty 27-bank scaffold for periodic or XML metadata publication. The shared
Everest Device Server still merges and exposes all 27 public banks. The legacy
sampled-image path is unchanged.

The camera sender uses stored DEFLATE (zlib level 0) inside the same authenticated
lossless ``zlib_u8_v1`` envelope. This trades XP compression CPU for bandwidth;
the encoder's public default remains level 1. Full 768x576 U8 at 25 frames/s
requires 88.47 Mbit/s of raw pixels before protocol overhead. Sender status now
reports compression level and the last envelope-encoding duration. Geometry,
authentication, bounded decompression, real observation age and FIFO limits
remain enforced. No camera pixels enter the Acquisition telemetry database.

Python3.4: 67 tests passed with 3 modern-only skips. Python3.12: all 77 camera,
owner-telemetry and ingress/integration tests passed. The second candidate's
XP deployment completed on 30 October; the backup and receipt preserve all
three previous module hashes. The first 120-second run delivered 1107 frames
(9.225 frames/s); a subsequent 120-second run delivered 1005 (8.375 frames/s).
The second run had no new Everest ingress errors. Native XP admission still
rejected observations, so removing compression did not establish 25Hz.

Growing frame IDs and native clock quantization, 30 October
----------------------------------------------------------

Native camera observation order now uses ``FrameCount + 1`` rather than a
microsecond ordinal calculated from timestamps. Replay state is bounded and
scoped per source, capture and channel. A new capture can reset FrameCount;
retired captures/sources, regressed counts and changed bytes under a repeated
ID remain rejected. Equivalent JSON/native retries retain the same digest.
Timestamps remain observation labels and freshness inputs, not frame IDs.

Read-only error sampling on XP found native timer values 1--6ms ahead of
``GetTickCount`` while wall-clock age was zero. Unsigned subtraction had
interpreted these small differences as approximately 49.7 days. Some fresh
frames also failed the copy-duration check because coarse clocks reported
zero elapsed time. Microsoft's GetTickCount reference documents typical
10--16ms resolution:
https://learn.microsoft.com/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount

The decoder now uses signed modular subtraction, admits at most 16ms of
negative quantization, and adds the full 16ms uncertainty to reported age.
The two-second deadline is not extended. Larger future offsets, old ticks,
wall-clock rollback with old monotonic observations and age plus uncertainty
at or beyond two seconds remain rejected. This is a measured compatibility
allowance on this XP host, not independent clock or hardware calibration.

Python3.4: 71 tests passed with 3 modern-only skips. Python3.12: all 81 tests
passed. Coverage includes per-channel IDs, capture resets, retries, timestamp
rollback without ID rollback, timer wrap and the unchanged stale deadline.
The deployed source build is
``7b3df4054e029b09fcbaed5d0be3a2f711db3b7e49284e7cb2d8ec7b464a3349``.
Only the passive Python module/server was replaced; the running VI and NI
tasks were not stopped, reinitialized or independently commanded.

The next 120-second live run delivered 1626 frames (13.55 frames/s), with
24.80--70.86 Mbit/s ingress windows. Reported camera age ranged from 0.020 to
2.751 seconds; 113 of 121 one-second observations were fresh. The sender FIFO
ranged from 0 to 47 frames and ended empty, without rejecting new frames.
There were 34 native admission rejections and 120 stale frames received, so
this is neither an all-frames nor a 25Hz qualification. All 27 public banks
advanced, remained fresh in these samples, and PostgreSQL stayed RUNNING
under ``metadata_only_no_pixels``. Synchronization metadata had one stale
sample at 2.062 seconds; this does not establish a hardware timing failure.

An independent web SSE observation received 101 distinct, strictly growing
frame IDs in 12.219 seconds, with maximum reported age 0.690 seconds. Pixel
payloads were consumed in RAM; only IDs/age/availability were retained in the
diagnostic receipt. This checks the web stream, not browser repaint cadence.

An isolated Everest loopback fixture delivered 250 full 768x576 U8 frames in
five seconds, with zero FIFO rejection and no NI/SQL/live Tango operation.
It excludes XP, the real LAN and native VI scheduling. A transient XP sender
``WinError 10048`` was also observed before the final restart; it did not recur
in the final 120-second sample. Native producer/transport timing and TCP
connection churn remain to be measured before changing the VI transport.
