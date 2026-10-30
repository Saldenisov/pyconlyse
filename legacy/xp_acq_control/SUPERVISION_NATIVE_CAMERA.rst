SuperVision: native camera and synchronization preparation
========================================================

This change is prepared on Everest. It does not deploy, stop LabVIEW, initialize
NI resources, change synchronization values, or restart live services.

Two independent owners on SuperVision XP
---------------------------------------

The Python 3.4 32-bit orchestrator has three buttons: Initialize, Deinitialize,
Stop server. An explicit Initialize creates two retained child processes:

* NI6602 ``Dev1``: NI-DAQmx, eight counter tasks ``SUPCOUNT0``..``SUPCOUNT7``.
* NI1409 ``img0``: NI-IMAQ C API through the installed 32-bit ``imaq.dll``.

The camera adapter calls imgInterfaceOpen, imgSessionOpen, sets channel and
black/white reference voltages, then imgGrabSetup. Each imgGrab waits for a new
frame and copies U8 rows into owned bytes before another grab. Driver row padding
is removed. One caller-owned bounded destination buffer is reused per session;
no repeated NULL request for driver output-buffer allocation occurs. Its memory
is released only after a successful session close. The current maximum is
524288 pixels, including 768 x 576 frames.
This reads the frame grabber directly; no LabVIEW or Vision Image reference is
needed. The existing driver and camera configuration must remain installed.

The source NI6602 profile uses ``/Dev1/PFI10`` as rising start trigger and
``/Dev1/PFI11`` as external timebase. Labels, in ctr0..ctr7 order, are laser_hf,
imac, laser, oscilloscope_1, oscilloscope_2, detection_1, detection_2, machine.
The eight finite/retriggerable tasks follow the reviewed VI initialization.
Saved initializer constants and an explicit local 16-value takeover profile
are distinct. The source UI conversion is 20 ticks/us; external clock frequency
and physical output delays have not been measured by this software.

Counter telemetry reports last returned command memory, not an oscilloscope
measurement. Counters continue in hardware after configuration. The existing
Tango DS ``counter_timing.set`` route selects Acquisition or SuperVision owner;
the local worker waits for pulse completion, stops that task, updates timing,
and starts it again. Native commands remain disabled while VI owns the board.

Independent native image stream
-------------------------------

Existing ``camera_stream.source_mode = LABVIEW_BRIDGE`` configurations retain
their behavior. Explicit ``VI_OR_NATIVE`` enables the same bounded camera
transport for whichever source the orchestrator currently owns:

::

    VI mode:
      IMAQ Grab -> FrameTap -> owned U8 FIFO -> typed local ingress
                                                |
    Native mode:                                |
      NI1409 child -> private IPC -> RAM staging +
                                                |
                                   independent admission worker
                                                |
                                          bounded FIFO
                                                |
                                  persistent TCP camera sender
                                                |
                                      Everest camera receiver
                                                |
                                         Tango DS / web

Native capture stages every returned grab immediately at the card dispatcher;
it is not sampled by the 0.2-second telemetry publisher or the old 1-second
image budget. Only this explicit camera path removes the post-read polling
sleep. NI1409's bounded next-frame wait paces capture; input failures retain
poll backoff. Synchronization keeps its own polling cadence and process.
Queued close/commands are checked between camera reads.

The sample sink only appends a bounded descriptor. Base64 decoding, validation,
compression and network I/O run on separate workers. Pixel IPC remains base64
in the existing private JSON protocol; its cost still needs measurement on XP.
No duplicate raw image is sent through the normal owner telemetry frame in
this mode. Neither this path nor its ACK writes images to Acquisition's DB.
Synchronization metadata continues on the existing telemetry/DB path.

Native stream identity is the orchestrator boot session plus the card worker
generation and increasing grab sequence. Timestamps describe age, not identity.
The sequence counts successful software grabs; it is not the hardware frame
counter and cannot prove that no camera frame was missed.

Bounded behavior and qualification
----------------------------------

``card_processes.cards.video.sample_sink`` reports staged, rejected and failed
append counts. A full queue, lifecycle fence or runtime lock contention rejects
that output sample explicitly. It does not fault the input card or stop the
independent synchronization owner. Downstream staging, admission, FIFO and
receiver ACK counters describe subsequent delivery separately.

Native ownership never follows automatically from lost VI telemetry. Initialize
still requires explicit VI release and local authorization. Uncertain or dead
native owners are retained for explicit reconciliation, never auto-restarted.
The preparation changes neither output profiles nor existing ownership gates.

The current native adapter selects one analog input channel. It does not yet
implement two simultaneous camera streams, NI1409 channel scanning, the VI's
interlace/BCG/profile pipeline, or a hardware ring-buffer guarantee of all frames.
Those features must not be inferred from the two-channel VI transport schema.
Neither 25 Hz capture/delivery nor physical pulse parity is qualified until the
later XP hardware test. Camera throughput and timing output measurements are
separate acceptance checks.

Official acquisition API reference:
https://www.ni.com/en/support/documentation/supplemental/06/ni-imaq-images-and-imaq-vision-images-in-c.html

The installed NI ``NI-IMAQ/Examples/MSVC/Grab/HL Grab/HLGrab.c`` retains the
same ImaqBuffer variable across imgGrab calls; the included ``niimaq.h`` declares
imgGrab's second parameter as void**. The adapter uses caller-owned memory
instead of repeatedly requesting NI output-buffer allocation.

Test entry points:

* tests.unit.test_supervision_native_camera_stream
* tests.unit.test_supervision_card_adapters
* tests.unit.test_supervision_initial_sync_profile
* tests.unit.test_supervision_camera_stream_publisher
* tests.unit.test_supervision_runtime

Tests use only RAM driver fixtures, private child processes and private
loopback connections. No live NI board, XP service or telemetry DB is used.
