Synchronization through the unified Acquisition device
======================================================

Implemented scope
-----------------

The r9 candidate connects the ELYSE Synchronization tab to the existing
web facade, ``elyse/acquisition/telemetry`` Device Server and retained XP NI
owner. The named operation is ``counter_timing.set`` with exactly::

    {"counter": 2, "delay_us": 1.25, "width_us": 3.5}

These numbers are a software-contract example, not an operating prescription.
The selector is an integer C10 output 0--7. Both timing values are explicit,
positive finite numbers in microseconds with nonzero, unsaturated I32 tick
encodings. Unknown fields, C11 selectors, raw banks, Boolean values, nonfinite
numbers and oversized integers are rejected before dispatch. No driver can be
selected through a request. The three local GUI buttons and 27-bank envelope
are unchanged. The matched capability set now contains 24 operations.

.. list-table:: C10 output names from the saved initialization plan
   :header-rows: 1

   * - Counter
     - Source label
     - Started on Initialize
   * - 0
     - Synchro PCI6071E
     - Yes
   * - 1
     - Synchro variable machine
     - Yes
   * - 2
     - Synchro mesure WCM
     - Yes
   * - 3
     - Synchro modulateur
     - No
   * - 4
     - Synchro HF
     - No
   * - 5
     - Synchro cible de Faraday
     - Yes
   * - 6
     - Synchro oscilloscope
     - Yes
   * - 7
     - Gate 1 / 50 Hz mains synchronized to 20 MHz pilot
     - Yes

The table identifies source wiring, not measured output timing. No independent
frequency-setting command or C11 route has been qualified. Those old placeholder
fields are not presented as active controls. Drafts start blank rather than
inventing current delay/width values from absent telemetry.

Source execution and admission
------------------------------

``acquisition_counter_timing.py`` retains source VI SHA256
``6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF``
and helper SHA256
``4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211``.
The remote adapter reuses its injected source executor: read PulseDone with
the saved nominal 1-ms waits and iteration limit, stop the selected retained
counter, write initial/low/high ticks, then restart the same counter. Both
initial delay and low time use the requested delay; high time uses width.
Conversion remains DBL*20, ties-to-even rounding, I32 then U32. Remote numeric
bounds refuse signed wrap and saturation; the local full-bank source API keeps
its recovered conversion and selector behaviour.

Typed requests do not claim a known 33-field local39 image. The adapter uses a
private scratch image solely to feed the selected pair to the source executor;
other scratch slots are inert padding. Reset/publication callbacks remain
private, scratch arrays are removed from the remote report, and
``shared_bank_observed=False``/``shared_bank_published=False`` remain explicit.
The original local full-bank API and its independent reads/publication are
preserved. Native ``C1011NI6602`` telemetry is not fabricated from a pair.

Additional remote policy requires current native inputs, General and confirmed
cooling, commissioned timing/full-stop controls and an already running selected
counter. The existing owner checks that selection again around preflight. This
prevents an Apply action from silently energizing a stopped pulse source;
it is Python admission policy, not a recovered hardware interlock. Modulator/HF
timing can be drafted beforehand, then applied after the explicit pulse-start
stage. Changing counter 3 or 4 invalidates the HT-increase sequence proof;
another successful explicit pulse-start sequence is required before an increase.

Runtime admission copies the three values. The owner rechecks input age before
entry. General Arrêt supersedes a queued timing update. A partial property write
retains uncertainty and NI ownership, prevents a restart through uncertain
properties, and is not replayed. The source executor does not reproduce native
LabVIEW error dialogs or infer a Continue response. Driver calls remain
unpreemptible. No additional NI reader or worker owns the same tasks.

Web behaviour and authority
---------------------------

The mounted Synchronization panel provides channel selection, delay/width
drafts, exact tick conversion and Apply. It shows only recorded property-write
memory as the last commanded ticks, never physical readback. Counter state and
properties come through ``runtime_json`` and the same control GET route.

