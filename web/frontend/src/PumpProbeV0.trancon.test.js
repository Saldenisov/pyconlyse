import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    HeatmapSelectorChart: ({ data, layout, wavelengthRange, delayRange, onRangesChange }) => <div>
      <pre data-testid="trancon-heatmap">{JSON.stringify({ trace: data[0], layout, wavelengthRange, delayRange })}</pre>
      <button type="button" onClick={() => onRangesChange(
        [data[0].x[0], data[0].x[data[0].x.length - 1]],
        [data[0].y[1], data[0].y[1]],
      )}>Select row one</button>
    </div>,
    PlotlyChart: ({ className, data }) => className?.includes('pp-plot-spectra')
      ? <pre data-testid="trancon-spectra">{JSON.stringify(data)}</pre> : null,
    SampleStageControl: Empty, DeviceConfigModal: Empty, HardwareModal: Empty,
    StageControl: Empty, SettingsPanel: Empty,
    DataBrowserWindow: ({ open, onLoadFile }) => open ? <div>
      <button onClick={() => onLoadFile('a.dat')}>Load source A</button>
      <button onClick={() => onLoadFile('b.dat')}>Load source B</button>
      <button onClick={() => onLoadFile('c.dat')}>Load source C</button>
    </div> : null,
  };
});

let mockTreatmentProps;
let mockDeletedPreview;
jest.mock('./pump-probe-v0/TreatmentPanel', () => (props) => {
  mockTreatmentProps = props;
  return <div>
    <pre data-testid="trancon-selection">{JSON.stringify(props.selection)}</pre>
    <button onClick={() => props.onPreview(mockDeletedPreview)}>Preview row deletion</button>
  </div>;
});

const LIVE = {
  running: false, control_mode: 'emulator', current_index: 0,
  wavelengths: [400, 500], delays: [-1, 1], heatmap: [[1, 2], [3, 4]],
  live_od: [1, 2], spectra: { signal: [1, 2], reference: [2, 3], background: [0, 0] },
};
const SOURCE_A = {
  path: 'a.dat', file_name: 'a.dat', source_sha256: 'a'.repeat(64),
  wavelengths: [600, 700, 800], delays: [10, 20, 30],
  heatmap: [[10, 11, 12], [20, 21, 22], [30, 31, 32]],
  channels: [{ key: 'BG1', label: 'BG1', values: [[1, 2, 3], [10, 20, 30], [100, 200, 300]] }],
  frame_counts: [1, 2, 3], source_frame_counts: [1, 2, 3], source_row_indices: [0, 1, 2],
  capabilities: ['scale', 'kinetic_clean'], operations: [],
};
const SOURCE_B = { ...SOURCE_A, path: 'b.dat', file_name: 'b.dat', source_sha256: 'b'.repeat(64),
  heatmap: [[110, 111, 112], [120, 121, 122], [130, 131, 132]] };
const SOURCE_C = { ...SOURCE_A, path: 'c.dat', file_name: 'c.dat', source_sha256: 'c'.repeat(64),
  heatmap: [[210, 211, 212], [220, 221, 222], [230, 231, 232]] };

const originalFetch = global.fetch;
let files;
let currentState;
let runReply;
let deriveReply;
let planReply;

