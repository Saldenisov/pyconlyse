import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ExperimentPreparation, { prepareV0, prepareVD2, shutdownVD2 } from './ExperimentPreparation';

const response = (payload, ok = true) => ({ ok, json: async () => payload });
const snapshot = job => response({ success: true, job });
const idleJob = () => snapshot({ status: 'idle', steps: [] });
const completedJob = (result, operation = 'prepare') => snapshot({ status: 'completed', operation, result });
const show = (experiment = 'VD2', suffix = '') => render(<MemoryRouter initialEntries={[
  `/experiment-preparation?experiment=${experiment}${suffix}`,
]}><ExperimentPreparation /></MemoryRouter>);
const originalFetch = global.fetch;
beforeEach(() => { global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });

  test('V0 starts its fixed-scope power preparation and retains failed checks', async () => {
    global.fetch
      .mockResolvedValueOnce(response({
        success: false,
        checks: [{ label: 'DAQmx card', ok: false, detail: 'DOWN' }],
      }));
    const updateStep = jest.fn();

    await expect(prepareV0(updateStep)).rejects.toMatchObject({ checks: [{ label: 'DAQmx card', ok: false, detail: 'DOWN' }] });

    expect(global.fetch).toHaveBeenNthCalledWith(1, '/api/pump-probe-v0/hardware/initialize', expect.objectContaining({ method: 'POST', credentials: 'include' }));
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(updateStep).toHaveBeenCalledWith(0, 'running', expect.stringContaining('STANDA and DG645 timing remain read-only'));
  });

  test('V0 requests one server-owned preparation, not individual device commands', async () => {
    const healthy = {
      success: true,
      checks: [{ label: 'DG645', ok: true, detail: 'ON' }],
    };
    global.fetch
      .mockResolvedValueOnce(response(healthy))
      .mockResolvedValueOnce(response(healthy));

    await prepareV0(jest.fn());

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch.mock.calls.every(([url]) => url.endsWith('/hardware/initialize'))).toBe(true);
  });

  test('VD2 initializes equipment and verifies RemoteEx and HPD-TA', async () => {
    global.fetch
      .mockResolvedValueOnce(response({ success: true, state: 'ON' }))
      .mockResolvedValueOnce(response({
        success: true,
        steps: [{ step: 'VD2 power', status: 'enabled' }],
      }))
      .mockResolvedValueOnce(response({
        success: true,
        remoteex_running: true,
        hpdta_running: true,
      }));
    const updateStep = jest.fn();

    const result = await prepareVD2(updateStep);

    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      '/api/pump-probe-vd2/initialize',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result.checks).toEqual([{ step: 'VD2 power', status: 'enabled' }]);
    expect(updateStep).toHaveBeenCalledWith(2, 'complete', 'RemoteEx is connected and HPD-TA is running.');
  });

  test('VD2 reports an already-ready rig without another runtime/startup request', async () => {
    const message = 'VD2 is already running; all checks passed. No restart or settings change was needed.';
    global.fetch
      .mockResolvedValueOnce(response({ success: true, state: 'ON' }))
      .mockResolvedValueOnce(response({
        success: true, already_ready: true, message,
        steps: [{ step: 'RemoteEx / HPD-TA', status: 'already running; verified idle' }],
      }));
    const updateStep = jest.fn();
    const result = await prepareVD2(updateStep);

    expect(result.alreadyReady).toBe(true);
    expect(result.message).toBe(message);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(updateStep).toHaveBeenCalledWith(1, 'complete', 'No restart, power change or settings reset was necessary.');
    expect(updateStep).toHaveBeenCalledWith(2, 'complete', message);
  });

  test('unverified shared OWIS is shown as a warning, not complete readiness', async () => {
    global.fetch.mockResolvedValueOnce(response({
      success: true, warnings: ['OWIS axis 2 unverified; shared power unchanged'],
      steps: [], message: 'Optical supplies OFF; OWIS axis 2 unverified.',
    }));
    const updateStep = jest.fn();
    const result = await shutdownVD2(updateStep);
    expect(result.warnings).toHaveLength(1);
    expect(updateStep).toHaveBeenCalledWith(1, 'warning', 'OWIS axis 2 unverified; shared power unchanged');
    expect(updateStep).toHaveBeenCalledWith(2, 'complete',
      'Flashlamp / camera / trigger supplies verified OFF. Xe lamp cooling power, Zaber power, control supply and unrelated outputs unchanged.');
  });

  test('V0 preparation failure retains component diagnostics', async () => {
    const failed = [{ label: 'DG645 power', ok: false, detail: 'PDU output 2 remains OFF' }];
    global.fetch
      .mockResolvedValueOnce(response({
        success: false, checks: failed, recommendation: 'Correct DG645 power, then press Prepare again',
      }));
    await expect(prepareV0(jest.fn())).rejects.toMatchObject({
      message: 'Correct DG645 power, then press Prepare again', checks: failed,
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

test('compact preparation page shows one action line and no operation log or checklist', async () => {
  global.fetch.mockResolvedValue(idleJob());
  show();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ready. Select Prepare or Unprepare.'));
  expect(screen.queryByText(/Operation log|startup checklist|automatic requirements/i)).not.toBeInTheDocument();
  expect(screen.queryByRole('list')).not.toBeInTheDocument();
  expect(screen.queryByText(/ready for acquisition/i)).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('one Unprepare VD2 click submits once and restores the verified result', async () => {
  let accept;
  global.fetch.mockResolvedValueOnce(idleJob()).mockImplementationOnce(() => new Promise(resolve => { accept = resolve; }));
  show();
  const button = screen.getByRole('button', { name: 'Unprepare VD2' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  fireEvent.click(button);
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Starting safe shutdown');
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(global.fetch).toHaveBeenLastCalledWith('/api/pump-probe-vd2/deinitialize?background=1', expect.objectContaining({ method: 'POST' }));
  await act(async () => { accept(completedJob({ message: 'VD2 supplies verified OFF; Xe cooling retained.' }, 'shutdown')); });
  expect(screen.getByRole('status')).toHaveTextContent('VD2 supplies verified OFF');
  expect(screen.getByRole('button', { name: 'Prepare VD2' })).toBeEnabled();
});

test('active job reload follows its phase without sending a new hardware request', async () => {
  const job = { job_id: 'same', status: 'running', operation: 'shutdown', phase: 'Waiting for Focus confirmation', steps: [] };
  global.fetch.mockResolvedValue(snapshot(job));
  const view = show();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Waiting for Focus confirmation'));
  expect(screen.getByRole('button', { name: 'Unpreparing VD2...' })).toBeDisabled();
  view.unmount();
  show('VD2', '&autostart=1');
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Waiting for Focus confirmation'));
  expect(global.fetch.mock.calls.every(([url, options]) => url.endsWith('/lifecycle') && !options.method)).toBe(true);
});

test('running status follows server phases and then the completed result', async () => {
  jest.useFakeTimers();
  const running = phase => snapshot({ status: 'running', operation: 'shutdown', phase });
  global.fetch.mockResolvedValueOnce(running('Closing shutters'))
    .mockResolvedValueOnce(running('Waiting for Focus confirmation'))
    .mockResolvedValueOnce(completedJob({ message: 'VD2 unprepared' }, 'shutdown'));
  show();
  await act(async () => { await Promise.resolve(); });
  expect(screen.getByRole('status')).toHaveTextContent('Closing shutters');
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('status')).toHaveTextContent('Waiting for Focus confirmation');
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('status')).toHaveTextContent('VD2 unprepared');
  expect(global.fetch).toHaveBeenCalledTimes(3);
});

test('poll failures keep controls locked and reconnect without another POST', async () => {
  jest.useFakeTimers();
  global.fetch.mockResolvedValueOnce(snapshot({ status: 'running', operation: 'shutdown', phase: 'Stopping acquisition' }))
    .mockRejectedValueOnce(new Error('Network unavailable'))
    .mockResolvedValueOnce(completedJob({ message: 'Stopped' }, 'shutdown'));
  show();
  await act(async () => { await Promise.resolve(); });
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('alert')).toHaveTextContent('Reconnecting without restarting hardware');
  expect(screen.getByRole('button', { name: 'Unpreparing VD2...' })).toBeDisabled();
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('status')).toHaveTextContent('Stopped');
  expect(global.fetch.mock.calls.every(([, options]) => !options.method)).toBe(true);
});

test.each(['failed', 'interrupted'])('%s snapshot is an error, never autostarted or shown as ready', async status => {
  global.fetch.mockResolvedValue(snapshot({ status, operation: 'shutdown', error: 'Cannot confirm Focus; power retained' }));
  show('VD2', '&autostart=1');
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot confirm Focus; power retained');
  expect(screen.getByRole('button', { name: 'Unprepare VD2' })).toBeEnabled();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('saved completed result is historical and never restarts equipment on reload', async () => {
  global.fetch.mockResolvedValue(completedJob({ message: 'VD2 unprepared' }, 'shutdown'));
  show('VD2', '&autostart=1');
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Last operation · VD2 unprepared'));
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test.each([new Error('Network error'), null])('unavailable or invalid lifecycle locks both buttons', async failure => {
  if (failure) global.fetch.mockRejectedValue(failure);
  else global.fetch.mockResolvedValue(response({ success: true }));
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Controls remain locked');
  expect(screen.getByRole('button', { name: 'Prepare VD2' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Unprepare VD2' })).toBeDisabled();
});

test('server warning remains visible on the single status line', async () => {
  global.fetch.mockResolvedValue(completedJob({ message: 'Optics OFF', warnings: ['OWIS axis 2 unverified; power retained'] }, 'shutdown'));
  show();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('OWIS axis 2 unverified; power retained'));
  expect(screen.getByRole('status')).toHaveClass('is-warning');
});

test('countdown shares the action line and uses server clock', async () => {
  jest.useFakeTimers();
  global.fetch.mockResolvedValue(snapshot({ status: 'running', operation: 'prepare', phase: 'Waiting for camera power', server_time: 1000, wait_until: 1030 }));
  show();
  await act(async () => { await Promise.resolve(); });
  expect(screen.getByRole('status')).toHaveTextContent('Waiting for camera power');
  expect(screen.getByRole('timer')).toHaveTextContent('30 s remaining');
  await act(async () => { jest.advanceTimersByTime(500); });
  expect(screen.getByRole('timer')).toHaveTextContent('30 s remaining');
});

test('accepted job replaces previous result while start request is in flight', async () => {
  jest.useFakeTimers();
  let accept;
  global.fetch.mockResolvedValueOnce(completedJob({ message: 'Previous result' }))
    .mockImplementationOnce(() => new Promise(resolve => { accept = resolve; }));
  show();
  await act(async () => { await Promise.resolve(); });
  fireEvent.click(screen.getByRole('button', { name: 'Prepare VD2' }));
  await act(async () => { jest.advanceTimersByTime(1500); });
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(screen.queryByText(/Previous result/)).not.toBeInTheDocument();
  await act(async () => { accept(completedJob({ message: 'New result' })); });
  expect(screen.getByRole('status')).toHaveTextContent('New result');
});

test('failed request exposes reason and a later operator click rechecks', async () => {
  global.fetch.mockResolvedValueOnce(idleJob())
    .mockResolvedValueOnce(response({ success: false, error: 'Camera shutter unverified; power retained' }, false))
    .mockResolvedValueOnce(completedJob({ message: 'Stopped' }, 'shutdown'));
  show();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Unprepare VD2' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Unprepare VD2' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Camera shutter unverified');
  fireEvent.click(screen.getByRole('button', { name: 'Unprepare VD2' }));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Stopped'));
});

test('V0 retains shutdown confirmation and its existing power scope', async () => {
  global.fetch.mockResolvedValueOnce(idleJob()).mockResolvedValueOnce(completedJob({ message: 'V0 stopped' }, 'shutdown'));
  show('V0');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Unprepare V0' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Unprepare V0' }));
  expect(screen.getByRole('alertdialog')).toHaveTextContent('Andor power is retained until CCD warm-up and SDK release are verified');
  expect(global.fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'OK', exact: true }));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('V0 stopped'));
  expect(global.fetch).toHaveBeenLastCalledWith('/api/pump-probe-v0/deinitialize?background=1', expect.objectContaining({ method: 'POST' }));
});

test('switching experiment uses the correct lifecycle and clears previous result', async () => {
  global.fetch.mockResolvedValueOnce(completedJob({ message: 'VD2 stopped' }, 'shutdown')).mockResolvedValueOnce(idleJob());
  show();
  await screen.findByText(/VD2 stopped/);
  fireEvent.change(screen.getByRole('combobox', { name: 'Experiment' }), { target: { value: 'V0' } });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Prepare V0' })).toBeEnabled());
  expect(screen.queryByText(/VD2 stopped/)).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenLastCalledWith('/api/pump-probe-v0/lifecycle', expect.objectContaining({ credentials: 'include' }));
});
