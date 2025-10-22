# NETIO PDU Web Client

A React-based web client for controlling multiple NETIO PDU (Power Distribution Unit) devices. This client is designed to manage 5 NETIO DS devices, each controlling 4 outputs in an ON/OFF manner.

## Features

### Multi-Device Support
- **5 NETIO Devices**: Control up to 5 separate NETIO PDU devices simultaneously
- **4 Outputs per Device**: Each device manages 4 power outlets
- **20 Total Outputs**: Control all 20 outputs from a single interface

### Device Selection
- **Show All**: Display all 5 NETIO devices at once
- **Selective View**: Choose which devices to display using checkboxes
- **Dynamic Layout**: Responsive grid layout adapts to selected devices

### Control Features
- **Individual Output Control**: Toggle each outlet ON/OFF independently
- **Bulk Control**: "All ON" and "All OFF" buttons for each device
- **Visual Feedback**: Color-coded toggle switches (green=ON, red=OFF)
- **Real-time Updates**: WebSocket-based monitoring for live state changes

### Interface
- **Modern Design**: Clean, responsive UI similar to ITest PSU client
- **Connection Status**: Visual indicator for WebSocket connection
- **Error Handling**: Clear error messages with retry functionality
- **Device Counter**: Shows number of devices currently displayed

## Components

### Main Component: `DSNetioPDUClient.js`
The primary React component that handles:
- Device state management
- WebSocket communication
- API calls to backend
- UI rendering

### Styling: `DSNetioPDUClient.css`
Comprehensive CSS styling with:
- Responsive grid layouts
- Toggle switch animations
- Mobile-friendly design
- Color-coded states

### Example: `NetioExample.js`
Demonstrates how to integrate the client with your device names.

## Usage

### Basic Setup

```javascript
import DSNetioPDUClient from './components/DSNetioPDUClient';

function App() {
  const deviceNames = [
    'elyse/pdu/netio1',
    'elyse/pdu/netio2',
    'elyse/pdu/netio3',
    'elyse/pdu/netio4',
    'elyse/pdu/netio5'
  ];

  return <DSNetioPDUClient deviceNames={deviceNames} />;
}
```

### Device Names
Replace the example device names with your actual Tango device server names:
- Format: `domain/family/member` (e.g., `elyse/pdu/netio1`)
- Must be registered in Tango database
- Should be DS_Netio_pdu device servers

## API Endpoints

The client communicates with the backend using these endpoints:

### Get Device Attributes
```
GET /api/device/{device_name}/attributes
```
Retrieves device information including:
- `ids`: Output IDs
- `names`: Output names
- `states`: Current states (0=OFF, 1=ON)

### Set Output States
```
POST /api/device/{device_name}/command/set_channels_states
Body: { "args": [state1, state2, state3, state4] }
```
Sets all output states at once. Each state is 0 (OFF) or 1 (ON).

### Alternative PDU Endpoint (if available)
```
GET /api/device/{device_name}/pdu/outputs
```
Direct PDU-specific endpoint (fallback to attributes endpoint).

## WebSocket Events

### Subscribe to Device
```javascript
socket.emit('subscribe_device', { device: deviceName });
```

### Unsubscribe from Device
```javascript
socket.emit('unsubscribe_device', { device: deviceName });
```

### Receive Updates
```javascript
socket.on('device_update', (data) => {
  // data.device: device name
  // data.outputs: array of output states
});
```

## Device Selection Options

### Show All Devices
Displays all 5 devices in a grid layout.

### Custom Selection
Check/uncheck individual devices to customize the view. Useful when:
- Working with specific equipment
- Reducing screen clutter
- Focusing on particular systems

## Backend Requirements

The client requires backend support for:
1. **Tango Device Servers**: DS_Netio_pdu instances must be running
2. **Flask API**: Backend API endpoints (device_api.py)
3. **WebSocket Server**: For real-time monitoring (optional but recommended)

## Architecture

```
┌─────────────────────────────────────┐
│   DSNetioPDUClient Component        │
│  (React Frontend)                   │
└──────────┬──────────────────────────┘
           │
           ├─── HTTP REST API
           │    (Fetch device data, send commands)
           │
           └─── WebSocket
                (Real-time monitoring)
                
┌─────────────────────────────────────┐
│   Flask Backend (device_api.py)     │
└──────────┬──────────────────────────┘
           │
           ├─── Tango API
           │
┌──────────▼──────────────────────────┐
│   Tango Device Servers              │
│   (DS_Netio_pdu instances)          │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│   NETIO PDU Hardware                │
│   (5 devices × 4 outputs)           │
└─────────────────────────────────────┘
```

## Comparison with ITest Client

| Feature | ITest PSU | NETIO PDU |
|---------|-----------|-----------|
| Purpose | Current control | Power switching |
| Output Type | Analog (current) | Digital (ON/OFF) |
| Controls | Setpoint adjustment | Toggle switches |
| Devices | Single/multiple slots | Multiple devices |
| Monitoring | Current/voltage | State only |

## Customization

### Change Number of Devices
Modify the `deviceNames` array to add/remove devices:
```javascript
const deviceNames = [
  'device1',
  'device2',
  // Add or remove as needed
];
```

### Change Outputs per Device
If your NETIO devices have different output counts, update `parseDeviceAttributes`:
```javascript
for (let i = 0; i < Math.max(ids.length, 8); i++) {  // Change 4 to 8
  // ...
}
```

### Styling
Modify `DSNetioPDUClient.css` to customize:
- Colors
- Layout
- Spacing
- Animations

## Troubleshooting

### Devices Not Loading
- Check device names match Tango database
- Verify backend API is running
- Check browser console for errors

### Cannot Toggle Outputs
- Ensure user has permissions
- Check device server state (should be ON)
- Verify network connectivity to PDU hardware

### WebSocket Not Connecting
- Check WebSocket server is running
- Verify authentication cookie is valid
- Check browser security settings

## Browser Support

- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Mobile browsers: ✅ Responsive design

## Performance

- **Lazy Loading**: Only loads selected devices
- **Optimized Rendering**: React state management
- **Efficient Updates**: WebSocket for minimal polling
- **Low Bandwidth**: Simple ON/OFF states

## Security

- Cookie-based authentication
- HTTPS recommended for production
- No sensitive data in localStorage
- CSRF protection via credentials

## Future Enhancements

Possible improvements:
- [ ] Export device states to file
- [ ] Scheduling/automation
- [ ] Power monitoring (if supported by hardware)
- [ ] Grouping outputs across devices
- [ ] Command history/logging
- [ ] Mobile app wrapper

## License

Part of the pyconlyse project.

## Support

For issues or questions, refer to the main pyconlyse documentation or device server documentation.
