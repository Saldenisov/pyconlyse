import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import '../css/ElectronicsClients.css';

export const TRIGGER_SOURCES = [
  [0, 'Internal'], [1, 'External rising edge'], [2, 'External falling edge'],
  [3, 'Single-shot external rising'], [4, 'Single-shot external falling'],
  [5, 'Single shot'], [6, 'Line'],
];
const DELAY_CHANNELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
const DELAY_REFERENCES = ['T0', 'T1', ...DELAY_CHANNELS];
const KEY_FIELDS = ['output_enabled', 'burst_enabled', 'waveform', 'frequency_hz', 'amplitude_vpp', 'offset_v'];
const DG_FIELDS = ['trigger_source', 'trigger_rate_hz', 'burst_enabled', 'burst_count', 'burst_period_s', 'delays_json'];
const STATUS_FIELDS = ['hardware_connection_state', 'initialization_state', 'hardware_lifecycle_status', 'idn', 'active_backend'];

const encode = (value) => encodeURIComponent(String(value));
const first = (value, fallback = '') => Array.isArray(value) ? (value[0] ?? fallback) : (value ?? fallback);

async function readJson(response, fallback) {
  let payload;
  try { payload = await response.json(); } catch (_) { throw new Error(fallback); }
  if (!response.ok || payload.success === false) throw new Error(payload.error || fallback);
  return payload;
}

function stateTone(state) {
  const value = String(state || '').toUpperCase();
  if (value === 'ON' || value === 'RUNNING') return 'good';
  if (value === 'FAULT' || value === 'ALARM' || value === 'UNKNOWN') return 'bad';
  return 'idle';
}

