import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './css/PumpProbeVD2.css';

const API_BASE = '/api/pump-probe-vd2';

const TIME_RANGES = [
  '0.5 ns', '1 ns', '2 ns', '5 ns', '10 ns', '20 ns', '50 ns', '100 ns',
  '200 ns', '500 ns', '1 us', '2 us', '5 us', '10 us', '20 us', '50 us',
  '100 us', '200 us', '500 us', '1 ms',
];

const CARDS = [
  {
    title: 'Streak camera',
    subtitle: 'Hamamatsu C7700 / HPD-TA RemoteEx',
    tone: 'camera',
    fields: [
      { key: 'time_range', label: 'Time range', options: TIME_RANGES },
      { key: 'streak_mode', label: 'Mode', options: ['Focus', 'Operate'] },
      { key: 'gate_mode', label: 'Gate mode', options: ['Normal', 'Gate'] },
      { key: 'mcp_gain', label: 'II-Gain', type: 'number', min: 0, max: 255, step: 1 },
      { key: 'streak_shutter', label: 'Shutter', options: ['Closed', 'Open'] },
      { key: 'streak_trigger_mode', label: 'Trig. mode', options: ['Cont', 'Ext. rising', 'Ext. falling'] },
      { key: 'streak_trigger_status', label: 'Trigger status', readOnly: true },
      { key: 'focus_time_over', label: 'Focus TimeOver', type: 'number', step: 1 },
    ],
  },
  {
    title: 'DG645 delay generator',
    subtitle: 'Timing held by the streak-camera RemoteEx session',
    tone: 'timing',
    fields: [
      { key: 'delay_trigger_mode', label: 'Trig. mode', options: ['Ext. rising', 'Ext. falling', 'Internal'] },
      { key: 'delay_repetition_rate', label: 'Repetition rate', type: 'number', min: 0.001, step: 0.001, unit: 'Hz' },
      { key: 'delay_setting', label: 'Setting' },
      ...['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'].map((channel) => ({
        key: `delay_${channel}`,
        label: `Delay ${channel.toUpperCase()}`,
        type: 'number',
        step: 0.000000001,
        unit: 's',
      })),
      { key: 'delay_ss_trigger', label: 'SS trigger', readOnly: true },
      { key: 'delay_burst_mode', label: 'Burst mode', options: ['Off', 'On'] },
      { key: 'delay_manual_control', label: 'Man. ctrl', options: ['Hide', 'Show'] },
    ],
  },
  {
    title: 'Spectrograph',
    subtitle: 'Spectrograph coupled to the streak camera',
    tone: 'spectrograph',
    fields: [
      { key: 'wavelength_nm', label: 'Wavelength', type: 'number', min: 0, max: 2000, step: 0.1, unit: 'nm' },
      { key: 'grating', label: 'Grating', options: ['50 g/mm', '150 g/mm', '300 g/mm', '600 g/mm', '1200 g/mm'] },
      { key: 'blaze', label: 'Blaze', readOnly: true },
      { key: 'ruling', label: 'Ruling', readOnly: true },
      { key: 'exit_mirror', label: 'Exit mirror', options: ['Front', 'Side'] },
      { key: 'turret', label: 'Turret', type: 'number', min: 1, max: 3, step: 1 },
      { key: 'spectrograph_shutter', label: 'Shutter', options: ['Closed', 'Open', 'External BNC'] },
      { key: 'focus_mirror', label: 'Focus mirror', type: 'number', step: 1 },
      { key: 'side_entry_iris', label: 'Side entry iris', type: 'number', min: 0, max: 100, step: 1 },
      { key: 'slit_width_um', label: 'Slit width', type: 'number', min: 0, max: 3000, step: 1, unit: 'um' },
    ],
  },
];

const ACQUISITION_FIELDS = [
  { key: 'live_exposure_time', label: 'Live exposure', type: 'number', min: 0, step: 0.001, unit: 's' },
  { key: 'acquire_exposure_time', label: 'Acquire exposure', type: 'number', min: 0, step: 0.001, unit: 's' },
  { key: 'analog_integration_count', label: 'Integrations', type: 'number', min: 1, step: 1 },
  { key: 'sequence_loops', label: 'Sequence loops', type: 'number', min: 1, step: 1 },
];

const VD2_POWER_CHANNELS = [
  { key: 'streak-camera', label: 'Streak camera / spectrograph', device: 'manip/SD2/PDU_SD2', outputId: 1 },
  { key: 'dg645-power', label: 'DG645', device: 'manip/SD2/PDU_SD2', outputId: 2 },
];

