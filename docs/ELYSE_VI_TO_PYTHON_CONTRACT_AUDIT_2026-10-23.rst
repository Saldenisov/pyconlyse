Acquisition / Supervision / Python contract audit
================================================

This document retains the historical baseline findings. Subsequent EPS/DPS
publication and qualified execution-telemetry changes are documented in
``ELYSE_EPS_DPS_EXECUTION_TELEMETRY_2026-10-23.rst``; they are not deployed to XP.

Decision and boundary
---------------------

The source contracts are substantially understood, but the current unified
Python server is not a fully qualified replacement for the complete experiment.
This audit compares the original Acquisition and Supervision artifacts with
Python baseline ``dd2f328e`` (deployed r5). Four delegated read-only reviews
covered initialization/reads, stage admission/faults, setpoints/Chroma/counters,
and native telemetry/command integration. Source validators and synthetic
adapters were used; no live NI, XP, VI, serial, Tango, web, archive or equipment
operation was performed for this audit.

The subsequent user instruction, ``remove averaging then``, changes the target:
the candidate now deliberately selects the last sample of each finite block
instead of calculating a mean. This is an approved Python measurement policy,
not restoration of VI numerical equivalence. It has not been deployed to XP.
Existing VI forwarding and its VI-side processing are unchanged.

Evidence identity
-----------------

The historical evidence root is ``C:\dev\pyconlyse``. Original source exports
are in ``legacy/xp_acq_agent/data/source_exports``. SHA256 identities:

* Acquisition root VI:
  ``6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF``.
* ``0_ACQ_ELYSE_XML_sha6fe8.zip``:
  ``6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527``.
* ``ACQ_17_original_members_XML_20261001.zip``:
  ``645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F``.
* Original Supervision VI:
  ``B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B``.
* Original Supervision BD XML:
  ``F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7``.
* Supervision extraction receipt, ``Supervision/analysis/lvkit_eval/
  parser_release_20261003/00.json``:
  ``FE605F15D9A481749C945AF7F406315C73BA78E572C8225A6658EC4396042FD5``.

The original Supervision identity must not be replaced with an earlier modified
copy merely because both files have the same name. Static LabVIEW 2020 import
images corroborate selected graphs; they do not establish LV2012 execution.

Initialization and measurement contracts
----------------------------------------

* The 11-card topology corresponds to 21 tasks: eight counter, three AI,
  six DIO and four AO tasks. C1/C2/C11 supply 64/64/16 analog channels;
  C3/C4/C5 supply 56/64/56 Boolean inputs and 40/32/40 Boolean outputs.
* C1/C2 source initializer frames 2383/944 configure RSE, 5000 Hz,
  finite 10 samples, OnboardClock and rising PFI0 triggers. The recovered
  C1 channel ranges and all 128 C1/C2 calibration coefficient pairs match
  the active Python configuration/CSV.
* Source NI6071E read calls 269/1269 calculate means. Root callers
  19337/647/55456 explicitly request 1000 samples/channel, although the
  initializer requests finite 10. Baseline r5 instead reads and averages
  10. These contracts must not be conflated. This audit does not resolve
  the installed driver's behavior for the source's differing counts.
* Source NI6602 sequence 3868 configures and starts selected counters inside
  the per-counter initializer frames. Python configures all 21 tasks first,
  then starts 0/1/2/5/6/7. Selection matches; startup ordering differs.
* C11 initializer property node 2561 explicitly assigns properties 6410/6182
  (RelativeTo/AutoStart); Python does not assign those C11 properties.
  Source C11 read 1269 uses timeout -1 and raw scaling False. Python uses
  bounded reads and a fixed 16-channel projection. C11's current calibration
  coefficients are identity, so the generic scaling currently changes no
  C11 numeric values. Downstream WCM/MeanPtByPt/VAM-A behavior is not native
  telemetry parity.
* Forty logical AO and 112 DO startup values match the resolved source
  literals. Diagram captions for C3/C5 are misleading; resolved bank wires,
  not captions, determine assignment. Python applies DO then AO without the
  source's pilot/first-AI-read composition.
* Source pilot error handling can clear/recreate C1/C2 after a read error.
  Python deliberately fails closed and retains unresolved handles instead.
  Explicit Python task cleanup is not equivalent to the source's final
  PSP/TPG close frame, which contains no general NI Stop/Clear or zeroing.

