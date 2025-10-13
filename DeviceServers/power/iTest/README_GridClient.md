# iTest PSU Enhanced Grid Client

Enhanced grid-based client for iTest Power Supply Units that follows the OWIS device server pattern - **one Device Server controlling multiple slots with a clean grid interface**.

## Overview

This implementation demonstrates how to create a client for iTest devices that:
- Uses **grid layout** instead of multiple tabs
- Has **one Itest DS** controlling multiple slots (similar to how OWIS DS controls 4 cards)
- Provides comprehensive per-slot control and monitoring
- Supports batch operations and automated sequences
- Offers live monitoring and updates

## Key Features

### 1. Grid-Based Layout
- **Flexible slots per row** (1-4 slots per row based on total slot count)
  - 1-4 slots: single row
  - 5-8 slots: 2 rows of up to 4 slots each  
  - 9-12 slots: 3 rows of up to 4 slots each
  - 12+ slots: 4 slots per row (scalable)
- Each slot has its own control widget with:
  - Output ON/OFF control
  - Current setpoint (spinbox + slider + adjustment buttons)
  - Live measurements (current, voltage, power)
  - Visual status indicators

### 2. Single Device Server Architecture
- One `DS_iTest_PSU` device server manages multiple slots
- Slots are discovered automatically via `INST:LIST?` SCPI command
- No need for separate DS instances per slot
- Follows the OWIS pattern where one DS controls multiple units

### 3. Multi-Slot Task Management
- **Sequence execution** across multiple slots
- **Batch operations** (All ON, All OFF, Zero All)
- **Current ramping** with coordinated timing
- **Automated test sequences**
- **Safety monitoring** during operations

## Architecture Comparison

### OWIS DS Pattern (Reference)
```
One DS_OWIS_PS90 Device Server
├── Axis 1 (pos1 attribute)
├── Axis 2 (pos2 attribute) 
├── Axis 3 (pos3 attribute)
└── Axis 4 (pos4 attribute)
```

### iTest DS Pattern (This Implementation)
```
One DS_iTest_PSU Device Server
├── Slot 1 (controlled via SetOutputCurrent/OutputOn commands)
├── Slot 2 (controlled via SetOutputCurrent/OutputOn commands)
├── Slot 3 (controlled via SetOutputCurrent/OutputOn commands)
└── Slot N (controlled via SetOutputCurrent/OutputOn commands)
```

## Installation and Setup

### 1. Device Server Configuration

Configure your iTest device server with properties for multi-slot operation:

```python
# Device Server Properties
Host = "192.168.1.100"              # iTest PSU IP address
Port = 5025                         # SCPI port (default 5025)
RackHosts = ""                      # For multi-rack: "192.168.1.100,192.168.1.101"
ChannelsPerRack = 8                 # Number of slots per rack
UseDiscovery = True                 # Auto-discover slots via INST:LIST?
SafeCurrentMin = -5.0              # Safety limits
SafeCurrentMax = 5.0
OutputAliases = '{"1": "Gate", "2": "Drain", "3": "Source", "4": "Bulk"}'  # Optional slot aliases
```

### 2. Starting the Device Server

```bash
# Start the device server
python DS_itest_psu.py test/itest/psu01

# Or via Astor/database registration
```

### 3. Launching the Grid Client

#### From PyConlyse Main Application
```bash
# The iTest client is now integrated into PyConlyse main app
# Just click the "iTest PSU" button and select your configuration
# Or use keyboard shortcut Ctrl+I (if configured)
python main_app/main_gui.py
```

#### Standalone Mode
```bash
# Launch standalone grid client
python DeviceServers/power/iTest/DS_iTest_PSU_client.py --standalone test/itest/psu01

# With task manager disabled
python DeviceServers/power/iTest/DS_iTest_PSU_client.py --standalone test/itest/psu01 --no-tasks

# Light theme
python DeviceServers/power/iTest/DS_iTest_PSU_client.py --standalone test/itest/psu01 --theme light
```

#### Direct Integration (for developers)
```python
from DeviceServers.power.iTest.DS_iTest_GridClient import ITestGridClient

# Create and show grid client
client = ITestGridClient("test/itest/psu01")
client.show()
```