const VD2_TANGO_SERVERS = [
  { key: 'streak-tango', label: 'Hamamatsu streak / HPD-TA', device: 'manip/camera/hamamatsu_streak_main' },
  { key: 'dg645-tango', label: 'DG645 digital generator', device: 'manip/sync/DG645' },
];

function valueText(value) {
  return value === null || value === undefined || value === '' ? '-' : String(value);
}

function EditableField({ field, value, onApply, busy }) {
  const [draft, setDraft] = useState(valueText(value));
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) {
      setDraft(valueText(value));
    }
  }, [editing, value]);

  if (field.readOnly) {
    return <output id={`vd2-${field.key}`} className="vd2-readonly">{valueText(value)}</output>;
  }

  const apply = () => {
    if (draft !== valueText(value)) {
      onApply(field.key, draft);
    }
    setEditing(false);
  };

  if (field.options) {
    const options = field.options.includes(valueText(value))
      ? field.options
      : [valueText(value), ...field.options];
    return (
      <select
        id={`vd2-${field.key}`}
        aria-label={field.label}
        value={valueText(value)}
        disabled={busy}
        onChange={(event) => onApply(field.key, event.target.value)}
      >
        {options.map((option) => <option value={option} key={option}>{option}</option>)}
      </select>
    );
  }

  return (
    <div className="vd2-editable-input">
      <input
        id={`vd2-${field.key}`}
        aria-label={field.label}
        type={field.type || 'text'}
        min={field.min}
        max={field.max}
        step={field.step}
        value={draft === '-' ? '' : draft}
        disabled={busy}
        onFocus={() => setEditing(true)}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={apply}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.currentTarget.blur();
          }
          if (event.key === 'Escape') {
            setDraft(valueText(value));
            event.currentTarget.blur();
          }
        }}
      />
      {field.unit && <span>{field.unit}</span>}
    </div>
  );
}

