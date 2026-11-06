import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import SkanaPanel from './SkanaPanel';

jest.mock('plotly.js-dist', () => ({ react: jest.fn().mockResolvedValue(undefined), purge: jest.fn() }));
beforeEach(() => { window.sessionStorage.clear(); });

const dataset = (extra = {}) => ({ ready: true, source: 'od', label: 'Calculated OD', shape: [4, 3],
  times: [0, 1, 2, 3], wavelengths: [400, 500, 600], time_unit: 'ns', signal_unit: 'OD',
  fingerprint: 'matrix-v1', ...extra });
const result = (extra = {}) => ({ method: 'svd', components: 2, time_unit: 'ns',
  times: [0, 1, 2, 3], wavelengths: [400, 500, 600], lof_percent: 1.25, rmse: 0.01,
  concentrations: [[1, 0], [0.6, 0.4], [0.3, 0.7], [0.1, 0.9]], spectra: [[1, 0], [0, 1], [1, 1]],
  singular_values: [3, 2, 0.01], converged: true, iterations: 1,
  model_preview: { z: [[1, 2, 3]], times: [0], wavelengths: [400, 500, 600] },
  residual_preview: { z: [[0, 0, 0]], times: [0], wavelengths: [400, 500, 600] }, ...extra });
function api(extra = {}) {
  return { dataset: jest.fn().mockResolvedValue({ dataset: dataset() }),
    import: jest.fn().mockResolvedValue({ dataset: dataset({ source: 'import' }) }),
    start: jest.fn().mockResolvedValue({ job: { id: 'job-one', status: 'queued' } }),
    status: jest.fn().mockResolvedValue({ job: { id: 'job-one', status: 'completed' }, result: result() }),
    cancel: jest.fn().mockResolvedValue({ job: { id: 'job-one', status: 'cancelled' } }),
    download: jest.fn().mockResolvedValue(new Blob(['{}'])), ...extra };
}
async function loaded(client = api()) {
  const view = render(<SkanaPanel client={client} sessionId="session-a" />);
  await screen.findByText(/4 delays × 3 wavelengths/);
  return { client, ...view };
}

test('existing engine limitations are visible even for a numerically completed fit', async () => {
  const client = api({ status: jest.fn().mockResolvedValue({ job: { id: 'job-one', status: 'completed' },
    result: result({ warnings: ['Existing SK-Ana restricts one free kinetic spectrum to nonnegative slope.'] }) }) });
  await loaded(client);
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('one free kinetic spectrum');
});

test('opens a separate analysis panel without calculating or treating downsampled previews', async () => {
  const { client } = await loaded();
  expect(screen.getByRole('heading', { name: 'SK-Ana · Spectrokinetic analysis' })).toBeInTheDocument();
  expect(client.dataset).toHaveBeenCalledWith('session-a', 'od', expect.any(AbortSignal));
  expect(client.start).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  expect(await screen.findByRole('region', { name: 'SK-Ana results' })).toHaveTextContent('Lack of fit: 1.2500%');
  expect(client.start).toHaveBeenCalledWith('session-a', { source: 'od', fingerprint: 'matrix-v1', method: 'svd',
    options: { rank: 2, max_rank: 10 } }, expect.any(AbortSignal));
  expect(client.download).not.toHaveBeenCalled();
});

