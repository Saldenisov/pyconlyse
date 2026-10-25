ELYSE supervised test programme: Monday, 26 October 2026
========================================================

Purpose and working method
--------------------------

Exercise the normal experiment sequence through one XP application on
``10.20.30.10``, one Everest Tango device
``elyse/acquisition/telemetry`` and the Pyconlyse web controls. The operator
remains at the installation and can use the hardware controls. The assistant
follows telemetry, requests one agreed operation at a time and records the
result. Start directly with the Python application in IDLE, then local
Initialize and native operation. No VI start, VI reference recording or live
VI-to-Python handover is scheduled. This document prepares the session; no
deployment or hardware action has been performed for its preparation.

The session uses normal operating procedures and existing protections. It
does not add repeated permission questions, deliberate cooling failures,
network-disconnection tests or repeated restarts. Required web authorizations
remain part of the implemented command path. Operator presence does not
establish an unknown feedback polarity, serial identity or voltage tolerance.

After each operation, report only: command result, relevant measured change,
remaining discrepancy and the next step. A short operator reply confirms the
physical effect. Advance after the procedure completes and observations agree;
do not use a fixed ten-second interval as equipment settling time. Capture an
approximately ten-second observation window where practical, extending it for
the actual equipment response. No automatic next stage or voltage increase.

Software preparation before the operator session
------------------------------------------------

The source baseline is ``791f1bff`` plus the r9 synchronization changes on
``codex/acq-unified-telemetry-v6``. It is an offline candidate, not a statement
of the currently installed version. Complete the following preparation before
calling the full experiment path ready:

* Prepare a matched XP, Device Server, web-backend and frontend update with a
  restorable previous set of files, properties and configuration. Preserve the
  existing rich ELYSE web layout. The historical deployment script and an
  isolated frontend bundle do not constitute this update.
* Verify the existing one-use web authorization path and restrict direct Tango
  command access to the intended trusted caller. Do not add another XP bridge
  or Device Server. Leave commands disabled during installation and read checks.
* Check actual commissioning evidence for HT feedback/zero tolerance,
  Canon/Section feedback polarity and Chroma identity/quiescence. The current
  ``_start_permit`` requires this full-stop qualification even for General.
  It raises ``Start blocked: full HT/Chroma/cooling shutdown not commissioned``
  when evidence is absent. Do not promise General will run merely because NI
  initialization succeeds, or set verification flags solely to pass this gate.
* Recheck the matched capability set: 24 named operations, runtime protocol 2,
  policy 2 and envelope 1. Check the local window has only Initialize,
  Deinitialize and Stop server. Keep the existing single recorder running;
  identify its actual destination and verify fresh commits without opening an
  actively written HDF5 file.

Open release issues are described in
``ELYSE_EXPERIMENT_COMMANDS_2026-10-24.rst`` and
``ELYSE_SINGLE_ACQUISITION_WEB_2026-10-24.rst``. Missing preparation narrows the
session to the parts that are ready; it is not permission to bypass admission.

Session inputs
--------------

Record these once at the start, rather than asking again before every stage:

* Installed revisions; XP boot/session ID; recorder/archive identity.
* Operator-selected HT target, intermediate values and dwell periods, using the
  installation's operating procedure. No values are supplied by this document.
* Verified measured-zero tolerance and the feedback used to establish HT OFF.
* Desired Faraday 1/3 physical positions and mirror position. The term
  ``open`` must be resolved to the physical action before a pulse is requested.
* Requested C10 synchronization output, delay and width in microseconds. Keep
  drafts distinct from applied values; the named command stops and restarts
  an already running counter on the current owner.

Use Europe/Paris timestamps with an explicit UTC offset. Monday is 26 October
2026; the date uses UTC+01:00 after the daylight-saving change. Keep UTC source
timestamps as well. The CSV template alongside this programme starts empty;
planned steps must not be presented as observed results.

Phase A: Python initialization and telemetry
--------------------------------------------

1. Begin with the single Python application in IDLE and zero native NI tasks.
   Confirm the installation state and the existing ownership checks before
   Initialize. Acquisition VI must not own the cards; absent VI telemetry alone
   is not proof that they are free. Without a producer, pre-initialization
   telemetry is expected to be unavailable; do not wait for a VI stream.