function heatmap() { return JSON.parse(screen.getByTestId('trancon-heatmap').textContent); }
function spectra() { return JSON.parse(screen.getByTestId('trancon-spectra').textContent); }
function selection() { return JSON.parse(screen.getByTestId('trancon-selection').textContent); }
function requests(path) { return pumpProbeRequest.mock.calls.filter(([value]) => value === path); }
function body(call) { return JSON.parse(call[1].body); }
function sourceOrder() {
  return within(screen.getByRole('region', { name: 'Derived dataset sources' }))
    .getAllByRole('listitem').map((item) => item.querySelector('[title]').getAttribute('title'));
}
function derived(method, sources) {
  return { ...SOURCE_A, path: `derived:${method}`, file_name: `derived:${method}`,
    source_sha256: 'd'.repeat(64), channels: [], heatmap: [[310, 311, 312], [320, 321, 322], [330, 331, 332]],
    source_spec: { kind: 'derived', method, sources } };
}
function deferred() {
  let resolve;
  const promise = new Promise((finish) => { resolve = finish; });
  return { promise, resolve };
}
async function openFiles() {
  fireEvent.click(screen.getByRole('button', { name: 'Files' }));
  await screen.findByRole('button', { name: 'Load source A' });
}
async function load(letter) {
  fireEvent.click(screen.getByRole('button', { name: `Load source ${letter}` }));
  await waitFor(() => expect(heatmap().trace.z).toEqual(files[`${letter.toLowerCase()}.dat`].heatmap));
}
async function readySources() {
  await openFiles();
  await load('A');
  await load('B');
}

beforeEach(() => {
  localStorage.clear();
  mockTreatmentProps = null;
  mockDeletedPreview = null;
  files = { 'a.dat': SOURCE_A, 'b.dat': SOURCE_B, 'c.dat': SOURCE_C };
  currentState = LIVE;
  runReply = { ...LIVE, running: true, run: { id: 'running-run', output_dir: 'C:\\data\\existing' } };
  planReply = { commissioned: true, fingerprint: 'f'.repeat(64), plan: { profile: { background_level: 10 } } };
  deriveReply = async (method, sources) => derived(method, sources);
  pumpProbeRequest.mockReset();
  pumpProbeRequest.mockImplementation(async (path, options) => {
    if (path === '/data/load') return files[JSON.parse(options.body).path];
    if (path === '/data/derive') {
      const request = JSON.parse(options.body);
      return deriveReply(request.method, request.sources);
    }
    if (path === '/run') { currentState = runReply; return runReply; }
    if (path === '/run/plan') return planReply;
    return currentState;
  });
  global.fetch = jest.fn().mockImplementation(async (_url, options) => ({
    ok: true, status: 200,
    json: async () => options?.method === 'POST'
      ? { path: 'C:\\data\\new-run' }
      : { root: 'C:\\data', path: 'C:\\data', entries: [] },
  }));
});
afterEach(() => { global.fetch = originalFetch; localStorage.clear(); });

test('Tango start binds the exact preview fingerprint before requesting hardware approval', async () => {
  currentState = { ...LIVE, control_mode: 'tango' };
  render(<PumpProbeV0 />);
  await openFiles();
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder' }), { target: { value: 'new-run' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(requests('/run')).toHaveLength(1));
  expect(requests('/run/plan')).toHaveLength(1);
  const preview = requests('/run/plan')[0];
  expect(body(requests('/run')[0])).toEqual({ ...body(preview), plan_fingerprint: planReply.fingerprint });
  expect(pumpProbeRequest.mock.calls.indexOf(preview)).toBeLessThan(pumpProbeRequest.mock.calls.indexOf(requests('/run')[0]));
});

test('uncommissioned Tango profile leaves RAW start unissued and shows calibration requirement', async () => {
  currentState = { ...LIVE, control_mode: 'tango' };
  planReply.commissioned = false;
  render(<PumpProbeV0 />);
  await openFiles();
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder' }), { target: { value: 'new-run' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await screen.findByText('Tango RAW profile requires BG_level verification for the configured Andor readout.');
  expect(requests('/run')).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'Start' })).toBeEnabled();
});

