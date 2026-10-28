Individual helper proof: no runtime qualification
================================================

These camera proof assets contain offline evidence; no VI binary, original
main LLB, NI library, image array, or live pixel data is included in this proof
subset. This directory also contains the separate native12 sync package,
documented in `README.md <README.md>`_. The existing canonical observer bundle
in the parent directory is unchanged.

On 2026-10-28, the private Epoch VI passed front-panel/block-diagram Open and
native Save in LabVIEW 2020 32-bit. Its saved binary SHA256 is
``f6bb97d1eab2f87ca932391219fefb04e88e089db9057445f814b1d981ebcc01``
(30,736 bytes). RunOnOpen, BadCompile, SourceOnly, and IsReentrant were false.
No VI was executed. LabVIEW 2012 export/Open/Save and physical camera operation
remain unqualified for this new helper.

``epoch_native2020_semantic_snapshot.json`` records the saved Epoch's bounded
graph: 101 wire endpoint lists, 14 constant terms, and 47 source-node entries.
It contains no executable LabVIEW code. The portable evaluator checks 3,840
combinations against the lifecycle model, including failed Setup invalidation,
stale-run protection, zero/regressed clocks, unknown actions, full U32 channel
values, and original image/error identity. This is source-graph analysis;
it does not demonstrate LabVIEW execution or persistent shift-register behavior.

The complete SetupObserve wrapper was then authored and saved entirely through
LabVIEW UI, without serializer writes or Run. The authoring binary SHA256 is
``1de01a7e5d18fa231866dfe257dc268b067de58e4eefa54a9b10438682cf202c``
(20,658 bytes). ``setup_native2020_semantic_snapshot.json`` captures its actual
saved wiring. Forty-eight offline cases verify action1, exact RunStamp/channel
forwarding, SetupOK derived from original error.status, image/error identity,
and reply forwarding. Epoch replies are explicitly stubbed in this wrapper
check; it does not execute Epoch or demonstrate native FGV persistence.
The final-name SetupObserve copy also reopened its front panel and block diagram
in a fresh project within the same LabVIEW process. A process restart and
LabVIEW2012 export/Open/Save were not verified.

Epoch state is ``(RunStamp,capture,actual_channel,valid)``. Begin clears capture
validity; matching successful Setup samples UTC and preserves actual U32 channel
without remapping or clamping. Failed matching Setup invalidates state. Read
preserves state. Stale End cannot invalidate a newer run. The four ordinary
camera ring choices are documentation, not an added physical range restriction.

FrameTap's separate six-field work-budget model requires a valid same-run epoch,
successful original Grab, ordered UTC, a new FrameCount, and at least 1,000 ms
between owned copy attempts. New capture resets frame identity while retaining
the rate budget; new run resets both logically. U32 tick subtraction wraps.
Every owned copy attempt consumes budget, including private copy/queue errors.
Pre-copy skips preserve all state. Tests sample the actual pre-copy tick as the
next deadline origin. FrameTap native implementation/qualification is pending;
queue capacity 1 and receiver throttling alone do not bound image-copy work.

The scalar regression distinguishes four-byte U32 data from a five-byte buffer
with an erroneous zero prefix. Native LabVIEW consumed the first four bytes,
turning intended literals 1/3 into 0. The corrected native-save artifact retained
exact four-byte literals 1/3 and U32MAX. The evaluator refuses nonzero data after
the scalar width and preserves tolerated trailing zero padding.

Reproduce using CPython 3.4 or later, without LabVIEW or third-party packages::

    python tools/labview_camera_helper_model.py legacy/labview/supervision_telemetry/individual_helpers/epoch_native2020_semantic_snapshot.json
    python tools/labview_camera_helper_model.py legacy/labview/supervision_telemetry/individual_helpers/setup_native2020_semantic_snapshot.json --kind setup
    python -m unittest tests.unit.test_labview_camera_helper_model

Both snapshots and native source identities are pinned in the verifier. Twenty
focused tests include semantic tampering refusal and a 10,001-call model trace
that admits eleven attempts at 0,1000,...,10000 ms even when every private copy
and queue diagnostic reports failure. These are offline graph/model results.

Process-restart/export and lifecycle caller checks remain separate. Source VIs
that have not passed their own Open/Save and export checks must not be promoted
because the Epoch proof passes. Main integration will be assembled natively on
XP later; no main VI, NI task, device state, or service is changed by these tools.
