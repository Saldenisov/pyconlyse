import React, { useEffect, useState } from 'react';

const Dashboard = () => {
  const [summary, setSummary] = useState({
    tangoDbUp: null,
    starterCount: 0,
    healthyStarters: 0,
    deviceCount: 0,
    availableDevices: 0,
  });
  const [error, setError] = useState('');

  useEffect(() => {
    let disposed = false;

    const loadSummary = async () => {
      try {
        const [tangoResponse, devicesResponse] = await Promise.all([
          fetch('/api/tango_status'),
          fetch('/api/devices'),
        ]);

        if (!tangoResponse.ok) {
          throw new Error(`Tango status failed (${tangoResponse.status})`);
        }
        if (!devicesResponse.ok) {
          throw new Error(`Device list failed (${devicesResponse.status})`);
        }

        const tangoData = await tangoResponse.json();
        const devicesData = await devicesResponse.json();

        const starters = tangoData.tango_statuses || [];
        const devices = devicesData.devices || [];
        const healthyStarters = starters.filter((starter) =>
          ['ON', 'MOVING', 'STANDBY'].includes(String(starter[2] || ''))
        ).length;
        const availableDevices = devices.filter((device) => device.available).length;

        if (!disposed) {
          setSummary({
            tangoDbUp: Boolean(tangoData.mysql_status),
            starterCount: starters.length,
            healthyStarters,
            deviceCount: devices.length,
            availableDevices,
          });
          setError('');
        }
      } catch (err) {
        if (!disposed) {
          setError(err.message);
        }
      }
    };

    loadSummary();
    const intervalId = setInterval(loadSummary, 5000);

    return () => {
      disposed = true;
      clearInterval(intervalId);
    };
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Runtime summary of Tango availability and exported devices.</p>
      {error && (
        <div className="error-alert">
          <strong>Dashboard error:</strong> {error}
        </div>
      )}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginTop: '24px',
        }}
      >
        <div className="dashboard-card">
          <h3>Tango DB</h3>
          <p>{summary.tangoDbUp === null ? 'Loading...' : summary.tangoDbUp ? 'Online' : 'Offline'}</p>
        </div>
        <div className="dashboard-card">
          <h3>Starter Devices</h3>
          <p>{summary.healthyStarters} / {summary.starterCount} healthy</p>
        </div>
        <div className="dashboard-card">
          <h3>Exported Devices</h3>
          <p>{summary.availableDevices} / {summary.deviceCount} reachable</p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