2. Press local Initialize once. Follow the driver-call trace through completion;
   record task inventory, startup status and errors. Initialization applies
   source startup AO/DO and starts the source-selected counters; it is not a
   read-only action. A partial initialization does not justify a second click.
3. Verify ``PYTHON_NATIVE`` and RUNNING, then verify successive receiver counts,
   source timestamps and live bank observations at XP, Everest and the web.
   The standard envelope remains 27 banks; native
   support currently populates at most 14, with 13 unsupported bank entries
   explicitly unavailable (``null``/``-80001``). Supported inputs can also become
   unavailable when stale. These are not missing network packets. Saved VI
   evidence may support later comparison, accounting for measurement time;
   acquiring a fresh VI reference is not a step in this session.
   EPS/DPS are software memory; AO/DO command memory is not electrical readback.
4. Establish the HT baseline and current cooling state. The source startup
   ``C9NI6703[0]`` command is 6.5 kV; it does not establish measured voltage or
   permit energization. Verify the measured value and supply state separately.

Phase B: normal staged start
----------------------------

Use this order. The exact named operation is included so the web label,
Device Server receipt and XP procedure can be matched without ambiguity.

1. General: ``modulator.general.start``. Observe the cabinet feedback and
   operator confirmation, then verify both Canon and Section circulation.
   The runtime performs General, then ``cooling.start`` and circulation
   verification within this request; no second cooling-start click is planned.
   General supplies the circulation cabinet; normal water flow is checked
   before the later energized stages, not assumed from General's EPS bit.
2. Chauffage: ``chauffage.start``. Observe the relevant C4 feedback and analog
   response. Confirm the physical effect and actual cooling indications.
3. PREMA: ``prema.start``. Record its input transitions and software sequence
   completion separately. Resolve any disagreement before Focales.
4. Focales: ``focales.start``. Verify supply power and the qualified serial
   transaction/result. Operator labels are Focale3 Port1, Focale2 Port2,
   Focale1 Port3; these are not verified Windows COM numbers. Use the confirmed
   port map. Do not open a second serial connection while the owner uses it.
   A read query is still a transmitted command; no opportunistic serial probing.
5. Relais HT: ``relays_ht.start``. Check the relevant raw input transitions
   against verified polarity, then the operator's physical observation.
6. HT supply: ``alimentation_ht.start``. Verify measured HT/current, actual
   supply feedback and the command image; do not infer voltage from the setpoint.
7. Modulator pulses: ``modulator_impulse.start``. Check current-owner counter
   start completion and the available independent indication. Both this step
   and successful HT-supply start must precede any HT increase.
8. HT changes: ``ht_voltage.set`` with each exact operator-selected value.
   Record command, measured HT/current and settling response after each change.
   No upward auto-ramp. The accepted [0, 20] kV encoding range is not an operating
   recommendation. The initialized 6.5-kV command must already be accounted for
   before the HT supply is energized; there is no assumption of a zero start.
9. Beamline, when requested for the experiment: qualify and exercise Faraday 1
   and 3 independently, then the mirror as needed. Available source intents are
   ``faraday_1.en_pulse``, ``faraday_3.en_pulse``,
   ``laser_mirror.en_pulse`` and ``laser_mirror.hors_pulse``. No Faraday HORS
   intent is currently qualified. Faraday 3 feedback labels disagree between
   source schemas. If the required position needs an unavailable direction,
   record that software gap and use the operator's established local control;
   do not rename EN as open or silently substitute a bank write.

Synchronization adjustments use the Synchronization tab and
``counter_timing.set`` with an explicit C10 counter, ``delay_us`` and
``width_us``. Apply outputs already running after General/cooling verification.
C10/ctr3 and ctr4 are not started on Initialize; their settings can be drafted
earlier but applied only after Marche impulsions modulateur. Changing either
invalidates the HT-increase sequence proof, so repeat the explicit Marche
impulsions step before requesting an increase. The confirmed source writes
initial delay and low ticks from delay, high ticks from width, with DBL*20 and
ties-to-even conversion. No frequency-only or C11 command is qualified.
Record the exact structured request in ``requested_sync_json`` in the CSV.

