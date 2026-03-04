# OWIS PS90 Communication Error Recovery

## Problem Description

When controlling the OWIS PS90 controller from LabVIEW or during stress testing, intermittent communication errors can occur:

```
ERROR: Device Device 1 DS_OWIS_PS90 set_target_ex to -16.11 for axis 2 did NOT work communication error.
Device Device 1 DS_OWIS_PS90 reading position of axis 1 failed: communication error
Device Device 1 DS_OWIS_PS90 reading position of axis 2 failed: communication error
...
```

Once communication fails, the device server gets stuck in a failing state where:
- All position reads fail
- All movement commands fail
- The polling loop continues spamming error messages
- Manual restart of the device server is required

## Root Causes

1. **Incorrect error handling bug** - Line 1329 had wrong boolean logic (`or` instead of `and`), causing all errors to show as "Wrong code number"

2. **Wrong baudrate** - Device was configured with 9600 baud but the controller requires 115200 baud for reliable communication

3. **No reconnection logic** - When USB communication glitches occur, there was no automatic recovery mechanism

4. **Cascading failures** - Once one command fails, the polling thread continues trying to read positions, causing error spam

## Solution Implemented

### 1. Fixed Error Handling (Line 1329)
```python
# BEFORE (WRONG):
if code > 0 or (code not in errors_connections or code not in errors_functions):
    return "Wrong code number"

# AFTER (CORRECT):
if code > 0 or (code not in errors_connections and code not in errors_functions):
    return "Wrong code number"
```

Now actual error messages like "communication error" are properly displayed.

### 2. Updated Baudrate Configuration
- Changed from 9600 → **115200 baud**
- Diagnostic confirmed all 4 axes respond correctly at 115200
- Updated in Tango database

### 3. Centralized Reconnection Mechanism

Added `_attempt_reconnection()` method that:
- Disconnects from COM port
- Waits 500ms
- Reconnects at 115200 baud
- Reinitializes all 4 axes
- Resets communication error counter
- Prevents concurrent reconnection attempts

### 4. Automatic Recovery in Position Reads

`read_position_axis_local()` now:
- Retries failed reads up to 2 times with 0.1s delay
- Tracks consecutive communication errors
- **Triggers reconnection after 3 consecutive failures**
- Automatically retries after successful reconnection
- Resets error counter on successful read

### 5. Automatic Recovery in Movement Commands

`move_axis_local()` now:
- Retries `set_target_ex` up to 3 times
- Triggers reconnection on communication errors
- Waits 1 second between retry attempts
- Continues movement after successful reconnection
- Resets error counter on successful command

## Configuration Parameters

Added to Tango database:
```python
max_retries: 3      # Number of retry attempts for movement commands
retry_delay: 1.0    # Seconds to wait between retries
```

## Behavior

### Transient Communication Error (Single failure)
```
1. Command fails with "communication error"
2. Wait 0.1s
3. Retry command
4. Success → continue normally
```

### Persistent Communication Error (3+ consecutive failures)
```
1. Detect 3 consecutive communication errors
2. Log: "Detected 3 consecutive communication errors, triggering reconnection..."
3. Disconnect from COM7
4. Wait 500ms
5. Reconnect to COM7 at 115200 baud
6. Reinitialize all axes (motor_init, set_target_mode, set_param)
7. Log: "Reconnection successful"
8. Retry failed command
9. Success → continue normally
```

### Recovery from LabVIEW Control Issues

When LabVIEW sends a command that causes communication failure:
- Device server automatically reconnects within ~2 seconds
- LabVIEW can continue sending commands
- No manual intervention required
- Error messages are informative (not "Wrong code number")

## Testing

### Diagnostic Script
```bash
python C:\dev\pyconlyse\DeviceServers\motion\owis\test_owis_connection_diag.py
```
Tests all baudrates and confirms which one works.

### Stress Test
```bash
python C:\dev\pyconlyse\DeviceServers\motion\owis\test_owis_axis2_stress.py
```
Performs 200 random movements of axis 2 to verify stability.

## Files Modified

1. `DS_OWIS_PS90.py`:
   - Line 1329: Fixed error handling logic
   - Line 124-125: Added communication error tracking
   - Line 226-280: Added `_attempt_reconnection()` method
   - Line 349-398: Enhanced `read_position_axis_local()` with auto-reconnection
   - Line 428-492: Enhanced `move_axis_local()` with retry and reconnection

2. `add_ds_OWIS_PS90.py`:
   - Line 81: Changed baudrate 9600 → 115200
   - Line 89-90: Added max_retries and retry_delay parameters

3. Tango Database:
   - Updated `baudrate: 115200`
   - Added `max_retries: 3`
   - Added `retry_delay: 1.0`

## Deployment

1. Stop the device server
2. Files are already updated in the repository
3. Restart the device server
4. Device server will now automatically recover from communication errors
5. Monitor logs for "Reconnection successful" messages

## Expected Log Output (Normal Operation)

```
Device Device 1 DS_OWIS_PS90 axis 2 started moving to -127.412.
Axis 2 movement completed at position -127.412
Device Device 1 DS_OWIS_PS90 axis 2 started moving to -16.114.
Axis 2 movement completed at position -16.114
```

## Expected Log Output (With Recovery)

```
Device Device 1 DS_OWIS_PS90 axis 2 started moving to -127.412.
Axis 2 movement completed at position -127.412
Communication error on set_target_ex (attempt 1/3), reconnecting in 1.0s...
Detected 3 consecutive communication errors, triggering reconnection...
Communication lost, attempting reconnection...
Reconnection successful
Reinitializing all axes after reconnection...
Device Device 1 DS_OWIS_PS90 axis 2 started moving to -16.114.
Axis 2 movement completed at position -16.114
```

## Benefits

✓ **Automatic recovery** - No manual restart needed
✓ **Intelligent reconnection** - Only reconnects when truly needed (3+ failures)
✓ **Fast recovery** - ~2 seconds from error to operational
✓ **Prevents error spam** - Single reconnection attempt instead of infinite failures
✓ **LabVIEW compatible** - Works seamlessly with external control software
✓ **Informative logging** - Clear messages about what's happening
✓ **Non-invasive** - Doesn't affect normal operation when communication is stable
