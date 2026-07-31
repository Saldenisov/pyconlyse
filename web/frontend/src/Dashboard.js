import React, { useEffect, useState } from 'react';
import {
  DEVICE_FAMILY_DEFINITIONS,
  normalizeDeviceFamilyText,
  resolveDeviceFamily,
} from './utils/deviceFamily';
import DashboardDiagnosticsModal from './DashboardDiagnosticsModal';

const cardStyle = {
  border: '1px solid #d8e0ea',
  borderRadius: '10px',
  padding: '16px',
  background: '#ffffff',
  boxShadow: '0 2px 8px rgba(15, 23, 42, 0.06)',
};

const sectionStyle = {
  ...cardStyle,
  marginTop: '24px',
};

const badgeStyle = (ok) => ({
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: '999px',
  fontSize: '0.8rem',
  fontWeight: 600,
  background: ok ? '#dff6e5' : '#fde6e7',
  color: ok ? '#166534' : '#b42318',
});

const buildCoverage = (deviceList) => {
  const families = new Map(
    DEVICE_FAMILY_DEFINITIONS.map((family) => [
      family.key,
      {
        ...family,
        totalDevices: 0,
        reachableDevices: 0,
        servers: new Set(),
      },
    ])
  );
  const serverMap = new Map();

  for (const device of deviceList || []) {
    const familyKey = resolveDeviceFamily(device);
    const family = families.get(familyKey) || families.get('generic');
    const serverName = String(device?.server || 'unknown');
    const reachable = Boolean(device?.available);

    family.totalDevices += 1;
    family.reachableDevices += reachable ? 1 : 0;
    family.servers.add(serverName);

    if (!serverMap.has(serverName)) {
      serverMap.set(serverName, {
        name: serverName,
        totalDevices: 0,
        reachableDevices: 0,
        families: new Set(),
      });
    }

    const serverEntry = serverMap.get(serverName);
    serverEntry.totalDevices += 1;
    serverEntry.reachableDevices += reachable ? 1 : 0;
    serverEntry.families.add(family.label);
  }

  const familySummary = Array.from(families.values())
    .filter((family) => family.totalDevices > 0)
    .map((family) => ({
      ...family,
      serverCount: family.servers.size,
      availabilityPercent: Math.round((family.reachableDevices / family.totalDevices) * 100),
    }))
    .sort((a, b) => b.totalDevices - a.totalDevices || a.label.localeCompare(b.label));

  const serverSummary = Array.from(serverMap.values())
    .map((server) => ({
      ...server,
      families: Array.from(server.families).sort(),
      availabilityPercent: Math.round((server.reachableDevices / server.totalDevices) * 100),
    }))
    .sort((a, b) => {
      if (a.reachableDevices !== b.reachableDevices) {
        return a.reachableDevices - b.reachableDevices;
      }
      return a.name.localeCompare(b.name);
    });

  return { familySummary, serverSummary };
};

const sortDevicesByAvailability = (deviceList) =>
  [...deviceList].sort((a, b) => {
    if (Boolean(a.available) !== Boolean(b.available)) {
      return a.available ? 1 : -1;
    }
    return String(a.name || '').localeCompare(String(b.name || ''));
  });

