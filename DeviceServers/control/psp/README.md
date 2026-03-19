# DS_PSP (minimal receiver)

This device server receives PSP strings and keeps FIFO history.

- Device name: `manip/general/PSP`
- Server: `DS_PSP/1_PSP`
- Main command: `receive(string) -> "OK"`

## Purpose

Receive string payloads from LabVIEW, keep FIFO history (global + per group),
and expose latest values/history to backend/frontend.

No Python bridge script is required in this workflow.

## Register in Tango DB

```bash
cd /Users/sad/dev/pyconlyse/DeviceServers/control/psp
python add_ds_PSP.py
```

## Start server

```bash
cd /Users/sad/dev/pyconlyse/DeviceServers/control/psp
python DS_PSP.py 1_PSP
```

## Read attributes

- `last_payload`
- `last_timestamp`
- `messages_received`
- `last_sender` (RW)
- `last_payload_json`
- `fifo_size` (RW)
- `fifo_total_cached`
- `group_counts_json`

## History / latest commands

- `get_group_history_json("vacuum|1800|5000")`
  Returns JSON with last 30 minutes (`1800` seconds) of `vacuum` group,
  capped to `5000` samples.
- `get_history_json(seconds)`
  Returns JSON list of global FIFO items in the requested time window.
- `get_latest_values_json()`
  Returns JSON map `{channel: latest_value}` and counters.
- `get_groups_json()`
  Returns JSON with group names and current FIFO counts.
- `clear_fifo("all")` or `clear_fifo("vacuum")`
  Clears all FIFO or one specific group.

## Outbound control commands (stub write path)

Because Python DS on macOS cannot directly write NI PSP variables, the server now
acts as a command mailbox for LabVIEW:

- Web/API writes command to DS queue
- LabVIEW polls DS queue and executes command on PSP side
- LabVIEW sends back ack/result

Supported enqueue commands:

- `write_variable_json('{"name":"elyse/hf/attenuator/set","value":0.25}')`
- `set_variable_value_json(...)`
- `set_channel_value_json(...)`
- `write_variable("channel=value")` (fallback)

Queue / ack commands:

- `get_pending_commands_json(limit)`
- `pop_pending_commands_json(limit)`
- `acknowledge_command_json('{"id":123,"ok":true,"message":"done"}')`
- `get_command_history_json(limit)`
- `clear_pending_commands()`

Related attributes:

- `pending_commands_count`
- `commands_received_total`
- `commands_ack_total`
- `last_command_json`
- `last_command_ack_json`
- `command_fifo_size` (RW)

## LabVIEW-side contract

LabVIEW should call Tango command:

- Device: `manip/general/PSP`
- Command: `receive`
- Input: a single `string` payload

The command returns `"OK"` on success.
