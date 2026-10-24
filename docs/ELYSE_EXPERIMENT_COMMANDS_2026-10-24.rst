Experiment commands: software candidate, 24 October 2026
======================================================

Scope and release boundary
--------------------------

The r8 candidate adds explicit remote intents for modulator pulses, HT supply
and scalar voltage selection, Faraday 1/3 EN pulses, and mirror EN/HORS pulses.
It does not run an experiment autonomously. Each stage and each voltage change
requires a separate operator decision. No target voltage, upward ramp rate,
settling interval or physical position tolerance is inferred from the VI.

This work used source exports, fake driver callbacks, private loopback servers
and temporary databases only. No XP deployment, NI initialization, hardware
command, live Tango mutation, recorder change or archive migration occurred.
The local window retains exactly Initialize, Deinitialize and Stop server.
The same dual-mode application forwards VI telemetry in IDLE and publishes
native telemetry only after local ownership initialization. The 27-bank wire
envelope and default-disabled execution sampling remain unchanged.

Source evidence and the meaning of EN
------------------------------------

The Supervision VI SHA256 is
``B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B``;
its extracted BDHb SHA256 is
``F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7``.
The Acquisition root-export archive SHA256 is
``6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527``;
the 17-original-helper export archive SHA256 is
``645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F``.

``acquisition_beamline.py`` retains source UIDs for each assertion, wait and
release. All four commands modify ``C5_OUT_DIO96``; they do not synthesize DPS.

.. list-table:: Confirmed command images, not measured positions
   :header-rows: 1

   * - Intent
     - C5 field
     - Nominal dwell
     - Source diagram / sequence / writers
   * - faraday_1.en_pulse
     - 23
     - 0.5 s
     - 53772 / 54575 / 54669, 55252
   * - faraday_3.en_pulse
     - 25
     - 0.5 s
     - 56943 / 62574 / 62647, 62956
   * - laser_mirror.en_pulse
     - 22
     - 1.0 s
     - 53656 selector 0 / 77973 / 53908, 86028
   * - laser_mirror.hors_pulse
     - 26
     - 1.0 s
     - 53656 selector 1 / 56518 / 56584, 56849

The source transport writes the Supervision PSP bank. Acquisition copies that
bank through timeout reader 25449, local bank 13 and writer 25484, then runtime
frame 7386, local reader 2378 and cluster conversion 8127 to DIO96 call 686;
helper C5 write 742 performs the output operation. Python replaces this
transport with the existing serialized full-bank owner callback. Sibling bits
are preserved. This substitution does not establish native dialog/error or
physical pulse-width equivalence.

Explicit Faraday HORS writes were not source-qualified. Fields 28/30 are used
only to reject conflicting retained commands, not as new actuators. Neither
``faraday.open`` nor Faraday HORS commands are exposed. Faraday 3 input labels
also conflict: Supervision labels field 42 EN and 41 HORS, whereas the
Acquisition schema reverses them. Therefore EN must not be presented as a
verified physical opening, insertion, retraction or beam-clear indication.
The unresolved direction and feedback mapping require independent site
qualification before beamline execution is enabled.

HT ordering and current-owner proof
----------------------------------

The existing named start/stop procedures remain separate. An increase through
``ht_voltage.set`` now requires a known retained C9 voltage command and
successful HT-supply and modulator-pulse sequences from the current NI owner.
Backend proof requires complete finite C9 command memory, EPS 45/52, successful
callback latches and started retained counter tasks without pending stop or
configuration uncertainty. Runtime proof additionally requires its own
successful completion latches and the current owner generation. EPS alone
cannot authorize an increase.

Admission and actual owner entry both check the operation. Stop, reset, fault,
cleanup and ownership replacement invalidate the proof; an accepted stop
supersedes queued voltage increases. Known-command decreases do not require
the new two-sequence gate. The existing remote scalar policy still requires
RUNNING state, fresh native inputs, commissioning and current cooling/full-stop
admission. Dedicated protective stop/discharge procedures do not acquire this
new scalar freshness requirement.

