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
    PlotPanel: ({ title, actions, children }) => <section><h2>{title}</h2>{actions}{children}</section>,
    PlotlyChart: Empty, HeatmapSelectorChart: Empty, SampleStageControl: Empty,
    DeviceConfigModal: Empty, DataBrowserWindow: Empty, StageControl: Empty, SettingsPanel: Empty,
    HardwareModal: ({ open }) => open ? <div>PDU controls opened</div> : null,
  };
});

const originalFetch = global.fetch;
let state;
beforeEach(() => {
  state = { running: false, real_time: false, control_mode: 'tango',
    wavelengths: [500, 600], delays: [0, 1], heatmap: [[0, 0], [0, 0]], live_od: [0, 0],
    spectra: { signal: [1, 2], reference: [2, 3], background: [0, 0] } };
  pumpProbeRequest.mockReset();
  pumpProbeRequest.mockImplementation(async (path, options) => {
    if (path === '/hardware-config') return { hardware_config: { control_mode: 'tango' } };
    if (path === '/lifecycle') return { job: { operation: 'prepare', status: 'completed', result: { success: true, checks: [] } } };
    if (path === '/realtime') state = { ...state, real_time: JSON.parse(options.body).enabled };
    return state;
  });
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ devices: [] }) });
});
afterEach(() => { global.fetch = originalFetch; });

test('hardware readiness and PDU controls live in Hardware while Start stays in the header', async () => {
  render(<PumpProbeV0 />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start', exact: true })).toBeEnabled());
  expect(screen.queryByRole('button', { name: /Initialize H[WV]/ })).not.toBeInTheDocument();
  expect(screen.queryByText('V0 ready')).not.toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Hardware', exact: true }));
  const hardware = screen.getByRole('tabpanel', { name: 'Hardware', exact: true });
  expect(within(hardware).getByText('V0 ready')).toBeVisible();
  fireEvent.click(within(hardware).getByRole('button', { name: 'PDU / Tango controls' }));
  expect(screen.getByText('PDU controls opened')).toBeVisible();
  expect(pumpProbeRequest.mock.calls.filter(([path]) => /hardware\/initialize|^\/run$/.test(path))).toHaveLength(0);
});

test('Alignment Current follows iTest and uses one enlarged monitor with the same realtime control', async () => {
  render(<PumpProbeV0 />);
  const compact = screen.getByRole('region', { name: 'Current spectra and OD' });
  expect(compact).toHaveClass('pp-current-monitor-compact');
  expect(within(compact).getByRole('button', { name: 'Real time off' })).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Alignment', exact: true }));
  const tabs = within(screen.getByRole('tablist', { name: 'V0 alignment controls' })).getAllByRole('tab');
  expect(tabs[0]).toHaveTextContent('iTest');
  expect(tabs[1]).toHaveTextContent('Current');
  fireEvent.click(tabs[1]);
  const expanded = screen.getByRole('region', { name: 'Current spectra and OD' });
  expect(expanded).toHaveClass('pp-current-monitor-expanded');
  fireEvent.click(within(expanded).getByRole('button', { name: 'Real time off' }));
  await waitFor(() => expect(within(expanded).getByRole('button', { name: 'Real time on' })).toHaveAttribute('aria-pressed', 'true'));
  expect(pumpProbeRequest.mock.calls.filter(([path]) => path === '/realtime')).toHaveLength(1);
  fireEvent.click(screen.getByRole('tab', { name: 'Acquisition', exact: true }));
  const monitor = screen.getByRole('region', { name: 'Current spectra and OD' });
  expect(monitor).toHaveClass('pp-current-monitor-compact');
  expect(within(monitor).getByRole('button', { name: 'Real time on' })).toBeVisible();
  expect(pumpProbeRequest.mock.calls.filter(([path]) => /hardware\/initialize|^\/run$/.test(path))).toHaveLength(0);
});
