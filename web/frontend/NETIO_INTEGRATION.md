# NETIO PDU Client Integration

## What Was Changed

The NETIO web client has been successfully integrated into the Equipment page.

### Files Modified

1. **`src/Equipment.js`**
   - Added import for `DSNetioPDUClient`
   - Added state management for NETIO client display
   - Modified PDU modal to include "NETIO Web Client" button
   - Added NETIO client rendering in the widget area
   - Kept existing "NETIO Direct Access" link (http://10.20.30.202)

2. **`src/Equipment.css`**
   - Updated `.modal-link` to support both `<a>` tags and `<button>` elements
   - Added proper styling for button elements in modal

### Files Created

1. **`src/components/DSNetioPDUClient.js`** - Main NETIO client component
2. **`src/components/DSNetioPDUClient.css`** - Styling for NETIO client
3. **`src/components/NetioExample.js`** - Usage example (optional)
4. **`src/components/NETIO_CLIENT_README.md`** - Comprehensive documentation

## How to Use

### Step 1: Navigate to Equipment Page
1. Open your web application
2. Click on the "Equipment" navigation link

### Step 2: Access NETIO Client
1. Click on the "PDU" equipment card (left side of the page)
2. A modal will appear with two options:
   - **NETIO Web Client** - Opens the new React-based client (recommended)
   - **NETIO Direct Access** - Opens the hardware web interface in new tab

### Step 3: Use NETIO Web Client
1. Click "NETIO Web Client" button
2. The client will load in the right panel
3. You'll see:
   - Connection status indicator
   - Device selection checkboxes (show/hide specific devices)
   - 5 device cards (one for each NETIO PDU)
   - Each device has 4 output controls
   - Toggle switches for individual outputs
   - "All ON" and "All OFF" buttons per device

### Step 4: Control Outputs
1. **Individual Control**: Click toggle switches to turn outlets ON/OFF
2. **Bulk Control**: Use "All ON" or "All OFF" buttons
3. **Device Selection**: Check/uncheck devices to customize view
4. **Monitoring**: Click "Start Monitoring" for real-time updates

### Step 5: Return to Equipment
- Click the "← Back to Equipment" button at the top of the widget area

## Device Names Configuration

The client is currently configured with these device names:
```javascript
[
  'elyse/pdu/netio1',
  'elyse/pdu/netio2',
  'elyse/pdu/netio3',
  'elyse/pdu/netio4',
  'elyse/pdu/netio5'
]
```

### To Change Device Names

Edit `src/Equipment.js` around line 139-145:

```javascript
<DSNetioPDUClient deviceNames={[
  'your/device/name1',    // Change these to your actual
  'your/device/name2',    // Tango device server names
  'your/device/name3',
  'your/device/name4',
  'your/device/name5'
]} />
```

## Backend Requirements

Make sure your backend supports:

1. **Device Attributes Endpoint**:
   ```
   GET /api/device/{device_name}/attributes
   ```
   Should return device attributes including `ids`, `names`, and `states`

2. **Command Execution Endpoint**:
   ```
   POST /api/device/{device_name}/command/set_channels_states
   Body: { "args": [0, 1, 0, 1] }
   ```
   Should execute the command on the Tango device

3. **WebSocket Server** (optional but recommended):
   - For real-time monitoring
   - Subscribe/unsubscribe events
   - Device update events

## Testing

### Quick Test Checklist

- [ ] Click PDU on Equipment page
- [ ] Modal opens with two options
- [ ] Click "NETIO Web Client"
- [ ] Client loads in right panel
- [ ] See 5 device cards (or configured number)
- [ ] Each device shows 4 outputs
- [ ] Toggle switches work
- [ ] "All ON" button works
- [ ] "All OFF" button works
- [ ] Device selection checkboxes work
- [ ] "Back to Equipment" button works

### If Something Doesn't Work

1. **Client doesn't load**:
   - Check browser console for errors
   - Verify device names match Tango database
   - Check backend API is running

2. **Outputs don't toggle**:
   - Check device server state (should be ON)
   - Verify backend API endpoints exist
   - Check network connectivity

3. **Styling issues**:
   - Clear browser cache
   - Check that DSNetioPDUClient.css is loaded
   - Inspect element to verify CSS classes

## Architecture

```
User clicks PDU
      ↓
Modal appears
      ↓
User clicks "NETIO Web Client"
      ↓
DSNetioPDUClient component loads
      ↓
Fetches device data from backend
      ↓
Displays 5 devices × 4 outputs
      ↓
User toggles outputs
      ↓
Sends command to backend
      ↓
Backend updates Tango device
      ↓
Physical outlet turns ON/OFF
```

## Features

✅ **Multi-device support** - Control 5 NETIO PDUs  
✅ **Device selection** - Show/hide specific devices  
✅ **Individual control** - Toggle each outlet  
✅ **Bulk control** - All ON/OFF per device  
✅ **Real-time monitoring** - WebSocket updates  
✅ **Responsive design** - Works on all screen sizes  
✅ **Error handling** - Clear error messages  
✅ **Easy navigation** - Back button to equipment page  

## Comparison: Web Client vs Direct Access

| Feature | NETIO Web Client | NETIO Direct Access |
|---------|------------------|---------------------|
| Access | Integrated in app | External webpage |
| Multiple Devices | ✅ All 5 in one view | ❌ One at a time |
| Device Selection | ✅ Show/hide devices | ❌ N/A |
| Real-time Updates | ✅ WebSocket | ⚠️ Manual refresh |
| Authentication | ✅ App login | ⚠️ Separate login |
| UI Consistency | ✅ Matches app style | ❌ Different UI |
| Mobile Friendly | ✅ Responsive | ⚠️ Varies by device |

## Next Steps

1. **Test the integration** with your actual device names
2. **Update device names** in Equipment.js if needed
3. **Verify backend API** endpoints are working
4. **Check WebSocket** connection for real-time monitoring
5. **Train users** on new interface

## Support

For issues or questions:
- Check `src/components/NETIO_CLIENT_README.md` for detailed documentation
- Verify device server configuration
- Check backend API logs
- Inspect browser console for errors

## Future Enhancements

Possible improvements:
- [ ] Save/load device configurations
- [ ] Schedule power on/off times
- [ ] Power consumption monitoring (if supported)
- [ ] Group outputs across devices
- [ ] Command history/audit log
- [ ] Export states to CSV
