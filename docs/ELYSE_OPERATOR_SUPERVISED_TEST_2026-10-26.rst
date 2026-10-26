Operator-stepped trial, v8-r12
==============================

Scope
-----

The operator requested one trial mode covering General, water, Chauffage,
PREMA, Focales and Relais HT, with one confirmed command at a time and physical
inspection between commands. This supersedes the preceding General-only
proposal. No operation is started by selecting the mode or opening the GUI.

``operator_supervised_test`` is an explicit local configuration permission,
separate from all physical ``*_verified`` facts. The reviewed allowlist is
General start/stop, cooling.start, Chauffage/PREMA/Focales/Relais HT start/stop,
and modulator reset. The existing 24-operation protocol is unchanged. Other
operations remain visible according to their existing eligibility rules;
HT supply/pulse energization, HT setpoints, counter timing and beamline motion
receive no exemption from their qualification conditions.

The mode retains complete NI startup, one-owner exclusion, session/revision,
leases, fresh inputs, command serialization, uncertain-worker retention,
journal and circulation checks. Initialization displays the cold-state
operator premise: all stages and HT physically OFF, HT zero, VI/other clients
stopped, and fixed Chroma targets F3=COM10/F2=COM11/F1=COM12. The confirmed
Initialize binds that premise to this retained backend. It is an operator
attestation, not a measurement or physical qualification. Close and attempted
HT energy effects invalidate it.

Stepped behavior
----------------

General performs the existing source General sequence. In this mode it does
not pre-open Chroma or start water automatically. It returns
``WAIT_OPERATOR_WATER``. Water can be started through the existing explicit
cooling command or the hardware controls. Later-stage permission requires
normal, fresh current-owner Canon/Section indications stabilized for the
existing two seconds. Stale/faulted inputs, stop, reinitialization and owner
changes invalidate the circulation-ready latch.

Chroma execution retains exact configured targets, 32-bit platform and DLL
hash validation, mutex/quiescence, timeout and worker-retention checks. Its
separate supervised-target permission does not change ``resources_verified``.
No Chroma serial call occurs during General's start preflight.

Cold supervised General Arrêt omits only the Python HT ramp preamble while the
operator cold-state premise remains valid and no HT energy effect was entered.
It still executes the complete source event-6 stop. In particular, source Focal
OFF is attempted; failures are recorded while remaining C4 stop frames are
attempted. Partial failure retains ownership and never reports physical OFF.
The existing 120-second cooling countdown still attempts General stop; trial
permission does not label automatic electrical protection as commissioned.

XP deployment
-------------

The r12 bundle contains 70 source/data files, build
``76311b8f213cf97c85658babd2818437adebbafce559ca239119e9f6f7166e0c``.
``INSTALL_R12.lnk`` was staged beside the previous shortcuts. Its additional
cold configuration transaction enables only the new permission field and
preserves every qualification flag, calibration, ownership record and journal.
It backs up the preceding base configuration and updates its manifest digest.

The operator installed it and initialized. Subsequent signed runtime reads
confirmed ``RUNNING``, complete startup, 21 retained tasks, test mode and current
cold attestation. The active session is
``f832e12c67284610b0ad1d8940af6193``. General capability was enabled without
changing physical qualification facts. No hardware command was sent by the
deployment tooling.

Web integration
---------------

The existing rich Modulateur UI already routes GENERAL/M through the single
telemetry Device Server. Two additional mismatches prevented usable control:
the local backend still validated a 19-operation legacy contract, and its
command route unconditionally required JWT although the laboratory entrypoint
deliberately exposes no login configuration. The old browser client also used
the request helper that removes approval headers.

The backend now imports the exact 24-operation pure command protocol directly.
The existing local counter-timing file received additive validator/executor
functions; the old monolithic Acquisition module was not replaced. The rich
UI/layout was preserved. Its narrow source edits are retained in
``docs/deployment_patches/elyse_rich_operator_web_2026-10-26.patch``; backend
contract/approval modules are the reviewed release files. The main tree's
richer Windows ACL authorization implementation was preserved, with only the
explicit mandatory-authorization argument backported.

The laboratory launcher explicitly enables LOCAL_CONSOLE approval only on
``http://127.0.0.1:5000``. It requires a literal local peer, exact Host and
Origin, and uses a server-owned local-console subject. Production/auth-required
or nonlocal requests retain JWT and the existing strict external approval
requirements. Forwarded headers and browser-supplied identities grant no role.

After the operator presses Confirmer, the UI requests one approval for the
unchanged operation/value/session/revision/device intent. This endpoint performs
only a current capability read. A persistent local key signs the stored nonce
record, including consumption state; atomic SQLite consumption permits one
dispatch only, with a 30-second expiry. The command path consumes approval
before its existing durable dispatch fence and Tango call. Lost responses and
unknown command outcomes are never automatically retried. Approval is not a
physical safety confirmation.

Key and approval storage are under
``F:\ELYSE_Telemetry_Server\postgres_v3\web-control``. Key bytes and approval
nonces are not recorded in this report. The telemetry recorder, archive,
Device Server and XP processes were not restarted by the web rollout. Only
the local web process changed from PID 51136 to PID 50328. Source/assets and
launch records are backed up under
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\web_operator_r12_20261026T104356Z``.

The optimized rich build is served as ``main.c1eeb324.js`` with SHA256
``e937d972193924eebbd62923b316837e90f5424cdec82b1f4fdb312b99e51aa0``.
Read-only live checks returned FRESH/RUNNING, test mode, LOCAL_CONSOLE and an
enabled General capability. A deliberately unused approval was issued to test
the non-actuating endpoint: 64-character nonce, 30-second expiry,
``dispatch_attempted=false``, ``hardware_writes=false``. The command endpoint
was not called by that verification.

The operator's first subsequent browser attempt arrived via the network
address ``10.20.30.202`` and was rejected with HTTP401 before dispatch. XP had
no command receipt, unchanged revision2, no General request or procedure, and
normal fresh reads. The operator was directed to the exact localhost page;
network rejection must not be treated as a native command failure or retried
automatically.

Validation
----------

* Actual CPython 3.4.4 x86: 149 tests passed in 20.790 seconds, including
  supervised backend/runtime, cold premise, manual-water behavior, partial-stop
  aggregation, prior parallel initialization and protocol regressions.
* Python3.12 with network denied: 518 passed, two opt-in skips, 31 existing
  warnings in 43.04 seconds for Acquisition unit coverage.
* Web API/approval coverage: 67 passed in 2.59 seconds with fake Tango only.
* The actual backported main backend, preserving its Windows ACL implementation,
  was preloaded and ran 36 route/local-approval tests successfully.
* Frontend helper/client: two Jest suites, 60 tests passed. The rich production
  build compiled successfully without replacing its layout.
* Actual Python3.4 parsed 64 source files and four installation utilities.

These checks establish software behavior and one successful XP initialization.
General actuation and subsequent physical stages remain operator observations;
they are not established by unit tests, approval issuance or a software receipt.
