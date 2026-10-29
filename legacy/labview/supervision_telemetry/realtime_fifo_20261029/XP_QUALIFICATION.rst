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
XP deployment and live throughput/freshness qualification are pending the
Windows execution warning. No 25Hz result is claimed.
