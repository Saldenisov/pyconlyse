Parallel card preparation, v8-r11
================================

Observed trigger
----------------

The operator installed r10, rebooted XP and requested Initialize. Everest
confirmed build ``d0a3a64d67c173ed6aca727666784f4ac2c0678602bb096bf9d927b9b3a4436b``
and native child PID 3492. The first Task constructor returned. Subsequent
stack notices remained in ``add_co_pulse_chan_ticks`` at
``C:\Python34\lib\site-packages\nidaqmx\_task_modules\co_channel_collection.py:155``.
That line invokes ``DAQmxCreateCOPulseChanTicks``. The 120-second parent RPC
deadline expired; the native operation had not returned an error code.
Thus r10 did not complete initialization. Telemetry ACKs only established
transport, not card readiness.

The operator then requested concurrent initialization of every card, per-card
diagnostics, and command refusal until all required cards are ready. The
operator reported another completed reboot before r11 staging. No General,
stage start or setpoint command was sent during this work.

Execution and readiness
-----------------------

One retained NI child now launches one preparation thread for each card 1--11.
Each thread calls the existing task factory with ``selected_devices=(card,)``.
The card-local NI calls, channels, timing, triggers and properties are unchanged.
Cross-card preparation is concurrent; the application cannot guarantee that
the native NI driver itself executes calls concurrently.

Threads only configure tasks. Ordinary failure on one card does not prevent
attempts or successful returns on other cards. The coordinator collects all
returned outcomes or expires one 30-second total preparation deadline. It
returns pending ownership rather than waiting sequentially for each card.
It never kills native calls, retries a card, or treats timeout as electrical OFF.
The pre-existing factory still attempts cleanup of its own failing card;
cleanup boundaries are logged and incomplete cleanup retains that owner.

Only complete preparation merges the returned task maps into one owner.
Counter starts and initial AO/DO images then execute in the existing order,
followed by the initial software-status publication. ``startup_complete`` is
true only after these startup effects and cancellation checks. Failed initial
software publication clears it again.

Partial initialization retains the backend in FAULT for explicit cleanup.
Cleanup refuses to race any live initialization thread. Once every call has
returned, an explicit Deinitialize/Stop server can close retained handles.
No automatic merge, startup replay or command enable occurs after a deadline.
Successful initialization still exposes 21 NI tasks across 11 cards.

Every remote named command, including stop commands previously permitted in
FAULT, is refused while production ``startup_complete`` is false. The local
backend read/command guard and runtime stop admission enforce the same barrier.
Lifecycle Deinitialize and Stop server remain available when their existing
ownership/operation checks permit them. Commissioning flags are unchanged.

Diagnostics and transport
-------------------------

``initialization_cards`` is a RAM-only runtime field containing every card's
state, current call, phase, elapsed time, task count and structured native error
when a call raises. Native ENTER/RETURNED/RAISED notices include card and UTC.
A timed-out call reports ``TIMED_OUT_UNKNOWN`` because it has not returned;
no native error code is invented. The XP window shows all 11 cards without
adding any button. Everest receives the same field in ``runtime_json``.

Card callbacks update locked RAM only. The coordinator serializes trace and
progress publication outside that lock. During initialization, the watchdog
repeats complete RAM snapshots so bounded progress queues cannot permanently
hide a terminal card state. Initialization notices never trigger NI reads.

After a deadline/cancellation result, the idle child continues to report late
card returns through an exact private ``initialization_status`` envelope.
Only card diagnostics, retained resource count and ``startup_complete=False``
are admitted. This channel cannot modify RPC responses, runtime readiness,
measurements, ownership flags or confirmed cleanup. A late successful return
therefore updates its diagnostic row without allowing commands.

Windows child input now uses ``PeekNamedPipe`` and ``ReadFile``. It waits
outside buffered/CRT reads and requests only bytes already present in the
single-reader pipe. This removes idle blocking stdin reads from the NI child;
the metadata prewarm remains. Whether this removes the XP driver stall still
requires the supervised r11 attempt; no native success is claimed from mocks.

Validation and staging
----------------------

* Actual CPython 3.4.4 x86: 122 tests passed in 19.177 seconds, including real
  anonymous pipe EOF/fragmentation, retained native-free child lifecycle,
  concurrent 11-card barrier, error isolation, pending ownership, late status,
  startup gating, VI status and last-sample telemetry regressions. The two
  opt-in dependency tests ran with real NI library/version metadata, without
  constructing a Task or addressing a card.
