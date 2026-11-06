import React, { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import TreatmentPanel, { validateTreatmentOperation, validateTreatmentRecipe } from './TreatmentPanel';
import { pumpProbeRequest } from './shared';
import { fetchWithCsrfToken } from '../api/csrfRequest';

jest.mock('./shared', () => ({ API_BASE: '/api/pump-probe-v0', pumpProbeRequest: jest.fn() }));
jest.mock('../api/csrfRequest', () => ({ fetchWithCsrfToken: jest.fn() }));

const capabilities = ['scale', 'raw_od', 'raw_background', 'kinetic_clean', 'legacy_baseline',
  'savitzky_golay', 'replace_nonfinite'];
const source = {
  path: '/data/experiment.zip', file_name: 'experiment.zip', source_sha256: 'a'.repeat(64),
  heatmap: [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]],
  delays: [-1, 0, 0, 2], wavelengths: [500, 600, 700], operations: [], capabilities,
  raw_layout: 'trancon-detectors-v1', od_algorithm: 'signed-mean-of-shot-log10-v1',
};
const replacement = { kind: 'replace_nonfinite', nan: -1.25, positive_inf: 9, negative_inf: -9 };
const smoothing = { kind: 'savitzky_golay', side: 1, order: 1, axis: 'wavelength',
  version: 'shifted-polynomial-v1', weights: [] };
const cleaning = { kind: 'kinetic_clean', mode: 'delete', wavelength_pixels: [0, 2],
  delay_pixels: [0, 3], od_bounds: [0, 10], precision: 'float64' };
const nonfiniteSource = { ...source, heatmap: [[null, 2, 3], ...source.heatmap.slice(1)],
  capabilities: ['scale', 'replace_nonfinite', 'raw_od'], nonfinite_counts: { nan: 1, positive_inf: 0, negative_inf: 0 } };

function recipe(operations, original = source) {
  return { schema: 'pyconlyse-v0-recipe-v1', source_path: original.path,
    source_sha256: original.source_sha256, ...(original.source_spec ? { source_spec: original.source_spec } : {}), operations };
}

function Harness({ original = source, initialApplied = original, onPreview = jest.fn(),
  onApply = jest.fn(), onClose = jest.fn(), selection }) {
  const [applied, setApplied] = useState(initialApplied);
  return <TreatmentPanel source={original} applied={applied} selection={selection} onPreview={onPreview}
    onApply={(value) => { setApplied(value); onApply(value); }} onClose={onClose} />;
}

function mockSuccess(original = source, resultFields = {}) {
  pumpProbeRequest.mockImplementation((_path, options) => Promise.resolve({
    ...original, operations: JSON.parse(options.body).operations, ...resultFields,
  }));
}

function change(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value: String(value) } });
}

function request(index = 0) {
  return JSON.parse(pumpProbeRequest.mock.calls[index][1].body);
}

function importRecipe(value) {
  const file = new File([JSON.stringify(value)], 'experiment-recipe.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: jest.fn().mockResolvedValue(JSON.stringify(value)) });
  fireEvent.change(screen.getByLabelText('Import recipe'), { target: { files: [file] } });
}

function readBlob(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsText(blob);
  });
}

