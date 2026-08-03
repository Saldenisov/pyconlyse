// ITestPSUClient.js - Specialized client for iTest PSU devices
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { withCsrfToken } from '../api/csrfRequest';
import './ITestPSUClient.css';

async function fetchItestTabConfig(deviceName) {
  const response = await fetch(`/api/device/ds_itest_psu/${deviceName}/tab_config`, {
    credentials: 'include'
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

async function fetchItestSlotData(deviceName) {
  const response = await fetch(`/api/device/itest/${deviceName}/all_slots`, {
    credentials: 'include'
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

function normalizeItestSlotData(data) {
  const ids = data.ids || [];
  const names = data.names || [];
  const states = data.states || [];
  const setpoints = data.currents_setpoint || [];
  const measuredCurrents = data.currents_meas || [];
  const limitsArray = data.current_limits || [];
  const limits = {};

  ids.forEach((id, idx) => {
    limits[id] = {
      min: limitsArray[idx * 2] || -5.0,
      max: limitsArray[idx * 2 + 1] || 15.0
    };
  });

  return { ids, names, states, setpoints, measuredCurrents, limits };
}

function normalizeTabConfigs(rawConfigs) {
  const defaults = {
    V0: { slots: [], defaults: {}, enabled: true },
    VD2: { slots: [], defaults: {}, enabled: true },
    REF: { slots: [], defaults: {}, enabled: true },
    ALL: { slots: [], defaults: {}, enabled: true },
  };

  const aliases = {
    V0: 'V0',
    VD: 'V0',
    VD2: 'VD2',
    REF: 'REF',
    RF: 'REF',
    ALL: 'ALL',
  };

  const normalized = { ...defaults };
  Object.entries(rawConfigs || {}).forEach(([rawName, rawPayload]) => {
    const canonical = aliases[String(rawName).toUpperCase()];
    if (!canonical || !rawPayload) return;
    const slots = Array.isArray(rawPayload.slots)
      ? rawPayload.slots
          .map((value) => Number.parseInt(value, 10))
          .filter((value) => Number.isFinite(value))
      : [];
    const defaultsMap = {};
    Object.entries(rawPayload.defaults || {}).forEach(([slotId, value]) => {
      const key = Number.parseInt(slotId, 10);
      defaultsMap[Number.isFinite(key) ? key : slotId] = value;
    });

    normalized[canonical] = {
      ...defaults[canonical],
      ...rawPayload,
      slots,
      defaults: defaultsMap,
    };
  });

  return normalized;
}

const ITestPSUClient = ({ deviceName }) => {
  // Tab configuration
  const [activeTab, setActiveTab] = useState('V0');
  const [tabConfigs, setTabConfigs] = useState({
    V0: { slots: [], defaults: {}, enabled: true },
    VD2: { slots: [], defaults: {}, enabled: true },
    REF: { slots: [], defaults: {}, enabled: true },
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
  
  const socketRef = useRef(null);

  useEffect(() => {
    let disposed = false;

    const loadInitialData = async () => {
      if (!deviceName) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const [configData, slotData] = await Promise.all([
          fetchItestTabConfig(deviceName),
          fetchItestSlotData(deviceName),
        ]);

        if (disposed) {
          return;
        }

        setTabConfigs((current) => normalizeTabConfigs(configData.tab_configs || current));
        const normalized = normalizeItestSlotData(slotData);
        setSlotIds(normalized.ids);
        setSlotNames(normalized.names);
        setSlotStates(normalized.states);
        setSlotSetpoints(normalized.setpoints);
        setSlotMeasuredCurrents(normalized.measuredCurrents);
        setSlotLimits(normalized.limits);
        setError(null);
      } catch (err) {
        if (!disposed) {
          setError(err.message);
        }
      } finally {
        if (!disposed) {
          setLoading(false);
        }
      }
    };

    loadInitialData();

    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    if (deviceName) {
      const socket = io('/', {
        withCredentials: true,
      });
      socketRef.current = socket;

      socket.on('connect', () => {
        setConnected(true);
      });

      socket.on('disconnect', () => {
        setConnected(false);
        setMonitoring(false);
      });

      socket.on('device_update', (data) => {
        if (data.device !== deviceName || !Array.isArray(data.slots)) {
          return;
        }

        setSlotIds(data.slots.map((slot) => slot.id));
        setSlotNames(data.slots.map((slot) => slot.name));
        setSlotStates(data.slots.map((slot) => (slot.state ? 1 : 0)));
        setSlotSetpoints(data.slots.map((slot) => slot.current_setpoint || 0));
        setSlotMeasuredCurrents(data.slots.map((slot) => slot.current_measured || 0));
      });

      socket.on('device_error', (data) => {
        if (data.device === deviceName) {
          setError(data.error);
        }
      });
    } else {
      setConnected(false);
      setMonitoring(false);
    }

    return () => {
      disposed = true;
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [deviceName]);

  const fetchSlotData = async () => {
    try {
      setLoading(true);
      const data = await fetchItestSlotData(deviceName);
      const normalized = normalizeItestSlotData(data);
      setSlotIds(normalized.ids);
      setSlotNames(normalized.names);
      setSlotStates(normalized.states);
      setSlotSetpoints(normalized.setpoints);
      setSlotMeasuredCurrents(normalized.measuredCurrents);
      setSlotLimits(normalized.limits);
      setError(null);
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
      const url = `/api/device/itest/${deviceName}/slot/${slotId}/output`;
      const response = await fetch(url, withCsrfToken(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ state })
      }));
      
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
      
      const url = `/api/device/itest/${deviceName}/slot/${slotId}/current`;
      const response = await fetch(url, withCsrfToken(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ value })
      }));
      
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
  const allCurrentSlotsEnabled =
    currentSlots.length > 0 &&
    currentSlots.every((id) => {
      const idx = slotIds.indexOf(id);
      return idx >= 0 && slotStates[idx] === 1;
    });

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
            checked={allCurrentSlotsEnabled}
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
