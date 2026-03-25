// StandaMotorsExample.js - Example page for Standa Motors Client
import React, { useState } from 'react';
import DSStandaMotorsClient from './components/DSStandaMotorsClient';
import './css/Example.css';

const StandaMotorsExample = () => {
  const [selectedConfig, setSelectedConfig] = useState('V0_short');

  const configDescriptions = {
    'ELYSE': 'ELYSE setup with 8 motors (delay lines and mirror mounts)',
    'V0': 'Complete V0 setup with 16 motors (mirror mounts, delays, shutters, etc.)',
    'V0_short': 'Minimal V0 setup for testing (2 motors)',
    'alignment': 'Alignment configuration with 16 selected motors',
    'OPA': 'OPA positioning system (X/Y axes)',
    'test': 'Test configuration with 2 motors'
  };

  return (
    <div className="example-page">
      <div className="page-header">
        <h1>Standa Motorized Stages Control</h1>
        <p className="subtitle">
          Web-based control interface for Standa motorized linear stages
        </p>
      </div>

      <div className="info-panel">
        <h2>Configuration Options</h2>
        <div className="config-list">
          {Object.entries(configDescriptions).map(([config, description]) => (
            <div 
              key={config} 
              className={`config-item ${selectedConfig === config ? 'selected' : ''}`}
              onClick={() => setSelectedConfig(config)}
            >
              <strong>{config}</strong>: {description}
            </div>
          ))}
        </div>
      </div>

      <div className="client-container">
        <DSStandaMotorsClient defaultConfig={selectedConfig} key={selectedConfig} />
      </div>
    </div>
  );
};

export default StandaMotorsExample;
