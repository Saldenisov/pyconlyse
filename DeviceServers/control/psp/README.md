# DS_PSP (minimal receiver)

This device server is intentionally minimal.

- Device name: `manip/general/PSP`
- Server: `DS_PSP/1_PSP`
- Main command: `receive(string) -> "OK"`

## Purpose

Receive string payloads from LabVIEW and expose the latest data via Tango
attributes for the web/backend.

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

## LabVIEW-side contract

LabVIEW should call Tango command:

- Device: `manip/general/PSP`
- Command: `receive`
- Input: a single `string` payload

The command returns `"OK"` on success.
