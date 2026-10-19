# Existing ACQ agent / web Supervision: local software qualification

`main.py --supervision` extends the **existing** Python 3.4 acquisition agent.
It uses its original four-byte length-prefixed TCP/JSON listener on port 8765.
One process owns the simulator, procedure runtime, durable SQLite state, and
legacy telemetry. There is no separate HTTP acquisition server on port 8768.
The former `supervision_server.py` entry point now forwards to `main.py`.

```text
browser -> Pyconlyse Supervision API -> signed agent RPC on the existing port
        -> original CommandRouter + shared simulation backend + durable runtime
        -> acknowledgement, restored history, and software phase journal
```

## Covered software boundary

All 23 reviewed procedure plans (158 steps) execute against logical memory stubs
in simulation mode with `--supervision`. Magnet procedures are included in
software simulation only; unresolved physical ownership does not authorize a
DAQ fallback. No NI task, serial device, output voltage, or physical readback
is involved. The old `discover_only` configuration cannot enable this extension.

Legacy `ping`, capabilities, status, snapshot, and 472-field synthetic PSP
commands remain usable. Named procedures own outputs: unsigned legacy raw
output setters are disabled in integrated supervision mode. Digital procedure
images feed the existing simulated digital/PSP snapshots. Native logical analog
values are reported separately as `procedure_outputs`, **not calibrated volts**.
The scenario `fault` fails a procedure before its next output step; restoring
`idle` permits a new intent.

This qualifies current Python plans, not the complete original LabVIEW
acquisition. The documented additional 150 ms `cooling.stop` VI wait remains a
plan-parity gap. All 20 recovered setpoint arrows execute as named logical ACQ
simulation commands. Arrows are not blocked by busy DPS in LabVIEW: their short
atomic compare/write lane overlaps normal procedures without changing the
procedure's run or DPS. Orphan magnet PT, physical
readbacks and hardware activation are not implemented by this bridge. The two
additional named lifecycle commands are a software orchestration of explicit
synthetic returns, not a complete native acquisition scheduler or initializer.

## Explicit simulated ACQ cycle

`Cycle ACQ` exposes `Initialiser ACQ` (`acq.initialize`) and `Arrêt général ACQ`
(`acq.stop`) through the same authenticated intent endpoint, database and
single-flight owner. Initialization applies the 152 source-checked logical
startup commands (including Canon 21, Section 27.9 and HT 6.5), six counter
fixtures, five card fixtures, 27 PSP reference fixtures and two TPG sessions.
The five runtime-loop flags represent synthetic entry/join, not acquisition
threads or driver execution. Startup prefix System Exec/time synchronization,
real pilot reads, fallback/handler behavior and native scheduling are excluded.

General stop is **not** event6 `shutdown`. Its seven ordered outer-stop phases
come from the recovered `CONTROLLED_STOP` facet. The HT command is reduced by
0.1 with simulated 500-ms waits while `command >= 6.6`; it is not zeroed.
Done/Stop/Clear uses an explicit synthetic Done=True return, not a measured
deadline. C6[8] and C7[2] remain unchanged; no Focales OFF is invented. Cleanup
closes the 27 PSP/two TPG fixtures and resets stop30 only. It does not clear all
NI tasks or make all outputs zero. Same-frame effects and independent native
branches use a chosen serial simulation schedule, not native pulse timing.

Lifecycle state/phase/error is durable: `UNMANAGED`, `INITIALIZING`, `RUNNING`,
`STOPPING`, `STOPPED`, `FAULT`, `UNKNOWN`. Existing procedure-only sessions
migrate to `UNMANAGED` without resetting outputs or inventing initialization.
After explicit management begins, normal procedures/arrows require `RUNNING`;
arrows cannot race initialization or general stop. A new initialization while
RUNNING is rejected as already initialized; a reused immutable ID returns its
original receipt. Stop requires browser confirmation before submission.

