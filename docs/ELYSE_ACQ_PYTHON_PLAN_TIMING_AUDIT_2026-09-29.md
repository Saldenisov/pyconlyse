# Acquisition procedure timing: source vs Python plan (2026-09-29)

The [read-only wait comparator](../tools/compare_acq_plan_waits_to_source.py)
compared literal root-VI `Wait (ms)` nodes in event cases 3–25 with waits
declared by the local non-actuating `PROCEDURE_PLANS` (including sweep and
counter-poll periods). Twenty event cases have matching *multisets* of
literal durations. Three have one additional 150 ms node each in the saved
VI: cooling stop (case 4), general-modulator stop (case 6), and focal stop
(case 10). A duration multiset does **not** prove execution order or elapsed
time: nested loops repeat, calls can block, and nodes in one LabVIEW frame
can execute concurrently.

Raw-diagram inspection distinguishes the three extra nodes:

- Case 4, ordered sequence `7929` frame 4 (`diag 22060`): the final
  `C3_OUT_DIO96[4]=True` local assignment and a 150 ms Wait are separate
  direct nodes in the same frame. The next frame cannot begin before the
  Wait completes. The Python plan restores that bit then proceeds without
  representing this frame-completion wait. Thus its modeled timing omits a
  source barrier, although the LabVIEW assignment and Wait need not be
  internally serialized.
- Case 6, sequence `26556` frame 0 (`diag 26598`): the extra 150 ms Wait
  shares a frame with a nested focal-off flat sequence. Case 10, sequence
  `23507` frame 0 (`diag 23518`), has the analogous topology. The Wait is
  not wired as a sequential step after the focal call. Adding 150 ms to a
  serial Python plan would be a **different** schedule, not a direct copy.

No plan wait was changed based only on this static observation. A faithful
scheduler needs explicit parallel-frame semantics or a justified elapsed-time
abstraction, then pure-code tests for completion and cancellation. The
comparison does not establish physical pulse width: DIO card commits occur
in a concurrent acquisition loop. No VI or hardware was run.
