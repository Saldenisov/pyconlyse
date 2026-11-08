import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from './api/csrfRequest';
import VD2ConversionQueue from './components/VD2ConversionQueue';
import VD2FolderPicker from './components/VD2FolderPicker';
import ServerSessionPicker from './components/ServerSessionPicker';
import { cleanServerPath, manifestTreatmentUrl, serverPathParent } from './serverPaths';
import { exposureMilliseconds, plannedRunFolder, protocolHardwareBusy, treatmentFolderUrl } from './vd2AlignmentMath';

const API_BASE = '/api/pump-probe-vd2';

export function fetchVd2(url, options = {}) {
  return fetchWithHardwareApproval(url, options);
}

export async function refreshVd2Passive(loadState, loadStartupReadiness) {
  await loadState();
  await loadStartupReadiness();
}

export const TIME_RANGES = [
  '0.5 ns', '1 ns', '2 ns', '5 ns', '10 ns', '20 ns', '50 ns', '100 ns',
  '200 ns', '500 ns', '1 us', '2 us', '5 us', '10 us', '20 us', '50 us',
  '100 us', '200 us', '500 us', '1 ms', '2 ms',
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
      { key: 'live_exposure_time', label: 'Live exposure', type: 'number', min: 1, step: 1, unit: 'ms', duration: true },
      { key: 'acquire_exposure_time', label: 'Acquire exposure', type: 'number', min: 1, step: 1, unit: 'ms', duration: true },
      { key: 'analog_integration_count', label: 'Integrations', type: 'number', min: 1, step: 1 },
      { key: 'sequence_loops', label: 'Sequence loops', type: 'number', min: 1, step: 1 },
    ],
  },
  {
    title: 'DG645 delay generator',
    subtitle: 'A = T0 + 2.0417 ms; E follows the calibrated Time range. Gates unchanged.',
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

const PHASE_PROTOCOLS = {
  BRUIT: {
    label: 'Bruit',
    file: 'BRUIT.his',
    instruction: 'Close beam. You have 10 s to prepare. Press Space to start immediately.',
    preparationSeconds: 10,
    tone: 'bruit',
  },
  BASE: {
    label: 'Base',
    file: 'BASE.his',
    instruction: 'Close Faraday cup, then start.',
    preparationSeconds: 0,
    tone: 'base',
  },
  ABSORPTION: {
    label: 'Absorption',
    file: 'ABS.his',
    instruction: 'Open Faraday cup, then start.',
    preparationSeconds: 0,
    tone: 'absorption',
  },
};

function valueText(value) {
  return value === null || value === undefined || value === '' ? '-' : String(value);
}

function defaultVd2RunName() {
  const now = new Date();
  const date = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('');
  const time = [now.getHours(), now.getMinutes(), now.getSeconds()].map((value) => String(value).padStart(2, '0')).join('');
  return `VD2_${date}_${time}`;
}

export function EditableField({ field, value, onApply, busy }) {
  const displayValue = field.duration ? exposureMilliseconds(value) : valueText(value);
  const [draft, setDraft] = useState(displayValue);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) {
      setDraft(displayValue);
    }
  }, [editing, displayValue]);

  if (field.readOnly) {
    return <output id={`vd2-${field.key}`} className="vd2-readonly">{valueText(value)}</output>;
  }

  const apply = () => {
    if (draft !== displayValue) {
      onApply(field.key, field.duration ? `${draft} ms` : draft);
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
            setDraft(displayValue);
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
  if (!canvas || !preview?.pixels_b64) return false;
  const { width, height } = preview;
  const encoded = window.atob(preview.pixels_b64);
  if (encoded.length !== width * height) return false;

  const lut = buildLut(palette, minimum, maximum);
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { alpha: false });
  if (!context) return false;
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
  return true;
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

const ROI_COLORS = ['#ffe176', '#70e7ff', '#f38fb9', '#9ee480', '#c6a0ff', '#ffab70'];

const roiColor = index => ROI_COLORS[index % ROI_COLORS.length];

export function updateRoisFromBounds(rois, id, next, linked, width, height) {
  const selected = rois.find(roi => roi.id === id);
  if (!selected) return rois;
  const old = roiBounds(selected, width, height);
  if (linked && next.x0 - old.x0 === next.x1 - old.x1 && next.y0 - old.y0 === next.y1 - old.y1) {
    const movableX = rois.filter(roi => roi.type !== 'horizontal').map(roi => roiBounds(roi, width, height));
    const movableY = rois.filter(roi => roi.type !== 'vertical').map(roi => roiBounds(roi, width, height));
    const dx = movableX.length ? clamp(next.x0 - old.x0, -Math.min(...movableX.map(b => b.x0)), width - 1 - Math.max(...movableX.map(b => b.x1))) : 0;
    const dy = movableY.length ? clamp(next.y0 - old.y0, -Math.min(...movableY.map(b => b.y0)), height - 1 - Math.max(...movableY.map(b => b.y1))) : 0;
    return rois.map(roi => ({ ...roi, x0: roi.x0 + (roi.type === 'horizontal' ? 0 : dx), x1: roi.x1 + (roi.type === 'horizontal' ? 0 : dx),
      y0: roi.y0 + (roi.type === 'vertical' ? 0 : dy), y1: roi.y1 + (roi.type === 'vertical' ? 0 : dy) }));
  }
  return rois.map(roi => {
    if (roi.id === id) return { ...roi, ...roiBounds(next, width, height) };
    if (!linked) return roi;
    const bounds = roiBounds(roi, width, height);
    const adjusted = Object.fromEntries(Object.keys(bounds).map(key => [key, bounds[key] + next[key] - old[key]]));
    if (roi.type === 'vertical') { adjusted.y0 = 0; adjusted.y1 = height - 1; }
    if (roi.type === 'horizontal') { adjusted.x0 = 0; adjusted.x1 = width - 1; }
    return { ...roi, ...roiBounds(adjusted, width, height) };
  });
}

function ProfilePlot({ title, series, axis, selectedId, onSelect, scale }) {
  const container = useRef(null);
  const [size, setSize] = useState({ width: 600, height: 400 });
  useEffect(() => {
    container.current.style.removeProperty('height');
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setSize({ width, height });
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [scale]);
  const { width, height } = size;
  const padding = { left: 42, right: 12, top: 14, bottom: 30 };
  const points = series.flatMap(trace => trace.points);
  const minimum = Math.min(...points.map(p => p.y));
  const maximum = Math.max(...points.map(p => p.y));
  const xmin = Math.min(...points.map(p => p.x));
  const xmax = Math.max(...points.map(p => p.x));
  const span = Math.max(1, maximum - minimum);
  const graphWidth = width - padding.left - padding.right;
  const graphHeight = height - padding.top - padding.bottom;
  const px = x => padding.left + (x - xmin) / (xmax - xmin || 1) * graphWidth;
  const py = y => padding.top + (1 - (y - minimum) / span) * graphHeight;

  return (
    <section className="vd2-profile" aria-label={title}>
      <header><strong>{title}</strong><span>{minimum.toFixed(1)} - {maximum.toFixed(1)}</span></header>
      <div className="vd2-roi-legend" aria-label={`${title} regions`}>
        {series.map(trace => <button type="button" key={trace.id} aria-pressed={trace.id === selectedId}
          style={{ color: trace.color }} onClick={() => onSelect?.(trace.id)}>ROI {trace.index + 1}</button>)}
      </div>
      <div ref={container} className="vd2-profile-plot" style={{ aspectRatio: `3 / ${2 * scale}` }}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title} dynamic profile`}>
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} />
        {Array.from({ length: 7 }, (_, i) => {
          const value = minimum + span * i / 6;
          return <g key={i}><line x1={padding.left - 4} y1={py(value)} x2={width - padding.right} y2={py(value)} className="vd2-roi-grid" />
            <text x={padding.left - 7} y={py(value) + 3} textAnchor="end">{value.toFixed(1)}</text></g>;
        })}
        {series.map(trace => <polyline key={trace.id} role="button" tabIndex="0"
          aria-label={`ROI ${trace.index + 1} ${title.toLowerCase()}`} aria-pressed={trace.id === selectedId}
          points={trace.points.map(p => `${px(p.x).toFixed(1)},${py(p.y).toFixed(1)}`).join(' ')}
          stroke={trace.color} style={{ strokeWidth: trace.id === selectedId ? 2.5 : 1.5 }}
          onClick={() => onSelect?.(trace.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect?.(trace.id); } }} />)}
        <text x={padding.left} y={height - 6}>{axis}</text>
        <text x={padding.left} y={height - 17}>{xmin}</text><text x={width - padding.right} y={height - 17} textAnchor="end">{xmax}</text>
      </svg>
      </div>
    </section>
  );
}

export function RoiProfiles({ preview, rois, selectedId, onSelect }) {
  const [scale, setScale] = useState(1);
  const profiles = useMemo(() => rois.map((roi, index) => ({ roi, index, profile: roiProfiles(preview, roi) }))
    .filter(item => item.profile), [preview, rois]);
  if (!profiles.length) {
    return <div className="vd2-profile-empty">Draw an ROI, then select it to inspect its live profile.</div>;
  }
  const traces = (kind, excluded, offset) => profiles.filter(item => item.roi.type !== excluded).map(({ roi, index, profile }) => ({
    id: roi.id, index, color: roiColor(index), points: profile[kind].map((y, i) => ({ x: profile.bounds[offset] + i, y })),
  }));
  const spectra = traces('spectrum', 'vertical', 'x0');
  const kinetics = traces('kinetics', 'horizontal', 'y0');
  return (
    <div className="vd2-profiles">
      <label className="vd2-profile-height">Plot height<input aria-label="ROI plot height" type="range" min="0.75" max="2" step="0.05" value={scale} onChange={event => setScale(Number(event.target.value))} /></label>
      {spectra.length > 0 && <ProfilePlot title="Spectrum" series={spectra} axis="camera X, px" selectedId={selectedId} onSelect={onSelect} scale={scale} />}
      {kinetics.length > 0 && <ProfilePlot title="Kinetics" series={kinetics} axis="camera Y, px" selectedId={selectedId} onSelect={onSelect} scale={scale} />}
    </div>
  );
}

function phaseProgress(job) {
  if (job?.status === 'processing') return { label: `Process ${job.process_percent ?? 0}%`, percent: job.process_percent ?? 0, processing: true };
  if (job?.status === 'queued') return { label: 'H5 queued', percent: 0, processing: true };
  if (job?.status === 'saving') return { label: 'Saving HIS', percent: 100 };
  if (job?.status !== 'acquiring') return null;
  const started = Date.parse(job.capture_started_at), rate = Number.parseFloat(job.capture_rate);
  if (!Number.isFinite(started) || !(rate > 0) || !job.frames_per_his) return { label: 'ACQ …', percent: 0 };
  const percent = Math.min(99, Math.max(0, Math.floor((Date.now() - started) * rate / (10 * job.frames_per_his))));
  return { label: `ACQ ≈${percent}%`, percent };
}

export function Vd2PhaseProtocol({ protocol, settings, disabled, settingsDisabled=disabled, onChange, onPhaseClick, onPhaseDoubleClick, project, sampleHolder, serverWorkspace, onMeasure, measurementUnavailable, measuring, measurementMessage }) {
  const active = protocolHardwareBusy(protocol);
  const [folderMenu, setFolderMenu] = useState(null);
  const actualFolder = protocol?.sample_folder || protocol?.his_path?.replace(/[\\/][^\\/]+$/, '') || plannedRunFolder(settings);
  const treatmentUrl=folder=>protocol?.is_replacement&&protocol?.manifest_path&&folder===actualFolder
    ?`/datatreatment?${new URLSearchParams({profile:'VD2',manifest:protocol.manifest_path})}`:treatmentFolderUrl(folder);
  const sampleRecord=project?.samples?.find(sample=>sample.name===settings.runName);
  const boundBruit=sampleRecord?.bruit_reference||sampleRecord?.pending_bruit_reference;
  const boundSource = project?.bruit_options?.find(item => item.id === boundBruit);
  const needsSampleBruit = settings.reuseBruit === 'none' && boundSource?.sample !== settings.runName;
  useEffect(() => {
    if (!folderMenu) return undefined;
    const close = () => setFolderMenu(null);
    const onKey = e => { if (e.key === 'Escape') close(); };
    window.addEventListener('click', close);
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('click', close); window.removeEventListener('keydown', onKey); };
  }, [folderMenu]);
  const openFolderMenu = (event, folder) => {
    event.preventDefault();
    setFolderMenu({ x: Math.min(event.clientX, window.innerWidth - 225), y: Math.min(event.clientY, window.innerHeight - 50), folder });
  };
  return (
    <section className="vd2-phase-protocol" aria-label="VD2 Bruit Base Absorption protocol">
      <header>
        <div>
          <h2>Measurement protocol</h2>
        </div>
        <div className={`vd2-protocol-state is-${protocol?.status || 'idle'}`}>
          {active ? `${protocol.phase_label || protocol.phase} ${protocol.status}` : (protocol?.status || 'idle')}
        </div>
      </header>
      {serverWorkspace&&<div className="vd2-server-workspace">
        <ServerSessionPicker load={serverWorkspace.history} onRestore={serverWorkspace.restore} disabled={settingsDisabled||active} />
        {serverWorkspace.error?<small role="alert">{serverWorkspace.error}</small>:<small role="status">{serverWorkspace.message||'This window has its own session.'}</small>}
      </div>}
      <div className="vd2-protocol-settings">
        <div className="vd2-project-folder" onContextMenu={event => openFolderMenu(event, plannedRunFolder(settings))}>
          <span>Everest folder</span>
          <VD2FolderPicker value={settings.outputRoot} disabled={settingsDisabled || active} onChange={value=>onChange('outputRoot',value)} />
        </div>
        <label>
          <span>Sample name</span>
          <input value={settings.runName} disabled={settingsDisabled || active} onChange={(event) => onChange('runName', event.target.value)} />
        </label>
      </div>
      <div className="vd2-protocol-settings vd2-sample-details">
        <label><span>Sample details</span><textarea rows="2" maxLength="4000" placeholder="Optional sample description" value={settings.sampleDescription || ''}
          disabled={settingsDisabled || active} onChange={event => onChange('sampleDescription', event.target.value)} /></label>
        <label><span>Noise Source</span><select value={settings.reuseBruit === 'none' ? 'none' : 'latest'} disabled={settingsDisabled || active}
          onChange={event => onChange('reuseBruit', event.target.value)}>
          <option value="latest">Latest completed Bruit in project</option>
          <option value="none">Bruit for each sample</option>
        </select></label>
      </div>
      <div className="vd2-phase-buttons">
        {onMeasure && <button type="button" className="vd2-measure-button" disabled={disabled || active || measuring || measurementUnavailable || protocol?.queue_full}
          onClick={onMeasure}>Do Measurement</button>}
        {Object.entries(PHASE_PROTOCOLS).map(([phase, definition]) => {
          const latest = protocol?.phase === phase && protocol.sample_name === settings.runName ? protocol
            : protocol?.processing_jobs?.findLast(job => job.phase === phase && job.sample_name === settings.runName);
          const progress = phaseProgress(latest);
          return (
          <button
            type="button"
            key={phase}
            className={`vd2-phase-button is-${definition.tone}${progress?.processing ? ' is-processing' : ''}`}
            style={progress ? { '--vd2-phase-progress': `${progress.percent}%` } : undefined}
            title={phase !== 'BRUIT' && needsSampleBruit ? 'Record Bruit for this sample first' : `${definition.label} · ${definition.file}`}
            disabled={disabled || active || measuring || Boolean(protocol?.queue_full) || (phase !== 'BRUIT' && needsSampleBruit)}
            onClick={() => onPhaseClick(phase)}
            onDoubleClick={() => onPhaseDoubleClick(phase)}
          >
            <strong>{definition.label}</strong>
            {progress && <small>{progress.label}</small>}
          </button>
        );})}
        {sampleHolder}
      </div>
      {measurementMessage && <small role="status">{measurementMessage}</small>}
      <VD2ConversionQueue jobs={protocol?.processing_jobs} />
      <details className="vd2-project-history">
        <summary>Previous measurements{project?.samples?.length?` · ${project.samples.length} samples`:''}</summary>
        {protocol?.manifest_path&&serverPathParent(protocol.manifest_path)!==cleanServerPath(settings.outputRoot)&&
          <button type="button" disabled={settingsDisabled||active} onClick={()=>{
            onChange('outputRoot',serverPathParent(protocol.manifest_path));
            if(protocol.sample_name)onChange('runName',protocol.sample_name);
          }}>Open last measured project</button>}
        {!project?.samples?.length&&<p>Choose the project folder to view its saved measurements.</p>}
        {project?.samples?.map(sample=><article key={sample.name}>
          <header><button type="button" disabled={settingsDisabled||active} onClick={()=>{
            onChange('runName',sample.name);onChange('sampleDescription',sample.description||'');
          }}>{sample.name}</button>
          <a target="_blank" rel="noopener noreferrer" href={manifestTreatmentUrl(project.manifest_path,sample.name)}>View in Data Treatment ↗</a></header>
          {(sample.measurements||[]).map(item=><div key={item.id}>
            <strong>{PHASE_PROTOCOLS[item.phase]?.label||item.phase}</strong> · {item.status} · {item.frames} frames
            {item.recorded_at&&<small> · {new Date(item.recorded_at).toLocaleString()}</small>}{!item.selected&&<small> · previous version</small>}
            {item.error&&<span role="alert"> · {item.error}</span>}
          </div>)}
          {!sample.ready&&<small>{sample.error}</small>}
        </article>)}
      </details>
      {protocol?.queue_full&&<small role="status">H5 conversion queue is full. Wait for one conversion to finish.</small>}
      {protocol?.his_path && (
        <footer>
          <a target="_blank" rel="noopener noreferrer" href={treatmentUrl(actualFolder)} onContextMenu={event => openFolderMenu(event, actualFolder)} title={actualFolder}>Run folder ↗</a>
          {protocol.h5_path && <span>{protocol.frame_count} frames · {protocol.lossless_verified===false?'H5 verification failed':'Lossless H5 verified'}
            {protocol.source_his_retained === false ? ' · HIS removed'
              : protocol.source_his_cleanup_pending ? ' · Removing HIS…'
                : protocol.source_his_retained === true ? ' · HIS retained' : ''}</span>}
          {protocol.manifest_path && <a target="_blank" rel="noopener noreferrer" href={manifestTreatmentUrl(protocol.manifest_path)}>Project manifest ↗</a>}
          <details><summary>Files</summary>{protocol.source_his_retained !== false && <span>{protocol.his_path}</span>}{protocol.h5_path && <span>{protocol.h5_path}</span>}</details>
          {protocol.error && <strong>{protocol.error}</strong>}
          {protocol.cleanup_warning && <strong role="alert">{protocol.cleanup_warning}</strong>}
        </footer>
      )}
      {folderMenu && <div className="vd2-folder-menu" role="menu" style={{ left: folderMenu.x, top: folderMenu.y }}>
        <a role="menuitem" target="_blank" rel="noopener noreferrer" href={treatmentUrl(folderMenu.folder)}>Open in Data Treatment</a>
      </div>}
    </section>
  );
}

function Vd2PhaseDialog({ prepared, remaining, starting, onCancel, onStart }) {
  if (!prepared) return null;
  const definition = PHASE_PROTOCOLS[prepared.phase];
  return (
    <div className="vd2-modal-backdrop" onClick={()=>{if(!starting)onCancel();}}>
      <section className="vd2-phase-dialog" role="dialog" aria-modal="true" tabIndex="-1" onClick={(event) => event.stopPropagation()} aria-label={`${definition.label} preparation`}>
        <header><h2>{definition.label}</h2><button type="button" disabled={starting} onClick={onCancel}>Cancel</button></header>
        <p>{definition.instruction}</p>
        {remaining > 0 && <strong className="vd2-countdown">{remaining} s</strong>}
        <footer>
          <button type="button" disabled={starting} onClick={onCancel}>Cancel</button>
          <button type="button" data-vd2-phase-start onClick={() => onStart(prepared.phase)} disabled={starting}>Start (Space)</button>
        </footer>
      </section>
    </div>
  );
}

function Vd2RepeatDialog({conflict,starting,onCancel,onChoose}) {
  const dialog=useRef(null),latest=useRef(null),opened=Boolean(conflict);
  latest.current={starting,onCancel};
  useEffect(()=>{
    if(!opened)return undefined;
    const previous=document.activeElement;
    dialog.current?.querySelector('footer button:last-child')?.focus();
    const onKey=event=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();if(!latest.current.starting)latest.current.onCancel();}
      if(event.key==='Tab') {
        const buttons=Array.from(dialog.current?.querySelectorAll('button:not(:disabled)')||[]);
        const index=buttons.indexOf(document.activeElement);
        event.preventDefault();(buttons[(index+(event.shiftKey?-1:1)+buttons.length)%buttons.length]||dialog.current)?.focus();
      }
    };
    document.addEventListener('keydown',onKey,true);
    return()=>{document.removeEventListener('keydown',onKey,true);if(previous?.isConnected)previous.focus();};
  },[opened]);
  if(!conflict)return null;
  const label=PHASE_PROTOCOLS[conflict.body.phase].label;
  return <div className="vd2-modal-backdrop" onClick={()=>{if(!starting)onCancel();}}>
    <section ref={dialog} tabIndex="-1" role="dialog" aria-modal="true" aria-label={`Repeat ${label}`} className="vd2-phase-dialog vd2-repeat-dialog" onClick={event=>event.stopPropagation()}>
      <h2>{label} already exists</h2><p>{conflict.body.run_name} · {conflict.body.frames_per_his} frames</p>
      <p>Overwrite this phase, or record in a new numbered folder?</p>
      <small>Previous versions remain in history. A new folder starts a separate sample run.</small>
      <footer><button type="button" disabled={starting} onClick={onCancel}>Cancel</button>
        <button type="button" disabled={starting} onClick={()=>onChoose(conflict.plan.choices.new_folder)}>New folder: {conflict.plan.choices.new_folder.run_name}</button>
        <button type="button" disabled={starting} onClick={()=>onChoose(conflict.plan.choices.replace)}>Overwrite {label}</button></footer>
    </section>
  </div>;
}

export {
  API_BASE, CARDS, PHASE_PROTOCOLS, valueText, defaultVd2RunName, ParameterCard,
  LUT_PALETTES, ROI_TOOLS, clamp, rainbowColor, buildLut, drawPreview, LutControl,
  roiBounds, decodePreviewPixels, roiProfiles, ROI_COLORS, roiColor, ProfilePlot,
  phaseProgress, Vd2PhaseDialog, Vd2RepeatDialog,
};
