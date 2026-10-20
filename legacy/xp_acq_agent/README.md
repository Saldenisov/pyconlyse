# ELYSE acquisition XP agent

## Distinct server entry points

`main.py` below describes the original discovery/simulation service (port 8765).
Its hardware-write block does not describe the separate
`acquisition_server.pyw` GUI/default port-8771 NI runtime. That GUI starts cold
in IDLE; explicit local initialization configures cards and writes startup AO/DO
images. General and fourteen additional source-stage paths are implemented on the
NI owner; the latter require `stage_controls_verified`, default false. The
cooling-trip branch additionally requires `cooling_trip_verified`, default
false. Standalone HT supply start/stop/reset additionally require the independent
`ht_controls_verified`, default false. They do not ramp voltage or independently
acknowledge supply OFF; legacy General Arrêt cannot clear their release
requirement. Only existing General buttons are exposed in the GUI; the new local
stage API has no HTTP/Tango route or GUI activation button.
Focales additionally requires `focal_controls_verified` and qualified serial
resources. Its native ON/OFF workers share ownership with General OFF; a failed
kill/join blocks later outputs and NI release until quiescence is confirmed.
Native worker exit does not establish physical OFF.
HTTP exposes authenticated reads, not control. Deinitialization is resource
release, not electrical shutdown.

The prepared GUI reports protocol 2, a fresh boot session, a source/data
fingerprint and a lifecycle revision. Production initialization acquires
`<absolute-config-path>.ownership` before NI initialization; an unreleased or
unqualified prior marker blocks a cold window in `RECOVERY_REQUIRED`. Successful
cleanup releases only this session's exact marker. Local electrical-OFF
confirmation alone cannot clear a prior owner: a qualified parent/native-child/
NI-competitor absence checker is also required, and none is shipped by default.
This is cooperative config-path ownership, not machine-wide NI exclusion.

The explicit Windows Startup installer now writes a cold supervisor launcher.
It permits at most three delayed restarts after confirmed nonzero child exits;
normal exit is not respawned. A live or unresponsive owner is not killed or
replaced. Its config-scoped OS lock and pre-spawn child journal block duplicate
launches after ambiguous supervisor failure. These small ownership journals
contain no telemetry; no history or SQLite is introduced. No Startup entry was
installed or updated by the source/test change.
Deliberate local prior-child recovery requires a held matching OS guard and
qualified evidence bound to the exact journal identity/bytes. No production
Windows checker is included: ambiguous journals stay blocked, not deleted on a
PID-only guess. Unattended restart/recovery remains unqualified.

Everest exposes the separate Python runtime through `AcqRuntime.runtime_json`
and the authenticated read-only web path `/api/elyse/acquisition/runtime`.
The Python Acquisition tab shows six validated input banks only while fresh,
with separate transport and NI ages. It does not substitute the 27-bank LabVIEW
bridge, PSP or simulator values. No web hardware commands are enabled. The
unwired `acquisition_command_admission.py` is an offline/local protocol
foundation, disabled by default, not an installed control endpoint.

See [current cross-layer status](../../docs/ELYSE_BUSINESS_LOGIC_STATUS.md) before
interpreting model coverage or historical package results as deployment parity.
Site-specific configuration and private keys are intentionally not committed.
`config.acquisition.example.json` requires a separately generated private key and
explicit site review; its unverified flags are not commissioning approval.
`--demo` selects a fake backend explicitly; it is never an automatic fallback.

Python 3.4-compatible, fail-closed bridge for the legacy `ACQUISITION.vi` host.

Current release provides:

- length-prefixed TCP/JSON command service;
- NI-DAQmx device and channel discovery without task creation;
- recovered task/channel/calibration inventory;
- recovered AI/DI task constructors behind an explicit resource-reservation gate;
- inert, all-11-card initialization plan with corrected NI6602 low ticks and
  separate initial delay, RSE analog-input mode, startup DO/AO images, and
  NI6703 logical-to-voltage conversion;
