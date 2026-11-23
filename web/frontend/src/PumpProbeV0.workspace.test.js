import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import PumpProbeV0 from './PumpProbeV0';
import { pumpProbeRequest } from './pump-probe-v0/shared';

jest.mock('./pump-probe-v0/shared', () => ({
  ...jest.requireActual('./pump-probe-v0/shared'), pumpProbeRequest: jest.fn(),
}));
jest.mock('./components/ITestPSUClient', () => () => <div>iTest controls</div>);
jest.mock('./components/LaserPointingController', () => () => <div>Laser controls</div>);
jest.mock('./pump-probe-v0/components', () => {
  const Empty = () => null;
  return {
    PlotPanel: ({ title, actions, headerDetails, children }) => <section><h2>{title}</h2>{actions}{headerDetails}{children}</section>,
    PlotlyChart: Empty, HeatmapSelectorChart: Empty, SampleStageControl: Empty,
    DeviceConfigModal: Empty, DataBrowserWindow: Empty,
    SettingsPanel: ({ runControls }) => <section aria-label="Scan settings">{runControls}</section>,
    StageControl: ({ orientation }) => <section aria-label="Delay line" className={`pp-stage-panel-${orientation}`}>Graphical delay line</section>,
    HardwareModal: ({ open }) => open ? <div>PDU controls opened</div> : null,
  };
});

const originalFetch = global.fetch;
let state;
beforeEach(() => {
  state = { running: false, real_time: false, control_mode: 'tango', position_mm: 0, set_position_mm: 0,
    wavelengths: [500, 600], delays: [0, 1], heatmap: [[0, 0], [0, 0]], live_od: [0, 0],
    spectra: { signal: [1, 2], reference: [2, 3], background: [0, 0] } };
  pumpProbeRequest.mockReset();
  pumpProbeRequest.mockImplementation(async (path, options) => {
    if (path === '/hardware-config') return { hardware_config: { control_mode: 'tango' } };
    if (path === '/lifecycle') return { job: { operation: 'prepare', status: 'completed', result: { success: true, checks: [] } } };
    if (path === '/realtime') state = { ...state, real_time: JSON.parse(options.body).enabled };
    if (path === '/stage/move') state = { ...state, set_position_mm: JSON.parse(options.body).position_mm, stage_moving: true };
    return state;
  });
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ devices: [] }) });
});
afterEach(() => { global.fetch = originalFetch; });

test.each([false, true])('Dark test %s binds a fresh snapshot and preserves ordinary commissioning guard', async (dark) => {
  const previous = pumpProbeRequest.getMockImplementation();
  pumpProbeRequest.mockImplementation(async (path, options) => {
    if (path === '/commissioning/andor-snapshot') return { diagnostic_snapshot_id: 'fresh-camera-token' };
    if (path === '/run/plan') return { fingerprint: 'bound-plan', commissioned: false, diagnostic_dark: dark };
    if (path === '/run') return { ...state, running: true };
    return previous(path, options);
  });
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ root: 'test', path: 'test/folder', entries: [], devices: [] }) });
  render(<PumpProbeV0 />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start', exact: true })).toBeEnabled());
  fireEvent.click(screen.getByRole('tab', { name: 'Files', exact: true }));
  await waitFor(() => expect(global.fetch.mock.calls.some(([url]) => url.includes('/data/list'))).toBe(true));
  fireEvent.click(screen.getByRole('tab', { name: 'Acquisition', exact: true }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder', exact: true }), { target: { value: 'dark-checkout' } });
  if (dark) fireEvent.click(screen.getByRole('checkbox', { name: 'Dark test' }));
  fireEvent.click(screen.getByRole('button', { name: 'Start', exact: true }));
  await waitFor(() => expect(pumpProbeRequest.mock.calls.some(([path]) => path === '/run/plan')).toBe(true));
  if (dark) {
    await waitFor(() => expect(pumpProbeRequest.mock.calls.some(([path]) => path === '/run')).toBe(true));
    const snapshot = pumpProbeRequest.mock.calls.find(([path]) => path === '/commissioning/andor-snapshot');
    expect(JSON.parse(snapshot[1].body)).toEqual({ diagnostic_dark: true });
    const request = pumpProbeRequest.mock.calls.find(([path]) => path === '/run');
    expect(JSON.parse(request[1].body)).toMatchObject({ diagnostic_dark: true, diagnostic_snapshot_id: 'fresh-camera-token', plan_fingerprint: 'bound-plan' });
  } else {
    await waitFor(() => expect(screen.getByText(/Tango RAW profile requires BG_level/)).toBeVisible());
    expect(pumpProbeRequest.mock.calls.some(([path]) => path === '/run' || path === '/commissioning/andor-snapshot')).toBe(false);
  }
});

test('hardware readiness and PDU controls live in Hardware while run controls live in Scan settings', async () => {
  render(<PumpProbeV0 />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start', exact: true })).toBeEnabled());
  const scan = screen.getByRole('region', { name: 'Scan settings' });
  expect(within(scan).getByRole('button', { name: 'Start', exact: true })).toBeVisible();
  expect(within(scan).getByRole('button', { name: 'Faraday closed' })).toBeVisible();
  expect(within(scan).getByRole('button', { name: 'Move Crystal' })).toBeVisible();
  expect(within(screen.getByRole('banner')).queryByRole('button', { name: 'Start', exact: true })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Initialize H[WV]/ })).not.toBeInTheDocument();
  expect(screen.queryByText('V0 ready')).not.toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'V0 Pump-Probe hardware status: Ready' }));
  const hardware = screen.getByRole('tabpanel', { name: 'Hardware', exact: true });
  expect(within(hardware).getByText('V0 ready')).toBeVisible();
  expect(within(hardware).getByText('V0 ready').closest('details')).toHaveAttribute('open');
  fireEvent.click(within(hardware).getByRole('button', { name: 'PDU / Tango controls' }));
  expect(screen.getByText('PDU controls opened')).toBeVisible();
  expect(pumpProbeRequest.mock.calls.filter(([path]) => /hardware\/initialize|^\/run$/.test(path))).toHaveLength(0);
});

