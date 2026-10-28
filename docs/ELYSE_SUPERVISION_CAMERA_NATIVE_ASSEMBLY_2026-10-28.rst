Camera transport: native XP assembly worksheet
=============================================

Scope
-----

This worksheet describes the exact stopped ``SUP_Camera_Transport.vi`` artifact
SHA256 ``4ab066c45cc6b15c2e0b0f95b2bcd8f239b9b8d6989d33c49b84843f39c28f03``
(19,484 bytes, LabVIEW12). Native Open/Save was previously qualified. Queue/TCP
execution and shutdown remain untested. This review changes no VI or packet guard.

Configured waits and actual stop behavior
----------------------------------------

* Data queue: ``ELYSE_SUP_CAMERA_RAW_LATEST_V1``, Variant elements, capacity 1;
  Dequeue node62 waits 100 ms.
* Stop queue: ``ELYSE_SUP_CAMERA_STOP_V1``, Boolean elements, capacity 1;
  Dequeue node397 polls with timeout 0.
* TCP Open43, Write75, ACK-prefix Read221 and ACK-body Read459 each use 1000 ms.
  The destination is ``127.0.0.1:8768``. Each available payload opens and closes
  its own connection. Both reads use the unwired Standard mode.
* Stop polling and network work are independent branches within the same While.
  The network Case is selected only by ``NOT data_Dequeue.timed_out``. A True
  stop token therefore does not cancel a send already eligible in that iteration.

The configured per-iteration wait budget is ``100 + 4*1000 = 4100ms``. A stop
token arriving after that iteration's poll can require another iteration, giving
a conservative two-iteration budget of 8200 ms. These sums exclude TCP Close,
conversion, queue management, and OS/LabVIEW scheduling. They are not hard
wall-clock join bounds. `NI TCP Read documentation
<https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/tcp-read.html>`_
defines the read timeout; `TCP Close
<https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/tcp-close-connection.html>`_
has no timeout input and still executes with an incoming error.

ACK handling is allocation-limited, not acceptance validation. Four bytes are
cast to I32; In Range and Coerce 551 clamps the body-read count to1..16384.
Its range Boolean drives an indicator only. Invalid lengths are not rejected;
the returned body is displayed as raw text. JSON, success status, RunStamp, and
FrameCount are not parsed or matched. See `NI coercion semantics
<https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/in-range-and-coerce.html>`_.

Native caller sequence
----------------------

1. Confirm the preceding producers and worker have returned. Fixed queue names
   provide no RunStamp namespace. Call Begin once; retain its exact RunStamp for
   camera and NI6602 observation.
2. Before either worker or producer starts, obtain owner refs for both correctly
   typed named queues, capacity 1, then flush both queues. Hold those refs through
   the run. Existing queues retain their original type/capacity; merely obtaining
   them does not establish a fresh session.
3. Start transport and producer branches in parallel after ordered initialization.
   Transport has seven FP objects but no assigned connector terminals, so its
   launch ordering needs a native structure/dataflow dependency.
4. Insert FrameTap inline before downstream NI image writers. Use image con6→4
   and original-error con5→3. In the original main, Grab15740 image15749 feeds
   Rotate14726 input14771 through wire19409. Route that dependency through
   FrameTap; an independent parallel branch of the mutable reference cannot
   freeze pixels during ImageToArray.
5. After all producer branches and final copy attempts complete, call End with
   the same RunStamp. End invalidates Epoch; it neither flushes transport data
   nor stops the worker. If pending-tail delivery is unwanted, flush the raw queue
   now, after producers are quiescent.
6. Flush the stop queue, enqueue Boolean True with timeout 0, and inspect the
   private enqueue error. A stale False element can fill the capacity 1 stop queue;
   a stale True can terminate a subsequent worker immediately.
7. Await actual worker completion, then release owner refs with force-destroy
   False. Worker releases its own two refs after its While. Do not force-destroy
   active queues. A nonforced owner release alone does not invalidate the worker's
   remaining refs. `NI Release Queue documentation
   <https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/release-queue.html>`_
   defines this reference-counted lifetime.

Completion and unresolved runtime behavior
-----------------------------------------

The caller can give a separate worker-completion acknowledgement a finite wait
deadline. The current worker provides no completion output or acknowledgement
queue. A deadline expiry cannot cancel a blocking static subVI call; an enclosing
parallel frame still waits for that call. On an unconfirmed join, report shutdown
pending, retain deterministic ownership, and do not start a new run on these names.

``DefaultErrorHandling=1`` and three error outputs are unwired: stop Obtain532,
stop Dequeue745, and VariantToData673. VariantToData664 is outside the guarded
network Case, so there is no source-level idle-conversion guard. Automatic error
handling or suspension has not been tested. This requires explicit native runtime
resolution before unattended operation can be claimed.

Loop stop depends on the stop element, FP Stop control, or the *initial data
Obtain* error status. Data-Dequeue errors, stop-queue errors, conversion errors,
and TCP errors do not drive stop. Queue invalidation can therefore produce
repeated immediate errors without a source backoff. `NI Dequeue documentation
<https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/dequeue-element.html>`_
defines invalid-reference errors. Startup flushing, retained owner refs, prior-worker
completion, and final release ordering are required caller responsibilities.

Machine-readable evidence: the packet's
``legacy/labview/supervision_telemetry/individual_helpers/camera/receipts/TRANSPORT_4AB066_READONLY_FINDING.json``. Its source
IDs and hash describe this retained artifact only; the receipt grants no runtime
approval and does not change FrameTap admission.
