// DSStandaMotorsClient.js - Multi-motor Standa web client with config selection
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './DSStandaMotorsClient.css';

// Layout configurations from DS_STANDA_client.py
const MOTOR_CONFIGS = {
  "ELYSE": {
    "selection": [
      "elyse/motorized_devices/de1",
      "manip/V0/F1",
      "elyse/motorized_devices/mme_x",
      "elyse/motorized_devices/mme_y",
      "elyse/motorized_devices/mm1_x",
      "elyse/motorized_devices/mm1_y",
      "elyse/motorized_devices/mm2_x",
      "elyse/motorized_devices/mm2_y",
    ],
    "width": 4,
  },
  "V0": {
    "selection": [
      "manip/V0/mm3_x",
      "manip/V0/mm3_y",
      "manip/V0/mm4_x",
      "manip/V0/mm4_y",
      "manip/V0/dv01",
      "manip/V0/dv02",
      "manip/V0/dv03",
      "manip/V0/dv04",
      "manip/V0/s1",
      "manip/V0/s2",
      "manip/V0/s3",
      "manip/V0/L-2_1",
      "manip/V0/opa_x",
      "manip/V0/opa_y",
      "manip/v0/ts_sc_m",
      "manip/v0/ts_opa_m",
    ],
    "width": 4,
  },
  "V0_short": {
    "selection": ["manip/V0/dv04", "manip/V0/L-2_1"],
    "width": 2
  },
  "alignment": {
    "selection": [
      "elyse/motorized_devices/de1",
      "elyse/motorized_devices/de2",
      "manip/V0/dv01",
      "manip/V0/dv02",
      "elyse/motorized_devices/mm1_x",
      "elyse/motorized_devices/mm1_y",
      "elyse/motorized_devices/mm2_x",
      "elyse/motorized_devices/mm2_y",
      "manip/V0/mm3_x",
      "manip/V0/mm3_y",
      "manip/V0/mm4_x",
      "manip/V0/mm4_y",
      "manip/V0/s1",
      "manip/V0/s2",
      "manip/V0/L-2_1",
      "manip/V0/dv03",
    ],
    "width": 4,
  },
  "OPA": {
    "selection": ["manip/v0/opa_x", "manip/v0/opa_y"],
    "width": 2
  },
  "test": {
    "selection": [
      "elyse/motorized_devices/mm1_x",
      "elyse/motorized_devices/mm1_y",
    ],
    "width": 4,
  },
};