- a separate, manually gated NI-DAQmx task adapter for all 11 cards. It can
  configure tasks and exposes explicit read, startup-output, and counter
  operations, but is not reachable from the TCP service;
- deterministic simulation mode;
- stateful emulation of the recovered digital, analog, and counter output image;
- synthetic acquisition snapshots for `idle`, `beam_ready`, and `fault` scenarios;
- `PSP_Supervision.vi`-compatible scalar snapshots with 472 recovered raw
  card-field names and `channel:value:source_timestamp` payloads;
- JSONL audit log and idempotent request IDs;
- pure conversion functions for recovered calibration formulae;
- an unconditional hardware-write block.

The network service deliberately does **not** create DAQmx tasks, reserve
devices, change output states, or expose the recovered task constructors.
Without the supervision extension, the original TCP service does not reproduce
the 23 mutating event procedures.
Output support remains
blocked until polarity, wiring, interlocks, safe values, and rollback behaviour
are commissioned against the real installation.

## Integrated web Supervision simulation (2026-10-07)

`main.py --supervision` extends the EXISTING Python 3.4 agent/listener on port
8765. It accepts signed, named simulation intents and persists
acknowledgements, phase events, logical output images, and all 29 DPS flags in
SQLite. All 23 reviewed plans run against logical stubs, including magnet plans;
physical ownership/DAQ fallback remains blocked. One process/backend supplies
legacy telemetry and Supervision. Default discover-only configuration stays
unchanged; the extension requires simulation mode. The former standalone entry
point now forwards to the original agent. No hardware operation is exposed.

See [SUPERVISION.md](SUPERVISION.md) for the local Everest harness, key handling,
the web connection, recovery semantics, tests, and unresolved hardware boundary.

## One-card analog input probe

`probe_inputs.pyw` is a separate, manually operated XP GUI. It discovers the
installed NI devices and tests one analog input, or all analog inputs, on card
1 (`PCI-6071E`), card 2 (`PCI-6071E`), or card 11 (`PCI-6220`). Each measurement
creates one software-timed analog-input task, reads one voltage, then closes
the task. It saves JSONL results to `runtime/input_probe.jsonl`. It does not
modify the running simulator or expose input probing through TCP.

Live XP verification on 2026-09-28 found NI-DAQmx 9.6.2 and all 11 expected
devices. With `DIFFERENTIAL` on every channel, each analog scan stopped at
`ai8` with NI error `-200077`: the driver permits `RSE` or `NRSE` there.
The diagnostic whole-card scan now uses `DIFFERENTIAL` for `ai0:7` and `RSE`
for `ai8+`. It completed 64/64, 64/64, and 16/16 voltage reads respectively.
These raw voltages establish Python/driver access, not correct terminal wiring,
signal meaning, calibration, timing, or equivalence to `ACQUISITION.vi`.
The diagnostic terminal-mode split is **not** LabVIEW parity: the native
`1_ACQ_INIT_NI6071E.vi` and `1_ACQ_INIT_NI6220.vi` diagrams use RSE on all
their analog inputs. The full acquisition constructors in `input_tasks.py`
and `hardware_tasks.py` now request RSE but remain gated and must not be
treated as validated initialization.

The separate `Audit all NI devices (no tasks)` action subsequently queried
the serial number, simulated flag, and six physical-channel collections on
each of the 11 real cards without creating a task or taking a reading. All
66 channel-collection queries succeeded; the full XP journal was copied to
`tools/xp_acq_input_probe_v1/input_probe.jsonl`. This is a driver/capability
audit, not a live signal test of the eight remaining cards. See
`docs/XP_NI_11_CARD_AUDIT_2026-09-28.md` for the per-card result and the
before/after LabVIEW experiment boundary.

The local inert startup plan now uses source-wire-corrected digital images:
`C3_DIO96_DO[1,4]=True` (cooling stops), `C4_DIO96_DO[1,4,6,8,17,19]=True`,
and `C5_DIO96_DO[33]=True` (laser stop). The saved LabVIEW constant captions
for C3 and C5 are transposed. See
`docs/ELYSE_ACQ_STARTUP_COMMAND_VECTOR_AUDIT_2026-09-29.md`. This correction
has not been deployed to XP. The simple TCP simulator still starts with zeroed
emulated outputs; its `initialize` response is not yet a replay of the full
LabVIEW startup procedure.

