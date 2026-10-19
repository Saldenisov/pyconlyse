import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { AcquisitionWatchdog, MachineFrequency, acquisitionLinkState, frequencyReadback } from './SupervisionHeader';
import Elyse from './Elyse';

function fixture() {
  const record = { data: Array(33).fill(0), age_seconds: 0.1, stale: false,
    error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name: 'C10-11 NI6602',
      fields: Array(33).fill({ type: 'DBL' }) } };
  record.data[3] = 181000;
  return { payload: { schema_version: 1, execution_allowed: false, quality: 'FRESH', server_state: 'ON',
    stale_after_seconds: 2, expected_banks: ['C1011NI6602'], error_banks: [],
    snapshot: { receiver_session: 'receiver-one', received_this_process: 27,
      publications: { C1011NI6602: record } } }, failure: '', elapsed: 0 };
}

test('watchdog indicates packet reception, never a receiver ON flag alone or equipment readiness', () => {
  const t = fixture();
  const view = render(<AcquisitionWatchdog telemetry={t} />);
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveClass('elyse-watchdog--connected');
  expect(acquisitionLinkState({ ...t, elapsed: 1.9 })).toBe('STALE');
  expect(acquisitionLinkState({ ...t, failure: 'offline' })).toBe('UNAVAILABLE');
  t.payload.snapshot.publications.C1011NI6602.error.code = 5;
  expect(acquisitionLinkState(t)).toBe('CONNECTED'); // transport, not instrument status
  t.payload.snapshot.publications.C1011NI6602.stale = true;
  view.rerender(<AcquisitionWatchdog telemetry={t} />);
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveClass('elyse-watchdog--stale');
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent('déconnecté');
  t.payload.snapshot.publications = {};
  expect(acquisitionLinkState(t)).toBe('WAITING');
  t.payload.server_state = 'FAULT';
  expect(acquisitionLinkState(t)).toBe('UNAVAILABLE');
});

test.each([NaN, Infinity, -1, undefined])('rejects invalid packet age %s', (age) => {
  const t = fixture(); t.payload.snapshot.publications.C1011NI6602.age_seconds = age;
  expect(acquisitionLinkState(t)).toBe('STALE');
});

test('frequency choices match native sparse ring and a user choice remains only a local draft', () => {
  const t = fixture();
  render(<MachineFrequency telemetry={t} />);
  const select = screen.getByRole('combobox', { name: 'Fréquence machine' });
  expect(select).toHaveValue('181000');
  expect(within(select).getAllByRole('option').map((option) => option.textContent))
    .toEqual(['—', '0,2 Hz', '0,5 Hz', '1 Hz', '2 Hz', '5 Hz', '10 Hz', '25 Hz', '50 Hz']);
  fireEvent.change(select, { target: { value: '81000' } });
  expect(select).toHaveValue('81000');
  expect(screen.getByText('Fréquence machine · brouillon')).toBeInTheDocument();
  expect(t.payload.snapshot.publications.C1011NI6602.data[3]).toBe(181000);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

test('stale or unmatched configured timing never becomes a measured frequency or a saved default', () => {
  const t = fixture();
  expect(frequencyReadback({ ...t, elapsed: 2 })).toBe('');
  t.payload.snapshot.publications.C1011NI6602.data[3] = 17;
  expect(frequencyReadback(t)).toBe('');
  render(<MachineFrequency telemetry={t} />);
  expect(screen.getByRole('combobox', { name: 'Fréquence machine' })).toHaveValue('');
  expect(screen.queryByText('Fréquence mesurée')).not.toBeInTheDocument();
});

test('one poller feeds header, display tabs and raw telemetry, and expires without user clicks', async () => {
  jest.useFakeTimers();
  const t = fixture();
  const client = { telemetry: jest.fn().mockResolvedValueOnce(t.payload).mockImplementation(() => new Promise(() => {})),
    snapshot: jest.fn().mockResolvedValue({ dps_fields: [], pages: {}, display_fields: {} }),
    replay: jest.fn(), stageIntent: jest.fn(), submitIntent: jest.fn() };
  try {
    const view = render(<Elyse client={client} />);
    await screen.findByText('Watchdog Acquisition : connecté');
    expect(screen.queryByRole('group', { name: 'Mode affichage' })).not.toBeInTheDocument();
    expect(screen.queryByText('Mesures en direct')).not.toBeInTheDocument();
    expect(screen.queryByText('Modèles hors ligne')).not.toBeInTheDocument();
    expect(screen.queryByText(/TÉLÉMÉTRIE XP → EVEREST/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox', { name: 'Fréquence machine' }), { target: { value: '81000' } });
    expect(screen.getByText('Fréquence machine · brouillon')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Modulateur', exact: true }));
    fireEvent.click(screen.getByRole('tab', { name: 'Télémétrie 10.20.30.10', exact: true }));
    expect(client.telemetry).toHaveBeenCalledTimes(1);
    await act(async () => { jest.advanceTimersByTime(2250); });
    expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveClass('elyse-watchdog--stale');
    expect(client.telemetry).toHaveBeenCalledTimes(2);
    expect(client.replay).not.toHaveBeenCalled();
    expect(client.stageIntent).not.toHaveBeenCalled();
    expect(client.submitIntent).not.toHaveBeenCalled();
    view.unmount();
    expect(client.telemetry.mock.calls[1][0].aborted).toBe(true);
  } finally { jest.useRealTimers(); }
});
