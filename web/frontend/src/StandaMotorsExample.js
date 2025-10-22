// StandaMotorsExample.js - Example page for Standa Motors Client
import React, { useState } from 'react';
import DSStandaMotorsClient from './components/DSStandaMotorsClient';
import './css/Example.css';

const StandaMotorsExample = () => {
  const [selectedConfig, setSelectedConfig] = useState('V0_short');

  const configDescriptions = {
    'ELYSE': 'ELYSE setup with 8 motors (delay lines and mirror mounts)',
    'V0': 'Complete V0 setup with 16 motors (mirror mounts, delays, shutters, etc.)',
    'V0_short': 'Minimal V0 setup for testing (2 motors)',
    'alignment': 'Alignment configuration with 16 selected motors',
    'OPA': 'OPA positioning system (X/Y axes)',
    'test': 'Test configuration with 2 motors'
  };

  return (
    <div className="example-page">
      <div className="page-header">
        <h1>Standa Motorized Stages Control</h1>
        <p className="subtitle">
          Web-based control interface for Standa motorized linear stages
        </p>
      </div>

      <div className="info-panel">
        <h2>Configuration Options</h2>
        <div className="config-list">
          {Object.entries(configDescriptions).map(([config, description]) => (
            <div 
              key={config} 
              className={`config-item ${selectedConfig === config ? 'selected' : ''}`}
              onClick={() => setSelectedConfig(config)}
            >
              <strong>{config}</strong>: {description}
            </div>
          ))}
        </div>
      </div>

      <div className="features-panel">
        <h2>Features</h2>
        <ul>
          <li><strong>Multiple Configurations:</strong> Switch between predefined motor layouts</li>
          <li><strong>Real-time Monitoring:</strong> Live position updates via WebSocket</li>
          <li><strong>Absolute & Relative Movement:</strong> Direct positioning or step-based control</li>
          <li><strong>Preset Positions:</strong> Quick access to frequently-used positions</li>
          <li><strong>Adjustable Step Size:</strong> Fine or coarse movement control (0.1 to 100 units)</li>
          <li><strong>Safety Limits:</strong> Position clamping within configured limits</li>
          <li><strong>State Indication:</strong> Visual feedback for motor state (ON/OFF/MOVING/FAULT)</li>
          <li><strong>Emergency Stop:</strong> Halt motor movement instantly</li>
        </ul>
      </div>

      <div className="client-container">
        <DSStandaMotorsClient defaultConfig={selectedConfig} key={selectedConfig} />
      </div>

      <div className="usage-panel">
        <h2>How to Use</h2>
        <ol>
          <li><strong>Select Configuration:</strong> Choose from dropdown at top (ELYSE, V0, alignment, etc.)</li>
          <li><strong>Monitor Connection:</strong> Check the connection status indicator (green = connected)</li>
          <li><strong>Enable Monitoring:</strong> Click "Start Monitoring" for real-time position updates</li>
          <li><strong>Move Motors:</strong>
            <ul>
              <li>Use <strong>◄◄</strong> and <strong>►►</strong> buttons for relative movement</li>
              <li>Type directly in position input for absolute positioning</li>
              <li>Click preset position buttons for quick positioning</li>
            </ul>
          </li>
          <li><strong>Adjust Step Size:</strong> Change step size for relative movements</li>
          <li><strong>Control Power:</strong> Use ON/STOP buttons to enable or halt motors</li>
        </ol>
      </div>

      <div className="api-info-panel">
        <h2>API Integration</h2>
        <p>This client uses the following REST API endpoints:</p>
        <ul>
          <li><code>GET /api/device/&#123;motor_name&#125;/attribute/position</code> - Read position</li>
          <li><code>GET /api/device/&#123;motor_name&#125;/state</code> - Read motor state</li>
          <li><code>GET /api/device/&#123;motor_name&#125;/properties</code> - Read configuration</li>
          <li><code>POST /api/device/&#123;motor_name&#125;/command/move_axis_abs</code> - Move to position</li>
          <li><code>POST /api/device/&#123;motor_name&#125;/command/turn_on</code> - Enable motor</li>
          <li><code>POST /api/device/&#123;motor_name&#125;/command/stop_movement</code> - Stop motor</li>
        </ul>
        <p>WebSocket events for real-time updates:</p>
        <ul>
          <li><code>subscribe_device</code> - Subscribe to motor updates</li>
          <li><code>unsubscribe_device</code> - Unsubscribe from updates</li>
          <li><code>device_update</code> - Receive position/state changes</li>
        </ul>
      </div>
    </div>
  );
};

export default StandaMotorsExample;
