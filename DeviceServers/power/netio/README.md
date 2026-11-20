# NETIO Tango driver

`DS_Netio_pdu` uses the authenticated native JSON API. Firmware version, model,
serial number, and age of the last valid native snapshot are exposed as read-only
Tango attributes. A reply must contain a valid identity and unique output IDs
with binary states before it can replace the output cache. A different serial
number is rejected until the device is deliberately reinitialized.

Output writes contain only the requested output IDs. Actions 5 (no change) and
6 (readback/default) are omitted. Firmware 2.4.4 was observed returning HTTP 200
while ignoring an entire mixed action array containing Action 5. Replaying
cached states of unrelated outlets would introduce a separate power-control
race and must not be used as a workaround.

Writes are serialized with lifecycle/status reads. HTTP failures, malformed
replies, and unconfirmed ON/OFF states fail the Tango command. A lost reply has
an unknown outcome: the driver does not automatically resend a power command.
Timed pulse actions retain their native asynchronous behavior.

## Firmware maintenance

Use the official [PowerPDU 4PS archive](https://www.netio-products.com/en/powerpdu-4ps-firmware)
and [universal firmware instructions](https://www.netio-products.com/en/universal-firmware-download-page).
Export full configuration before and after maintenance; backups contain secrets
and must remain outside Git. Preserve IP configuration, users, output names,
power-up defaults, restart settings, and API settings across schema migrations.

The vendor's universal upgrade path requires 4.0.5 with MCU 1.55, then the
transitional 5.0.0 package, then 5.3.3. MCU packages restart physical outputs;
stop dependent acquisition and complete required lamp/camera cooling first.
Verify the actual version and serial after every transition. A completed HTTP
upload or a device reboot does not prove that firmware changed. Do not downgrade
after a version whose release notes prohibit it.

Restarting a NETIO Tango server itself performs discovery/status reads and does
not switch physical outputs. Restart one named server through its Tango Starter,
wait for the prior process to exit, then verify firmware/serial, ON state, fresh
native snapshots, and unchanged physical output states. Preserve controlled
startup registration and startup level.

## Software-only checks

```powershell
python -m pytest tests/unit/test_netio_output_actions.py -q
```

Tests cover partial actions, unrelated output preservation, legacy/current
payloads, invalid replies, uncertain writes without replay, and HTTP success
without the requested state change. They do not contact equipment.
