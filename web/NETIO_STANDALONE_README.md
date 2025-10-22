# NETIO PDU Standalone Web Client

## Overview

A standalone HTML page for controlling NETIO PDU devices, similar to the ITest client implementation.

## Files Created

1. **`test_netio_pdu.html`** - Standalone NETIO web client page (in `/web` directory)
2. **`frontend/src/components/DSNetioPDUClient.js`** - React component (not used in standalone)
3. **`frontend/src/components/DSNetioPDUClient.css`** - CSS styling (not used in standalone)

## How It Works

### User Flow

1. Navigate to Equipment page (http://10.20.30.202:5000/equipment)
2. Click "PDU" card
3. Modal appears with two options:
   - **NETIO Web Client** → Opens `/test_netio_pdu.html` in new tab
   - **NETIO Direct Access** → Opens hardware interface (http://10.20.30.202)

### Standalone Page Features

The `test_netio_pdu.html` page provides:

#### Loading Options
- **Load Single Device**: Enter one device name
- **Load All 5 NETIO Devices**: Quick load all configured devices
- **Load Custom List**: Enter comma-separated device names

#### Control Features
- View all loaded devices in grid layout
- 4 outputs per device with toggle switches
- "All ON" and "All OFF" buttons per device
- Real-time WebSocket updates
- Visual state indicators (red=OFF, green=ON)

## Configuration

### Default Device Names

Edit line 327-333 in `test_netio_pdu.html`:

```javascript
const DEFAULT_DEVICES = [
    'elyse/pdu/netio1',  // Change to your device names
    'elyse/pdu/netio2',
    'elyse/pdu/netio3',
    'elyse/pdu/netio4',
    'elyse/pdu/netio5'
];
```

## URL Access

### Standalone Page
```
http://10.20.30.202:5000/test_netio_pdu.html
```

### Via Equipment Page
```
http://10.20.30.202:5000/equipment → Click PDU → Click "NETIO Web Client"
```

## API Endpoints Used

### Get Device Attributes
```
GET /api/device/{device_name}/attributes
```
Returns: `ids`, `names`, `states` arrays

### Set Output States
```
POST /api/device/{device_name}/command/set_channels_states
Body: { "args": [0, 1, 0, 1] }
```
Sets all 4 outputs (0=OFF, 1=ON)

## Comparison: ITest vs NETIO

| Feature | ITest PSU | NETIO PDU |
|---------|-----------|-----------|
| URL | `/test_ds_itest_psu.html` | `/test_netio_pdu.html` |
| Control Type | Analog current | Digital ON/OFF |
| Inputs | Text + nudge buttons | Toggle switches |
| Multi-Device | Single device | Multiple devices |
| Loading | Enter device name | Single/All/Custom |
| WebSocket | Auto-subscribe | Auto-subscribe |

## Testing

### Quick Test
1. Open http://10.20.30.202:5000/test_netio_pdu.html
2. Click "Load All 5 NETIO Devices"
3. Verify 5 device cards appear
4. Toggle an output
5. Verify hardware outlet responds

### Single Device Test
1. Enter device name: `elyse/pdu/netio1`
2. Click "Load Single Device"
3. Verify 4 outputs appear
4. Test toggle switches

## Troubleshooting

### Page doesn't load
- Verify `test_netio_pdu.html` is in `/web` directory
- Check backend server is running
- Try accessing directly: http://10.20.30.202:5000/test_netio_pdu.html

### Devices don't load
- Check device names match Tango database
- Verify backend API is accessible
- Check browser console for errors
- Ensure devices are registered and running

### Outputs don't toggle
- Verify device server state is ON
- Check device has `set_channels_states` command
- Ensure proper authentication
- Check network connectivity to hardware

### WebSocket not connecting
- Check Socket.IO is available (CDN link)
- Verify backend WebSocket server is running
- Check browser console for connection errors

## Development

### Testing Locally
```bash
# Start backend server
cd C:\dev\pyconlyse\web
python app.py

# Access in browser
http://localhost:5000/test_netio_pdu.html
```

### Modifying Device Names
Edit the `DEFAULT_DEVICES` array at the top of the script section.

### Styling Changes
All CSS is embedded in the `<style>` tag. Modify as needed.

### Adding Features
The JavaScript is in the `<script>` tag. Common additions:
- Add more quick-load presets
- Save/load device configurations
- Add scheduling features
- Export state logs

## File Locations

```
C:\dev\pyconlyse\web\
├── test_netio_pdu.html           ← Standalone NETIO client
├── test_ds_itest_psu.html        ← ITest client (reference)
├── backend\
│   └── device_api.py             ← API endpoints
└── frontend\
    ├── build\                     ← Built React app
    └── src\
        ├── Equipment.js           ← Updated to link to NETIO page
        └── components\
            ├── DSNetioPDUClient.js    ← React component (unused)
            └── DSNetioPDUClient.css   ← CSS (unused)
```

## Next Steps

1. **Test the page**: Open `/test_netio_pdu.html` and verify functionality
2. **Update device names**: Edit `DEFAULT_DEVICES` if needed
3. **Restart server**: Ensure backend serves the new HTML file
4. **Test from Equipment page**: Verify modal link works

## Support

- Check browser console for JavaScript errors
- Check backend logs for API errors
- Verify Tango device servers are running
- Test API endpoints directly with curl/Postman

## Future Enhancements

- [ ] Save favorite device configurations
- [ ] Add device groups/presets
- [ ] Schedule on/off times
- [ ] Power consumption tracking (if supported)
- [ ] Export state history to CSV
- [ ] Mobile-optimized view