const DSStandaMotorsClient = ({ defaultConfig = "V0_short" }) => {
  const [selectedConfig, setSelectedConfig] = useState(defaultConfig);
  const [motors, setMotors] = useState({});
  const [connected, setConnected] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [relativeSteps, setRelativeSteps] = useState({});
  
  const socketRef = useRef(null);
  const updateTimers = useRef({});

  const currentMotorNames = MOTOR_CONFIGS[selectedConfig]?.selection || [];

  useEffect(() => {
    if (currentMotorNames.length > 0) {
      fetchAllMotorsData();
      initializeWebSocket();
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      // Clear any pending timers
      Object.values(updateTimers.current).forEach(timer => clearTimeout(timer));
    };
  }, [selectedConfig]);

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
      if (data.device && motors[data.device]) {
        setMotors(prev => ({
          ...prev,
          [data.device]: {
            ...prev[data.device],
            position: data.position !== undefined ? data.position : prev[data.device].position,
            state: data.state || prev[data.device].state
          }
        }));
      }
    });

    socketRef.current.on('device_error', (data) => {
      if (data.device && motors[data.device]) {
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

  const fetchAllMotorsData = async () => {
    try {
      setLoading(true);
      const motorsData = {};
      const stepsData = {};
      
      for (const motorName of currentMotorNames) {
        try {
          // Fetch position
          const posResponse = await fetch(`/api/device/${motorName}/attribute/position`, {
            credentials: 'include'
          });
          
          let position = 0;
          let state = 'UNKNOWN';
          let unit = 'mm';
          let limitMin = -100;
          let limitMax = 100;
          let friendlyName = motorName.split('/').pop();
          let presetPositions = [];

          if (posResponse.ok) {
            const posData = await posResponse.json();
            position = posData.value || 0;
          }

          // Fetch state
          try {
            const stateResponse = await fetch(`/api/device/${motorName}/state`, {
              credentials: 'include'
            });
            if (stateResponse.ok) {
              const stateData = await stateResponse.json();
              state = stateData.state || 'UNKNOWN';
            }
          } catch (err) {
            console.warn(`Could not fetch state for ${motorName}`);
          }

          // Fetch properties
          try {
            const propsResponse = await fetch(`/api/device/${motorName}/properties`, {
              credentials: 'include'
            });
            if (propsResponse.ok) {
              const propsData = await propsResponse.json();
              unit = propsData.unit?.[0] || 'mm';
              limitMin = parseFloat(propsData.limit_min?.[0] || -100);
              limitMax = parseFloat(propsData.limit_max?.[0] || 100);
              friendlyName = propsData.friendly_name?.[0] || friendlyName;
              presetPositions = (propsData.preset_pos || []).map(p => parseFloat(p));
            }
          } catch (err) {
            console.warn(`Could not fetch properties for ${motorName}`);
          }

          motorsData[motorName] = {
            name: motorName,
            friendlyName,
            position,
            state,
            unit,
            limitMin,
            limitMax,
            presetPositions
          };

          // Default step size is 1
          stepsData[motorName] = 1;

        } catch (err) {
          console.error(`Error fetching ${motorName}:`, err);
          motorsData[motorName] = {
            name: motorName,
            friendlyName: motorName.split('/').pop(),
            position: 0,
            state: 'FAULT',
            unit: 'mm',
            limitMin: -100,
            limitMax: 100,
            presetPositions: [],
            error: err.message
          };
          stepsData[motorName] = 1;
        }
      }
      
      setMotors(motorsData);
      setRelativeSteps(stepsData);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleMonitoring = () => {
    if (!socketRef.current || !connected) return;

    if (monitoring) {
      currentMotorNames.forEach(motorName => {
        socketRef.current.emit('unsubscribe_device', { device: motorName });
      });
      setMonitoring(false);
    } else {
      currentMotorNames.forEach(motorName => {
        socketRef.current.emit('subscribe_device', { device: motorName });
      });
      setMonitoring(true);
    }
  };

  const moveMotorAbsolute = async (motorName, targetPosition) => {
    try {
      const response = await fetch(`/api/device/${motorName}/command/move_axis_abs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: [targetPosition] })
      });
      
      if (response.ok) {
        // Update local state optimistically
        setMotors(prev => ({
          ...prev,
          [motorName]: {
            ...prev[motorName],
            position: targetPosition
          }
        }));
        setError(null);
      } else {
        throw new Error(`Failed to move motor ${motorName} to ${targetPosition}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const moveMotorRelative = async (motorName, direction) => {
    const motor = motors[motorName];
    if (!motor) return;

    const step = relativeSteps[motorName] || 1;
    const newPosition = motor.position + (step * direction);
    
    // Clamp to limits
    const clampedPosition = Math.max(motor.limitMin, Math.min(motor.limitMax, newPosition));
    
    await moveMotorAbsolute(motorName, clampedPosition);
  };

  const turnMotorOn = async (motorName) => {
    try {
      const response = await fetch(`/api/device/${motorName}/command/turn_on`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: [] })
      });
      
      if (response.ok) {
        setError(null);
      } else {
        throw new Error(`Failed to turn on motor ${motorName}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const stopMotor = async (motorName) => {
    try {
      const response = await fetch(`/api/device/${motorName}/command/stop_movement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: [] })
      });
      
      if (response.ok) {
        setError(null);
      } else {
        throw new Error(`Failed to stop motor ${motorName}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const setRelativeStep = (motorName, step) => {
    setRelativeSteps(prev => ({
      ...prev,
      [motorName]: step
    }));
  };

  const handlePositionInputChange = (motorName, value) => {
    // Update display immediately
    setMotors(prev => ({
      ...prev,
      [motorName]: {
        ...prev[motorName],
        position: parseFloat(value) || 0
      }
    }));

    // Debounce actual movement
    clearTimeout(updateTimers.current[motorName]);
    updateTimers.current[motorName] = setTimeout(() => {
      const numValue = parseFloat(value);
      if (!isNaN(numValue)) {
        moveMotorAbsolute(motorName, numValue);
      }
    }, 800);
  };

  const handlePositionKeyPress = (e, motorName) => {
    if (e.key === 'Enter') {
      clearTimeout(updateTimers.current[motorName]);
      const value = parseFloat(e.target.value);
      if (!isNaN(value)) {
        moveMotorAbsolute(motorName, value);
      }
    }
  };

  const renderMotor = (motorName) => {
    const motor = motors[motorName];
    if (!motor) return null;

    const stateClass = motor.state === 'ON' ? 'on' : 
                      motor.state === 'MOVING' ? 'moving' : 
                      motor.state === 'FAULT' ? 'fault' : 'off';

    return (
      <div key={motorName} className={`motor-card ${stateClass}`}>
        <div className="motor-header">
          <h3>{motor.friendlyName}</h3>
          <div className="motor-state">
            <span className={`state-badge ${stateClass}`}>
              {motor.state}
            </span>
          </div>
        </div>
        
        {motor.error && (
          <div className="motor-error">
            Error: {motor.error}
          </div>
        )}
        
        <div className="motor-position">
          <label>Position:</label>
          <div className="position-display">
            <span className="position-value">{motor.position.toFixed(3)}</span>
            <span className="position-unit">{motor.unit}</span>
          </div>
        </div>

        <div className="motor-limits">
          <small>Limits: {motor.limitMin} to {motor.limitMax} {motor.unit}</small>
        </div>

        <div className="motor-controls">
          <button 
            className="motor-btn move-left"
            onClick={() => moveMotorRelative(motorName, -1)}
            title={`Move -${relativeSteps[motorName]} ${motor.unit}`}
          >
            ◄◄
          </button>
          
          <input
            type="number"
            className="position-input"
            step="0.001"
            min={motor.limitMin}
            max={motor.limitMax}
            value={motor.position.toFixed(3)}
            onChange={(e) => handlePositionInputChange(motorName, e.target.value)}
            onKeyPress={(e) => handlePositionKeyPress(e, motorName)}
          />
          
          <button 
            className="motor-btn move-right"
            onClick={() => moveMotorRelative(motorName, 1)}
            title={`Move +${relativeSteps[motorName]} ${motor.unit}`}
          >
            ►►
          </button>
        </div>

        <div className="step-selector">
          <label>Step size:</label>
          <select 
            value={relativeSteps[motorName] || 1}
            onChange={(e) => setRelativeStep(motorName, parseFloat(e.target.value))}
          >
            <option value={0.1}>0.1 {motor.unit}</option>
            <option value={0.5}>0.5 {motor.unit}</option>
            <option value={1}>1 {motor.unit}</option>
            <option value={2}>2 {motor.unit}</option>
            <option value={5}>5 {motor.unit}</option>
            <option value={10}>10 {motor.unit}</option>
            <option value={20}>20 {motor.unit}</option>
            <option value={50}>50 {motor.unit}</option>
            <option value={100}>100 {motor.unit}</option>
          </select>
        </div>

        {motor.presetPositions.length > 0 && (
          <div className="preset-positions">
            <label>Presets:</label>
            <div className="preset-buttons">
              {motor.presetPositions.map((pos, idx) => (
                <button
                  key={idx}
                  className="preset-btn"
                  onClick={() => moveMotorAbsolute(motorName, pos)}
                  title={`Move to ${pos} ${motor.unit}`}
                >
                  {pos}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="motor-actions">
          <button 
            className="action-btn on"
            onClick={() => turnMotorOn(motorName)}
            title="Turn motor ON"
          >
            ON
          </button>
          <button 
            className="action-btn stop"
            onClick={() => stopMotor(motorName)}
            title="Stop motor movement"
          >
            STOP
          </button>
        </div>
        
        <div className="motor-name-full">
          <small>{motorName}</small>
        </div>
      </div>
    );
  };

  if (loading) {
    return <div className="standa-client loading">Loading Standa Motors...</div>;
  }

  return (
    <div className="standa-client">
      <div className="client-header">
        <h2>Standa Motorized Stages</h2>
        <div className="header-controls">
          <div className="config-selector">
            <label>Configuration:</label>
            <select 
              value={selectedConfig}
              onChange={(e) => setSelectedConfig(e.target.value)}
            >
              {Object.keys(MOTOR_CONFIGS).map(configName => (
                <option key={configName} value={configName}>
                  {configName} ({MOTOR_CONFIGS[configName].selection.length} motors)
                </option>
              ))}
            </select>
          </div>

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
          
          <div className="motor-count">
            <span>{currentMotorNames.length} motors loaded</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
          <button onClick={fetchAllMotorsData}>Retry</button>
        </div>
      )}

      <div className="motors-grid" style={{ gridTemplateColumns: `repeat(${MOTOR_CONFIGS[selectedConfig]?.width || 4}, 1fr)` }}>
        {currentMotorNames.map(motorName => renderMotor(motorName))}
      </div>
      
      <div className="info-section">
        <small>
          • Select a configuration from the dropdown to load different motor sets<br/>
          • Use ◄◄ / ►► buttons for relative movement with selected step size<br/>
          • Type values directly in position input for absolute positioning<br/>
          • Click preset buttons to move to predefined positions<br/>
          • Enable monitoring for real-time position updates<br/>
          • Use STOP button to halt any ongoing movement
        </small>
      </div>
    </div>
  );
};

export default DSStandaMotorsClient;
