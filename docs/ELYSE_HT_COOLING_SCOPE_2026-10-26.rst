HT-scoped cooling monitor, v8-r14
================================

Corrected boundary
-------------------

The operator clarified that General, initial water startup and the cold
pre-experiment state must not activate the additional two-minute shutdown
policy. The preceding r13 condition used General as experiment activity;
that condition was too broad.

The Python owner now activates this additional monitor only from a fresh
current-owner NI sample showing measured HT above the already configured
zero tolerance and an active HT-supply feedback contact. Feedback qualification,
complete startup and certain native ownership are required. A setpoint,
software OK flag, General or water-start request alone is insufficient.
No new voltage threshold or physical qualification flag is introduced.

Once qualified HT exposure has been observed, missing or stale telemetry,
native faults and ownership uncertainty cannot silently disarm the monitor.
Fresh qualified HT zero, supply OFF and stopped modulator pulses end that
scope. Explicit local electrical-OFF attestation during an accepted lifecycle
close also ends it. Neither path clears an independent runtime/NI fault.

Red cooling indications when HT first appears start the same 120-second
operator-confirmation window as a subsequent green-to-red transition. An
exact per-incident confirmation suppresses only that additional countdown;
late confirmation cannot cancel an already admitted stop. Existing source VI
interlocks, energy-start gates and native shutdown sequences are unchanged.

Current and historical episodes
-------------------------------

Cooling episodes are bound to a runtime boot session. A cold new owner retains
prior-session episodes and their stop errors as audited history, without
reusing them as current countdowns or blocking a new General admission.
This classification does not assert electrical OFF, delete journal history,
release native tasks or clear the separate ownership-recovery barrier.

The web investigation also found a separate legacy receiver problem: with XP
not running, the VI observer restored Canon and Section incidents starting at
2026-10-22T18:36:56.073392+00:00 and 18:36:56.343972+00:00. It displayed them
as current, expired countdowns with stop UNAVAILABLE despite machine_active
being unknown. Those entries were four-day-old history, not new experiment
measurements.

The telemetry Device Server now uses the shared journal policy. Its receive-only
VI observer exposes raw indications and retains prior episodes as history;
it does not own a forced-stop timer or claim authority to stop LabVIEW. When
Python owns the cards, the facade continues to project that owner's actual
HT-scoped policy. Journal shutdown occurs outside receiver RAM/ingress locks;
failed receiver startup also closes or retains its owned journal explicitly.

Validation and deployment
--------------------------

* Actual CPython3.4.4 x86: 149 tests passed. New tests distinguish cold/General/
  water-only startup from measured HT exposure, exercise red at HT admission,
  preserve exposure through stale data and uncertain ownership, and retain
  previous failed stops as history before Initialize.
* Python3.12 with external network denied: 577 tests passed, nine optional
  integration tests skipped. Receiver startup-failure cleanup and previous
  journal restoration are included.
* Web control/telemetry regression: 58 tests passed. Packet shape remains
  27 banks, named operations remain 25, and XP retains three buttons.
* Actual Python3.4 parsed 65 executable candidate files, imported the cold
  runtime without NI driver imports, and reproduced its fingerprint.

The final XP candidate contains 70 source/data files and the matched installer,
fingerprint ``407d4d0112989b6d434d0c333a08b0a3f270efb832dd2870af7a33b2ec1f7910``.
The matched Everest package contains 46 files. ``INSTALL_R14.lnk`` is staged
in the existing redirected ``elyse-r9-start-20261026`` shortcut directory.
The operator reported r13 installed but not started; replacement is a cold
source update, not another Initialize.

Four reviewed Device Server/policy files were backed up and installed under
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\cooling_scope_r14_20261026T122218Z``.
Old telemetry DS PID37664 exited normally; replacement PID25180 reported ON.
The live web cooling endpoint then returned active=False, stop_state=NONE,
remaining_seconds=null and two retained historical incidents. The old false
current countdown was therefore removed on the served site.

PostgreSQL remains unavailable. All 18,562 pending disk-spool frames survived
the telemetry-only restart. PostgreSQL, VI and NI resources were not restarted
or actuated. XP installation was opened through its RDP desktop and reached
Windows' file-security warning. Human dismissal of that security prompt and
the subsequent XP IDLE-window verification remain pending; a staged package
must not be described as an already running acquisition owner.
