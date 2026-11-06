import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ITestPSUClient from './ITestPSUClient';
import { resolveDeviceFamily } from '../utils/deviceFamily';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import { editAlignmentWindow } from '../vd2AlignmentMath';
import { useVd2AlignmentReadout } from '../useVd2AlignmentReadout';
import { AlignmentSignalBuffer } from '../vd2AlignmentSearch';
import VD2AlignmentSearch from './VD2AlignmentSearch';
import {alignmentTimeMemoryKey,useVd2Memory,validAlignmentWindows} from '../vd2AlignmentMemory';

function plotPoint(svg, event) {
  const matrix = svg.getScreenCTM?.();
  if (matrix && svg.createSVGPoint) {
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(matrix.inverse());
  }
  const bounds = svg.getBoundingClientRect();
  return { x: bounds.width ? (event.clientX - bounds.left) * 560 / bounds.width : 299,
    y: bounds.height ? (event.clientY - bounds.top) * 450 / bounds.height : 213 };
}

export function AlignmentOptics({ blocked = false }) {
  const [readback, setReadback] = useState(null);
  const [receivedAt, setReceivedAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [readError, setReadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [pending, setPending] = useState('');
  const alive = useRef(false);
  const actionActive = useRef(false);
  const currentRequest = useRef(null);
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    if (currentRequest.current || actionActive.current) return;
    const controller = new AbortController();
    currentRequest.current = controller;
    const requestGeneration = generation.current;
    const startedAt = Date.now();
    const timeout = window.setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch('/api/pump-probe-vd2/alignment/optics', { credentials: 'include', signal: controller.signal });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Optical-path readback unavailable');
      if (alive.current && generation.current === requestGeneration) {
        setReadback(payload);
        setReceivedAt(startedAt);
        setNow(Date.now());
        setReadError('');
      }
    } catch (error) {
      if (alive.current && generation.current === requestGeneration) setReadError('Optical-path readback unavailable: ' + error.message);
    } finally {
      window.clearTimeout(timeout);
      if (currentRequest.current === controller) currentRequest.current = null;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    refresh();
    const poll = window.setInterval(refresh, 2500);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      alive.current = false;
      generation.current += 1;
      currentRequest.current?.abort();
      currentRequest.current = null;
      window.clearInterval(poll);
      window.clearInterval(clock);
    };
  }, [refresh]);

  const runAction = async action => {
    actionActive.current = true;
    generation.current += 1;
    currentRequest.current?.abort();
    currentRequest.current = null;
    setPending(action);
    setReceivedAt(0);
    setActionError('');
    try {
      const response = await fetchWithHardwareApproval(`/api/pump-probe-vd2/alignment/${action}`, { method: 'POST', credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Camera setup action failed');
    } catch (error) {
      if (alive.current) setActionError(error.message);
    } finally {
      actionActive.current = false;
      if (alive.current) {
        setPending('');
        await refresh();
      }
    }
  };

  const fresh = receivedAt > 0 && now - receivedAt < 6000 && !readError;
  const mirror = readback?.zaber_mirror;
  const flashLamp = fresh && mirror?.at_flash_lamp;
  const position = Number.isFinite(mirror?.position_mm) ? `${mirror.position_mm.toFixed(4)} mm` : '';
  const mirrorText = !mirror ? 'Checking…' : mirror.state === 'MOVING' ? 'Moving…'
    : mirror.at_flash_lamp ? `Flash lamp · Out · ${position}` : `${mirror.state || 'UNKNOWN'} · ${position || 'Position unavailable'}`;
  return (
    <section className="vd2-alignment-optics" aria-label="Camera optical path">
      <header><h2>Camera optical path</h2><strong className={fresh && readback?.ready ? 'is-confirmed' : 'is-unconfirmed'}>
        {fresh && readback?.ready ? 'Ready · Flash lamp + both shutters open' : 'Not confirmed'}
      </strong></header>
      <div className="vd2-optics-readings">
        {[["streak_shutter", 'Streak-camera shutter'], ['spectrograph_shutter', 'Spectrograph shutter']].map(([key, label]) => {
          const shutter = readback?.shutters?.[key];
          return <div key={key} className={fresh && shutter?.value === 'Open' && !shutter.error ? 'is-confirmed' : 'is-unconfirmed'}>
            <span>{label}</span><strong>{shutter?.value || 'Checking…'}{!fresh && readback ? ' · unverified' : ''}</strong>
            {shutter?.error && <small role="alert">{shutter.error}</small>}
          </div>;
        })}
        <div className={flashLamp ? 'is-confirmed' : 'is-unconfirmed'}>
          <span>Zaber source-selection mirror</span><strong>{mirrorText}{!fresh && readback ? ' · unverified' : ''}</strong>
          {mirror?.error && <small role="alert">{mirror.error}</small>}
        </div>
      </div>
      {readError && <p role="alert">{readError}</p>}
      {readback && !fresh && !readError && <p role="status">Waiting for fresh optical-path readback.</p>}
      {actionError && <p role="alert">{actionError}</p>}
      <div className="vd2-optics-actions">
        <button type="button" onClick={() => runAction('flash-lamp')} aria-pressed={Boolean(flashLamp)}
          disabled={blocked || Boolean(pending) || !fresh || mirror?.state !== 'ON' || Boolean(mirror?.error) || Boolean(flashLamp)}>
          {pending === 'flash-lamp' ? 'Selecting Flash lamp…' : 'Flash lamp · Out · 0 mm'}
        </button>
        <button type="button" disabled={blocked || Boolean(pending)} onClick={() => runAction('open-shutters')}>
          {pending === 'open-shutters' ? 'Opening shutters…' : 'Open both shutters'}
        </button>
      </div>
      {blocked && <p>Stop acquisition before changing the camera optical path.</p>}
    </section>
  );
}

export function AlignmentKinetics({ geometry, region, frameId, context, fresh = true, freshnessMessage = '', measurements }) {
  const localMeasurements = useMemo(() => new AlignmentSignalBuffer(), []);
  const signalBuffer = measurements || localMeasurements;
  const { timeMin: domainMin, timeMax: domainMax, timeUnit: unit } = geometry;
  const domain = [domainMin, domainMax];
  const windowKey = alignmentTimeMemoryKey(unit, domainMin, domainMax);
  const validateWindows = useCallback(value => validAlignmentWindows(value, domainMin, domainMax), [domainMin, domainMax]);
  const [selectedWindows, setWindows, memoryError] = useVd2Memory(windowKey, null, validateWindows, true);
  const { result, profile, error } = useVd2AlignmentReadout(frameId, context, region, selectedWindows);
  const windows = selectedWindows || result?.payload.windows;
  const measured = result?.payload.comparison;
  const comparison = measured || { found: false, error: error || 'Calculating selected zones…' };
  const summary = result?.payload.summary;
  const [readoutClock, setReadoutClock] = useState(() => performance.now());
  const elapsed = result ? Math.max(0, readoutClock - result.receivedAt) + result.transit : 0;
  const current = fresh && !error && result?.payload.fresh && result.payload.frame_age_ms + elapsed < 1500;
  useEffect(() => {
    if (!selectedWindows && windows && validateWindows(windows)) setWindows(windows);
  }, [selectedWindows, windows, validateWindows, setWindows]);
  useEffect(() => {
    const timer = window.setInterval(() => setReadoutClock(performance.now()), 250);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!current || !measured?.found) { signalBuffer.invalidate(); return; }
    // Search uses distinct live per-frame values, never the held display mean.
    const age = result.payload.frame_age_ms + result.transit;
    signalBuffer.record(result.payload.profile.frameId, measured.percent,
      result.payload.signal_key, result.receivedWallAt - age);
  }, [current, measured, result, signalBuffer]);
  useEffect(() => () => signalBuffer.invalidate(), [signalBuffer]);
  const [autoY, setAutoY] = useState(true);
  const [zoomAxis, setZoomAxis] = useState('xy');
  const [zoom, setZoom] = useState(null);
  const [panMode, setPanMode] = useState(false);
  const graph = useRef(null);
  const axes = useRef(null);
  const drag = useRef(null);
  const clipId = useRef(`alignment-plot-${Math.random().toString(36).slice(2)}`);
  const displayed = profile;
  const hasPlot = Boolean(displayed);
  useEffect(() => {
    const svg = graph.current;
    if (!svg) return undefined;
    const wheel = event => {
      const { x, y } = plotPoint(svg, event);
      if (x < 60 || x > 538 || y < 12 || y > 414 || !axes.current) return;
      event.preventDefault();
      if (drag.current) return;
      const { xmin, xmax, ymin, ymax, baseYmin, baseYmax, zoomAxis: direction } = axes.current;
      const factor = Math.exp(Math.max(-500, Math.min(500, event.deltaY)) * 0.002);
      const fx = (x - 60) / 478, fy = (414 - y) / 402;
      const width = Math.max(1e-12, (xmax - xmin) * factor);
      const height = Math.max(1e-12, (ymax - ymin) * factor);
      const anchorX = xmin + fx * (xmax - xmin), anchorY = ymin + fy * (ymax - ymin);
      const nextMin = anchorY - fy * height, nextMax = anchorY + (1 - fy) * height;
      setZoom(previous => ({ ...previous,
        ...(direction !== 'y' ? { xmin: anchorX - fx * width, xmax: anchorX + (1 - fx) * width } : {}),
        ...(direction !== 'x' ? { ymin: nextMin, ymax: nextMax,
          yFractionMin: (nextMin - baseYmin) / (baseYmax - baseYmin),
          yFractionMax: (nextMax - baseYmin) / (baseYmax - baseYmin) } : {}) }));
    };
    svg.addEventListener('wheel', wheel, { passive: false });
    return () => { svg.removeEventListener('wheel', wheel); drag.current = null; };
  }, [hasPlot]);
  if (!displayed) return <div className="vd2-alignment-message" role="status">{geometry.error || error || 'Waiting for server Alignment readout…'}</div>;
  const { points, timeUnit } = displayed;
  const comparable = comparison.found;
  const averaged = summary;
  const shownPercent = averaged?.mean ?? comparison.percent;
  // Existing Web processes supply the same per-frame I and I₀ without an OD field.
  const opticalDensity = comparison.optical_density === undefined && comparison.base > 0 && comparison.y > 0
    ? Math.log10(comparison.base) - Math.log10(comparison.y) : comparison.optical_density;
  const resultAge = result ? result.payload.summary_age_ms + elapsed : 0;
  const held = averaged && !current;
  const calculationStatus = !comparable ? comparison.error || comparison.reason
    : averaged?.kind === 'mean'
      ? `1 s mean ± SD · n = ${averaged.n}${held ? ` · last result ${(resultAge / 1000).toFixed(1)} s ago` : ''}`
      : held ? `Last frame result · ${(resultAge / 1000).toFixed(1)} s ago` : 'Frame result · collecting 1 s mean…';
  const samples = points;
  const allPoints = comparable ? [...points, ...comparison.baseline] : points;
  const dataXmin = Math.min(...allPoints.map(p => p.x)), dataXmax = Math.max(...allPoints.map(p => p.x));
  const xmin = zoom?.xmin ?? dataXmin;
  const xmax = zoom?.xmax ?? dataXmax;
  const minimum = Math.min(...allPoints.map(p => p.y));
  const maximum = Math.max(...allPoints.map(p => p.y));
  const baseYmin = minimum === maximum ? minimum - 0.5 : minimum;
  const baseYmax = minimum === maximum ? maximum + 0.5 : maximum;
  const ymin = autoY ? baseYmin + (zoom?.yFractionMin ?? 0) * (baseYmax - baseYmin) : zoom?.ymin ?? baseYmin;
  const ymax = autoY ? baseYmin + (zoom?.yFractionMax ?? 1) * (baseYmax - baseYmin) : zoom?.ymax ?? baseYmax;
  axes.current = { xmin, xmax, ymin, ymax, baseYmin, baseYmax, zoomAxis };
  const px = value => 60 + 478 * (value - xmin) / (xmax - xmin || 1);
  const py = value => 414 - 402 * (value - ymin) / (ymax - ymin);
  const line = samples => samples.map(p => `${px(p.x)},${py(p.y)}`).join(' ');
  const minimumWindowWidth = (domain[1] - domain[0]) / Math.max(1, samples.length - 1);
  const captureDrag = (event, start, details) => {
    event.preventDefault();
    event.stopPropagation();
    drag.current = { pointerId: event.pointerId, start, ...details };
    graph.current.setPointerCapture?.(event.pointerId);
  };
  const startWindowDrag = (event, name, mode) => {
    if (panMode || drag.current || event.button !== 0) return;
    captureDrag(event, plotPoint(graph.current, event), { name, mode, windows, xSpan: xmax - xmin });
  };
  const startPan = event => {
    if (!panMode || drag.current || event.button !== 0) return;
    const point = plotPoint(graph.current, event);
    if (point.x < 60 || point.x > 538 || point.y < 12 || point.y > 414) return;
    captureDrag(event, point, { viewport: axes.current });
  };
  const movePlot = event => {
    const gesture = drag.current;
    if (!gesture || event.pointerId !== gesture.pointerId) return;
    const point = plotPoint(graph.current, event);
    const dx = (point.x - gesture.start.x) / 478;
    if (!gesture.viewport) {
      setWindows(editAlignmentWindow(gesture.windows, gesture.name, gesture.mode,
        dx * gesture.xSpan, domain, minimumWindowWidth));
      return;
    }
    const view = gesture.viewport;
    const offsetX = -dx * (view.xmax - view.xmin);
    const offsetY = (point.y - gesture.start.y) / 402 * (view.ymax - view.ymin);
    const nextMin = view.ymin + offsetY, nextMax = view.ymax + offsetY;
    setZoom({ xmin: view.xmin + offsetX, xmax: view.xmax + offsetX, ymin: nextMin, ymax: nextMax,
      yFractionMin: (nextMin - view.baseYmin) / (view.baseYmax - view.baseYmin),
      yFractionMax: (nextMax - view.baseYmin) / (view.baseYmax - view.baseYmin) });
  };
  const stopDrag = event => { if (drag.current?.pointerId === event.pointerId) drag.current = null; };
  const windowKeyboard = (event, name, mode) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault(); event.stopPropagation();
    const delta = minimumWindowWidth * (event.shiftKey ? 5 : 1) * (event.key === 'ArrowRight' ? 1 : -1);
    setWindows(editAlignmentWindow(windows, name, mode, delta, domain, minimumWindowWidth));
  };
  return (
    <section className="vd2-alignment-kinetics" aria-label="Alignment kinetics">
      {memoryError&&<small role="alert">{memoryError}</small>}
      {displayed.clipped && <p role="status">Camera covers {displayed.availableMin.toFixed(1)}–{displayed.availableMax.toFixed(1)} nm; ROI uses the available overlap.</p>}
      <div className="vd2-drop-controls">
        <span className="vd2-window-baseline">I₀ · Before</span><span className="vd2-window-signal">I · After</span>
        <button type="button" onClick={() => setWindows(null)}>Auto zones</button>
        {windows && <details className="vd2-window-values"><summary>Zones · {timeUnit}</summary>
          {['baseline', 'signal'].map(name => <div key={name}>
            <strong>{name === 'baseline' ? 'I₀' : 'I'}</strong>
            {['start', 'end'].map((edge, index) => <label key={edge}>{edge === 'start' ? 'From' : 'To'}
              <input type="number" step="any" aria-label={`${name === 'baseline' ? 'Baseline' : 'Signal'} ${edge} time`}
                value={Number(windows[name][index].toPrecision(7))} onChange={event => {
                  if (event.target.value === '') return;
                  const interval = [...windows[name]]; interval[index] = Number(event.target.value);
                  setWindows({ ...windows, [name]: interval });
                }} /></label>)}
          </div>)}
        </details>}
        {!current && result && <span role="status">Last frame · not updating{error || freshnessMessage ? ` · ${error || freshnessMessage}` : ''}</span>}
      </div>
      {!comparable && <p role="alert" className="vd2-alignment-message">Calculation unavailable: {comparison.error || comparison.reason}</p>}
      <div className="vd2-alignment-plot">
      <div className="vd2-alignment-plot-actions">
        <button type="button" aria-label="Pan kinetics" aria-pressed={panMode} title="Drag the plot to pan in X and Y"
          onClick={() => setPanMode(value => !value)}>✋</button>
        <button type="button" aria-label="Auto Y" aria-pressed={autoY}
          title={`Automatic Y range: ${autoY ? 'on' : 'off'}`}
          onClick={() => { setZoom({ ...axes.current, yFractionMin: 0, yFractionMax: 1 }); setAutoY(!autoY); }}>*</button>
        <div className="vd2-zoom-axes" role="group" aria-label="Zoom axis">
          {['x', 'y', 'xy'].map(direction => <button key={direction} type="button"
            aria-label={`Zoom ${direction.toUpperCase()}`} aria-pressed={zoomAxis === direction}
            title={`Mouse wheel: ${direction.toUpperCase()} ${direction === 'xy' ? 'axes' : 'axis'}`}
            onClick={() => setZoomAxis(direction)}>{direction.toUpperCase()}</button>)}
        </div>
        {zoom && <button type="button" onClick={() => setZoom({ xmin: dataXmin, xmax: dataXmax,
          ymin: baseYmin, ymax: baseYmax, yFractionMin: 0, yFractionMax: 1 })}>Reset zoom</button>}
      </div>
      <svg ref={graph} viewBox="0 0 560 450" role="img" aria-label={`Kinetics versus time (${timeUnit})`}
        className={panMode ? 'vd2-kinetics-pannable' : undefined} onPointerDown={startPan} onPointerMove={movePlot}
        onPointerUp={stopDrag} onPointerCancel={stopDrag} onLostPointerCapture={stopDrag}>
        <title>Drag the yellow I0 and green I windows or their edges. I0 is the local trend fitted BEFORE the fall and evaluated at the SAME times as the averaged I window. Relative displayed-intensity change: 100 × (I0 − I) / I0.</title>
        <defs><clipPath id={clipId.current}><rect x="60" y="12" width="478" height="402" /></clipPath></defs>
        <rect x="60" y="12" width="478" height="402" fill="#111820" />
        <g aria-label="Y axis divisions">
          {Array.from({ length: 17 }, (_, i) => {
            const value = ymin + (ymax - ymin) * i / 16;
            const y = py(value);
            return <g key={i}>
              <line x1={i % 2 === 0 ? 54 : 57} y1={y} x2="60" y2={y} />
              {i % 2 === 0 && <>
                <line className="vd2-kinetics-grid" x1="60" y1={y} x2="538" y2={y} />
                <text x="50" y={y + 3} textAnchor="end">{value.toFixed(1)}</text>
              </>}
            </g>;
          })}
        </g>
        <line x1="60" y1="12" x2="60" y2="414" /><line x1="60" y1="414" x2="538" y2="414" />
        <g clipPath={`url(#${clipId.current})`}>
        {windows && ['baseline', 'signal'].map(name => {
          const interval = windows[name];
          const label = name === 'baseline' ? 'Baseline' : 'Signal';
          const color = name === 'baseline' ? '#ffd54f' : '#8be9b6';
          return <g key={name} className="vd2-drop-window">
            <rect role="slider" tabIndex="0" aria-label={`${label} window`} aria-valuemin={domain[0]}
              aria-valuemax={domain[1]} aria-valuenow={(interval[0] + interval[1]) / 2}
              aria-valuetext={`${interval[0]} to ${interval[1]} ${timeUnit}`}
              x={px(interval[0])} y="12" width={Math.max(1, px(interval[1]) - px(interval[0]))} height="402"
              fill={color} fillOpacity="0.13" stroke={color} strokeWidth="1"
              onPointerDown={event => startWindowDrag(event, name, 'move')}
              onKeyDown={event => windowKeyboard(event, name, 'move')} />
            {['start', 'end'].map((mode, index) => <rect key={mode} role="slider" tabIndex="0"
              aria-label={`${label} ${mode}`} aria-valuemin={domain[0]} aria-valuemax={domain[1]} aria-valuenow={interval[index]}
              className="vd2-window-handle" x={px(interval[index]) - 4} y="12" width="8" height="402"
              fill={color} fillOpacity="0.45" onPointerDown={event => startWindowDrag(event, name, mode)}
              onKeyDown={event => windowKeyboard(event, name, mode)} />)}
            <text x={(px(interval[0]) + px(interval[1])) / 2} y="28" textAnchor="middle" fill={color} pointerEvents="none">
              {name === 'baseline' ? 'I₀' : 'I'}
            </text>
          </g>;
        })}
        <polyline aria-label="Current kinetics" points={line(points)} fill="none" stroke="#70e7ff" strokeWidth="2" />
        {comparable && <>
          <polyline aria-label="Local pre-drop baseline" points={line(comparison.baseline)} fill="none" stroke="#ffd54f" strokeWidth="2" strokeDasharray="6 4" />
          <line className="vd2-drop-marker" x1={px(comparison.x)} x2={px(comparison.x)} y1={py(comparison.base)} y2={py(comparison.y)} />
          <line className="vd2-drop-marker" aria-label="Mean after drop" x1={px(comparison.windowStart)} x2={px(comparison.windowEnd)} y1={py(comparison.y)} y2={py(comparison.y)} />
        </>}
        </g>
        <g className="vd2-kinetics-labels">
          <text x="528" y="366" textAnchor="end" className="vd2-drop-value" aria-label="Relative signal drop">
            ΔI/I₀ · {comparable && Number.isFinite(shownPercent) ? `${Math.abs(shownPercent) < 0.005 ? '0.00' : shownPercent.toFixed(2)}%` : '—%'}
            {comparable && (Number.isFinite(averaged?.sd) ? ` ± ${averaged.sd.toFixed(2)}%` : ' ± —%')}
          </text>
          <text x="528" y="330" textAnchor="end" className="vd2-optical-density" aria-label="Optical density">
            <title>Apparent absorption from the displayed frame: OD = log₁₀(I₀/I). Both intensities must be positive.</title>
            Absorption · OD {comparable && Number.isFinite(opticalDensity) ? opticalDensity.toFixed(3) : '—'}
          </text>
          <text x="528" y="384" textAnchor="end" aria-label="Alignment calculation status">{calculationStatus}</text>
          <text x="528" y="400" textAnchor="end" className="vd2-kinetics-title">Kinetics · {displayed.wavelengthMin.toFixed(1)}–{displayed.wavelengthMax.toFixed(1)} nm</text>
        </g>
        <g aria-label="X axis divisions">{Array.from({ length: 5 }, (_, i) => {
          const x = xmin + (xmax - xmin) * i / 4;
          return <g key={i}><line x1={px(x)} x2={px(x)} y1="414" y2="419" />
            <text x={px(x)} y="434" textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{x.toPrecision(4)}</text></g>;
        })}</g>
        <text x="270" y="448">Time, {timeUnit}</text>
      </svg>
      </div>
    </section>
  );
}

