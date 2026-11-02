Acquisition telemetry reliability: evidence and cold update
=========================================================

Scope and result
----------------

This update is prepared for Acquisition XP, 10.20.30.10, against the exact
2026-10-30 deployed source bytes. It has not been installed. The running VI,
cards, Python server, Tango device, web and recorder are not restarted by
preparation. SuperVision XP is outside this update.

Incident evidence, 2 November, Europe/Paris
------------------------------------------

* Before the manual server restart, its authenticated runtime replied IDLE
  with zero NI resources. Its VI counters remained 95057 accepted and 12128
  rejected. Last decoded VI input was approximately 10:33:47. The latest
  protocol-valid archived sample was 10:45:58.350948. This does not prove an
  independently fresh physical measurement or a crash at either time.
* The later receiver answered a deliberately invalid local frame correctly;
  that diagnostic added one known rejection to the old session. LabVIEW was
  present, and the operator confirmed that its time and card values changed.
  The exact reason its XML export had stopped was not established. ActiveX
  inventory failed with 429; this was not a VI execution error.
* The existing desktop shortcut opened START_Acquisition_Telemetry.vi but
  contained no Python launch. Two launcher shortcuts were installed separately
  on 2 November. The cold server started at approximately 17:21:26 without
  Initialize or a VI restart. All 27 banks subsequently reached FRESH; C3's
  error code was zero. During 17:21:40--17:22:53, accepted XML increased by
  853 and rejected XML by 111. OWNER_STATE_BUSY_VI_NOT_ADMITTED was observed;
  the individual cause of every rejected frame was not recorded.
* The missing interval contains diagnostic packets, not a continuous record
  of card values. The previous alarm-journal warning concerns historical
  closure and does not establish the cause of this telemetry interruption.

Reproduced defect and change
---------------------------

Two regression tests fail against the deployed source: XML serialization and
publisher-status collection both retain the NI/lifecycle lock. A simultaneous
VI receipt deliberately refuses that busy lock and is rejected. The tests pass
after serialization and transport-status collection move outside that lock.

The source admission decision remains atomic with runtime state capture.
Initialize still checks recent VI traffic under the publication lock. The
ingress path only attempts the owner lock; it never waits for it while holding
the publication lock. A concurrent Initialize is rejected before the NI factory
is invoked. Native fault/transition states do not fall back to VI. Encoding
delay now ages the XML receipt instead of giving an old snapshot a new age.

The listener retains its single socket/thread and retries a failed request
loop with bounded backoff. No process, NI worker or hardware command is
automatically restarted. Raw connections, completed XML frames, byte counts,
rejections, thread liveness and listener failures are exposed separately.
Transport health distinguishes source silence, admission failure, delayed
snapshots, stopped workers and delivery failure. The existing GUI displays
health, accepted/rejected counts and last valid XML age; its three buttons
and all 27 bank contracts remain unchanged.

The shortcut helper now reads actual IPv4 LISTEN rows through the Windows
GetTcpTable API. It does not submit probe packets or use a trial bind as
evidence that a server is listening. TIME_WAIT rows are excluded explicitly.
The parser also masks the unused high 16 port bits as required by the
`Microsoft TCP row contract <https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcprow_w2k>`_.

Diagnostic events use a separate bounded queue and increasing event IDs.
The writer retains at most a 2 MiB current log plus one backup under
runtime/logs/telemetry_diagnostics.jsonl. Disk errors, queue overflow, writer
startup failure and stuck writes are reported without gating telemetry,
commands, Initialize or server shutdown. This is not the alarm journal.

Validation and limits
---------------------

Actual CPython 3.4 tests cover both lock regressions, concurrent Initialize,
real local XML framing and 27-bank admission, malformed frames, source aging,
listener retry, diagnostic overflow/disk failure and unchanged buttons. A
broader Python 3.12 suite also exercises signed transport, source switching,
federated/hybrid telemetry and cached application reads. All NI backends are
fake; no device or live experiment endpoint is used by these tests.

The patch removes two reproduced contention paths. Other owner contention
can still cause honest rejections. Latest-only forwarding does not guarantee
every source snapshot; cross-bank physical atomicity remains unproved. The
whole-process failure hypothesis requires Windows Application event evidence,
not inference from a stale web display.

Cold application on 3 November or later
--------------------------------------

After the current Python server has released NI resources and closed, run
APPLY_RELIABILITY.cmd on Acquisition XP. Acquisition VI may remain running.
The installer verifies all prior hashes before changes, backs up only the six
updated source files, preserves configuration/ownership/alarm history, and
  opens only the cold unified Python server. It never opens or stops a VI.

The prepared COLLECT_CRASH_EVENTS.cmd optionally reads up to 50 Windows
Application errors dated 2 November into the package folder. It does not
change services or processes. Collecting it before tomorrow's restart may
help distinguish an actual Python/LabVIEW crash from source silence.

After installation, verify a new boot identity, IDLE / NI resources: 0 in VI
mode, increasing accepted/acknowledged counters, 27 FRESH banks and PostgreSQL
commits. Deployment, sustained live rejection-rate comparison and a controlled
server-only reconnect test remain pending. No current-process patch is applied.
