# LabVIEW Shared Variables - Python Access Guide

## Your Setup

- **LabVIEW Server**: `eureka` (10.20.30.10)
- **Protocol**: NI-PSP (Port 3580) ✓ CONFIRMED OPEN
- **Example Variable**: `ni.var.psp://eureka/SUPERVISION/C1011NI6602`
  - Library: `SUPERVISION`
  - Variable: `C1011NI6602`

## Current Status

✅ Network connectivity confirmed  
✅ Port 3580 (NI-PSP Server) is accessible  
✅ `pythonnet` installed  
❌ NI .NET assemblies not installed on this machine  
❌ OPC UA not enabled on LabVIEW server  

## Solutions

### Option 1: Install NI Software (RECOMMENDED)

To read/write variables from Python, install:

1. **NI LabVIEW Runtime** (free)
   - Download: https://www.ni.com/en-us/support/downloads/software-products.html
   - Search for "LabVIEW Runtime"
   
2. **NI Measurement & Automation Explorer (MAX)** (included with Runtime)

After installation, use `ni_variable_dotnet_client.py`:

```python
from ni_variable_dotnet_client import NIVariableManager

manager = NIVariableManager(host="eureka")

# Read variable
value = manager.read_variable('SUPERVISION', 'C1011NI6602')
print(f"Value: {value}")

# Write variable
manager.write_variable('SUPERVISION', 'C1011NI6602', 123.45)

manager.close()
```

### Option 2: Enable OPC UA on LabVIEW Server

If you have access to the LabVIEW server, enable OPC UA:

1. Open LabVIEW project on `eureka`
2. Enable OPC UA Server in project settings
3. Use `ni_variable_opcua_client.py` from Python:

```python
from ni_variable_opcua_client import OPCUAVariableClient

client = OPCUAVariableClient(host="eureka", port=4840)
client.connect()
variables = client.browse_variables()
client.disconnect()
```

### Option 3: Use Remote Machine with NI Software

Run Python scripts from a machine that already has NI software installed and can access the network.

## Files Created

| File | Purpose |
|------|---------|
| `discover_ni_variables.py` | Network discovery (confirms port 3580 open) |
| `ni_variable_dotnet_client.py` | **Main client** - requires NI .NET assemblies |
| `ni_variable_opcua_client.py` | OPC UA client (if enabled on server) |
| `ni_psp_client.py` | Low-level PSP protocol attempts |

## Variable URL Format

```
ni.var.psp://hostname/library/variable
ni.var.psp://eureka/SUPERVISION/C1011NI6602
           └─host──┘ └─library─┘ └─variable─┘
```

Equivalent UNC path for NI APIs:
```
\\eureka\SUPERVISION\C1011NI6602
```

## Quick Test After Installing NI Software

```python
import clr
clr.AddReference("NationalInstruments.NetworkVariable")
from NationalInstruments.NetworkVariable import NetworkVariableBufferedSubscriber

# Connect and read
subscriber = NetworkVariableBufferedSubscriber("\\\\eureka\\SUPERVISION\\C1011NI6602")
subscriber.Connect()
value = subscriber.ReadData().GetValue()
print(f"C1011NI6602 = {value}")
subscriber.Disconnect()
```

## Discovering More Variables

Once NI software is installed, you can:

1. **Use NI MAX GUI**
   - Open Measurement & Automation Explorer
   - Navigate to Network → eureka → Shared Variables
   - Browse all available variables

2. **Browse programmatically** (after NI install):
   ```python
   from ni_variable_dotnet_client import NIVariableManager
   
   manager = NIVariableManager("eureka")
   # List all variables in SUPERVISION library
   # (requires browsing API - check NI documentation)
   ```

3. **Check LabVIEW Project File** (.lvproj)
   - Look for `<Item Name="SUPERVISION">` 
   - Lists all variables in that library

## DataSocket Alternative

If DataSocket Server is enabled on `eureka`, you can access variables via HTTP:

```python
import urllib.request

url = "http://eureka/datasocket/SUPERVISION/C1011NI6602"
response = urllib.request.urlopen(url)
value = response.read()
```

*(Currently not enabled based on port scan results)*

## Troubleshooting

### "Could not load NationalInstruments.NetworkVariable"
- Install NI LabVIEW Runtime
- Verify installation: Check `C:\Program Files\National Instruments\` exists

### Connection Timeout
- Verify network: `ping eureka` or `ping 10.20.30.10`
- Check firewall allows port 3580
- Confirm Shared Variable Engine is running on `eureka`

### Variable Not Found
- Verify exact names (case-sensitive)
- Check spelling: `SUPERVISION` vs `supervision`
- Use NI MAX to browse available variables

## Next Steps

1. **Install NI LabVIEW Runtime** on this machine
2. **Test** `ni_variable_dotnet_client.py`
3. **Discover** other variables in the SUPERVISION library
4. **Build** your data acquisition system using `NIVariableManager`

## Example: Continuous Monitoring

```python
import time
from ni_variable_dotnet_client import NIVariableManager

manager = NIVariableManager("eureka")

try:
    while True:
        value = manager.read_variable('SUPERVISION', 'C1011NI6602')
        print(f"{time.strftime('%H:%M:%S')} - C1011NI6602: {value}")
        time.sleep(1)  # Read every second
except KeyboardInterrupt:
    print("Stopped")
finally:
    manager.close()
```

## Support

- NI Documentation: https://www.ni.com/docs/
- NI Forums: https://forums.ni.com/
- LabVIEW Community: https://www.ni.com/en-us/support/documentation/labview.html