const Dashboard = () => {
  const [summary, setSummary] = useState({
    tangoDbUp: null,
    tangoHost: '',
    starterCount: 0,
    healthyStarters: 0,
    deviceCount: 0,
    availableDevices: 0,
  });
  const [starters, setStarters] = useState([]);
  const [devices, setDevices] = useState([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [deviceSnapshotAge, setDeviceSnapshotAge] = useState(null);
  const [deviceSnapshotRefreshing, setDeviceSnapshotRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [serverActionInProgress, setServerActionInProgress] = useState('');
  const [contextMenu, setContextMenu] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState('');
  const [serverFilter, setServerFilter] = useState('');
  const coverage = buildCoverage(devices);
  const normalizedServerFilter = normalizeDeviceFamilyText(serverFilter).trim();
  const filteredServerSummary = coverage.serverSummary.filter((server) => {
    if (!normalizedServerFilter) {
      return true;
    }
    const nameMatch = normalizeDeviceFamilyText(server.name).includes(normalizedServerFilter);
    const familyMatch = server.families.some((family) =>
      normalizeDeviceFamilyText(family).includes(normalizedServerFilter)
    );
    return nameMatch || familyMatch;
  });

  useEffect(() => {
    const closeMenu = () => setContextMenu(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  useEffect(() => {
    let disposed = false;
    let devicesRequestInFlight = false;

    const loadTangoStatus = async () => {
      try {
        const tangoResponse = await fetch('/api/tango_status');

        if (!tangoResponse.ok) {
          throw new Error(`Tango status failed (${tangoResponse.status})`);
        }

        const tangoData = await tangoResponse.json();
        const starterList = tangoData.starters || [];
        const healthyStarters = starterList.filter((starter) => starter.healthy).length;

        if (!disposed) {
          setSummary((currentSummary) => ({
            ...currentSummary,
            tangoDbUp: Boolean(tangoData.mysql_status),
            tangoHost: String(tangoData.tango_host || ''),
            starterCount: starterList.length,
            healthyStarters,
          }));
          setStarters(starterList);
          setError('');
        }
      } catch (err) {
        if (!disposed) {
          setError(err.message);
        }
      }
    };

    const loadDevices = async () => {
      if (devicesRequestInFlight) {
        return;
      }

      devicesRequestInFlight = true;
      if (!disposed) {
        setDevicesLoading(true);
      }

      try {
        const devicesResponse = await fetch(
          '/api/devices?probe_state=1&include_dserver=1&include_admin=1&stale_ok=1'
        );
        if (!devicesResponse.ok) {
          throw new Error(`Device list failed (${devicesResponse.status})`);
        }

        const devicesData = await devicesResponse.json();
        const deviceList = devicesData.devices || [];
        const availableDevices = deviceList.filter((device) => device.available).length;

        if (!disposed) {
          setSummary((currentSummary) => ({
            ...currentSummary,
            deviceCount: deviceList.length,
            availableDevices,
          }));
          setDevices(sortDevicesByAvailability(deviceList));
          setDeviceSnapshotAge(
            Number.isFinite(Number(devicesData.snapshot_age_s))
              ? Number(devicesData.snapshot_age_s)
              : null
          );
          setDeviceSnapshotRefreshing(Boolean(devicesData.refreshing));
          setError('');
        }
      } catch (err) {
        if (!disposed) {
          setError(err.message);
        }
      } finally {
        devicesRequestInFlight = false;
        if (!disposed) {
          setDevicesLoading(false);
        }
      }
    };

    loadTangoStatus();
    loadDevices();
    const tangoIntervalId = setInterval(loadTangoStatus, 5000);
    const devicesIntervalId = setInterval(loadDevices, 5000);

    return () => {
      disposed = true;
      clearInterval(tangoIntervalId);
      clearInterval(devicesIntervalId);
    };
  }, []);

  const runServerAction = async (device, action) => {
    setContextMenu(null);
    setActionMessage('');

    if (!device.server) {
      setError(`No server name is available for ${device.name}`);
      return;
    }

    const serverName = String(device.server);
    setServerActionInProgress(serverName);

    try {
      const response = await fetch('/api/server/control', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action,
          server_name: device.server,
          device_name: device.name,
        }),
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Server action failed (${response.status})`);
      }

      setActionMessage(
        `${action} executed for ${payload.server_name} via ${payload.starter}`
      );

      const [tangoResponse, devicesResponse] = await Promise.all([
        fetch('/api/tango_status'),
        fetch('/api/devices?probe_state=1&include_dserver=1&include_admin=1&stale_ok=1'),
      ]);
      if (tangoResponse.ok && devicesResponse.ok) {
        const tangoData = await tangoResponse.json();
        const devicesData = await devicesResponse.json();
        const starterList = tangoData.starters || [];
        const deviceList = devicesData.devices || [];
        const healthyStarters = starterList.filter((starter) => starter.healthy).length;
        const availableDevices = deviceList.filter((entry) => entry.available).length;
        const sortedDevices = sortDevicesByAvailability(deviceList);

        setSummary({
          tangoDbUp: Boolean(tangoData.mysql_status),
          tangoHost: String(tangoData.tango_host || ''),
          starterCount: starterList.length,
          healthyStarters,
          deviceCount: deviceList.length,
          availableDevices,
        });
        setStarters(starterList);
        setDevices(sortedDevices);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setServerActionInProgress('');
    }
  };

  const openDiagnostics = async (device) => {
    setContextMenu(null);
    setDiagnostics(null);
    setDiagnosticsError('');
    setDiagnosticsLoading(true);

    try {
      if (!device.server) {
        throw new Error(`No server name is available for ${device.name}`);
      }
      const response = await fetch(
        `/api/server/${encodeURIComponent(device.server)}/diagnostics?device_name=${encodeURIComponent(device.name)}`
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Diagnostics failed (${response.status})`);
      }
      setDiagnostics(payload);
    } catch (err) {
      setDiagnosticsError(err.message);
    } finally {
      setDiagnosticsLoading(false);
    }
  };

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Live overview of the current Tango connection, starter hosts, and exported devices.</p>
      {error && (
        <div className="error-alert">
          <strong>Dashboard error:</strong> {error}
        </div>
      )}
      {actionMessage && (
        <div
          style={{
            marginTop: '16px',
            padding: '12px',
            borderRadius: '8px',
            background: '#e7f6ec',
            color: '#166534',
            border: '1px solid #ccebd6',
          }}
        >
          {actionMessage}
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
        <div style={cardStyle}>
          <h3>Tango DB</h3>
          <p>{summary.tangoDbUp === null ? 'Loading...' : summary.tangoDbUp ? 'Online' : 'Offline'}</p>
          <p style={{ margin: 0, color: '#475467' }}>
            {summary.tangoHost || 'TANGO_HOST not reported'}
          </p>
        </div>
        <div style={cardStyle}>
          <h3>Starter Hosts</h3>
          <p>{summary.healthyStarters} / {summary.starterCount} healthy</p>
        </div>
        <div style={cardStyle}>
          <h3>Exported Devices</h3>
          <p>
            {devicesLoading && summary.deviceCount === 0
              ? 'Checking devices...'
              : `${summary.availableDevices} / ${summary.deviceCount} reachable`}
          </p>
          {deviceSnapshotAge !== null && (
            <p style={{ margin: 0, color: '#667085', fontSize: '0.85rem' }}>
              Snapshot: {deviceSnapshotAge.toFixed(0)} s ago
              {deviceSnapshotRefreshing ? ', updating' : ''}
            </p>
          )}
        </div>
      </div>

      <div style={sectionStyle}>
        <h2 style={{ marginTop: 0 }}>Controllable Server Coverage</h2>
        <p style={{ marginTop: 0, color: '#475467' }}>
          Coverage is derived from exported devices and grouped by web client capabilities.
        </p>
        {coverage.familySummary.length === 0 ? (
          <p>No control families detected yet.</p>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
            }}
          >
            {coverage.familySummary.map((family) => (
              <div
                key={family.key}
                style={{
                  border: '1px solid #e4e7ec',
                  borderRadius: '8px',
                  padding: '12px',
                  background: '#fafafa',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                  <strong>{family.label}</strong>
                  <span style={badgeStyle(family.reachableDevices === family.totalDevices)}>
                    {family.availabilityPercent}%
                  </span>
                </div>
                <div style={{ marginTop: '8px', color: '#475467', fontSize: '0.9rem' }}>
                  Devices: {family.reachableDevices} / {family.totalDevices}
                </div>
                <div style={{ marginTop: '4px', color: '#667085', fontSize: '0.85rem' }}>
                  Servers: {family.serverCount}
                </div>
              </div>
            ))}
          </div>
        )}
        <h3 style={{ marginTop: '18px', marginBottom: '10px' }}>Detected Tango Servers</h3>
        <div style={{ marginBottom: '10px' }}>
          <input
            type="text"
            value={serverFilter}
            onChange={(event) => setServerFilter(event.target.value)}
            placeholder="Filter by server name or family..."
            style={{
              width: '100%',
              maxWidth: '440px',
              border: '1px solid #d0d5dd',
              borderRadius: '8px',
              padding: '8px 10px',
              fontSize: '0.9rem',
            }}
          />
        </div>
        {coverage.serverSummary.length === 0 ? (
          <p>No servers detected yet.</p>
        ) : filteredServerSummary.length === 0 ? (
          <p>No servers match the current filter.</p>
        ) : (
          <div style={{ display: 'grid', gap: '10px', maxHeight: '280px', overflowY: 'auto' }}>
            {filteredServerSummary.map((server) => (
              <div
                key={server.name}
                style={{
                  border: '1px solid #e4e7ec',
                  borderRadius: '8px',
                  padding: '10px',
                  background: server.reachableDevices === server.totalDevices ? '#ffffff' : '#fff7f7',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                  <strong style={{ wordBreak: 'break-word' }}>{server.name}</strong>
                  <span style={badgeStyle(server.reachableDevices === server.totalDevices)}>
                    {server.reachableDevices}/{server.totalDevices}
                  </span>
                </div>
                <div style={{ marginTop: '6px', color: '#667085', fontSize: '0.85rem' }}>
                  Families: {server.families.join(', ')}
                </div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                  <button
                    type="button"
                    onClick={() =>
                      runServerAction({ name: server.name, server: server.name }, 'start')
                    }
                    disabled={serverActionInProgress === server.name}
                    style={{ padding: '6px 10px', cursor: 'pointer' }}
                  >
                    {serverActionInProgress === server.name ? 'Working...' : 'Start'}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      runServerAction({ name: server.name, server: server.name }, 'restart')
                    }
                    disabled={serverActionInProgress === server.name}
                    style={{ padding: '6px 10px', cursor: 'pointer' }}
                  >
                    Restart
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={sectionStyle}>
        <h2 style={{ marginTop: 0 }}>Starter Hosts</h2>
        {starters.length === 0 ? (
          <p>No starter devices reported.</p>
        ) : (
          <div style={{ display: 'grid', gap: '12px' }}>
            {starters.map((starter) => (
              <div
                key={starter.name}
                style={{
                  border: '1px solid #e4e7ec',
                  borderRadius: '8px',
                  padding: '12px',
                  background: '#fafafa',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '12px',
                    alignItems: 'center',
                  }}
                >
                  <strong>{starter.host || starter.name}</strong>
                  <span style={badgeStyle(Boolean(starter.healthy))}>{starter.state}</span>
                </div>
                <div style={{ marginTop: '6px', color: '#475467', fontSize: '0.9rem' }}>
                  {starter.name}
                </div>
                <div style={{ marginTop: '4px', color: '#667085', fontSize: '0.85rem' }}>
                  Downtime: {Number(starter.downtime_seconds || 0).toFixed(1)} s
                </div>
                {starter.stopped_servers && starter.stopped_servers.length > 0 && (
                  <div style={{ marginTop: '8px', color: '#b42318', fontSize: '0.85rem' }}>
                    Stopped: {starter.stopped_servers.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={sectionStyle}>
        <h2 style={{ marginTop: 0 }}>Exported Devices</h2>
        <div style={{ marginBottom: '12px', color: '#475467' }}>
          Unreachable devices are shown first, then reachable devices.
        </div>
        {devices.length === 0 ? (
          <p>No exported devices returned by Tango.</p>
        ) : (
          <div
            style={{
              display: 'grid',
              gap: '10px',
              maxHeight: '520px',
              overflowY: 'auto',
              paddingRight: '4px',
            }}
          >
            {devices.map((device) => (
              <div
                key={device.name}
                onContextMenu={(event) => {
                  event.preventDefault();
                  setContextMenu({
                    x: event.clientX,
                    y: event.clientY,
                    device,
                  });
                }}
                style={{
                  border: '1px solid #e4e7ec',
                  borderRadius: '8px',
                  padding: '12px',
                  background: device.available ? '#ffffff' : '#fff7f7',
                  cursor: 'context-menu',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '12px',
                    alignItems: 'center',
                  }}
                >
                  <strong style={{ wordBreak: 'break-word' }}>{device.name}</strong>
                  <span style={badgeStyle(Boolean(device.available))}>
                    {device.available ? 'TANGO REACHABLE' : 'TANGO UNREACHABLE'}
                  </span>
                </div>
                <div style={{ marginTop: '6px', color: '#475467', fontSize: '0.9rem' }}>
                  Class: {device.class || 'unknown'}
                </div>
                <div
                  style={{
                    marginTop: '4px',
                    color: '#667085',
                    fontSize: '0.85rem',
                    wordBreak: 'break-word',
                  }}
                >
                  Server: {device.server || 'unknown'}
                </div>
                <div style={{ marginTop: '4px', color: '#667085', fontSize: '0.85rem' }}>
                  Tango state: {device.available ? (device.state || 'UNKNOWN') : 'unavailable'}
                </div>
                <div style={{ marginTop: '6px', color: '#667085', fontSize: '0.8rem' }}>
                  Right-click for hardware and server diagnostics
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            zIndex: 1000,
            minWidth: '180px',
            background: '#ffffff',
            border: '1px solid #d0d5dd',
            borderRadius: '10px',
            boxShadow: '0 12px 32px rgba(15, 23, 42, 0.18)',
            padding: '8px',
          }}
          onClick={(event) => event.stopPropagation()}
        >
          <div
            style={{
              padding: '8px',
              fontSize: '0.8rem',
              color: '#475467',
              borderBottom: '1px solid #eaecf0',
              marginBottom: '6px',
              wordBreak: 'break-word',
            }}
          >
            {contextMenu.device.name}
          </div>
          <button
            type="button"
            onClick={() => openDiagnostics(contextMenu.device)}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '8px 10px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            View Status and Logs
          </button>
          <button
            type="button"
            onClick={() => runServerAction(contextMenu.device, 'start')}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '8px 10px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            Start Server
          </button>
          <button
            type="button"
            onClick={() => runServerAction(contextMenu.device, 'restart')}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '8px 10px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            Restart Server
          </button>
          <button
            type="button"
            onClick={() => runServerAction(contextMenu.device, 'hard_kill')}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '8px 10px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: '#b42318',
            }}
          >
            Hard Kill Server
          </button>
        </div>
      )}
      {(diagnostics || diagnosticsLoading || diagnosticsError) && (
        <DashboardDiagnosticsModal
          diagnostics={diagnostics}
          loading={diagnosticsLoading}
          error={diagnosticsError}
          onClose={() => {
            setDiagnostics(null);
            setDiagnosticsLoading(false);
            setDiagnosticsError('');
          }}
        />
      )}
    </div>
  );
};

export default Dashboard;