test('no calculated OD gives clear instructions and disables fitting', async () => {
  const client = api({ dataset: jest.fn().mockResolvedValue({ dataset: dataset({ ready: false }) }) });
  render(<SkanaPanel client={client} sessionId="session-a" />);
  expect(await screen.findByText(/Calculate OD in Treatment/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Run analysis' })).toBeDisabled();
  expect(client.start).not.toHaveBeenCalled();
});

test('ALS options preserve component signs and upstream initialization/normalization names', async () => {
  const { client } = await loaded();
  fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'mcr_als' } });
  fireEvent.click(screen.getByLabelText('Per-component spectral constraints'));
  fireEvent.click(screen.getByLabelText('Spectrum 2 nonnegative'));
  fireEvent.change(screen.getByLabelText('Initialization'), { target: { value: 'pca' } });
  fireEvent.change(screen.getByLabelText('Spectral normalization'), { target: { value: 'l1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await screen.findByRole('region', { name: 'SK-Ana results' });
  expect(client.start.mock.calls[0][1]).toMatchObject({ method: 'mcr_als', options: {
    n_components: 2, maxiter: 1000, thresh: 1e-6, init_method: 'pca', nonneg_c: true,
    nonneg_s: [true, false], norm_s: true, norm_mode: 'l1' } });
});

test('kinetics preserves unknown units until user supplies an explicit unit', async () => {
  const client = api({ dataset: jest.fn().mockResolvedValue({ dataset: dataset({ time_unit: '??' }) }) });
  await loaded(client);
  fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'target' } });
  expect(screen.getByRole('button', { name: 'Run analysis' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Explicit kinetic time unit'), { target: { value: 'ps' } });
  fireEvent.change(screen.getByLabelText('Reaction scheme'), { target: { value: 'A -> B ; 0.1 / 1\nc0_A_1=1/1\neps_A=1/1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await screen.findByRole('region', { name: 'SK-Ana results' });
  expect(client.start.mock.calls[0][1].options).toMatchObject({ time_unit: 'ps', global_generations: 0,
    population_factor: 15, nonnegative_s: false, tol: 1e-8 });
  expect(screen.queryByRole('option', { name: /DAS/ })).not.toBeInTheDocument();
});

test('nonconvergence is an explicit warning and diagnostics remain inspectable', async () => {
  const client = api({ status: jest.fn().mockResolvedValue({ job: { id: 'job-one', status: 'completed' },
    result: result({ converged: false, iterations: null, diagnostics: { reason: 'iteration limit' } }) }) });
  await loaded(client);
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Convergence was not reached');
  expect(screen.getByText(/"iteration limit"/)).toBeInTheDocument();
  expect(screen.getByText(/iterations: not reported by engine/)).toBeInTheDocument();
});

test('imports user-selected text with explicit orientation, time unit and a new dataset identity', async () => {
  const client = api({ dataset: jest.fn().mockResolvedValueOnce({ dataset: dataset() })
    .mockResolvedValue({ dataset: dataset({ source: 'import', fingerprint: 'import-v2', label: 'closed.csv' }) }) });
  await loaded(client);
  const file = { name: 'closed.csv', size: 45, text: jest.fn().mockResolvedValue('time,400,500\n0,1,2\n1,2,3') };
  fireEvent.change(screen.getByLabelText('Matrix text file'), { target: { files: [file] } });
  fireEvent.change(screen.getByLabelText('Table orientation'), { target: { value: 'wavelength_rows' } });
  fireEvent.change(screen.getByLabelText('Imported time unit'), { target: { value: 'us' } });
  fireEvent.click(screen.getByRole('button', { name: 'Import matrix' }));
  await screen.findByText(/closed.csv · 4 delays/);
  expect(client.import).toHaveBeenCalledWith('session-a', { text: 'time,400,500\n0,1,2\n1,2,3',
    filename: 'closed.csv', time_unit: 'us', orientation: 'wavelength_rows' }, expect.any(AbortSignal));
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await screen.findByRole('region', { name: 'SK-Ana results' });
  expect(client.start.mock.calls[0][1]).toMatchObject({ source: 'import', fingerprint: 'import-v2' });
});

test('a refresh invalidates prior output and stale async results cannot replace the new matrix', async () => {
  let complete;
  const client = api({ status: jest.fn(() => new Promise((resolve) => { complete = resolve; })) });
  const view = await loaded(client);
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(client.status).toHaveBeenCalledTimes(1));
  const priorSignal = client.status.mock.calls[0][2];
  view.rerender(<SkanaPanel client={client} sessionId="session-b" refreshToken={1} />);
  await screen.findByText(/4 delays × 3 wavelengths/);
  expect(priorSignal.aborted).toBe(true);
  await act(async () => { complete({ job: { id: 'job-one', status: 'completed' }, result: result() }); });
  expect(screen.queryByRole('region', { name: 'SK-Ana results' })).not.toBeInTheDocument();
  expect(client.cancel).toHaveBeenCalledWith('session-a', 'job-one');
});

test('polling is latest-only and leaving the tab aborts HTTP reads without cancelling server analysis', async () => {
  jest.useFakeTimers();
  try {
    let settle;
    const client = api({ status: jest.fn(() => new Promise((resolve) => { settle = resolve; })) });
    const view = render(<SkanaPanel client={client} sessionId="session-a" />);
    await act(async () => { await Promise.resolve(); });
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
    await act(async () => { await Promise.resolve(); });
    await act(async () => { jest.advanceTimersByTime(10000); });
    expect(client.status).toHaveBeenCalledTimes(1);
    const signal = client.status.mock.calls[0][2];
    view.unmount();
    expect(signal.aborted).toBe(true);
    expect(client.cancel).not.toHaveBeenCalled();
    await act(async () => { settle({ job: { id: 'job-one', status: 'completed' }, result: result() }); });
    await act(async () => { jest.advanceTimersByTime(10000); });
    expect(client.status).toHaveBeenCalledTimes(1);
  } finally { jest.useRealTimers(); }
});

test('returning to the tab restores imported source and running job without starting another fit', async () => {
  let finishOldRead;
  const imported = dataset({ source: 'import', fingerprint: 'import-matrix-v1', label: 'Imported dataset' });
  const latest = { id: 'job-one', status: 'running', method: 'mcr_als', source: 'import', fingerprint: imported.fingerprint };
  const client = api();
  client.dataset.mockImplementation((_session, source) => Promise.resolve({
    dataset: source === 'import' ? imported : dataset(),
    latest_job: source === 'import' && client.start.mock.calls.length ? latest : null,
  }));
  client.status.mockImplementationOnce(() => new Promise((resolve) => { finishOldRead = resolve; }))
    .mockResolvedValue({ job: { ...latest, status: 'completed' }, result: result({ method: 'mcr_als', lof_percent: 0.25 }) });
  const first = await loaded(client);
  fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'import' } });
  await screen.findByText(/Imported dataset · 4 delays/);
  fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'mcr_als' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(client.status).toHaveBeenCalledTimes(1));
  const firstReadSignal = client.status.mock.calls[0][2];
  first.unmount();
  expect(firstReadSignal.aborted).toBe(true);
  expect(client.cancel).not.toHaveBeenCalled();
  render(<SkanaPanel client={client} sessionId="session-a" />);
  expect(await screen.findByRole('region', { name: 'SK-Ana results' })).toHaveTextContent('0.25000%');
  expect(screen.getByLabelText('Source')).toHaveValue('import');
  expect(screen.getByLabelText('Method')).toHaveValue('mcr_als');
  expect(client.dataset.mock.calls.at(-1)[1]).toBe('import');
  expect(client.start).toHaveBeenCalledTimes(1);
  await act(async () => { finishOldRead({ job: { id: 'job-one', status: 'completed' }, result: result({ lof_percent: 99 }) }); });
  expect(screen.getByRole('region', { name: 'SK-Ana results' })).toHaveTextContent('0.25000%');
});