Python implementation anchors: ``hardware_plan.py``, ``input_tasks.py``,
``hardware_tasks.py``, ``CardBackend.initialize`` / ``read_snapshot`` in
``acquisition_backend.py``. These are under
``legacy/xp_acq_control/elyse_agent``.

Requests, stage writes and actual admission
------------------------------------------

Supervision's five page producers require all 29 sampled local DPS bits to
be False; HT/HF/Fluides have additional adjustment-button gates. This is
request serialization, not an independently verified machine permit.
Page Modulateur unbundle 32126 feeds DPS bundle 33466. Acquisition's reviewed
start handlers test Boolean NewVal=True; they do not test the displayed
klystron-water/EPS indicators as entry permits. EPS OK fields are literal
software-completion assignments, not physical feedback.

Representative source traces:

.. list-table:: Request-to-command crosswalk
   :header-rows: 1

   * - Operation
     - DPS / ACQ event
     - Command and requested waits
   * - Chauffage start
     - 4 / 12
     - C4_OUT[3] pulse, then [2] reset; 150/3000/150/100 ms
   * - PREMA start
     - 6 / 13
     - C4_OUT[5] pulse, then [2] reset; 150/500/150/250/100 ms
   * - Focales start
     - 10 / 15
     - C4_OUT[7] pulse, 29 s wait, helper 48404, 1.5 s wait, [2] reset
   * - General stop, event 6
     - 3 / 6
     - Chroma OFF helper, then C4_OUT stop fields 8/17/6/4/1

The reviewed raw cooling trip is::

    (C4_IN[19] OR C4_IN[38]) AND (NOT C3_IN[0] OR NOT C3_IN[6])

It requests Canon/Section cooling stops on C3_OUT[1]/[4]; it does not directly
issue Chauffage/PREMA/Focales/HT/General stop. Absence of a software gate in
these graphs does not establish the cabinet's electrical interlock truth
table. Python commissioning gates and the requested 120-second cooling policy
are additional policies, not recovered source permits.

Setpoints, Chroma and distinct stop contracts
--------------------------------------------

* HT measurement is C2[7], source gain 2.44; HT current is C2[15], gain 0.22.
  HT command is C9[0], mapped by the original NI6703 writer to 0.5 V/kV.
  Source caller reader 10449 -> local12 writer 10472 is independent of AO
  writer 278. Whole-bank writes must preserve the other nine channels.
* Six original setpoint families / 20 arrow rules are reconstructed:
  Canon temperature C8[1], Section temperature C8[2], HT C9[0], preamp
  amplitude C8[6], HF attenuation C8[4], HF phase C8[3]. Current remote
  protocol has only one numeric operation, ``ht_voltage.set``. Other
  named setpoint routes are missing. Original HT arrows clamp 6..20;
  Python remote 0..20 is a different admission policy, not a safety range.
* Acquisition counter selectors 1..16 address /10/ctr0..7. Supervision
  selectors 17..32 address its own Dev1 counters on another computer.
  They must not all be routed to Acquisition. Python counter timing is
  local-only, and its RAM publication is not delivered counter-bank data.
* Both original Chroma helpers perform reset=True, then nonzero voltage,
  slew, current, output Boolean and Close. OFF is not a passive read or a
  zero-setpoint operation. Saved branch settings are F3 COM10/70V/15.1A,
  F2 COM11/80V/20.9A, F1 COM12/80V/13.73A; saved slew is 0.02.
* Historical read-only XP evidence already maps COM10/11/12 to Moxa
  10.20.30.51 Port1/2/3 and Focale_3/2/1 aliases. This corroborates the
  operator's port mapping. It does not prove current cable identity,
  responding instruments or baud. Chroma serial measurement getters are
  not implemented; native callback success still does not prove DC output.
* General event6, original outer controlled stop and the Python measured-HT
  extension are three different contracts. Original outer ramp compares
  command C9[0] strictly below 6.6 and decrements 0.1 per requested 500 ms;
  it does not verify measured zero. The Python 8-kV handoff, supply stop,
  pulse-counter stop and fresh zero/OFF checks are user-requested additions.
  Electrical feedback and a justified zero tolerance remain unqualified.

Native telemetry and operator surface are incomplete
---------------------------------------------------

``standard_banks.py`` currently populates five input banks and seven remembered
output-command banks. The other 15, including EPS, DPS and C1011NI6602, carry
null and application error -80001. Internal ``stage_state`` is not mapped into
those standard banks. C11 raw inputs do not substitute for counter data.