const ElectronicsController = ({ device }) => {
  const name = String(device?.name || '');
  const isDg645 = String(device?.class || '').toUpperCase() === 'DS_DG645' || name.toLowerCase().includes('dg645');
  const [summary, setSummary] = useState({ state: 'UNKNOWN', status: '' });
  const [properties, setProperties] = useState({});
  const [values, setValues] = useState({});
  const [draft, setDraft] = useState({});
  const [power, setPower] = useState({ configured: false, on: null, label: '', outputId: null });
  const [delay, setDelay] = useState({ channel: 'A', reference: 'T0', seconds: '0' });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const deviceUrl = `/api/device/${encode(name)}`;

  const readAttribute = useCallback(async (attribute) => {
    const response = await fetch(`${deviceUrl}/attribute/${encode(attribute)}`, { credentials: 'include' });
    const payload = await readJson(response, `Could not read ${attribute}`);
    return payload.value;
  }, [deviceUrl]);

  const refresh = useCallback(async ({ quiet = false } = {}) => {
    try {
      if (!quiet) setBusy('Refreshing');
      const [summaryPayload, propertyPayload] = await Promise.all([
        fetch(`${deviceUrl}/summary`, { credentials: 'include' }).then((r) => readJson(r, 'Device summary failed')),
        fetch(`${deviceUrl}/properties`, { credentials: 'include' }).then((r) => readJson(r, 'Device properties failed')),
      ]);
      const nextSummary = summaryPayload.device_info || {};
      setSummary(nextSummary);
      setProperties(propertyPayload);

      const powerDevice = String(first(propertyPayload.power_dependency_device, ''));
      const outputId = Number(first(propertyPayload.power_dependency_output_id, NaN));
      let nextPower = { configured: Boolean(powerDevice && Number.isFinite(outputId)), on: null, label: powerDevice, outputId };
      if (nextPower.configured) {
        try {
          const [ids, states, names] = await Promise.all(['ids', 'states', 'names'].map((attribute) =>
            fetch(`/api/device/${encode(powerDevice)}/attribute/${attribute}`, { credentials: 'include' })
              .then((r) => readJson(r, `PDU ${attribute} failed`))
          ));
          const index = Array.from(ids.value || []).map(Number).indexOf(outputId);
          nextPower = {
            ...nextPower,
            on: index >= 0 ? Number(Array.from(states.value || [])[index]) === 1 : null,
            outputName: index >= 0 ? String(Array.from(names.value || [])[index] || '') : '',
          };
        } catch (_) {
          // Keep the instrument usable when only dependency readback is unavailable.
        }
      }
      setPower(nextPower);

      const safeFields = STATUS_FIELDS.filter((field) => !(isDg645 && field === 'idn' && nextPower.on === false));
      const operational = String(nextSummary.state || '').toUpperCase() === 'ON';
      const controlFields = isDg645 ? (nextPower.on && operational ? DG_FIELDS : []) : KEY_FIELDS;
      const entries = await Promise.all([...safeFields, ...controlFields].map(async (field) => {
        try { return [field, await readAttribute(field)]; } catch (_) { return null; }
      }));
      const nextValues = Object.fromEntries(entries.filter(Boolean));
      setValues(nextValues);
      setDraft((current) => quiet && Object.keys(current).length ? current : nextValues);
      if (!quiet) { setError(''); setMessage('Readback refreshed.'); }
    } catch (err) {
      if (!quiet) setError(err.message);
    } finally {
      if (!quiet) setBusy('');
    }
  }, [deviceUrl, isDg645, readAttribute]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(() => refresh({ quiet: true }), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const execute = async (command, args, label) => {
    try {
      setBusy(label); setError(''); setMessage('');
      const response = await fetchWithHardwareApproval(`${deviceUrl}/command/${encode(command)}`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args === undefined ? {} : { args }),
      });
      const payload = await readJson(response, `${label} failed`);
      setMessage(payload.result == null ? `${label} completed.` : `${label}: ${payload.result}`);
      await refresh({ quiet: true });
    } catch (err) { setError(err.message); } finally { setBusy(''); }
  };

  const write = async (attribute, value, label) => {
    try {
      setBusy(label); setError(''); setMessage('');
      const response = await fetchWithHardwareApproval(`${deviceUrl}/attribute/${encode(attribute)}`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      });
      const payload = await readJson(response, `${label} failed`);
      setValues((current) => ({ ...current, [attribute]: payload.value }));
      setDraft((current) => ({ ...current, [attribute]: payload.value }));
      setMessage(`${label} applied; readback ${payload.value}.`);
    } catch (err) { setError(err.message); } finally { setBusy(''); }
  };

  const initialized = String(summary.state || '').toUpperCase() === 'ON';
  const controlsDisabled = Boolean(busy) || !initialized;
  const displayState = power.configured && power.on === false ? 'POWER OFF' : (summary.state || 'UNKNOWN');
  const delays = useMemo(() => {
    try { return JSON.parse(String(values.delays_json || '{}')); } catch (_) { return {}; }
  }, [values.delays_json]);

  const Field = ({ attribute, label, type = 'number', step = 'any', children }) => (
    <div className="electronics-field">
      <label htmlFor={`${name}-${attribute}`}>{label}</label>
      {children || <input id={`${name}-${attribute}`} type={type} step={step} value={draft[attribute] ?? ''}
        disabled={controlsDisabled} onChange={(event) => setDraft((current) => ({ ...current, [attribute]: event.target.value }))} />}
      <span className="electronics-readback">Readback: {values[attribute] ?? '—'}</span>
      <button type="button" disabled={controlsDisabled} onClick={() => write(attribute,
        type === 'number' ? Number(draft[attribute]) : draft[attribute], `Set ${label}`)}>Set</button>
    </div>
  );

  return (
    <section className="electronics-controller">
      <div className="electronics-controller-header">
        <div>
          <p className="electronics-kind">{isDg645 ? 'Stanford Research Systems · Digital delay generator' : 'Keysight · Waveform generator'}</p>
          <h2>{name}</h2>
          <p className="electronics-idn">{values.idn || first(properties.friendly_name, 'Identity available after initialization')}</p>
        </div>
        <span className={`electronics-state ${stateTone(displayState)}`}>{displayState}</span>
      </div>

      <div className="electronics-lifecycle">
        <div><span>Transport</span><strong>{values.hardware_connection_state || 'unknown'}</strong></div>
        <div><span>Initialization</span><strong>{values.initialization_state || 'unknown'}</strong></div>
        {isDg645 && <div><span>Backend</span><strong>{values.active_backend || first(properties.driver_backend, '—')}</strong></div>}
        {power.configured && <div><span>PDU power</span><strong className={power.on ? 'power-on' : 'power-off'}>{power.on === null ? 'unknown' : power.on ? 'ON' : 'OFF'} · output {power.outputId}</strong></div>}
      </div>
      <p className="electronics-lifecycle-note">{values.hardware_lifecycle_status || summary.status}</p>

      {power.configured && power.on === false && <div className="electronics-alert warning">
        DG645 power is OFF on {power.label}, output {power.outputId}. Power is never enabled automatically.{' '}
        <Link to="/pdu-clients">Open PDU controls</Link>.
      </div>}

      <div className="electronics-toolbar">
        <button type="button" className="primary" disabled={Boolean(busy) || (isDg645 && power.on !== true)} onClick={() => execute('turn_on', undefined, 'Initialize device')}>Initialize device</button>
        <button type="button" disabled={Boolean(busy) || !initialized} onClick={() => execute('turn_off', undefined, 'Release device')}>Release device</button>
        <button type="button" disabled={Boolean(busy)} onClick={() => refresh()}>Refresh</button>
        {busy && <span className="electronics-busy">{busy}…</span>}
      </div>
      {error && <div className="electronics-alert error"><strong>Error:</strong> {error}</div>}
      {message && <div className="electronics-alert success">{message}</div>}
      {!initialized && <p className="electronics-passive-note">Controls remain locked until the operator initializes this DS.</p>}

      {!isDg645 && <div className="electronics-control-grid">
        <div className="electronics-panel">
          <h3>Output</h3>
          <div className="electronics-toggle-row"><span>Channel output</span><strong>{Number(values.output_enabled) ? 'ON' : 'OFF'}</strong>
            <button type="button" disabled={controlsDisabled} onClick={() => write('output_enabled', Number(values.output_enabled) ? 0 : 1, 'Output')}>{Number(values.output_enabled) ? 'Turn off' : 'Turn on'}</button></div>
          <div className="electronics-toggle-row"><span>Burst mode</span><strong>{Number(values.burst_enabled) ? 'ON' : 'OFF'}</strong>
            <button type="button" disabled={controlsDisabled} onClick={() => write('burst_enabled', Number(values.burst_enabled) ? 0 : 1, 'Burst mode')}>{Number(values.burst_enabled) ? 'Disable' : 'Enable'}</button></div>
        </div>
        <div className="electronics-panel electronics-settings-panel">
          <h3>Waveform</h3>
          <Field attribute="waveform" label="Function" type="text"><select id={`${name}-waveform`} disabled={controlsDisabled} value={draft.waveform ?? 'SIN'} onChange={(event) => setDraft((current) => ({ ...current, waveform: event.target.value }))}>{['SIN', 'SQU', 'RAMP', 'NOIS', 'DC', 'USER'].map((item) => <option key={item}>{item}</option>)}</select></Field>
          <Field attribute="frequency_hz" label="Frequency (Hz)" />
          <Field attribute="amplitude_vpp" label="Amplitude (Vpp)" />
          <Field attribute="offset_v" label="Offset (V)" />
        </div>
      </div>}

      {isDg645 && <div className="electronics-control-grid">
        <div className="electronics-panel electronics-settings-panel">
          <h3>Trigger and burst</h3>
          <Field attribute="trigger_source" label="Trigger source" type="number"><select id={`${name}-trigger_source`} disabled={controlsDisabled} value={draft.trigger_source ?? 0} onChange={(event) => setDraft((current) => ({ ...current, trigger_source: Number(event.target.value) }))}>{TRIGGER_SOURCES.map(([code, label]) => <option key={code} value={code}>{code} · {label}</option>)}</select></Field>
          <Field attribute="trigger_rate_hz" label="Internal rate (Hz)" />
          <div className="electronics-toggle-row"><span>Burst mode</span><strong>{Number(values.burst_enabled) ? 'ON' : 'OFF'}</strong><button type="button" disabled={controlsDisabled} onClick={() => write('burst_enabled', Number(values.burst_enabled) ? 0 : 1, 'Burst mode')}>{Number(values.burst_enabled) ? 'Disable' : 'Enable'}</button></div>
          <Field attribute="burst_count" label="Burst count" step="1" />
          <Field attribute="burst_period_s" label="Burst period (s)" />
        </div>
        <div className="electronics-panel electronics-delay-panel">
          <h3>Delay channels</h3><p>Set a delay relative to T0, T1, or another output. Values are seconds.</p>
          <div className="electronics-delay-form">
            <label>Channel<select disabled={controlsDisabled} value={delay.channel} onChange={(event) => setDelay((current) => ({ ...current, channel: event.target.value }))}>{DELAY_CHANNELS.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Reference<select disabled={controlsDisabled} value={delay.reference} onChange={(event) => setDelay((current) => ({ ...current, reference: event.target.value }))}>{DELAY_REFERENCES.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Delay (s)<input disabled={controlsDisabled} type="number" step="any" value={delay.seconds} onChange={(event) => setDelay((current) => ({ ...current, seconds: event.target.value }))} /></label>
            <button type="button" className="primary" disabled={controlsDisabled} onClick={() => execute('set_delay', `${delay.channel},${delay.reference},${delay.seconds}`, `Set delay ${delay.channel}`)}>Set delay</button>
          </div>
          {Object.keys(delays).length > 0 && <div className="electronics-delay-readbacks">{DELAY_CHANNELS.map((channel) => <div key={channel}><strong>{channel}</strong><span>{delays[channel] || '—'}</span></div>)}</div>}
          {!values.delays_json && initialized && <p className="electronics-upgrade-note">Restart the updated DS_DG645 to enable the passive A–H delay readback table.</p>}
        </div>
      </div>}
    </section>
  );
};

export default ElectronicsController;
