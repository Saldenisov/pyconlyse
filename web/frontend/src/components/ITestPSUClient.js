// ITestPSUClient.js - Specialized client for iTest PSU devices
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import './ITestPSUClient.css';

const CURRENT_STEPS = [0.001, 0.01, 0.1, 1];
const DEFAULT_CURRENT_STEP = 0.1;

function readCurrentStep(storageKey) {
  try {
    const saved = Number(window.localStorage.getItem(storageKey));
    return CURRENT_STEPS.includes(saved) ? saved : DEFAULT_CURRENT_STEP;
  } catch {
    return DEFAULT_CURRENT_STEP;
  }
}

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
  const setpoints = Object.fromEntries(ids.map((id, index) => [id, data.currents_setpoint?.[index]]));
  const measuredCurrents = data.currents_meas || [];
  const limitsArray = data.current_limits || [];
  const limits = {};

  ids.forEach((id, idx) => {
    const min = limitsArray[idx * 2];
    const max = limitsArray[idx * 2 + 1];
    limits[id] = {
      min: min ?? -5.0,
      max: max ?? 15.0,
      verified: Number.isFinite(min) && Number.isFinite(max) && min <= max,
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

function SlotCurrentControl({ name, setpoint, limits, canStep, storageKey, onApply }) {
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(() => readCurrentStep(storageKey));
  const [stepMenuOpen, setStepMenuOpen] = useState(false);
  const requestActive = useRef(false);
  const editor = useRef(null);
  const stepButton = useRef(null);
  const inputValue = draft ?? setpoint.toFixed(3);

  useEffect(() => {
    const syncStep = (event) => {
      if (event.key === storageKey || event.key === null) {
        setCurrentStep(readCurrentStep(storageKey));
      }
    };
    window.addEventListener('storage', syncStep);
    return () => window.removeEventListener('storage', syncStep);
  }, [storageKey]);

  useEffect(() => {
    if (!stepMenuOpen) return undefined;
    editor.current?.querySelector('.itest-step-menu [aria-pressed="true"]')?.focus();
    const closeOutside = (event) => {
      if (!editor.current?.contains(event.target)) setStepMenuOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [stepMenuOpen]);

  const chooseStep = (step) => {
    setCurrentStep(step);
    try {
      window.localStorage.setItem(storageKey, String(step));
    } catch {
      // The selected step is still available for this view.
    }
    setStepMenuOpen(false);
    stepButton.current?.focus();
  };

  const apply = async (value) => {
    if (requestActive.current) return;
    requestActive.current = true;
    setSaving(true);
    try {
      if (await onApply(value)) setDraft(null);
    } finally {
      requestActive.current = false;
      setSaving(false);
    }
  };

  const nudge = (direction) => Number((setpoint + direction * currentStep).toFixed(3));

  return (
    <div className="itest-current-editor" ref={editor} onKeyDown={(event) => {
      if (event.key === 'Escape' && stepMenuOpen) {
        event.stopPropagation();
        setStepMenuOpen(false);
        stepButton.current?.focus();
      }
    }}>
      <div className="slot-control">
        <input
          type="number"
          step="0.001"
          min={limits.min}
          max={limits.max}
          value={inputValue}
          readOnly={saving}
          aria-label={`${name} current (A)`}
          className="current-input"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' || event.nativeEvent.isComposing) return;
            event.preventDefault();
            event.stopPropagation();
            if (!event.repeat) apply(inputValue);
          }}
        />
        <div className="itest-current-arrows" onContextMenu={(event) => {
          event.preventDefault();
          setStepMenuOpen(true);
        }}>
          {[1, -1].map((direction) => {
            const target = nudge(direction);
            const action = direction === 1 ? 'Increase' : 'Decrease';
            return (
              <button key={direction} type="button"
                aria-label={`${action} ${name} current`}
                title={`${action} by ${currentStep} A · right-click to change step`}
                disabled={saving || !canStep || target < limits.min || target > limits.max}
                onClick={() => { setStepMenuOpen(false); apply(target); }}>
                {direction === 1 ? '▴' : '▾'}
              </button>
            );
          })}
        </div>
        <button type="button" className="btn-set-current" disabled={saving} onClick={() => apply(inputValue)}>Set</button>
      </div>
      <div className="slot-limits">
        <small>Limits: {limits.min}…{limits.max} A</small>
        <button ref={stepButton} type="button" className="itest-step-trigger"
          aria-label={`${name} current step: ${currentStep} A`}
          aria-expanded={stepMenuOpen} onClick={() => setStepMenuOpen(!stepMenuOpen)}>
          Step {currentStep} A
        </button>
        {stepMenuOpen && (
          <div className="itest-step-menu" role="group" aria-label={`${name} current step options`}>
            {CURRENT_STEPS.map((step) => (
              <button type="button" key={step} aria-pressed={step === currentStep} onClick={() => chooseStep(step)}>
                {step} A
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const ITestPSUClient = ({ deviceName, fixedTab = null, compact = false }) => {
  // Tab configuration
  const [selectedTab, setActiveTab] = useState('V0');
  const activeTab = fixedTab || selectedTab;
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
  const [slotSetpoints, setSlotSetpoints] = useState({});
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
        if (disposed || socketRef.current !== socket) return;
        setConnected(true);
        socket.emit('subscribe_device', { device: deviceName });
      });

      socket.on('subscribed', (data) => {
        if (disposed || socketRef.current !== socket || data.device !== deviceName) return;
        setMonitoring(true);
      });

      socket.on('disconnect', () => {
        if (disposed || socketRef.current !== socket) return;
        setConnected(false);
        setMonitoring(false);
      });

      socket.on('connect_error', (err) => {
        if (disposed || socketRef.current !== socket) return;
        setConnected(false);
        setMonitoring(false);
        setError(err.message);
      });

      socket.on('device_update', (data) => {
        if (disposed || socketRef.current !== socket || data.device !== deviceName || !Array.isArray(data.slots)) {
          return;
        }

        setMonitoring(true);
        setError(null);
        setSlotIds(data.slots.map((slot) => slot.id));
        setSlotNames(data.slots.map((slot) => slot.name));
        setSlotStates(data.slots.map((slot) => (slot.state ? 1 : 0)));
        setSlotSetpoints(Object.fromEntries(data.slots.map((slot) => [slot.id, slot.current_setpoint])));
        setSlotMeasuredCurrents(data.slots.map((slot) => slot.current_measured || 0));
      });

      socket.on('device_error', (data) => {
        if (!disposed && socketRef.current === socket && data.device === deviceName) {
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

  const setSlotOutputState = async (slotId, state) => {
    try {
      const url = `/api/device/itest/${deviceName}/slot/${slotId}/output`;
      const response = await fetchWithHardwareApproval(url, {
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

  const setSlotCurrent = async (slotId, inputValue) => {
    const limits = slotLimits[slotId] || { min: -5.0, max: 15.0 };
    const value = typeof inputValue === 'string' && inputValue.trim() ? Number(inputValue) : inputValue;
    if (!Number.isFinite(value)) throw new Error('Please enter a valid number');
    if (value < limits.min || value > limits.max) {
      throw new Error(`Current ${value}A outside limits [${limits.min}, ${limits.max}]A`);
    }

    const socket = socketRef.current;
    const url = `/api/device/itest/${deviceName}/slot/${slotId}/current`;
    const response = await fetchWithHardwareApproval(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ value })
    });
    const data = await response.json();
    if (!response.ok || data?.success !== true) {
      throw new Error(data?.error || 'Failed to set current');
    }
    if (data.slot_id !== slotId || !Number.isFinite(data.current_setpoint)) {
      throw new Error('iTest did not return a valid setpoint for this channel');
    }
    if (socketRef.current === socket) {
      setSlotSetpoints((previous) => ({ ...previous, [slotId]: data.current_setpoint }));
    }
  };
  
  const handleSlotCurrentChange = async (slotId, inputValue) => {
    const socket = socketRef.current;
    try {
      await setSlotCurrent(slotId, inputValue);
      if (socketRef.current === socket) setError(null);
      return true;
    } catch (err) {
      if (socketRef.current === socket) setError(err.message);
      return false;
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
    <div className={`itest-client${compact ? ' is-compact' : ''}`}>
      <div className="client-header">
        <h2>iTest PSU: {deviceName}</h2>
        <div className="connection-status">
          <span className={`status ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '🟢 Connected' : '🔴 Disconnected'}
          </span>
          <span
            className={`monitor-btn ${monitoring ? 'active' : ''}`}
            role="status"
            aria-live="polite"
          >
            {monitoring ? 'Monitoring automatically' : 'Waiting for monitoring'}
          </span>
        </div>
      </div>

      {/* Tab navigation */}
      {!fixedTab && <div className="tab-navigation">
        {Object.keys(tabConfigs).map(tabName => (
          <button
            key={tabName}
            className={`tab-btn ${activeTab === tabName ? 'active' : ''}`}
            onClick={() => setActiveTab(tabName)}
          >
            {tabName}
          </button>
        ))}
      </div>}

      {/* Tab controls */}
      {!compact && <div className="tab-controls">
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
      </div>}

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
          const setpoint = slotSetpoints[slotId] ?? 0.0;
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
              
              <SlotCurrentControl key={`${deviceName}:${slotId}`} name={name} setpoint={setpoint} limits={limits}
                canStep={Number.isFinite(slotSetpoints[slotId]) && slotLimits[slotId]?.verified}
                storageKey={`pyconlyse.itest.current-step.${deviceName.toLowerCase()}.${slotId}`}
                onApply={(value) => handleSlotCurrentChange(slotId, value)} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ITestPSUClient;
