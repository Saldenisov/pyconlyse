import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchWithCsrfToken, fetchWithHardwareApproval } from './api/csrfRequest';
import VD2TranslationStages, { VD2SampleHolder } from './components/VD2TranslationStages';
import VD2PDUControl from './components/VD2PDUControl';
import VD2RoiEditor from './components/VD2RoiEditor';
import VD2LiveAverage from './components/VD2LiveAverage';
import VD2ConversionQueue from './components/VD2ConversionQueue';
import VD2FolderPicker from './components/VD2FolderPicker';
import ServerSessionPicker from './components/ServerSessionPicker';
import useVd2ServerWorkspace from './useVd2ServerWorkspace';
import {workspaceHeaders} from './browserWorkspaceIdentity';
import { cleanServerPath, manifestTreatmentUrl, serverPathParent } from './serverPaths';
import VD2ReadDiagnostics, { DEFERRED_ACQUISITION_READ } from './components/VD2ReadDiagnostics';
import FrameDisplayRate from './components/FrameDisplayRate';
import useFrameDisplayRate from './useFrameDisplayRate';
import { AlignmentSignalBuffer } from './vd2AlignmentSearch';
import { startPreviewPolling } from './vd2PreviewPolling';
import { createPreviewFreshnessClock } from './vd2PreviewFreshness';
import { alignmentRegionFromBounds, alignmentRegionGeometry } from './vd2RoiMath';
import {ALIGNMENT_REGION_KEY,DEFAULT_ALIGNMENT_REGION,useVd2Memory,validAcquisitionRois,validAlignmentRegion} from './vd2AlignmentMemory';
import { AlignmentKinetics, AlignmentRegion, VD2AlignmentMagnets } from './components/VD2Alignment';
import { exposureMilliseconds, plannedRunFolder, previewShouldPoll, protocolHardwareBusy, protocolSaveActive, treatmentFolderUrl } from './vd2AlignmentMath';
import './css/PumpProbeVD2.css';

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

function Vd2ErrorTray({ errors, activeErrorId, onPrevious, onNext, onCopy, onDismiss, onClear }) {
  if (!errors.length) return null;
  const activeIndex = Math.max(0, errors.findIndex((entry) => entry.id === activeErrorId));
  const entry = errors[activeIndex];
  return (
    <section className="vd2-error-tray" role="alert" aria-live="assertive">
      <div className="vd2-error-tray-meta">
        <strong>{entry.source}</strong>
        <span>{activeIndex + 1} / {errors.length}</span>
        <time dateTime={new Date(entry.timestamp).toISOString()}>{new Date(entry.timestamp).toLocaleTimeString()}</time>
      </div>
      <pre>{entry.message}</pre>
      <div className="vd2-error-tray-actions">
        <button type="button" onClick={onPrevious} disabled={errors.length < 2} title="Previous error" aria-label="Previous error">&lt;</button>
        <button type="button" onClick={onNext} disabled={errors.length < 2} title="Next error" aria-label="Next error">&gt;</button>
        <button type="button" onClick={() => onCopy(entry.message)} title="Copy error" aria-label="Copy error">Copy</button>
        <button type="button" onClick={() => onDismiss(entry.id)} title="Close this error" aria-label="Close this error">x</button>
        <button type="button" onClick={onClear}>Clear all</button>
      </div>
    </section>
  );
}

