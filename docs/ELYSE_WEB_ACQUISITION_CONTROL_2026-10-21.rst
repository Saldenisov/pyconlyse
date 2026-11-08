ELYSE web / Python Acquisition command integration
=================================================

Deployment route superseded on 2026-10-21
----------------------------------------

The separate ``elyse/acquisition/control`` device and web environment source
selector below describe the earlier v2 candidate, not the current activation
plan. Follow ``ELYSE_UNIFIED_TELEMETRY_2026-10-21.rst`` instead: Python pushes
the standard 27-bank envelope to the existing ``elyse/acquisition/telemetry``
device, which also carries the named return commands. The v2 package must not
be activated as the new unified release. Historical implementation details
below are retained for provenance.

Scope and provenance
--------------------

The existing ``acq-control-candidate-20261021-v1`` XP implementation and
``acq-control-everest-candidate-20261021-v2`` Tango facade were reused, not
replaced by another wire protocol. Their source snapshot is promoted under
``legacy/xp_acq_control``. The independent, currently used read-only
``legacy/xp_acq_agent`` and its live LabVIEW telemetry receiver are unchanged.
This separate source tree avoids replacing modules used by the old service.
Source identity is recomputed from installed source/data bytes, not asserted
to be a deployment, firmware, or hardware qualification.

Command path
------------

Browser -> authenticated Flask POST -> ``elyse/acquisition/control`` Tango
``ExecuteCommand`` -> authenticated XP HTTP ``/commands`` on port 8772 ->
the existing single NI-owner thread. No browser or web process contacts XP,
NI cards, Chroma, or PSP directly. XP has exactly three lifecycle buttons:
Initialize, Deinitialize, Stop server. Initialization remains local only.

Mapped web actions: General start/stop, Chauffage start/stop, PREMA start/stop,
Focales start/stop, Relais HT start/stop, modulator reset, HT supply start,
stop/reset, modulator impulse start/stop and cooling start. HT voltage is a
named protocol operation but its web arrows remain disabled until a separate
numeric editor and commissioned limits are supplied. HF arrows, preamplifier,
magnet-supply controls and temperature setpoints remain disabled: no arbitrary
outputs or invented mapping to General is accepted.

General startup policy
----------------------

General powers the circulation cabinet, so its source sequence necessarily
precedes the water command. The additional Python policy is:

1. Execute the existing General power/reset sequence.
2. Execute the existing ``cooling.start`` source procedure.
3. Read the real CANON and SECTION inputs repeatedly on the same NI owner.
4. Require normal indications continuously for 2 seconds and at least two
   measurements before completing General and allowing subsequent starts.

The default wait bound is 30 seconds (constructor accepts 2..120 seconds).
This is an admission timeout, not an approved equipment warmup/cooldown time.
It is not a change to hardware interlocks or the existing 120-second cooling
incident policy. Input polarity, complete HT stop and Chroma resources must
first be commissioned locally. No configuration flag was enabled by this work.
Unknown, stale, simulated, missing or faulted inputs do not establish a permit.
A timeout reports failure and retains card ownership; it does not cut power
or pretend the earlier General pulse was rolled back. General stop remains
available in supported fault/busy states. A second General start is rejected
until the previous start has been stopped/verified.

Cooling start is allowed as a recovery action even when circulation is not
yet normal; subsequent heating/HT starts still require normal current cooling.
Remote cooling stop stays disabled: elapsed cooldown and safe physical lamp/
accelerator state have not been qualified. Xe continuous-lamp cooling, shared
OWIS/Zaber and DG645 timings are not modified by this integration.

Receipts and safety boundaries
------------------------------

Every command binds an exact boot session, revision, random ID, named operation
and explicit confirmation. XP uses a separate command HMAC key and a single-use
two-second lease. Reusing an ID with another request is rejected. Commands are
only admitted by a runtime advertising ``control_policy_version=2``; the old
candidate cannot silently receive commands through the updated facade.
Internal state/watchdog reads do not allocate leases: only an authenticated
HTTP snapshot reply issues one, avoiding lease exhaustion from normal polling.
Commands are
never retried automatically. Flask commits its SQLite dispatch fence before
Tango I/O; lost replies remain INDETERMINATE across browser/server reloads.
Only exact matching XP receipts reconcile that record. Other starts are blocked
while a same-session uncertain dispatch remains unresolved; General stop is not
silently blocked by this web fence. Session/revision checks also run at XP.

