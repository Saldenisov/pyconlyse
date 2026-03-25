import React, { useEffect, useMemo, useState } from 'react';
import './css/DeviceClients.css';
import './css/DAQmxClients.css';

const DAQmxClients = () => {
  const [devices, setDevices] = useState([]);
  const [selectedDeviceName, setSelectedDeviceName] = useState('');
  const [loadedDeviceName, setLoadedDeviceName] = useState('');
  const [latestPayload, setLatestPayload] = useState({});
  const [channels, setChannels] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshSec, setRefreshSec] = useState(1.0);
  const [filterText, setFilterText] = useState('');
  const [writeChannel, setWriteChannel] = useState('');
  const [writeValue, setWriteValue] = useState('');
  const [writeResult, setWriteResult] = useState('');
  const [writing, setWriting] = useState(false);

  const filteredChannels = useMemo(() => {
    const needle = String(filterText || '').trim().toLowerCase();
    if (!needle) {
      return channels;
    }
    return channels.filter((item) => item.name.toLowerCase().includes(needle));
  }, [channels, filterText]);

  const loadDevices = async () => {
    setLoadingDevices(true);
    setError('');
    try {
      const response = await fetch('/api/daqmx/devices?probe_state=1', { credentials: 'include' });
      if (!response.ok) {
        throw new Error(`DAQmx devices request failed (${response.status})`);
      }
      const payload = await response.json();
      const loaded = Array.isArray(payload.devices) ? payload.devices : [];
      setDevices(loaded);

      if (loaded.length > 0) {
        setSelectedDeviceName((current) => {
          if (current && loaded.some((dev) => dev.name === current)) {
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
  };

  const loadLatest = async (deviceName) => {
    if (!deviceName) {
      return;
    }
    setLoadingData(true);
    try {
      const response = await fetch(`/api/daqmx/device/${encodeURIComponent(deviceName)}/latest`, {
        credentials: 'include',
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `DAQmx latest read failed (${response.status})`);
      }

      setLatestPayload(payload.latest || {});
      setChannels(Array.isArray(payload.channels) ? payload.channels : []);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    loadDevices();
  }, []);

  useEffect(() => {
    if (!loadedDeviceName) {
      return undefined;
    }
    loadLatest(loadedDeviceName);
    if (!autoRefresh) {
      return undefined;
    }
    const delayMs = Math.max(0.2, Number(refreshSec || 1.0)) * 1000;
    const timer = setInterval(() => loadLatest(loadedDeviceName), delayMs);
    return () => clearInterval(timer);
  }, [loadedDeviceName, autoRefresh, refreshSec]);

  const loadSelectedDevice = async () => {
    if (!selectedDeviceName) {
      return;
    }
    setLoadedDeviceName(selectedDeviceName);
    setWriteResult('');
    await loadLatest(selectedDeviceName);
  };

  const writeChannelValue = async () => {
    const channel = String(writeChannel || '').trim();
    const raw = String(writeValue || '').trim();
    if (!loadedDeviceName || !channel || raw === '') {
      return;
    }

    let value = raw;
    const maybeNumber = Number(raw);
    if (!Number.isNaN(maybeNumber) && raw !== '') {
      value = maybeNumber;
    }

    setWriting(true);
    setWriteResult('');
    try {
      const response = await fetch(`/api/daqmx/device/${encodeURIComponent(loadedDeviceName)}/write`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, value }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `DAQmx write failed (${response.status})`);
      }
      setWriteResult(`Written: ${channel} = ${String(payload.value)}`);
      loadLatest(loadedDeviceName);
    } catch (err) {
      setWriteResult(`Write error: ${err.message}`);
    } finally {
      setWriting(false);
    }
  };

  const lastTimestamp = latestPayload?.timestamp;

  return (
    <div className="device-clients-page daqmx-clients-page">
      <div className="page-header">
        <h1>DAQmx / Supervision Clients</h1>
        <p>Read real-time parameters and send control values through Tango DAQmx devices.</p>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="daqmx-panel">
        <div className="daqmx-top-actions">
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
                {device.name} ({device.class}, {device.state || 'UNKNOWN'})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={loadSelectedDevice}
            disabled={!selectedDeviceName || loadingDevices}
          >
            Load Device
          </button>
          <button
            type="button"
            onClick={() => loadLatest(loadedDeviceName)}
            disabled={!loadedDeviceName || loadingData}
          >
            Refresh Data
          </button>
        </div>

        {devices.length === 0 && !loadingDevices && (
          <p>No DAQmx devices were found. Start `DS_DAQmx_ZMQ` or PSP supervision DS first.</p>
        )}

        {loadedDeviceName && (
          <>
            <div className="daqmx-meta">
              <span><strong>Loaded:</strong> {loadedDeviceName}</span>
              <span><strong>Channels:</strong> {channels.length}</span>
              <span><strong>Timestamp:</strong> {lastTimestamp ? String(lastTimestamp) : 'n/a'}</span>
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
                  min="0.2"
                  step="0.1"
                  value={refreshSec}
                  onChange={(event) => setRefreshSec(event.target.value)}
                />
                s
              </label>
            </div>

            <div className="daqmx-write-panel">
              <h3>Write Channel</h3>
              <div className="daqmx-write-row">
                <input
                  type="text"
                  placeholder="Channel name"
                  value={writeChannel}
                  onChange={(event) => setWriteChannel(event.target.value)}
                />
                <input
                  type="text"
                  placeholder="Value"
                  value={writeValue}
                  onChange={(event) => setWriteValue(event.target.value)}
                />
                <button
                  type="button"
                  disabled={writing || !writeChannel.trim() || String(writeValue).trim() === ''}
                  onClick={writeChannelValue}
                >
                  Send Value
                </button>
              </div>
              {writeResult && <div className="daqmx-write-result">{writeResult}</div>}
            </div>

            <div className="daqmx-channels-panel">
              <div className="daqmx-channels-header">
                <h3>Channels</h3>
                <input
                  type="text"
                  placeholder="Filter channels"
                  value={filterText}
                  onChange={(event) => setFilterText(event.target.value)}
                />
              </div>
              <div className="daqmx-table-wrap">
                <table className="daqmx-table">
                  <thead>
                    <tr>
                      <th>Channel</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredChannels.map((channel) => (
                      <tr key={channel.name}>
                        <td>{channel.name}</td>
                        <td>{String(channel.value)}</td>
                      </tr>
                    ))}
                    {filteredChannels.length === 0 && (
                      <tr>
                        <td colSpan={2}>No channels match current filter.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default DAQmxClients;