function ParameterCard({ card, values, onApply, busy }) {
  return (
    <section className={`vd2-card vd2-card-${card.tone}`}>
      <header>
        <h2>{card.title}</h2>
        <p>{card.subtitle}</p>
      </header>
      <div className="vd2-table" role="table" aria-label={`${card.title} parameters`}>
        <div className="vd2-table-head" role="row">
          <span role="columnheader">Parameter</span>
          <span role="columnheader">Value</span>
        </div>
        {card.fields.map((field) => (
          <div className="vd2-table-row" role="row" key={field.key}>
            <label role="cell" htmlFor={`vd2-${field.key}`}>{field.label}</label>
            <div role="cell">
              <EditableField field={field} value={values[field.key]} onApply={onApply} busy={busy} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

const LUT_PALETTES = {
  rainbow: 'Rainbow',
  grayscale: 'Grayscale',
};

const ROI_TOOLS = {
  vertical: { label: 'Vertical', color: '#f1c84b', profile: 'Kinetics' },
  horizontal: { label: 'Horizontal', color: '#61c7ec', profile: 'Spectrum' },
  rectangle: { label: 'Rectangle', color: '#ec76c1', profile: 'Both' },
};

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function rainbowColor(value) {
  const anchors = [
    [0, [0, 0, 44]],
    [0.18, [0, 0, 255]],
    [0.38, [0, 220, 255]],
    [0.56, [0, 255, 80]],
    [0.76, [255, 245, 0]],
    [1, [255, 32, 0]],
  ];
  const upperIndex = anchors.findIndex(([stop]) => value <= stop);
  const upper = anchors[Math.max(1, upperIndex)];
  const lower = anchors[Math.max(0, anchors.indexOf(upper) - 1)];
  const mix = (value - lower[0]) / (upper[0] - lower[0]);
  return lower[1].map((component, index) => Math.round(component + mix * (upper[1][index] - component)));
}

function buildLut(palette, minimum, maximum) {
  const lut = new Uint8ClampedArray(256 * 3);
  const span = Math.max(1, maximum - minimum);
  for (let intensity = 0; intensity < 256; intensity += 1) {
    const normalized = clamp((intensity - minimum) / span, 0, 1);
    const color = palette === 'grayscale'
      ? [Math.round(normalized * 255), Math.round(normalized * 255), Math.round(normalized * 255)]
      : rainbowColor(normalized);
    const index = intensity * 3;
    lut[index] = color[0];
    lut[index + 1] = color[1];
    lut[index + 2] = color[2];
  }
  return lut;
}

function drawPreview(canvas, preview, palette, minimum, maximum) {
  if (!canvas || !preview?.pixels_b64) return;
  const { width, height } = preview;
  const encoded = window.atob(preview.pixels_b64);
  if (encoded.length !== width * height) return;

  const lut = buildLut(palette, minimum, maximum);
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { alpha: false });
  const image = context.createImageData(width, height);
  for (let source = 0, target = 0; source < encoded.length; source += 1, target += 4) {
    const intensity = encoded.charCodeAt(source);
    const color = intensity * 3;
    image.data[target] = lut[color];
    image.data[target + 1] = lut[color + 1];
    image.data[target + 2] = lut[color + 2];
    image.data[target + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

function LutControl({ palette, range, preview, onPaletteChange, onRangeChange, onAutoscale }) {
  const maximum = Math.max(range.maximum, range.minimum + 1);
  return (
    <section className={`vd2-lut is-${palette}`} aria-label="LUT control">
      <div className="vd2-lut-heading">
        <span>LUT control</span>
        <select aria-label="LUT palette" value={palette} onChange={(event) => onPaletteChange(event.target.value)}>
          {Object.entries(LUT_PALETTES).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
        <button
          type="button"
          className="vd2-lut-autoscale"
          title="Autoscale LUT range from current frame"
          aria-label="Autoscale LUT range"
          onClick={onAutoscale}
          disabled={!preview}
        >
          *
        </button>
      </div>
      <div className="vd2-lut-gradient" aria-hidden="true" />
      <div className="vd2-lut-range">
        <label>
          <span>Low {range.minimum}</span>
          <input
            type="range"
            min="0"
            max="254"
            value={range.minimum}
            onChange={(event) => onRangeChange('minimum', Number(event.target.value))}
          />
        </label>
        <label>
          <span>High {maximum}</span>
          <input
            type="range"
            min="1"
            max="255"
            value={maximum}
            onChange={(event) => onRangeChange('maximum', Number(event.target.value))}
          />
        </label>
      </div>
    </section>
  );
}

function roiBounds(roi, width, height) {
  const x0 = clamp(Math.min(roi.x0, roi.x1), 0, width - 1);
  const x1 = clamp(Math.max(roi.x0, roi.x1), 0, width - 1);
  const y0 = clamp(Math.min(roi.y0, roi.y1), 0, height - 1);
  const y1 = clamp(Math.max(roi.y0, roi.y1), 0, height - 1);
  return { x0, x1, y0, y1 };
}

function decodePreviewPixels(preview) {
  if (!preview?.pixels_b64) return null;
  const encoded = window.atob(preview.pixels_b64);
  if (encoded.length !== preview.width * preview.height) return null;
  const pixels = new Uint8Array(encoded.length);
  for (let index = 0; index < encoded.length; index += 1) {
    pixels[index] = encoded.charCodeAt(index);
  }
  return pixels;
}

function roiProfiles(preview, roi) {
  const pixels = decodePreviewPixels(preview);
  if (!pixels || !roi) return null;
  const { width, height } = preview;
  const { x0, x1, y0, y1 } = roiBounds(roi, width, height);
  const spectrum = [];
  const kinetics = [];

  for (let x = x0; x <= x1; x += 1) {
    let sum = 0;
    for (let y = y0; y <= y1; y += 1) sum += pixels[y * width + x];
    spectrum.push(sum / (y1 - y0 + 1));
  }
  for (let y = y0; y <= y1; y += 1) {
    let sum = 0;
    for (let x = x0; x <= x1; x += 1) sum += pixels[y * width + x];
    kinetics.push(sum / (x1 - x0 + 1));
  }
  return { spectrum, kinetics, bounds: { x0, x1, y0, y1 } };
}

function ProfilePlot({ title, samples, color, axis }) {
  const width = 360;
  const height = 146;
  const padding = { left: 34, right: 8, top: 10, bottom: 24 };
  if (!samples?.length) return null;
  const minimum = Math.min(...samples);
  const maximum = Math.max(...samples);
  const span = Math.max(1, maximum - minimum);
  const graphWidth = width - padding.left - padding.right;
  const graphHeight = height - padding.top - padding.bottom;
  const points = samples.map((sample, index) => {
    const x = padding.left + (index / Math.max(1, samples.length - 1)) * graphWidth;
    const y = padding.top + (1 - (sample - minimum) / span) * graphHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <section className="vd2-profile" aria-label={title}>
      <header><strong>{title}</strong><span>{minimum.toFixed(1)} - {maximum.toFixed(1)}</span></header>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title} dynamic profile`}>
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} />
        <polyline points={points} stroke={color} />
        <text x={padding.left} y={height - 6}>{axis}</text>
        <text x="4" y={padding.top + 8}>count</text>
      </svg>
    </section>
  );
}

function RoiProfiles({ preview, roi }) {
  const profiles = useMemo(() => roiProfiles(preview, roi), [preview, roi]);
  if (!roi || !profiles) {
    return <div className="vd2-profile-empty">Draw an ROI, then select it to inspect its live profile.</div>;
  }
  const tool = ROI_TOOLS[roi.type];
  return (
    <div className="vd2-profiles">
      {roi.type !== 'vertical' && <ProfilePlot title="Spectrum" samples={profiles.spectrum} color={tool.color} axis="camera X, px" />}
      {roi.type !== 'horizontal' && <ProfilePlot title="Kinetics" samples={profiles.kinetics} color={tool.color} axis="camera Y, px" />}
    </div>
  );
}

function Vd2HardwareModal({ open, power, tango, loading, error, onClose, onRefresh, onToggle, onAllPower, onServer }) {
  if (!open) return null;
  const outputFor = (channel) => power.outputs.find((output) => Number(output.id) === channel.outputId);
  return (
    <div className="vd2-modal-backdrop" onClick={onClose}>
      <section className="vd2-hardware-modal" onClick={(event) => event.stopPropagation()} aria-label="VD2 hardware">
        <header>
          <h2>Hardware</h2>
          <button type="button" onClick={onClose}>Close</button>
        </header>
        <div className="vd2-hardware-toolbar">
          <button type="button" onClick={() => onAllPower(true)} disabled={loading}>Turn required ON</button>
          <button type="button" onClick={() => onAllPower(false)} disabled={loading}>Turn required OFF</button>
          <button type="button" onClick={onRefresh} disabled={loading}>Refresh</button>
        </div>
        {error && <div className="vd2-error" role="alert">{error}</div>}
        <div className="vd2-hardware-columns">
          <section>
            <h3>NETIO PDU SD2</h3>
            {VD2_POWER_CHANNELS.map((channel) => {
              const output = outputFor(channel);
              const isOn = output ? Number(output.state) === 1 : null;
              return (
                <button
                  type="button"
                  key={channel.key}
                  className={`vd2-hardware-toggle ${isOn ? 'is-on' : ''}`}
                  disabled={loading || isOn === null}
                  onClick={() => onToggle(channel, !isOn)}
                >
                  <span>{channel.label}</span>
                  <small>{channel.device} / out {channel.outputId}</small>
                  <strong>{isOn === null ? 'UNKNOWN' : (isOn ? 'ON' : 'OFF')}</strong>
                </button>
              );
            })}
          </section>
          <section>
            <h3>Tango</h3>
            {VD2_TANGO_SERVERS.map((server) => {
              const status = tango[server.device] || { state: 'UNKNOWN', ok: false };
              return (
                <div className={`vd2-tango-row ${status.ok ? 'is-on' : ''}`} key={server.key}>
                  <div>
                    <strong>{server.label}</strong>
                    <small>{server.device}</small>
                    {status.error && <em>{status.error}</em>}
                  </div>
                  <b>{status.state}</b>
                  <button type="button" disabled={loading} onClick={() => onServer(server, 'start')}>Start</button>
                  <button type="button" disabled={loading} onClick={() => onServer(server, 'restart')}>Restart</button>
                </div>
              );
            })}
          </section>
        </div>
      </section>
    </div>
  );
}

function PumpProbeVD2() {
  const [state, setState] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [previewError, setPreviewError] = useState('');
  const [previewEnabled, setPreviewEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState('acquisition');
  const [lutPalette, setLutPalette] = useState('rainbow');
  const [lutRange, setLutRange] = useState({ minimum: 0, maximum: 255 });
  const [roiTool, setRoiTool] = useState('vertical');
  const [rois, setRois] = useState([]);
  const [selectedRoiId, setSelectedRoiId] = useState(null);
  const [drawingRoi, setDrawingRoi] = useState(null);
  const [hardwareOpen, setHardwareOpen] = useState(false);
  const [hardwarePower, setHardwarePower] = useState({ outputs: [] });
  const [hardwareTango, setHardwareTango] = useState({});
  const [hardwareLoading, setHardwareLoading] = useState(false);
  const [hardwareError, setHardwareError] = useState('');
  const requestActive = useRef(false);
  const previewRequestActive = useRef(false);
  const previewCanvas = useRef(null);
  const previewOverlay = useRef(null);
  const nextRoiId = useRef(1);

  const loadState = useCallback(async () => {
    if (requestActive.current) return;
    requestActive.current = true;
    try {
      const response = await fetch(`${API_BASE}/state`, { credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read VD2 state');
      setState(payload);
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      requestActive.current = false;
    }
  }, []);

  useEffect(() => {
    loadState();
    const interval = window.setInterval(loadState, 2500);
    return () => window.clearInterval(interval);
  }, [loadState]);

  const loadPreview = useCallback(async () => {
    if (previewRequestActive.current) return;
    previewRequestActive.current = true;
    try {
      const response = await fetch(`${API_BASE}/preview`, { credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read live frame');
      if (!payload.frame_available) return;
      setPreview(payload);
      setPreviewError('');
    } catch (requestError) {
      if (requestError.message === 'Live acquisition has stopped producing frames' || requestError.message === 'Live acquisition is not active') {
        setPreview(null);
        setPreviewEnabled(false);
      }
      setPreviewError(requestError.message);
    } finally {
      previewRequestActive.current = false;
    }
  }, []);

  useEffect(() => {
    if (
      activeTab !== 'acquisition'
      || !previewEnabled
      || !state?.connected
      || !state?.application_running
      || state?.remoteex_status !== 'busy'
    ) return undefined;
    loadPreview();
    const interval = window.setInterval(loadPreview, 350);
    return () => window.clearInterval(interval);
  }, [
    activeTab,
    loadPreview,
    previewEnabled,
    state?.application_running,
    state?.connected,
    state?.remoteex_status,
  ]);

  useEffect(() => {
    drawPreview(previewCanvas.current, preview, lutPalette, lutRange.minimum, lutRange.maximum);
  }, [lutPalette, lutRange, preview]);

  const runRequest = useCallback(async (path, body) => {
    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Control request failed');
      setState(payload);
      if (path === '/command/StartLive') {
        setPreview(null);
        setPreviewEnabled(true);
        setPreviewError('');
      }
      if (
        path === '/command/StopAcquisition'
        || path === '/command/StopSequence'
        || path === '/command/StopApplication'
        || path === '/command/ShutdownRemoteEx'
      ) {
        setPreview(null);
        setPreviewEnabled(false);
        setPreviewError('');
      }
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }, []);

  const writeParameter = useCallback((name, value) => runRequest(`/parameter/${name}`, { value }), [runRequest]);
  const runCommand = useCallback((name) => runRequest(`/command/${name}`), [runRequest]);

  const loadHardware = useCallback(async () => {
    setHardwareLoading(true);
    setHardwareError('');
    try {
      const powerResponse = await fetch('/api/device/manip/SD2/PDU_SD2/pdu/outputs', { credentials: 'include' });
      const powerPayload = await powerResponse.json();
      if (!powerResponse.ok || powerPayload.success === false) throw new Error(powerPayload.error || 'Could not read PDU SD2');
      setHardwarePower({ outputs: powerPayload.outputs || [] });
      const entries = await Promise.all(VD2_TANGO_SERVERS.map(async (server) => {
        try {
          const response = await fetch(`/api/device/${server.device}/state`, { credentials: 'include' });
          const payload = await response.json();
          if (!response.ok || payload.success === false) throw new Error(payload.error || 'Offline');
          return [server.device, { ok: true, state: String(payload.state || 'UNKNOWN').replace(/^DevState\./, '') }];
        } catch (requestError) {
          return [server.device, { ok: false, state: 'OFFLINE', error: requestError.message }];
        }
      }));
      setHardwareTango(Object.fromEntries(entries));
    } catch (requestError) {
      setHardwareError(requestError.message);
    } finally {
      setHardwareLoading(false);
    }
  }, []);

  const toggleHardwarePower = useCallback(async (channel, enabled) => {
    const outputs = hardwarePower.outputs || [];
    if (!outputs.length) return;
    setHardwareLoading(true);
    setHardwareError('');
    try {
      const nextStates = outputs.map((output) => Number(output.id) === channel.outputId ? (enabled ? 1 : 0) : Number(output.state));
      const response = await fetch('/api/device/manip/SD2/PDU_SD2/command/set_channels_states', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ args: nextStates }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) throw new Error(payload.error || `Could not switch ${channel.label}`);
      await loadHardware();
    } catch (requestError) {
      setHardwareError(requestError.message);
      setHardwareLoading(false);
    }
  }, [hardwarePower.outputs, loadHardware]);

  const setAllHardwarePower = useCallback(async (enabled) => {
    const outputs = hardwarePower.outputs || [];
    if (!outputs.length) return;
    setHardwareLoading(true);
    setHardwareError('');
    try {
      const outputIds = new Set(VD2_POWER_CHANNELS.map((channel) => channel.outputId));
      const nextStates = outputs.map((output) => outputIds.has(Number(output.id)) ? (enabled ? 1 : 0) : Number(output.state));
      const response = await fetch('/api/device/manip/SD2/PDU_SD2/command/set_channels_states', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ args: nextStates }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) throw new Error(payload.error || 'Could not switch VD2 power');
      await loadHardware();
    } catch (requestError) {
      setHardwareError(requestError.message);
      setHardwareLoading(false);
    }
  }, [hardwarePower.outputs, loadHardware]);

  const controlHardwareServer = useCallback(async (server, action) => {
    setHardwareLoading(true);
    setHardwareError('');
    try {
      const response = await fetch('/api/server/control', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({ action, device_name: server.device }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) throw new Error(payload.error || `Could not ${action} ${server.label}`);
      await loadHardware();
      await loadState();
    } catch (requestError) {
      setHardwareError(requestError.message);
      setHardwareLoading(false);
    }
  }, [loadHardware, loadState]);

  useEffect(() => {
    if (hardwareOpen) loadHardware();
  }, [hardwareOpen, loadHardware]);

  useEffect(() => {
    if (activeTab === 'hardware' && state?.connected && state?.application_running) {
      runCommand('RefreshStatus');
    }
  }, [activeTab, runCommand, state?.application_running, state?.connected]);
  const updateLutRange = useCallback((bound, value) => {
    setLutRange((previous) => {
      if (bound === 'minimum') {
        return { ...previous, minimum: Math.min(value, previous.maximum - 1) };
      }
      return { ...previous, maximum: Math.max(value, previous.minimum + 1) };
    });
  }, []);
  const autoscaleLut = useCallback(() => {
    if (!preview) return;
    setLutRange({
      minimum: clamp(Number(preview.minimum) || 0, 0, 254),
      maximum: clamp(Number(preview.maximum) || 255, 1, 255),
    });
  }, [preview]);
  const previewPoint = useCallback((event) => {
    const box = previewOverlay.current?.getBoundingClientRect();
    if (!box || !preview) return null;
    return {
      x: clamp(Math.round((event.clientX - box.left) * preview.width / box.width), 0, preview.width - 1),
      y: clamp(Math.round((event.clientY - box.top) * preview.height / box.height), 0, preview.height - 1),
    };
  }, [preview]);
  const constrainRoi = useCallback((roi) => {
    if (!preview) return roi;
    if (roi.type === 'vertical') return { ...roi, y0: 0, y1: preview.height - 1 };
    if (roi.type === 'horizontal') return { ...roi, x0: 0, x1: preview.width - 1 };
    return roi;
  }, [preview]);
  const beginRoi = useCallback((event) => {
    if (!preview || event.button !== 0) return;
    const selected = event.target.dataset.roiId;
    if (selected) {
      setSelectedRoiId(selected);
      return;
    }
    const point = previewPoint(event);
    if (!point) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrawingRoi(constrainRoi({ type: roiTool, x0: point.x, y0: point.y, x1: point.x, y1: point.y }));
  }, [constrainRoi, preview, previewPoint, roiTool]);
  const updateRoi = useCallback((event) => {
    if (!drawingRoi) return;
    const point = previewPoint(event);
    if (point) setDrawingRoi((roi) => constrainRoi({ ...roi, x1: point.x, y1: point.y }));
  }, [constrainRoi, drawingRoi, previewPoint]);
  const completeRoi = useCallback((event) => {
    if (!drawingRoi || !preview) return;
    const point = previewPoint(event);
    const roi = constrainRoi({ ...drawingRoi, x1: point?.x ?? drawingRoi.x1, y1: point?.y ?? drawingRoi.y1 });
    const bounds = roiBounds(roi, preview.width, preview.height);
    const tooSmall = roi.type === 'vertical'
      ? bounds.x1 - bounds.x0 < 2
      : roi.type === 'horizontal'
        ? bounds.y1 - bounds.y0 < 2
        : bounds.x1 - bounds.x0 < 2 || bounds.y1 - bounds.y0 < 2;
    setDrawingRoi(null);
    if (tooSmall) return;
    const id = `roi-${nextRoiId.current++}`;
    setRois((current) => [...current, { ...roi, id }]);
    setSelectedRoiId(id);
  }, [constrainRoi, drawingRoi, preview, previewPoint]);
  const removeRoi = useCallback((id) => {
    setRois((current) => current.filter((roi) => roi.id !== id));
    setSelectedRoiId((current) => current === id ? null : current);
  }, []);
  const selectedRoi = rois.find((roi) => roi.id === selectedRoiId) || null;
  const values = state?.values || {};
  const statusClass = state?.state === 'ON' || state?.state === 'RUNNING' ? 'online' : 'offline';

  return (
    <main className="vd2-page">
      <header className="vd2-header">
        <div>
          <p className="vd2-eyebrow">VOD-VD</p>
          <h1>Pump probe VD2</h1>
          <p className="vd2-subtitle">Streak-camera control and timing configuration</p>
        </div>
        <div className="vd2-statuses" aria-live="polite">
          <span className={`vd2-status ${statusClass}`}>Tango {state?.state || 'OFFLINE'}</span>
          <span className={`vd2-status ${state?.connected ? 'online' : 'offline'}`}>RemoteEx {state?.connected ? 'connected' : 'disconnected'}</span>
          <span className={`vd2-status ${state?.application_running ? 'online' : 'offline'}`}>HPD-TA {state?.application_running ? 'running' : 'stopped'}</span>
        </div>
        <div className="vd2-header-actions">
          <button type="button" onClick={() => setHardwareOpen(true)} disabled={busy}>Hardware</button>
          <button type="button" onClick={loadState} disabled={busy}>Refresh</button>
          <button type="button" onClick={() => runCommand('Connect')} disabled={busy}>Connect</button>
          <button type="button" onClick={() => runCommand('StartApplication')} disabled={busy}>Start HPD-TA</button>
          <button type="button" className="vd2-stop" onClick={() => runCommand('StopApplication')} disabled={busy || !state?.application_running}>Close HPD-TA</button>
          <button type="button" className="vd2-stop" onClick={() => runCommand('ShutdownRemoteEx')} disabled={busy || !state?.connected}>Stop RemoteEx</button>
          <button type="button" onClick={() => runCommand('Disconnect')} disabled={busy}>Disconnect</button>
        </div>
      </header>

      {error && <div className="vd2-error" role="alert">{error}</div>}

      <div className="vd2-tabs" role="tablist" aria-label="VD2 control views">
        <button type="button" role="tab" aria-selected={activeTab === 'acquisition'} className={activeTab === 'acquisition' ? 'is-active' : ''} onClick={() => setActiveTab('acquisition')}>Acquisition</button>
        <button type="button" role="tab" aria-selected={activeTab === 'hardware'} className={activeTab === 'hardware' ? 'is-active' : ''} onClick={() => setActiveTab('hardware')}>Hardware setup</button>
      </div>

      {activeTab === 'acquisition' && (
        <section className="vd2-control-strip" aria-label="Acquisition controls">
          <div className="vd2-acquisition-fields">
            {ACQUISITION_FIELDS.map((field) => (
              <label key={field.key}>
                <span>{field.label}</span>
                <EditableField field={field} value={values[field.key]} onApply={writeParameter} busy={busy} />
              </label>
            ))}
          </div>
          <div className="vd2-acquisition-actions">
            <button
              type="button"
              onClick={() => runCommand('StartLive')}
              disabled={busy || !state?.application_running || state?.remoteex_status === 'starting'}
            >
              Live
            </button>
            <button type="button" onClick={() => runCommand('AcquireSingle')} disabled={busy}>Single</button>
            <button type="button" onClick={() => runCommand('Acquire')} disabled={busy}>Acquire</button>
            <button type="button" onClick={() => runCommand('StartSequence')} disabled={busy}>Sequence</button>
            <button type="button" className="vd2-stop" onClick={() => runCommand('StopAcquisition')} disabled={busy}>Stop</button>
          </div>
          <div className="vd2-remote-details">
            <span>RemoteEx status</span>
            <strong>{state?.remoteex_status || '-'}</strong>
            <span>Device</span>
            <code>{state?.device || 'manip/camera/hamamatsu_streak_main'}</code>
          </div>
        </section>
      )}

      {activeTab === 'acquisition' && (
        <section className="vd2-preview" aria-label="Live streak-camera preview">
          <LutControl
            palette={lutPalette}
            range={lutRange}
            preview={preview}
            onPaletteChange={setLutPalette}
            onRangeChange={updateLutRange}
            onAutoscale={autoscaleLut}
          />
          <header>
            <div>
              <h2>Live image</h2>
              <p>C13440-20CU display frame</p>
            </div>
            <div className="vd2-preview-meta">
              <span>{preview ? `${preview.width} x ${preview.height}` : 'Waiting for frame'}</span>
              {preview && <span>{preview.minimum} - {preview.maximum}</span>}
              <button type="button" onClick={() => { setPreviewEnabled(true); loadPreview(); }} disabled={busy}>Refresh frame</button>
            </div>
          </header>
          {previewError && <div className="vd2-preview-error" role="alert">{previewError}</div>}
          <div className="vd2-roi-tools" aria-label="ROI tools">
            <span>ROI integration</span>
            {Object.entries(ROI_TOOLS).map(([tool, definition]) => (
              <button
                type="button"
                key={tool}
                className={roiTool === tool ? 'is-active' : ''}
                onClick={() => setRoiTool(tool)}
                title={`${definition.profile} ROI`}
              >
                {definition.label}
              </button>
            ))}
            <span className="vd2-roi-hint">Drag on image. Select an ROI to view its profile.</span>
            <button type="button" className="vd2-roi-clear" onClick={() => { setRois([]); setSelectedRoiId(null); }} disabled={!rois.length}>Clear</button>
          </div>
          <div className="vd2-preview-canvas-wrap">
            <div className="vd2-image-stage">
              <canvas ref={previewCanvas} className="vd2-preview-canvas" />
              {preview && (
                <svg
                  ref={previewOverlay}
                  className="vd2-roi-overlay"
                  viewBox={`0 0 ${preview.width} ${preview.height}`}
                  onPointerDown={beginRoi}
                  onPointerMove={updateRoi}
                  onPointerUp={completeRoi}
                  onPointerCancel={() => setDrawingRoi(null)}
                >
                  {[...rois, ...(drawingRoi ? [{ ...drawingRoi, id: 'drawing' }] : [])].map((roi, index) => {
                    const bounds = roiBounds(roi, preview.width, preview.height);
                    const definition = ROI_TOOLS[roi.type];
                    const selected = roi.id === selectedRoiId;
                    return (
                      <g key={roi.id} className={selected ? 'is-selected' : ''}>
                        <rect
                          data-roi-id={roi.id === 'drawing' ? undefined : roi.id}
                          x={bounds.x0}
                          y={bounds.y0}
                          width={Math.max(1, bounds.x1 - bounds.x0 + 1)}
                          height={Math.max(1, bounds.y1 - bounds.y0 + 1)}
                          stroke={definition.color}
                        />
                        {roi.id !== 'drawing' && <text x={bounds.x0 + 4} y={bounds.y0 + 15} fill={definition.color}>{index + 1}</text>}
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
          </div>
          <section className="vd2-roi-analysis" aria-label="ROI analysis">
            <aside className="vd2-roi-list">
              <header><strong>Regions</strong><span>{rois.length}</span></header>
              {rois.length === 0 && <p>No regions</p>}
              {rois.map((roi, index) => {
                const definition = ROI_TOOLS[roi.type];
                return (
                  <div className={`vd2-roi-row ${roi.id === selectedRoiId ? 'is-selected' : ''}`} key={roi.id}>
                    <button type="button" className="vd2-roi-select" onClick={() => setSelectedRoiId(roi.id)}>
                      <i style={{ background: definition.color }} />
                      <span>{index + 1}. {definition.label}</span>
                    </button>
                    <button type="button" className="vd2-roi-remove" title={`Remove ROI ${index + 1}`} aria-label={`Remove ROI ${index + 1}`} onClick={() => removeRoi(roi.id)}>×</button>
                  </div>
                );
              })}
            </aside>
            <RoiProfiles preview={preview} roi={selectedRoi} />
          </section>
        </section>
      )}

      {activeTab === 'hardware' && (
        <>
          <div className="vd2-hardware-actions">
            <button
              type="button"
              onClick={() => runCommand('RefreshStatus')}
              disabled={busy || !state?.application_running || state?.remoteex_status === 'busy'}
            >
              Read hardware
            </button>
          </div>
          <section className="vd2-grid" aria-label="Hardware setup">
            {CARDS.map((card) => (
              <ParameterCard card={card} values={values} onApply={writeParameter} busy={busy} key={card.title} />
            ))}
          </section>
        </>
      )}
      <Vd2HardwareModal
        open={hardwareOpen}
        power={hardwarePower}
        tango={hardwareTango}
        loading={hardwareLoading}
        error={hardwareError}
        onClose={() => setHardwareOpen(false)}
        onRefresh={loadHardware}
        onToggle={toggleHardwarePower}
        onAllPower={setAllHardwarePower}
        onServer={controlHardwareServer}
      />
    </main>
  );
}

export default PumpProbeVD2;
