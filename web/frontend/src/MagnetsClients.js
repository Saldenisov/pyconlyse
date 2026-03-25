import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ITestPSUClient from './components/ITestPSUClient';
import { resolveDeviceFamily } from './utils/deviceFamily';
import './css/DeviceClients.css';

const MagnetsClients = () => {
  const [availableDevices, setAvailableDevices] = useState([]);
  const [selectedDeviceName, setSelectedDeviceName] = useState('');
  const [manualDeviceName, setManualDeviceName] = useState('');
  const [loadedDeviceName, setLoadedDeviceName] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isItestDevice = (device) => {
    const name = String(device?.name || '').toLowerCase();
    const cls = String(device?.class || '').toLowerCase();
    const server = String(device?.server || '').toLowerCase();
    if (name.startsWith('dserver/')) {
      return false;
    }
    if (resolveDeviceFamily(device) === 'itest_psu') {
      return true;
    }
    const fingerprint = `${name} ${cls} ${server}`;
    return fingerprint.includes('itest') || fingerprint.includes('psu');
  };

  useEffect(() => {
    let cancelled = false;

    const loadItestDevices = async () => {
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
          .filter((device) => isItestDevice(device))
          .map((device) => String(device.name))
          .sort((a, b) => a.localeCompare(b));

        if (!cancelled) {
          setAvailableDevices(names);
          setSelectedDeviceName(names[0] || '');
          setManualDeviceName(names[0] || '');
          setLoadedDeviceName('');
          setError('');
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setAvailableDevices([]);
          setSelectedDeviceName('');
          setManualDeviceName('');
          setLoadedDeviceName('');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadItestDevices();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadSelectedDevice = () => {
    if (!selectedDeviceName) {
      return;
    }
    setLoadedDeviceName(selectedDeviceName);
  };

  const loadManualDevice = () => {
    const trimmed = String(manualDeviceName || '').trim();
    if (!trimmed) {
      return;
    }
    setLoadedDeviceName(trimmed);
  };

  return (
    <div className="device-clients-page">
      <div className="page-header">
        <h1>Magnets Clients</h1>
        <p>Select an iTest power-supply server to control magnet channels</p>
      </div>

      {loading && <p>Loading iTest devices...</p>}
      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      {!loading && !error && availableDevices.length === 0 && (
        <div style={{ marginTop: '12px' }}>
          <p>No magnet/iTest devices found in `/api/devices`.</p>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', marginTop: '8px' }}>
            <input
              type="text"
              placeholder="Manual device name, e.g. ELYSE/pdu/iTest"
              value={manualDeviceName}
              onChange={(event) => setManualDeviceName(event.target.value)}
              style={{ minWidth: '320px' }}
            />
            <button type="button" onClick={loadManualDevice} disabled={!manualDeviceName.trim()}>
              Open Manually
            </button>
          </div>
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
            <h3 style={{ marginTop: 0 }}>Choose iTest Device</h3>
            <div style={{ display: 'grid', gap: '6px', marginBottom: '10px' }}>
              {availableDevices.map((deviceName) => (
                <label key={deviceName} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input
                    type="radio"
                    name="magnets-device"
                    checked={selectedDeviceName === deviceName}
                    onChange={() => setSelectedDeviceName(deviceName)}
                  />
                  <span>{deviceName}</span>
                </label>
              ))}
            </div>
            <button
              type="button"
              onClick={loadSelectedDevice}
              disabled={!selectedDeviceName}
            >
              Load Selected
            </button>
          </div>

          {loadedDeviceName ? (
            <ITestPSUClient deviceName={loadedDeviceName} />
          ) : (
            <p>Select a device and click `Load Selected`.</p>
          )}
        </>
      )}

      {!loading && !error && availableDevices.length === 0 && loadedDeviceName && (
        <ITestPSUClient deviceName={loadedDeviceName} />
      )}
    </div>
  );
};

export default MagnetsClients;
