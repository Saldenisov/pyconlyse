# iTest PSU Tango Device Server

A minimal Tango Device Server to control an iTest/ITECH-like power supply over Ethernet via SCPI.

Features:
- Starting current setpoint from a JSON config or a Tango device property
- Commands to bump current by ±0.01 A (fine) and ±0.1 A (coarse)
- Attributes for measured current/voltage and the current setpoint

## Install dependency

Recommended on Windows:

```powershell
conda install -c conda-forge pytango
```

Or with pip (if a wheel is available for your Python):

```powershell
python -m pip install PyTango
```

## Files

- `scpi_client.py` – tiny TCP SCPI client
- `DS_itest_psu.py` – Tango Device implementation (supports output selection by name)
- `itest_psu_config.json` – example config with `start_current`

## Configure

Device properties supported:
- `Host` (string): PSU IP (e.g., `10.20.30.24`)
- `Port` (int, default 5025)
- `StartCurrent` (double, default 0.0)
- `ConfigPath` (string, optional): path to JSON with `{ "start_current": <float> }`
- `EnableOutputOnInit` (bool, default False)
- `EOL` (string, default "\n"): one of `\n`, `\r\n`, `\r`
- `RackHosts` (string, optional): comma-separated host[:port]; leave empty for single IP
- `ChannelsPerRack` (int, default 1): used if no output names defined in config

Example JSON config (with output names and templates):

```json
```
{
  "start_current": 0.25,
  "outputs": ["Rack1_Out1", "Rack1_Out2", "Rack2_Out1", "Rack2_Out2"],
  "commands": {
    "select_output": "INST:SEL '{name}'",
    "set_current": "SOUR:CURR {value:.4f}",
    "get_current": "SOUR:CURR?",
    "measure_current": "MEAS:CURR?",
    "measure_voltage": "MEAS:VOLT?",
    "output_on": "OUTP ON",
    "output_off": "OUTP OFF",
    "get_output": "OUTP?"
  }
}
```
## Run with Tango DB

1) Create a new device class instance (e.g., via Jive):
   - Class: `ITestPSU`
- Executable: your Python with `DS_itest_psu.py`
   - Set device properties: `Host=10.20.30.24`, `Port=5025`, `ConfigPath=C:\\dev\\pyconlyse\\DeviceServers\\power\\iTest\\itest_psu_config.json` (or `StartCurrent`)

2) Start the server process:

```powershell
python C:\dev\pyconlyse\DeviceServers\power\iTest\DS_itest_psu.py ITestPSU/test
```

## Run without Tango DB

Create a property file `props.json` such as:

```json
{
  "device": {
    "Host": "10.20.30.24",
    "Port": 5025,
    "ConfigPath": "C:\\dev\\pyconlyse\\DeviceServers\\power\\iTest\\itest_psu_config.json",
    "EnableOutputOnInit": true,
    "EOL": "\n"
  }
}
```

Run with `-nodb -propfile`:

```powershell
python C:\dev\pyconlyse\DeviceServers\power\iTest\DS_itest_psu.py ITestPSU/test -nodb -propfile=props.json
```

## Use

Attributes:
- `CurrentSetpoint` (RW, A)
- `MeasuredCurrent` (RO, A)
- `MeasuredVoltage` (RO, V)

Commands:
- `IncCurrentFine`, `DecCurrentFine` → ±0.01 A (defaults to first output/channel)
- `IncCurrentCoarse`, `DecCurrentCoarse` → ±0.1 A
- `GetAllOutputs` → JSON with state and measurements for each output
- `OutputOn(name)`, `OutputOff(name)`
- `SetOutputCurrent([name, amps])`, `BumpOutputCurrent([name, delta])`

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

- The SCPI commands used are common defaults across many lab PSUs. If your iTest model uses different mnemonics, adjust `scpi_client.py` or tell me the exact strings and I’ll wire them in.