Initialization fails before dependent later steps. Simulated general stop
attempts remaining effects and independent closes after individual failures,
retains partial images, and finishes `FAILED`/`FAULT`, never a false STOPPED.
An explicit new initialization or stop can be retried after a terminal fault.
Loss during INITIALIZING/STOPPING restores UNKNOWN in both ledgers and excludes
replay. Completed RUNNING/STOPPED logical simulation images survive restart
without repeating initialization; they do not certify restarted native tasks.

## Local run on Everest

From `C:\dev\pyconlyse`, using modern Python for the web host:

```powershell
python tools/run_elyse_supervision_local.py --frontend-build .tmp/elyse-agent-lifecycle-build-20261007
```

The harness requires actual Python 3.4 at `tools/xp_python34_extracted/python.exe`
(override with `--python34`). It creates a runtime key without printing contents,
starts the original agent on `127.0.0.1:8765`, checks a signed round trip, and
serves isolated Supervision at `http://127.0.0.1:5059/elyse`. It never restarts the
lab web service on port 5000, registers no live device routes, and never contacts
the acquisition computer. This loopback-only development harness is
unauthenticated: do not expose it to a LAN or the Internet. Generated state is
in `legacy/xp_acq_agent/runtime/everest-supervision`, ignored by Git.

In `Supervision / ACQ`, select a page/control, save an intent, and submit it to
simulation. Business events and ACQ phases are restored from the server. Reuse
the same state directory on later runs; do not delete it to make unresolved
work appear idle. `--acq-port` and `--web-port` select other local test ports
without terminating an existing process. Default wait scale is 1;
`--time-scale 0` accelerates software tests, not hardware timing qualification.

The first arrow on an uninitialized field requires an explicit finite simulation
base. No zero or physical readback is invented. Subsequent arrows use the
restored ACQ value as a readonly base. Arithmetic and native clamps match the
20-rule crosswalk, including `>> Att HF` adding 1, not 5, and Fluides having no
native clamp. These are logical native units, not calibrated voltages or
commissioned physical safety limits. Clients name a page/control/base; they
cannot supply a raw target, delta or range.

## Deployable agent entry point

The portable ZIP contains the original agent plus its extension, not a parallel
server. Do not overwrite `C:\xp_elyse_deployment` or stop LabVIEW to test stubs.
For a future operator-approved install on the acquisition host, Python 3.4.4
is assumed at `C:\Python34\python.exe`; the simulation entry point is:

```bat
C:\Python34\python.exe generate_supervision_key.py runtime\acq.key
start_supervision.bat
```

For a local standalone agent with that Python installation, use
`start_supervision_local.bat`. Key generation refuses to replace an existing
file. Protect keys with Windows ACLs; keep them outside the browser/static tree.
The ZIP contains no keys, runtime database, vendor binary, or NI task adapter.

The modern web backend connects explicitly:

```powershell
$env:ELYSE_ACQ_URL = "tcp://127.0.0.1:8765"
$env:ELYSE_ACQ_LOCAL_SIMULATION = "true"
$env:ELYSE_ACQ_SHARED_KEY_FILE = "C:\ProgramData\Pyconlyse\acq.key"
```

For a future remote simulator, use `tcp://10.20.30.10:8765`. Keep the real web
backend's existing JWT/CSRF/device-auth settings enabled. No browser receives
the key. Missing configuration remains disconnected; loopback needs explicit
local-simulation opt-in. The remote installation was not changed or tested.

## Admission and recovery

- ACQ checks session/revision atomically. All 29 DPS bits gate procedure
  admission. One procedure runs at a time; completion resets only its own bit.
- Immutable intent ID/payload is deduplicated durably before revision/busy
  checks. Changed payload under the same ID is rejected. Reload/restart and
  repeated clicks never resend an accepted intent.
- Steps and logical images are journalled. Failure stops later steps and
  preserves partial simulated changes; this is not physical rollback.
- Named setpoints atomically compare session/revision and the previous value.
  The value and terminal success commit together; deduplication never adds the
  delta twice. Procedure and arrow IDs share a namespace. Setpoint faults leave
  values unchanged. Any UNKNOWN outcome blocks both lanes, unlike ordinary
  busy DPS. Selecting an older intent restores its own phase journal.