const originalCreate = URL.createObjectURL;
const originalRevoke = URL.revokeObjectURL;
let anchorClick;
beforeEach(() => {
  pumpProbeRequest.mockReset(); fetchWithCsrfToken.mockReset();
  URL.createObjectURL = jest.fn(() => 'blob:migration-test');
  URL.revokeObjectURL = jest.fn();
  anchorClick = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => {
  anchorClick.mockRestore();
  URL.createObjectURL = originalCreate;
  URL.revokeObjectURL = originalRevoke || jest.fn();
});

test.each([['delete', 'legacy_sgl'], ['approx', 'float64']])(
  'constructs %s cleaning from inclusive pixels, OD bounds and explicit %s precision', async (mode, precision) => {
    mockSuccess();
    const onApply = jest.fn();
    render(<Harness selection={{ wavelength_pixels: [1, 2], delay_pixels: [1, 2] }} onApply={onApply} />);
    change('Operation', 'kinetic_clean');
    expect(screen.getByLabelText('Delay pixels lower')).toHaveValue(1);
    expect(screen.getByLabelText('Delay pixels upper')).toHaveValue(2);
    expect(screen.getByLabelText('Wavelength pixels lower')).toHaveValue(1);
    change('Delay pixels lower', 0); change('Delay pixels upper', 3);
    change('Wavelength pixels lower', 0); change('Wavelength pixels upper', 2);
    change('Cleaning mode', mode); change('Precision', precision);
    change('OD lower', -1.5); change('OD upper', 4.25);
    fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
    await screen.findByText('Preview shown; changes pending.');
    expect(request()).toEqual({ path: source.path, source_sha256: source.source_sha256,
      operations: [{ kind: 'kinetic_clean', mode, precision, wavelength_pixels: [0, 2],
        delay_pixels: [0, 3], od_bounds: [-1.5, 4.25] }] });
    expect(onApply).not.toHaveBeenCalled();
    expect(source.operations).toEqual([]);
  },
);

test('legacy baseline sends selected positional delay interval and warns about truncation', async () => {
  mockSuccess();
  render(<Harness selection={{ delay_pixels: [1, 2], wavelength_pixels: [0, 2] }} />);
  change('Operation', 'legacy_baseline');
  expect(screen.getByText(/Legacy scalar subtraction can shorten the delay map/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(request().operations).toEqual([{ kind: 'legacy_baseline', delay_pixels: [1, 2] }]);
  // Duplicate delay values remain different positional pixels.
  expect(source.delays.slice(1, 3)).toEqual([0, 0]);
});

test('SG binds version and chosen axis; longer window must fit that axis', async () => {
  const longDelays = { ...source, delays: [0, 1, 2, 3, 4, 5, 6], heatmap: Array.from({ length: 7 }, () => [1, 2, 3]) };
  mockSuccess(longDelays);
  render(<Harness original={longDelays} />);
  change('Operation', 'savitzky_golay'); change('SG side', 2); change('Polynomial order', 2);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('SG window exceeds the selected axis.');
  expect(pumpProbeRequest).not.toHaveBeenCalled();
  change('Filter axis', 'delay');
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(request().operations).toEqual([{ kind: 'savitzky_golay', side: 2, order: 2, axis: 'delay',
    version: 'shifted-polynomial-v1', weights: [] }]);
  expect(screen.getByText(/Web shifted-window polynomial filter/)).toBeInTheDocument();
});

test('replacement rejects blank values and unlocks cleaning/SG after explicit Apply', async () => {
  const finiteResult = { heatmap: [[-1.25, 2, 3], ...source.heatmap.slice(1)],
    capabilities: capabilities.filter((kind) => !kind.startsWith('raw_')),
    nonfinite_counts: { nan: 0, positive_inf: 0, negative_inf: 0 } };
  mockSuccess(nonfiniteSource, finiteResult);
  render(<Harness original={nonfiniteSource} />);
  expect(screen.queryByRole('option', { name: 'Kinetic cleaning' })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'SG smoothing' })).not.toBeInTheDocument();
  change('Operation', 'replace_nonfinite'); change('NaN replacement', '');
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('NaN replacement must be finite.');
  expect(pumpProbeRequest).not.toHaveBeenCalled();
  change('NaN replacement', -1.25); change('+Inf replacement', 9); change('-Inf replacement', -9);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(request().operations).toEqual([replacement]);
  expect(screen.queryByRole('option', { name: 'SG smoothing' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
  expect(screen.getByRole('option', { name: 'Kinetic cleaning' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'SG smoothing' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Recalculate original RAW' })).toBeInTheDocument();
  change('Operation', 'kinetic_clean');
  // null is a displayed gap, never an implicit zero in finite OD bounds.
  expect(screen.getByLabelText('OD lower')).toHaveValue(2);
  change('Operation', 'savitzky_golay');
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(request(1).operations).toEqual([replacement, smoothing]);
});

test('exported replacement→SG recipe reimports against original nonfinite capabilities', async () => {
  const applied = { ...nonfiniteSource, operations: [replacement, smoothing],
    capabilities: capabilities.filter((kind) => !kind.startsWith('raw_')) };
  mockSuccess(nonfiniteSource, { ...applied });
  render(<Harness original={nonfiniteSource} initialApplied={applied} />);
  fireEvent.click(screen.getByRole('button', { name: 'Download recipe' }));
  expect(anchorClick).toHaveBeenCalledTimes(1);
  const exported = JSON.parse(await readBlob(URL.createObjectURL.mock.calls[0][0]));
  expect(exported).toMatchObject({ schema: 'pyconlyse-v0-recipe-v1', source_path: source.path,
    source_sha256: source.source_sha256, operations: [replacement, smoothing] });
  importRecipe(exported);
  await screen.findByText('Preview shown; changes pending.');
  expect(request().operations).toEqual([replacement, smoothing]);
  expect(request().source_sha256).toBe(source.source_sha256);
});

test.each([
  [[replacement, { kind: 'legacy_baseline', delay_pixels: [0, 1] }]],
  [[{ kind: 'raw_od', zero_slot_policy: 'retain' }, cleaning]],
])('recipe schema accepts finite-producing prefix followed by supported OD treatment', (operations) => {
  expect(validateTreatmentRecipe(recipe(operations, nonfiniteSource), nonfiniteSource)).toEqual(operations);
  expect(() => validateTreatmentRecipe(recipe([operations[1]], nonfiniteSource), nonfiniteSource)).toThrow();
});

test('derived preview, DAT and recipe export preserve ordered source_spec and fingerprint', async () => {
  const sourceSpec = { kind: 'derived', method: 'average', sources: [
    { path: '/data/a.dat', source_sha256: 'b'.repeat(64) },
    { path: '/data/b.dat', source_sha256: 'c'.repeat(64) },
  ] };
  const derived = { ...source, path: `derived:${source.source_sha256}`, file_name: 'average', source_spec: sourceSpec };
  const onApply = jest.fn();
  mockSuccess(derived);
  fetchWithCsrfToken.mockResolvedValue({ ok: true, blob: async () => new Blob(['derived data']) });
  render(<Harness original={derived} onApply={onApply} />);
  change('Operation', 'legacy_baseline'); change('Delay pixels lower', 0); change('Delay pixels upper', 1);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(request()).toMatchObject({ path: derived.path, source_sha256: derived.source_sha256, source_spec: sourceSpec });
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
  fireEvent.click(screen.getByRole('button', { name: 'Download DAT' }));
  await waitFor(() => expect(anchorClick).toHaveBeenCalledTimes(1));
  expect(fetchWithCsrfToken.mock.calls[0][0]).toBe('/api/pump-probe-v0/data/treat');
  expect(JSON.parse(fetchWithCsrfToken.mock.calls[0][1].body)).toEqual({ path: derived.path,
    source_sha256: derived.source_sha256, source_spec: sourceSpec, format: 'dat',
    operations: [{ kind: 'legacy_baseline', delay_pixels: [0, 1] }] });
  expect(fetchWithCsrfToken.mock.calls[0][1]).toMatchObject({ credentials: 'include', method: 'POST' });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Download recipe' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Download recipe' }));
  const exported = JSON.parse(await readBlob(URL.createObjectURL.mock.calls[1][0]));
  expect(exported.source_spec).toEqual(sourceSpec);
  expect(exported.source_sha256).toBe(derived.source_sha256);
  expect(onApply).toHaveBeenCalledTimes(1);
});

test('response with changed derived contributors never becomes an applicable preview', async () => {
  const spec = { kind: 'derived', method: 'merge', sources: [{ path: 'a', source_sha256: 'b'.repeat(64) }] };
  const derived = { ...source, source_spec: spec };
  pumpProbeRequest.mockResolvedValue({ ...derived, source_spec: { ...spec, method: 'average' } });
  const onPreview = jest.fn();
  render(<Harness original={derived} onPreview={onPreview} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('source specification changed');
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  expect(onPreview.mock.calls.every(([value]) => value === null)).toBe(true);
});

test('late parameter response cannot replace a newer preview or its applied recipe', async () => {
  let finishOld;
  const old = { ...source, operations: [{ kind: 'scale', factor: 2 }], heatmap: source.heatmap.map((row) => row.map(() => 99)) };
  const latest = { ...source, operations: [{ kind: 'scale', factor: 3 }] };
  pumpProbeRequest.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }))
    .mockResolvedValueOnce(latest);
  const onPreview = jest.fn(); const onApply = jest.fn();
  render(<Harness onPreview={onPreview} onApply={onApply} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  const oldSignal = pumpProbeRequest.mock.calls[0][1].signal;
  change('Scale factor', 3);
  expect(oldSignal.aborted).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  await act(async () => finishOld(old));
  expect(onPreview).not.toHaveBeenCalledWith(old);
  expect(onPreview).toHaveBeenLastCalledWith(latest);
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
  expect(onApply).toHaveBeenLastCalledWith(latest);
});

test.each(['close', 'reset'])('%s during pending request cannot resurrect its preview', async (action) => {
  let finish;
  const result = { ...source, operations: [{ kind: 'scale', factor: 2 }] };
  pumpProbeRequest.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const onPreview = jest.fn(); const onApply = jest.fn(); const onClose = jest.fn();
  render(<Harness onPreview={onPreview} onApply={onApply} onClose={onClose} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  const signal = pumpProbeRequest.mock.calls[0][1].signal;
  fireEvent.click(screen.getByRole('button', { name: action === 'close' ? 'Close corrections' : 'Reset to source' }));
  expect(signal.aborted).toBe(true);
  await act(async () => finish(result));
  expect(onPreview).not.toHaveBeenCalledWith(result);
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  if (action === 'reset') expect(onApply).toHaveBeenCalledWith(source);
  else { expect(onApply).not.toHaveBeenCalled(); expect(onClose).toHaveBeenCalledTimes(1); }
});

test('reset while reading imported recipe ignores the late file without sending treatment', async () => {
  let finishText;
  const file = new File(['pending'], 'recipe.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: () => new Promise((resolve) => { finishText = resolve; }) });
  const onApply = jest.fn();
  render(<Harness onApply={onApply} />);
  fireEvent.change(screen.getByLabelText('Import recipe'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'Reset to source' }));
  await act(async () => finishText(JSON.stringify(recipe([smoothing]))));
  expect(pumpProbeRequest).not.toHaveBeenCalled();
  expect(onApply).toHaveBeenCalledTimes(1);
  expect(onApply).toHaveBeenCalledWith(source);
});

test.each([
  { kind: 'scale', factor: [] }, { kind: 'scale', factor: {} },
  { ...cleaning, delay_pixels: [{}, 1] }, { ...cleaning, wavelength_pixels: [[0], 1] },
  { ...cleaning, od_bounds: [null, 1] }, { ...cleaning, od_bounds: [0, {}] },
  { ...smoothing, side: [] }, { ...smoothing, order: {} },
  { ...replacement, nan: null }, { ...replacement, positive_inf: [] }, { ...replacement, negative_inf: {} },
  { kind: 'raw_background', zero_slot_policy: 'retain', counts: [0, {}] },
  ['scale'],
])('rejects malformed imported numeric parameter instead of coercing to zero: %j', (operation) => {
  expect(() => validateTreatmentRecipe(recipe([operation]), source)).toThrow();
});

test('UI import rejects object operations and source fingerprint/spec mismatches before request', async () => {
  const derived = { ...source, source_spec: { kind: 'derived', method: 'average', sources: [] } };
  render(<Harness original={derived} />);
  importRecipe({ ...recipe([], derived), operations: { kind: 'scale', factor: 2 } });
  expect(await screen.findByRole('alert')).toHaveTextContent('at most 32 operations');
  importRecipe({ ...recipe([smoothing], derived), source_sha256: 'd'.repeat(64) });
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('does not match'));
  importRecipe({ ...recipe([smoothing], derived), source_spec: { ...derived.source_spec, method: 'merge' } });
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('does not match'));
  expect(pumpProbeRequest).not.toHaveBeenCalled();
});

test('SG validator distinguishes explicit model version, unweighted policy and axis length', () => {
  expect(validateTreatmentOperation(smoothing, [4, 3], capabilities)).toEqual(smoothing);
  expect(() => validateTreatmentOperation({ ...smoothing, version: 'NI-exact' }, [4, 3], capabilities)).toThrow(/version/);
  expect(() => validateTreatmentOperation({ ...smoothing, weights: [1, 1, 1] }, [4, 3], capabilities)).toThrow(/unweighted/);
  expect(() => validateTreatmentOperation({ ...smoothing, side: 2, order: 2 }, [7, 3], capabilities)).toThrow(/axis/);
  expect(validateTreatmentOperation({ ...smoothing, side: 2, order: 2, axis: 'delay' }, [7, 3], capabilities)).toMatchObject({ axis: 'delay', side: 2 });
});
