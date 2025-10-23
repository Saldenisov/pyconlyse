// DSItestPSUClient.js - Multi-slot DS iTest PSU web client
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './DSItestPSUClient.css';

const DSItestPSUClient = ({ deviceName }) => {
  const [slots, setSlots] = useState([]);
  const [slotCount, setSlotCount] = useState(0);
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [globalStep, setGlobalStep] = useState(0.01);
  
  const socketRef = useRef(null);
  const inputRefs = useRef({});

  useEffect(() => {
    if (deviceName) {
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
      if (data.device === deviceName && data.slots) {
        setSlots(data.slots);
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

  const fetchSlotData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/device/ds_itest_psu/${deviceName}/slots`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setSlots(data.slots || []);
        setSlotCount(data.slot_count || 0);
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

  const setSlotCurrent = async (slotId, currentValue) => {
    try {
      const response = await fetch(`/api/device/ds_itest_psu/${deviceName}/slot/${slotId}/current`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ current: currentValue })
      });
      
      if (response.ok) {
        const data = await response.json();
        // Update local state
        setSlots(prevSlots => 
          prevSlots.map(slot => 
            slot.id === slotId 
              ? { ...slot, current_setpoint: data.current_setpoint }
              : slot
          )
        );
        setError(null);
      } else {
        throw new Error(`Failed to set current for slot ${slotId}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const setSlotState = async (slotId, enabled) => {
    try {
      const response = await fetch(`/api/device/ds_itest_psu/${deviceName}/slot/${slotId}/state`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ enabled })
      });
      
      if (response.ok) {
        const data = await response.json();
        // Update local state
        setSlots(prevSlots => 
          prevSlots.map(slot => 
            slot.id === slotId 
              ? { ...slot, state: data.state }
              : slot
          )
        );
        setError(null);
      } else {
        throw new Error(`Failed to set state for slot ${slotId}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const nudgeSlot = (slotId, direction) => {
    const slot = slots.find(s => s.id === slotId);
    if (!slot) return;
    
    const newValue = slot.current_setpoint + (direction * globalStep);
    // Clamp to reasonable range (-50A to +50A)
    const clampedValue = Math.max(-50, Math.min(50, newValue));
    
    setSlotCurrent(slotId, clampedValue);
  };

  const handleInputKeyPress = (e, slotId) => {
    if (e.key === 'Enter') {
      const value = parseFloat(e.target.value);
      if (!isNaN(value)) {
        setSlotCurrent(slotId, value);
      }
    }
  };

  const handleInputChange = (e, slotId) => {
    const value = parseFloat(e.target.value);
    if (!isNaN(value) && e.target.value !== '') {
      // Real-time update (debounced)
      clearTimeout(inputRefs.current[slotId]);
      inputRefs.current[slotId] = setTimeout(() => {
        setSlotCurrent(slotId, value);
      }, 500);
    }
  };

  const renderSlot = (slot) => {
    return (
      <div key={slot.id} className="slot-control">
        <div className="slot-header">
          <h4>{slot.name} (ID: {slot.id})</h4>
          <label className="slot-toggle">
            <input
              type="checkbox"
              checked={slot.state}
              onChange={(e) => setSlotState(slot.id, e.target.checked)}
            />
            <span className="toggle-switch"></span>
            ON
          </label>
        </div>
        
        <div className="slot-measurements">
          <div className="measurement">
            <label>Measured</label>
            <span className="value">{slot.current_measured.toFixed(3)} A</span>
          </div>
          <div className="measurement">
            <label>Setpoint</label>
            <span className="value">{slot.current_setpoint.toFixed(3)} A</span>
          </div>
        </div>
        
        <div className="slot-controls">
          <button 
            className="nudge-btn dec coarse"
            onClick={() => nudgeSlot(slot.id, -10)}
            title={`-${(globalStep * 10).toFixed(3)} A`}
          >
            --
          </button>
          <button 
            className="nudge-btn dec"
            onClick={() => nudgeSlot(slot.id, -1)}
            title={`-${globalStep.toFixed(3)} A`}
          >
            -
          </button>
          
          <input
            type="number"
            className="current-input"
            step="0.001"
            min="-50"
            max="50"
            value={slot.current_setpoint.toFixed(3)}
            onChange={(e) => handleInputChange(e, slot.id)}
            onKeyPress={(e) => handleInputKeyPress(e, slot.id)}
            placeholder="Current (A)"
          />
          
          <button 
            className="nudge-btn inc"
            onClick={() => nudgeSlot(slot.id, 1)}
            title={`+${globalStep.toFixed(3)} A`}
          >
            +
          </button>
          <button 
            className="nudge-btn inc coarse"
            onClick={() => nudgeSlot(slot.id, 10)}
            title={`+${(globalStep * 10).toFixed(3)} A`}
          >
            ++
          </button>
        </div>
      </div>
    );
  };

  if (loading) {
    return <div className="ds-itest-client loading">Loading DS iTest PSU...</div>;
  }

  return (
    <div className="ds-itest-client">
      <div className="client-header">
        <h2>DS iTest PSU: {deviceName}</h2>
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
          
          <div className="step-control">
            <label>Step:</label>
            <select 
              value={globalStep} 
              onChange={(e) => setGlobalStep(parseFloat(e.target.value))}
            >
              <option value={0.001}>0.001 A</option>
              <option value={0.01}>0.010 A</option>
              <option value={0.1}>0.100 A</option>
              <option value={1.0}>1.000 A</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
          <button onClick={fetchSlotData}>Retry</button>
        </div>
      )}

      <div className="slots-grid">
        {slots.map(slot => renderSlot(slot))}
      </div>
      
      <div className="info-section">
        <small>
          • Click +/- buttons for step adjustments ({globalStep.toFixed(3)} A)<br/>
          • Click ++/-- for 10x step adjustments ({(globalStep * 10).toFixed(3)} A)<br/>
          • Type values directly in input fields (supports negative values)<br/>
          • Toggle switches control output state for each slot<br/>
          • Real-time monitoring shows live updates when enabled
        </small>
      </div>
    </div>
  );
};

export default DSItestPSUClient;