test.each(['average', 'merge'])('source queue order and source fingerprints reach %s derivation unchanged', async (method) => {
  render(<PumpProbeV0 />);
  await readySources();
  expect(sourceOrder()).toEqual(['a.dat', 'b.dat']);
  fireEvent.click(screen.getByRole('button', { name: 'Move source 2 up' }));
  expect(sourceOrder()).toEqual(['b.dat', 'a.dat']);
  fireEvent.change(screen.getByRole('combobox', { name: 'Combine method' }), { target: { value: method } });
  fireEvent.click(screen.getByRole('button', { name: 'Combine' }));
  await waitFor(() => expect(requests('/data/derive')).toHaveLength(1));
  const expected = [SOURCE_B, SOURCE_A].map(({ path, source_sha256 }) => ({ path, source_sha256 }));
  expect(body(requests('/data/derive')[0])).toEqual({ method, sources: expected });
  expect(requests('/data/derive')[0][1]).toEqual(expect.objectContaining({ method: 'POST' }));
  await waitFor(() => expect(heatmap().trace.z).toEqual(derived(method, expected).heatmap));
  expect(sourceOrder()).toEqual(['b.dat', 'a.dat']);
  expect(screen.getByRole('button', { name: 'File OD' })).toHaveAttribute('aria-pressed', 'true');
});

test('a late derived reply cannot replace the next loaded file', async () => {
  const pending = deferred();
  deriveReply = () => pending.promise;
  render(<PumpProbeV0 />);
  await readySources();
  fireEvent.click(screen.getByRole('button', { name: 'Combine' }));
  await waitFor(() => expect(requests('/data/derive')).toHaveLength(1));
  const signal = requests('/data/derive')[0][1].signal;
  await load('C');
  expect(signal.aborted).toBe(true);
  await act(async () => { pending.resolve(derived('average', [])); });
  expect(heatmap().trace.z).toEqual(SOURCE_C.heatmap);
  expect(sourceOrder()).toEqual(['a.dat', 'b.dat', 'c.dat']);
});

test('a late derived reply after acknowledged Start cannot replace live or retained file display', async () => {
  const pending = deferred();
  deriveReply = () => pending.promise;
  render(<PumpProbeV0 />);
  await readySources();
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder' }), { target: { value: 'new-run' } });
  fireEvent.click(screen.getByRole('button', { name: 'Combine' }));
  await waitFor(() => expect(requests('/data/derive')).toHaveLength(1));
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(heatmap().trace.z).toEqual(LIVE.heatmap));
  expect(requests('/data/derive')[0][1].signal.aborted).toBe(true);
  await act(async () => { pending.resolve(derived('average', [])); });
  expect(heatmap().trace.z).toEqual(LIVE.heatmap);
  fireEvent.click(screen.getByRole('button', { name: 'File OD' }));
  expect(heatmap().trace.z).toEqual(SOURCE_B.heatmap);
});

test('Continue reuses saved run output directory without creating any folder', async () => {
  currentState = { ...LIVE, run: { resume_available: true, output_dir: 'C:\\data\\existing-run' } };
  render(<PumpProbeV0 />);
  fireEvent.click(await screen.findByRole('button', { name: 'Continue' }));
  await waitFor(() => expect(requests('/run')).toHaveLength(1));
  expect(body(requests('/run')[0])).toEqual(expect.objectContaining({
    running: true, run_action: 'continue', save_path: 'C:\\data\\existing-run',
  }));
  expect(global.fetch.mock.calls.filter(([url, options]) => String(url).endsWith('/data/folder')
    && options?.method === 'POST')).toHaveLength(0);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Live OD' })).toHaveAttribute('aria-pressed', 'true'));
});

test('run rejection survives a successful state poll and retains file until explicit retry succeeds', async () => {
  const normalRequest = pumpProbeRequest.getMockImplementation();
  let rejectRun = true;
  pumpProbeRequest.mockImplementation(async (path, options) => {
    if (path === '/run' && rejectRun) throw new Error('Point commit rejected');
    return normalRequest(path, options);
  });
  render(<PumpProbeV0 />);
  await openFiles();
  await load('A');
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder' }), { target: { value: 'new-run' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await screen.findByText('Point commit rejected');
  const pollsAfterFailure = requests('/state').length;
  await waitFor(() => expect(requests('/state').length).toBeGreaterThan(pollsAfterFailure));
  expect(screen.getByText('Point commit rejected')).toBeInTheDocument();
  expect(heatmap().trace.z).toEqual(SOURCE_A.heatmap);
  expect(screen.getByRole('button', { name: 'File OD' })).toHaveAttribute('aria-pressed', 'true');
  rejectRun = false;
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => expect(heatmap().trace.z).toEqual(LIVE.heatmap));
  expect(requests('/run')).toHaveLength(2);
  expect(screen.queryByText('Point commit rejected')).not.toBeInTheDocument();
});

