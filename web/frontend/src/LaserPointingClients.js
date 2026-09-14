import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import LaserPointingController from './components/LaserPointingController';
import { resolveDeviceFamily } from './utils/deviceFamily';
import './css/DeviceClients.css';
import './css/LaserPointingClients.css';

const LaserPointingClients = ({ deviceOverride = null }) => {
  const [availableDevices, setAvailableDevices] = useState(
    Array.isArray(deviceOverride) ? deviceOverride : []
  );
  const [selectedDeviceNames, setSelectedDeviceNames] = useState([]);
  const [loadedDeviceNames, setLoadedDeviceNames] = useState([]);
  const [loading, setLoading] = useState(!Array.isArray(deviceOverride));
  const [error, setError] = useState('');

  useEffect(() => {
    if (Array.isArray(deviceOverride)) return undefined;
    let cancelled = false;

    const loadDevices = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          '/api/devices?probe_state=0&include_dserver=0',
          { credentials: 'include' }
        );
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || `Device list failed (${response.status})`);
        const names = (payload.devices || [])
          .filter((device) => resolveDeviceFamily(device) === 'laser_pointing')
          .filter((device) => !String(device?.name || '').toLowerCase().startsWith('dserver/'))
          .map((device) => String(device.name))
          .sort((a, b) => a.localeCompare(b));
        if (!cancelled) {
          setAvailableDevices(names);
          setSelectedDeviceNames([]);
          setLoadedDeviceNames([]);
          setError('');
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message);
          setAvailableDevices([]);
          setSelectedDeviceNames([]);
          setLoadedDeviceNames([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadDevices();
    return () => { cancelled = true; };
  }, [deviceOverride]);

  const toggleDevice = (deviceName) => {
    setSelectedDeviceNames((current) => {
      if (current.includes(deviceName)) {
        return current.filter((name) => name !== deviceName);
      }
      return [...current, deviceName].sort((a, b) => a.localeCompare(b));
    });
  };

  const selectAll = () => setSelectedDeviceNames(availableDevices);
  const clearSelection = () => setSelectedDeviceNames([]);
  const loadSelectedDevices = () => setLoadedDeviceNames(selectedDeviceNames);

  return (
    <main className="device-clients-page laser-pointing-page">
      <div className="page-header laser-pointing-page-header">
        <h1>Laser Pointing Controllers</h1>
        <p>Select LaserPointing device servers to load their alignment controls</p>
      </div>

      {loading && <p>Discovering LaserPointing device servers…</p>}
      {error && <div className="error-alert"><strong>Error:</strong> {error}</div>}
      {!loading && !error && availableDevices.length === 0 && (
        <div>
          <p>No <code>DS_LaserPointing</code> controllers were found.</p>
          <p>Use the <Link to="/device-clients">generic device browser</Link> to inspect server state.</p>
        </div>
      )}
      {!loading && !error && availableDevices.length > 0 && (
        <>
          <section className="device-load-selector" aria-labelledby="laser-device-selector-heading">
            <h3 id="laser-device-selector-heading">Choose LaserPointing Controllers</h3>
            <div className="device-load-selector-actions">
              <button type="button" onClick={selectAll}>Select All</button>
              <button type="button" onClick={clearSelection}>Clear</button>
              <button
                type="button"
                onClick={loadSelectedDevices}
                disabled={selectedDeviceNames.length === 0}
              >
                Load Selected ({selectedDeviceNames.length})
              </button>
            </div>
            <div className="device-load-selector-list">
              {availableDevices.map((deviceName) => (
                <label key={deviceName}>
                  <input
                    type="checkbox"
                    checked={selectedDeviceNames.includes(deviceName)}
                    onChange={() => toggleDevice(deviceName)}
                  />
                  <span>{deviceName}</span>
                </label>
              ))}
            </div>
          </section>

          {loadedDeviceNames.length > 0 ? (
            loadedDeviceNames.map((deviceName) => (
              <LaserPointingController key={deviceName} deviceName={deviceName} />
            ))
          ) : (
            <p>Select one or more controllers and click <strong>Load Selected</strong>.</p>
          )}
        </>
      )}
    </main>
  );
};

export default LaserPointingClients;
