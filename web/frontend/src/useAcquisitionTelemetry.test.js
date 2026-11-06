import React from 'react';
import { act, render, renderHook, screen } from '@testing-library/react';
import useAcquisitionTelemetry, { TELEMETRY_POLL_MS, useLatestRead } from './useAcquisitionTelemetry';
import { AcquisitionWatchdog } from './SupervisionHeader';
import FluidesPanel from './FluidesPanel';

function payload(age = 0.5) {
  const bank = (size, name, kind, value) => ({ age_seconds: age, stale: false,
    data: Array(size).fill(value), error: { status: false, code: 0 },
    lv_type: { type: 'Cluster', name, fields: Array(size).fill({ type: kind }) } });
  return { schema_version: 1, server_state: 'ON', quality: 'FRESH', stale_after_seconds: 2,
    snapshot: { receiver_session: 'one', received_this_process: 1, publications: {
      C1NI6071E: bank(64, 'C1NI6071E', 'DBL', 20),
      C3_IN_DIO96: bank(56, 'C3_IN_DIO96', 'Boolean', true),
      C4_IN_DIO96: bank(64, 'C4_IN_DIO96', 'Boolean', true),
    } } };
}

async function advance(ms) {
  // Settle each timer's promise before the next clock step, as a browser does.
  for (let t = 0; t < ms; t += 25) {
    await act(async () => { jest.advanceTimersByTime(Math.min(25, ms - t)); });
  }
}

function Fluides({ client }) {
  const telemetry = useAcquisitionTelemetry(client);
  return <><AcquisitionWatchdog telemetry={telemetry} />
    <FluidesPanel telemetry={telemetry} trend={{ samples: [], paused: false }} /></>;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test('fast reads start at 500-ms intervals, not 500 ms after each response', async () => {
  const starts = [];
  const client = { telemetry: jest.fn(() => {
    starts.push(performance.now());
    return new Promise(resolve => setTimeout(() => resolve(payload()), 200));
  }) };
  const view = renderHook(() => useAcquisitionTelemetry(client));
  await advance(1750);
  expect(TELEMETRY_POLL_MS).toBe(500);
  expect(starts.map(t => t - starts[0])).toEqual([0, 500, 1000, 1500]);
  view.unmount();
});

test('850-ms replies keep Fluides and watchdog fresh without overlapping reads', async () => {
  let active = 0, maximum = 0;
  const client = { telemetry: jest.fn(() => {
    active += 1; maximum = Math.max(maximum, active);
    return new Promise(resolve => setTimeout(() => { active -= 1; resolve(payload()); }, 850));
  }) };
  const view = render(<Fluides client={client} />);
  await advance(850);
  for (let i = 0; i < 60; i += 1) {
    await advance(100);
    expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent(': connecté');
    expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('20,0');
    expect(screen.getByLabelText('Canon Pressostat · true')).toBeInTheDocument();
  }
  expect(maximum).toBe(1);
  expect(client.telemetry.mock.calls.length).toBeGreaterThanOrEqual(7);
  view.unmount();
});

test('a hung read expires the last sample at 2 seconds, without catch-up requests', async () => {
  const client = { telemetry: jest.fn().mockResolvedValueOnce(payload(0.5))
    .mockImplementation(() => new Promise(() => {})) };
  const view = render(<Fluides client={client} />);
  await advance(0);
  await act(async () => { await Promise.resolve(); });
  await advance(1500);
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent('données périmées');
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('—');
  expect(screen.getByLabelText('Canon Pressostat · inconnu')).toBeInTheDocument();
  await advance(6000);
  expect(client.telemetry).toHaveBeenCalledTimes(2);
  view.unmount();
  expect(client.telemetry.mock.calls[1][0].aborted).toBe(true);
});

test('repeated HTTP success never refreshes an already stale source bank', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(payload(2.1)) };
  const view = render(<Fluides client={client} />);
  await advance(2000);
  expect(client.telemetry.mock.calls.length).toBeGreaterThan(2);
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent('données périmées');
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('—');
  view.unmount();
});

test('failed reads are explicit and a later fresh response recovers automatically', async () => {
  const client = { telemetry: jest.fn().mockResolvedValueOnce(payload())
    .mockRejectedValueOnce(new Error('offline')).mockResolvedValue(payload()) };
  const view = render(<Fluides client={client} />);
  await act(async () => { await Promise.resolve(); });
  await advance(500);
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent('déconnecté');
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('—');
  await advance(500);
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent(': connecté');
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('20,0');
  view.unmount();
});

test('disabled reads and late settlements after unmount cannot start new requests', async () => {
  let settle;
  const client = { telemetry: jest.fn(() => new Promise(resolve => { settle = resolve; })),
    coolingSafety: jest.fn() };
  const disabled = renderHook(() => useLatestRead(client, 'coolingSafety', false));
  await advance(1000);
  expect(client.coolingSafety).not.toHaveBeenCalled();
  disabled.unmount();
  const view = renderHook(() => useAcquisitionTelemetry(client));
  const signal = client.telemetry.mock.calls[0][0];
  view.unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => { settle(payload()); });
  await advance(2000);
  expect(client.telemetry).toHaveBeenCalledTimes(1);
});