Digital input probing of the `PCI-DIO-96` cards is intentionally excluded:
configuring an 8255 input port can reset neighboring output ports. Output and
counter tasks are also excluded. NI MAX inventory can still confirm that all
cards are present without configuring their ports.

## Recovered full-card adapter: staged, not commissioned

`elyse_agent.hardware_plan.card_initialization_plan()` produces an inert
description of cards 1–11 without importing NI-DAQmx or touching devices.
`elyse_agent.hardware_tasks.create_legacy_card_tasks()` is a separate manual
adapter. Both `authorized=True` and `outputs_commissioned=True` are required
before it creates any task. Neither flag can be set through the TCP protocol
or service configuration. Construction does not start counters or write
outputs; `start_legacy_counters()` and `write_initial_images()` are separate,
explicit operations. Do not invoke this adapter on the acquisition computer
until LabVIEW is stopped and the physical output wiring, polarity, safe
startup state, transient behavior, and rollback are independently confirmed.

The native NI6602 initialization sets `initial_delay_ticks=0` for all eight
counters. The distinct low-tick values are in `data/ni6602_timing.csv`.
Later runtime reconfiguration maps `Délai` in microseconds to **both**
initial-delay and low ticks; `Largeur` maps to high ticks. The adapter
accepts physical counters 0–7 only: the parent's logical counter selection
has not been proven. Counter property changes, DIO line grouping, output
polarity, analog per-channel ranges, LabVIEW error handling, and the complete
event/PSP lifecycle still require commissioning or further native review.
The adapter must not be described as hardware-validated or equivalent to
`ACQUISITION.vi`.

## XP deployment

1. Install Python 3.4.4 x86 from the verified offline bundle.
2. Run the bundle's `install_offline.py` from IDLE to install the pinned wheels.
3. Copy this directory to `C:\elyse_acq_agent`.
4. Run `discover_once.bat` only while LabVIEW is stopped or when the operator has
   explicitly accepted concurrent read-only NI-DAQmx enumeration.
5. Run `start_agent.bat` for the command service.

The production configuration binds to `10.20.30.10:8765` in `discover_only`
mode. `allow_hardware_writes` must remain `false`; setting it to `true` aborts
startup.

## Protocol

Each message is a four-byte unsigned big-endian payload length followed by a
UTF-8 JSON object:

```json
{"id":"request-1","command":"ping","params":{}}
```

Supported commands include `ping`, `initialize`, `get_status`,
`get_capabilities`, `get_channel_summary`, `discover_hardware`,
`describe_legacy_tasks`, `get_snapshot`, `set_simulation_scenario`, and
`advance_simulation`, `set_simulated_digital_output`,
`set_simulated_analog_output`, `set_simulated_counter_output`, and
`reset_simulated_outputs`, `get_psp_catalog`, and `get_psp_snapshot`. See
`PROTOCOL.md` for the migration contract.

Simulation output commands mutate memory only. Every acknowledgement and
snapshot reports `hardware_writes: false`; the discover-only backend rejects
the same commands. This lets supervision exercise the future output contract
without creating or writing any NI-DAQmx task.

Start the safe simulator with `start_simulator.bat`. It creates no NI-DAQmx
tasks and performs no hardware access. A client can stream compact telemetry:

```text
C:\Python34\python.exe demo_stream.py --host 10.20.30.10 --scenario beam_ready
```

## Copied LabVIEW telemetry bridge (2026-10-12, fixture-tested on XP)

The opt-in `--labview-telemetry` mode reuses this agent's TCP/JSON listener.
It creates **no backend**, NI task, PSP connection or hardware command path.
Only `ping`, `get_status`, `get_capabilities`, `ingest_labview_telemetry` and
`get_labview_telemetry` are available. Normal simulation/discovery behavior is
unchanged without the flag. Supervision, discover-once and initialization
flags cannot be combined with telemetry mode.

