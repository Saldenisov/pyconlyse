Native XML worker diagnostic derivative
======================================

The XP-native ``ACQ_SharedState_Transport_Auto.vi`` derivative has SHA256
``156bdd968267435c6be0bfee46b1536903d543fc433d68940b98270fce800cfa``
(20,442 bytes). Its header is 12.0.0 release build4; RunOnOpen is zero.
BadSignal, BadNode, BadSubVI, BadSubVILink, BadCompile, and HasInsaneItems are zero.
Only source bytes were read during this audit; no VI was loaded or executed.

Three indicators were added natively on XP:

=======================  ==========  ========  ========================================
Original error output    Node        FP term   Indicator label
=======================  ==========  ========  ========================================
532                      Obtain495   779       Telemetry stop queue obtain error
745                      Dequeue397  961       Telemetry stop queue dequeue error
316                      Flatten310  1211      Telemetry packet flatten error
=======================  ==========  ========  ========================================

All 12 typed primitive error outputs are now consumed. The three new edges are
``532 -> 779``, ``745 -> 961``, and ``316 -> 1211``. All 57 original signal
endpoint lists, existing operation/constant signatures, and original seven
front-panel controls are preserved. The ten resulting front-panel terminals
remain unassigned to the connector pane (conNum=-1); the worker exposes no
public error or stop input/output pins.

Native Save also synchronized one existing wired polymorphic input cache:
FlattenToXML343 input670 changed from a nine-I32 cluster hint to LVVariant.
The same upstream1179 was already LVVariant. The opcode and input/output wires
are unchanged. This correction is recorded in ``source_audit.json``; equality
of serialized runtime output has not been tested.

Historical reference and delivery
---------------------------------

The immutable historical worker has SHA256
``f24df3c61e67a0c0a31d28cf891ef1e619e4b3a0c842522409e06cde9dd6d357``.
The historical individual-helper packet remains unchanged. This new receipt
directory contains text only and permits separate inventory of the derivative.
The frozen binary source is::

    C:\dev\sup_vi_camera_20261027\individual_helpers_20261028\review_88fd4200\xp_wrapper_xml_20261029_0340\ACQ_SharedState_Transport_Auto.vi

The saved entry still calls the runtime path
``../../SUP_Telemetry_Helpers_88fd4200/sync_lifecycle/ACQ_SharedState_Transport_Auto.vi``.
A repository override folder is an inventory location. Delivery must map its
bytes to that native saved runtime target, or the caller must be relinked and
saved natively with a new source receipt. A directory copy alone does not
change a saved VI link.

These indicators consume error outputs and expose diagnostics. They do not
demonstrate successful stop delivery, XML framing/ACK behavior, recovery,
runtime shutdown, or physical device behavior. DefaultErrorHandling remains1.
No VI binary was copied or changed by the auditor; Git staging and commit
remain pending root review.