test('Alignment shows iTest beside one enlarged monitor without acquisition status and shares realtime state', async () => {
  render(<PumpProbeV0 />);
  const compact = screen.getByRole('region', { name: 'Current spectra and OD' });
  expect(compact).toHaveClass('pp-current-monitor-compact');
  expect(within(compact).getByRole('button', { name: 'Real time off' })).toBeVisible();
  expect(screen.queryByRole('region', { name: 'Delay line', exact: true })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Alignment', exact: true }));
  expect(screen.getByRole('heading', { name: 'iTest · V0' })).toBeVisible();
  expect(screen.queryByRole('region', { name: 'OWIS delay line', exact: true })).not.toBeInTheDocument();
  expect(screen.queryByText('control')).not.toBeInTheDocument();
  expect(screen.queryByRole('tab', { name: 'Current', exact: true })).not.toBeInTheDocument();
  const expanded = screen.getByRole('region', { name: 'Current spectra and OD' });
  expect(expanded).toHaveClass('pp-current-monitor-expanded');
  expect(screen.getByRole('region', { name: 'Delay line', exact: true })).toHaveClass('pp-stage-panel-horizontal');
  fireEvent.click(within(expanded).getByRole('button', { name: 'Real time off' }));
  await waitFor(() => expect(within(expanded).getByRole('button', { name: 'Real time on' })).toHaveAttribute('aria-pressed', 'true'));
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/realtime')).toHaveLength(1);
  fireEvent.click(screen.getByRole('tab', { name: 'Acquisition', exact: true }));
  const monitor = screen.getByRole('region', { name: 'Current spectra and OD' });
  expect(monitor).toHaveClass('pp-current-monitor-compact');
  expect(within(monitor).getByRole('button', { name: 'Real time on' })).toBeVisible();
  expect(pumpProbeRequest.mock.calls.filter(([path]) => /hardware\/initialize|^\/run$/.test(path))).toHaveLength(0);
});


test('relocated Faraday and crystal controls retain their existing requests', async () => {
  render(<PumpProbeV0 />);
  const scan = screen.getByRole('region', { name: 'Scan settings' });
  await waitFor(() => expect(within(scan).getByRole('button', { name: 'Start', exact: true })).toBeEnabled());
  fireEvent.click(within(scan).getByRole('button', { name: 'Faraday closed' }));
  await waitFor(() => expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/faraday')).toHaveLength(1));
  const [, options] = pumpProbeRequest.mock.calls.find(([path]) => path === '/faraday');
  expect(JSON.parse(options.body)).toEqual({ closed: false });
  fireEvent.click(within(scan).getByRole('button', { name: 'Move Crystal' }));
  await waitFor(() => expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/crystal/move')).toHaveLength(1));
});
