# ELYSE acquisition TCP contract

## Boundary

The XP process is a hardware-adjacent agent, not a web server. A modern
PyConlyse/Tango backend connects to it over TCP and exposes browser-facing HTTP
and WebSocket APIs. This keeps browser dependencies and authentication off the
unsupported XP host.

## Framing

Each frame contains a four-byte unsigned big-endian payload length followed by
one UTF-8 JSON object. Maximum payload size is 1 MiB. Every request carries a
unique `id`; duplicate IDs with identical content are idempotent, while reuse
with different content is rejected. The opt-in telemetry commands below use
publication sequencing and fresh reads instead of this response cache.

Request:

```json
{"id":"b29...","command":"get_snapshot","params":{}}
```

Success:

```json
{"id":"b29...","ok":true,"result":{}}
```

Failure:

```json
{"id":"b29...","ok":false,"error":{"code":"command_error","message":"..."}}
```

## Copied Acquisition telemetry (opt-in)

`--labview-telemetry` disables the entire backend command set. Only `ping`,
`get_status`, `get_capabilities`, `ingest_labview_telemetry`, and
`get_labview_telemetry` remain. No NI/PSP backend is instantiated.
Development listener: `127.0.0.1:8766`, separate from an existing 8765 agent.
Only IPv4 loopback peers can ingest; this does not authenticate the producer.

Example request, explicitly synthetic:

```json
{"id":"fixture-0","command":"ingest_labview_telemetry","params":{"session_id":"acq-copy-20261012","publication":"C1NI6071E","sequence":0,"source_seconds_1904":3870000000.25,"producer_kind":"fixture","data":[1.5,null,-0.2],"error":{"status":false,"code":0,"source":""}}}
```

Accepted publication names are `C1NI6071E`, `C2NI6071E`, `C3_IN_DIO96`,
`C4_IN_DIO96`, `C5_IN_DIO96`, `EPS`, `EPC`, and `VTA`. These are saved VI
publication families, not an inferred card/channel geometry. `data` remains
opaque JSON; physical units and channel labels must be established separately.
The timestamp preserves LabVIEW seconds since 1904, without Unix conversion.
`producer_kind` is an unauthenticated claim: `fixture` or `copied_acquisition`.
The error object preserves producer status, integer code and source string.
Non-finite/unavailable values must use JSON `null`, not invented zeros.

Each publication has an independent sequence, integer 0..2^53-1. Newer packets
replace its latest value. Exact duplicates are acknowledged but do not refresh
receiver age; older or changed same-sequence packets are rejected. Restarting a
producer at sequence zero requires a new session and deliberate receiver
restart. Ingest always rechecks the peer and sequence, even for a reused request
ID. `get_labview_telemetry` always computes a fresh snapshot, including for a
reused request ID. Missing publications remain absent; age >=2 seconds is stale.
The 2-second threshold is a receiver default, not a proven hardware freshness
limit. There is no cross-publication atomicity or certified measurement quality.

Limit: eight latest publications, 256 KiB per publication, 8192 JSON nodes,
depth 12, strings 4096 characters. Oversized/invalid packets are rejected.
No full live VI publisher has been commissioned. Connecting the copied VI to
this endpoint requires separate source-wire and nonblocking-worker verification.

## Simulation lifecycle

1. `initialize` creates only in-memory state.
2. `set_simulation_scenario` selects `idle`, `beam_ready`, or `fault`.
3. `get_snapshot` returns complete emulated acquisition state.
4. `advance_simulation` advances deterministic time for tests.
5. `set_simulated_digital_output`, `set_simulated_analog_output`, and
   `set_simulated_counter_output` mutate only the in-memory output image.
6. `reset_simulated_outputs` restores the all-off/zero safe image.
7. `get_psp_catalog` returns the recovered raw `PSP_Supervision.vi` card-field
   names and their source task/index metadata.
8. `get_psp_snapshot` returns the same simulator image as 472 scalar PSP
   messages in `channel:value:source_timestamp` form plus a latest-value map.

The snapshot mirrors the recovered LabVIEW raw I/O geometry: 144 analog inputs,
176 digital inputs, 112 digital outputs, 40 analog outputs, and 8 counter
outputs. Output acknowledgements always carry `simulated: true` and
`hardware_writes: false`. No DAQmx task is created by these commands.

The same `get_snapshot` response envelope is retained when the backend later
changes from `simulation` to `discover_only` and then to commissioned DAQmx
input/output adapters.

## PSP Supervision compatibility

The observed LabVIEW/Tango path does not publish one vector per NI card.
`PSP_Supervision.vi` emits one scalar string per cluster field. `DS_PSP`
parses the first two colons as `channel`, `value`, and optional source
timestamp, then builds its latest-value dictionary.

`get_psp_snapshot` mirrors that boundary without contacting Tango or NI PSP:

```json
{
  "format": "psp_supervision_scalar_v1",
  "payload_format": "channel:value:source_timestamp",
  "channel_count": 472,
  "data": {"07 CPB7 b67 M/A Eclairage Ecran 1": 1.0},
  "payloads": ["07 CPB7 b67 M/A Eclairage Ecran 1:1:1690000000.000000"],
  "hardware_writes": false
}
```

The catalog contains 456 active AI/DI/DO/AO fields and 16 confirmed C10
delay/width fields. Sixteen unresolved legacy C11 timing fields are excluded
instead of being fabricated. Counter delay/width values are exported in the
microsecond units observed on the SuperVision synchronization page; the
in-memory mutation API continues to accept seconds.

## Cutover sequence

1. Web supervision and integration tests use simulation exclusively.
2. Read-only DAQmx discovery validates installed driver and device inventory.
3. Input tasks run in shadow mode while LabVIEW remains authoritative.
4. Output polarity, safe states, interlocks, and rollback are commissioned.
5. One configuration change selects the production adapter; TCP clients do not
   change.
