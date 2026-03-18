import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import './css/DeviceClients.css';
import './css/VacuumClients.css';

const MAX_POINTS_PER_CHANNEL = 4000;

const VacuumClients = () => {
  const plotRef = useRef(null);
  const [devices, setDevices] = useState([]);
  const [selectedDeviceName, setSelectedDeviceName] = useState('');
  const [loadedDeviceName, setLoadedDeviceName] = useState('');
  const [series, setSeries] = useState({});
  const [latestByChannel, setLatestByChannel] = useState({});
  const [sampleCount, setSampleCount] = useState(0);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshSec, setRefreshSec] = useState(2.0);
  const [windowMinutes, setWindowMinutes] = useState(30);
  const [visibleChannels, setVisibleChannels] = useState({});

  const channelNames = useMemo(
    () => Object.keys(series).sort((a, b) => a.localeCompare(b)),
    [series]
  );

  const shownChannels = useMemo(
    () => channelNames.filter((channel) => visibleChannels[channel] !== false),
    [channelNames, visibleChannels]
  );

  const latestRows = useMemo(() => {
    return shownChannels
      .map((channel) => ({ channel, ...(latestByChannel[channel] || {}) }))
      .sort((a, b) => a.channel.localeCompare(b.channel));
  }, [shownChannels, latestByChannel]);

  const loadDevices = useCallback(async () => {
    setLoadingDevices(true);
    setError('');
    try {
      const response = await fetch('/api/psp/devices?probe_state=1', { credentials: 'include' });
      if (!response.ok) {
        throw new Error(`PSP devices request failed (${response.status})`);
      }
      const payload = await response.json();
      const loaded = Array.isArray(payload.devices) ? payload.devices : [];
      setDevices(loaded);
      if (loaded.length > 0) {
        setSelectedDeviceName((current) => {
          if (current && loaded.some((device) => device.name === current)) {
            return current;
          }
          return loaded[0].name;
        });
      } else {
        setSelectedDeviceName('');
      }
    } catch (err) {
      setError(err.message);
      setDevices([]);
      setSelectedDeviceName('');
    } finally {
      setLoadingDevices(false);
    }
  }, []);

  const loadVacuumHistory = useCallback(async (deviceName) => {
    if (!deviceName) {
      return;
    }
    setLoadingData(true);
    try {
      const seconds = Math.max(60, Number(windowMinutes || 30) * 60);
      const response = await fetch(
        `/api/psp/device/${encodeURIComponent(deviceName)}/group/vacuum/history?seconds=${seconds}&limit=${MAX_POINTS_PER_CHANNEL}`,
        { credentials: 'include' }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `PSP history failed (${response.status})`);
      }

      const nextSeries = payload.series && typeof payload.series === 'object' ? payload.series : {};
      const nextLatest = payload.latest_by_channel && typeof payload.latest_by_channel === 'object'
        ? payload.latest_by_channel
        : {};
      setSeries(nextSeries);
      setLatestByChannel(nextLatest);
      setSampleCount(Number(payload.sample_count || 0));
      setError('');

      setVisibleChannels((current) => {
        const next = {};
        for (const name of Object.keys(nextSeries)) {
          if (Object.prototype.hasOwnProperty.call(current, name)) {
            next[name] = current[name];
          } else {
            next[name] = true;
          }
        }
        return next;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingData(false);
    }
  }, [windowMinutes]);

  const loadSelectedDevice = async () => {
    if (!selectedDeviceName) {
      return;
    }
    setLoadedDeviceName(selectedDeviceName);
    await loadVacuumHistory(selectedDeviceName);
  };

  const toggleChannel = (channelName) => {
    setVisibleChannels((current) => ({
      ...current,
      [channelName]: current[channelName] === false,
    }));
  };

  useEffect(() => {
    loadDevices();
  }, [loadDevices]);

  useEffect(() => {
    if (!loadedDeviceName) {
      return undefined;
    }
    loadVacuumHistory(loadedDeviceName);
    if (!autoRefresh) {
      return undefined;
    }
    const delayMs = Math.max(0.5, Number(refreshSec || 2.0)) * 1000;
    const timer = setInterval(() => loadVacuumHistory(loadedDeviceName), delayMs);
    return () => clearInterval(timer);
  }, [loadedDeviceName, autoRefresh, refreshSec, windowMinutes, loadVacuumHistory]);

  useEffect(() => {
    const node = plotRef.current;
    if (!node) {
      return;
    }

    const traces = shownChannels.map((channelName) => {
      const points = Array.isArray(series[channelName]) ? series[channelName] : [];
      return {
        name: channelName,
        type: 'scattergl',
        mode: 'lines',
        line: { width: 1.4 },
        x: points.map((point) => new Date(Number(point.ts) * 1000)),
        y: points.map((point) => Number(point.value)),
      };
    });

    const now = Date.now();
    const rangeStart = now - Math.max(1, Number(windowMinutes || 30)) * 60 * 1000;

    Plotly.react(
      node,
      traces,
      {
        title: `Vacuum signals (${windowMinutes} min window)`,
        margin: { t: 44, r: 20, b: 40, l: 52 },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#fbfdff',
        xaxis: {
          title: 'Time',
          type: 'date',
          range: [new Date(rangeStart), new Date(now)],
          showgrid: true,
          gridcolor: '#e8eef5',
        },
        yaxis: {
          title: 'Value',
          showgrid: true,
          gridcolor: '#e8eef5',
        },
        legend: {
          orientation: 'h',
          y: 1.14,
        },
      },
      {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
      }
    );
  }, [series, shownChannels, windowMinutes]);

  useEffect(() => {
    const node = plotRef.current;
    return () => {
      if (node) {
        Plotly.purge(node);
      }
    };
  }, []);

  return (
    <div className="device-clients-page vacuum-clients-page">
      <div className="page-header">
        <h1>Vacuum Real-time Monitoring</h1>
        <p>Live vacuum trends from PSP FIFO storage (group: vacuum).</p>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="vacuum-toolbar">
        <button type="button" onClick={loadDevices} disabled={loadingDevices}>
          Refresh Devices
        </button>
        <select
          value={selectedDeviceName}
          onChange={(event) => setSelectedDeviceName(event.target.value)}
          disabled={loadingDevices || devices.length === 0}
        >
          {devices.map((device) => (
            <option key={device.name} value={device.name}>
              {device.name} ({device.state || 'UNKNOWN'})
            </option>
          ))}
        </select>
        <button type="button" onClick={loadSelectedDevice} disabled={!selectedDeviceName || loadingDevices}>
          Load Vacuum
        </button>
        <button type="button" onClick={() => loadVacuumHistory(loadedDeviceName)} disabled={!loadedDeviceName || loadingData}>
          Refresh Data
        </button>
      </div>

      {devices.length === 0 && !loadingDevices && (
        <p>No `DS_PSP` devices found. Start `manip/general/PSP` first.</p>
      )}

      {loadedDeviceName && (
        <>
          <div className="vacuum-meta">
            <span><strong>Loaded:</strong> {loadedDeviceName}</span>
            <span><strong>Samples:</strong> {sampleCount}</span>
            <span><strong>Channels:</strong> {channelNames.length}</span>
            <label className="inline-checkbox">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(event) => setAutoRefresh(event.target.checked)}
              />
              Auto refresh
            </label>
            <label>
              every
              <input
                type="number"
                min="0.5"
                step="0.5"
                value={refreshSec}
                onChange={(event) => setRefreshSec(event.target.value)}
              />
              s
            </label>
            <label>
              window
              <input
                type="number"
                min="5"
                max="120"
                step="5"
                value={windowMinutes}
                onChange={(event) => setWindowMinutes(event.target.value)}
              />
              min
            </label>
          </div>

          <div className="vacuum-layout">
            <aside className="vacuum-left">
              <div className="vacuum-card">
                <h3>Channels</h3>
                <div className="vacuum-channels">
                  {channelNames.map((channel) => (
                    <label key={channel} className="vacuum-checkbox">
                      <input
                        type="checkbox"
                        checked={visibleChannels[channel] !== false}
                        onChange={() => toggleChannel(channel)}
                      />
                      <span>{channel}</span>
                    </label>
                  ))}
                  {channelNames.length === 0 && <p className="vacuum-muted">No vacuum channels yet.</p>}
                </div>
              </div>

              <div className="vacuum-card">
                <h3>Latest Values</h3>
                <div className="vacuum-table-wrap">
                  <table className="vacuum-table">
                    <thead>
                      <tr>
                        <th>Channel</th>
                        <th>Value</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latestRows.map((row) => (
                        <tr key={row.channel}>
                          <td>{row.channel}</td>
                          <td>{Number(row.value).toExponential(6)}</td>
                          <td>{row.ts ? new Date(Number(row.ts) * 1000).toLocaleTimeString() : 'n/a'}</td>
                        </tr>
                      ))}
                      {latestRows.length === 0 && (
                        <tr>
                          <td colSpan={3}>No values yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </aside>

            <section className="vacuum-right">
              <div className="vacuum-plot" ref={plotRef} />
            </section>
          </div>
        </>
      )}
    </div>
  );
};

export default VacuumClients;
