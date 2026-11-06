import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchWithCsrfToken } from '../api/csrfRequest';
import { API_BASE, pumpProbeRequest } from './shared';
import './TreatmentPanel.css';

const OPERATIONS = [
  ['scale', 'Scale OD'], ['raw_od', 'Recalculate original RAW'],
  ['raw_background', 'Detector RAW background'], ['kinetic_clean', 'Kinetic cleaning'],
  ['legacy_baseline', 'Legacy baseline'], ['savitzky_golay', 'SG smoothing'],
  ['replace_nonfinite', 'Replace NaN / infinity'],
];
const canonical = (value) => JSON.stringify(value, (_key, item) => (
  item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]])) : item
));
const sourceIdentity = (source) => canonical([source.path, source.source_sha256, source.source_spec || null]);
const shapeOf = (dataset) => [dataset.heatmap?.length || dataset.delays?.length || 0,
  dataset.wavelengths?.length || dataset.heatmap?.[0]?.length || 0];
function number(value, label, integer = false) {
  if (!['number', 'string'].includes(typeof value) || value === null || value === undefined || typeof value === 'boolean'
      || (typeof value === 'string' && !value.trim()) || !Number.isFinite(Number(value))
      || (integer && !Number.isInteger(Number(value)))) throw new Error(`${label} must be ${integer ? 'an integer' : 'finite'}.`);
  return Number(value);
}
function pair(value, size, label) {
  if (!Array.isArray(value) || value.length !== 2) throw new Error(`${label} requires two pixels.`);
  const result = value.map((x) => number(x, label, true));
  if (result[0] < 0 || result[0] > result[1] || result[1] >= size) throw new Error(`${label} must be ordered within 0..${size - 1}.`);
  return result;
}
function keys(operation, allowed) {
  if (Object.keys(operation).some((key) => !allowed.includes(key))) throw new Error('Unknown operation parameter.');
}
export function validateTreatmentOperation(operation, shape, capabilities) {
  if (!operation || Array.isArray(operation) || typeof operation !== 'object'
      || !capabilities.includes(operation.kind)) throw new Error('Operation is not available for this source.');
  const { kind } = operation;
  if (kind === 'scale') {
    keys(operation, ['kind', 'factor']); return { kind, factor: number(operation.factor, 'Scale factor') };
  }
  if (kind === 'raw_od' || kind === 'raw_background') {
    keys(operation, ['kind', 'zero_slot_policy', ...(kind === 'raw_background' ? ['counts'] : [])]);
    if (!['retain', 'drop_whole_zero'].includes(operation.zero_slot_policy)) throw new Error('Unknown zero-slot policy.');
    const result = { kind, zero_slot_policy: operation.zero_slot_policy };
    if (kind === 'raw_background') {
      if (!Array.isArray(operation.counts) || operation.counts.length !== 2) throw new Error('Two background counts are required.');
      result.counts = operation.counts.map((x) => number(x, 'Background count', true));
      if (result.counts.some((x) => Math.abs(x) > 65535)) throw new Error('Background counts must be within -65535..65535.');
    }
    return result;
  }
  if (kind === 'kinetic_clean') {
    keys(operation, ['kind', 'mode', 'wavelength_pixels', 'delay_pixels', 'od_bounds', 'precision']);
    if (shape[1] < 2) throw new Error('Kinetic cleaning requires at least two wavelength pixels.');
    if (!['delete', 'approx'].includes(operation.mode)) throw new Error('Choose delete or approx cleaning.');
    if (!['legacy_sgl', 'float64'].includes(operation.precision)) throw new Error('Choose a cleaning precision.');
    if (!Array.isArray(operation.od_bounds) || operation.od_bounds.length !== 2) throw new Error('Two OD bounds are required.');
    const bounds = operation.od_bounds.map((x) => number(x, 'OD bound'));
    if (bounds[0] > bounds[1]) throw new Error('OD bounds must be ordered.');
    return { kind, mode: operation.mode, wavelength_pixels: pair(operation.wavelength_pixels, shape[1], 'Wavelength pixels'),
      delay_pixels: pair(operation.delay_pixels, shape[0], 'Delay pixels'), od_bounds: bounds, precision: operation.precision };
  }
  if (kind === 'legacy_baseline') {
    keys(operation, ['kind', 'delay_pixels']);
    return { kind, delay_pixels: pair(operation.delay_pixels, shape[0], 'Delay pixels') };
  }
  if (kind === 'savitzky_golay') {
    keys(operation, ['kind', 'side', 'order', 'axis', 'version', 'weights']);
    const side = number(operation.side, 'SG side', true); const order = number(operation.order, 'Polynomial order', true);
    if (!['wavelength', 'delay'].includes(operation.axis) || side < 0 || order < 0 || order >= 2 * side + 1) throw new Error('SG order must be below its odd window size.');
    if (2 * side + 1 > shape[operation.axis === 'delay' ? 0 : 1]) throw new Error('SG window exceeds the selected axis.');
    if (operation.version !== undefined && operation.version !== 'shifted-polynomial-v1') throw new Error('Unsupported SG version.');
    if (operation.weights !== undefined && (!Array.isArray(operation.weights) || operation.weights.length)) throw new Error('Only unweighted SG is supported.');
    return { kind, side, order, axis: operation.axis, ...(operation.version ? { version: operation.version } : {}), ...(operation.weights ? { weights: [] } : {}) };
  }
  if (kind === 'replace_nonfinite') {
    keys(operation, ['kind', 'nan', 'positive_inf', 'negative_inf']);
    return { kind, nan: number(operation.nan, 'NaN replacement'), positive_inf: number(operation.positive_inf, '+Inf replacement'), negative_inf: number(operation.negative_inf, '-Inf replacement') };
  }
  throw new Error('Unknown operation.');
}
export function validateTreatmentRecipe(recipe, source) {
  if (!recipe || recipe.schema !== 'pyconlyse-v0-recipe-v1' || recipe.source_path !== source.path
      || recipe.source_sha256 !== source.source_sha256 || canonical(recipe.source_spec || null) !== canonical(source.source_spec || null)) throw new Error('Recipe source path, fingerprint or source specification does not match.');
  if (!Array.isArray(recipe.operations) || recipe.operations.length > 32) throw new Error('Recipe requires at most 32 operations.');
  const available = new Set(source.capabilities || []);
  return recipe.operations.map((operation, index) => {
    if (operation?.kind?.startsWith('raw_') && index !== 0) throw new Error('RAW recalculation must be the first operation.');
    const validated = validateTreatmentOperation(operation, shapeOf(source), [...available]);
    // Replay validates each resulting stage; finite replacement/RAW may enable OD operations.
    if (validated.kind === 'replace_nonfinite' || validated.kind.startsWith('raw_')) {
      available.add('kinetic_clean'); available.add('savitzky_golay'); available.add('legacy_baseline');
    }
    return validated;
  });
}
function validResult(result, source) {
  if (!result || result.source_sha256 !== source.source_sha256) throw new Error('Correction response does not match the source fingerprint.');
  const [height, width] = shapeOf(result);
  if (!height || !width || result.delays?.length !== height || result.wavelengths?.length !== width
      || !result.heatmap?.every((row) => Array.isArray(row) && row.length === width)
      || !result.delays.every((x) => typeof x === 'number' && Number.isFinite(x))
      || !result.wavelengths.every((x) => typeof x === 'number' && Number.isFinite(x))
      || (result.source_row_indices && result.source_row_indices.length !== height)) throw new Error('Correction response has inconsistent data and axes.');
  if (canonical(result.source_spec || null) !== canonical(source.source_spec || null)) throw new Error('Correction response source specification changed.');
  return result;
}
function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function defaultPixels(selection, key, size) {
  const candidate = selection?.[key];
  return candidate?.length === 2 ? candidate.map((x) => String(Math.max(0, Math.min(size - 1, x)))) : ['0', String(Math.max(0, size - 1))];
}
function finiteBounds(dataset) {
  let lower = Infinity; let upper = -Infinity;
  (dataset.heatmap || []).forEach((row) => row.forEach((value) => {
    if (typeof value === 'number' && Number.isFinite(value)) { lower = Math.min(lower, value); upper = Math.max(upper, value); }
  }));
  return Number.isFinite(lower) ? [String(lower), String(upper)] : ['-1', '1'];
}

