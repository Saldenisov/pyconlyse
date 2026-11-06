import { frameRateFromSamples } from './frameDisplayRateMath';

export function exposureMilliseconds(value) {
  const match = String(value ?? '').trim().match(/^([\d.eE+-]+)\s*(ns|us|µs|ms|s)?$/);
  if (!match || !Number.isFinite(Number(match[1]))) return '';
  const factor = { ns: 1e-6, us: 1e-3, 'µs': 1e-3, ms: 1, s: 1000 }[match[2] || 's'];
  return String(Number((Number(match[1]) * factor).toPrecision(12)));
}

export function plannedRunFolder(settings) {
  return `${String(settings.outputRoot || '').replace(/[\\/]+$/, '')}\\${settings.runName || ''}`;
}

export function treatmentFolderUrl(folder) {
  return `/datatreatment?${new URLSearchParams({ profile: 'VD2', folder }).toString()}`;
}

export function previewShouldPoll(tab, state, protocol, enabled) {
  const sequenceAcquiring = protocol?.status === 'acquiring';
  const cameraAvailable = Boolean(state?.connected && state?.application_running)
    || Boolean(state?.state_deferred && sequenceAcquiring);
  return ['acquisition', 'alignment'].includes(tab) && enabled && cameraAvailable
    && !protocolSaveActive(protocol)
    && (state?.remoteex_status === 'busy' || sequenceAcquiring);
}

export function protocolHardwareBusy(protocol) {
  return typeof protocol?.acquisition_active==='boolean'?protocol.acquisition_active:['acquiring','saving','processing'].includes(protocol?.status);
}

export function protocolSaveActive(protocol) {
  return typeof protocol?.acquisition_active==='boolean'
    ?protocol.acquisition_active&&protocol.acquisition_phase==='saving':['saving','processing'].includes(protocol?.status);
}

export function alignmentProfile(preview, calibration, region) {
  if (!preview?.pixels_b64 || !calibration) return { error: 'Waiting for calibrated axes from the Live image.' };
  const { width, height } = preview;
  if (calibration.width !== width || calibration.height !== height
    || calibration.wavelengths?.length !== width || calibration.timedelays?.length !== height) {
    return { error: 'Image size differs from calibration. Updating calibrated axes…' };
  }
  const { wavelengthMin, wavelengthMax, topPercent, bottomPercent } = region;
  if (![wavelengthMin, wavelengthMax, topPercent, bottomPercent].every(Number.isFinite)
    || wavelengthMax <= wavelengthMin || topPercent < 0 || bottomPercent > 100 || bottomPercent <= topPercent) {
    return { error: 'Choose increasing wavelength and vertical limits (0–100%).' };
  }
  const columns = calibration.wavelengths.map((value, index) => ({ value, index }))
    .filter(({ value }) => value >= wavelengthMin && value <= wavelengthMax);
  if (!columns.length) return { error: 'Selected wavelengths are outside the calibrated camera image.' };
  const pixels = window.atob(preview.pixels_b64);
  if (pixels.length !== width * height) return { error: 'Incomplete image frame.' };
  const first = Math.min(height - 1, Math.floor(height * topPercent / 100 + 1e-9));
  const end = Math.min(height, Math.max(first + 1, Math.ceil(height * bottomPercent / 100 - 1e-9)));
  const points = [];
  for (let row = first; row < end; row += 1) {
    const mean = columns.reduce((sum, { index }) => sum + pixels.charCodeAt(row * width + index), 0) / columns.length;
    points.push({ x: calibration.timedelays[row], y: mean });
  }
  const availableMin = Math.min(...calibration.wavelengths);
  const availableMax = Math.max(...calibration.wavelengths);
  return { points, timeUnit: calibration.time_unit, frameId: preview.received_at,
    intensityKey: preview.intensity_key, calibrationKey: preview.calibration_key,
    measurementKey: preview.measurement_key || preview.intensity_key,
    bounds: { x0: Math.min(...columns.map(c => c.index)), x1: Math.max(...columns.map(c => c.index)), y0: first, y1: end - 1 },
    wavelengthMin: Math.min(...columns.map(c => c.value)), wavelengthMax: Math.max(...columns.map(c => c.value)),
    clipped: wavelengthMin < availableMin || wavelengthMax > availableMax,
    availableMin, availableMax };
}

export function detectAlignmentDrop(profile, integrationPoints = 5) {
  if (profile.error) return { found: false, error: profile.error };
  const count = Number(integrationPoints);
  if (!Number.isInteger(count) || count < 3 || count > 50) return { found: false, error: 'Choose 3–50 integration points.' };
  const points = [...(profile.points || [])].sort((a, b) => a.x - b.x);
  const beforeCount = Math.max(6, count * 2);
  if (points.length < beforeCount + count) return { found: false, error: `Need at least ${beforeCount + count} points in the time ROI.` };
  if (points.some((p, i) => !Number.isFinite(p.x) || !Number.isFinite(p.y) || (i > 0 && p.x <= points[i - 1].x))) {
    return { found: false, error: 'Invalid time/intensity samples.' };
  }
  const median = values => {
    const sorted = [...values].sort((a, b) => a - b), middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };
  const mad = values => { const centre = median(values); return median(values.map(value => Math.abs(value - centre))) * 1.4826; };
  const differences = points.slice(1).map((p, i) => p.y - points[i].y);
  const noiseFloor = Math.max(mad(differences) / Math.sqrt(2), 1e-9 * Math.max(1, ...points.map(p => Math.abs(p.y))));
  let best = null;
  for (let edge = beforeCount; edge <= points.length - count; edge += 1) {
    if (points[edge].y >= points[edge - 1].y) continue;
    const before = points.slice(edge - beforeCount, edge);
    // Robust local trend: isolated bad pixels cannot tilt A0 into a false step.
    const slopes = [];
    before.forEach((a, i) => before.slice(i + 1).forEach(b => slopes.push((b.y - a.y) / (b.x - a.x))));
    const slope = median(slopes), origin = before[before.length - 1].x;
    const intercept = median(before.map(p => p.y - slope * (p.x - origin)));
    const baselineAt = x => intercept + slope * (x - origin);
    const noise = Math.max(noiseFloor, mad(before.map(p => p.y - baselineAt(p.x))));
    const sharpness = points[edge - 1].y + slope * (points[edge].x - points[edge - 1].x) - points[edge].y;
    if (sharpness < 3 * Math.sqrt(2) * noise) continue;
    // Follow the short falling edge to its foot, then average N points there.
    const lastFoot = Math.min(points.length - count, edge + Math.min(count, 6) - 1);
    let foot = edge;
    for (let i = edge + 1; i <= lastFoot; i += 1) {
      if (baselineAt(points[i].x) - points[i].y > baselineAt(points[foot].x) - points[foot].y + noise * 0.5) foot = i;
    }
    const after = points.slice(foot, foot + count);
    const deficits = after.map(p => baselineAt(p.x) - p.y);
    const base = after.reduce((sum, p) => sum + baselineAt(p.x), 0) / count;
    const drop = deficits.reduce((sum, value) => sum + value, 0) / count;
    if (base <= 0 || drop < 3 * noise || sharpness < drop * 0.25
        || deficits.filter(value => value >= drop * 0.5).length < Math.ceil(count * 0.8)) continue;
    if (!best || drop > best.drop) {
      best = { found: true, base, y: base - drop, drop, percent: 100 * drop / base,
        x: after.reduce((sum, p) => sum + p.x, 0) / count,
        edgeX: points[edge].x, integrationPoints: count,
        windowStart: after[0].x, windowEnd: after[after.length - 1].x,
        baseline: [before[0], after[after.length - 1]].map(p => ({ x: p.x, y: baselineAt(p.x) })),
        noise };
    }
  }
  return best || { found: false, reason: 'No sharp drop detected' };
}

export function previewRefreshRate(samples, now) {
  return frameRateFromSamples(samples, now);
}

export function alignmentDropWindows(profile) {
  const points = [...(profile.points || [])].sort((a, b) => a.x - b.x);
  if (profile.error || points.length < 6) return null;
  const automatic = detectAlignmentDrop(profile, 5);
  if (automatic.found) {
    const edge = points.findIndex(point => point.x === automatic.edgeX);
    return { baseline: [points[Math.max(0, edge - 10)].x, points[edge - 1].x],
      signal: [automatic.windowStart, automatic.windowEnd] };
  }
  const last = points.length - 1;
  const baselineEnd = Math.max(2, Math.min(last - 3, Math.floor(last * 0.35)));
  const signalStart = Math.max(baselineEnd + 1, Math.min(last - 2, Math.floor(last * 0.65)));
  return { baseline: [points[Math.max(0, baselineEnd - Math.max(2, Math.floor(last * 0.2)))].x, points[baselineEnd].x],
    signal: [points[signalStart].x, points[Math.min(last, Math.max(signalStart + 2, Math.floor(last * 0.85)))].x] };
}

export function measureAlignmentWindows(profile, windows) {
  if (profile.error) return { found: false, error: profile.error };
  const points = [...(profile.points || [])].sort((a, b) => a.x - b.x);
  if (!windows || points.length < 6) return { found: false, error: 'Choose baseline and signal windows with at least 3 points each.' };
  const { baseline, signal } = windows;
  if (!baseline || !signal || [...baseline, ...signal].some(value => !Number.isFinite(value))
      || baseline[0] >= baseline[1] || signal[0] >= signal[1] || baseline[1] >= signal[0]) {
    return { found: false, error: 'Baseline window must end before the signal window.' };
  }
  if (points.some((p, i) => !Number.isFinite(p.x) || !Number.isFinite(p.y) || (i > 0 && p.x <= points[i - 1].x))) {
    return { found: false, error: 'Invalid time/intensity samples.' };
  }
  const before = points.filter(p => p.x >= baseline[0] && p.x <= baseline[1]);
  const after = points.filter(p => p.x >= signal[0] && p.x <= signal[1]);
  if (before.length < 3 || after.length < 3) return { found: false, error: 'Each window needs at least 3 points.' };
  // Fit only the explicitly selected pre-drop samples. Predict that rising
  // trend at the SAME times as the averaged post-drop samples, in this frame.
  const origin = before.reduce((sum, p) => sum + p.x, 0) / before.length;
  const intercept = before.reduce((sum, p) => sum + p.y, 0) / before.length;
  const denominator = before.reduce((sum, p) => sum + (p.x - origin) ** 2, 0);
  if (denominator <= 0) return { found: false, error: 'Baseline window has no time span.' };
  const slope = before.reduce((sum, p) => sum + (p.x - origin) * (p.y - intercept), 0) / denominator;
  const baselineAt = x => intercept + slope * (x - origin);
  const base = after.reduce((sum, p) => sum + baselineAt(p.x), 0) / after.length;
  const y = after.reduce((sum, p) => sum + p.y, 0) / after.length;
  if (base <= 0 || !Number.isFinite(base)) return { found: false, error: 'I₀ must be positive in the selected windows.' };
  const drop = base - y;
  return { found: true, base, y, drop, percent: 100 * drop / base,
    x: after.reduce((sum, p) => sum + p.x, 0) / after.length,
    windowStart: signal[0], windowEnd: signal[1], baselinePoints: before.length, signalPoints: after.length,
    baseline: [baseline[0], signal[1]].map(x => ({ x, y: baselineAt(x) })) };
}

export function editAlignmentWindow(windows, name, mode, delta, domain, minimumWidth) {
  const [low, high] = windows[name];
  const gap = Math.max(Number.EPSILON, (domain[1] - domain[0]) * 1e-6);
  const lower = name === 'signal' ? windows.baseline[1] + gap : domain[0];
  const upper = name === 'baseline' ? windows.signal[0] - gap : domain[1];
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  let next;
  if (mode === 'move') {
    const shift = clamp(delta, lower - low, upper - high);
    next = [low + shift, high + shift];
  } else if (mode === 'start') next = [clamp(low + delta, lower, high - minimumWidth), high];
  else next = [low, clamp(high + delta, low + minimumWidth, upper)];
  return { ...windows, [name]: next };
}