Development configuration uses loopback port 8766, leaving an existing 8765
agent untouched. Receiver CLI equivalent (XP tests used the GUI, not this command):

```text
C:\Python34\python.exe main.py --config config.labview-telemetry.json --labview-telemetry --telemetry-session acq-copy-20261012
```

`telemetry_receiver.pyw` is an alternative manual GUI launcher. Opening it does
not bind a listener; the operator must press Start. This launcher hardwires
loopback port 8766 and telemetry-only mode even if the JSON configuration is
changed. It displays missing/stale/latest values and stops only its own TCP
receiver. It does not start, stop or modify LabVIEW. Its Start, Stop, restart and
window-close paths were exercised on XP using the existing Python/Tkinter
installation. The receiver was closed after the synthetic commissioning test;
this work did not leave a new listener running.

An explicit `--bind 0.0.0.0` is available only in this non-actuating mode for
remote readers. The XP network/firewall and permitted readers still require
operator review; no system setting has been changed. Binding only to
`10.20.30.10` is rejected in this mode because it would exclude the required
loopback publisher. Locality is checked on every ingest, including repeated
request IDs; it is **not** authentication of the LabVIEW process.

`data/labview_telemetry_fixture.json` is a synthetic three-value test packet,
not a real card image. Frame it with the existing four-byte big-endian UTF-8
JSON byte length. Native LabVIEW sender can use an already serialized ASCII
JSON string, String Length, a four-byte big-endian flattened header,
Concatenate Strings and TCP Write. A request acknowledgement must be read
and framed with TCP Read; no NI/PSP operation belongs in the helper.
The new native `ACQ_Telemetry_Send_JSON.vi` was built through the XP LabVIEW
2012 UI, saved in the copied project and run with the synthetic packet only.
It opens `127.0.0.1:8766`, writes the length-prefixed request, reads the
four-byte response header, type-casts it, reads the bounded body and closes
the connection. Connection and error wires chain Open -> Write -> Read header
-> Read body -> Close; final error goes to an indicator. All four blocking TCP
operations have an explicit 1000 ms timeout each, not a verified total deadline.
Its length values are I32: for positive sizes below the protocol limit, their
four-byte big-endian representation equals U32.

The range indicator checks `1 <= ACK length < 65536`, but the coerce output
feeds TCP Read directly: this is **not strict rejection** of an invalid length.
The VI displays the raw ACK JSON and does not validate `id`, `ok` or `accepted`.
Request-size guarding, general UTF-8/JSON serialization, connector-pane wiring,
bounded queue and separate worker loop remain absent. The helper must not yet
be inserted into a live Acquisition loop.

Packet requires exactly `session_id`, `publication`, `sequence`,
`source_seconds_1904`, `producer_kind`, `data`, `error`. Publications are the
eight saved runtime families: `C1NI6071E`, `C2NI6071E`, `EPS`, `EPC`, `VTA`,
`C3_IN_DIO96`, `C4_IN_DIO96`, `C5_IN_DIO96`. Payload preserves JSON values;
it does not assume pin mappings, units, array sizes or cluster schema.
LabVIEW timestamp remains seconds since 1904, distinct from receiver UTC and
monotonic age. `producer_kind` is `fixture` or `copied_acquisition`; both are
unverified producer claims. Nonfinite values must be encoded as `null` with
appropriate producer error/quality evidence, not silently replaced by zero.

Each publication has a monotonic sequence within an explicitly configured
session. Same-sequence identical retransmission acknowledges without
refreshing age; older or changed same-sequence packets are rejected. After
producer restart, change session and restart receiver deliberately. Eight
latest images are retained in RAM only. Size, nesting and item limits apply.
Reads bypass the legacy response cache; missing images are missing, not
generated simulation values. At age >= 2 seconds each publication is stale.
LabVIEW error cluster is retained independently. Publications are **not**
an atomic whole-machine snapshot, and are never labeled physically verified.

