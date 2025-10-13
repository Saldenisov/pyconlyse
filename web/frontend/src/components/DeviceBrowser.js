// DeviceBrowser.js - Device browser and selector component
import React, { useState, useEffect } from 'react';
import DeviceControl from './DeviceControl';
import ITestPSUClient from './ITestPSUClient';
import './DeviceBrowser.css';

const DeviceBrowser = () => {
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const [clientType, setClientType] = useState('generic');

  useEffect(() => {
    fetchDevices();
  }, []);

  const fetchDevices = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/devices', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setDevices(data.devices || []);
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (err) {
      console.error('Error fetching devices:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getDeviceType = (deviceName, deviceClass = '') => {
    const name = deviceName.toLowerCase();
    const cls = deviceClass.toLowerCase();
    
    if (name.includes('itest') || name.includes('psu') || cls.includes('itest')) {
      return 'itest_psu';
    } else if (name.includes('camera') || name.includes('basler') || name.includes('andor')) {
      return 'camera';
    } else if (name.includes('motor') || name.includes('standa') || name.includes('owis')) {
      return 'motor';
    } else {
      return 'generic';
    }
  };

  const getDeviceIcon = (deviceType, state) => {
    const stateColor = state === 'ON' ? '🟢' : state === 'FAULT' ? '🔴' : '🟡';
    
    switch (deviceType) {
      case 'itest_psu':
        return `⚡ ${stateColor}`;
      case 'camera':
        return `📷 ${stateColor}`;
      case 'motor':
        return `⚙️ ${stateColor}`;
      default:
        return `🔧 ${stateColor}`;
    }
  };

  const selectDevice = (device) => {
    setSelectedDevice(device);
    const deviceType = getDeviceType(device.name, device.class);
    
    // Set appropriate client type
    if (deviceType === 'itest_psu') {
      setClientType('itest_psu');
    } else {
      setClientType('generic');
    }
  };

  const filteredDevices = devices.filter(device => 
    device.name.toLowerCase().includes(filter.toLowerCase()) ||
    (device.class && device.class.toLowerCase().includes(filter.toLowerCase())) ||
    (device.server && device.server.toLowerCase().includes(filter.toLowerCase()))
  );

  const availableDevices = filteredDevices.filter(device => device.available);
  const unavailableDevices = filteredDevices.filter(device => !device.available);

  const renderClient = () => {
    if (!selectedDevice) return null;

    switch (clientType) {
      case 'itest_psu':
        return <ITestPSUClient deviceName={selectedDevice.name} />;
      default:
        return <DeviceControl deviceName={selectedDevice.name} deviceType={clientType} />;
    }
  };

  if (loading) {
    return (
      <div className="device-browser">
        <div className="loading">Loading devices...</div>
      </div>
    );
  }

  return (
    <div className="device-browser">
      <div className="browser-sidebar">
        <div className="sidebar-header">
          <h2>Device Browser</h2>
          <button onClick={fetchDevices} className="refresh-btn">🔄 Refresh</button>
        </div>

        <div className="filter-section">
          <input
            type="text"
            placeholder="Filter devices..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="filter-input"
          />
        </div>

        {error && (
          <div className="error-section">
            <div className="error">Error: {error}</div>
            <button onClick={fetchDevices}>Retry</button>
          </div>
        )}

        <div className="devices-section">
          <div className="section-header">
            <h3>Available Devices ({availableDevices.length})</h3>
          </div>
          
          <div className="device-list">
            {availableDevices.map(device => {
              const deviceType = getDeviceType(device.name, device.class);
              const isSelected = selectedDevice && selectedDevice.name === device.name;
              
              return (
                <div
                  key={device.name}
                  className={`device-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => selectDevice(device)}
                >
                  <div className="device-icon">
                    {getDeviceIcon(deviceType, device.state)}
                  </div>
                  <div className="device-info">
                    <div className="device-name">{device.name}</div>
                    <div className="device-details">
                      <span className="device-class">{device.class}</span>
                      <span className="device-state">{device.state}</span>
                    </div>
                    <div className="device-server">{device.server}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {unavailableDevices.length > 0 && (
            <>
              <div className="section-header">
                <h3>Unavailable Devices ({unavailableDevices.length})</h3>
              </div>
              
              <div className="device-list unavailable">
                {unavailableDevices.map(device => (
                  <div key={device.name} className="device-item unavailable">
                    <div className="device-icon">🔴</div>
                    <div className="device-info">
                      <div className="device-name">{device.name}</div>
                      <div className="device-details">Unavailable</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {selectedDevice && (
          <div className="client-type-section">
            <h4>Client Type</h4>
            <select 
              value={clientType} 
              onChange={(e) => setClientType(e.target.value)}
              className="client-type-select"
            >
              <option value="generic">Generic Control</option>
              <option value="itest_psu">iTest PSU</option>
            </select>
          </div>
        )}
      </div>

      <div className="client-area">
        {selectedDevice ? (
          <>
            <div className="client-header">
              <h2>Device Client</h2>
              <div className="selected-device">
                {getDeviceIcon(getDeviceType(selectedDevice.name, selectedDevice.class), selectedDevice.state)}
                <span>{selectedDevice.name}</span>
              </div>
            </div>
            {renderClient()}
          </>
        ) : (
          <div className="no-selection">
            <div className="placeholder">
              <h3>Select a device to control</h3>
              <p>Choose a device from the browser on the left to start controlling it through the web interface.</p>
              <div className="features">
                <h4>Available Features:</h4>
                <ul>
                  <li>📊 Real-time monitoring</li>
                  <li>⚡ Direct device control</li>
                  <li>📝 Attribute reading/writing</li>
                  <li>🎛️ Command execution</li>
                  <li>🔌 WebSocket live updates</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DeviceBrowser;