export default function TreatmentPanel({ source, applied, selection, onPreview, onApply, onClose }) {
  const capabilities = useMemo(() => [...new Set([
    ...(applied.capabilities || source.capabilities || []).filter((key) => !key.startsWith('raw_')),
    ...(source.capabilities || []).filter((key) => key.startsWith('raw_')),
  ])], [applied.capabilities, source.capabilities]);
  const [kind, setKind] = useState(capabilities.includes('scale') ? 'scale' : (capabilities[0] || ''));
  const [factor, setFactor] = useState('2'); const [backgroundI, setBackgroundI] = useState('0');
  const [backgroundII, setBackgroundII] = useState('0'); const [zeroPolicy, setZeroPolicy] = useState('retain');
  const [mode, setMode] = useState('delete'); const [precision, setPrecision] = useState('legacy_sgl');
  const shape = useMemo(() => shapeOf(applied), [applied]);
  const [wavePixels, setWavePixels] = useState(() => defaultPixels(selection, 'wavelength_pixels', shape[1]));
  const [delayPixels, setDelayPixels] = useState(() => defaultPixels(selection, 'delay_pixels', shape[0]));
  const [bounds, setBounds] = useState(() => finiteBounds(applied));
  const [axis, setAxis] = useState(shape[1] >= 3 || shape[0] < 3 ? 'wavelength' : 'delay');
  const [side, setSide] = useState(Math.max(...shape) >= 3 ? '1' : '0');
  const [order, setOrder] = useState(Math.max(...shape) >= 3 ? '1' : '0');
  const [replacements, setReplacements] = useState(['2', '2', '-2']);
  const [preview, setPreview] = useState(null); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const mounted = useRef(true); const revision = useRef(0); const requestController = useRef(null); const previewStamp = useRef(null);
  const callbacks = useRef({ onPreview, onApply }); callbacks.current = { onPreview, onApply };
  const sourceKey = sourceIdentity(source);
  const appliedVersion = useRef({ value: applied, revision: 0 });
  if (appliedVersion.current.value !== applied) appliedVersion.current = { value: applied, revision: appliedVersion.current.revision + 1 };
  const appliedKey = canonical([sourceKey, appliedVersion.current.revision]);
  const context = useRef({ sourceKey, appliedKey }); context.current = { sourceKey, appliedKey };
  const previousContext = useRef({ sourceKey, appliedKey });
  const invalidate = useCallback(() => {
    revision.current += 1; requestController.current?.abort(); requestController.current = null; previewStamp.current = null;
    setPreview(null); setBusy(false); setError(''); callbacks.current.onPreview(null);
  }, []);
  const isCurrent = (stamp) => mounted.current && stamp.revision === revision.current
    && stamp.sourceKey === context.current.sourceKey && stamp.appliedKey === context.current.appliedKey;
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; revision.current += 1; requestController.current?.abort(); };
  }, []);
  useEffect(() => {
    if (previousContext.current.sourceKey !== sourceKey || previousContext.current.appliedKey !== appliedKey) {
      invalidate();
      setWavePixels((current) => current.map((x) => String(Math.max(0, Math.min(shape[1] - 1, Number(x) || 0)))));
      setDelayPixels((current) => current.map((x) => String(Math.max(0, Math.min(shape[0] - 1, Number(x) || 0)))));
      previousContext.current = { sourceKey, appliedKey };
    }
  }, [sourceKey, appliedKey, shape, invalidate]); // Requests carry their own source and applied revision.
  useEffect(() => {
    if (!capabilities.includes(kind)) { invalidate(); setKind(capabilities[0] || ''); }
  }, [capabilities, kind, invalidate]);
  const changed = (setter) => (event) => { invalidate(); setter(event.target.value); };
  const changedPair = (setter, values, index) => (event) => {
    invalidate(); setter(values.map((value, i) => i === index ? event.target.value : value));
  };
  const requestFields = () => ({ path: source.path, source_sha256: source.source_sha256,
    ...(source.source_spec ? { source_spec: source.source_spec } : {}) });
  const runPreview = async (operations) => {
    invalidate(); const stamp = { ...context.current, revision: revision.current };
    const controller = new AbortController(); requestController.current = controller; setBusy(true);
    try {
      const result = await pumpProbeRequest('/data/treat', { method: 'POST', signal: controller.signal,
        body: JSON.stringify({ ...requestFields(), operations }) });
      if (isCurrent(stamp)) { validResult(result, source); previewStamp.current = stamp; setPreview(result); callbacks.current.onPreview(result); }
    } catch (failure) {
      if (isCurrent(stamp) && failure.name !== 'AbortError') setError(failure.message);
    } finally { if (isCurrent(stamp)) setBusy(false); }
  };
  const previewCorrection = async () => {
    try {
      let operation = { kind };
      if (kind === 'scale') operation.factor = factor;
      if (kind.startsWith('raw_')) operation.zero_slot_policy = zeroPolicy;
      if (kind === 'raw_background') operation.counts = [backgroundI, backgroundII];
      if (kind === 'kinetic_clean') operation = { kind, mode, precision, wavelength_pixels: wavePixels, delay_pixels: delayPixels, od_bounds: bounds };
      if (kind === 'legacy_baseline') operation.delay_pixels = delayPixels;
      if (kind === 'savitzky_golay') operation = { kind, side, order, axis, version: 'shifted-polynomial-v1', weights: [] };
      if (kind === 'replace_nonfinite') operation = { kind, nan: replacements[0], positive_inf: replacements[1], negative_inf: replacements[2] };
      operation = validateTreatmentOperation(operation, shape, capabilities);
      const operations = kind.startsWith('raw_') ? [operation] : [...(applied.operations || []), operation];
      if (operations.length > 32) throw new Error('Recipe requires at most 32 operations.');
      await runPreview(operations);
    } catch (failure) { invalidate(); setError(failure.message); }
  };
  const applyPreview = () => {
    if (!preview || !previewStamp.current || !isCurrent(previewStamp.current)) { invalidate(); return; }
    callbacks.current.onApply(preview); invalidate();
  };
  const exportData = async () => {
    invalidate(); const stamp = { ...context.current, revision: revision.current };
    const controller = new AbortController(); requestController.current = controller; setBusy(true);
    try {
      const response = await fetchWithCsrfToken(`${API_BASE}/data/treat`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ ...requestFields(), operations: applied.operations || [], format: 'dat' }) });
      if (!response.ok) { const result = await response.json(); throw new Error(result.error || 'DAT export failed.'); }
      const blob = await response.blob();
      if (isCurrent(stamp)) downloadBlob(blob, `${(source.file_name || 'derived').replace(/\.[^.]+$/, '')}-corrected.dat`);
    } catch (failure) { if (isCurrent(stamp) && failure.name !== 'AbortError') setError(failure.message); }
    finally { if (isCurrent(stamp)) setBusy(false); }
  };
  const exportRecipe = () => {
    const recipe = { schema: 'pyconlyse-v0-recipe-v1', source_path: source.path, source_sha256: source.source_sha256,
      ...(source.source_spec ? { source_spec: source.source_spec } : {}), raw_layout: source.raw_layout,
      od_algorithm: applied.od_algorithm, operations: applied.operations || [] };
    downloadBlob(new Blob([JSON.stringify(recipe, null, 2)], { type: 'application/json' }), `${(source.file_name || 'derived').replace(/\.[^.]+$/, '')}-recipe.json`);
  };
  const importRecipe = async (event) => {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file) return;
    invalidate(); const stamp = { ...context.current, revision: revision.current };
    try {
      const text = await file.text(); if (!isCurrent(stamp)) return;
      const operations = validateTreatmentRecipe(JSON.parse(text), source);
      await runPreview(operations);
    } catch (failure) { if (isCurrent(stamp)) setError(failure.message); }
  };
  const useSelection = () => {
    invalidate(); setWavePixels(defaultPixels(selection, 'wavelength_pixels', shape[1]));
    setDelayPixels(defaultPixels(selection, 'delay_pixels', shape[0]));
  };
  const displayed = preview || applied; const nonfinite = displayed.nonfinite_counts || {};
  const removed = displayed.shot_selection?.removed_zero_slots?.reduce((sum, count) => sum + count, 0) || 0;

  const pixelInputs = (title, values, setter, size) => (
    <fieldset><legend>{title} (inclusive, 0..{size - 1})</legend>
      {['lower', 'upper'].map((label, index) => <label key={label}>{title} {label}
        <input type="number" step="1" value={values[index]} onChange={changedPair(setter, values, index)} />
      </label>)}
    </fieldset>
  );
  return (
    <section className="pp-treatment-window" role="dialog" aria-label="OD corrections">
      <div className="pp-panel-title"><span>OD corrections</span>
        <button type="button" onClick={() => { invalidate(); onClose(); }} aria-label="Close corrections">x</button>
      </div>
      <div className="pp-treatment-body">
        <div className="pp-treatment-source" title={source.path}>{source.file_name || 'Derived dataset'}</div>
        <label>Operation<select value={kind} onChange={changed(setKind)} disabled={!capabilities.length}>
          {OPERATIONS.filter(([key]) => capabilities.includes(key)).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
        {kind === 'scale' && <label>Scale factor<input type="number" step="any" value={factor} onChange={changed(setFactor)} /></label>}
        {kind.startsWith('raw_') && <>
          {kind === 'raw_background' && <div className="pp-treatment-counts">
            <label>Detector I, counts<input type="number" step="1" value={backgroundI} onChange={changed(setBackgroundI)} /></label>
            <label>Detector II, counts<input type="number" step="1" value={backgroundII} onChange={changed(setBackgroundII)} /></label>
          </div>}
          <label>Stored zero slots<select value={zeroPolicy} onChange={changed(setZeroPolicy)}>
            <option value="retain">Retain every shot slot</option><option value="drop_whole_zero">Exclude slots with all six groups zero</option>
          </select></label><p>RAW recalculation starts a new recipe from original shots.</p>
        </>}
        {(kind === 'kinetic_clean' || kind === 'legacy_baseline') && <>
          <button type="button" onClick={useSelection} disabled={Boolean(preview)} title={preview ? 'Apply or cancel preview before selecting pixels' : undefined}>Use current selection</button>
          {pixelInputs('Delay pixels', delayPixels, setDelayPixels, shape[0])}
        </>}
        {kind === 'kinetic_clean' && <>
          {pixelInputs('Wavelength pixels', wavePixels, setWavePixels, shape[1])}
          <label>Cleaning mode<select value={mode} onChange={changed(setMode)}><option value="delete">Delete rows</option><option value="approx">Replace with neighbors</option></select></label>
          <label>Precision<select value={precision} onChange={changed(setPrecision)}><option value="legacy_sgl">Legacy single precision</option><option value="float64">Float64</option></select></label>
          <div className="pp-treatment-counts">{['lower', 'upper'].map((label, index) => <label key={label}>OD {label}
            <input type="number" step="any" value={bounds[index]} onChange={changedPair(setBounds, bounds, index)} /></label>)}</div>
          <p>Delete changes OD rows and delay positions. Original RAW remains available.</p>
        </>}
        {kind === 'legacy_baseline' && <p>Legacy scalar subtraction can shorten the delay map. Check the preview before applying.</p>}
        {kind === 'savitzky_golay' && <>
          <label>Filter axis<select value={axis} onChange={changed(setAxis)}><option value="wavelength">Wavelength</option><option value="delay">Delay</option></select></label>
          <label>SG side<input type="number" min="0" step="1" value={side} onChange={changed(setSide)} /></label>
          <label>Polynomial order<input type="number" min="0" step="1" value={order} onChange={changed(setOrder)} /></label>
          <p>Web shifted-window polynomial filter; window = 2 * side + 1.</p>
        </>}
        {kind === 'replace_nonfinite' && <div className="pp-treatment-counts">
          {['NaN replacement', '+Inf replacement', '-Inf replacement'].map((label, index) => <label key={label}>{label}
            <input type="number" step="any" value={replacements[index]} onChange={changedPair(setReplacements, replacements, index)} /></label>)}
        </div>}
        <div className="pp-treatment-actions">
          <button type="button" onClick={previewCorrection} disabled={busy || !kind}>{busy ? 'Calculating...' : 'Preview'}</button>
          <button type="button" onClick={applyPreview} disabled={busy || !preview}>Apply</button>
          <button type="button" onClick={invalidate} disabled={!busy && !preview}>Cancel preview</button>
          <button type="button" onClick={() => { invalidate(); callbacks.current.onApply(source); }}>Reset to source</button>
        </div>
        <p role="status">{preview ? 'Preview shown; changes pending.' : `${applied.operations?.length || 0} applied corrections (in memory).`}</p>
        <p>NaN: {nonfinite.nan || 0}; +Inf: {nonfinite.positive_inf || 0}; -Inf: {nonfinite.negative_inf || 0}; excluded zero slots: {removed}</p>
        {displayed.source_row_indices && <p>Source rows: {displayed.source_row_indices.join(', ')}</p>}
        {!!displayed.modified_source_row_indices?.length && <p>Modified source rows: {displayed.modified_source_row_indices.join(', ')}</p>}
        {error && <p role="alert" className="pp-treatment-error">{error}</p>}
        <div className="pp-treatment-actions">
          <button type="button" onClick={exportData} disabled={busy || Boolean(preview)}>Download DAT</button>
          <button type="button" onClick={exportRecipe} disabled={busy || Boolean(preview)}>Download recipe</button>
          <label className="pp-treatment-import">Import recipe<input aria-label="Import recipe" type="file" accept="application/json,.json" onChange={importRecipe} /></label>
        </div>
      </div>
    </section>
  );
}
