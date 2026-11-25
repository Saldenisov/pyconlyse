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

function readBeamLineOrder(storageKey) {
  if (!storageKey) return [];
  try {
    const saved = JSON.parse(window.localStorage.getItem(storageKey));
    return Array.isArray(saved) ? saved.filter(Number.isInteger) : [];
  } catch {
    return [];
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

async function fetchItestSlotData(deviceName, qualified = false, signal) {
  const query = qualified ? '?qualified=1' : '';
  const response = await fetch(`/api/device/itest/${deviceName}/all_slots${query}`, {
    signal,
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

function SlotCurrentControl({ name, setpoint, limits, canStep, storageKey, onApply, readOnly, beamline }) {
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(() => readCurrentStep(storageKey));
  const [stepMenuOpen, setStepMenuOpen] = useState(false);
  const requestActive = useRef(false);
  const editor = useRef(null);
  const stepButton = useRef(null);
  const inputValue = draft ?? (Number.isFinite(setpoint) ? setpoint.toFixed(3) : '');

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
    if (readOnly || requestActive.current) return;
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
          readOnly={saving || readOnly}
          aria-label={beamline ? `${name} · consigne à régler (A)` : `${name} current (A)`}
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
            const label = beamline
              ? `${direction === 1 ? 'Augmenter' : 'Diminuer'} la consigne · ${name}` : `${action} ${name} current`;
            return (
              <button key={direction} type="button"
                aria-label={label}
                title={beamline ? `${label} (${currentStep} A)` : `${action} by ${currentStep} A · right-click to change step`}
                disabled={readOnly || saving || !canStep || target < limits.min || target > limits.max}
                onClick={() => { setStepMenuOpen(false); apply(target); }}>
                {direction === 1 ? (beamline ? '>' : '▴') : (beamline ? '<' : '▾')}
              </button>
            );
          })}
        </div>
        <button type="button" className="btn-set-current" disabled={saving || readOnly} onClick={() => apply(inputValue)}>
          {beamline ? 'Régler' : 'Set'}
        </button>
      </div>
      <div className="slot-limits">
        <small>{beamline ? 'Limites' : 'Limits'}: {limits.verified || !beamline ? `${limits.min}…${limits.max} A` : '—'}</small>
        <button ref={stepButton} type="button" className="itest-step-trigger"
          aria-label={beamline ? `${name} · pas : ${currentStep} A` : `${name} current step: ${currentStep} A`}
          aria-expanded={stepMenuOpen} onClick={() => setStepMenuOpen(!stepMenuOpen)}>
          {beamline ? 'Pas' : 'Step'} {currentStep} A
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

const ITestPSUClient = ({ deviceName, fixedTab = null, compact = false, readOnly = false, beamline = false }) => {
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
  const [configuredNames, setConfiguredNames] = useState({});
  const [hardwareAvailable, setHardwareAvailable] = useState(false);
  const commandsLocked = readOnly || (beamline && !hardwareAvailable);
  const [slotIds, setSlotIds] = useState([]);
  const [slotStates, setSlotStates] = useState([]);
  const [slotSetpoints, setSlotSetpoints] = useState({});
  const [slotMeasuredCurrents, setSlotMeasuredCurrents] = useState([]);
  const [slotLimits, setSlotLimits] = useState({}); // slot_id -> {min, max}
  
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const orderKey = beamline ? `pyconlyse.itest.beamline-order.${deviceName.toLowerCase()}.${activeTab}` : null;
  const [slotOrder, setSlotOrder] = useState(() => readBeamLineOrder(orderKey));
  const dragging = useRef(null);
  const [dropTarget, setDropTarget] = useState(null);
  
  const socketRef = useRef(null);

  useEffect(() => {
    if (!beamline || !deviceName) return undefined;
    const controller = new AbortController();
    let timer;
    const loadConfig = async () => {
      try {
        const config = await fetchItestTabConfig(deviceName);
        if (controller.signal.aborted) return;
        setTabConfigs(normalizeTabConfigs(config.tab_configs));
        setConfiguredNames(config.slot_names || {});
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    const readSlots = async () => {
      try {
        const data = await fetchItestSlotData(deviceName, true, controller.signal);
        if (!controller.signal.aborted) {
          const normalized = normalizeItestSlotData(data);
          setHardwareAvailable(data.hardware_available === true);
          setSlotIds(normalized.ids);
          setSlotNames(normalized.names);
          setSlotStates(normalized.states);
          setSlotSetpoints(normalized.setpoints);
          setSlotMeasuredCurrents(normalized.measuredCurrents);
          setSlotLimits(normalized.limits);
        }
      } catch {
        if (!controller.signal.aborted) setHardwareAvailable(false);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(readSlots, 1000);
      }
    };
    loadConfig();
    readSlots();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [deviceName, beamline]);

  useEffect(() => {
    if (beamline) return undefined;
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
        setSlotMeasuredCurrents(data.slots.map((slot) => slot.current_measured));
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
  }, [deviceName, beamline]);

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
    if (commandsLocked) return;
    try {
      const url = `/api/device/itest/${deviceName}/slot/${slotId}/output`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ state })
      });
      
      if (response.ok) {
        if (!beamline) await fetchSlotData();
      } else {
        throw new Error(`Failed to set output state`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const setSlotCurrent = async (slotId, inputValue) => {
    if (commandsLocked) throw new Error('iTest controls are locked');
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
  const orderedSlots = beamline ? [...new Set([...slotOrder, ...currentTabConfig.slots])] : currentTabConfig.slots;
  const currentSlots = orderedSlots.filter(id => currentTabConfig.slots.includes(id) && (beamline || slotIds.includes(id)));
  const moveSlot = (source, target) => {
    const from = orderedSlots.indexOf(source);
    const to = orderedSlots.indexOf(target);
    if (from < 0 || to < 0 || from === to) return;
    const next = [...orderedSlots];
    next.splice(from, 1);
    next.splice(to, 0, source);
    setSlotOrder(next);
    try { window.localStorage.setItem(orderKey, JSON.stringify(next)); } catch { /* applied in memory */ }
  };
  const endDrag = () => {
    dragging.current = null;
    setDropTarget(null);
  };
  const allCurrentSlotsEnabled =
    currentSlots.length > 0 &&
    currentSlots.every((id) => {
      const idx = slotIds.indexOf(id);
      return idx >= 0 && slotStates[idx] === 1;
    });

  return (
    <div className={`itest-client${compact ? ' is-compact' : ''}${beamline ? ' itest-beamline' : ''}`}>
      <div className="client-header">
        <h2>{beamline ? `iTest · ${activeTab}` : `iTest PSU: ${deviceName}`}</h2>
        {beamline ? <div className="connection-status" role="status">
          {hardwareAvailable ? 'Télémétrie iTest active' : 'Télémétrie iTest indisponible'}
        </div> : <div className="connection-status">
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
        </div>}
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
          className="btn-load-defaults" disabled={readOnly}
          onClick={() => loadTabDefaults(activeTab)}
        >
          Load Defaults
        </button>
        <label className="toggle-all">
          <input 
            type="checkbox"
            checked={allCurrentSlotsEnabled} disabled={readOnly}
            onChange={(e) => toggleTabOutputs(activeTab, e.target.checked)}
          />
          <span>Enable All Slots</span>
        </label>
      </div>}

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
          {!beamline && <button onClick={fetchSlotData}>Retry</button>}
        </div>
      )}

      {/* Slot controls grid */}
      <div className={beamline ? 'sup-line__grid itest-beamline__grid' : 'slots-grid'}>
        {currentSlots.map(slotId => {
          const idx = slotIds.indexOf(slotId);
          const hasReading = !beamline || (hardwareAvailable && idx >= 0);
          const name = (beamline && configuredNames[slotId]) || (hasReading && slotNames[idx]) || `Slot ${slotId}`;
          const state = hasReading ? slotStates[idx] : undefined;
          const setpoint = (hasReading ? slotSetpoints[slotId] : null) ?? (beamline ? null : 0.0);
          const measured = (hasReading ? slotMeasuredCurrents[idx] : null) ?? (beamline ? null : 0.0);
          const limits = (hasReading && slotLimits[slotId]) || { min: -5.0, max: 15.0 };
          const editor = <SlotCurrentControl key={`${deviceName}:${slotId}`} name={name} setpoint={setpoint} limits={limits}
            readOnly={commandsLocked || (beamline && !limits.verified)} beamline={beamline}
            canStep={Number.isFinite(slotSetpoints[slotId]) && slotLimits[slotId]?.verified}
            storageKey={`pyconlyse.itest.current-step.${deviceName.toLowerCase()}.${slotId}`}
            onApply={(value) => handleSlotCurrentChange(slotId, value)} />;
          if (beamline) {
            const outputKnown = state === 0 || state === 1;
            return <section key={slotId} aria-label={name} data-slot-id={slotId}
              className={`sup-line__card itest-beamline__card${dropTarget === slotId ? ' is-drop-target' : ''}`}
              onDragOver={(event) => {
                if (dragging.current === null || dragging.current === slotId) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                setDropTarget(slotId);
              }}
              onDrop={(event) => {
                if (dragging.current === null) return;
                event.preventDefault();
                moveSlot(dragging.current, slotId);
                endDrag();
              }}>
              <div className="sup-line__toolbar">
                <button type="button" aria-label={`${name} · marche / arrêt`} aria-pressed={outputKnown ? state === 1 : undefined}
                  disabled={commandsLocked || !outputKnown} onClick={() => setSlotOutputState(slotId, state === 1 ? 0 : 1)}>M/A</button>
                <div className="sup-line__states">
                  <span className={state === 1 ? 'itest-beamline__output-on' : ''} role="img"
                    aria-label={outputKnown ? state === 1 ? 'Sortie en marche' : 'Sortie à l’arrêt' : 'Sortie inconnue'} />
                </div>
                <button type="button" className="itest-beamline__handle" draggable aria-label={`Déplacer ${name}`}
                  title="Glisser ou utiliser les touches fléchées"
                  onDragStart={(event) => {
                    dragging.current = slotId;
                    event.dataTransfer.setData('text/plain', String(slotId));
                    event.dataTransfer.effectAllowed = 'move';
                  }} onDragEnd={endDrag}
                  onKeyDown={(event) => {
                    const offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -4, ArrowDown: 4 };
                    if (!(event.key in offsets)) return;
                    event.preventDefault();
                    const target = currentSlots[currentSlots.indexOf(slotId) + offsets[event.key]];
                    if (target !== undefined) moveSlot(slotId, target);
                  }}>⠿</button>
              </div>
              <div className="sup-line__range">Slot {slotId}</div>
              <h3 title={name}>{name}</h3>
              <div className="sup-line__readings">
                {[[setpoint, 'Consigne', 'consigne'], [measured, 'Lecture', 'lecture']].map(([value, label, field]) => (
                  <div key={field} className={`sup-line__value sup-line__value--${field}`}>
                    <small>{label}</small>
                    <output aria-label={`${name} · ${label}`}>{Number.isFinite(value) ? value.toFixed(3) : '—'}</output>
                    <span>A</span>
                  </div>
                ))}
              </div>
              {editor}
            </section>;
          }
          
          return (
            <div key={slotId} className="slot-card">
              <div className="slot-header">
                <h4>{name}</h4>
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={state === 1} disabled={readOnly} aria-label={`${name} output`}
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
              
              {editor}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ITestPSUClient;
