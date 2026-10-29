SuperVision Telemetry: prepared native FIFO patch, 29 October 2026
=================================================================

Prepared on Everest only. No XP files, running VI, NI tasks, synchronization
settings, Device Server, recorder or live web processes were changed.
The original SuperVision archive and the frozen native-main/XML artifacts
remain byte-identical. This directory is a patch, not a complete installation.

Dataflow
--------

The existing native entry already runs three parallel branches: the original
copied SuperVision, the XML/synchronization observer, and camera transport.
That structure is retained. Camera capture performs no socket calls::

  existing IMAQ Grab / FrameCount
    -> existing FrameTap / owned U8 array copy, 1000ms copy gate now 0ms
    -> ordinary Enqueue Element, timeout=0, bounded FIFO=128
    -> independent existing SUP_Camera_Transport while loop
    -> loopback TCP 127.0.0.1:8768, existing typed packet and ACK
    -> existing SuperVision Python orchestrator, optional independent sender
    -> Everest same Tango DS camera ingress :8769 -> latest web image

The three camera data-queue size inputs (entry owner, producer lookup and
consumer obtain) are all 128. LabVIEW ignores later size inputs when a named
queue already exists, so updating the producer alone would not fix capacity1.
The two stop queues and XML snapshot queue remain capacity1. Their startup,
flush, stop enqueue, join and release signal topology is unchanged.

Lossy Enqueue is replaced with ordinary Enqueue. Full FIFO rejects the new
frame immediately; it does not silently overwrite the oldest frame or wait
inside acquisition. The existing Boolean connector ``replaced_or_error`` is
kept for caller compatibility; it now means enqueue timeout/full or error.
That output is diagnostic, not an independent safety signal or a durable loss
log. A bounded FIFO cannot guarantee all frames through an indefinite outage.

The consumer's 100ms Dequeue timeout waits only when FIFO is empty. Its 1000ms
TCP timeouts bound socket operations and remain unchanged. There is no added
consumer sleep or fixed frame-rate limiter. The original camera-loop 30ms
wait, camera/channel selection, IMAQ setup, synchronization and NI logic are
unchanged. VI still serializes/copies each selected image in the capture path;
this patch does not establish its cost on XP.

128 frames correspond to 5.12 s at 25 Hz. For 768x576 U8, pixel storage alone is
54 MiB, before array/Variant/flattening and Python staging copies. Raw payload
at 25 Hz is 11.0592 MB/s or 88.4736 Mbit/s before overhead. Memory, source CPU, actual
compression and LAN throughput must be measured on XP. These values are not a
measured transfer rate. NI1409 still has one selected input/ADC; this patch
does not provide two simultaneous 25 Hz camera streams.

Native artifacts and qualification
----------------------------------

Four changed files were edited/saved by LabVIEW 2020 x86 and exported by its
native SaveForPrevious API to LabVIEW 2012. No VI binary-resource writer was
used. All four have RunOnOpen=0; opening the candidate entry does not start it.
Receipts record exact hashes and native application identity.

Read-only extraction checks every wire connection, primitive identity,
constant change, referenced callee path, front-panel connector and structural
node identity against the frozen baseline. Only the four intended literal
changes, Lossy-to-Enqueue replacement and new timeout0 wire are allowed.
Compiler type indices, cached resources and diagram routing geometry differ
between native versions and are not used as semantic identities.

The entry was edited with LabVIEW's OpenVIWithoutRefees API: hardware callees
were not loaded or executed. Consequently its saved State=0/BadNode=1 records
unloaded references. Its call paths, terminals and wires are retained, but a
complete dependency load/compile in LabVIEW 2012 is still REQUIRED before Run.
The three camera helpers have saved BadNode=0/BadSignal=0/BadCompile=0.
This package is source-audited preparation, not a qualified runnable release.

``baseline/entry_stopped.vi`` preserves the stopped precursor for reproducible
comparison. Do not substitute the RunOnOpen entry from the older package when
inspecting these files. Do not use this patch to overwrite the original
``C:\PILOTAGE_ELYSE_SUP\SUPERVISION.llb``.

Tomorrow's XP integration and test
----------------------------------

1. Preserve the currently working original VI and launch shortcut. Stage a
   separate copy of the existing complete Telemetry dependency tree. Keep its
   relative directory structure and original NI/calibration/config files.
2. Overlay the three camera files into ``SUP_Telemetry_Helpers_88fd4200/camera``
   (including ``observer_v3``). Put the new stopped entry in an ``entry`` folder
   below the copied Telemetry directory: its ``../SUPERVISION.llb`` and
   ``../../SUP_Telemetry_Helpers_88fd4200/...`` links must resolve inside the
   staged tree. Keep the frozen XML derivative156bdd968267435c... and original
   main 87c73e3e3a163446... unchanged. Use the full hashes in manifest.json.
3. In native LabVIEW 2012, load the complete stopped copy, resolve only the
   intended staged helpers, verify unbroken Run arrow and error list, then
   save. Recheck main/XML/synchronization hashes. Do not run if closure fails.
4. Enable the prepared optional ``camera_stream`` block on the existing Python
   orchestrator, ``source_mode=LABVIEW_BRIDGE``, ``every_n=1``, ``capacity=128``,
   ``max_bytes=67108864``, destination Everest 10.20.30.202:8769. See
   ``../native_main_20261029/runtime/SOURCE_CAMERA_STREAM.rst``. Default sampled
   publication still has its old image budget if this block is left disabled.
5. Once original SuperVision is stopped normally and ownership is released,
   run the Telemetry COPY under operator control. Measure at least 120 s in one
   fixed channel: actual Grab frame sequence, VI/Python ingress, staging/full
   counters, Everest ACKs, source age, process memory and web render sequence.
   Expect about 3000 frames only if the camera actually supplies 25 Hz. Compare
   sequence identities, not HTTP polling count or browser repaint count.
6. Test controlled local-network slowdown: capture must continue, overflow must
   be accounted for, memory must stay bounded. Confirm stop/join/release works.
   Retain last web image during gaps. Restore the original VI after the test
   window if live qualification fails. Images must not enter Acquisition's DB;
   synchronization/centroid metadata keep their existing numeric-only policy.

No live 25 Hz test, camera initialization, synchronization start or deployment
was performed by this preparation.
