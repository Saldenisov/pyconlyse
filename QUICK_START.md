# Quick Start: LabVIEW Variable Access

## ✅ What We Have

- **Server**: `eureka` (10.20.30.10)
- **Port 3580**: NI-PSP Server ✓ CONFIRMED OPEN
- **Library**: `SUPERVISION`
- **Variables**: 27 variables (see `variable_list.py`)

## 📋 Complete Variable List

```
C1011NI6602    C1201TAG      C1NI6071C     C2NI6071E
C3_IN_DIO96    C3_OUT_DIO96  C4_IN_DIO96   C4_OUT_DIO96
C5_IN_DIO96    C5_OUT_DIO96  C6NI6703      C7NI6703
C8NI6703       C9NI6703      DPC           DPS
EPC            EPS           IT            VAM-A
VAM-S          VDD           VDM-A         VDM-S
VTA            VTL           VTS
```

## 🚀 Quick Start (After Installing NI Software)

### Step 1: Install NI LabVIEW Runtime
Download from: https://www.ni.com/en-us/support/downloads/software-products.html

### Step 2: Test Single Variable
```python
import clr
clr.AddReference("NationalInstruments.NetworkVariable")
from NationalInstruments.NetworkVariable import NetworkVariableBufferedSubscriber

subscriber = NetworkVariableBufferedSubscriber("\\\\eureka\\SUPERVISION\\C1011NI6602")
subscriber.Connect()
value = subscriber.ReadData().GetValue()
print(f"Value: {value}")
subscriber.Disconnect()
```

### Step 3: Read All Variables
```bash
python test_read_all.py
```

This will:
- Read all 27 variables
- Display values in console
- Save snapshot to `supervision_snapshot.json`

### Step 4: Continuous Monitoring
```bash
python ni_multi_variable_manager.py
```

Menu options:
1. List all variables
2. Read all variables once
3. **Monitor continuously** (updates every second)
4. **Export to CSV** (for data logging)
5. Read single variable
6. Write to variable

## 📁 Files

| File | Purpose |
|------|---------|
| `variable_list.py` | List of all 27 SUPERVISION variables |
| `test_read_all.py` | Quick test - read all variables once |
| `ni_multi_variable_manager.py` | Full-featured manager with monitoring & CSV export |
| `ni_variable_dotnet_client.py` | Base client class (used by manager) |
| `README_NI_VARIABLES.md` | Complete documentation |

## 💡 Common Use Cases

### Read All Variables Once
```python
from variable_list import SUPERVISION_VARIABLES
from ni_variable_dotnet_client import NIVariableManager

manager = NIVariableManager("eureka")

for var_name in SUPERVISION_VARIABLES:
    value = manager.read_variable('SUPERVISION', var_name)
    print(f"{var_name}: {value}")

manager.close()
```

### Monitor Specific Variables
```python
import time
from ni_variable_dotnet_client import NIVariableManager

manager = NIVariableManager("eureka")

watch_list = ['C1011NI6602', 'DPC', 'VTA']

while True:
    for var in watch_list:
        value = manager.read_variable('SUPERVISION', var)
        print(f"{var}: {value}", end="  ")
    print()
    time.sleep(1)
```

### Log to CSV (10 minutes)
```python
from ni_multi_variable_manager import SupervisionVariableManager
from variable_list import SUPERVISION_VARIABLES

manager = SupervisionVariableManager()
manager.set_variables(SUPERVISION_VARIABLES)
manager.export_to_csv('data.csv', duration=600, interval=1.0)
```

### Write Variable
```python
from ni_variable_dotnet_client import NIVariableManager

manager = NIVariableManager("eureka")
manager.write_variable('SUPERVISION', 'C1011NI6602', 123.45)
manager.close()
```

## 🔧 Current Status

✅ Network access to eureka confirmed  
✅ Port 3580 open  
✅ `pythonnet` installed  
✅ All 27 variables identified  
✅ Scripts ready  
❌ **NI LabVIEW Runtime not installed** ← Install this next!

## 📞 Next Steps

1. **Install NI LabVIEW Runtime**
2. Run `python test_read_all.py` to verify
3. Use `ni_multi_variable_manager.py` for your data acquisition system

## 🎯 Example Output (After Installation)

```
Reading 27 variables from eureka/SUPERVISION
======================================================================
✓ C1011NI6602         = 25.3
✓ C1201TAG           = 100.5
✓ C1NI6071C          = 0.0
✓ DPC                = 1.013
✓ VTA                = 298.15
...
✓ VTS                = 273.15

Summary
======================================================================
Total variables: 27
Successfully read: 27
Errors: 0

✓ Saved snapshot to supervision_snapshot.json
```

## 📖 Documentation

See `README_NI_VARIABLES.md` for complete documentation including:
- Troubleshooting
- Alternative protocols (OPC UA)
- Advanced usage
- API reference
