// ITestPSUClient.js - Specialized client for iTest PSU devices
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './ITestPSUClient.css';

const ITestPSUClient = ({ deviceName }) => {
  const [currentSetpoint, setCurrentSetpoint] = useState(0.0);
  const [measuredCurrent, setMeasuredCurrent] = useState(0.0);
  const [measuredVoltage, setMeasuredVoltage] = useState(0.0);
  const [currentLimits, setCurrentLimits] = useState({ min: -5.0, max: 15.0 });
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedSlot, setSelectedSlot] = useState(1);
  const [availableSlots, setAvailableSlots] = useState([]);
  
  const socketRef = useRef(null);
  const newSetpointRef = useRef();

  useEffect(() => {
    if (deviceName) {
      fetchAvailableSlots();
      initializeWebSocket();
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, [deviceName]);

  useEffect(() => {
    if (deviceName && selectedSlot) {
      fetchCurrentReadings();
    }
  }, [deviceName, selectedSlot]);

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
        if (data.current_setpoint !== undefined) setCurrentSetpoint(data.current_setpoint);
        if (data.measured_current !== undefined) setMeasuredCurrent(data.measured_current);
        if (data.measured_voltage !== undefined) setMeasuredVoltage(data.measured_voltage);
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

  const fetchAvailableSlots = async () => {
    try {
      const response = await fetch(`/api/device/ds_itest_psu/${deviceName}/slots`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        const slotIds = data.available_slot_ids || [];
        setAvailableSlots(slotIds);
        if (slotIds.length > 0 && !slotIds.includes(selectedSlot)) {
          setSelectedSlot(slotIds[0]);
        }
      } else {
        console.warn('Could not fetch available slots, using default slot 1');
        setAvailableSlots([1]);
        setSelectedSlot(1);
      }
    } catch (err) {
      console.warn('Could not fetch available slots:', err);
      setAvailableSlots([1]);
      setSelectedSlot(1);
    }
  };

  const fetchCurrentReadings = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/device/itest/${deviceName}/slot/${selectedSlot}/current`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setCurrentSetpoint(data.current_setpoint || 0.0);
        setMeasuredCurrent(data.measured_current || 0.0);
        setMeasuredVoltage(data.measured_voltage || 0.0);
        if (data.current_limits) {
          setCurrentLimits(data.current_limits);
        }
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

  const handleCurrentAction = async (action, value = null) => {
    try {
      const body = { action };
      if (value !== null) body.value = value;
      
      const response = await fetch(`/api/device/itest/${deviceName}/slot/${selectedSlot}/current`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body)
      });
      
      if (response.ok) {
        const data = await response.json();
        setCurrentSetpoint(data.current_setpoint);
        setError(null);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to execute ${action}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const setCurrentValue = () => {
    const value = parseFloat(newSetpointRef.current.value);
    if (isNaN(value)) {
      setError('Please enter a valid number');
      return;
    }
    
    // Client-side validation
    if (value < currentLimits.min || value > currentLimits.max) {
      setError(`Current value ${value}A is outside limits [${currentLimits.min}, ${currentLimits.max}]A`);
      return;
    }
    
    handleCurrentAction('set', value);
  };

  if (loading) {
    return <div className="itest-client loading">Loading iTest PSU...</div>;
  }

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

      <div className="slot-selection">
        <h3>Slot Selection</h3>
        <div className="slot-selector">
          <label>Active Slot:</label>
          <select 
            value={selectedSlot} 
            onChange={(e) => setSelectedSlot(parseInt(e.target.value))}
            className="slot-dropdown"
          >
            {availableSlots.map(slotId => (
              <option key={slotId} value={slotId}>
                Slot {slotId}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
          <button onClick={fetchCurrentReadings}>Retry</button>
        </div>
      )}

      <div className="measurements-section">
        <h3>Current Measurements - Slot {selectedSlot}</h3>
        <div className="measurements-grid">
          <div className="measurement-item">
            <label>Current Setpoint</label>
            <div className="value-display">
              <span className="value">{currentSetpoint.toFixed(4)}</span>
              <span className="unit">A</span>
            </div>
          </div>
          
          <div className="measurement-item">
            <label>Measured Current</label>
            <div className="value-display">
              <span className="value">{measuredCurrent.toFixed(4)}</span>
              <span className="unit">A</span>
            </div>
          </div>
          
          <div className="measurement-item">
            <label>Measured Voltage</label>
            <div className="value-display">
              <span className="value">{measuredVoltage.toFixed(3)}</span>
              <span className="unit">V</span>
            </div>
          </div>
        </div>
      </div>

      <div className="control-section">
        <h3>Current Control - Slot {selectedSlot}</h3>
        
        <div className="setpoint-control">
          <label>Set Current (A):</label>
          <div className="limits-info">
            <small>Limits: {currentLimits.min}A to {currentLimits.max}A</small>
          </div>
          <div className="input-group">
            <input 
              ref={newSetpointRef}
              type="number" 
              step="0.001" 
              min={currentLimits.min}
              max={currentLimits.max}
              defaultValue={currentSetpoint}
              placeholder={`Enter current value (${currentLimits.min} to ${currentLimits.max}A)`}
            />
            <button onClick={setCurrentValue} className="set-btn">Set</button>
          </div>
        </div>

        <div className="bump-controls">
          <h4>Quick Adjustments</h4>
          <div className="bump-grid">
            <button 
              className="bump-btn coarse dec" 
              onClick={() => handleCurrentAction('dec_coarse')}
            >
              -0.1 A
            </button>
            
            <button 
              className="bump-btn fine dec" 
              onClick={() => handleCurrentAction('dec_fine')}
            >
              -0.01 A
            </button>
            
            <button 
              className="bump-btn fine inc" 
              onClick={() => handleCurrentAction('inc_fine')}
            >
              +0.01 A
            </button>
            
            <button 
              className="bump-btn coarse inc" 
              onClick={() => handleCurrentAction('inc_coarse')}
            >
              +0.1 A
            </button>
          </div>
        </div>
      </div>

      <div className="info-section">
        <small>
          • Use the bump buttons for quick adjustments<br/>
          • Fine adjustments: ±0.01 A<br/>
          • Coarse adjustments: ±0.1 A<br/>
          • Current limits: {currentLimits.min}A to {currentLimits.max}A<br/>
          • Real-time monitoring shows live updates when enabled
        </small>
      </div>
    </div>
  );
};

export default ITestPSUClient;