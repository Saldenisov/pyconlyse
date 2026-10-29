Native XP telemetry entry: saved-source qualification
====================================================

``Supervision Telemetry.vi`` was saved natively through LabVIEW 2012 on XP,
then saved with ``RunOnOpen=1``. Its exact SHA256 is
``477860f5505ffd1094ac185b802a96c8a4e3ddbfd3986a5d2be492176c9ee34e``
(21,433 bytes). This entry runs when opened; opening it is an execution action.
The audit read file bytes without opening or executing a VI.

This text-only directory records source qualification. The frozen binary source
is::

    C:\dev\sup_vi_camera_20261027\individual_helpers_20261028\review_88fd4200\xp_wrapper_xml_20261029_0340\Supervision Telemetry.vi

The entry's 64 signal endpoint lists, checked operation/constant/call/structure
signatures, front-panel identities, terminal types, and three callee paths match
the native stopped wrapper with SHA256
``fa2c035f708dcb54c6cb1bb2f97923efd6553ed88b545a420c8c40c7349056e0``.
The only changed execution property is ``RunOnOpen: 0 -> 1``.
The header is 12.0.0 release build4. BadSignal, BadNode, BadSubVI,
BadSubVILink, BadCompile, and HasInsaneItems are all zero.

Startup and shutdown source
---------------------------

Four owner queues have capacity1. Each Obtain error feeds its matching Flush
error input. All four Flush errors feed MergeErrors2671; its result controls the
Error/NoError Case and a startup error indicator. The Error case is empty.
The NoError case contains three parallel branches: the XML worker, the copied
main followed by the two stop Enqueues, and the camera worker.

Both stop Enqueues send True with timeout0. Both error outputs and both timed-out
outputs feed private indicators. Four Release Queue nodes execute outside the
Case in the final outer native sequence frame, after all three branches return.
All four release errors are consumed. Force-destroy and error inputs retain
their default False/no-error values. All 14 primitive error outputs and the
MergeErrors output are wired.

This supplies a native dataflow join. A numeric hard join deadline, successful
network acknowledgement, and physical device behavior were not demonstrated.
Timeout indicators expose failure to enqueue a stop token; wiring an indicator
does not implement a recovery policy.

Saved caller-relative targets
-----------------------------

* Main: ``../SUPERVISION.llb/0_SUP_ELYSE.vi``.
* XML: ``../../SUP_Telemetry_Helpers_88fd4200/sync_lifecycle/ACQ_SharedState_Transport_Auto.vi``.
* Camera: ``../../SUP_Telemetry_Helpers_88fd4200/camera/SUP_Camera_Transport.vi``.

Preserve the native saved directory layout. The standalone readback directory
is an audit location and does not itself reproduce those dependency paths.
Caller source/link identity does not independently prove the hashes of files
loaded into a running LabVIEW application instance.

The copied main is covered by ``../revision624/source_audit.json``. Its archive
SHA256 is ``87c73e3e3a1634461f27f1cafbbcb0f476d2cbc2663cf485079342a24f3d05c9``;
the original archive remains ``d427b2ba8544e4ffd6868f4e2ef74762363c7c713e30b2ff151e5f5ad168bcf4``.

XML diagnostic derivative
-------------------------

The native XML worker copy has SHA256
``156bdd968267435c6be0bfee46b1536903d543fc433d68940b98270fce800cfa``
(20,442 bytes), header12.0f4, RunOnOpen0, and zero bad flags. Three new private
error indicators consume stop-queue Obtain532, stop Dequeue745, and packet
Flatten316. All 12 primitive error outputs are now consumed. All 57 original
wire endpoint lists and original operation/literal signatures remain.

Native Save also synchronized one existing wired polymorphic input cache:
FlattenToXML343 input670 changed from a nine-I32 cluster hint to LVVariant.
Its existing upstream1179 was already LVVariant; its input/output wires and
operation are unchanged. This correction is recorded explicitly. Equality of
serialized runtime output was not tested. The immutable reference XML worker
with SHA256 ``f24df3c61e67a0c0a31d28cf891ef1e619e4b3a0c842522409e06cde9dd6d357``
remains unchanged.

Launch guard and remaining boundary
-----------------------------------

Root observed an Explorer/RDP copy of the XP executable at
``C:\Program Files\National Instruments\LabVIEW 2012\LabVIEW.exe``.
The readback is 38,663,232 bytes, SHA256
``5c894a31a084e9e26f9491b697f02e069c760dde26ba46686d7144f41e13ff8c``.
Independent read-only inspection confirms PE32, I386 machine0x014c, and
FileVersion/ProductVersion12.0.1f2. ``xp_executable_readback.json`` records the
header and version-resource evidence. The executable was never loaded or run.
This identifies the observed file for a hash-pinned launch guard; it does not
identify a currently running remote process or establish runtime behavior.

Native execution, a fresh-process start, actual loaded dependency hashes,
camera delivery, NI6602 observation, transport acknowledgements, and shutdown
runtime remain unqualified. Source qualification supplies the exact entry
identity and connections; it does not authorize an automatic launch.

Only text receipts were prepared here. No VI was modified or copied, and no Git
staging or commit was performed.
