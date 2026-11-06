import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import PumpProbeV0 from './PumpProbeV0';
import { pumpProbeRequest } from './pump-probe-v0/shared';

jest.mock('./pump-probe-v0/shared', () => ({
  ...jest.requireActual('./pump-probe-v0/shared'),
  pumpProbeRequest: jest.fn(),
}));
jest.mock('./pump-probe-v0/components', () => {
  const React = require('react');
  const Empty = () => null;
  return {
    PlotPanel: ({ title, actions, children }) => <section><h2>{title}</h2>{actions}{children}</section>,
    HeatmapSelectorChart: ({ data }) => <pre data-testid="heatmap">{JSON.stringify({ x: data[0].x, y: data[0].y, z: data[0].z })}</pre>,
    PlotlyChart: Empty, SampleStageControl: Empty, DeviceConfigModal: Empty,
    HardwareModal: Empty, StageControl: Empty,
    SettingsPanel: ({ onSettingChange }) => <div>
      <button onClick={() => onSettingChange('pointCount', 7)}>Set seven points</button>
      <button onClick={() => onSettingChange('pointCount', 9)}>Set nine points</button>
    </div>,
    DataBrowserWindow: ({ open, onLoadFile }) => open
      ? <button onClick={() => onLoadFile('sample.dat')}>Load fixture</button> : null,
  };
});
let mockLatePreview;
jest.mock('./pump-probe-v0/TreatmentPanel', () => ({ source, onPreview }) => {
  mockLatePreview = onPreview;
  return (
  <button onClick={() => onPreview({ ...source, heatmap: source.heatmap.map((row) => row.map((x) => x * 2)) })}>
    Preview fixture
  </button>
  );
});

const live = {
  running: false, control_mode: 'emulator', current_index: 0,
  wavelengths: [400, 500], delays: [-1, 1], heatmap: [[1, 2], [3, 4]],
  live_od: [1, 2], spectra: { signal: [1, 2], reference: [2, 3], background: [0, 0] },
};
const file = {
  path: 'sample.dat', file_name: 'sample.dat', source_sha256: 'file-source',
  wavelengths: [600, 700, 800], delays: [10, 20, 30],
  heatmap: [[10, 11, 12], [20, 21, 22], [30, 31, 32]],
};
const filePlot = { x: file.wavelengths, y: file.delays, z: file.heatmap };
const livePlot = { x: live.wavelengths, y: live.delays, z: live.heatmap };
const originalFetch = global.fetch;
let runReply;
let runFailure;
let serverState;
function acceptRun() { serverState = runReply; return runReply; }

function plot() { return JSON.parse(screen.getByTestId('heatmap').textContent); }
async function loadFile() {
  fireEvent.click(screen.getByRole('button', { name: 'Files' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Load fixture' }));
  await waitFor(() => expect(plot()).toEqual(filePlot));
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder' }), { target: { value: 'run1' } });
}
async function previewFile() {
  fireEvent.click(screen.getByRole('button', { name: 'Corrections' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Preview fixture' }));
  const preview = { ...filePlot, z: file.heatmap.map((row) => row.map((x) => x * 2)) };
  await waitFor(() => expect(plot()).toEqual(preview));
  return preview;
}

beforeEach(() => {
  runReply = { ...live, running: true, run: { id: 'new-run', status: 'running' } };
  runFailure = null;
  serverState = live;
  pumpProbeRequest.mockReset();
  pumpProbeRequest.mockImplementation(async (path) => {
    if (path === '/data/load') return file;
    if (path === '/run') {
      if (runFailure) throw runFailure;
      return acceptRun();
    }
    return serverState;
  });
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ root: 'C:\\data', path: 'C:\\data', entries: [] }),
  });
});
afterEach(() => { global.fetch = originalFetch; });

test('explicit file/live switches keep unequal axes and heatmaps with their owner', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  expect(screen.getByRole('button', { name: 'File OD' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'Live OD' }));
  expect(plot()).toEqual(livePlot);
  expect(screen.getByRole('button', { name: 'Corrections' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'File OD' }));
  expect(plot()).toEqual(filePlot);
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(0);
});

test('successful start selects live after acknowledgement and retains file preview for later', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  const preview = await previewFile();
  let acknowledge;
  pumpProbeRequest.mockImplementation(async (path) => {
    if (path === '/run') return new Promise((resolve) => { acknowledge = (state) => { serverState = state; resolve(state); }; });
    return serverState;
  });
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(acknowledge).toEqual(expect.any(Function)));
  expect(plot()).toEqual(preview);
  acknowledge(runReply);
  await waitFor(() => expect(plot()).toEqual(livePlot));
  expect(screen.getByRole('button', { name: 'Live OD' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'File OD' }));
  expect(plot()).toEqual(preview);
});

test('failed start retains file axes and preview', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  const preview = await previewFile();
  runFailure = new Error('Start rejected');
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await screen.findByText('Start rejected');
  expect(plot()).toEqual(preview);
  expect(screen.getByRole('button', { name: 'File OD' })).toHaveAttribute('aria-pressed', 'true');
});

test('a response without a running acknowledgement retains file display', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  runReply = { ...live, running: false };
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(pumpProbeRequest).toHaveBeenCalledWith('/run', expect.any(Object)));
  expect(plot()).toEqual(filePlot);
  expect(screen.getByRole('button', { name: 'File OD' })).toHaveAttribute('aria-pressed', 'true');
});


