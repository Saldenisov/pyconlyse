import React, { useEffect, useMemo, useState } from 'react';
import { fetchWithHardwareApproval } from './api/csrfRequest';
import './css/DeviceClients.css';
import './css/DAQmxClients.css';

const DIRECT_CLASS = 'DS_DAQmx';

const readJson = async (response) => {
  try {
    return await response.json();
  } catch (_error) {
    return { error: `HTTP ${response.status}` };
  }
};

export const groupDAQmxChannels = (channels = []) => channels.reduce(
  (groups, channel) => {
    const kind = String(channel.kind || 'other');
    if (kind === 'DigitalOut') groups.outputs.push(channel);
    else if (kind === 'DigitalIn') groups.inputs.push(channel);
    else if (kind === 'AIcurrent' || kind === 'AIVoltage') groups.analog.push(channel);
    else if (kind === 'DigitalCounter') groups.counters.push(channel);
    else groups.other.push(channel);
    return groups;
  },
  { outputs: [], inputs: [], analog: [], counters: [], other: [] }
);

export const formatDAQmxValue = (channel) => {
  if (!channel || channel.value === null || channel.value === undefined) return '—';
  if (channel.value_known === false) return 'Unknown';
  const value = channel.value;
  let text = String(value);
  if (typeof value === 'number' && Number.isFinite(value)) {
    text = Math.abs(value) >= 10000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)
      ? value.toExponential(3)
      : Number(value.toPrecision(6)).toString();
  }
  return channel.unit ? `${text} ${channel.unit}` : text;
};