QUEUED, EXECUTING, COMPLETED, FAILED and INDETERMINATE describe software command
progress. COMPLETED is never converted to hardware acknowledgement or a green
physical status. Indicators update only from current input telemetry. EPS
software flags and unavailable VAM/history banks are not fabricated from a
successful command. Python analog display uses the acquired bank's explicit
``legacy_scaled_values``, not a second scaling of raw volts. Missing calibrated
values remain unavailable. Selecting Python never falls back to old LabVIEW
readings when the Python source disappears.

Cold deployment / operator-supervised activation
------------------------------------------------

No production web restart, Tango registration, XP launch, NI initialization,
key/ACL change or live equipment command is performed by packaging/testing.
The server already copied to XP as ``C:\ACQ_Python_Control_20261021_v1`` does
not contain the added water-start/capability contract and must be updated from
the v2 package before these web actions can be enabled. Preserve its keys,
configuration and ownership/recovery journal; do not overwrite running code.

Activation requires:

* Stop the old Acquisition/Supervision card owners under operator supervision.
* Install the v2 XP package as a separate cold release on port 8772, with
  existing read key and a distinct command key; retain Initialize-only startup.
* Verify cooling polarity, HT feedback/zero-stop and Chroma resources locally.
  Keep each unqualified capability disabled. Do not turn every flag on merely
  to make buttons clickable. Bind/authenticate the intended Tango facade and
  restrict ExecuteCommand through Tango access policy before enabling commands.
* Register the separate ``AcqTelemetryControl`` device as
  ``elyse/acquisition/control``, using xp_port=8772 and explicit key paths.
  Do not replace ``elyse/acquisition/telemetry`` or the recording receiver.
* Enable authenticated PyConlyse login/CSRF, and explicitly select
  ``ELYSE_ACQUISITION_SOURCE=xp_control`` for both display and command source.
  Restart only the web service during a safe operator-approved transition.
* Open the XP window in IDLE, check identity/links, then initialize locally
  only when the previous card owners have exited. Verify each permitted action
  from current physical inputs; software tests are not hardware commissioning.

Software verification
---------------------

Driver-free tests cover admission, exact envelopes, leases, at-most-once
dispatch, faults, unknown readings, repeated circulation measurements,
General/water order and refusal of repeated General. The policy suite also
runs on the real Python 3.4.4 interpreter. An integration test uses real signed
loopback HTTP with fake NI/Tango and the actual broker/owner thread; it checks
web -> facade -> HTTP -> General -> water -> next stage -> General stop and
one-thread ownership. Separate Flask/JWT/SQLite and React tests cover source
selection, authentication, confirmation, stale revisions and lost replies.
None of these tests energizes real equipment or validates electrical polarity.

Deployment observation: separate Tango bridge started (2026-10-21)
-----------------------------------------------------------------

On explicit operator request, ``elyse/acquisition/control`` was registered as
class ``AcqTelemetryControl`` in ``DS_AcqTelemetryControl/everest`` and started
through the existing Everest Starter. The wrapper is
``DeviceServers/DS_AcqTelemetryControl.bat``. The new server answered Tango
ping and exported ``runtime_json`` and ``ExecuteCommand``; observed PID was
12908. Starter mode is 1 with startup level 0: manual start, no boot start or
automatic command replay. ``commands_enabled`` remains false; the existing
read-key file is referenced without copying or modifying its contents.

The operator explicitly stopped the XP Acquisition server during this check.
It was not restarted or initialized. The new bridge therefore correctly reports
``UNKNOWN / UNAVAILABLE`` with an XP connection timeout, rather than claiming
ready hardware. The copied v1 site configuration still has
``remote_control_enabled=false`` and unverified hardware gates; its runtime
also lacks the required v2 cooling/capability policy. It must not be admitted
by weakening the bridge checks or merely setting all verification flags true.

``elyse/acquisition/telemetry`` was left running and unchanged. Its latest
27 LabVIEW publications were all stale during this check; a responding
receive-only device is not evidence of current acquisition. Python runtime
telemetry is polled by the new bridge from XP ``/snapshot`` and is not pushed
into that old LabVIEW receiver. The production web process was not restarted
or switched to Python commands. The bridge client and control policy checks
passed 20 driver-free tests before startup; no equipment command was sent.
