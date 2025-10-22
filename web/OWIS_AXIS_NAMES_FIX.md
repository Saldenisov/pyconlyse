# Fix: OWIS PS90 Axis Names Not Displaying Correctly

## Problem
The axes names in the OWIS PS90 web interface were showing neither friendly names nor correct IDs (1, 2, 3, 4). Instead, they were showing generic fallback names like "Axis 1", "Axis 2", etc.

## Root Cause
The Tango device server attributes `states`, `positions`, and `friendly_names` return **Python dictionary strings** (not actual objects). For example:
```python
"{'1': <DevState.ON: 6>, '2': <DevState.OFF: 0>}"
```

The JavaScript frontend code was treating these string values as if they were already JavaScript objects, attempting to access them with `friendlyNames[axisId]`, which failed because:
1. The value was a string, not an object
2. No parsing was done to convert the Python dict string to JavaScript object

## Solution

### 1. Frontend Fix (test_owis_ps90.html)
Added a `parseStringDict()` helper function that:
- Takes the Python dict string from Tango attributes
- Handles DevState enum values like `<DevState.ON: 6>` → extracts the numeric value `6`
- Converts Python string format to valid JSON (single quotes → double quotes)
- Handles Python boolean/None values (`True`/`False`/`None` → `true`/`false`/`null`)
- Parses the result into a proper JavaScript object

```javascript
const parseStringDict = (strDict) => {
    if (!strDict || typeof strDict !== 'string') return {};
    try {
        let jsonStr = strDict
            .replace(/<DevState\.[A-Z]+: (\d+)>/g, '$1')  // Handle DevState enums
            .replace(/'/g, '"')  // Single quotes to double quotes
            .replace(/\bTrue\b/g, 'true')  // Python True to JS true
            .replace(/\bFalse\b/g, 'false')  // Python False to JS false
            .replace(/\bNone\b/g, 'null');  // Python None to JS null
        return JSON.parse(jsonStr);
    } catch (e) {
        console.warn('Failed to parse string dict:', strDict, e);
        return {};
    }
};
```

### 2. Backend Fix (websocket_handler.py)
Added support for OWIS multi-axis devices in the WebSocket monitoring:
- Detects OWIS devices by checking for 'owis' or 'ps90' in the device name
- Reads the `states` and `positions` attributes (which are Python dict strings)
- Parses them using regex to handle DevState enums
- Converts to proper Python dicts with integer keys
- Sends as JSON objects to the frontend via WebSocket

This ensures that real-time updates via WebSocket also work correctly with proper axis data.

## Files Modified
1. `C:\dev\pyconlyse\web\test_owis_ps90.html` - Added parseStringDict() function in parseDeviceData()
2. `C:\dev\pyconlyse\web\backend\websocket_handler.py` - Added OWIS device support with string dict parsing

## Testing
To verify the fix:
1. Load an OWIS PS90 device (e.g., `manip/general/DS_OWIS_PS90`)
2. Check that axis names show the configured friendly_names from the device properties
3. Verify that axis IDs are correctly shown as 1, 2, 3, 4
4. Confirm that position and state updates work correctly via WebSocket

## Background
The issue stems from how the Tango device server base class `DS_MOTORIZED_MULTI_AXES` in `DeviceServers/base/motor.py` returns attributes:

```python
@attribute(label="Axes friendly_names", dtype=str, ...)
def friendly_names(self):
    names = {}
    for axis_id, axis_param in self._delay_lines_parameters.items():
        names[axis_id] = axis_param["friendly_name"]
    return str(names)  # Returns string representation!
```

This design choice (returning `str(dict)` instead of structured data) requires parsing on the client side.