On XP, original folder was copied via Explorer while original VI remained
running: `C:\PILOTAGE_ELYSE_ACQ` -> `C:\ELYSE_ACQ_TELEMETRY_20261012`.
`ACQ_Telemetry_Copy.lvproj` was transferred into that copy, brought forward,
and its root reference replaced through LabVIEW's project UI with
`C:\ELYSE_ACQ_TELEMETRY_20261012\ACQUISITION.llb\0_ACQ_ELYSE.vi`.
The copied project and standalone telemetry helper were saved.
No original VI has been edited, saved or run by this work. No sender is
connected to live values. The full copied Acquisition has not been run.
The fresh XP folder was copied back through the RDP redirected drive and
archived locally at
`C:\dev\ELYSE-ACQ-telemetry\2026-10-12\ACQ_Telemetry_XP_fixture_verified_20261012.zip`.
All 214 ZIP file entries were SHA-256 checked against the copied folder
(5,891,359 bytes uncompressed; ZIP 3,326,203 bytes). Archive SHA-256:
`FE3E497383F93C17E3B6356BC572034F787F581A2479C6B7ABC8C80CEEDABCB8`.
Fresh `ACQUISITION.llb` hash matches the earlier original baseline:
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
The archive includes the copied folder, helper, project and staged agent,
including Python bytecode caches produced by the fixture test. Successful
ingests remained in RAM; no runtime audit journal was captured in this folder.
Manual results below are recorded observations, not a persisted packet trace.
The archive does not include every external NI `instr.lib` dependency and is
not a complete machine backup. The authoritative updated status is this README;
the archived agent README preserves its earlier, pre-commissioning wording.

The updated local `lvkit` checkout extracted the saved helper without VI or
generated-code execution. `tools/validate_acq_telemetry_sender.py` pins source
and XML hashes and checks all 24 wires, 9 primitives plus concatenation, one
diagram, no subVI calls, destination/port/constants and disabled RunOnOpen.
Its audit report is
`C:\dev\ELYSE-ACQ-telemetry\2026-10-12\helper_static_audit.json`.

Manual XP commissioning used `id=lv-fixture-0`, `publication=C1NI6071E`,
`sequence=0`, `producer_kind=fixture`, `data=[1.5,null,-0.2]`:

| Condition | Observed result | Scope |
| --- | --- | --- |
| Receiver running | `ok:true`, `accepted:true`, `duplicate:false`; VI error 0 | Synthetic packet only |
| Identical packet repeated | `duplicate:true`; receiver timestamp/age not refreshed | Duplicate handling, not a new measurement |
| Receiver stopped | VI finished with TCP Open error 56; ACK cleared, range false | Failure reported; elapsed duration not measured |
| Receiver restarted | `accepted:true`, `duplicate:false`; VI error 0 | RAM store intentionally reset |
| Receiver window closed | Own GUI exited and listener stopped | Original Acquisition untouched |

Other seven publication families remained missing. No actual NI measurement,
LAN reader, live-data tap, startup/shutdown or hardware output was tested.

Before integration: verify project application instance and copied reference
paths; harden and test the pure fixture sender; use a bounded nonblocking queue
or lossy mailbox to duplicate existing read values into a separate telemetry loop. Do
not block the acquisition loop on TCP, route telemetry errors into legacy
stop/error wires, create second NI tasks or run the full copied Acquisition
while original owns hardware. Actual startup requires a separate safe switch
plan and operator approval. Commands toward LabVIEW remain absent.

## Tests

Telemetry changes and legacy regression suite: 869 tests passed in 51.481 s
on local Python 3.4.4 (`tools/xp_python34_testenv/Scripts/python.exe`). Hardware
tests use mock adapters; telemetry integration uses loopback only. Separate
manual XP/LabVIEW TCP commissioning above proves the synthetic fixture path,
not live card telemetry or whole-Acquisition equivalence. Six modern-Python
static-audit/mutation tests separately exercise the saved helper validator.

```text
C:\Python34\python.exe -m unittest discover -s tests -v
```