function PumpProbeVD2() {
  const [state, setState] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewClock, setPreviewClock] = useState(() => performance.now());
  const [previewAvailable, setPreviewAvailable] = useState(false);
  const previewIdentity = useRef(null);
  const [errors, setErrors] = useState([]);
  const [readFailures, setReadFailures] = useState({});
  const [activeErrorId, setActiveErrorId] = useState(null);
  const [previewError, setPreviewError] = useState('');
  const [alignmentAverage, setAlignmentAverage] = useState(null);
  const previewPaint = useRef({});
  const [liveAverageReadError, setLiveAverageReadError] = useState('');
  const [previewEnabled, setPreviewEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState(() => new URLSearchParams(window.location.search).get('tab') === 'alignment' ? 'alignment' : 'acquisition');
  const [calibration, setCalibration] = useState(null);
  const [calibrationUpdating, setCalibrationUpdating] = useState(false);
  const [calibrationError, setCalibrationError] = useState('');
  const [calibrationAttempt, setCalibrationAttempt] = useState(0);
  const [previewStream, setPreviewStream] = useState('last_frame');
  const [alignmentRegion,setAlignmentRegion,alignmentMemoryError]=useVd2Memory(ALIGNMENT_REGION_KEY,DEFAULT_ALIGNMENT_REGION,validAlignmentRegion,true);
  const [imageRight, setImageRight] = useState(() => {
    try { return window.localStorage.getItem('pyconlyse.vd2.imageRight') === 'true'; } catch (_error) { return false; }
  });
  const [imageWidth, setImageWidth] = useState(() => {
    try { return clamp(Number(window.localStorage.getItem('pyconlyse.vd2.imageWidth')) || 560, 320, 760); } catch (_error) { return 560; }
  });
  const [dragPanel, setDragPanel] = useState(false);
  const [lutPalette, setLutPalette] = useState('rainbow');
  const [lutRange, setLutRange] = useState({ minimum: 0, maximum: 255 });
  const [roiTool, setRoiTool] = useState('vertical');
  const roiMemoryKey=preview?.width>0&&preview?.height>0?`pyconlyse.vd2.acquisition.rois.v1:${preview.width}x${preview.height}`:null;
  const [rois,setRois,roiMemoryError]=useVd2Memory(roiMemoryKey,[],validAcquisitionRois);
  const [linkRois, setLinkRois] = useState(false);
  const [selectedRoiId, setSelectedRoiId] = useState(null);
  const [drawingRoi, setDrawingRoi] = useState(null);
  const [protocol, setProtocol] = useState(null);
  const protocolHardwareActive=protocolHardwareBusy(protocol),protocolSaving=protocolSaveActive(protocol);
  const [projectReadback, setProjectReadback] = useState(null);
  const [projectError, setProjectError] = useState('');
  const [protocolSettings, setProtocolSettings] = useState(() => ({
    framesPerHis: '100',
    outputRoot: 'E:\\DATA_VD2',
    runName: defaultVd2RunName(),
    sampleDescription: '',
    reuseBruit: 'latest',
  }));
  const project = projectReadback?.root === protocolSettings.outputRoot ? projectReadback.data : null;
  const serverWorkspace=useVd2ServerWorkspace(protocolSettings,setProtocolSettings);
  const returnContext=useRef({});
  returnContext.current={view:activeTab,windowId:serverWorkspace.windowId};
  const restoreJob=useRef(new URLSearchParams(window.location.search).get('restore_job'));
  const [preparedPhase, setPreparedPhase] = useState(null);
  const [guidedRun, setGuidedRun] = useState(null);
  const [guidedChoice, setGuidedChoice] = useState(null);
  const [guidedMessage, setGuidedMessage] = useState('');
  const [preparationTick, setPreparationTick] = useState(Date.now());
  const [protocolStarting, setProtocolStarting] = useState(false);
  const protocolStartActive=useRef(false);
  const protocolAlive=useRef(true),phasePlanAbort=useRef(null);
  const [repeatConflict,setRepeatConflict]=useState(null);
  useEffect(()=>{protocolAlive.current=true;return()=>{protocolAlive.current=false;phasePlanAbort.current?.abort();};},[]);
  const alignmentMeasurements = useMemo(() => new AlignmentSignalBuffer(), []);
  const requestActive = useRef(false);
  const stateReadEpoch = useRef(0);
  const protocolRequestActive = useRef(false);
  const previewRequestActive = useRef(false);
  const previewPaused = useRef(false);
  const previewReadComplete = useRef(Promise.resolve());
  const previewFreshness = useMemo(() => createPreviewFreshnessClock(), []);
  const previewController = useRef(null);
  const previewCanvas = useRef(null);
  const previewOverlay = useRef(null);
  const nextRoiId = useRef(1);
  const phaseClickTimer = useRef(null);
  const errorSequence = useRef(0);
  const lastPollError = useRef({ state: '', protocol: '' });

  const reportError = useCallback((message, source = 'Control', scope = null) => {
    const text = String(message || '').trim();
    if (!text) return;
    if (scope) setReadFailures(current => current[scope] === text ? current : { ...current, [scope]: text });
    const id = `${Date.now()}-${++errorSequence.current}`;
    setErrors((current) => [...current, {
      id,
      source,
      scope,
      message: text,
      timestamp: Date.now(),
    }].slice(-50));
    setActiveErrorId(id);
  }, []);

  const resolveReadErrors = useCallback(scope => {
    setReadFailures(current => current[scope] ? { ...current, [scope]: '' } : current);
    setErrors(current => current.some(entry => entry.scope === scope)
      ? current.filter(entry => entry.scope !== scope) : current);
  }, []);

  useEffect(() => {
    const identity=restoreJob.current;
    if(!serverWorkspace.ready||!identity)return undefined;
    let active=true;
    const key=`pyconlyse.vd2.restored-job:${identity}`;
    try {if(window.sessionStorage.getItem(key))return undefined;}catch(_error){/* Restore once for this mount. */}
    (async()=>{
      try {
        const response=await fetch(`${API_BASE}/lifecycle`,{credentials:'include'});
        const payload=await response.json(),job=payload.job;
        if(!response.ok||!payload.success||job?.job_id!==identity||job?.status!=='completed'||!job.result?.restored)throw new Error('Saved camera restoration is no longer the latest completed job; interface unchanged.');
        if(!active)return;
        const ui=job.result.restored.ui;
        if(ui?.form)setProtocolSettings(ui.form);
        setActiveTab(ui?.tab==='alignment'?'alignment':'acquisition');
        restoreJob.current=null;
        try{window.sessionStorage.setItem(key,'1');}catch(_error){/* Current mount still restored. */}
      }catch(cause){if(active){restoreJob.current=null;reportError(cause.message,'Interface restore');}}
    })();
    return()=>{active=false;};
  },[serverWorkspace.ready,reportError]);

  const reportPollError = useCallback((message, request) => {
    const text = String(message || '').trim();
    if (!text || lastPollError.current[request] === text) return;
    lastPollError.current[request] = text;
    reportError(text, 'Background check', request);
  }, [reportError]);

  useEffect(() => {
    if (!errors.length) {
      setActiveErrorId(null);
      return;
    }
    if (!errors.some((entry) => entry.id === activeErrorId)) {
      setActiveErrorId(errors[errors.length - 1].id);
    }
  }, [activeErrorId, errors]);

  const loadState = useCallback(async () => {
    if (requestActive.current || protocolStartActive.current) return;
    requestActive.current = true;
    const epoch = stateReadEpoch.current;
    try {
      const context=returnContext.current;
      const headers={'X-VD2-View':context.view,...(context.windowId?workspaceHeaders(context.windowId):{})};
      const response = await fetch(`${API_BASE}/state`, { credentials: 'include',headers });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read VD2 state');
      if (epoch !== stateReadEpoch.current) return;
      if (payload.state_deferred) {
        setState(current => ({
          ...current, ...payload,
          attribute_errors: { ...current?.attribute_errors, ...payload.attribute_errors },
        }));
        return;
      }
      setState(payload);
      if(payload.recovery_warning)reportPollError(payload.recovery_warning,'recovery');
      else {lastPollError.current.recovery='';resolveReadErrors('recovery');}
      lastPollError.current.state = '';
      if (!Object.keys(payload.attribute_errors || {}).length) resolveReadErrors('state');
    } catch (requestError) {
      if (epoch === stateReadEpoch.current) reportPollError(requestError.message, 'state');
    } finally {
      requestActive.current = false;
    }
  }, [reportPollError, resolveReadErrors]);

  useEffect(() => {
    loadState();
    const interval = window.setInterval(loadState, 2500);
    return () => window.clearInterval(interval);
  }, [loadState]);

  const loadProtocol = useCallback(async () => {
    if (protocolRequestActive.current) return;
    protocolRequestActive.current = true;
    try {
      const response = await fetch(`${API_BASE}/protocol/state`, { credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read VD2 protocol');
      setProtocol(payload);
      lastPollError.current.protocol = '';
      resolveReadErrors('protocol');
    } catch (requestError) {
      reportPollError(requestError.message, 'protocol');
    } finally {
      protocolRequestActive.current = false;
    }
  }, [reportPollError, resolveReadErrors]);

  useEffect(() => {
    loadProtocol();
    const interval = window.setInterval(loadProtocol, 1200);
    return () => window.clearInterval(interval);
  }, [loadProtocol]);

  const projectConversionState=(protocol?.processing_jobs||[]).map(job=>`${job.job_id}:${job.status}`).join('|');
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE}/protocol/project?${new URLSearchParams({ output_root: protocolSettings.outputRoot })}`,
          { credentials: 'include', signal: controller.signal });
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Project manifest unavailable');
        if (!controller.signal.aborted) { setProjectReadback({ root: protocolSettings.outputRoot, data: payload }); setProjectError(''); }
      } catch (error) {
        if (!controller.signal.aborted) { setProjectReadback(null); setProjectError(error.message); }
      }
    }, 450);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [protocolSettings.outputRoot, protocol?.completed_at,protocol?.acquisition_active,projectConversionState]);

  const loadPreview = useCallback(async () => {
    if (previewRequestActive.current || previewPaused.current || protocolStartActive.current) return;
    previewRequestActive.current = true;
    let finishRead;
    previewReadComplete.current = new Promise(resolve => { finishRead = resolve; });
    const controller = new AbortController();
    previewController.current = controller;
    let expired = false;
    const timeout = window.setTimeout(() => { expired = true; controller.abort(); }, 8000);
    const startedAt = performance.now();
    try {
      const response = await fetch(`${API_BASE}/preview`, { credentials: 'include', cache: 'no-store', signal: controller.signal });
      const payload = await response.json();
      if (expired) throw new Error('Live preview read timed out.');
      if (controller.signal.aborted || previewPaused.current) return;
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read live frame');
      if (!payload.frame_available && payload.stream_state === 'waiting_for_frame') return;
      const identity = payload.received_at;
      const previous = previewIdentity.current;
      if (identity && previous && (identity === previous || Date.parse(identity) < Date.parse(previous))) return;
      setPreviewStream(payload.stream_state || 'acquiring');
      setPreviewAvailable(Boolean(payload.frame_available));
      setPreviewError('');
      if (payload.stream_state === 'no_valid_image') {
        setCalibration(null);
        setCalibrationError('');
      }
      if (!payload.frame_available) {
        previewFreshness.invalidate('No current image returned by the server.');
        return;
      }
      const now = performance.now();
      previewFreshness.observe(payload, { serverDate: response.headers?.get?.('Date'), startedAt, receivedAt: now });
      previewIdentity.current = identity;
      setPreviewClock(now);
      setPreview(payload);
      setCalibration(payload.calibration || null);
      setPreviewError('');
    } catch (requestError) {
      if ((controller.signal.aborted && !expired) || previewPaused.current) return;
      const message = expired ? 'Live preview read timed out.' : requestError.message;
      previewFreshness.invalidate(message);
      setPreviewAvailable(false);
      setPreviewError(message);
    } finally {
      window.clearTimeout(timeout);
      previewController.current = null;
      previewRequestActive.current = false;
      finishRead();
    }
  }, [previewFreshness]);

  const previewPolling = previewShouldPoll(activeTab, state, protocol, previewEnabled);
  useEffect(() => {
    if (
      !['acquisition', 'alignment'].includes(activeTab)
      || !previewEnabled
      || (!previewPolling && (!state?.connected || !state?.application_running))
      || protocolSaving
    ) return undefined;
    if (!previewPolling) { loadPreview(); return undefined; }
    const stop = startPreviewPolling(loadPreview);
    return () => { stop(); previewController.current?.abort(); };
  }, [
    activeTab,
    loadPreview,
    previewEnabled,
    state?.application_running,
    state?.connected,
    state?.remoteex_status,
    protocol?.status,
    protocolSaving,
    previewPolling,
  ]);

  useEffect(() => {
    const timer = window.setInterval(() => setPreviewClock(performance.now()), 500);
    return () => { window.clearInterval(timer); previewController.current?.abort(); };
  }, []);
  const previewTiming = previewFreshness.status(previewClock);
  const previewFresh = previewAvailable && !previewError && previewTiming.fresh;
  const previewStride = activeTab === 'alignment' && previewPolling
    && String(state?.acquisition_mode).toLowerCase() === 'live' && alignmentAverage?.enabled
    ? alignmentAverage.frames : 1;
  const { hz: previewHz, frameDisplayed } = useFrameDisplayRate('vd2',
    ['acquisition', 'alignment'].includes(activeTab) && previewEnabled, previewStride);

  useEffect(() => {
    const canvas = previewCanvas.current;
    if (!canvas || !preview) return;
    const paint = previewPaint.current;
    const frame = paint.frame;
    const newFrame = preview !== paint.latest;
    const contextChanged = canvas !== paint.canvas || previewStride !== paint.stride
      || preview.width !== frame?.width || preview.height !== frame?.height
      || preview.calibration_key !== frame?.calibration_key;
    if (newFrame) {
      paint.latest = preview;
      paint.pending = (paint.pending || 0) + 1;
    }
    // Pace the canvas only. Alignment readout still uses the full server stream.
    const next = contextChanged || paint.pending >= previewStride ? preview : frame;
    if (!contextChanged && next === frame && paint.palette === lutPalette && paint.range === lutRange) return;
    if (drawPreview(canvas, next, lutPalette, lutRange.minimum, lutRange.maximum)) {
      if (next === preview) paint.pending = 0;
      Object.assign(paint, { frame: next, canvas, stride: previewStride, palette: lutPalette, range: lutRange });
      canvas.dataset.frameReceivedAt = next.received_at || '';
      canvas.dataset.frameDrawnAt = performance.now().toFixed(3);
      frameDisplayed(next.received_at || next);
    }
  }, [lutPalette, lutRange, preview, previewStride, activeTab, frameDisplayed]);

  useEffect(() => {
    try {
      window.localStorage.setItem('pyconlyse.vd2.imageRight', String(imageRight));
      window.localStorage.setItem('pyconlyse.vd2.imageWidth', String(imageWidth));
    } catch (_error) { /* Keep the in-memory layout. */ }
  }, [imageRight, imageWidth]);

  const calibrationKey = previewAvailable ? preview?.calibration_key : null;
  const calibrationAvailable = Boolean(previewAvailable && preview?.calibration);
  useEffect(() => {
    if (activeTab !== 'alignment' || !calibrationKey || calibrationAvailable
        || !state?.connected || !state?.application_running
        || protocolHardwareActive) return undefined;
    let disposed = false;
    let timer;
    const controller = new AbortController();
    setCalibrationUpdating(true);
    (async () => {
      try {
        const response = await fetchVd2(`${API_BASE}/alignment/calibration`, {
          method: 'POST', credentials: 'include', signal: controller.signal,
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Calibration unavailable');
        if (!disposed) setCalibrationError('');
        if (payload.stream_state === 'no_valid_image') {
          if (!disposed) {
            setPreviewAvailable(false);
            setPreviewStream('no_valid_image');
            setCalibration(null);
            setCalibrationError('');
          }
          return;
        }
        // Only preview may pair axes with a frame; a late response cannot label
        // an old frame with the calibration of a newly selected wavelength.
        if (!disposed) await loadPreview();
      } catch (error) {
        if (!disposed) setCalibrationError(error.message);
      } finally {
        if (!disposed) {
          setCalibrationUpdating(false);
          timer = window.setTimeout(() => setCalibrationAttempt(value => value + 1), 5000);
        }
      }
    })();
    return () => {
      disposed = true;
      controller.abort();
      window.clearTimeout(timer);
      setCalibrationUpdating(false);
    };
  }, [activeTab, calibrationKey, calibrationAvailable, calibrationAttempt, loadPreview,
    state?.connected, state?.application_running, protocolHardwareActive]);
  const alignment = useMemo(() => alignmentRegionGeometry(calibration, alignmentRegion), [calibration, alignmentRegion]);
  const alignmentContext = !alignment.error && preview?.calibration &&
    JSON.stringify([preview.calibration_key, preview.measurement_key || preview.intensity_key, alignmentRegion]);
  const resizeImage = event => {
    event.preventDefault();
    const start = event.clientX;
    const size = imageWidth;
    const move = e => setImageWidth(clamp(size + (e.clientX - start) * (imageRight ? -1 : 1), 320, 760));
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const runRequest = useCallback(async (path, body) => {
    const stopping = ['/command/StopAcquisition', '/command/StopSequence', '/command/StopApplication',
      '/command/ShutdownRemoteEx', '/command/Disconnect'].includes(path);
    const wasPaused = previewPaused.current;
    if (stopping) {
      previewPaused.current = true;
      previewController.current?.abort();
    }
    setBusy(true);
    try {
      const url = `${API_BASE}${path}`;
      const response = await fetchVd2(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        const failure = new Error(payload.error || 'Control request failed');
        if (payload.code === 'READBACK_UNAVAILABLE' && payload.command_acknowledged === true) failure.scope = 'state';
        throw failure;
      }
      setState(payload);
      if (['/command/StartLive', '/command/StartSequence', '/command/Acquire', '/command/AcquireSingle'].includes(path)) {
        previewPaused.current = false;
        setPreviewEnabled(true);
        setPreviewError('');
      }
      if (stopping) {
        stateReadEpoch.current += 1;
        setPreviewEnabled(false);
        setPreviewStream('last_frame');
        setPreviewError('');
      }
    } catch (requestError) {
      if (stopping) {
        if (requestError.scope === 'state') {
          stateReadEpoch.current += 1;
          setPreviewEnabled(false);
          setPreviewStream('last_frame');
        } else {
          previewPaused.current = wasPaused;
        }
      }
      reportError(requestError.message, 'Control', requestError.scope || null);
    } finally {
      setBusy(false);
    }
  }, [reportError]);

  const writeParameter = useCallback((name, value) => runRequest(`/parameter/${name}`, { value }), [runRequest]);
  const runCommand = useCallback((name) => runRequest(`/command/${name}`), [runRequest]);
  const refreshAll = useCallback(async () => {
    setBusy(true);
    try {
      const response = await fetchVd2(`${API_BASE}/refresh`, { method: 'POST', credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Could not reconnect VD2');
      // Ignore state reads started before this verified reconnection. Their
      // late failures must not restore a notification that Refresh resolved.
      stateReadEpoch.current += 1;
      setState(payload);
      lastPollError.current.state = '';
      if (!Object.keys(payload.attribute_errors || {}).length) resolveReadErrors('state');
      resolveReadErrors('connection');
      previewPaused.current = false;
      setPreviewEnabled(true);
      // A connected control link does not prove that the image/axes recovered.
      // Let their own successful reads clear their respective errors.
      await previewReadComplete.current;
      if (payload.connected && payload.application_running) await loadPreview();
      setCalibrationAttempt(value => value + 1);
    } catch (error) {
      reportError(error.message, 'Refresh connection', 'connection');
    } finally {
      setBusy(false);
    }
  }, [loadPreview, reportError, resolveReadErrors]);
  const updateProtocolSetting = useCallback((name, value) => {
    setProtocolSettings((current) => ({ ...current, [name]: value }));
  }, []);

  const startProtocolPhase = useCallback(async (phase,resolution=null) => {
    if(protocolStartActive.current)return;
    protocolStartActive.current=true;
    setProtocolStarting(true);
    try {
      const body=resolution?.body||{
        phase,frames_per_his:protocolSettings.framesPerHis,output_root:protocolSettings.outputRoot,run_name:protocolSettings.runName,
        sample_description:protocolSettings.sampleDescription||'',
        reuse_bruit:guidedRun?.reuse ?? (protocolSettings.reuseBruit==='none'?'none':'latest'),
      };
      let choice=resolution?.choice;
      if(!choice) {
        const abort=new AbortController();phasePlanAbort.current=abort;
        const timer=window.setTimeout(()=>abort.abort(),10000);
        let planned;
        try {planned=await fetchWithCsrfToken(`${API_BASE}/protocol/plan`,{method:'POST',credentials:'include',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
        finally {window.clearTimeout(timer);phasePlanAbort.current=null;}
        if(planned.status===404)throw new Error('Measurement overwrite options need Web reload. No acquisition was started.');
        const plan=await planned.json();
        if(!protocolAlive.current)return;
        if(!planned.ok||!plan.success)throw new Error(plan.error||'Unable to review the measurement folder');
        if (plan.conflict && guidedRun) {
          if (guidedRun.jobs.length || !plan.choices?.new_folder) throw new Error('This phase destination changed. Review the project before continuing.');
          choice = plan.choices.new_folder;
        } else if(plan.conflict) {setPreparedPhase(null);setRepeatConflict({body,plan});return;}
        else choice=plan.choices?.record;
      }
      if(!choice?.token)throw new Error('A reviewed acquisition destination is required');
      const url = `${API_BASE}/protocol/start`;
      const options = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({...body,destination_token:choice.token}),
      };
      let response, payload;
      for (let attempt = 0; attempt <= 3; attempt += 1) {
        if (!protocolAlive.current) return;
        response = await fetchVd2(url, options);
        payload = await response.json();
        // The server emits this code before consuming the plan or calling Tango.
        if (response.status !== 409 || payload.code !== 'VD2_CONTROL_LOCKED' || attempt === 3) break;
        await new Promise(resolve => window.setTimeout(resolve, 250 * (attempt + 1)));
      }
      if (!protocolAlive.current) return;
      if (response.status === 409 && payload.code === 'VD2_CONTROL_LOCKED') {
        reportError(payload.error, `Start ${phase}`);
        return;
      }
      if (!response.ok || !payload.success) throw new Error(payload.error || `Could not start ${phase}`);
      setProtocol(payload);
      setProtocolSettings(current=>({...current,runName:payload.sample_name||choice.run_name}));
      if (guidedRun) {
        setGuidedRun(run => run && ({ ...run, jobs: [...run.jobs, payload.job_id] }));
        setGuidedMessage(`${PHASE_PROTOCOLS[phase].label} acquisition started.`);
      }
      setRepeatConflict(null);
      setPreparedPhase(null);
      previewPaused.current = false;
      setPreviewEnabled(true);
      setPreviewError('');
    } catch (requestError) {
      if(!protocolAlive.current)return;
      setRepeatConflict(null);setPreparedPhase(null);
      if (guidedRun) {setGuidedRun(null);setGuidedMessage('Measurement stopped. Check the phase status before trying again.');}
      reportError(requestError.message, `Start ${phase}`);
    } finally {
      protocolStartActive.current=false;
      if(protocolAlive.current)setProtocolStarting(false);
    }
  }, [protocolSettings, reportError, guidedRun]);

  const beginGuidedRun = reuse => {
    setGuidedChoice(null);
    setGuidedMessage('Waiting for Absorption confirmation.');
    setGuidedRun({ reuse, phases: reuse === 'none' ? ['ABSORPTION', 'BASE', 'BRUIT'] : ['ABSORPTION', 'BASE'], jobs: [] });
    setPreparedPhase({ phase: 'ABSORPTION', readyAt: Date.now() });
  };
  const chooseGuidedRun = () => {
    if (!project) return;
    const own = project?.samples?.find(sample => sample.name === protocolSettings.runName)?.bruit_reference;
    const options = (project?.bruit_options || []).filter(item => item.status === 'completed');
    const candidate = options.find(item => item.id === own) || [...options].sort((a, b) => String(b.completed_at).localeCompare(String(a.completed_at)))[0];
    if (candidate) setGuidedChoice(candidate);
    else beginGuidedRun('none');
  };
  const cancelPreparedPhase = () => {
    setPreparedPhase(null);
    if (guidedRun) {setGuidedRun(null);setGuidedMessage('Measurement cancelled before the next phase.');}
  };
  useEffect(() => {
    if (!guidedRun?.jobs.length || !protocol) return;
    const jobs = new Map((protocol.processing_jobs || []).map(job => [job.job_id, job]));
    if (protocol.job_id) jobs.set(protocol.job_id, protocol);
    const completed = guidedRun.jobs.map(id => jobs.get(id));
    const failed = completed.find(job => job?.status === 'failed');
    if (failed) {
      setGuidedRun(null);
      setPreparedPhase(null);
      setGuidedMessage(`${failed.phase_label || failed.phase} failed. ${failed.error || 'Review the phase before retrying.'}`);
      return;
    }
    if (preparedPhase || protocolStarting || protocolHardwareBusy(protocol)) return;
    const last = completed.at(-1);
    if (!['queued', 'processing', 'completed'].includes(last?.status)) return;
    const phase = guidedRun.phases[guidedRun.jobs.length];
    if (phase) {
      setGuidedMessage(`Waiting for ${PHASE_PROTOCOLS[phase].label} confirmation.`);
      setPreparedPhase({ phase, readyAt: Date.now() + PHASE_PROTOCOLS[phase].preparationSeconds * 1000 });
    } else if (completed.every(job => job?.status === 'completed')) {
      setGuidedRun(null);
      setGuidedMessage('Measurement saved. All H5 files verified.');
    } else {
      setGuidedMessage('Waiting for H5 conversion and verification.');
    }
  }, [guidedRun, protocol, preparedPhase, protocolStarting]);

  const prepareProtocolPhase = useCallback((phase) => {
    window.clearTimeout(phaseClickTimer.current);
    phaseClickTimer.current = window.setTimeout(() => {
      setPreparedPhase({ phase, readyAt: Date.now() + PHASE_PROTOCOLS[phase].preparationSeconds * 1000 });
    }, 230);
  }, []);

  const startProtocolPhaseImmediately = useCallback((phase) => {
    window.clearTimeout(phaseClickTimer.current);
    startProtocolPhase(phase);
  }, [startProtocolPhase]);

  useEffect(() => () => window.clearTimeout(phaseClickTimer.current), []);

  useEffect(() => {
    if (!preparedPhase) return undefined;
    setPreparationTick(Date.now());
    window.requestAnimationFrame(() => document.querySelector('.vd2-phase-dialog')?.focus());
    const interval = window.setInterval(() => setPreparationTick(Date.now()), 200);
    return () => window.clearInterval(interval);
  }, [preparedPhase]);

  const preparationRemaining = preparedPhase
    ? Math.max(0, Math.ceil((preparedPhase.readyAt - preparationTick) / 1000))
    : 0;

  useEffect(() => {
    if (!preparedPhase || protocolStarting) return undefined;
    const onKeyDown = (event) => {
      const dialog = event.target?.closest?.('.vd2-phase-dialog');
      if (event.code !== 'Space' || !dialog || (event.target !== dialog && !event.target.hasAttribute('data-vd2-phase-start'))) return;
      event.preventDefault();
      if (!event.repeat) startProtocolPhase(preparedPhase.phase);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [preparedPhase, protocolStarting, startProtocolPhase]);

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
    const scale = Math.min(box.width / preview.width, box.height / preview.height);
    return {
      x: clamp(Math.round((event.clientX - box.left - (box.width - preview.width * scale) / 2) / scale), 0, preview.width - 1),
      y: clamp(Math.round((event.clientY - box.top - (box.height - preview.height * scale) / 2) / scale), 0, preview.height - 1),
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
    while(rois.some(roi=>roi.id===`roi-${nextRoiId.current}`))nextRoiId.current+=1;
    const id = `roi-${nextRoiId.current++}`;
    setRois((current) => [...current, { ...roi, id }]);
    setSelectedRoiId(id);
  }, [constrainRoi, drawingRoi, preview, previewPoint,rois,setRois]);
  const removeRoi = useCallback((id) => {
    setRois((current) => current.filter((roi) => roi.id !== id));
    setSelectedRoiId((current) => current === id ? null : current);
  }, [setRois]);
  const values = state?.values || {};
  const alignmentControlsBlocked = busy || protocolStarting || !state?.connected || !state?.application_running
    || protocolHardwareActive;
  const acquisitionIdle = state?.acquisition_status === 'idle';
  const acquisitionReadError = state?.attribute_errors?.acquisition_status || '';
  const acquisitionReadDeferred = acquisitionReadError === DEFERRED_ACQUISITION_READ;
  const awaitingCameraState = state?.state_deferred && !state?.state;
  const readIssues = useMemo(() => ({
    status: { label: 'Camera status', message: state?.status || '' },
    acquisition: { label: 'Acquisition status', message: state?.attribute_errors?.acquisition_status || '' },
    preview: { label: 'Frame preview', message: previewError },
    calibration: { label: 'Calibration', message: calibrationError },
    averaging: { label: 'Rolling average read', message: liveAverageReadError },
    state: { label: 'State read', message: readFailures.state || '' },
    protocol: { label: 'Protocol read', message: readFailures.protocol || '' },
  }), [state, previewError, calibrationError, liveAverageReadError, readFailures]);
  const statusClass = state?.state === 'ON' || state?.state === 'RUNNING' ? 'online' : 'offline';
  const showPreviousError = () => {
    if (errors.length < 2) return;
    const activeIndex = Math.max(0, errors.findIndex((entry) => entry.id === activeErrorId));
    setActiveErrorId(errors[(activeIndex - 1 + errors.length) % errors.length].id);
  };
  const showNextError = () => {
    if (errors.length < 2) return;
    const activeIndex = Math.max(0, errors.findIndex((entry) => entry.id === activeErrorId));
    setActiveErrorId(errors[(activeIndex + 1) % errors.length].id);
  };
  const dismissError = (id) => setErrors((current) => current.filter((entry) => entry.id !== id));
  const clearErrors = () => setErrors([]);
  const copyError = async (message) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(message);
        return;
      }
      const textarea = document.createElement('textarea');
      textarea.value = message;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.append(textarea);
      textarea.select();
      const copied = document.execCommand('copy');
      textarea.remove();
      if (!copied) throw new Error('Browser refused clipboard access');
    } catch (clipboardError) {
      reportError(`Could not copy error: ${clipboardError.message}`, 'Copy error');
    }
  };

  return (
    <main className="vd2-page">
      <header className="vd2-header" aria-label="VD2 header">
        <div>
          <h1>Pump probe VD2</h1>
          <p className="vd2-subtitle">Streak-camera control and timing configuration</p>
        </div>
        <div className="vd2-statuses" aria-live="polite">
          {awaitingCameraState ? <span className="vd2-status">Camera status deferred</span> : <>
            <span className={`vd2-status ${statusClass}`}>Tango {state?.state || 'OFFLINE'}</span>
            <span className={`vd2-status ${state?.connected ? 'online' : 'offline'}`}>RemoteEx {state?.connected ? 'connected' : 'disconnected'}</span>
            <span className={`vd2-status ${state?.connected && state?.application_running ? 'online' : 'offline'}`}>HPD-TA {!state?.connected ? 'status unknown' : state?.application_running ? 'running' : 'stopped'}</span>
          </>}
        </div>
        <div className="vd2-header-actions">
          <button type="button" onClick={refreshAll} disabled={busy || protocolHardwareActive}>Refresh</button>
        </div>
      </header>

      <Vd2ErrorTray
        errors={errors}
        activeErrorId={activeErrorId}
        onPrevious={showPreviousError}
        onNext={showNextError}
        onCopy={copyError}
        onDismiss={dismissError}
        onClear={clearErrors}
      />

      {state?.status && <div className="vd2-startup-error" role="alert">{state.status}</div>}
      {acquisitionReadError && (acquisitionReadDeferred
        ? <div className="vd2-read-deferred" role="status">Acquisition status check deferred: another VD2 operation is in progress.</div>
        : <div className="vd2-startup-error" role="alert">Acquisition status unavailable: {acquisitionReadError}</div>)}
      {state && !awaitingCameraState && !state.connected && <div className="vd2-startup-error" role="alert">RemoteEx control link is disconnected. HPD-TA may still be running; its acquisition state is unknown. Reconnect before sending camera commands.</div>}
      <VD2ReadDiagnostics issues={readIssues} />
      {(alignmentMemoryError||roiMemoryError)&&<small role="alert">{alignmentMemoryError||roiMemoryError}</small>}

      <div className="vd2-tabs" role="tablist" aria-label="VD2 control views">
        <button type="button" role="tab" aria-selected={activeTab === 'acquisition'} className={activeTab === 'acquisition' ? 'is-active' : ''} onClick={() => setActiveTab('acquisition')}>Acquisition</button>
        <button type="button" role="tab" aria-selected={activeTab === 'hardware'} className={activeTab === 'hardware' ? 'is-active' : ''} onClick={() => setActiveTab('hardware')}>Hardware setup</button>
        <button type="button" role="tab" aria-selected={activeTab === 'delay-lines'} className={activeTab === 'delay-lines' ? 'is-active' : ''} onClick={() => setActiveTab('delay-lines')}>Delay Lines</button>
        <button type="button" role="tab" aria-selected={activeTab === 'pdu'} className={activeTab === 'pdu' ? 'is-active' : ''} onClick={() => setActiveTab('pdu')}>PDU</button>
        <button type="button" role="tab" aria-selected={activeTab === 'alignment'} className={activeTab === 'alignment' ? 'is-active' : ''} onClick={() => setActiveTab('alignment')}>Alignment</button>
      </div>

      {['acquisition', 'alignment'].includes(activeTab) && (
        <div className={`vd2-acquisition-workspace ${imageRight ? 'is-image-right' : ''} ${activeTab === 'alignment' ? 'is-alignment' : ''}`}
          style={{ '--vd2-image-width': `${imageWidth}px` }}
          onDragOver={event => { if (dragPanel) event.preventDefault(); }}
          onDrop={event => { if (dragPanel) { event.preventDefault(); const box = event.currentTarget.getBoundingClientRect(); setImageRight(event.clientX > box.left + box.width / 2); setDragPanel(false); } }}>
          <div className="vd2-acquisition-sidebar">
            {activeTab === 'alignment' ? <>
              <AlignmentRegion region={alignmentRegion} onChange={(key, value) => setAlignmentRegion(current => ({ ...current, [key]: value }))}
                calibrationUpdating={calibrationUpdating} calibrated={Boolean(calibration) && previewAvailable}
                calibrationError={previewStream === 'no_valid_image' ? '' : calibrationError || preview?.calibration_error || ''} />
              <VD2LiveAverage onReadError={setLiveAverageReadError} onReadback={setAlignmentAverage} disabled={alignmentControlsBlocked}>
                <button type="button" onClick={() => runCommand('StartLive')} disabled={alignmentControlsBlocked || !acquisitionIdle}>Live</button>
                <button type="button" className="vd2-stop" onClick={() => runCommand('StopAcquisition')} disabled={alignmentControlsBlocked || acquisitionIdle}>Stop</button>
              </VD2LiveAverage>
              <VD2AlignmentMagnets measurements={alignmentMeasurements} live={state?.acquisition_status === 'busy' && String(state?.acquisition_mode).toLowerCase() === 'live'} />
            </> : <>
            <section className="vd2-control-strip" aria-label="Acquisition controls">
              <div className="vd2-acquisition-actions">
                <button
                  type="button"
                  onClick={() => runCommand('StartLive')}
                  disabled={busy || protocolHardwareActive || !state?.application_running || state?.remoteex_status === 'starting'}
                >
                  Live
                </button>
                <button type="button" onClick={() => runCommand('AcquireSingle')} disabled={busy || protocolHardwareActive}>Single</button>
                <button type="button" onClick={() => runCommand('Acquire')} disabled={busy || protocolHardwareActive}>Acquire</button>
                <button type="button" onClick={() => runCommand('StartSequence')} disabled={busy || protocolHardwareActive}>Sequence</button>
                <button type="button" className="vd2-stop" onClick={() => runCommand('StopAcquisition')} disabled={busy}>Stop</button>
              </div>
              <VD2LiveAverage onReadError={setLiveAverageReadError} liveActive={state?.remoteex_status === 'busy'} disabled={busy || !state?.connected || !state?.application_running || protocolHardwareActive}>
                <label><span>Frames / HIS</span><input aria-label="Frames / HIS" type="number" min="1" max="100000" step="1" value={protocolSettings.framesPerHis}
                  disabled={!serverWorkspace.ready || busy || protocolStarting || Boolean(repeatConflict) || protocolHardwareActive} onChange={event => updateProtocolSetting('framesPerHis', event.target.value)} /></label>
              </VD2LiveAverage>
            </section>
            <Vd2PhaseProtocol
              protocol={protocol}
              project={project}
              settings={protocolSettings}
              disabled={!serverWorkspace.ready || busy || protocolStarting || Boolean(repeatConflict) || !state?.application_running || state?.remoteex_status === 'busy'}
              settingsDisabled={!serverWorkspace.ready || busy || protocolStarting || Boolean(repeatConflict) || Boolean(preparedPhase) || Boolean(guidedRun || guidedChoice)}
              serverWorkspace={serverWorkspace}
              onChange={updateProtocolSetting}
              onPhaseClick={prepareProtocolPhase}
              onPhaseDoubleClick={startProtocolPhaseImmediately}
              onMeasure={chooseGuidedRun}
              measurementUnavailable={!project}
              measuring={Boolean(guidedRun || guidedChoice)}
              measurementMessage={guidedMessage}
              sampleHolder={<VD2SampleHolder disabled={busy || protocolStarting || protocolHardwareActive} />}
            />
            {projectError && <p role="alert" className="vd2-stage-error">{projectError}</p>}
            <section className="vd2-roi-analysis" aria-label="ROI analysis">
              <aside className="vd2-roi-list">
                <header><strong>Regions</strong><span>{rois.length}</span></header>
                <label className="vd2-roi-link"><input type="checkbox" checked={linkRois} onChange={event => setLinkRois(event.target.checked)} />Move together</label>
                {rois.length === 0 && <p>No regions</p>}
                {rois.map((roi, index) => {
                  const definition = ROI_TOOLS[roi.type];
                  return (
                    <div className={`vd2-roi-row ${roi.id === selectedRoiId ? 'is-selected' : ''}`} key={roi.id}>
                      <button type="button" className="vd2-roi-select" onClick={() => setSelectedRoiId(roi.id)}>
                        <i style={{ background: roiColor(index) }} />
                        <span>{index + 1}. {definition.label}</span>
                      </button>
                      <button type="button" className="vd2-roi-remove" title={`Remove ROI ${index + 1}`} aria-label={`Remove ROI ${index + 1}`} onClick={() => removeRoi(roi.id)}>×</button>
                    </div>
                  );
                })}
              </aside>
              <RoiProfiles preview={preview} rois={rois} selectedId={selectedRoiId} onSelect={setSelectedRoiId} />
            </section>
            </>}
          </div>

        <div className="vd2-panel-splitter" role="separator" aria-label="Resize live image" aria-orientation="vertical" tabIndex="0"
          aria-valuemin="320" aria-valuemax="760" aria-valuenow={imageWidth} onPointerDown={resizeImage}
          onKeyDown={event => { if (['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); setImageWidth(clamp(imageWidth + (event.key === 'ArrowRight' ? 20 : -20) * (imageRight ? -1 : 1), 320, 760)); } }} />
        <div className="vd2-image-column">
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
              <h2 draggable onDragStart={() => setDragPanel(true)} onDragEnd={() => setDragPanel(false)} title="Drag image panel to either side">↔ Live image</h2>
              <p>C13440-20CU display frame</p>
            </div>
            <div className="vd2-preview-meta">
              <span>{preview ? `${preview.width} x ${preview.height}` : 'Waiting for frame'}</span>
              <span>{previewStream === 'no_valid_image' ? (preview ? 'No current image · Previous frame' : 'Waiting for first frame')
                : protocolSaving ? protocol.status : state?.acquisition_status === 'busy' || previewStream === 'acquiring' ? 'Acquiring' : 'Last frame'}</span>
              {preview && <span>{preview.minimum} - {preview.maximum}</span>}
              <button type="button" onClick={() => { previewPaused.current = false; setPreviewEnabled(true); loadPreview(); }} disabled={busy}>Refresh frame</button>
              <button type="button" onClick={() => setImageRight(current => !current)} aria-label="Swap image and controls" title="Move image to the other side">↔</button>
            </div>
          </header>
          {previewError && <div className="vd2-preview-error" role="alert">{previewError}</div>}
          {!previewError && previewStream === 'no_valid_image' && <div className="vd2-preview-status" role="status">
            {state?.acquisition_status === 'busy' ? 'Waiting for a camera image.' : 'No image available yet. Start Live or acquire a frame.'}
          </div>}
          {activeTab === 'acquisition' && <div className="vd2-roi-tools" aria-label="ROI tools">
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
          </div>}
          <div className="vd2-preview-canvas-wrap">
            <div className="vd2-image-stage">
              <canvas ref={previewCanvas} className="vd2-preview-canvas" />
              <FrameDisplayRate hz={previewStride > 1 && !previewFresh ? 0 : previewHz} />
              {preview && (
                <svg
                  ref={previewOverlay}
                  className="vd2-roi-overlay"
                  viewBox={`0 0 ${preview.width} ${preview.height}`}
                  onPointerDown={activeTab === 'acquisition' ? beginRoi : undefined}
                  onPointerMove={activeTab === 'acquisition' ? updateRoi : undefined}
                  onPointerUp={activeTab === 'acquisition' ? completeRoi : undefined}
                  onPointerCancel={() => setDrawingRoi(null)}
                >
                  {activeTab === 'alignment' && alignment.bounds && <VD2RoiEditor bounds={alignment.bounds}
                    width={preview.width} height={preview.height} pointFromEvent={previewPoint} label="Alignment ROI"
                    onChange={bounds => setAlignmentRegion(alignmentRegionFromBounds(bounds, calibration))} />}
                  {(activeTab === 'acquisition' ? [...rois, ...(drawingRoi ? [{ ...drawingRoi, id: 'drawing' }] : [])] : []).map((roi, index) => {
                    const bounds = roiBounds(roi, preview.width, preview.height);
                    const definition = ROI_TOOLS[roi.type];
                    const selected = roi.id === selectedRoiId;
                    return (
                      <g key={roi.id} className={selected ? 'is-selected' : ''}>
                        {roi.id === 'drawing' ? <rect x={bounds.x0} y={bounds.y0}
                          width={Math.max(1, bounds.x1 - bounds.x0 + 1)} height={Math.max(1, bounds.y1 - bounds.y0 + 1)} stroke={definition.color} />
                          : <VD2RoiEditor bounds={bounds} width={preview.width} height={preview.height}
                            pointFromEvent={previewPoint} selected={selected} type={roi.type} color={roiColor(index)}
                            label={`${definition.profile} ROI ${index + 1}`} onSelect={() => setSelectedRoiId(roi.id)}
                            onChange={next => setRois(current => updateRoisFromBounds(current, roi.id, next, linkRois, preview.width, preview.height))} />}
                        {roi.id !== 'drawing' && <text x={bounds.x0 + 4} y={bounds.y0 + 15} fill={roiColor(index)}>{index + 1}</text>}
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
          </div>
        </section>
        {activeTab === 'alignment' && <AlignmentKinetics geometry={alignment} region={alignmentRegion} context={alignmentContext}
          frameId={preview?.received_at} fresh={previewFresh}
          freshnessMessage={previewError || previewTiming.reason} measurements={alignmentMeasurements} />}
        </div>
        </div>
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
              <ParameterCard card={card} values={values} onApply={writeParameter} busy={busy || protocolHardwareActive} key={card.title} />
            ))}
          </section>
        </>
      )}
      {activeTab === 'delay-lines' && (
        <section className="vd2-delay-lines" aria-label="VD2 delay lines">
          <h2>Delay Lines</h2>
          <VD2TranslationStages showHeading={false} />
        </section>
      )}
      {activeTab === 'pdu' && <VD2PDUControl />}
      <Vd2PhaseDialog
        prepared={preparedPhase}
        remaining={preparationRemaining}
        starting={protocolStarting}
        onCancel={cancelPreparedPhase}
        onStart={startProtocolPhase}
      />
      {guidedChoice && <div className="vd2-modal-backdrop">
        <section className="vd2-phase-dialog" role="dialog" aria-modal="true" aria-label="Choose Bruit for this measurement">
          <header><h2>Do Measurement</h2></header>
          <p>Reuse Bruit from {guidedChoice.sample}? Camera settings are checked before acquisition.</p>
          <footer>
            <button type="button" onClick={() => setGuidedChoice(null)}>Cancel</button>
            <button type="button" onClick={() => beginGuidedRun('none')}>Record new Bruit</button>
            <button type="button" onClick={() => beginGuidedRun(guidedChoice.id)}>Absorption + Base · reuse Bruit</button>
          </footer>
        </section>
      </div>}
      <Vd2RepeatDialog conflict={repeatConflict} starting={protocolStarting} onCancel={()=>setRepeatConflict(null)}
        onChoose={choice=>startProtocolPhase(repeatConflict.body.phase,{body:repeatConflict.body,choice})} />
    </main>
  );
}

export default PumpProbeVD2;