- Timeout, disconnect, bad signature, or malformed response yields `UNKNOWN`,
  never automatic resend. Authenticated terminal history for the original
  acceptance session resolves lost receipts after restart or a later client.
- Process loss during work preserves `UNKNOWN` and its DPS bit on restart.
  Operator-assisted resolution is not implemented. Never delete a live state
  database/ownership file to bypass exclusion or infer safe physical state.
- Stopping the harness terminates only its own agent child. Unfinished work
  remains unresolved at next startup; no hardware shutdown is claimed.

## Signed extension of the original protocol

The outer request remains `{id, command, params}`. For `command: supervision`,
params contain exactly `method`, `path`, `payload`, `timestamp`, `nonce`, and
`signature`. HMAC-SHA256 uses a distinct `RPC/GET` or `RPC/POST` domain and
authenticates responses. Every request is verified before the old volatile
response cache. Nonce replay is rejected; clock tolerance is 30 s and the
signed body/frame limit is 65536 bytes.

| Signed logical route | Purpose |
| --- | --- |
| `GET /v1/state` | Session, revision, simulated quality, 29 DPS bits, active/latest run |
| `POST /v1/intents` | Named procedure with ID and expected session/revision |
| `GET /v1/intents/<id>` | Durable result and original acceptance session |
| `GET /v1/trace/<id>` | Software phase journal |
| `GET /v1/outputs` | Shared logical image, not physical readback |
| `GET /v1/setpoints` | Six nullable logical fields with session/revision |
| `GET /v1/lifecycle` | Durable simulated cycle/phase/error with session/revision |
| `GET /v1/observation` | Atomic state/lifecycle/setpoint observation for web polling |
| `POST /v1/setpoints` | Named arrow with immutable ID, explicit base and session/revision |
| `POST /v1/replay/saved-xnode` | Stateless isolated replay of five saved APP-17 bodies; no acquisition-data or output binding |