test('nonmonotonic duplicate axes keep every heatmap row and select row one by position', async () => {
  files['a.dat'] = { ...SOURCE_A, wavelengths: [600, 500, 600], delays: [0, 5, 0],
    source_row_indices: [7, 8, 12] };
  render(<PumpProbeV0 />);
  await openFiles();
  await load('A');
  const { trace, layout } = heatmap();
  expect(trace.x).toEqual([0, 1, 2]);
  expect(trace.y).toEqual([0, 1, 2]);
  expect(trace.z).toEqual(SOURCE_A.heatmap);
  expect(layout.xaxis.range).toEqual([-0.5, 2.5]);
  expect(layout.yaxis.range).toEqual([-0.5, 2.5]);
  expect(layout.yaxis.tickvals).toEqual([0, 1, 2]);
  expect(layout.yaxis.ticktext.map(String)).toEqual([
    expect.stringContaining('0'), expect.stringContaining('5'), expect.stringContaining('0'),
  ]);
  expect(trace.customdata[1][0]).toEqual([600, 5, 0, 1, 8]);
  expect(trace.customdata[2][2]).toEqual([600, 0, 2, 2, 12]);
  fireEvent.click(screen.getByRole('button', { name: 'Select row one' }));
  fireEvent.click(screen.getByRole('button', { name: 'Corrections' }));
  expect(selection()).toEqual({ wavelength_pixels: [0, 2], delay_pixels: [1, 1] });
});

test('singleton axes use a nonzero positional plot extent without dropping their cell', async () => {
  files['a.dat'] = { ...SOURCE_A, wavelengths: [900], delays: [-7], heatmap: [[4]], channels: [],
    source_row_indices: [13] };
  render(<PumpProbeV0 />);
  await openFiles();
  await load('A');
  const { trace, layout } = heatmap();
  expect(trace.x).toEqual([0]);
  expect(trace.y).toEqual([0]);
  expect(trace.z).toEqual([[4]]);
  expect(layout.xaxis.range).toEqual([-0.5, 0.5]);
  expect(layout.yaxis.range).toEqual([-0.5, 0.5]);
  expect(trace.customdata[0][0]).toEqual([900, -7, 0, 0, 13]);
});

test('delete preview renders its corrected axes and aligned RAW view, retaining original applied source', async () => {
  mockDeletedPreview = { ...SOURCE_A, delays: [10, 30],
    heatmap: [SOURCE_A.heatmap[0], SOURCE_A.heatmap[2]], source_row_indices: [0, 2],
    frame_counts: [1, 3], source_frame_counts: [1, 2, 3],
    channels: [{ ...SOURCE_A.channels[0], values: [SOURCE_A.channels[0].values[0], SOURCE_A.channels[0].values[2]] }],
    operations: [{ kind: 'kinetic_clean', mode: 'delete' }], raw_lineage: { unchanged: true } };
  render(<PumpProbeV0 />);
  await openFiles();
  await load('A');
  fireEvent.click(screen.getByRole('button', { name: 'Corrections' }));
  fireEvent.click(screen.getByRole('button', { name: 'Preview row deletion' }));
  await waitFor(() => expect(heatmap().trace.z).toEqual(mockDeletedPreview.heatmap));
  expect(heatmap().trace.y).toEqual([10, 30]);
  expect(heatmap().trace.customdata[1][0][4]).toBe(2);
  fireEvent.click(screen.getByRole('button', { name: 'Select row one' }));
  expect(spectra()[0]).toEqual(expect.objectContaining({ x: SOURCE_A.wavelengths, y: [100, 200, 300] }));
  expect(mockTreatmentProps.source.source_row_indices).toEqual([0, 1, 2]);
  expect(mockTreatmentProps.applied.frame_counts).toEqual([1, 2, 3]);
});
