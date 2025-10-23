# iTest PSU Web Client - Tab Configuration Guide

## Overview

The iTest PSU web client now supports a tabbed interface with three predefined tabs:
- **VD** - Vacuum Diode configuration
- **VD2** - Vacuum Diode 2 configuration  
- **RF** - Radio Frequency configuration

Each tab can display specific slots in a custom order with predefined default values.

## Features

1. **Tabbed Layout** - Switch between VD, VD2, and RF tabs
2. **Load Defaults** - Button to apply predefined current values for all slots in the active tab
3. **Enable All Slots** - Master toggle to turn on/off all slots in the active tab
4. **Custom Slot Order** - Define which slots appear in each tab and in what order
5. **Compact Display** - Modern card-based layout showing all slots simultaneously

## Configuration in Tango DB

### Property: `tab_config`

Add a device property called `tab_config` to your iTest PSU device in the Tango database. The value should be a JSON string with the following structure:

```json
{
  "VD": {
    "slots": [1, 2, 3],
    "defaults": {
      "1": 0.5,
      "2": 1.0,
      "3": 0.75
    }
  },
  "VD2": {
    "slots": [4, 5],
    "defaults": {
      "4": 2.0,
      "5": 1.5
    }
  },
  "RF": {
    "slots": [6, 7, 8],
    "defaults": {
      "6": 0.1,
      "7": 0.2,
      "8": 0.15
    }
  }
}
```

### Configuration Fields

For each tab (VD, VD2, RF):

- **`slots`** (array of integers): List of slot IDs to display in this tab, in the order they should appear
- **`defaults`** (object): Key-value pairs where keys are slot IDs (as strings) and values are the default current in Amperes

### Example: Using Jive or Python

#### Using Jive (Tango GUI Tool)

1. Open Jive
2. Navigate to your device (e.g., `elyse/pdu/itest`)
3. Right-click → "Device Wizard" → "Properties"
4. Add or edit property: `tab_config`
5. Set the value as a single-line JSON string (minified):

```json
{"VD":{"slots":[1,2,3],"defaults":{"1":0.5,"2":1.0,"3":0.75}},"VD2":{"slots":[4,5],"defaults":{"4":2.0,"5":1.5}},"RF":{"slots":[6,7,8],"defaults":{"6":0.1,"7":0.2,"8":0.15}}}
```

#### Using Python Script

```python
import tango
import json

# Connect to database
db = tango.Database()

# Define configuration
config = {
    "VD": {
        "slots": [1, 2, 3],
        "defaults": {
            "1": 0.5,
            "2": 1.0,
            "3": 0.75
        }
    },
    "VD2": {
        "slots": [4, 5],
        "defaults": {
            "4": 2.0,
            "5": 1.5
        }
    },
    "RF": {
        "slots": [6, 7, 8],
        "defaults": {
            "6": 0.1,
            "7": 0.2,
            "8": 0.15
        }
    }
}

# Convert to JSON string
config_json = json.dumps(config)

# Set device property
device_name = "elyse/pdu/itest"
db.put_device_property(device_name, {"tab_config": config_json})

print(f"Tab configuration set for {device_name}")
```

## Default Behavior

If the `tab_config` property is not set or is invalid:
- All three tabs (VD, VD2, RF) will be available
- No slots will be assigned to any tab (empty slots arrays)
- No default values will be available
- The "Load Defaults" button will have no effect

## Usage in Web Client

1. **Switch Tabs**: Click on VD, VD2, or RF tab buttons at the top
2. **View Slots**: All slots configured for the active tab are displayed as cards
3. **Load Defaults**: Click "Load Defaults" to set all slots to their configured default currents
4. **Enable/Disable All**: Use the "Enable All Slots" checkbox to turn all outputs on/off for the current tab
5. **Individual Control**: Each slot card has:
   - Toggle switch for output on/off
   - Current readings (setpoint and measured)
   - Input field to set new current value
   - Displays the current limits for that slot

## Slot Configuration Reference

The slot configuration (`config` property) should already be set up with slot names and limits:

```json
{
  "S1": ["VD Slot 1", [-5.0, 15.0]],
  "S2": ["VD Slot 2", [-5.0, 15.0]],
  "S3": ["VD Slot 3", [-5.0, 15.0]],
  "S4": ["VD2 Slot 1", [-5.0, 15.0]],
  "S5": ["VD2 Slot 2", [-5.0, 15.0]],
  "S6": ["RF Slot 1", [-2.0, 10.0]],
  "S7": ["RF Slot 2", [-2.0, 10.0]],
  "S8": ["RF Slot 3", [-2.0, 10.0]]
}
```

This defines:
- Slot names that appear in the UI
- Current limits [min, max] for validation

## Tips

1. **Slot Order**: The order of slots in the `slots` array determines the visual order in the UI
2. **Validation**: Default values must be within the slot's configured current limits
3. **Flexibility**: You can assign any slot to any tab - the tab names are just organizational
4. **Updates**: After changing `tab_config`, refresh the web page to load the new configuration
