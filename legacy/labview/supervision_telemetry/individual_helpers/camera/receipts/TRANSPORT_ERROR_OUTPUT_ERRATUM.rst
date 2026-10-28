Transport error-output mapping correction
========================================

This corrects the retained read-only finding SHA256
``9df0e70eb433ca92b1895ea8ab71c9db880fc9c1c5a4e72ca66a6719fb194988``
and worksheet SHA256
``f8d6d18ddd0fb39997e4aac82615be5b49ca5b48154e4eb60b5ba2f5d7bbdde6``.
Those files remain unchanged. The correction concerns the audit's port mapping;
the original canonical VI was not changed.

The exact canonical LabVIEW12 artifact ``4ab066c4...`` and frozen native20
baseline ``8f48e7ae...`` both contain four unwired primitive error outputs:

====================  ======  ========  ===============
Operation             Node    Output    Output objFlags
====================  ======  ========  ===============
Obtain stop queue     495     532       65
Dequeue stop queue    397     745       1
Variant To Data       664     677       1
Flatten To String     310     316       1
====================  ======  ========  ===============

All four resolve to ``Cluster{Boolean,NumInt32,String}``, have output bit 0 set,
and have no signal. Variant To Data term 673 is the **error input**, with
objFlags 65536 and output bit 0 clear. The earlier identification of 673 as an
output was wrong. Flatten To String output 316 was omitted from the earlier list.

For all four actual outputs, local terminal bounds are
``(top24,left24,bottom32,right32)``. Variant input 673 instead occupies
``(top24,left0,bottom32,right8)``. Bounds are diagram-local, not screen coordinates.

Native20 baseline qualification
------------------------------

Frozen VI SHA256:
``8f48e7ae30ff3d32b986f86bd606a2803669c8511c602ff2855d36fff74f6ffa``;
20,288 bytes. It retains all 58 wire endpoint lists, all 19 primitive opcodes,
all 15 literal payloads, all primitive port-UID mappings, all seven unassigned FP
connector mappings, and the Boolean Case range map from canonical ``4ab066...``.
The comparison covered 176 typed heap objects with no ordinary resolved-type
shape difference. Native version/cache/layout changes do not consume errors.

``DefaultErrorHandling=1`` remains unchanged. All bad-node/signal/subVI/compile
flags, RunOnOpen, and IsReentrant are 0. No Run, Call, UI, or hardware action was
performed by this audit. Only the root-authorized exact native byte copy was
created; no RSRC serializer or source overwrite was used.

The previous queue, timeout, ACK, stop-order, owner-lifetime and inline-image
findings remain applicable. In particular, the address literal remains
``127.0.0.1`` and port 8768. This erratum grants no runtime approval. Future native
indicator wiring must be checked against a separately saved artifact.

Machine-readable directional evidence and full baseline comparison:
``TRANSPORT20_BASELINE_AND_ERROR_OUTPUT_ERRATUM.json``.