* Python 3.12, network denied: 490 passed and two optional dependency skips
  before the late-status channel; the subsequent affected-suite run passed
  93 with those same two skips in 17.27 seconds.
* Independent review found no remaining blocking ownership/cleanup/gating
  issue after the late-status regression was fixed.
* Actual Python 3.4 parsed 63 package source files and three installation tools.

The staged XP package has 69 source/data files, build
``c12e287556e6742f5984d79ee8cd982994a1fff87a5265a7c2dee3bd9cb5d6f2``.
``INSTALL_R11.lnk`` was added beside the prior installer/read-trace shortcuts.
It performs a cold, backed-up source update and preserves hardware configuration,
calibration, journal and ownership evidence. The already provisioned distinct
command key is reused. ``START_SERVER.lnk`` starts the canonical application
directly through ``C:\Python34\pythonw.exe``. Neither shortcut initializes NI.
At the time of this note r11 is staged; live installation/readiness is unverified.
Everest's command property remains disabled; no command transport enable or
commissioning change is implied by this initialization work.

Supervised installation and live observations
--------------------------------------------

The operator installed r11 at 09:51:13 UTC (10:51:13 Paris), started the server
and requested Initialize. Everest subsequently confirmed the exact r11 build,
session ``3c69ef96d8f44c19b6ff79b5ca42919c``, child PID 2820,
``RUNNING``, ``startup_complete=true`` and 21 retained tasks. All 11 cards
reported READY without native errors or pending outcomes. Card preparation
durations were 0.344--0.453 seconds; the accumulating report-level elapsed
value includes subsequent owner lifetime and is not total startup duration.
Counter starts and fixed startup images returned before startup_complete.
This verifies one successful XP attempt; it does not isolate the relative
contributions of the polling-pipe change and parallel preparation.

An independent telemetry deployment mismatch then became visible. Everest's
old validator accepted all-null initialization packets but rejected the first
populated EPS/DPS packet with ``Unmigrated Python bank cannot claim valid values``.
XP retained that unacknowledged packet and direct signed runtime reads remained
fresh, while the standard 27-bank stream aged. An offline reproduction using
the current captured runtime passed the candidate validator with 14 populated
banks and failed the installed validator with that exact exception.

Only these three already-tested telemetry contract modules were then updated
on Everest; XP and its live task owner were untouched:

* ``legacy/xp_acq_control/elyse_agent/standard_banks.py``
* ``legacy/xp_acq_control/elyse_agent/native_telemetry.py``
* ``legacy/xp_acq_control/elyse_agent/telemetry_publisher.py``

The telemetry Device Server was restarted with the same arguments, directory
and environment. The archive implementation/configuration and database were
preserved. Backup and launch records are under
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\native_validator_r11_20261026T095828Z``.
The subsequent acknowledged stream resumed without restarting XP.

The explicitly requested command transport was also enabled on the same
Device Server with the separately provisioned key matching XP's installed
key digest. Its prior properties are retained under
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\command_transport_r11_20261026T100214Z``.
Only the local telemetry device was reinitialized; no ExecuteCommand request
or hardware command was issued. This enables transport, not commissioning or
proof of trusted-caller authorization; the previously observed missing
AccessControl service remains a separate qualification item.

At 10:05:37 UTC (11:05:37 Paris), runtime sequence was 3127,
``telemetry_source_current=true`` and both command transports were enabled.
The receiver count had reached 715 since its reinitialization. All 27 bank
envelopes were present; 14 migrated banks were populated, including EPS/DPS.
The C4 packet age was 0.562 seconds with no packet error. The remaining 13
banks retain explicit unavailable status. All six direct input banks were
being read without errors. The C2 HT measurement channels read zero; this
does not independently verify high-voltage safety or feedback calibration.

General remained refused as ``STAGE_CONTROLS_NOT_COMMISSIONED``;
``full_stop_commissioned=false``. Existing HT feedback, Chroma resource and
cooling-polarity flags were not relabeled as verified merely to enable it.
The existing General-only pulse implementation is narrower than the full
General/water/stage programme and is not exposed by r11's unified control
runtime. Source General event-6 still unconditionally attempts Focal OFF;
unpowered supplies alone are not a source-supported reason to skip it.