test('a completed matching job is hydrated from the server without a new calculation', async () => {
  const client = api({ dataset: jest.fn().mockResolvedValue({ dataset: dataset(), latest_job: {
    id: 'job-one', status: 'completed', source: 'od', fingerprint: 'matrix-v1', method: 'svd',
  } }) });
  render(<SkanaPanel client={client} sessionId="session-a" />);
  expect(await screen.findByRole('region', { name: 'SK-Ana results' })).toBeInTheDocument();
  expect(client.status).toHaveBeenCalledWith('session-a', 'job-one', expect.any(AbortSignal));
  expect(client.start).not.toHaveBeenCalled();
  expect(screen.getByText(/Controls configure the next run/)).toBeInTheDocument();
});

test.each([{ source: 'od', fingerprint: 'old-matrix' }, { source: 'import', fingerprint: 'matrix-v1' }])(
  'latest job with a different input identity is not restored: %j', async (identity) => {
    const client = api({ dataset: jest.fn().mockResolvedValue({ dataset: dataset(), latest_job: {
      id: 'job-other', status: 'running', method: 'svd', ...identity,
    } }) });
    await loaded(client);
    expect(client.status).not.toHaveBeenCalled();
    expect(client.start).not.toHaveBeenCalled();
    expect(screen.queryByRole('region', { name: 'SK-Ana results' })).not.toBeInTheDocument();
  });

test('cancellation describes deferred solver interruption and discards the cancelled result', async () => {
  const client = api({ status: jest.fn().mockResolvedValue({ job: { id: 'job-one', status: 'running' } }) });
  const view = await loaded(client);
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Request cancellation' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Request cancellation' }));
  expect(await screen.findByText(/numerical solve may finish before its result is discarded/)).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Request cancellation' })).not.toBeInTheDocument());
  expect(screen.queryByRole('region', { name: 'SK-Ana results' })).not.toBeInTheDocument();
  view.unmount();
});

test('a completed response already in flight cannot reapply a cancelled result', async () => {
  let finishRead;
  const client = api({ status: jest.fn(() => new Promise((resolve) => { finishRead = resolve; })) });
  await loaded(client);
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(client.status).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Request cancellation' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Request cancellation' })).not.toBeInTheDocument());
  await act(async () => { finishRead({ job: { id: 'job-one', status: 'completed' }, result: result() }); });
  expect(screen.queryByRole('region', { name: 'SK-Ana results' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Run analysis' })).toBeEnabled();
});

test('import preprocessing warnings stay visible and are never hidden as ordinary fit statistics', async () => {
  const client = api({ dataset: jest.fn().mockResolvedValue({ dataset: dataset({ source: 'import',
    warnings: ['Imported nonfinite signal cells were replaced with zero.'] }) }) });
  await loaded(client);
  expect(screen.getByRole('alert')).toHaveTextContent('nonfinite signal cells were replaced with zero');
  expect(client.start).not.toHaveBeenCalled();
});

test('rejected fit or import is shown without fabricating a result', async () => {
  const client = api({ start: jest.fn().mockRejectedValue(new Error('Matrix was changed; reload first.')) });
  await loaded(client);
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Matrix was changed; reload first.');
  expect(screen.queryByRole('region', { name: 'SK-Ana results' })).not.toBeInTheDocument();
});

test('rank validation rejects oversized component arrays before any job is created', async () => {
  const { client } = await loaded();
  fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'mcr_als' } });
  fireEvent.click(screen.getByLabelText('Per-component spectral constraints'));
  fireEvent.change(screen.getByLabelText('Components'), { target: { value: '100000000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Choose 1..3 components');
  expect(client.start).not.toHaveBeenCalled();
});