The protocol accepts one finite numeric voltage in [0, 20] kV. This is an
encoding domain, not a qualified operating range. No automatic upward ramp or
automatic transition to another stage is added. Software completion remains
distinct from measured voltage, physical equipment acknowledgement and an
independent safety permit.

C5 failure, ownership and protective stopping
--------------------------------------------

Beamline execution requires explicit local commissioning, operator confirmation,
fresh nonsimulated current-owner inputs, General/current cooling admission and
the existing full-stop qualification. Selected and opposite command bits must
already be released. These exclusion checks are additional Python policy,
not recovered VI hardware interlocks.

Only the retained initialization owner may write the bank. Every possibly
applied assertion attempts the selected False release in ``finally``;
cancellation and diagnostic observers cannot suppress it. Assertion failures
skip the dwell and never replay True. A failed release retains an uncertainty
record, rejects new energizing/motion and prevents NI ownership cleanup.

Independent reviewed energy-reducing stops remain callable on the original
owner: General, HT/discharge, modulator/counter and other existing stop paths.
Their private scope cannot write or retry C5 and does not bypass serial
quiescence checks. Thus C5 uncertainty cannot authorize another motion, but
does not by itself remove the separate protective stopping paths. A blocked
native call remains unpreemptible; this software is not a hard real-time
emergency-stop channel.

Web, transport and authorization
--------------------------------

The Experiment panel uses the actual Acquisition provider and the fixed route
web facade -> existing telemetry Device Server -> signed XP control channel ->
single NI owner. The legacy Supervision widgets remain read-only. The panel
provides explicit start/stop choices, a numeric HT value and four accurately
named source pulse intents. No arbitrary bank write or ambiguous Faraday
opening command is accepted.

Confirmation freezes the operation, actual numeric value, source session,
revision and complete capability set. Editing the value or observing a changed
source, boot, revision, capability set or freshness invalidates confirmation.
An uncertain HTTP result is not cancellation of physical execution. Commands
have a 10 s client deadline and are never automatically retried. Uncertain
intents persist in a bounded sessionStorage ledger across page reloads; only
matching authoritative receipts can reconcile them. Empty history or a new
boot does not establish nonexecution. A separately bounded protective-stop
reservation prevents the ordinary ledger capacity from removing an otherwise
admitted General Arrêt. This remains an operator-confirmed command, not a
substitute for local protective controls.

JWT, CSRF and ``operator_confirmed`` are not sufficient actuation authority.
The POST facade now always requires the existing external manual-approval
policy and a one-use nonce before any command-database or Tango access, even
in local/development mode. Approval binds the fixed ExecuteCommand target,
operation, value, XP session and expected revision. The random command ID is
correlation metadata; replay prevention consumes the separate approval nonce.
An explicit optional False cannot downgrade production authorization. The UI
accepts an externally granted nonce; it does not issue approval itself.

A missing, expired or mismatched approval produces an exact correlated
REJECTED receipt with ``dispatch_attempted=False`` before command DB/Tango
access. Only the allowlisted authorization status/code pairs can clear that
new first-attempt browser reservation. Generic errors, mismatched identities,
5xx responses and lost replies remain UNKNOWN. This distinction avoids
permanent browser lockout after a provably undispatched authorization refusal
without clearing older/reloaded uncertainty or retrying an operation.

Direct Tango ExecuteCommand remains a trusted-transport boundary and does not
verify that web nonce. Before enabling commands, a qualified Tango ACL must
restrict that entry point to the approved facade/trusted callers, or a
separately reviewed Device Server approval mechanism must be implemented.
Default ``commands_enabled=False`` is appropriate for this offline candidate,
not evidence that direct Tango access is safe to enable. No live ACL was
inspected or changed during this task.

Release and qualification requirements
--------------------------------------

The candidate has exactly 23 named capabilities. Runtime protocol 2, policy 2
and envelope 1 remain unchanged; the exact capability-set check rejects mixed
old/new components. A later release must coordinate XP, Device Server, backend
facade/authorization module and built frontend. Both package variants retain
all execution/commissioning defaults False. No physical qualification is
implied by a passing offline test.

