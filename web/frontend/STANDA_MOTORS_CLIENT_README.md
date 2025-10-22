# Standa Motors Web Client

A comprehensive web-based control interface for Standa motorized linear stages, built with React and integrated with the PYCONLYSE backend.

## Overview

The Standa Motors Client provides a modern, intuitive interface for controlling multiple motorized stages through a web browser. It includes configuration presets matching the existing PyQt5 client layouts, real-time position monitoring via WebSocket, and comprehensive motor control features.

## Features

### 🎛️ Configuration Management
- **Predefined Layouts**: Six preconfigured motor layouts from the PyQt5 client:
  - `ELYSE`: 8 motors (delay lines and mirror mounts)
  - `V0`: 16 motors (complete V0 setup)
  - `V0_short`: 2 motors (minimal test setup)
  - `alignment`: 16 motors (alignment configuration)
  - `OPA`: 2 motors (OPA positioning system)
  - `test`: 2 motors (test configuration)
- **Dynamic Configuration Switching**: Change configurations on-the-fly without page reload
- **Adaptive Grid Layout**: Automatically adjusts grid columns based on configuration width

### 🔄 Real-time Control
- **WebSocket Integration**: Live position and state updates
- **Absolute Positioning**: Direct input for precise positioning
- **Relative Movement**: Step-based movement with ◄◄ / ►► buttons
- **Adjustable Step Sizes**: 0.1, 0.5, 1, 2, 5, 10, 20, 50, 100 units
- **Preset Positions**: Quick access to predefined positions from device properties
- **Position Clamping**: Automatic limiting within configured min/max values

### 🎨 User Interface
- **Visual State Indicators**: Color-coded motor states (ON/OFF/MOVING/FAULT)
- **Position Display**: Large, readable position values with units
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Error Handling**: Clear error messages with retry functionality
- **Connection Status**: Real-time connection indicator

### 🛡️ Safety Features
- **Limit Enforcement**: Prevents movement beyond configured limits
- **Emergency Stop**: Immediate motor halt functionality
- **Debounced Input**: Prevents accidental rapid movements
- **State Monitoring**: Visual indication of motor power state

## Files Structure

```
web/frontend/src/
├── components/
│   ├── DSStandaMotorsClient.js       # Main client component
│   └── DSStandaMotorsClient.css      # Client styling
├── css/
│   └── Example.css                   # Example page styling
└── StandaMotorsExample.js            # Demo/example page
```

## Component Usage

### Basic Usage

```jsx
import DSStandaMotorsClient from './components/DSStandaMotorsClient';

function MyPage() {
  return (
    <DSStandaMotorsClient defaultConfig="V0_short" />
  );
}
```

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `defaultConfig` | string | `"V0_short"` | Initial configuration to load |

### Available Configurations

All configurations are defined in `MOTOR_CONFIGS` constant:

```javascript
const MOTOR_CONFIGS = {
  "ELYSE": { selection: [...], width: 4 },
  "V0": { selection: [...], width: 4 },
  "V0_short": { selection: [...], width: 2 },
  "alignment": { selection: [...], width: 4 },
  "OPA": { selection: [...], width: 2 },
  "test": { selection: [...], width: 4 }
};
```

## API Endpoints

The client communicates with the backend using the following REST API endpoints:

### Read Operations
- `GET /api/device/{motor_name}/attribute/position` - Get current position
- `GET /api/device/{motor_name}/state` - Get motor state
- `GET /api/device/{motor_name}/properties` - Get configuration (limits, presets, unit)

### Control Operations
- `POST /api/device/{motor_name}/command/move_axis_abs` - Move to absolute position
  ```json
  { "args": [position] }
  ```
- `POST /api/device/{motor_name}/command/turn_on` - Enable motor power
  ```json
  { "args": [] }
  ```
- `POST /api/device/{motor_name}/command/stop_movement` - Stop motor immediately
  ```json
  { "args": [] }
  ```

### WebSocket Events

#### Client → Server
- `subscribe_device` - Subscribe to motor updates
  ```javascript
  socket.emit('subscribe_device', { device: motorName });
  ```
- `unsubscribe_device` - Unsubscribe from updates
  ```javascript
  socket.emit('unsubscribe_device', { device: motorName });
  ```

