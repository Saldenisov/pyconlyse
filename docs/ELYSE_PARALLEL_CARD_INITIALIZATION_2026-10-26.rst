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