const DAQmxClients = ({ deviceOverride = null }) => {
  const [devices, setDevices] = useState(Array.isArray(deviceOverride) ? deviceOverride : []);
  const [selectedDeviceName, setSelectedDeviceName] = useState('');
  const [loadedDeviceName, setLoadedDeviceName] = useState('');
  const [latestPayload, setLatestPayload] = useState({});
  const [deviceInfo, setDeviceInfo] = useState({});
  const [deviceState, setDeviceState] = useState('UNKNOWN');
  const [channels, setChannels] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(!Array.isArray(deviceOverride));
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshSec, setRefreshSec] = useState(1.0);
  const [filterText, setFilterText] = useState('');
  const [writeChannel, setWriteChannel] = useState('');
  const [writeValue, setWriteValue] = useState('');
  const [writeResult, setWriteResult] = useState('');
  const [activeCommand, setActiveCommand] = useState('');

  const loadedDevice = devices.find((device) => device.name === loadedDeviceName);
  const isDirectCard = loadedDevice?.class === DIRECT_CLASS || latestPayload?.source === 'direct';
  const grouped = useMemo(() => groupDAQmxChannels(channels), [channels]);
  const filteredOther = useMemo(() => {
    const needle = String(filterText || '').trim().toLowerCase();
    if (!needle) return grouped.other;
    return grouped.other.filter((item) => item.name.toLowerCase().includes(needle));
  }, [grouped.other, filterText]);

  const selectPreferredDevice = (loaded) => {
    if (!loaded.length) return '';
    return loaded.find((device) => device.class === DIRECT_CLASS)?.name || loaded[0].name;
  };

  const loadDevices = async () => {
    if (Array.isArray(deviceOverride)) {
      setDevices(deviceOverride);
      setSelectedDeviceName((current) => current || selectPreferredDevice(deviceOverride));
      setLoadingDevices(false);
      return;
    }
    setLoadingDevices(true);
    setError('');
    try {
      const response = await fetch('/api/daqmx/devices?probe_state=1', { credentials: 'include' });
      const payload = await readJson(response);
      if (!response.ok) throw new Error(payload.error || `DAQmx devices request failed (${response.status})`);
      const loaded = Array.isArray(payload.devices) ? payload.devices : [];
      setDevices(loaded);
      setSelectedDeviceName((current) => (
        current && loaded.some((device) => device.name === current)
          ? current
          : selectPreferredDevice(loaded)
      ));
    } catch (requestError) {
      setError(requestError.message);
      setDevices([]);
      setSelectedDeviceName('');
    } finally {
      setLoadingDevices(false);
    }
  };

  const loadLatest = async (deviceName, quiet = false) => {
    if (!deviceName) return;
    if (!quiet) setLoadingData(true);
    try {
      const response = await fetch(`/api/daqmx/device/${encodeURIComponent(deviceName)}/latest`, {
        credentials: 'include',
      });
      const payload = await readJson(response);
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `DAQmx latest read failed (${response.status})`);
      }
      setLatestPayload(payload.latest || {});
      setDeviceInfo(payload.device_info || {});
      setDeviceState(payload.state || 'UNKNOWN');
      setChannels(Array.isArray(payload.channels) ? payload.channels : []);
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      if (!quiet) setLoadingData(false);
    }
  };

  useEffect(() => { loadDevices(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!loadedDeviceName) return undefined;
    loadLatest(loadedDeviceName);
    if (!autoRefresh) return undefined;
    const delayMs = Math.max(0.25, Number(refreshSec || 1.0)) * 1000;
    const timer = setInterval(() => loadLatest(loadedDeviceName, true), delayMs);
    return () => clearInterval(timer);
  }, [loadedDeviceName, autoRefresh, refreshSec]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSelectedDevice = () => {
    if (!selectedDeviceName) return;
    setLoadedDeviceName(selectedDeviceName);
    setWriteResult('');
  };

  const sendMutation = async (url, body, commandKey) => {
    setActiveCommand(commandKey);
    setWriteResult('');
    try {
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const payload = await readJson(response);
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Hardware request failed (${response.status})`);
      }
      await loadLatest(loadedDeviceName, true);
      return payload;
    } finally {
      setActiveCommand('');
    }
  };

  const setDigitalOutput = async (channel, value) => {
    try {
      await sendMutation(
        `/api/daqmx/device/${encodeURIComponent(loadedDeviceName)}/write`,
        { channel: channel.name, value, command_variant: 'write_digital_output' },
        `write:${channel.name}`
      );
      setWriteResult(`${channel.name} set ${value ? 'ON' : 'OFF'}`);
    } catch (requestError) {
      setWriteResult(`Write error: ${requestError.message}`);
    }
  };

  const resetCounter = async (channel) => {
    try {
      await sendMutation(
        `/api/daqmx/device/${encodeURIComponent(loadedDeviceName)}/counter/reset`,
        { channel: channel.name, command_variant: 'reset_counter' },
        `reset:${channel.name}`
      );
      setWriteResult(`${channel.name} reset`);
    } catch (requestError) {
      setWriteResult(`Reset error: ${requestError.message}`);
    }
  };

  const writeChannelValue = async () => {
    const channel = String(writeChannel || '').trim();
    const raw = String(writeValue || '').trim();
    if (!loadedDeviceName || !channel || raw === '') return;
    const numericValue = Number(raw);
    const value = Number.isNaN(numericValue) ? raw : numericValue;
    try {
      const payload = await sendMutation(
        `/api/daqmx/device/${encodeURIComponent(loadedDeviceName)}/write`,
        { channel, value },
        'advanced-write'
      );
      setWriteResult(`Written: ${channel} = ${String(payload.value)}`);
    } catch (requestError) {
      setWriteResult(`Write error: ${requestError.message}`);
    }
  };

  const lastTimestamp = latestPayload?.timestamp;
  const cardLabel = deviceInfo?.name || latestPayload?.device || loadedDeviceName?.split('/').pop();
  const stateClass = String(deviceState).toLowerCase().replace('devstate.', '');

  return (
    <div className="device-clients-page daqmx-clients-page">
      <header className="daqmx-hero">
        <div>
          <span className="daqmx-eyebrow">National Instruments · Physical I/O</span>
          <h1>DAQ Control</h1>
          <p>Operate the TRANCON card and monitor its interlocks, analog signals, and pulse counter.</p>
        </div>
        {loadedDeviceName && (
          <div className={`daqmx-state-pill state-${stateClass}`}>
            <span className="daqmx-state-dot" />
            {String(deviceState).replace('DevState.', '')}
          </div>
        )}
      </header>

      {error && <div className="error-alert" role="alert"><strong>DAQ error:</strong> {error}</div>}
      {writeResult && <div className="daqmx-command-result" role="status">{writeResult}</div>}

      <section className="daqmx-toolbar" aria-label="DAQ device selection">
        <button type="button" className="secondary" onClick={loadDevices} disabled={loadingDevices}>
          {loadingDevices ? 'Discovering…' : 'Discover cards'}
        </button>
        <label>
          Tango device
          <select
            aria-label="Tango device"
            value={selectedDeviceName}
            onChange={(event) => setSelectedDeviceName(event.target.value)}
            disabled={loadingDevices || devices.length === 0}
          >
            {devices.map((device) => (
              <option key={device.name} value={device.name}>
                {device.name} · {device.class} · {device.state || 'UNKNOWN'}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={loadSelectedDevice} disabled={!selectedDeviceName || loadingDevices}>
          Open card
        </button>
        <button type="button" className="secondary" onClick={() => loadLatest(loadedDeviceName)} disabled={!loadedDeviceName || loadingData}>
          {loadingData ? 'Reading…' : 'Refresh now'}
        </button>
        <label className="daqmx-auto-refresh">
          <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />
          Live
          <input
            aria-label="Refresh interval seconds"
            type="number"
            min="0.25"
            step="0.25"
            value={refreshSec}
            onChange={(event) => setRefreshSec(event.target.value)}
          />
          s
        </label>
      </section>

      {devices.length === 0 && !loadingDevices && (
        <div className="daqmx-empty">No DAQ devices are registered in Tango.</div>
      )}

      {loadedDeviceName && (
        <>
          <section className="daqmx-card-summary">
            <div><span>Card</span><strong>{cardLabel || 'DAQmx'}</strong></div>
            <div><span>Model</span><strong>{deviceInfo?.product_type || 'Remote supervision source'}</strong></div>
            <div><span>Serial</span><strong>{deviceInfo?.serial_num || '—'}</strong></div>
            <div><span>Channels</span><strong>{channels.length}</strong></div>
            <div><span>Last sample</span><strong>{lastTimestamp ? new Date(Number(lastTimestamp) * 1000).toLocaleTimeString() : 'Now'}</strong></div>
          </section>

          {isDirectCard && (
            <main className="daqmx-dashboard">
              <section className="daqmx-section daqmx-output-section">
                <div className="daqmx-section-title">
                  <div><span>DO</span><h2>Digital outputs</h2></div>
                  <p>Explicit ON/OFF commands; unknown means no command has been issued since server start.</p>
                </div>
                <div className="daqmx-control-grid">
                  {grouped.outputs.map((channel) => {
                    const busy = activeCommand === `write:${channel.name}`;
                    const on = channel.value_known !== false && Number(channel.value) === 1;
                    const off = channel.value_known !== false && Number(channel.value) === 0;
                    return (
                      <article className="daqmx-control-card" key={channel.name}>
                        <div className="daqmx-control-heading">
                          <div>
                            <h3>{channel.name}</h3>
                            <code>{channel.physical_channel}</code>
                          </div>
                          <span className={`daqmx-output-state ${on ? 'on' : off ? 'off' : 'unknown'}`}>
                            {on ? 'ON' : off ? 'OFF' : 'UNKNOWN'}
                          </span>
                        </div>
                        <div className="daqmx-output-actions">
                          <button
                            type="button"
                            className="daqmx-off-button"
                            aria-label={`Set ${channel.name} OFF`}
                            disabled={busy}
                            onClick={() => setDigitalOutput(channel, 0)}
                          >OFF</button>
                          <button
                            type="button"
                            className="daqmx-on-button"
                            aria-label={`Set ${channel.name} ON`}
                            disabled={busy}
                            onClick={() => setDigitalOutput(channel, 1)}
                          >{busy ? 'Sending…' : 'ON'}</button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>

              <div className="daqmx-lower-grid">
                <section className="daqmx-section">
                  <div className="daqmx-section-title"><div><span>DI</span><h2>Digital inputs</h2></div></div>
                  <div className="daqmx-readout-list">
                    {grouped.inputs.map((channel) => (
                      <article className="daqmx-readout-row" key={channel.name}>
                        <span className={`daqmx-input-lamp ${Number(channel.value) ? 'active' : ''}`} />
                        <div><h3>{channel.name}</h3><code>{channel.physical_channel}</code></div>
                        <strong>{Number(channel.value) ? 'ACTIVE' : 'INACTIVE'}</strong>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="daqmx-section">
                  <div className="daqmx-section-title"><div><span>AI</span><h2>Analog inputs</h2></div></div>
                  <div className="daqmx-analog-grid">
                    {grouped.analog.map((channel) => (
                      <article className={`daqmx-analog-card ${channel.alarm ? 'alarm' : ''}`} key={channel.name}>
                        <div><h3>{channel.name}</h3><code>{channel.physical_channel}</code></div>
                        <strong>{formatDAQmxValue(channel)}</strong>
                        <small>
                          {channel.alarm
                            ? 'Outside configured alarm limits'
                            : channel.limit_alarm_min !== null || channel.limit_alarm_max !== null
                              ? `Limits ${channel.limit_alarm_min ?? '—'} – ${channel.limit_alarm_max ?? '—'} ${channel.unit || ''}`
                              : channel.kind}
                        </small>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="daqmx-section daqmx-counter-section">
                  <div className="daqmx-section-title"><div><span>CTR</span><h2>Counters</h2></div></div>
                  {grouped.counters.map((channel) => (
                    <article className="daqmx-counter-card" key={channel.name}>
                      <div><h3>{channel.name}</h3><code>{channel.counter} ← {channel.physical_channel}</code></div>
                      <strong>{formatDAQmxValue(channel)}</strong>
                      <button
                        type="button"
                        className="secondary"
                        disabled={activeCommand === `reset:${channel.name}`}
                        onClick={() => resetCounter(channel)}
                      >{activeCommand === `reset:${channel.name}` ? 'Resetting…' : 'Reset counter'}</button>
                    </article>
                  ))}
                </section>
              </div>
            </main>
          )}

          {!isDirectCard && (
            <section className="daqmx-section daqmx-supervision-section">
              <div className="daqmx-section-title">
                <div><span>NET</span><h2>Supervision values</h2></div>
                <input type="search" placeholder="Filter channels" value={filterText} onChange={(event) => setFilterText(event.target.value)} />
              </div>
              <div className="daqmx-table-wrap">
                <table className="daqmx-table">
                  <thead><tr><th>Channel</th><th>Value</th></tr></thead>
                  <tbody>
                    {filteredOther.map((channel) => <tr key={channel.name}><td>{channel.name}</td><td>{formatDAQmxValue(channel)}</td></tr>)}
                    {!filteredOther.length && <tr><td colSpan={2}>No matching values.</td></tr>}
                  </tbody>
                </table>
              </div>
              <details className="daqmx-advanced-write">
                <summary>Advanced channel write</summary>
                <div className="daqmx-write-row">
                  <input type="text" placeholder="Channel name" value={writeChannel} onChange={(event) => setWriteChannel(event.target.value)} />
                  <input type="text" placeholder="Value" value={writeValue} onChange={(event) => setWriteValue(event.target.value)} />
                  <button type="button" disabled={activeCommand === 'advanced-write' || !writeChannel.trim() || !String(writeValue).trim()} onClick={writeChannelValue}>
                    Send value
                  </button>
                </div>
              </details>
            </section>
          )}
        </>
      )}
    </div>
  );
};

export default DAQmxClients;
