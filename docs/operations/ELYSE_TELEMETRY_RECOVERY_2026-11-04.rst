Everest telemetry interruption: 4 November 2026
==============================================

Scope
-----

Restore the telemetry receiver and existing PostgreSQL archive, preserve failure
evidence, and remove the unattended-restart gap. No screen access, XP deployment,
VI lifecycle operation, NI initialization, hardware command or protection change
was performed. All times below are Europe/Paris (UTC+01:00).

Evidence and causal limits
--------------------------

* The web telemetry endpoint returned HTTP 503. DS_AcqTelemetry/everest process
  PID 37832 was absent; its Tango database export was stale. Starter and the
  separate control device server remained running. Acquisition XP port 8772
  answered an HTTP read; the passive source did not need a restart.
* PID 37832 was launched directly by tools/deploy_telemetry_reconnect.py on
  3 November at 07:20:07, rather than through Starter and the production batch
  wrapper. The wrapper's existing five-second nonzero-exit retry was bypassed.
* Starter AutoRestartDuration was unset at both device and class levels. Its
  documented default is zero. It was not changed: a Starter-wide policy change
  would affect unrelated device servers.
* PostgreSQL was also absent. Its log ended at 10:45:36 with a checkpoint start
  and no clean shutdown. Recovery subsequently reported interruption with last
  known up time 10:45:07. The latest archived C3_IN_DIO96 observation before the
  interruption was 10:47:43.050636, source sequence 1109190.
* Windows recorded a conhost.exe application hang/closure at 10:48:19. This is
  temporally consistent with loss of manually launched processes, but does not
  establish that it terminated either PostgreSQL or the receiver. No matching
  Python native crash event or traceback was recovered. The original exit cause
  remains unknown; the missing automatic restart path is established separately.
* Earlier PostgreSQL messages include Windows shared-memory reservation error
  487 while other connections continued to work. These messages do not establish
  the cause of the subsequent process loss.

Restoration
-----------

* 13:50:50: Starter.DevStart launched the existing production receiver through
  C:\dev\pyconlyse\DeviceServers\DS_AcqTelemetry.bat. PID 13500 is owned by
  wrapper PID 25624, which is owned by Starter. No second receiver was started.
* The 27 banks and HTTP 200/FRESH returned immediately. While PostgreSQL was
  unavailable, accepted data accumulated in the existing durable SQLite spool
  on F:. This is separate from the earlier interval with no running receiver.
* 13:52:14: the existing PostgreSQL cluster was started, without initialization,
  WAL deletion or repair. Its former 30-second startup helper deadline expired
  during normal crash recovery; the running postmaster was left untouched.
* 13:53:31: PostgreSQL reported ready to accept connections. The independent
  archive worker resumed delivery without restarting the receiver.
* 13:59:45: all 27 banks were fresh, maximum age 0.313 seconds; PostgreSQL state
  RUNNING, no last_error, 4497 records committed in this receiver process and
  11 pending. The prior backlog had decreased from 737 at 13:54:44.
* Acquisition source session remained cc750396a70641e0a2a8dc5ffbd37cc0. Data from
  the interval without a receiver must not be described as reconstructed or
  continuous; the latest-only upstream source cannot replay that interval.

Recovery changes
----------------

1. The receiver deployment tool now uses Starter.DevStart rather than Popen.
   It verifies the replacement process identity before declaring deployment
   complete. It no longer attaches production receiver lifetime to a deployment
   command's process hierarchy.
2. Windows task ELYSE-Telemetry-Recovery independently checks the receiver and
   existing PostgreSQL cluster every minute and at current-user logon. It uses
   an OS file lock in addition to Task Scheduler's IgnoreNew policy.
3. Two absent observations at least ten seconds apart are required. With the
   one-minute schedule, fallback recovery normally takes approximately one to
   two minutes; the existing receiver wrapper still retries ordinary nonzero
   child exits after five seconds. No sub-second or sleep/logoff guarantee is
   implied. The task uses the current user's interactive token.
4. Recovery only starts absent processes. It never kills a process, restarts a
   live/stale receiver, performs Initialize, contacts XP, sends commands to a
   device, starts another PostgreSQL cluster or changes Starter-wide policy.
   Existing listeners, wrappers and retained PostgreSQL children prevent a
   competing start. An uncertain PostgreSQL status also prevents a start.
5. A recorded zero receiver exit or clean PostgreSQL shutdown disarms automatic
   restart for that component. A subsequent manual start rearms observation.
   For maintenance, create F:\ELYSE_PostgreSQL\recovery\PAUSE or disable the
   named task. Remove PAUSE after maintenance. The normal-stop recognition is
   log-based; losing the stop record is an unavoidable ambiguity, so use PAUSE
   before planned maintenance.
6. Receiver source now includes best-effort lifecycle and native-fault capture
   for its next start. It preserves every installed device initialization and
   command path. It does not retrofit a handler into the already running process.
   Logs are bounded, independent of alarm history, and cannot gate operation.

Files and checks
----------------

Installed watchdog: F:\ELYSE_PostgreSQL\recovery\telemetry_recovery_watchdog.py.
Its state.json records PID observations and scheduled execution times;
events.jsonl records recovery attempts/errors. Receiver diagnostics use
receiver_lifecycle.jsonl and receiver_native_fault.log in that directory.
The current production log remains
F:\ELYSE_PostgreSQL\logs\device_server\DS_AcqTelemetry_everest.log.

Incident evidence, protected pre-restart log copies, read-only database evidence
and deployment receipts are in
C:\dev\SuperVision_Telemetry\receiver_failure_20261104.

Validation uses isolated policy fixtures and mocked service starts, not forced
crashes of a running experiment. It covers absent-process recovery, startup
grace, duplicate prevention, intentional stops/rearming, long WAL recovery,
uncertain PostgreSQL status and diagnostic failure isolation. Scheduled task
execution was separately verified against the healthy live system; its first
minute invocation returned result 0 with both original restored PIDs unchanged.

Starter policy reference:
https://www.esrf.fr/computing/cs/tango/tango_doc/ds_doc/tango-ds/System/starter/FullDocument.html