#### Server → Client
- `device_update` - Position/state update
  ```javascript
  {
    device: "manip/V0/dv04",
    position: 45.123,
    state: "ON"
  }
  ```
- `device_error` - Error notification
  ```javascript
  {
    device: "manip/V0/dv04",
    error: "Movement failed"
  }
  ```

## Configuration Mapping

The web client configurations directly map to the PyQt5 client configurations defined in `DeviceServers/motion/standa/DS_STANDA_client.py`:

| Configuration | Motors | Description |
|--------------|--------|-------------|
| ELYSE | 8 | `de1`, `F1`, `mme_x/y`, `mm1_x/y`, `mm2_x/y` |
| V0 | 16 | Complete V0 chamber setup |
| V0_short | 2 | `dv04`, `L-2_1` (quick test) |
| alignment | 16 | Full alignment motor set |
| OPA | 2 | `opa_x`, `opa_y` |
| test | 2 | `mm1_x`, `mm1_y` |

## Motor States

The client displays motors with different visual indicators based on state:

- 🟢 **ON** (Green): Motor powered and ready
- 🟡 **MOVING** (Yellow/Amber): Motor in motion
- 🔴 **FAULT** (Red): Motor in error state
- ⚫ **OFF** (Gray): Motor powered off

## Development

### Adding New Configurations

To add a new configuration, edit `DSStandaMotorsClient.js`:

```javascript
const MOTOR_CONFIGS = {
  // ... existing configs ...
  "my_new_config": {
    "selection": [
      "device/domain/motor1",
      "device/domain/motor2"
    ],
    "width": 2  // Grid columns
  }
};
```

### Customizing Step Sizes

Modify the step selector options in the render method:

```javascript
<option value={0.01}>0.01 {motor.unit}</option>
<option value={0.05}>0.05 {motor.unit}</option>
// Add more as needed
```

### Styling Customization

All styles are in `DSStandaMotorsClient.css`. Key CSS classes:

- `.standa-client` - Main container
- `.motor-card` - Individual motor card
- `.motor-card.on|moving|fault|off` - State-specific styles
- `.config-selector` - Configuration dropdown
- `.motor-controls` - Movement controls section
- `.preset-buttons` - Preset position buttons

## Integration with Existing App

### Adding to Navigation

Add to your main App routing:

```jsx
import StandaMotorsExample from './StandaMotorsExample';

<Route path="/standa-motors" element={<StandaMotorsExample />} />
```

### Adding to DeviceClients Page

Integrate into existing device clients page:

```jsx
import DSStandaMotorsClient from './components/DSStandaMotorsClient';

// In your render method
{deviceType === 'STANDA' && (
  <DSStandaMotorsClient defaultConfig="V0_short" />
)}
```

## Performance Considerations

- **Debouncing**: Position inputs are debounced (800ms) to prevent excessive API calls
- **Optimistic Updates**: UI updates immediately before server confirmation
- **Selective Monitoring**: Only subscribe to motors in active configuration
- **Cleanup**: Proper WebSocket disconnection and timer cleanup on unmount

## Troubleshooting

### Motors Not Loading
1. Check backend API is running and accessible
2. Verify motor names in configuration match Tango device names
3. Check browser console for API errors

### WebSocket Connection Issues
1. Verify WebSocket server is running
2. Check authentication cookie (`access_token_cookie`)
3. Ensure CORS settings allow WebSocket connections

### Position Updates Not Showing
1. Click "Start Monitoring" button
2. Check WebSocket connection status (should be green)
3. Verify device is publishing change events in Tango

## Future Enhancements

Potential improvements for future versions:

- [ ] Graphical position visualization
- [ ] Position history/trajectory recording
- [ ] Macro/sequence programming
- [ ] Multi-motor synchronized movement
- [ ] Position bookmarking system
- [ ] Export/import configuration files
- [ ] Joystick/gamepad support
- [ ] Position limit visualization

## License

Part of the PYCONLYSE project. See main project LICENSE file.

## Related Files

- PyQt5 Client: `DeviceServers/motion/standa/DS_STANDA_client.py`
- Widget Implementation: `DeviceServers/motion/standa/DS_STANDA_Widget.py`
- Device Server: `DeviceServers/motion/standa/DS_Standa_Motor.py`
- Backend API: `web/backend/` (if implemented)
- WebSocket Handler: `web/backend/websocket_handler.py`
