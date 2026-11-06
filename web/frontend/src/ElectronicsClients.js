import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import ElectronicsController from './components/ElectronicsController';
import { resolveDeviceFamily } from './utils/deviceFamily';
import './css/ElectronicsClients.css';

export const isElectronicsDevice = (device) =>
  resolveDeviceFamily(device) === 'electronics' &&
  !String(device?.name || '').toLowerCase().startsWith('dserver/');

const ElectronicsClients = ({ deviceOverride = null }) => {
  const [devices, setDevices] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loaded, setLoaded] = useState([]);
  const [loading, setLoading] = useState(deviceOverride === null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (deviceOverride !== null) {
      setDevices(deviceOverride.map((item) => typeof item === 'string' ? { name: item, class: '' } : item));
      setSelected([]);
      setLoaded([]);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    const discover = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/devices?probe_state=0&include_dserver=0', { credentials: 'include' });
        if (!response.ok) throw new Error(`Device discovery failed (${response.status})`);
        const payload = await response.json();
        const found = (payload.devices || []).filter(isElectronicsDevice)
          .sort((a, b) => String(a.name).localeCompare(String(b.name)));
        if (!cancelled) {
          setDevices(found);
          setSelected([]);
          setLoaded([]);
          setError('');
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    discover();
    return () => { cancelled = true; };
  }, [deviceOverride]);

  const byName = useMemo(() => Object.fromEntries(devices.map((item) => [item.name, item])), [devices]);
  const toggle = (name) => setSelected((current) =>
    current.includes(name) ? current.filter((item) => item !== name) : [...current, name].sort()
  );

  return (
    <main className="electronics-page">
      <header className="electronics-page-header">
        <div>
          <p className="electronics-eyebrow">Equipment / Electronics</p>
          <h1>Electronics Controllers</h1>
          <p>Load only the Tango device servers you need. Startup remains passive.</p>
        </div>
        <Link className="electronics-back-link" to="/equipment">Back to Equipment</Link>
      </header>

      {loading && <p>Discovering electronics device servers…</p>}
      {error && <div className="electronics-alert error"><strong>Error:</strong> {error}</div>}
      {!loading && !error && devices.length === 0 && <div className="electronics-alert">No Keysight or DG645 Tango devices were found.</div>}

      {!loading && !error && devices.length > 0 && (
        <section className="electronics-selector" aria-labelledby="electronics-selector-heading">
          <div className="electronics-selector-heading-row">
            <div>
              <h2 id="electronics-selector-heading">Choose controllers</h2>
              <p>Selection does not connect, initialize, or power hardware.</p>
            </div>
            <div className="electronics-selector-actions">
              <button type="button" onClick={() => setSelected(devices.map((item) => item.name))}>Select all</button>
              <button type="button" onClick={() => setSelected([])}>Clear</button>
              <button type="button" className="primary" disabled={!selected.length} onClick={() => setLoaded(selected)}>
                Load selected ({selected.length})
              </button>
            </div>
          </div>
          <div className="electronics-device-options">
            {devices.map((item) => (
              <label key={item.name} className="electronics-device-option">
                <input type="checkbox" checked={selected.includes(item.name)} onChange={() => toggle(item.name)} />
                <span>
                  <strong>{item.class === 'DS_DG645' ? 'SRS DG645' : 'Keysight 33509B'}</strong>
                  <small>{item.name}</small>
                </span>
              </label>
            ))}
          </div>
        </section>
      )}

      <div className="electronics-controller-list">
        {loaded.map((name) => <ElectronicsController key={name} device={byName[name] || { name }} />)}
      </div>
    </main>
  );
};

export default ElectronicsClients;