The XP and Everest package manifests do not deploy the changed web sources.
The historical r5 installer and ``deploy_acq_unified_everest.py`` alone are not
complete r8 updaters: the latter switches assets/restarts the existing checkout
but does not stage the backend modules. Before an authorized cold rollout,
record and back up the exact XP package, Device Server source closure, web
backend sources, frontend assets, properties and configuration. Keep commands
disabled while installing the matched revision; verify IDLE, VI forwarding,
27-bank updates and current metadata without initialization. Restore the
matched previous sources/assets/configuration on failure, not a mixed subset.
Only a separate operator-authorized qualification may enable actuation.

Physical Faraday direction/feedback, HT measured feedback and tolerances,
Chroma identity/serial quiescence, full stop/cooling commissioning and aggregate
native read timing remain release conditions, not test-fixture assumptions.

Validation
----------

Runtime/source changes are committed as ``03387381`` and the web/authorization
path as ``0e2d1aa``. Test counts below overlap and must not be added together.

Actual CPython 3.4.4 x86 ran 343 tests in 25.218 s: 342 passed and one optional
dependency-import test was skipped. Cold packaged acceptance forbids native
library loading and leaves the backend factory unused. It verifies all 27
envelope banks, signed loopback ACKs, VI exclusion, non-waiting publication,
EPS/DPS-only updates, the 23-operation set, source pulse metadata and the
RAM-only HT ordering gate. It reports initialized cards False, sent hardware
commands False and contacted live Everest False.

The Python 3.12.14 regression with ``--deny-network`` passed 650 tests, skipped
two platform/optional tests and deselected two unavailable Windows symlink
creation cases, in 51.94 s. The latter fail before their production assertions
with ``WinError 1314`` in this account; they were not claimed as executed.
The 24 warnings are existing deprecation/import-rewrite warnings. This subset
includes source/runtime/isolation contracts, temporary archive fixtures, the
real Flask-to-signed-control pipeline and shared authorization routes. No live
PostgreSQL integration was enabled. Counts overlap with the Python 3.4 suite.

The frontend passed all 20 Jest suites, 213/213 tests, in 13.044 s. Seven
focused suites passed 106 tests in 9.111 s; ESLint passed with zero warnings
for all eight changed/new JavaScript files. Tests exercise the mounted Elyse
page, nonce arming/consumption, exact numeric confirmation, source/session
changes, the 10 s deadline, page reloads, full-ledger protective stopping,
strict pre-dispatch refusals and malformed/uncertain replies. A known refusal
cannot clear a prior same-ID/reloaded intent. Every POST remains manual.

The optimized frontend build completed with seven pre-existing hook-dependency
warnings in six unchanged components, old Browserslist/Node tool notices and a
1.54 MB gzip main-bundle size warning. The changed files passed separate strict
linting. The build used the existing dependency tree through process-local
module resolution and a new temporary output directory, not live web assets.
Compiled pulse names, the one-use approval UI and the strict pre-dispatch
receipt fields were checked in the generated main bundle.

Build output:
``C:\Users\elyse\AppData\Local\Temp\elyse-experiment-web-r8-6db31deb35dc446c9526fb0b6e598ec7``.
The SHA256 of ``static/js/main.bba06361.js`` is
``898261C6B797CAB92369D03EB4B8677481A7CAEC84E44D9469DD767A56A23456``;
``asset-manifest.json`` SHA256 is
``25B4918B11559FD23F0575CF94ADABCD19E81D0BF2F592CF7ABE3CCDA9DFC545``.

The XP package contains 68 hashed files; the Everest package contains 43.
Candidate build ID:

``1672571cc568fe598e5b9369a8c6a449791b753c5eb9b5cd53eac76eb5f2772a``.

Non-overwriting development packages and sibling ZIPs are retained under
``C:\Users\elyse\AppData\Local\Temp\elyse-experiment-r8-2b69dc7da6ab4f459547c79d357ddfae``
and the corresponding ``-everest`` directory. Neither is installed on XP.

Independent review accepted the code only as an offline/default-disabled
candidate. Command enablement and deployment remain blocked by the unqualified
direct-Tango authorization boundary, incomplete coordinated rollback and the
physical commissioning limits above. The historical deployment CLI was not
repaired, approved or run by this change.
