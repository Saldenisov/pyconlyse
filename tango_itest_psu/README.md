# ITest PSU Tango Device Server

A minimal Tango Device Server to control an iTest/ITECH-like power supply over Ethernet via SCPI.

Features:
- Reads a starting current setpoint from a JSON config file or a Tango device property
- Commands to bump the current by ±0.01 A (fine) and ±0.1 A (coarse)
- Attributes for measured current/voltage and the current setpoint

## Installation

Recommended: conda (Windows-friendly):

```powershell
conda install -c conda-forge pytango
```

Or with pip (if a wheel is available for your Python):

```powershell
python -m pip install PyTango
```

## Files

- `scpi_client.py` – tiny TCP SCPI client
- `itest_psu_device.py` – Tango Device implementation
- `itest_psu_config.json` – example config with `start_current`

## Configuration

You can configure the device via Tango Database device properties or run without DB (`-nodb`) and pass properties via a file.

Device properties supported:
- `Host` (string): PSU IP (e.g., `10.20.30.24`)
- `Port` (int, default 5025): SCPI TCP port
- `StartCurrent` (double, default 0.0): starting setpoint if `ConfigPath` not provided
- `ConfigPath` (string, optional): path to JSON with `{ "start_current": <float> }`
- `EnableOutputOnInit` (bool, default False)
- `EOL` (string, default "\n"): one of `\n`, `\r\n`, `\r`

Example JSON config:

```json
{
  "start_current": 0.25
}
```

## Running with Tango DB

1) Create a new device class instance (e.g., via Jive):
   - Class: `ITestPSU`
   - Executable: your Python with `itest_psu_device.py`
   - Set device properties: `Host=10.20.30.24`, `Port=5025`, `ConfigPath=C:\\dev\\pyconlyse\\tango_itest_psu\\itest_psu_config.json` (or `StartCurrent`)

2) Start the server process:

```powershell
python C:\dev\pyconlyse\tango_itest_psu\itest_psu_device.py ITestPSU/test
```

## Running without Tango DB (ad-hoc)

Create a property file `props.json` such as:

```json
{
  "device": {
    "Host": "10.20.30.24",
    "Port": 5025,
    "ConfigPath": "C:\\dev\\pyconlyse\\tango_itest_psu\\itest_psu_config.json",
    "EnableOutputOnInit": true,
    "EOL": "\n"
  }
}
```

Then run with `-nodb -propfile`:

```powershell
python C:\dev\pyconlyse\tango_itest_psu\itest_psu_device.py ITestPSU/test -nodb -propfile=props.json
```

Note: When running without DB, you can still interact via `PyTango.DeviceProxy` using the exact device name you started with (e.g., `ITestPSU/test`).

## Using the device

Attributes:
- `CurrentSetpoint` (RW, A)
- `MeasuredCurrent` (RO, A)
- `MeasuredVoltage` (RO, V)

Commands:
- `IncCurrentFine`, `DecCurrentFine` → ±0.01 A
- `IncCurrentCoarse`, `DecCurrentCoarse` → ±0.1 A

Example with Python:

```python
from tango import DeviceProxy

d = DeviceProxy("ITestPSU/test")
print("IDN:", d.read_attribute("InstrumentId").value)
print("Cur setpoint:", d.read_attribute("CurrentSetpoint").value)
print("+0.01 →", d.command_inout("IncCurrentFine"))
print("-0.1 →", d.command_inout("DecCurrentCoarse"))
```

## Notes

- The SCPI commands used are common defaults. If your iTest/ITECH device uses different mnemonics, update `scpi_client.py` accordingly or open a PR to make them configurable.
- Output enable state is write-only by default due to inconsistent query support on some models. If your unit supports `OUTP?`, you can extend the implementation.