The shared confirmation freezes the structured value, boot, revision and
capability set. Value comparison is structural: an equal object reconstructed
by React/polling does not invalidate confirmation; changing channel or either
timing does. A lost reply leaves the structured intent in the existing bounded
ledger across remounts without resending it. The existing protective-stop slot
is unchanged. The command client validates timing before consuming an approval.

One-use authorization binds the exact nested counter/delay/width values as
well as the existing device, operation, session and revision. The external
policy needs a permitted ``acquisition.command.counter_timing.set`` execute
operation, with a bounded object schema for the three timing fields inside
``args.value``. No live policy or role is granted by this change. Missing policy
continues to refuse dispatch. Direct-Tango authorization and coordinated
XP/DS/web rollout remain the existing release conditions.

Independent transport publication continues during owner operations; old NI
samples are not made fresh by a command/progress notification. Execution-time
sampling defaults remain unchanged. A nominal 22-ms poll-wait total is not a
hard timing limit or proof of native-driver response time.

Validation and delivery
-----------------------

Validation uses injected Python owners, temporary authorization records,
private loopback transport and temporary package/build directories only.
No XP installation, VI operation, NI ownership change, serial transaction,
live Device Server command, recorder change or database migration occurred.
The dirty live checkout and rich ELYSE layout remain untouched.

The Monday programme and observation template now include the structured
synchronization request and distinguish startup counters from modulator/HF
counters. The candidate still requires a coordinated deployment into that live
layout, the existing command authorization and site qualification. A passing
software test does not establish physical pulse timing or operating limits.

Acceptance results
------------------

Actual CPython 3.4.4 x86 ran 354 tests in 28.720 s: 353 passed and one optional
dependency test was skipped. The final oversized-integer validation change was
also checked by rerunning all 11 synchronization tests on that interpreter.
The final Python 3.12.14 software-only regression, with ``--deny-network``,
passed 684 tests in 55.37 s. Nine optional/platform tests were skipped,
including seven unconfigured PostgreSQL integration cases. Two Windows
symlink-creation tests remain deselected because of the previously observed
``WinError 1314``; they are not claimed as executed. The 24 existing warnings
remain. Counts overlap and must not be added together.

All 22 frontend Jest suites passed, 242 tests, in 15.843 s. Changed JavaScript
passed strict linting with no source findings. Tests cover the actual ELYSE
tab/provider, exact nested values through authorization and transport,
structural confirmation comparison, changed values, uncertain replies across
remounts, same-owner execution, cancellation, a superseding General stop,
freshness recheck and partial property-write failure. The real external
approval implementation is exercised with temporary policy/nonce fixtures;
each nested parameter is bound and a consumed approval cannot be reused.

The optimized build succeeded with seven existing hook warnings in five
unchanged components, old toolchain notices and the existing bundle-size
warning. The new/changed controls have no source lint findings.

Development artifacts, not installed releases:

* XP package: 68 files under
  ``C:\Users\elyse\AppData\Local\Temp\elyse-sync-r9-final-0febf0f3bd344a01978ff44c896f42d0``;
  sibling ``-everest`` package: 44 files. Both retain commands disabled by
  default and require the exact 24-operation set. Isolated Everest imports
  confirm the new pure validator is included without importing NI.
* Cold packaged Python 3.4 acceptance passed all 27-bank, signed-loopback,
  VI/native-exclusion and typed-value/default-disabled checks. Build ID:
  ``703e150b66e809d8c9e644cb1fb3a10c32832181f66769ce9f11b9cd127262e0``.
  It reports cards initialized False, hardware commands sent False and live
  Everest contacted False; manifest hashes were verified.
* Frontend output:
  ``C:\Users\elyse\AppData\Local\Temp\elyse-sync-web-r9-final-7f67d8d9f5d64c31834f66d10a1b30ac``.
  ``static/js/main.f76262c8.js`` SHA256:
  ``DD38CF17E6AA17D2EEC9307CC7538226493FFE9B34340B17E2997F42C3B6B87A``.
  ``asset-manifest.json`` SHA256:
  ``D559A8DA286E298B9E348397A184EEEC2977A425F03E677E1DDB8371A7DB5451``.
