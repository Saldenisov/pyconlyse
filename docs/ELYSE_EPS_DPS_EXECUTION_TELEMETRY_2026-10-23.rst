EPS/DPS and telemetry during Acquisition commands
================================================

Scope and result
----------------

The unified Python 3.4 candidate now publishes the complete 77-field EPS and
29-field DPS software images, including changes during native procedures.
Software observations and hardware measurements have independent sequences,
ages and validity conditions. A command heartbeat cannot make an old AI/DI
sample fresh. The 27-bank envelope, three local buttons, VI bridge exclusion
and control admission gates remain unchanged.

This change closes status publication and the qualified execution-sample path;
it does not establish full experiment equivalence. EPS represents Acquisition
software assignments, not independent equipment feedback or an electrical
permit. DPS represents admitted requests awaiting their source completion
tails. Neither bank proves that an external supply acknowledged a command.
Unported producers remain unported even though the complete initialized RAM
vectors can now be transmitted.

Only local source analysis, fake adapters and private loopback/subprocess
tests were used. No XP deployment, NI operation, running VI, live Tango/web
service, serial port, recorder or database was changed.

Source evidence and request lifecycle
-------------------------------------

The evidence root is ``C:\dev\pyconlyse``. Original exports are retained in
``legacy/xp_acq_agent/data/source_exports``. The source identity and wider
limitations are documented in
``ELYSE_VI_TO_PYTHON_CONTRACT_AUDIT_2026-10-23.rst``. Relevant SHA256 identities:

* Root XML archive: ``6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527``.
* Original helper archive: ``645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F``.
* Recovered procedure catalog: ``A9D821E7519EA50F6B35593E58C78129EC7D8A7BFEDCC06098E247BEF011A0B0``.

Root frame 33052 initializes both complete Boolean images to False through
constants 25379/28919 and local references 44/36. Python marks these literals
valid only after successful complete backend initialization. Construction,
partial initialization and task release cannot manufacture valid False banks.

The reviewed Supervision producers serialize requests through DPS. Their
display colours are not imported as acquisition permits. In Python, an
accepted request is recorded in the backend method after preflight, Boolean
NewVal=True and procedure setup, before source effects. A rejected request or
NewVal=False does not set a pending bit. Direct and isolated execution use the
same backend transition; transport code does not synthesize a second request.

Source completion assignments alone clear DPS. Cancellation or failure leaves
the last confirmed pending state in diagnostics rather than inventing a reset.
Automatic raw cooling trips do not synthesize user DPS requests. HT scalar
setpoints, counter operations and the outer stop extension are not relabelled
as DPS operations.

The missing General DPS publications are restored without extra hardware
writes: General Marche frame 35570 reads local DPS through 35614 and publishes
through 35620; General Arret frame 35146 uses 37688 and 37694. A source
publication snapshot remains distinct from current local RAM, because later
assignments can occur after that publication. The source impulsion EPS42/EPS52
assignment asymmetry is preserved; EPS55 is not guessed from a label.

Source checks cover startup frame 33052, General stop, the dispatcher, 23
procedures comprising 159 frames, both Focal helper graphs and impulsion
assignments. These checks establish graph correspondence, not LV2012 or NI
driver execution on XP.

Independent observations and owner fences
-----------------------------------------

Backend software events contain immutable full EPS/DPS images, a source
revision and an explicit ``SOFTWARE_STATE_NOT_MEASUREMENT`` tag. Their
observer reads RAM only: no NI operation, wait or parallel reader is added.
Reentry into measurement from this observer is rejected. Observer failure is
diagnostic and cannot skip a pulse release or source stop.

The runtime gives software observations their own sequence and age. A
same-revision identical image may renew owner observation; conflicting images
or a regressing source revision fail closed. Validity requires the current
backend, session and lifecycle, no accepted cancellation, and no unresolved
error or ownership uncertainty. FAULT retains diagnostics but projects EPS/DPS
as unavailable. Unchanged RAM does not expire solely because no assignment
occurred; every successful read or safe checkpoint can confirm the same image.

Measurement acceptance additionally requires a real nonsimulated native
sample, complete finite AI/DI input shapes, age below two seconds, the current
operation revision and, for isolated execution, the current worker generation
and request. Superseded, cancelled, late, malformed and progress-only messages
cannot refresh measurement time. General command admission invalidates old
measurements just as other procedures do.

The child uses separate latest-only software and sample/progress slots. This
prevents one traffic class from starving the other without creating unbounded
queues. It does not make the stream a lossless log of every intermediate
assignment. Publisher identity includes both observation sequences; an EPS/DPS
change is sent even when no new measurement was accepted.

IPC timing and bounded sampling
-------------------------------

