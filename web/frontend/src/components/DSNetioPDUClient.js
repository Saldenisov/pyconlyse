// DSNetioPDUClient.js - Multi-device NETIO PDU web client
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './DSNetioPDUClient.css';

const DSNetioPDUClient = ({ deviceNames = [] }) => {
  const [devices, setDevices] = useState({});
  const [selectedDevices, setSelectedDevices] = useState([]);
  const [showAllDevices, setShowAllDevices] = useState(true);
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const socketRef = useRef(null);

  useEffect(() => {
    if (deviceNames && deviceNames.length > 0) {
      setSelectedDevices(deviceNames);
      fetchAllDevicesData();
      initializeWebSocket();
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, [deviceNames]);

  const initializeWebSocket = () => {
    const token = getCookie('access_token_cookie');
    
    socketRef.current = io('/', {
      transports: ['websocket'],
      auth: { token: token }
    });

    socketRef.current.on('connect', () => {
      setConnected(true);
    });

    socketRef.current.on('disconnect', () => {
      setConnected(false);
      setMonitoring(false);
    });

    socketRef.current.on('device_update', (data) => {
      if (data.device && devices[data.device]) {
        setDevices(prev => ({
          ...prev,
          [data.device]: {
            ...prev[data.device],
            outputs: data.outputs || prev[data.device].outputs
          }
        }));
      }
    });

    socketRef.current.on('device_error', (data) => {
      if (data.device && devices[data.device]) {
        setError(`${data.device}: ${data.error}`);
      }
    });
  };

  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  };

  const fetchAllDevicesData = async () => {
    try {
      setLoading(true);
      const devicesData = {};
      
      for (const deviceName of deviceNames) {
        try {
          const response = await fetch(`/api/device/${deviceName}/pdu/outputs`, {
            credentials: 'include'
          });
          
          if (response.ok) {
            const data = await response.json();
            devicesData[deviceName] = {
              name: deviceName,
              outputs: data.outputs || [],
              state: data.state || 'UNKNOWN'
            };
          } else {
            // Try alternative API endpoint
            const altResponse = await fetch(`/api/device/${deviceName}/attributes`, {
              credentials: 'include'
            });
            
            if (altResponse.ok) {
              const altData = await altResponse.json();
              devicesData[deviceName] = parseDeviceAttributes(deviceName, altData.attributes);
            }
          }
        } catch (err) {
          console.error(`Error fetching ${deviceName}:`, err);
          devicesData[deviceName] = {
            name: deviceName,
            outputs: [],
            error: err.message
          };
        }
      }
      
      setDevices(devicesData);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const parseDeviceAttributes = (deviceName, attributes) => {
    // Parse NETIO device attributes to extract outputs
    const outputs = [];
    const ids = attributes.ids?.value || [];
    const names = attributes.names?.value || [];
    const states = attributes.states?.value || [];
    
    for (let i = 0; i < Math.max(ids.length, 4); i++) {
      outputs.push({
        id: ids[i] || (i + 1),
        name: names[i] || `Output ${i + 1}`,
        state: states[i] || 0
      });
    }
    
    return {
      name: deviceName,
      outputs: outputs,
      state: 'ON'
    };
  };

  const toggleMonitoring = () => {
    if (!socketRef.current || !connected) return;

    if (monitoring) {
      selectedDevices.forEach(deviceName => {
        socketRef.current.emit('unsubscribe_device', { device: deviceName });
      });
      setMonitoring(false);
    } else {
      selectedDevices.forEach(deviceName => {
        socketRef.current.emit('subscribe_device', { device: deviceName });
      });
      setMonitoring(true);
    }
  };

  const setOutputState = async (deviceName, outputId, state) => {
    try {
      // Get current device state
      const device = devices[deviceName];
      if (!device) return;
      
      // Build states array for all outputs
      const states = device.outputs.map(output => 
        output.id === outputId ? (state ? 1 : 0) : output.state
      );
      
      const response = await fetch(`/api/device/${deviceName}/command/set_channels_states`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: states })
      });
      
      if (response.ok) {
        // Update local state
        setDevices(prev => ({
          ...prev,
          [deviceName]: {
            ...prev[deviceName],
            outputs: prev[deviceName].outputs.map(output =>
              output.id === outputId ? { ...output, state: state ? 1 : 0 } : output
            )
          }
        }));
        setError(null);
      } else {
        throw new Error(`Failed to set output ${outputId} for ${deviceName}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const setAllOutputs = async (deviceName, state) => {
    try {
      const device = devices[deviceName];
      if (!device) return;
      
      const states = device.outputs.map(() => state ? 1 : 0);
      
      const response = await fetch(`/api/device/${deviceName}/command/set_channels_states`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: states })
      });
      
      if (response.ok) {
        setDevices(prev => ({
          ...prev,
          [deviceName]: {
            ...prev[deviceName],
            outputs: prev[deviceName].outputs.map(output => ({ ...output, state: state ? 1 : 0 }))
          }
        }));
        setError(null);
      } else {
        throw new Error(`Failed to set all outputs for ${deviceName}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleDeviceSelection = (deviceName) => {
    setSelectedDevices(prev => {
      if (prev.includes(deviceName)) {
        return prev.filter(name => name !== deviceName);
      } else {
        return [...prev, deviceName];
      }
    });
  };

  const selectAllDevices = () => {
    setSelectedDevices(deviceNames);
    setShowAllDevices(true);
  };

  const deselectAllDevices = () => {
    setSelectedDevices([]);
    setShowAllDevices(false);
  };

  const renderOutput = (deviceName, output) => {
    return (
      <div key={`${deviceName}-${output.id}`} className="output-control">
        <div className="output-header">
          <span className="output-label">
            {output.id}. {output.name}
          </span>
          <label className="output-toggle">
            <input
              type="checkbox"
              checked={output.state === 1}
              onChange={(e) => setOutputState(deviceName, output.id, e.target.checked)}
            />
            <span className="toggle-switch"></span>
            <span className={`state-label ${output.state === 1 ? 'on' : 'off'}`}>
              {output.state === 1 ? 'ON' : 'OFF'}
            </span>
          </label>
        </div>
      </div>
    );
  };

  const renderDevice = (deviceName) => {
    const device = devices[deviceName];
    if (!device) return null;

    return (
      <div key={deviceName} className="device-card">
        <div className="device-header">
          <h3>{deviceName}</h3>
          <div className="device-controls">
            <button 
              className="device-btn all-on"
              onClick={() => setAllOutputs(deviceName, true)}
              title="Turn all outputs ON"
            >
              All ON
            </button>
            <button 
              className="device-btn all-off"
              onClick={() => setAllOutputs(deviceName, false)}
              title="Turn all outputs OFF"
            >
              All OFF
            </button>
          </div>
        </div>
        
        {device.error && (
          <div className="device-error">
            Error: {device.error}
          </div>
        )}
        
        <div className="outputs-grid">
          {device.outputs.map(output => renderOutput(deviceName, output))}
        </div>
      </div>
    );
  };

  if (loading) {
    return <div className="netio-client loading">Loading NETIO PDU devices...</div>;
  }

  const visibleDevices = showAllDevices 
    ? deviceNames 
    : selectedDevices.filter(name => deviceNames.includes(name));

  return (
    <div className="netio-client">
      <div className="client-header">
        <h2>NETIO PDU Control</h2>
        <div className="header-controls">
          <div className="connection-status">
            <span className={`status ${connected ? 'connected' : 'disconnected'}`}>
              {connected ? '🟢 Connected' : '🔴 Disconnected'}
            </span>
            <button 
              className={`monitor-btn ${monitoring ? 'active' : ''}`}
              onClick={toggleMonitoring}
              disabled={!connected}
            >
              {monitoring ? 'Stop Monitoring' : 'Start Monitoring'}
            </button>
          </div>
          
          <div className="device-count">
            <span>{visibleDevices.length} / {deviceNames.length} devices shown</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
          <button onClick={fetchAllDevicesData}>Retry</button>
        </div>
      )}

      <div className="device-selector">
        <h3>Device Selection:</h3>
        <div className="selector-controls">
          <button onClick={selectAllDevices} className="selector-btn">
            Show All
          </button>
          <button onClick={deselectAllDevices} className="selector-btn">
            Hide All
          </button>
        </div>
        <div className="device-checkboxes">
          {deviceNames.map(deviceName => (
            <label key={deviceName} className="device-checkbox">
              <input
                type="checkbox"
                checked={selectedDevices.includes(deviceName)}
                onChange={() => toggleDeviceSelection(deviceName)}
              />
              {deviceName}
            </label>
          ))}
        </div>
      </div>

      <div className="devices-grid">
        {visibleDevices.map(deviceName => renderDevice(deviceName))}
      </div>
      
      <div className="info-section">
        <small>
          • Each NETIO device controls 4 outputs (PDU outlets)<br/>
          • Toggle individual outputs with ON/OFF switches<br/>
          • Use "All ON" / "All OFF" buttons to control all outputs of a device<br/>
          • Select/deselect devices to customize view<br/>
          • Enable monitoring for real-time updates
        </small>
      </div>
    </div>
  );
};

export default DSNetioPDUClient;
