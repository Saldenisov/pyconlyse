import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import './css/DeviceClients.css';
import './css/VacuumClients.css';

const MAX_POINTS_PER_CHANNEL = 4000;
const MIN_LOG_MAGNITUDE = 1e-12;
const DEFAULT_Y_MIN = 1e-10;
const DEFAULT_Y_MAX = 1e-2;

const isMeasurementChannel = (channelName) => String(channelName || '').endsWith('/measurement');
const toLogMagnitude = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return Math.max(Math.abs(numeric), MIN_LOG_MAGNITUDE);
};
const toPlotTime = (point) => {
  const recvTs = Number(point?.recv_ts);
  if (Number.isFinite(recvTs) && recvTs > 0) {
    return new Date(recvTs * 1000);
  }
  const ts = Number(point?.ts);
  if (Number.isFinite(ts) && ts > 0) {
    return new Date(ts * 1000);
  }
  return null;
};

const VacuumClients = () => {
  const plotRef = useRef(null);
  const userYRangeRef = useRef(null);
  const [devices, setDevices] = useState([]);
  const [selectedDeviceName, setSelectedDeviceName] = useState('');
  const [loadedDeviceName, setLoadedDeviceName] = useState('');
  const [sessionStartMs, setSessionStartMs] = useState(null);
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
    () => Object.keys(series)
      .filter((channel) => isMeasurementChannel(channel))
      .sort((a, b) => a.localeCompare(b)),
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
      const windowSec = Math.max(60, Number(windowMinutes || 30) * 60);
      const nowMs = Date.now();
      const elapsedSec = Number.isFinite(sessionStartMs)
        ? Math.max(1, Math.ceil((nowMs - sessionStartMs) / 1000))
        : windowSec;
      const paddingSec = Math.max(2, Math.ceil(Number(refreshSec || 2.0)) + 1);
      const seconds = elapsedSec < windowSec
        ? elapsedSec + paddingSec
        : windowSec + paddingSec;
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
  }, [windowMinutes, sessionStartMs, refreshSec]);

  const loadSelectedDevice = async () => {
    if (!selectedDeviceName) {
      return;
    }
    setSessionStartMs(Date.now());
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
      const plotPoints = points
        .map((point) => {
          const magnitude = toLogMagnitude(point.value);
          const plotTime = toPlotTime(point);
          if (magnitude === null || !plotTime) {
            return null;
          }
          return {
            x: plotTime,
            y: magnitude,
            rawValue: Number(point.value),
          };
        })
        .filter(Boolean);

      return {
        name: channelName,
        type: 'scattergl',
        mode: plotPoints.length > 1 ? 'lines+markers' : 'markers',
        line: { width: 1.4 },
        marker: { size: plotPoints.length > 1 ? 5 : 8 },
        x: plotPoints.map((point) => point.x),
        y: plotPoints.map((point) => point.y),
        customdata: plotPoints.map((point) => [point.rawValue]),
        hovertemplate:
          '%{fullData.name}<br>' +
          'Time: %{x}<br>' +
          '|value|: %{y:.3e}<br>' +
          'raw: %{customdata[0]:.3e}<extra></extra>',
      };
    });

    const now = Date.now();
    const windowMs = Math.max(1, Number(windowMinutes || 30)) * 60 * 1000;
    const baseStartMs = Number.isFinite(sessionStartMs) ? sessionStartMs : now;
    const initialEndMs = baseStartMs + windowMs;
    const rangeEndMs = now < initialEndMs ? initialEndMs : now;
    const rangeStartMs = now < initialEndMs ? baseStartMs : rangeEndMs - windowMs;

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
          range: [new Date(rangeStartMs), new Date(rangeEndMs)],
          showgrid: true,
          gridcolor: '#e8eef5',
        },
        yaxis: {
          title: '|Value|',
          type: 'log',
          range: userYRangeRef.current || [Math.log10(DEFAULT_Y_MIN), Math.log10(DEFAULT_Y_MAX)],
          tickmode: 'array',
          tickvals: [1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2],
          ticktext: ['10^-10', '10^-9', '10^-8', '10^-7', '10^-6', '10^-5', '10^-4', '10^-3', '10^-2'],
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
  }, [series, shownChannels, windowMinutes, sessionStartMs]);

  useEffect(() => {
    const node = plotRef.current;
    if (!node) {
      return undefined;
    }

    const handleRelayout = (eventData) => {
      if (!eventData || typeof eventData !== 'object') {
        return;
      }

      if (Object.prototype.hasOwnProperty.call(eventData, 'yaxis.autorange') && eventData['yaxis.autorange']) {
        userYRangeRef.current = null;
        return;
      }

      const y0 = eventData['yaxis.range[0]'];
      const y1 = eventData['yaxis.range[1]'];
      if (Number.isFinite(y0) && Number.isFinite(y1)) {
        userYRangeRef.current = [y0, y1];
      }
    };

    node.on('plotly_relayout', handleRelayout);

    return () => {
      node.removeListener?.('plotly_relayout', handleRelayout);
      Plotly.purge(node);
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
                          <td>{toLogMagnitude(row.value)?.toExponential(6) || 'n/a'}</td>
                          <td>{toPlotTime(row)?.toLocaleTimeString() || 'n/a'}</td>
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