export function AlignmentRegion({ region, onChange, calibrationUpdating = false, calibrated = false, calibrationError = '' }) {
  return (
    <section className="vd2-alignment-region" aria-label="Alignment ROI">
      <header><strong>ROI · wavelength × time</strong><span role="status">{calibrationUpdating ? 'Updating calibration…' : calibrated ? 'Calibration · automatic' : 'Waiting for calibrated axes…'}</span></header>
      {calibrationError && <p className="vd2-alignment-message" role="alert">{calibrationError}</p>}
      <div className="vd2-alignment-roi-fields">
        {[
          ['wavelengthMin', 'From, nm'], ['wavelengthMax', 'To, nm'],
          ['topPercent', 'Top, %'], ['bottomPercent', 'Bottom, %'],
          ].map(([key, label]) => <label key={key}>{label}<input type="number" step="any"
            value={Number.isFinite(region[key]) ? Number(region[key].toFixed(4)) : ''} onChange={e => onChange(key, Number(e.target.value))} /></label>)}
      </div>
      <p className="vd2-alignment-message">Drag the ROI on the image to move it. Drag its handles to resize.</p>
    </section>
  );
}

export function VD2AlignmentMagnets({ measurements, live = false }) {
  const [devices, setDevices] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [searchRunning,setSearchRunning]=useState(false);
  useEffect(() => {
    let disposed = false;
    (async () => {
      try {
        const response = await fetch('/api/devices?probe_state=0&include_dserver=0', { credentials: 'include' });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Unable to list iTest devices');
        const names = [...new Set((payload.devices || []).filter(d => !String(d.name).startsWith('dserver/')
          && (resolveDeviceFamily(d) === 'itest_psu' || /itest/i.test(`${d.name} ${d.class} ${d.server}`))).map(d => d.name))];
        const configured = await Promise.all(names.map(async name => {
          const result = await fetch(`/api/device/ds_itest_psu/${name}/tab_config`, { credentials: 'include' });
          const config = await result.json();
          if (!result.ok) throw new Error(config.error || `Unable to load ${name} VD2 slots`);
          return config.tab_configs?.VD2?.enabled !== false && config.tab_configs?.VD2?.slots?.length ? name : null;
        }));
        if (!disposed) setDevices(configured.filter(Boolean));
      } catch (err) {
        if (!disposed) setError(err.message);
      } finally {
        if (!disposed) setLoading(false);
      }
    })();
    return () => { disposed = true; };
  }, []);
  return (
    <section className="vd2-alignment-magnets" aria-label="VD2 iTest magnets">
      <h2>VD2 · iTest magnets</h2>
      {!loading && devices.length===1 && measurements && <VD2AlignmentSearch device={devices[0]} measurements={measurements} live={live} onRunning={setSearchRunning} />}
      {loading && <p>Loading configured VD2 channels…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !devices.length && <p>No VD2 iTest channels configured.</p>}
      {devices.map(device => <fieldset className="vd2-search-manual" disabled={searchRunning} key={device}>
        <ITestPSUClient deviceName={device} fixedTab="VD2" compact /></fieldset>)}
    </section>
  );
}