Child and parent monotonic clocks are not compared as absolute timestamps.
The child reports capture-start offsets relative to its current request, and
the parent uses its own request-send anchor. The conservative sample age is
the larger of the reported local age plus parent queue delay and the parent
elapsed request time minus the child's capture-start offset. This includes
child outbox/pipe backpressure and parent dispatch delay. Missing, nonfinite,
negative or impossible provenance cannot qualify a fresh execution sample.

No concurrent NI reader is introduced. Optional execution sampling runs only
on the existing owner at explicit safe waits. ``safe_sample_budget_seconds``
remains None by default until aggregate read duration is qualified on site.
The backend conservative budget is six reads times configured read timeout,
plus 0.05 s: 3.05 s at the current 0.5 s timeout. An explicitly enabled budget
cannot reduce this derived bound. Critical asserted-pulse spans are excluded.

The execution reader apportions remaining dwell time among remaining reads,
discards late or partial samples, and stops a started AI task in ``finally``.
Native start/stop calls remain unpreemptible; a hard real-time deadline cannot
be promised. Short one- or two-second waits may therefore have no qualified
full sample. EPS/DPS can still update while old measurements become
unavailable. A blocked native driver call cannot yield new physical readings.

Wire, receiver and web semantics
--------------------------------

The maximum populated native set is now 14 banks: five input banks, seven
remembered output-command banks and EPS/DPS. The remaining 13 retain null data
and error -80001; no synthetic counter or other unported bank is added.
Trusted native tuple vectors are normalized to lists before encoding, while
the public wire validator continues to require exact types and lengths.

The unchanged wire envelope has one age. Native publication uses the oldest
populated category: measurement age for input/command images and software
observation age for EPS/DPS. Expired measurements are null before publication;
a new software event cannot make retained old AI values look current. Cached
views advance both ages and clear both currentness attestations on owner-lock
contention or stale application metadata.

The signed receiver, Tango facade and web presentation are tested together.
During an EPS/DPS-only command update, stale AI remains null and aggregate
quality remains INCOMPLETE. Software progress cannot create an equipment-start
permit. Authentication, leases, session/revision checks, commissioning flags,
local-only initialization and default remote-command disablement are unchanged.

Validation and candidate
------------------------

Source and tests are committed as ``0b76b898``. The candidate label is
``acq-unified-stage-telemetry-20261023-v8-r7``. Test counts overlap and must not
be added together.

* Actual CPython 3.4.4 x86: 296 tests run, 295 passed and one optional
  dependency-import test skipped, 22.640 s. The 23-module combined regression
  covers existing input/recovery/journal/GUI/isolation contracts plus status
  projection, command telemetry, cooperative procedures and priority admission.
* Python 3.12.14 with ``--deny-network``: 400 passed, one skipped, 31.94 s.
  This larger subset also covers the standard and dual-mode wire paths,
  receiver, Tango facade, web API, packager and temporary archive fixtures.
  Its 24 warnings are existing deprecation/import-rewrite warnings; no
  unhandled-thread warning was reported. No live PostgreSQL test was enabled.
* The four added suites contain 65 tests: source/software-state and deadline
  contracts (25), standard-bank projection (16), end-to-end publisher pipeline
  (6), and runtime/isolated execution observations (18). They include a
  250 ms getter delay, pipe/dispatch backpressure, impossible age provenance,
  source revision regression, superseded commands, cancellation, malformed
  samples, stale views and an EPS/DPS-only signed receiver-to-web update.
* All 67 candidate manifest hashes and the cold Python 3.4 acceptance passed.
  The acceptance forbids native library loading, leaves the backend factory
  unused, verifies signed private-loopback ACKs and all 27 envelope names,
  checks EPS/DPS updates without measurement refresh, and checks VI exclusion
  and non-waiting telemetry projection. It reports cards initialized False,
  hardware commands sent False and live Everest contacted False.
* ``git diff --check`` passed. Independent review found no remaining code
  blocker in the changed status/execution path. Physical timing qualification
  and the unported producers remain separate, unresolved release limits.

Candidate build ID:

``608e2173820902544e61cfd6aa23e7d1a92a92719eb8c4cc88b8b8740db39713``.

The non-overwriting development package is retained at
``C:\Users\elyse\AppData\Local\Temp\elyse-stage-telemetry-r7-f9958cc850e24d038e663428651c9abc``
with a sibling ZIP. It is not installed on XP. Packaging uses the module entry
point, not direct script invocation from ``tools``::

    python -m tools.package_acq_web_control <new-candidate-directory>
    C:\dev\pyconlyse\tools\xp_python34_extracted\python.exe tools\check_standard_telemetry_python34.py <new-candidate-directory>

The historical r5 installer is not an approved updater for this changed source
closure. A later deployment requires a reviewed cold-state update and explicit
operator authorization. It must not initialize cards or enable execution
sampling merely because these software tests passed.

