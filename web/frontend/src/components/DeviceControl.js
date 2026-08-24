// DeviceControl.js - Generic device control component
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import './DeviceControl.css';

const DeviceControl = ({ deviceName, deviceType = 'generic' }) => {
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [attributes, setAttributes] = useState({});
  const [commands, setCommands] = useState({});
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingAttributes, setLoadingAttributes] = useState(false);
  const [loadingCommands, setLoadingCommands] = useState(false);
  const [attributesLoaded, setAttributesLoaded] = useState(false);
  const [commandsLoaded, setCommandsLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [realTimeData, setRealTimeData] = useState({});
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);

  const socketRef = useRef(null);

  const parseJsonOrThrow = async (response, fallbackMessage) => {
    let payload = null;
    try {
      payload = await response.json();
    } catch (_err) {
      payload = null;
    }
    if (!response.ok || payload?.success === false) {
      throw new Error(payload?.error || fallbackMessage || `HTTP ${response.status}`);
    }
    return payload;
  };

  useEffect(() => {
    setDeviceInfo(null);
    setAttributes({});
    setCommands({});
    setAttributesLoaded(false);
    setCommandsLoaded(false);
    setError(null);
    setRealTimeData({});
    setLoadingSummary(true);

    if (deviceName) {
      fetchDeviceSummary();
      initializeWebSocket();
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, [deviceName]);

  const initializeWebSocket = () => {
    socketRef.current = io('/', {
      withCredentials: true,
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
        fetchDeviceSummary();
        if (attributesLoaded) {
          fetchAttributes(true);
        }
      }
    });

    socketRef.current.on('error', (data) => {
      console.error('WebSocket error:', data.message);
      setError(data.message);
    });
  };

  const fetchDeviceSummary = async () => {
    try {
      setLoadingSummary(true);
      const response = await fetch(`/api/device/${deviceName}/summary`, {
        credentials: 'include'
      });

      const data = await parseJsonOrThrow(response, 'Failed to load device summary');
      setDeviceInfo(data.device_info);
      setError(null);
    } catch (err) {
      console.error('Error fetching device summary:', err);
      setError(err.message);
    } finally {
      setLoadingSummary(false);
    }
  };

  const fetchAttributes = async (force = false) => {
    if (!force && attributesLoaded) {
      return;
    }

    try {
      setLoadingAttributes(true);
      const response = await fetch(`/api/device/${deviceName}/attributes`, {
        credentials: 'include'
      });
      const data = await parseJsonOrThrow(response, 'Failed to load attributes');
      setAttributes(data.attributes || {});
      setAttributesLoaded(true);
      setError(null);
    } catch (err) {
      console.error('Error fetching attributes:', err);
      setError(err.message);
    } finally {
      setLoadingAttributes(false);
    }
  };

  const fetchCommands = async (force = false) => {
    if (!force && commandsLoaded) {
      return;
    }

    try {
      setLoadingCommands(true);
      const response = await fetch(`/api/device/${deviceName}/commands`, {
        credentials: 'include'
      });
      const data = await parseJsonOrThrow(response, 'Failed to load commands');
      setCommands(data.commands || {});
      setCommandsLoaded(true);
      setError(null);
    } catch (err) {
      console.error('Error fetching commands:', err);
      setError(err.message);
    } finally {
      setLoadingCommands(false);
    }
  };

  const fetchAllDetails = async () => {
    await Promise.all([fetchAttributes(true), fetchCommands(true)]);
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
      if (!attributesLoaded) {
        await fetchAttributes();
      }
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
      if (!attributesLoaded) {
        await fetchAttributes();
      }
      const url = `/api/device/${deviceName}/attribute/${attributeName}`;
      const response = await fetchWithHardwareApproval(url, {
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
      if (!commandsLoaded) {
        await fetchCommands();
      }
      const url = `/api/device/${deviceName}/command/${commandName}`;
      const response = await fetchWithHardwareApproval(url, {
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
        fetchDeviceSummary();
        if (attributesLoaded) {
          fetchAttributes(true);
        }
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

  if (loadingSummary) {
    return <div className="device-control loading">Loading device information...</div>;
  }

  if (error && !deviceInfo) {
    return (
      <div className="device-control error">
        <h3>Error: {error}</h3>
        <button onClick={fetchDeviceSummary}>Retry</button>
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
          <p><strong>Type:</strong> {deviceType}</p>
          {realTimeData.timestamp && (
            <p><strong>Last Update:</strong> {new Date(realTimeData.timestamp).toLocaleString()}</p>
          )}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px' }}>
            <button onClick={fetchDeviceSummary}>Refresh Summary</button>
            <button onClick={fetchAllDetails}>Load/Refresh All Details</button>
          </div>
        </div>
      )}

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="device-sections">
        <div className="attributes-section">
          <h3>Attributes</h3>
          <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => fetchAttributes(!attributesLoaded)}
              disabled={loadingAttributes}
            >
              {attributesLoaded ? 'Refresh Attributes' : 'Load Attributes'}
            </button>
            {loadingAttributes && <span>Loading...</span>}
          </div>
          {attributesLoaded && (
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
              {Object.keys(attributes).length === 0 && (
                <div>No attributes were returned for this device.</div>
              )}
            </div>
          )}
          {!attributesLoaded && !loadingAttributes && (
            <div>Attributes are loaded on demand.</div>
          )}
        </div>

        <div className="commands-section">
          <h3>Commands</h3>
          <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => fetchCommands(!commandsLoaded)}
              disabled={loadingCommands}
            >
              {commandsLoaded ? 'Refresh Commands' : 'Load Commands'}
            </button>
            {loadingCommands && <span>Loading...</span>}
          </div>
          {commandsLoaded && (
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
              {Object.keys(commands).length === 0 && (
                <div>No commands were returned for this device.</div>
              )}
            </div>
          )}
          {!commandsLoaded && !loadingCommands && (
            <div>Commands are loaded on demand.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DeviceControl;
