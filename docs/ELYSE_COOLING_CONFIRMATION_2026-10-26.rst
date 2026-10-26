Cooling indication confirmation and fault readback, v8-r13
========================================================

Observed failure
----------------

The preceding Python test completed General start, then failed cooling-start
verification. The recorded alarm causes were only C3_IN_DIO96[0] and [6], both
raw True and labeled ``220V`` by the saved Fluides display. Incidents began at
2026-10-26T10:57:52.890625+00:00 with a deadline exactly 120 seconds later.
The additional Python watchdog requested General stop. Source stop frames
0 through 16 were attempted; Focales OFF reported Chroma initialization errors
with native status ``-1073807339`` for all three configured targets. The result
was ``PARTIAL_STOP_FAILURE``, not confirmation of physical electrical OFF.

The retained native child was ``IDLE_OWNED`` with 21 tasks, no active request
and no reported ownership uncertainty. The runtime nevertheless stopped
sampling because its loop admitted reads only in RUNNING. Network delivery
could remain responsive while actual input timestamps stopped advancing.
The operator subsequently closed/restarted the application. No operating-system
or LabVIEW crash is established by this software record.

Indication and source logic
---------------------------

The original saved Supervision palettes render these two raw Boolean inputs
False/green and True/red. Acquisition channel names instead describe Canon and
Section ``marche``. No independent 220-V measurement accompanies these bits.
The original Acquisition predicate is::

    (C4_IN[19] OR C4_IN[38]) AND (NOT C3_IN[0] OR NOT C3_IN[6])

Both observed C3 inputs True make that expression False, irrespective of the
two C4 values. The preceding 220V-only Python countdown was therefore additional
policy based on display indications, not a recovered Acquisition trip.
Neither inversion of the raw bits nor proof of electrical supply failure
follows from the labels or colors.

The operator clarified the required additional policy: red before water starts
does not begin a countdown. A later transition from established green to red
requires a physical circulation check by the operator within two minutes.
Confirmation means the operator reports circulating water despite the red
indication; it is not independent sensor verification.

Revised additional policy
-------------------------

* Each circuit arms only after distinct fresh normal observations spanning two
  seconds while General is active. Startup red remains visible through the
  existing raw indications, without creating an automatic-stop incident.
* A subsequent fresh red indication creates a unique circuit incident and an
  unchanged 120-second deadline. Web control asks whether water is physically
  circulating. Missing or negative confirmation leaves the deadline active.
* ``cooling.confirm_circulation`` accepts only one or two exact current incident
  UUIDs through the existing authenticated, session/revision-fenced command
  route and one-use web approval. There is no wildcard or browser-supplied
  operator identity.
* Confirmation before the deadline suppresses only those additional Python
  countdowns. Red indications remain visible, the operator decision is journaled,
  and the receipt explicitly reports software completion without NI writes.
  An already admitted stop cannot be canceled by a late confirmation.
* Fresh normal observations spanning two seconds clear and rearm the circuit.
  Another red episode has a new ID and requires another confirmation. Cached,
  missing or stale input does not establish green or clear an incident.
* Confirmation does not change runtime state/revision, cancel an active
  procedure, refresh a measurement, clear a runtime fault, or grant heating,
  HT, Chroma or beamline permission. Native Acquisition interlocks and source
  stop procedures are unchanged.

Policy-v1 incidents whose nonempty cause list contains only ``220V`` are
reclassified into historical records with an audit event. Their preceding
stop state/error is retained in that history. Mixed causes, flow/pressure/
controller faults and unknown empty cause lists remain conservative legacy
incidents and cannot receive the new operator exemption. Historical events
are not deleted. Arming is never restored from a previous process's cache.

Fault input observations
------------------------

After a settled procedure fault, the same initialized owner can continue
input reads. FAULT and its original error remain sticky. An explicit diagnostic
attestation binds each completed sample to boot, sequence, owner generation
and actual source age. A previous completed sample remains observable during
the same owner's next read-only RPC until its two-second expiry. Stop, close,
cancellation, uncertain ownership, changed generation and failed diagnostic
read invalidate that attestation. A diagnostic read failure retains ownership
and is reported separately; it does not automatically retry control or clear
the original fault.

The standard 27-bank packet publishes only the five mapped AI/DI input banks
from this fault diagnostic evidence. Command memory and EPS/DPS remain
unavailable during FAULT. The complete native runtime still includes all six
input banks. Everest retains FAULT quality and exposes diagnostic freshness
separately from normal source/control readiness. Cached application/HTTP views
age both nested and top-level sample ages consistently. No additional server,
NI owner or device-command route is introduced; the XP GUI retains three buttons.
Accepted fresh execution samples also update the RAM cooling policy during
long procedures. Their transported sample age is retained. That observer
neither invokes the source cooling-trip procedure nor sends a native command.

Cooling reset boundary
-----------------------

Channel identities establish Canon reset as C3_OUT_DIO96[2],
``/3/port7/line2``, and Section reset as C3_OUT_DIO96[5], ``/3/port7/line5``.
Both startup values are False. No assertion/pulse writer for either output was
found in the saved Acquisition/Supervision root graphs. Assertion polarity,
pulse duration and physical reset conditions remain unproven.

The existing Modulateur Reset instead writes C4_OUT_DIO96[2] True, requests
150 ms, then writes False. It is not evidence for inventing the same pulse on
C3. This release sends no new cooling reset and does not hide an electrical
fault by changing raw input values.

Deployment boundary
--------------------

The candidate uses the existing one XP application and one Everest telemetry/
command Device Server. The command set now has 25 named operations; the added
operation is the software incident decision above. XP, Device Server and web
must receive the matched contract. Cold source installation preserves existing
configuration, ownership markers, calibration, keys and journals. No Initialize,
General, water, heating or HT command is part of packaging or verification.

An independent archive check reported PostgreSQL ``ConnectionTimeout`` and
``DEGRADED_RETRY`` with 18,562 pending disk-spool frames and zero database
commits in that Device Server process. The queue reports durable ingress;
this is not evidence that those frames have reached PostgreSQL. Archive
services and queue contents were not restarted or modified by this correction.

Candidate and verification
--------------------------

The final cold XP candidate contains 70 source/data files plus the matched
source installer. Its source fingerprint is
``ab9cb517194bf12fdb2acdb8454eee7260f65fdeac17f2139fbc814797d8cef8``.
The matched Everest payload contains 44 files. Both preserve the three-button
GUI, 27-bank envelope and all existing physical qualification flags.

``INSTALL_R13.lnk`` is staged in the existing redirected shortcut directory:
``\\tsclient\C\Users\elyse\AppData\Local\Temp\elyse-r9-start-20261026``.
It targets Python3.4 directly and refuses source replacement while port8772
is open. It does not initialize cards, delete ownership evidence, send a
device command or clear current incidents. ``START_SERVER.lnk`` remains the
canonical application launcher. Coordinated Device Server/web activation
and cold XP installation remain separate from the completed software tests.

Validation used RAM/native fakes, isolated loopback test receivers and fake
Tango boundaries, not live device commands:

* Actual CPython3.4.4 x86: 142 tests passed, including fault readback through a
  delayed read RPC, HTTP-cache aging, execution-time red transitions, exact
  incident confirmation, deadline races and asynchronous journal/cleanup.
* Python3.12 Acquisition suite: 564 passed, nine optional integrations skipped;
  the additional execution-cooling file independently passed three tests.
* Web API/auth/approval/telemetry suite: 94 passed. The three additional
  execution-cooling tests plus this suite passed 97 tests in one invocation.
* Rich main frontend: 135 tests in nine suites; release frontend: 99 tests in
  five suites. Final parenthesis-only changes passed their targeted suites.
* The optimized rich frontend compiled successfully. The existing layout was
  preserved; its narrow main-tree changes are recorded in
  ``docs/deployment_patches/elyse_rich_cooling_confirmation_2026-10-26.patch``.
* Actual Python3.4 parsed all 65 executable candidate files, imported the cold
  runtime and reproduced the packaged source fingerprint without NI imports
  or task creation.

No claim of physical circulation, Chroma communication, successful hardware
shutdown or completed live rollout follows from these tests.