#### With Task Manager (Advanced)
```python
from DeviceServers.power.iTest.DS_iTest_GridClient import ITestGridClient
from DeviceServers.power.iTest.ITestTaskManager import integrate_task_manager

# Create grid client with task management
client = ITestGridClient("test/itest/psu01")
task_manager = integrate_task_manager(client)
client.show()
```

## Usage Examples

### 1. Basic Grid Control

The grid client automatically discovers available slots and creates individual control widgets.
**Example with 8 slots** (2 rows of 4):

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│   Slot 1    │   Slot 2    │   Slot 3    │   Slot 4    │
│  (Gate1)    │  (Drain1)   │  (Source1)  │  (Bulk1)    │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ ON │ OFF    │ ON │ OFF    │ ON │ OFF    │ ON │ OFF    │
│ [-0.1][-0.01][+0.01][+0.1]│ (similar)   │ (similar)   │
│ Current: 1.25A             │             │             │
│ I: 1.247A                  │ I: 0.000A   │ I: 2.150A   │
│ V: 3.45V                   │ V: 0.00V    │ V: 1.85V    │
│ P: 4.302W                  │ P: 0.000W   │ P: 3.978W   │
├─────────────┼─────────────┼─────────────┼─────────────┤
│   Slot 5    │   Slot 6    │   Slot 7    │   Slot 8    │
│  (Gate2)    │  (Drain2)   │  (Source2)  │  (Bulk2)    │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ ON │ OFF    │ ON │ OFF    │ ON │ OFF    │ ON │ OFF    │
│ (similar controls and measurements for slots 5-8)       │
└─────────────┴─────────────┴─────────────┴─────────────┘
     [Refresh] [All ON] [All OFF] [Zero All]
```

### 2. Batch Operations

Use the toolbar buttons for coordinated control:

```python
# All operations work across all discovered slots
client.all_on_btn.click()      # Turn all outputs ON
client.all_off_btn.click()     # Turn all outputs OFF  
client.zero_all_btn.click()    # Set all currents to 0A
```

### 3. Task Sequences

Define and execute automated sequences:

```python
from ITestTaskManager import TaskSequence, Task, TaskType

# Create a current step test sequence
sequence = TaskSequence(
    sequence_id="characterization",
    name="Device Characterization",
    tasks=[
        Task("init", TaskType.OUTPUT_CONTROL, ["Gate", "Drain"], {"enable": False}),
        Task("set_gate", TaskType.SET_CURRENT, ["Gate"], {"current": -2.0}),
        Task("enable_gate", TaskType.OUTPUT_CONTROL, ["Gate"], {"enable": True}),
        Task("ramp_drain", TaskType.RAMP_CURRENT, ["Drain"], {
            "start_current": 0.0, "end_current": 3.0, "duration": 10.0, "steps": 30
        }),
        Task("measure", TaskType.MEASURE, [], {}),
        Task("ramp_down", TaskType.RAMP_CURRENT, ["Drain"], {
            "start_current": 3.0, "end_current": 0.0, "duration": 5.0, "steps": 10
        }),
        Task("cleanup", TaskType.OUTPUT_CONTROL, [], {"enable": False}),
    ]
)

# Execute via task manager
task_manager.executor.execute_sequence(sequence)
```

### 4. Configuration Examples

#### Single Rack Configuration
```python
# Single iTest PSU with 8 slots
device_properties = {
    "Host": "192.168.1.100",
    "Port": 5025,
    "ChannelsPerRack": 8,
    "UseDiscovery": True,
    "OutputAliases": '{"1": "VGS1", "2": "VGS2", "3": "VDS1", "4": "VDS2"}'
}
```

#### Multi-Rack Configuration
```python
# Two iTest PSUs (16 slots total)
device_properties = {
    "RackHosts": "192.168.1.100:5025,192.168.1.101:5025",
    "ChannelsPerRack": 8,
    "UseDiscovery": True,
    "SafeCurrentMin": -10.0,
    "SafeCurrentMax": 10.0
}
```

## Key Advantages

### 1. No Tab Proliferation
- **Before**: Separate tabs for each slot → cluttered interface
- **After**: Clean grid layout showing all slots at once

### 2. Unified Control
- **Before**: Multiple device servers, one per slot
- **After**: Single device server manages all slots (like OWIS)

### 3. Coordinated Operations
- Batch operations across multiple slots
- Synchronized sequences and timing
- Safety monitoring across all channels

### 4. Live Monitoring
- Real-time updates for all slots
- Visual status indicators
- Power calculation and display

## Technical Implementation Details

### Grid Layout Algorithm
```python
# Dynamic grid layout based on number of slots
total_slots = len(slot_infos)
if total_slots <= 4:
    grid_cols = total_slots  # 1-4 slots: single row
