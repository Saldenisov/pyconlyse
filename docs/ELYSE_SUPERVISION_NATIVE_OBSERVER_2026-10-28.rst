SuperVision telemetry qualification, 28 October 2026
===================================================

The camera observer is exported for LabVIEW 2012, but the complete SuperVision
Telemetry application is not yet qualified to run. The modified main returned
``Memory Full`` during stopped loading in local LabVIEW 2020 32-bit. The native
UI seed opened both its front panel and full block diagram after legacy motor
and Thorlabs dependencies were located. Its main has 23 compilation errors;
the profile subVI has two missing ``IMAQ GetRowCol`` calls. The observed errors
identify NI Vision Development Module functions absent from the host. No Run
was performed. The running XP VI and its card ownership were not replaced.

Observer evidence
-----------------

``legacy/labview/supervision_telemetry`` contains the authored observer and its
capacity-one queue helper. NI libraries, the original SuperVision library and
camera pixels are excluded. Both helpers use native LabVIEW 12.0.0 release
build 4 format and have RunOnOpen disabled.

The observer passed stopped Open and Save in LabVIEW 2020 32-bit, followed by
native Save for Previous Version to 12.0. Its reparsed source retains 17 root
front-panel fields, the 12-port interface and the 95-byte camera header. The
dimension/error guard passed 13,450 offline cases. Image and original error
pass through unchanged; copy and queue errors have separate outputs. The
transport worker remains separate from the RAM copy and latest queue.

Save for Previous Version cleared the observer's current DSInit cache
(``nDCOs=0``, ``fpdcoTableTMI=-1``). Native LabVIEW 2012 Open/Save, actual camera
execution, capture ordering in the final main and worker shutdown remain to be
verified. Export is not evidence that a frame reached Everest.

The portable read-only verifier and its eight refusal tests passed on actual
Python 3.4 and Python 3.12. They check pinned VI/proof bytes, bounded RSRC
version/flags and the explicit custom dependency closure. They do not load a VI
or establish runtime qualification.

Everest software deployment
--------------------------

The existing Tango receiver and web application were initially absent and were
started with their saved interpreter, arguments and configuration. The three
receiver modules from ``b2ca4f5a`` and the additive web integration from
``8bbc7c59`` were then deployed. Existing Acquisition properties and SuperVision
read-only migration admission were preserved.

Post-deployment observations:

* DS state ON; all 27 bank sequences advance with their source sessions retained.
* Maximum observed bank age: 0.219 s.
* ``/elyse`` and telemetry, video and synchronization GETs return HTTP 200.
* SuperVision counter values and video remain explicitly unavailable; values and
  frame are null. No Acquisition values substitute for SuperVision observations.
* SuperVision reports VI_PASSIVE_SHADOW, zero resources and disabled command
  capabilities. Hardware acknowledgement and physical measurement verification
  remain false.

The receiver replacement pauses reception. These observations do not prove
continuous archival recording through the replacement interval. No XP card
initialization, VI execution or device command was performed by this deployment.

Operational evidence is retained locally at::

  F:\ELYSE_Orchestrators\supervision_vi_20261027\operational_readback_20261028T085433604917Z.json
  F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\counter_projection_20261028T085026392309Z\deployment.json

Remaining acceptance
--------------------

Resolve the main load failure against the exact native seed and its original
dependencies, qualify the observer in LabVIEW 2012, relink the final wrapper and
perform stopped compilation of the complete copied application. A hardware
owner handover and live camera/synchronization test must wait for the operator's
permission to stop the currently running VI. Preserve the original VI and
desktop shortcut throughout.
