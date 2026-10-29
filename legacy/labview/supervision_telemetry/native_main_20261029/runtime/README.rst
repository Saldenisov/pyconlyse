Live SuperVision Telemetry qualification, 2026-10-29
==================================================

The copied native entry was started on SuperVision XP in LabVIEW 2012 x86.
Its original SuperVision initialization executed. The Python receiver remained
VI_PASSIVE_SHADOW, with zero NI resources and every command disabled. The
original PILOTAGE_ELYSE_SUP library was not edited.

Actual native counter-only XML and binary U8 packets reached the receiver,
Everest Tango Device Server and the web. The 16 counter values are observed
LabVIEW control memory, not independent measurements of physical timing.
The image is 768 x 576 U8, observed channel metadata 2. This does not establish
laser state or physical channel calibration.

The initial Everest replacement probe ran before Tango export completed.
Its original failure receipt is retained. A fresh read subsequently verified
ON, the expected new process, the complete source closure and unchanged Tango
properties. The separate PostgreSQL process was absent and the durable ingress
spool had reached its 100000-record bound. Starting the existing database
restored draining without deleting pending data. The live receipt records the
remaining backlog; database catch-up was not complete.

r21 fixes a camera starvation defect in the latest-only queue: enqueueing a
replaceable image no longer consumes the video delivery budget. Only a matching
verified transport ACK updates that budget. Queue callbacks release the queue
lock before taking the publisher lock. A late ACK from a retired VI source
cannot suppress its replacement. This is still a deliberately sampled video
channel, not a 25-frame/s lossless recording transport.

The web now keeps the last validated canvas mounted during stale/unavailable
responses and read failures. Its age and source status remain visible. Invalid
or regressed frames cannot replace retained pixels, and duplicate images do not
receive a new freshness window. The deployed main asset is main.cf889b14.js.
Static assets were activated without restarting the web, VI or XP receiver;
older hashed assets remain available to already-open pages.

Validation
----------

* Packaged CPython 3.4.4 x86: 51 tests, 48 passed, 3 modern-only skips;
  79 Python files compiled; no NI imports, listeners or permitted network calls.
* Packaged CPython 3.12: 80 tests passed.
* Python 3.4 cold installer fixture: 92 files, exact repeat ALREADY_INSTALLED,
  unrelated target preserved, no process or hardware start.
* Frontend: 94 tests passed in three suites; production build succeeded.
* Live qualification: 27 banks progressed within one source session; see
  live_qualification.json for exact ages, counters, image sequence and archive
  backlog. It includes no credentials.

Bandwidth boundary
------------------

Each raw frame contains 442368 bytes. At 25 frames/s, raw pixels require
11.0592 MB/s (88.4736 Mbit/s); existing base64 requires at least 14.7456 MB/s
(117.9648 Mbit/s), before protocol overhead. Both observed ELYSE Ethernet
interfaces negotiated 1 Gbit/s; sustained path throughput was not benchmarked.
One real frame compressed losslessly with zlib level 1 to 178403 bytes,
equivalent to 35.6806 Mbit/s at 25 frames/s for that particular content.
Compression performance on XP and a continuous full-frame transport remain
unqualified. The current sampled channel does not deliver every Grab frame.