elif total_slots <= 8:
    grid_cols = 4  # 5-8 slots: 2 rows of up to 4
elif total_slots <= 12:
    grid_cols = 4  # 9-12 slots: 3 rows of up to 4
else:
    grid_cols = 4  # >12 slots: 4 slots per row (scalable)
    
for i, slot_info in enumerate(slot_infos):
    row = i // grid_cols
    col = i % grid_cols
    self.grid_layout.addWidget(slot_widget, row, col)
```

### Device Discovery
```python
# Automatic slot discovery via SCPI
def _discover_outputs_via_scpi(self):
    raw = scpi.query("INST:LIST?")  # e.g., "1,2819;2,2819;3,2819;4,2819"
    for entry in raw.split(";"):
        slot_str, model_str = entry.split(",", 1)
        slot = int(slot_str.strip())
        model = model_str.strip()
        name = f"slot_{slot}_model_{model}"
        # Create slot info...
```

### Multi-Slot Commands
```python
# Commands work with slot names
device.command_inout("SetOutputCurrent", ("slot_1_model_2819", 1.5))
device.command_inout("OutputOn", "slot_1_model_2819")

# Batch operations iterate through all slots
for slot_name in available_slots:
    device.command_inout("SetOutputCurrent", (slot_name, target_current))
```

## Comparison: Before vs After

| Aspect | Old Approach | New Grid Approach |
|--------|-------------|------------------|
| **Layout** | Multiple tabs | Single grid view |
| **Device Servers** | One DS per slot | One DS for all slots |
| **Coordination** | Manual, per-tab | Automated batch operations |
| **Monitoring** | Switch between tabs | All slots visible at once |
| **Complexity** | N device servers | 1 device server |
| **Similar to** | - | OWIS 4-axis control |

## Files Overview

```
DeviceServers/power/iTest/
├── DS_iTest_GridClient.py          # Main grid client implementation
├── ITestTaskManager.py             # Task and sequence management
├── DS_itest_psu.py                 # Device server (existing, enhanced)
├── DS_iTest_PSU_Widget.py          # Original widget (reference)
├── README_GridClient.md            # This documentation
└── config_examples/
    ├── single_rack.json            # Single PSU configuration
    ├── multi_rack.json             # Multi-PSU configuration  
    └── test_sequences.json         # Example test sequences
```

## Troubleshooting

### Connection Issues
```bash
# Test device connectivity
telnet 192.168.1.100 5025
*IDN?
INST:LIST?
```

### Discovery Problems
```python
# Manual slot configuration if discovery fails
device_properties = {
    "UseDiscovery": False,
    "outputs": ["slot_1", "slot_2", "slot_3", "slot_4"]
}
```

### Performance Optimization
```python
# Adjust update intervals
self.update_timer.start(500)  # 500ms instead of 1000ms

# Limit concurrent operations
max_concurrent_slots = 4
```

## Future Enhancements

1. **Graphical Plotting**: Real-time current/voltage plots per slot
2. **Data Logging**: CSV export of measurements and sequences
3. **Custom Sequences**: GUI sequence editor
4. **Templates**: Save/load common configurations
5. **Remote Control**: API for external automation

## Summary

This enhanced iTest grid client successfully implements the OWIS device server pattern:
- **One DS controls multiple slots** instead of one DS per slot
- **Grid layout** provides comprehensive overview without tab switching
- **Multi-slot task management** enables coordinated operations
- **Live monitoring** shows real-time status of all slots
- **Clean, scalable architecture** that grows with slot count

The result is a professional, efficient interface that follows established patterns while providing modern functionality for power supply control and automation.