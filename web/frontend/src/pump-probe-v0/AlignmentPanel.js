import React, { useEffect, useState } from 'react';
import ITestPSUClient from '../components/ITestPSUClient';
import { resolveDeviceFamily } from '../utils/deviceFamily';

export default function AlignmentPanel({ children, delayControl }) {
  const [devices, setDevices] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch('/api/devices?probe_state=0&include_dserver=0', {
          signal: controller.signal, credentials: 'include',
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Unable to load iTest devices');
        const names = [...new Set((result.devices || [])
          .filter(device => !String(device.name).startsWith('dserver/')
            && resolveDeviceFamily(device) === 'itest_psu')
          .map(device => device.name))];
        if (!controller.signal.aborted) setDevices(names);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, []);

  return <section className="pp-alignment" aria-label="V0 Alignment">
    <div className="pp-alignment-layout">
      <div className="pp-alignment-controls">
        {delayControl}
        <div className="pp-alignment-magnets">
          <h2 className="pp-alignment-heading">iTest · V0</h2>
          {loading && <p role="status">Loading V0 iTest channels…</p>}
          {error && <p role="alert">{error}</p>}
          {!loading && !error && !devices.length && <p>No iTest device is registered.</p>}
          {devices.map(name => <ITestPSUClient key={name} deviceName={name} fixedTab="V0" compact />)}
        </div>
      </div>
      <div className="pp-alignment-monitor">{children}</div>
    </div>
  </section>;
}