Only authenticated status 409 with `accepted: false` proves non-acceptance.
Other uncertain outcomes retain exclusion. Responses retain
`execution_allowed: false`, `hardware_writes: false`, and
`physical_status: NOT_EXECUTED`. HMAC does not encrypt. Python 3.4 is
[end-of-life](https://www.python.org/downloads/release/python-344/); restrict the
service to isolated lab networks. It is neither a public production server nor
a hardware safety system.

## Verification and packaging

Actual Python 3.4 portable tests, from the extracted package:

```bat
C:\Python34\python.exe -m unittest discover -s tests -p "test_supervision*.py" -v
```

Repository tests launch actual loopback Python 3.4 agents:

```powershell
python -m pytest tests/web/test_elyse_supervision_business.py tests/web/test_elyse_acq_process_integration.py tests/web/test_elyse_acq_tcp_integration.py tests/web/test_elyse_acq_transport.py -q
python tools/build_elyse_acq_supervision.py --output .tmp/elyse-acq-agent-unified-py34.zip
```

The builder verifies exact plan/crosswalk parity, uses an explicit source
allowlist, and refuses to replace a ZIP. `manifest.json` records source hashes
and the real single-agent entry point. It is not a digital signature. Keys,
runtime databases, vendor binaries, and hardware task adapters are excluded.

The shared `elyse_agent/saved_xnode.py` core also supplies pyconlyse's
`saved_xnode` web replay operation. `data/saved_xnode_contract.json` maps exact
APP-17 UIDs, input order, formula bodies and 29 border pairs to pinned source
evidence. True error status skips input evaluation and returns 0.0; false
status computes even with nonzero error code. Two bodies are saved inside a
Disabled frame and remain isolated replay fixtures. Finite bounded inputs,
nonzero ratio denominators and finite results are required. Python validation
refusals do not simulate native error codes. No native VI equivalence,
scheduler behavior, engineering units or live telemetry is qualified.
# Saved timing adapter replay

`POST /v1/replay/saved-timing` uses the shared Python 3.4 core
`elyse_agent/saved_timing.py`. Exact payload: `source_id`, `uid`, `inputs`.
Only source `APP-17` and saved bodies `19070`, `32991`, `32954` are admitted.
The web replay operation `saved_timing` uses the same functions.

`19070` returns saved template `62172`; its unwired Source Name/Period faces
do not override that snapshot. `32991` returns template `63524`.
`32954` projects field5, `Finished Late? [i-1]`, from an explicitly supplied
29-field Timing object. JSON storage types are validated; no native coercion
or runtime default is inferred. `19142` remains rejected because its Error
output has no qualified saved producer.

These calls are stateless, do not submit intents, and do not consult runtime
or outputs. Constants and numeric Mode values do not implement a scheduler,
period units, CPU assignments, deadlines, or late-cycle policies. No hardware
or source VI executes. Source bodies, terminal pairs, wires and SHA256 pins
are recorded in `data/saved_timing_contract.json`.

# Saved NI6220 completed-return replay

`POST /v1/replay/ni6220-means` and web operation `saved_ni6220` use one
Python 3.4 core, `elyse_agent/saved_ni6220.py`. Payload requires `source_id`,
`uid`, `returned_channels`, `sample_count`, and `read_error`. Only `APP-08`
loop `612` is admitted. Returned rows and error are explicit snapshots.

Saved loop N caps channel means: sixteen returned rows with N=10 yield ten
means. The fixed False scaling branch passes those means unchanged. Returned
DAQ error remains independent of the data calculation, including status=True.
This does not release a blocked read or establish error-handler/cleanup timing.

JSON replay requires nonnegative I32 N, rectangular finite numeric rows within
4096 cells, and explicit error status/code/source. Validation is replay policy.
Native Mean bitwise parity, negative N, selected empty rows, DAQ returns and
live telemetry remain unqualified. Existing input-task reads still use their
separate strict all-channel model. No hardware adapter or live read changes.
# Saved initializer caller routing

Signed stateless `POST /v1/replay/initializer-frame` and web operation
`saved_initializer` share `elyse_agent/saved_initializer.py`. Supply
`source_id: "APP-00"`, frame `uid: "227"`, four ordered `fixtures`
(`tasks`, `error_out`) and exact selected `clear_returns`. Frame `133`
instead takes `read_error`, `fallback_result` and `clear_returns`.
All external returns are supplied; no VI, initializer or Clear call runs.
Opaque tokens do not prove valid tasks. Error status selects branches;
nonzero code alone does not. Fallback preserves original read error separately.
JSON limits are replay storage policy, not LabVIEW coercion or defaults.
# Saved final cleanup routing

Signed stateless `POST /v1/replay/cleanup-frame` and web `saved_cleanup`
replay APP-00 frame246 with explicit `outer_joined`, `stop_before`,
`psp_error_seed`, two opaque `tpg_sessions`, an inert `schedule` and exact
selected `returned_errors`. Events are `psp_close` with `index`, `tpg_close`
with `bank`, `handler` with `node_uid`, `stop_reset`, and `frame_returned`.
Return records have `node_uid`, `iteration` (PSP index or null) and `error`.
The PSP register is uninitialized; no default seed is inferred. Handler
outputs are unused. Reset30=False is independent of close errors. Partial
schedules may stop before a close or handler returns. No resource closes;
frame return proves only supplied node completion, never physical success.

# Saved request facets

Signed stateless `POST /v1/replay/request-facet` and web `saved_requests`
share `elyse_agent/saved_requests.py`. Supervision payload requires
`facet: "supervision_dps"`, `source_id: "APP-17"`, exact page frame `uid`,
`page` (`ht`, `modulator`, `fluides`, `magnets`, `hf`), `gate_dps`,
`adjustments`, `commands`, and `base_dps`. Both DPS vectors have 29 Booleans.
Gate and bundle-base values come from different saved local-read sites;
atomic sampling and PSP delivery remain unqualified. Command and adjustment
vectors are extracted scalar terminal values, not decoded Page clusters.
If any gate or adjustment bit is True, this writer facet is skipped and
JSON `base_dps` must be null. Other event branches are outside this replay.
Otherwise supplied base is copied and only mapped command fields change.
All-False commands still select the write. Existing modern helpers retain
their single-snapshot projection and public signatures.

Acquisition payload requires `facet: "acquisition_entry"`,
`source_id: "APP-00"`, `uid: "43"`, `event_index` 3..25 and Boolean
`new_value`. False skips sequence entry; True retains raw U32 duration
1000 for event3 or 150 otherwise. Event25 registration flags are preserved
without assigning a scheduler policy. No event, writer or device call runs.

# Saved Acquisition dispatch and handler-tail facets

Signed stateless `POST /v1/replay/dispatch-facet` and web `saved_dispatch`
share `elyse_agent/saved_dispatch.py`. Supply exact `source_id: "APP-00"`,
`uid`, `facet`, Boolean `dps` list29 and `event_index`.
For `dispatch`, UID is `8105` and event index is null. Lowest True field
selects its one-based case. All-False selects case0/ACTION=False. Cases1..24
retain their two True property assignments; DPS22 has a property target
without a registered procedure event. Tail selectors25..29 return
`SAVED_DEFAULT` and write ACTION=False without property assignments/events.
Selector8105 saved default0/frame9471 is independently corroborated by original
heap readers and a native20.0.1f1 static print. Literal85221/raw0000 connects
through wire42492 to local19100/bank35. Original12 source execution and native
runtime equivalence remain unqualified. Replay retains the selected index and
does not clear requests. Static proof pins are in the dispatch contract.

For `reset` or `publication`, supply event3..25 and exact respective saved
frame UID from `data/saved_dispatch_contract.json`. Reset clears only that
event's mapped field. Publication forwards its independently supplied read
snapshot, which may differ from reset output. Reaching each frame is a
supplied precondition. No procedure/property/event/PSP write runs, and reset
is not acknowledgement of delivery or success. Modern 24-field plan bridge
retains its separate slice policy and explicit orphan-plan refusal.

# Saved Timeout PSP read caller

Signed stateless `POST /v1/replay/psp-read-frame` and web `saved_psp_reads`
share `elyse_agent/saved_psp_reads.py`. Supply `source_id: "APP-00"`,
`uid: "10115"`, `frame_returned: true`, all twelve `defaults` and
`returns`, plus Boolean `stop_before` and `tcp_ed_before`. Each return has
`data` and `error` (`status`, `code`, `source`). Reader UID selects exact
cluster length and Boolean/float element representation. Float JSON values
must be finite floats. Shapes, I32 code and source length are replay policy.

Each returned error feeds the next reader. Each returned data tuple is
assigned to its own bank even when error.status is True; native read-on-error
substitution is outside this caller model. Only final EPC reader error.status
selects two False assignments to stop30 and TCP ED45. Earlier errors may be
cleared by later supplied returns. Default tuples represent separate local
reads; no global epoch or identity with actual native returned data is inferred.
Complete-frame reachability is supplied. Partial writes, stalls, native PSP
delivery/freshness and real Wait/event timing remain unqualified. No PSP call
or device write runs, and local data-write order is not made atomic.

### Saved Supervision read slices

`POST /v1/replay/supervision-read-slice` and web operation `saved_sup_reads` replay APP-17 sequence13595 frames14799/15121 (13 supplied reader returns) or independent frame49696 reader51964. Returned data always reaches its saved local assignment. First chain/independent Error inputs are unwired; last chain Error crosses sequence local34531; independent returned Error is unused. Data/reference objects remain supplied opaque snapshots. No native Refnum decoding,PSP default substitution,delivery,freshness,atomicity,downstream consumer or whole Timeout equivalence is claimed.

### Saved stop-local transitions

`POST /v1/replay/stop-trace` and web operation `saved_stop` replay explicit APP-00 stop-local tokens or completed-frame reset postconditions. Three supplied error-arm entries retain two PSP-write arms setting stop30/TCP45 True and one PSP-read arm setting both False. Each runtime loop consumes its captured stop value after supplied body completion; an exited loop cannot restart in the same trace. Five loops must exit before the outer TCP read. Reset pairs are independent writes, not atomic transactions. Caller order, body completion, error-arm entry and external stop changes are supplied. Scheduling, liveness, native errors/defaults, restart epochs, transport delivery and physical stopping remain unqualified. No equipment operation runs.
