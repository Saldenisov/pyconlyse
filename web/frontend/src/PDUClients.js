import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import DSNetioPDUClient from './components/DSNetioPDUClient';
import { resolveDeviceFamily } from './utils/deviceFamily';
import './css/DeviceClients.css';

const PDUClients = () => {
  const [availableDevices, setAvailableDevices] = useState([]);
  const [selectedDeviceNames, setSelectedDeviceNames] = useState([]);
  const [loadedDeviceNames, setLoadedDeviceNames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isNetioPduDevice = (device) => {
    const fingerprint = `${device?.name || ''} ${device?.class || ''} ${device?.server || ''}`.toLowerCase();
    if (fingerprint.includes('itest') || fingerprint.includes('psu')) {
      return false;
    }
    if (resolveDeviceFamily(device) !== 'netio') {
      return false;
    }
    return !String(device?.name || '').toLowerCase().startsWith('dserver/');
  };

  useEffect(() => {
    let cancelled = false;

    const loadNetioDevices = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/devices?probe_state=0&include_dserver=0', {
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error(`Device list failed (${response.status})`);
        }

        const payload = await response.json();
        const names = (payload.devices || [])
          .filter((device) => isNetioPduDevice(device))
          .map((device) => String(device.name))
          .sort((a, b) => a.localeCompare(b));

        if (!cancelled) {
          setAvailableDevices(names);
          setSelectedDeviceNames([]);
          setLoadedDeviceNames([]);
          setError('');
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setAvailableDevices([]);
          setSelectedDeviceNames([]);
          setLoadedDeviceNames([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadNetioDevices();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleDevice = (deviceName) => {
    setSelectedDeviceNames((current) => {
      if (current.includes(deviceName)) {
        return current.filter((name) => name !== deviceName);
      }
      return [...current, deviceName].sort((a, b) => a.localeCompare(b));
    });
  };

  const selectAll = () => {
    setSelectedDeviceNames(availableDevices);
  };

  const clearSelection = () => {
    setSelectedDeviceNames([]);
  };

  const loadSelectedDevices = () => {
    setLoadedDeviceNames(selectedDeviceNames);
  };

  return (
    <div className="device-clients-page">
      <div className="page-header">
        <h1>PDU Clients</h1>
        <p>Select NETIO devices to load their output controls</p>
      </div>

      {loading && <p>Loading NETIO devices...</p>}
      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      {!loading && !error && availableDevices.length === 0 && (
        <div style={{ marginTop: '12px' }}>
          <p>No `DS_Netio_pdu` devices found in `/api/devices`.</p>
          <p>
            You can still use the generic browser: <Link to="/device-clients">Device Clients</Link>
          </p>
        </div>
      )}

      {!loading && !error && availableDevices.length > 0 && (
        <>
          <div
            style={{
              border: '1px solid #d0d5dd',
              borderRadius: '8px',
              padding: '12px',
              marginBottom: '14px',
            }}
          >
            <h3 style={{ marginTop: 0 }}>Choose PDU Devices</h3>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
              <button type="button" onClick={selectAll}>
                Select All
              </button>
              <button type="button" onClick={clearSelection}>
                Clear
              </button>
              <button
                type="button"
                onClick={loadSelectedDevices}
                disabled={selectedDeviceNames.length === 0}
              >
                Load Selected ({selectedDeviceNames.length})
              </button>
            </div>
            <div style={{ display: 'grid', gap: '6px' }}>
              {availableDevices.map((deviceName) => (
                <label key={deviceName} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={selectedDeviceNames.includes(deviceName)}
                    onChange={() => toggleDevice(deviceName)}
                  />
                  <span>{deviceName}</span>
                </label>
              ))}
            </div>
          </div>

          {loadedDeviceNames.length > 0 ? (
            <DSNetioPDUClient deviceNames={loadedDeviceNames} />
          ) : (
            <p>Select one or more devices and click `Load Selected`.</p>
          )}
        </>
      )}
    </div>
  );
};

export default PDUClients;