Throughout stages 1--9, watch measurement ages as well as changing EPS/DPS.
Transport updates during a long command do not establish a new NI sample.
Execution-time measurement sampling is disabled by default pending aggregate
read-timing qualification; an honest stale input during a procedure must be
distinguished from a stopped publisher. Record this limitation rather than
refreshing the sample timestamp or adding a parallel NI reader.

Phase C: normal stop with cooling retained
------------------------------------------

1. The operator announces the stop. Mark its time and the last stable HT value.
   To retain General for cooldown, use the separate named operations: explicit
   decreasing ``ht_voltage.set`` requests toward the agreed 8-kV handoff when
   required, then ``alimentation_ht.stop`` and ``modulator_impulse.stop``.
   Never raise a lower command to 8 kV; a fresh measured zero skips reduction.
   Verify fresh measured zero, supply OFF and both counter-stop results before
   treating HT as stopped. The staged route requires operator-selected values;
   there is no standalone automatic HT-ramp-and-stop intent. The automatic
   8-kV preamble is part of the full General stop, which would also stop General
   and is therefore reserved until after cooldown. This preamble is an explicit
   Python extension, not original VI event-6 equivalence.
2. Stop Focales, Relais HT, PREMA and Chauffage with their named ``.stop``
   operations, following the installation's normal procedure. Record partial
   failures individually. General remains ON while the operator retains water
   circulation for cooldown.
3. The previously used 2--3 minutes is a planning allowance, not a measured
   thermal acceptance criterion. Follow actual temperature trends and the
   operator's cooldown decision. Continue recording during this interval.
4. After cooldown, request ``modulator.general.stop`` and verify the final
   cabinet, stage and HT observations. Its full-stop sequence includes the
   remaining stage stops; keep receipts for any redundant stop calls. Do not
   use Deinitialize or Stop server as a substitute for General Arrêt.
5. Deinitialize only after the stop result and physical state agree. Confirm
   native tasks are released. The same application returns to the VI-listening
   mode; absent VI data must appear unavailable, not as a running VI. Leave the
   application in IDLE unless closure is requested. Recording continues unless
   the operator explicitly requests its termination.

Handling a discrepancy during the session
-----------------------------------------

If a physical response is wrong, the operator uses the appropriate established
hardware control immediately; no HTTP timeout needs to expire first. The
assistant stops issuing further start/motion/increase requests and preserves
the telemetry and command ID. A timeout/UNKNOWN receipt is not proof that
nothing happened, so the command is not resent. A command completed in software
is not substituted for missing physical feedback. Continue diagnosis from the
original owner and evidence; do not clear ownership records, restart the owner
or launch VI against retained tasks to make an error disappear.

The circulation alarm/countdown requirement remains 120 s with immediate
identification and logging of the failed circuit. Deliberate pump interruption
is outside this normal experiment programme. Existing protection behaviour
must not be disabled for this session.

Evidence and acceptance
-----------------------

Record one CSV row per step using
``ELYSE_MONDAY_TEST_LOG_2026-10-26.csv``. For each actual command retain the
command ID, XP session/revision, value, receipt transitions and timestamps.
Include raw C3/C4/C5 changes and available EPS/DPS with bank quality, rather
than screenshots of colours alone. The continuous archive supplies the full
trace; the CSV provides operator annotations, not a second telemetry recorder.

Track ``C2NI6071E[7]`` (measured HT), ``C2NI6071E[15]`` (HT current),
``C9NI6703[0]`` (command HT), ``C1NI6071E[0]``/``[8]`` (Canon/Section
temperatures), EPS 8/14/20/32/26/45/52 and qualified cooling feedback. Interpret
raw Boolean levels only with the verified polarity. Record initial values,
transition times, peak/settled observations and any quality gap. These channel
labels require the site calibration/feedback qualification above.

The session demonstrates the steps actually observed: direct Python
initialization without overlapping NI owners, command delivery through the
same device, physical responses consistent with measurements, HT changes and
shutdown with cooldown.
Mark unavailable directions, missing qualification and any untested step
explicitly. Do not label the entire VI migration complete from one successful
start/stop, or claim every original source packet was archived by a latest-only
transport.