During EXECUTING, the native standard-bank mapper requires RUNNING and emits
unavailable values even when an internal execution sample exists. Therefore
27 envelope names do not establish continuous 27-bank experiment telemetry.
The receiver/web honestly preserve unavailable data as INCOMPLETE.

The protocol has 19 named operations, but counter timing and outer controlled
stop are local-only. ``AcquisitionCommands.js`` supplies value=null and is not
mounted by the current Elyse page; the existing page blocks non-telemetry
control clicks. A usable HT setpoint widget and complete stage-control wiring
are not established by the presence of server command methods. Native
commissioning flags and remote command enablement remain False by default.

Unaveraged candidate contract
-----------------------------

The new candidate is labelled ``acq-unified-unaveraged-inputs-20261023-v8-r6``:

Implementation and regression tests are committed as ``519a3b75``. The
historical r5 installer is not a deployment path for this changed source set.

* NI finite acquisition remains 10 samples/channel at the existing rate and
  trigger; one-sample finite support is not assumed.
* Every channel row and all returned samples must be complete, finite numbers.
  The last value, index 9, is selected without summation or averaging.
* C1/C2/C11 use the same selection policy; the HT shutdown measurement helper
  uses the same unaveraged reader. Calibration is applied once after selection.
* Backend provenance reports ``last_raw_sample_of_finite_block``,
  ``software_averaging=False``, acquired count 10 and selected index 9.
* The unused input-only probe adapter also selects the last sample; no
  acquisition adapter falls back to the historical pure ``channel_means``.
* Task timing, startup output images, commands, protection flags, zero
  tolerance, three GUI buttons and the 27-bank wire contract are unchanged.
* Only selected values are transmitted; this does not archive every raw
  hardware sample. VI-mode numerical processing is not modified. Changing
  software averaging can change noise/threshold crossings and still requires
  supervised qualification before enabling native controls.

Validation and next work
------------------------

Audit checks executed on development files only:

* Eight hash-pinned initializer/read/startup/runtime source validators passed;
  two additional inert coefficient/startup comparisons passed.
* Stage-admission and running-fault writer censuses, 16-procedure catalog and
  original Supervision DPS-reference checks passed. A Python 3.4 mock smoke
  completed 49 assertions/checks, not 49 separately discovered test methods.
* Original Chroma, NI6703 and NI6602 graph validators passed; 94 Supervision
  display projections and 28 parameter-page unit tests passed. A Python 3.4
  mock smoke completed 31 assertions, not 31 unit test methods.
* Current native telemetry/dual-mode/control regression: 61 tests passed on
  Python 3.12.14, one warning. This does not qualify native hardware behavior.
* New unaveraged-input suite: 29/29 passed on actual CPython 3.4.4 x86 and
  Python 3.12.14. Cases include all three AI banks, final impulse versus mean,
  finite-prefix overflow, malformed blocks, timeout/driver failure, single
  calibration, HT contact polarity, unchanged command memory and 27-bank shape.
* Combined candidate regression on CPython 3.4.4: 205 tests run,
  204 passed and one optional test skipped, 19.379 s. The modern telemetry,
  package, isolation and input subset passed 135 tests, one skipped and one
  warning, 21.01 s. Counts overlap and must not be added together.
* The 67-file candidate package passed Python 3.4 cold acceptance: every
  manifest hash, signed loopback ACK, 27 banks, dual-mode source exclusion
  and non-waiting telemetry projection. Native library loads were forbidden;
  no card initialized and Everest was not contacted. Candidate build ID:
  ``7de744deacbe8b6fbacb3c90039d42af02c70c9a87a924a3cd385d6e67d0703b``.

Next implementation work is distinguishable from physical qualification:
native status/counter producers; fresh telemetry during procedures; mounted
operator controls and named setpoints; explicit C11 properties and startup
ordering decisions; feature-specific HT/Chroma/counter tests in the release
branch. Physical follow-up must establish cooling/interlock polarity, serial
identity/baud, measured HT zero criteria, actual output response and fault
shutdown with an operator present. No such physical check is authorized or
performed by this audit or the unaveraged change.

The historical Everest deployment CLI also needs an enforced approval/change
identifier, dry-run preflight and a tested restore path before future use.
Its docstring alone is not an execution gate. No deployment CLI was run here.
