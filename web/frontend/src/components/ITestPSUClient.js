// ITestPSUClient.js - Specialized client for iTest PSU devices
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './ITestPSUClient.css';

const ITestPSUClient = ({ deviceName }) => {
  // Tab configuration
  const [activeTab, setActiveTab] = useState('VD');
  const [tabConfigs, setTabConfigs] = useState({
    VD: { slots: [], defaults: {}, enabled: true },
    VD2: { slots: [], defaults: {}, enabled: true },
    RF: { slots: [], defaults: {}, enabled: true },
    ALL: { slots: [], defaults: {}, enabled: true }
  });
  
  // Slot data arrays
  const [slotNames, setSlotNames] = useState([]);
  const [slotIds, setSlotIds] = useState([]);
  const [slotStates, setSlotStates] = useState([]);
  const [slotSetpoints, setSlotSetpoints] = useState([]);
  const [slotMeasuredCurrents, setSlotMeasuredCurrents] = useState([]);
  const [slotLimits, setSlotLimits] = useState({}); // slot_id -> {min, max}
  
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [availableSlots, setAvailableSlots] = useState([]);
  
  const socketRef = useRef(null);
  const newSetpointRef = useRef();

  useEffect(() => {
    if (deviceName) {
      fetchTabConfiguration();
      fetchSlotData();
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
      if (data.device === deviceName) {
        if (data.states !== undefined) setSlotStates(data.states);
        if (data.currents_setpoint !== undefined) setSlotSetpoints(data.currents_setpoint);
        if (data.currents_meas !== undefined) setSlotMeasuredCurrents(data.currents_meas);
      }
    });

    socketRef.current.on('device_error', (data) => {
      if (data.device === deviceName) {
        setError(data.error);
      }
    });
  };

  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  };

  const fetchTabConfiguration = async () => {
    try {
      const response = await fetch(`/api/device/ds_itest_psu/${deviceName}/tab_config`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setTabConfigs(data.tab_configs || tabConfigs);
      }
    } catch (err) {
      console.warn('Could not fetch tab configuration:', err);
    }
  };

  const fetchSlotData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/device/itest/${deviceName}/all_slots`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setSlotIds(data.ids || []);
        setSlotNames(data.names || []);
        setSlotStates(data.states || []);
        setSlotSetpoints(data.currents_setpoint || []);
        setSlotMeasuredCurrents(data.currents_meas || []);
        
        // Parse limits array [min1, max1, min2, max2, ...] into object
        const limitsObj = {};
        const limitsArray = data.current_limits || [];
        (data.ids || []).forEach((id, idx) => {
          limitsObj[id] = {
            min: limitsArray[idx * 2] || -5.0,
            max: limitsArray[idx * 2 + 1] || 15.0
          };
        });
        setSlotLimits(limitsObj);
        setAvailableSlots(data.ids || []);
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTabDefaults = async (tabName) => {
    const config = tabConfigs[tabName];
    if (!config || !config.defaults) return;
    
    try {
      for (const [slotId, defaultValue] of Object.entries(config.defaults)) {
        await setSlotCurrent(parseInt(slotId), defaultValue);
      }
      setError(null);
    } catch (err) {
      setError(`Failed to load defaults: ${err.message}`);
    }
  };
  
  const toggleTabOutputs = async (tabName, state) => {
    const config = tabConfigs[tabName];
    if (!config || !config.slots) return;
    
    try {
      for (const slotId of config.slots) {
        await setSlotOutputState(slotId, state ? 1 : 0);
      }
      setError(null);
    } catch (err) {
      setError(`Failed to toggle outputs: ${err.message}`);
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

  const setSlotOutputState = async (slotId, state) => {
    try {
      const response = await fetch(`/api/device/itest/${deviceName}/slot/${slotId}/output`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ state })
      });
      
      if (response.ok) {
        await fetchSlotData();
      } else {
        throw new Error(`Failed to set output state`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const setSlotCurrent = async (slotId, value) => {
    try {
      const limits = slotLimits[slotId] || { min: -5.0, max: 15.0 };
      if (value < limits.min || value > limits.max) {
        throw new Error(`Current ${value}A outside limits [${limits.min}, ${limits.max}]A`);
      }
      
      const response = await fetch(`/api/device/itest/${deviceName}/slot/${slotId}/current`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ value })
      });
      
      if (response.ok) {
        await fetchSlotData();
      } else {
        throw new Error(`Failed to set current`);
      }
    } catch (err) {
      throw err;
    }
  };
  
  const handleSlotCurrentChange = async (slotId, inputValue) => {
    const value = parseFloat(inputValue);
    if (isNaN(value)) {
      setError('Please enter a valid number');
      return;
    }
    
    try {
      await setSlotCurrent(slotId, value);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return <div className="itest-client loading">Loading iTest PSU...</div>;
  }

  const currentTabConfig = tabConfigs[activeTab] || { slots: [], defaults: {}, enabled: true };
  const currentSlots = currentTabConfig.slots.filter(id => slotIds.includes(id));

  return (
    <div className="itest-client">
      <div className="client-header">
        <h2>iTest PSU: {deviceName}</h2>
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
      </div>

      {/* Tab navigation */}
      <div className="tab-navigation">
        {Object.keys(tabConfigs).map(tabName => (
          <button
            key={tabName}
            className={`tab-btn ${activeTab === tabName ? 'active' : ''}`}
            onClick={() => setActiveTab(tabName)}
          >
            {tabName}
          </button>
        ))}
      </div>

      {/* Tab controls */}
      <div className="tab-controls">
        <button 
          className="btn-load-defaults"
          onClick={() => loadTabDefaults(activeTab)}
        >
          Load Defaults
        </button>
        <label className="toggle-all">
          <input 
            type="checkbox"
            checked={currentSlots.every(id => {
              const idx = slotIds.indexOf(id);
              return idx >= 0 && slotStates[idx] === 1;
            })}
            onChange={(e) => toggleTabOutputs(activeTab, e.target.checked)}
          />
          <span>Enable All Slots</span>
        </label>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
          <button onClick={fetchSlotData}>Retry</button>
        </div>
      )}

      {/* Slot controls grid */}
      <div className="slots-grid">
        {currentSlots.map(slotId => {
          const idx = slotIds.indexOf(slotId);
          if (idx < 0) return null;
          
          const name = slotNames[idx] || `Slot ${slotId}`;
          const state = slotStates[idx] || 0;
          const setpoint = slotSetpoints[idx] || 0.0;
          const measured = slotMeasuredCurrents[idx] || 0.0;
          const limits = slotLimits[slotId] || { min: -5.0, max: 15.0 };
          
          return (
            <div key={slotId} className="slot-card">
              <div className="slot-header">
                <h4>{name}</h4>
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={state === 1}
                    onChange={(e) => setSlotOutputState(slotId, e.target.checked ? 1 : 0)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
              
              <div className="slot-readings">
                <div className="reading">
                  <span className="label">Setpoint:</span>
                  <span className="value">{setpoint.toFixed(3)} A</span>
                </div>
                <div className="reading">
                  <span className="label">Measured:</span>
                  <span className="value">{measured.toFixed(3)} A</span>
                </div>
              </div>
              
              <div className="slot-control">
                <input
                  type="number"
                  step="0.001"
                  min={limits.min}
                  max={limits.max}
                  defaultValue={setpoint.toFixed(3)}
                  className="current-input"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSlotCurrentChange(slotId, e.target.value);
                    }
                  }}
                />
                <button
                  className="btn-set-current"
                  onClick={(e) => {
                    const input = e.target.previousSibling;
                    handleSlotCurrentChange(slotId, input.value);
                  }}
                >
                  Set
                </button>
              </div>
              
              <div className="slot-limits">
                <small>Limits: {limits.min} to {limits.max} A</small>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ITestPSUClient;