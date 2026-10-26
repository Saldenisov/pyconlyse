Optional local SuperVision initial synchronization profile
==========================================================

Local configuration may contain ``initial_sync_values_us``: exactly16 finite,
positive delay/width values in SuperVision counter order0--7. Omitting the
field retains the original initializer's saved constants and per-frame
configure/start order. No file, VI control, telemetry bank or remote command
automatically selects an override. The same three GUI buttons remain.

The field flows from the validated local GUI configuration through the
existing ``trusted_service_options.sync`` to ``SupervisionSyncService`` and
then ``SupervisionCounterCard.initialize``. It is not an arbitrary factory or
remote profile interface. Service construction and adapter initialization both
validate the full profile before any task construction; invalid values do not
partially fall back to saved constants. Null is rejected in configuration;
omit the field to use source defaults.

Encoding preserves the source factor20 and signed-I32 unsaturated tick bounds.
Nearest-even integer conversion matches the adapter's existing timing-write
policy; values that encode zero ticks are rejected. Only LowTicks/HighTicks
are overridden. InitialDelay stays0, rising PFI10 start trigger and rising
external PFI11 timebase stay unchanged, with low idle, retriggering and finite
one-sample timing. No external clock frequency is programmed or measured.

For an explicit override, all eight counters are configured before any is
started. A configuration failure starts zero counters and retains every task
already returned by the driver. After successful configuration, starts occur
in counter order. A failure partway through starts retains earlier started
tasks and all handles, with explicit uncertainty; it does not automatically
stop, replay, roll back or replace an owner. This preparation barrier is local
to the NI6602 card. The separate camera process remains independent.

Provenance and current selection
--------------------------------

``F:\ELYSE_Orchestrators\supervision_takeover_20261026\before_takeover_telemetry.json``
contains an Acquisition-forwarded 33-value counter observation at
2026-10-26T16:21:46.409487+00:00. Its SuperVision half includes IMAC4691.2,
LASER2000.5 and Detection1 delay1250. Those values are mirrored control memory,
not proof of the current SuperVision application's controls or native task
settings. The later direct SuperVision front-panel observation reported by
the parent at17:27 instead matches the saved source values: IMAC2176,
LASER2008.30 and Detection1 delay500. These observations must remain distinct;
the earlier capture is not rewritten or silently promoted to a takeover profile.

With the direct front panel matching source defaults, leave the optional field
omitted unless a separately reviewed canonical source/task observation calls
for an override. A copied bank can be fresh at its receiver while carrying
different-context or stale upstream control memory. A front-panel value also
does not independently establish physical pulse timing. The adapter reports
``initial_timing_provenance`` in its snapshot and synchronization memory;
an explicit profile is labeled
``explicit_local_VI_control_memory_not_physical_readback``.

Native boundaries
------------------

NI6602 uses the installed32-bit nidaqmx/NI-DAQmx API. No device reset or named
task deletion is introduced. The original counter2 Stop/Clear/ClearErrors
preamble is still not applied to an unknown task owned by another client.
Unreturned native construction retains an uncertainty sentinel. Successful
task.close plus child-process join is software cleanup evidence, not an
independent physical output acknowledgment. A hung/crashed native owner is not
automatically restarted merely because its parent PID or telemetry disappears.

The separate NI1409 ABI remains U32 interface/session identifiers, stdcall
ordinary NI-IMAQ functions and cdecl variadic imgSetAttribute2. This profile
change neither changes that ABI nor qualifies installed XP DLL behavior. A
failed session close retains its parent interface; no parent-close shortcut
is used to conceal unresolved child ownership.

Verification
--------------

Six additional RAM-driver tests cover all16 override encodings, all-eight
configuration before the first start, validation before driver loading,
eighth-counter configuration failure with zero starts, source factor/tie
conversion, service propagation and optional GUI configuration. The original
source-profile test still proves per-frame starts when no override is supplied.
The combined27 tests pass actual CPython3.4 x86 and Python3.12 with external
networking denied. No live NI call or deployment is performed by this work.
