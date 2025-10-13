// DeviceClients.js - Main page for device clients
import React from 'react';
import DeviceBrowser from './components/DeviceBrowser';
import './css/DeviceClients.css';

const DeviceClients = () => {
  return (
    <div className="device-clients-page">
      <div className="page-header">
        <h1>Device Clients</h1>
        <p>Control and monitor PYCONLYSE devices through web-based clients</p>
      </div>
      
      <DeviceBrowser />
      
      <div className="page-footer">
        <div className="help-section">
          <h4>How to use:</h4>
          <ol>
            <li>Select a device from the browser sidebar</li>
            <li>Choose the appropriate client type (Generic or specialized)</li>
            <li>Use the client interface to control the device</li>
            <li>Enable monitoring for real-time updates</li>
          </ol>
        </div>
      </div>
    </div>
  );
};

export default DeviceClients;