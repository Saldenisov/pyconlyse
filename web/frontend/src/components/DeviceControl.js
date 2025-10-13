// DeviceControl.js - Generic device control component
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './DeviceControl.css';

const DeviceControl = ({ deviceName, deviceType = 'generic' }) => {
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [attributes, setAttributes] = useState({});
  const [commands, setCommands] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [realTimeData, setRealTimeData] = useState({});
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  
  const socketRef = useRef(null);

  useEffect(() => {
    if (deviceName) {
      fetchDeviceInfo();
      initializeWebSocket();
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, [deviceName]);

  const initializeWebSocket = () => {
    const token = getCookie('access_token_cookie');
    
    socketRef.current = io('/', {
      transports: ['websocket'],
      auth: {
        token: token
      }
    });

    socketRef.current.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);
    });

    socketRef.current.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setConnected(false);
      setMonitoring(false);
    });

    socketRef.current.on('device_update', (data) => {
      if (data.device === deviceName) {
        setRealTimeData(data);
      }
    });

    socketRef.current.on('device_error', (data) => {
      if (data.device === deviceName) {
        console.error('Device error:', data.error);
        setError(data.error);
      }
    });

    socketRef.current.on('command_result', (data) => {
      if (data.device === deviceName) {
        console.log('Command result:', data);
        // Refresh device info after command execution
        fetchDeviceInfo();
      }
    });

    socketRef.current.on('error', (data) => {
      console.error('WebSocket error:', data.message);
      setError(data.message);
    });
  };

  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  };

  const fetchDeviceInfo = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/device/${deviceName}/info`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setDeviceInfo(data.device_info);
        setAttributes(data.device_info.attributes || {});
        setCommands(data.device_info.commands || {});
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (err) {
      console.error('Error fetching device info:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleMonitoring = () => {
    if (!socketRef.current || !connected) return;

    if (monitoring) {
      socketRef.current.emit('unsubscribe_device', { device: deviceName });
      setMonitoring(false);
    } else {
      socketRef.current.emit('subscribe_device', { device: deviceName });
      setMonitoring(true);
    }
  };

  const readAttribute = async (attributeName) => {
    try {
      const response = await fetch(`/api/device/${deviceName}/attribute/${attributeName}`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setAttributes(prev => ({
          ...prev,
          [attributeName]: {
            ...prev[attributeName],
            value: data.value,
            quality: data.quality,
            timestamp: data.timestamp
          }
        }));
      } else {
        throw new Error(`Failed to read ${attributeName}`);
      }
    } catch (err) {
      console.error('Error reading attribute:', err);
      setError(err.message);
    }
  };

  const writeAttribute = async (attributeName, value) => {
    try {
      const response = await fetch(`/api/device/${deviceName}/attribute/${attributeName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ value })
      });
      
      if (response.ok) {
        const data = await response.json();
        setAttributes(prev => ({
          ...prev,
          [attributeName]: {
            ...prev[attributeName],
            value: data.value,
            quality: data.quality,
            timestamp: data.timestamp
          }
        }));
      } else {
        throw new Error(`Failed to write ${attributeName}`);
      }
    } catch (err) {
      console.error('Error writing attribute:', err);
      setError(err.message);
    }
  };

  const executeCommand = async (commandName, args = null) => {
    try {
      const response = await fetch(`/api/device/${deviceName}/command/${commandName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ args })
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`Command ${commandName} result:`, data.result);
        // Refresh device info after command execution
        fetchDeviceInfo();
        return data.result;
      } else {
        throw new Error(`Failed to execute ${commandName}`);
      }
    } catch (err) {
      console.error('Error executing command:', err);
      setError(err.message);
      throw err;
    }
  };

  const renderAttributeValue = (attr, attrName) => {
    const currentValue = realTimeData[attrName] !== undefined 
      ? realTimeData[attrName] 
      : attr.value;

    if (attr.writable) {
      return (
        <div className="attribute-input">
          <input
            type="number"
            step="0.001"
            defaultValue={currentValue}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                writeAttribute(attrName, parseFloat(e.target.value));
              }
            }}
          />
          <button onClick={() => readAttribute(attrName)}>Read</button>
        </div>
      );
    } else {
      return (
        <div className="attribute-readonly">
          <span className="value">{currentValue}</span>
          <span className="unit">{attr.unit}</span>
          <button onClick={() => readAttribute(attrName)}>Refresh</button>
        </div>
      );
    }
  };

  if (loading) {
    return <div className="device-control loading">Loading device information...</div>;
  }

  if (error) {
    return (
      <div className="device-control error">
        <h3>Error: {error}</h3>
        <button onClick={fetchDeviceInfo}>Retry</button>
      </div>
    );
  }

  if (!deviceInfo) {
    return <div className="device-control">No device information available</div>;
  }

  return (
    <div className="device-control">
      <div className="device-header">
        <h2>{deviceName}</h2>
        <div className="device-status">
          <span className={`state ${deviceInfo.state?.toLowerCase()}`}>
            {deviceInfo.state}
          </span>
          <span className={`connection ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '🟢' : '🔴'}
          </span>
        </div>
        <button 
          className={`monitor-btn ${monitoring ? 'active' : ''}`}
          onClick={toggleMonitoring}
          disabled={!connected}
        >
          {monitoring ? 'Stop Monitoring' : 'Start Monitoring'}
        </button>
      </div>

      {deviceInfo.status && (
        <div className="device-info">
          <p><strong>Status:</strong> {deviceInfo.status}</p>
          <p><strong>Server:</strong> {deviceInfo.server}</p>
          <p><strong>Class:</strong> {deviceInfo.info}</p>
          {realTimeData.timestamp && (
            <p><strong>Last Update:</strong> {new Date(realTimeData.timestamp).toLocaleString()}</p>
          )}
        </div>
      )}

      <div className="device-sections">
        <div className="attributes-section">
          <h3>Attributes</h3>
          <div className="attributes-grid">
            {Object.entries(attributes).map(([attrName, attr]) => (
              <div key={attrName} className="attribute-item">
                <label>{attrName}</label>
                {attr.error ? (
                  <div className="error">Error: {attr.error}</div>
                ) : (
                  renderAttributeValue(attr, attrName)
                )}
                {attr.description && (
                  <small className="description">{attr.description}</small>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="commands-section">
          <h3>Commands</h3>
          <div className="commands-grid">
            {Object.entries(commands).map(([cmdName, cmd]) => (
              <div key={cmdName} className="command-item">
                <button 
                  onClick={() => executeCommand(cmdName)}
                  className="command-btn"
                >
                  {cmdName}
                </button>
                {cmd.in_type_desc && (
                  <small>Input: {cmd.in_type_desc}</small>
                )}
                {cmd.out_type_desc && (
                  <small>Output: {cmd.out_type_desc}</small>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeviceControl;