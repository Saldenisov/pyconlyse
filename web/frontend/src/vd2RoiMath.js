const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

export const DEFAULT_PAIRED_CORRECTION = { center: null, bandwidth: null, monitorRows: '30', fixed: null };

export function pairedSpectralRegion(calibration, settings) {
  const axis = calibration?.wavelengths;
  if (!axis || axis.length < 2) return {};
  const [first, last] = calibration.spectral_calibration?.[1] || [0, axis.length - 1];
  const min = Math.min(axis[first], axis[last]);
  const max = Math.max(axis[first], axis[last]);
  if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) return {};

  const span = max - min;
  const center = settings.center ?? ((min + max) / 2).toFixed(2);
  const bandwidth = settings.bandwidth ?? String(Math.min(120, Math.floor(span * 10) / 10));
  const band = { center_nm: Number(center), half_width_nm: Number(bandwidth) / 2,
    monitor_rows: Number(settings.monitorRows) };
  const low = band.center_nm - band.half_width_nm;
  const high = band.center_nm + band.half_width_nm;
  const available = { min, max, span, center, bandwidth };
  if (!(low >= min && high <= max && band.half_width_nm > 0)
    || !Number.isInteger(band.monitor_rows) || band.monitor_rows < 1 || band.monitor_rows >= calibration.height) return available;

  const columns = axis.flatMap((wavelength, index) =>
    index >= first && index <= last && wavelength >= low && wavelength <= high ? [index] : []);
  if (!columns.length) return available;
  return { ...available, band, bounds: { x0: columns[0], x1: columns.at(-1),
    width: axis.length, height: calibration.height } };
}

// Bounds are inclusive camera-pixel indices, independent of screen scaling.
export function editRoiBounds(bounds, dx, dy, handle, width, height) {
  const next = { ...bounds };
  dx = Math.round(dx);
  dy = Math.round(dy);
  if (handle === 'move') {
    dx = clamp(dx, -bounds.x0, width - 1 - bounds.x1);
    dy = clamp(dy, -bounds.y0, height - 1 - bounds.y1);
    return { x0: bounds.x0 + dx, x1: bounds.x1 + dx, y0: bounds.y0 + dy, y1: bounds.y1 + dy };
  }
  if (handle.includes('w')) next.x0 = clamp(bounds.x0 + dx, 0, bounds.x1 - 1);
  if (handle.includes('e')) next.x1 = clamp(bounds.x1 + dx, bounds.x0 + 1, width - 1);
  if (handle.includes('n')) next.y0 = clamp(bounds.y0 + dy, 0, bounds.y1 - 1);
  if (handle.includes('s')) next.y1 = clamp(bounds.y1 + dy, bounds.y0 + 1, height - 1);
  return next;
}

export function alignmentRegionFromBounds(bounds, calibration) {
  const x0 = Math.min(bounds.x0, calibration.width - 2);
  const x1 = Math.max(bounds.x1, x0 + 1);
  const wavelengths = [calibration.wavelengths[x0], calibration.wavelengths[x1]];
  return { wavelengthMin: Math.min(...wavelengths), wavelengthMax: Math.max(...wavelengths),
    topPercent: 100 * bounds.y0 / calibration.height,
    bottomPercent: 100 * (bounds.y1 + 1) / calibration.height };
}


// Geometry for editing the overlay and remembering cursor positions. Pixel
// intensities and all measurement arithmetic stay on the server.
export function alignmentRegionGeometry(calibration, region) {
  const { wavelengthMin, wavelengthMax, topPercent, bottomPercent } = region;
  if (![wavelengthMin, wavelengthMax, topPercent, bottomPercent].every(Number.isFinite)
    || wavelengthMin < 0 || wavelengthMin >= wavelengthMax || topPercent < 0
    || topPercent >= bottomPercent || bottomPercent > 100) {
    return { error: 'Choose increasing wavelength and vertical limits (0–100%).' };
  }
  const { wavelengths, timedelays, width, height, time_unit: unit } = calibration || {};
  if (!width || !height || wavelengths?.length !== width || timedelays?.length !== height) {
    return { error: 'Waiting for calibrated axes from the Live image.' };
  }
  const columns = wavelengths.flatMap((wavelength, index) =>
    wavelength >= wavelengthMin && wavelength <= wavelengthMax ? [index] : []);
  if (!columns.length) return { error: 'Selected wavelengths are outside the calibrated camera image.' };
  const y0 = Math.min(height - 1, Math.floor(height * topPercent / 100 + 1e-9));
  const y1 = Math.min(height, Math.max(y0 + 1, Math.ceil(height * bottomPercent / 100 - 1e-9))) - 1;
  const times = timedelays.slice(y0, y1 + 1);
  return { bounds: { x0: columns[0], x1: columns[columns.length - 1], y0, y1 },
    timeUnit: unit, timeMin: Math.min(...times), timeMax: Math.max(...times) };
}
