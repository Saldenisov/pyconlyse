// DSNetioPDUClient.js - Multi-device NETIO PDU web client
import React, { useCallback, useState, useEffect, useMemo, useRef } from 'react';
import io from 'socket.io-client';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import './DSNetioPDUClient.css';

const EMPTY_DEVICES = [];
const devicePath = (deviceName) => encodeURI(String(deviceName));
const asInt = (value, fallback = 0) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};
const normalizeOutput = (output, index) => ({
  id: asInt(output?.id, index + 1),
  name: String(output?.name || `Output ${index + 1}`),
  state: asInt(output?.state, 0) ? 1 : 0,
});
const parseDeviceAttributes = (deviceName, attributes) => {
  const outputs = [];
  const ids = attributes.ids?.value || [];
  const names = attributes.names?.value || [];
  const states = attributes.states?.value || attributes.output_statuses?.value || [];
  for (let i = 0; i < Math.max(ids.length, 4); i++) {
    outputs.push({
      id: asInt(ids[i], i + 1),
      name: String(names[i] || `Output ${i + 1}`),
      state: asInt(states[i], 0) ? 1 : 0,
    });
  }
  return { name: deviceName, outputs, state: 'ON' };
};

const DSNetioPDUClient = ({ deviceNames: requestedDeviceNames = EMPTY_DEVICES }) => {
  const deviceNamesKey = JSON.stringify(requestedDeviceNames || EMPTY_DEVICES);
  const deviceNames = useMemo(() => JSON.parse(deviceNamesKey), [deviceNamesKey]);
  const [devices, setDevices] = useState({});
  const [selectedDevices, setSelectedDevices] = useState([]);
  const [showAllDevices, setShowAllDevices] = useState(true);
  const [connected, setConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [monitoring, setMonitoring] = useState(true);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyDevices, setBusyDevices] = useState({});
  
  const socketRef = useRef(null);
  const monitoringRef = useRef(true);
  const selectedDevicesRef = useRef([]);
  const busyDevicesRef = useRef(new Set());

  const parseJsonOrThrow = async (response, fallbackMessage) => {
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = null;
    }
    if (!response.ok || payload?.success === false) {
      const detail = payload?.error || payload?.msg || payload?.message;
      const message = detail || `${fallbackMessage || 'Request failed'} (HTTP ${response.status})`;
      const requestError = new Error(message);
      requestError.status = response.status;
      throw requestError;
    }
    return payload;
  };

  useEffect(() => {
    selectedDevicesRef.current = selectedDevices;
  }, [selectedDevices]);

  const fetchAllDevicesData = useCallback(async () => {
    try {
      setLoading(true);
      const devicesData = {};
      
      for (const deviceName of deviceNames) {
        try {
          const response = await fetch(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
            credentials: 'include'
          });
          
          if (response.ok) {
            const data = await response.json();
            devicesData[deviceName] = {
              name: deviceName,
              outputs: (data.outputs || []).map(normalizeOutput),
              state: data.state || 'UNKNOWN'
            };
          } else {
            // Try alternative API endpoint
            const altResponse = await fetch(`/api/device/${devicePath(deviceName)}/attributes`, {
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
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [deviceNames]);

  useEffect(() => {
    if (!deviceNames.length) return undefined;
    selectedDevicesRef.current = deviceNames;
    setSelectedDevices(deviceNames);
    fetchAllDevicesData();
    const socket = io('/', { withCredentials: true });
    socketRef.current = socket;
    let hasConnected = false;
    socket.on('connect', () => {
      if (socketRef.current !== socket) return;
      setConnected(true);
      setConnectionError(null);
      if (monitoringRef.current) {
        selectedDevicesRef.current.forEach(deviceName => {
          socket.emit('subscribe_device', { device: deviceName });
        });
      }
      if (hasConnected) fetchAllDevicesData();
      hasConnected = true;
    });
    socket.on('disconnect', () => {
      if (socketRef.current !== socket) return;
      setConnected(false);
      setConnectionError(new Error('Live updates connection lost. Pyconlyse is reconnecting; use Reconnect to retry now.'));
    });
    socket.on('connect_error', (cause) => {
      if (socketRef.current !== socket) return;
      setConnected(false);
      setConnectionError(new Error(`Live updates connection failed: ${cause?.message || 'server unavailable'}. Use Reconnect to try again.`));
    });
    socket.on('device_update', (data) => {
      if (socketRef.current !== socket || !data.device) return;
      setDevices(prev => {
        if (!prev[data.device]) return prev;
        return {
          ...prev,
          [data.device]: {
            ...prev[data.device],
            outputs: data.outputs || prev[data.device].outputs,
            state: data.state || prev[data.device].state,
          },
        };
      });
    });
    socket.on('device_error', (data) => {
      if (socketRef.current === socket && deviceNames.includes(data.device)) {
        setError(`${data.device}: ${data.error}`);
      }
    });
    return () => {
      if (socketRef.current === socket) socketRef.current = null;
      socket.disconnect();
    };
  }, [deviceNames, fetchAllDevicesData]);

  const toggleMonitoring = () => {
    if (!socketRef.current || !connected) return;

    if (monitoring) {
      selectedDevices.forEach(deviceName => {
        socketRef.current.emit('unsubscribe_device', { device: deviceName });
      });
      monitoringRef.current = false;
      setMonitoring(false);
    } else {
      selectedDevices.forEach(deviceName => {
        socketRef.current.emit('subscribe_device', { device: deviceName });
      });
      monitoringRef.current = true;
      setMonitoring(true);
    }
  };

  const setOutputState = async (deviceName, outputId, state) => {
    if (busyDevicesRef.current.has(deviceName)) return;
    busyDevicesRef.current.add(deviceName);
    setBusyDevices(prev => ({ ...prev, [deviceName]: true }));
    try {
      // A command writes the whole PDU. Read it first so an old tab cannot
      // overwrite changes to other outlets made by experiment preparation.
      const current = await fetch(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
        credentials: 'include',
      });
      const currentPayload = await parseJsonOrThrow(current, `Failed to read ${deviceName}`);
      const currentOutputs = (currentPayload.outputs || []).map(normalizeOutput);
      const currentOutput = currentOutputs.find(output => output.id === outputId);
      if (!currentOutput) throw new Error(`Output ${outputId} is missing on ${deviceName}`);
      setDevices(prev => ({
        ...prev,
        [deviceName]: { ...prev[deviceName], state: currentPayload.state, outputs: currentOutputs },
      }));
      if (currentOutput.state === (state ? 1 : 0)) {
        setError(null);
        return;
      }

      const states = currentOutputs.map(output =>
        output.id === outputId ? (state ? 1 : 0) : output.state
      );
      
      const url = `/api/device/${devicePath(deviceName)}/command/set_channels_states`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: states })
      });

      await parseJsonOrThrow(response, `Failed to set output ${outputId} for ${deviceName}`);

      const verify = await fetch(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
        credentials: 'include',
      });
      const verifyPayload = await parseJsonOrThrow(
        verify,
        `Failed to verify output ${outputId} state for ${deviceName}`
      );
      const normalizedOutputs = (verifyPayload.outputs || []).map(normalizeOutput);
      const updatedOutput = normalizedOutputs.find((output) => output.id === outputId);
      if (updatedOutput && updatedOutput.state !== (state ? 1 : 0)) {
        throw new Error(
          `Output ${outputId} on ${deviceName} did not change state. Check device-side permissions/rules.`
        );
      }
      setDevices((prev) => ({
        ...prev,
        [deviceName]: {
          ...prev[deviceName],
          state: verifyPayload.state || prev[deviceName].state,
          outputs: normalizedOutputs,
        },
      }));
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      busyDevicesRef.current.delete(deviceName);
      setBusyDevices(prev => ({ ...prev, [deviceName]: false }));
    }
  };

  const setAllOutputs = async (deviceName, state) => {
    if (busyDevicesRef.current.has(deviceName)) return;
    busyDevicesRef.current.add(deviceName);
    setBusyDevices(prev => ({ ...prev, [deviceName]: true }));
    try {
      const current = await fetch(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
        credentials: 'include',
      });
      const currentPayload = await parseJsonOrThrow(current, `Failed to read ${deviceName}`);
      const currentOutputs = (currentPayload.outputs || []).map(normalizeOutput);
      if (!currentOutputs.length) throw new Error(`No outputs found on ${deviceName}`);
      const states = currentOutputs.map(() => state ? 1 : 0);
      
      const url = `/api/device/${devicePath(deviceName)}/command/set_channels_states`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: states })
      });

      await parseJsonOrThrow(response, `Failed to set all outputs for ${deviceName}`);

      const verify = await fetch(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
        credentials: 'include',
      });
      const verifyPayload = await parseJsonOrThrow(
        verify,
        `Failed to verify outputs state for ${deviceName}`
      );
      const normalizedOutputs = (verifyPayload.outputs || []).map(normalizeOutput);
      if (normalizedOutputs.length !== states.length ||
          normalizedOutputs.some(output => output.state !== (state ? 1 : 0))) {
        throw new Error(`Outputs on ${deviceName} did not reach the requested state.`);
      }
      setDevices((prev) => ({
        ...prev,
        [deviceName]: {
          ...prev[deviceName],
          state: verifyPayload.state || prev[deviceName].state,
          outputs: normalizedOutputs,
        },
      }));
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      busyDevicesRef.current.delete(deviceName);
      setBusyDevices(prev => ({ ...prev, [deviceName]: false }));
    }
  };

  const changeSelectedDevices = (next) => {
    if (monitoringRef.current && socketRef.current?.connected) {
      selectedDevicesRef.current.filter(name => !next.includes(name)).forEach(name => {
        socketRef.current.emit('unsubscribe_device', { device: name });
      });
      next.filter(name => !selectedDevicesRef.current.includes(name)).forEach(name => {
        socketRef.current.emit('subscribe_device', { device: name });
      });
    }
    selectedDevicesRef.current = next;
    setSelectedDevices(next);
  };

  const toggleDeviceSelection = (deviceName) => {
    changeSelectedDevices(selectedDevices.includes(deviceName)
      ? selectedDevices.filter(name => name !== deviceName)
      : [...selectedDevices, deviceName]);
  };

  const selectAllDevices = () => {
    changeSelectedDevices(deviceNames);
    setShowAllDevices(true);
  };

  const deselectAllDevices = () => {
    changeSelectedDevices([]);
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
              disabled={!!busyDevices[deviceName]}
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
              disabled={!!busyDevices[deviceName]}
              title="Turn all outputs ON"
            >
              All ON
            </button>
            <button 
              className="device-btn all-off"
              onClick={() => setAllOutputs(deviceName, false)}
              disabled={!!busyDevices[deviceName]}
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
              {connected ? '🟢 Live updates connected' : '🔴 Live updates disconnected'}
            </span>
            {!connected && (
              <button className="monitor-btn" onClick={() => socketRef.current?.connect()}>
                Reconnect
              </button>
            )}
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

      {connectionError && (
        <div className="error-alert" role="alert">
          {connectionError.message}
        </div>
      )}

      {error && (
        <div className="error-alert" role="alert">
          <strong>Error:</strong> {error.message || error}
          <button onClick={fetchAllDevicesData}>Refresh readings</button>
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
          • Monitoring starts automatically for live updates
        </small>
      </div>
    </div>
  );
};

export default DSNetioPDUClient;