test('a late file load cannot replace the live display or retained file after start', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  let finishLoad;
  pumpProbeRequest.mockImplementation(async (path) => {
    if (path === '/data/load') return new Promise((resolve) => { finishLoad = resolve; });
    if (path === '/run') return acceptRun();
    return serverState;
  });
  fireEvent.click(screen.getByRole('button', { name: 'Load fixture' }));
  await waitFor(() => expect(finishLoad).toEqual(expect.any(Function)));
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(plot()).toEqual(livePlot));
  await act(async () => {
    finishLoad({ ...file, file_name: 'late.dat', heatmap: file.heatmap.map((row) => row.map(() => 999)) });
  });
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeInTheDocument());
  expect(plot()).toEqual(livePlot);
  fireEvent.click(screen.getByRole('button', { name: 'File OD' }));
  expect(plot()).toEqual(filePlot);
});

test('a treatment callback captured before start cannot replace retained preview afterward', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  const preview = await previewFile();
  const finishPreview = mockLatePreview;
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(plot()).toEqual(livePlot));
  await act(async () => {
    finishPreview({ ...file, heatmap: file.heatmap.map((row) => row.map(() => 999)) });
  });
  expect(plot()).toEqual(livePlot);
  fireEvent.click(screen.getByRole('button', { name: 'File OD' }));
  expect(plot()).toEqual(preview);
});


test('loading a RAW-only file leaves OD explicitly owned by live', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  pumpProbeRequest.mockImplementation(async (path) => path === '/data/load'
    ? { ...file, heatmap: undefined, channels: [{ key: 'raw', values: file.heatmap }] }
    : serverState);
  fireEvent.click(screen.getByRole('button', { name: 'Load fixture' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Live OD' })).toHaveAttribute('aria-pressed', 'true'));
  expect(screen.getByRole('button', { name: 'File OD' })).toBeDisabled();
  expect(plot()).toEqual(livePlot);
});


test('Start waits for the latest ACK across serialized in-flight config edits', async () => {
  const configurations = [];
  pumpProbeRequest.mockImplementation(async (path, options) => {
    if (path === '/data/load') return file;
    if (path === '/config') return new Promise((resolve) => {
      configurations.push({ payload: JSON.parse(options.body), resolve });
    });
    if (path === '/run') return acceptRun();
    return serverState;
  });
  render(<PumpProbeV0 />);
  await loadFile();
  fireEvent.click(screen.getByRole('button', { name: 'Set seven points' }));
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await act(async () => {});
  expect(configurations).toHaveLength(1);
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(0);
  await act(async () => { configurations[0].resolve(live); });
  await waitFor(() => expect(configurations).toHaveLength(2));
  expect(configurations[1].payload.point_count).toBe(7);
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Set nine points' }));
  await act(async () => { configurations[1].resolve(live); });
  await waitFor(() => expect(configurations).toHaveLength(3));
  expect(configurations[2].payload.point_count).toBe(9);
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(0);
  expect(plot()).toEqual(filePlot);
  await act(async () => { configurations[2].resolve(live); });
  await waitFor(() => expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(1));
  expect(plot()).toEqual(livePlot);
});

test('configuration failure prevents Start and retains file preview; retry can recover', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  const preview = await previewFile();
  let rejectConfiguration = true;
  pumpProbeRequest.mockImplementation(async (path) => {
    if (path === '/config' && rejectConfiguration) throw new Error('Configuration rejected');
    if (path === '/run') return acceptRun();
    return serverState;
  });
  fireEvent.click(screen.getByRole('button', { name: 'Set seven points' }));
  await screen.findByText('Configuration rejected');
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await act(async () => {});
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(0);
  expect(plot()).toEqual(preview);
  expect(screen.getByRole('button', { name: 'File OD' })).toHaveAttribute('aria-pressed', 'true');
  rejectConfiguration = false;
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(plot()).toEqual(livePlot));
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(1);
});

test('Start rechecks settings edited while folder creation is in flight', async () => {
  render(<PumpProbeV0 />);
  await loadFile();
  let finishFolder;
  global.fetch.mockImplementation(async (_url, options) => options?.method === 'POST'
    ? new Promise((resolve) => { finishFolder = resolve; })
    : { ok: true, json: async () => ({ root: 'C:\\data', path: 'C:\\data', entries: [] }) });
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(finishFolder).toEqual(expect.any(Function)));
  let finishConfiguration;
  pumpProbeRequest.mockImplementation(async (path) => {
    if (path === '/config') return new Promise((resolve) => { finishConfiguration = resolve; });
    if (path === '/run') return acceptRun();
    return serverState;
  });
  fireEvent.click(screen.getByRole('button', { name: 'Set nine points' }));
  await waitFor(() => expect(finishConfiguration).toEqual(expect.any(Function)));
  await act(async () => { finishFolder({ ok: true, json: async () => ({ path: 'C:\\data\\run1' }) }); });
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(0);
  await act(async () => { finishConfiguration(live); });
  await waitFor(() => expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/run')).toHaveLength(1));
});


test('pre-ACK state replies cannot undo a mutation; later state polls can report completion', async () => {
  jest.useFakeTimers();
  let finishOldState;
  let holdNextState = false;
  pumpProbeRequest.mockImplementation(async (path) => {
    if (path === '/data/load') return file;
    if (path === '/run') return acceptRun();
    if (path === '/state' && holdNextState) {
      holdNextState = false;
      return new Promise((resolve) => { finishOldState = resolve; });
    }
    return serverState;
  });
  try {
    await act(async () => { render(<PumpProbeV0 />); });
    await loadFile();
    holdNextState = true;
    await act(async () => { jest.advanceTimersByTime(250); });
    expect(finishOldState).toEqual(expect.any(Function));
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await act(async () => {});
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
    await act(async () => { finishOldState(live); });
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
    expect(plot()).toEqual(livePlot);
    serverState = { ...live, run: { status: 'completed' } };
    await act(async () => { jest.advanceTimersByTime(250); });
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
    expect(plot()).toEqual(livePlot);
  } finally { jest.useRealTimers(); }
});
