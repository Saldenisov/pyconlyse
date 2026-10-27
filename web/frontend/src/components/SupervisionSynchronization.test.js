import React from 'react';
import { act, render, screen } from '@testing-library/react';
import SupervisionSynchronization from './SupervisionSynchronization';

const payload = (sequence = 1) => ({ schema_version: 1, owner: 'supervision', available: true,
  stale: false, values: Array.from({ length: 16 }, (_, index) => index + .25), age_seconds: .1,
  session_id: 'a'.repeat(32), sequence, read_only: true, hardware_acknowledged: false,
  physical_measurements_verified: false, selector: -1, pending_selector: false,
  source_mode: 'LABVIEW_BRIDGE', source: 'observed_labview_control_memory' });
const flush = async () => { await act(async () => { await Promise.resolve(); }); };
const advance = async (ms) => { await act(async () => { jest.advanceTimersByTime(ms); }); };
beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test('renders16 independent SuperVision values with no command buttons', async () => {
  const client = { synchronization: jest.fn().mockResolvedValue(payload()) };
  const { unmount } = render(<SupervisionSynchronization client={client} />);
  await flush();
  expect(screen.getByRole('status', { name: /synchronisation SuperVision$/ })).toHaveTextContent('Mémoire récente');
  for (let index = 0; index < 8; index += 1) {
    const name = ['LASER-HF', 'IMAC', 'LASER', 'Osc1', 'Osc2', 'Detect1', 'Detect2', 'Machine'][index];
    expect(screen.getByRole('rowheader', { name: `ctr${index} · ${name}` })).toBeInTheDocument();
    expect(screen.getByLabelText(`SuperVision ctr${index} délai`)).toHaveTextContent(String(index * 2 + .25));
    expect(screen.getByLabelText(`SuperVision ctr${index} largeur`)).toHaveTextContent(String(index * 2 + 1.25));
  }
  expect(screen.queryAllByRole('button')).toHaveLength(0);
  expect(screen.getByText('Paramètres lus sur SuperVision. Les impulsions physiques ne sont pas mesurées ici.')).toBeInTheDocument();
  unmount();
});

test('repeated observation cannot renew freshness and a new session recovers', async () => {
  const client = { synchronization: jest.fn().mockResolvedValue(payload()) };
  const { unmount } = render(<SupervisionSynchronization client={client} />);
  await flush(); await advance(1000); await advance(1000);
  expect(screen.getByRole('status', { name: /synchronisation SuperVision$/ })).toHaveTextContent('Mémoire périmée');
  expect(screen.getByLabelText('SuperVision ctr0 délai')).toHaveTextContent('—');
  client.synchronization.mockResolvedValue({ ...payload(), session_id: 'b'.repeat(32) });
  await advance(1000);
  expect(screen.getByRole('status', { name: /synchronisation SuperVision$/ })).toHaveTextContent('Mémoire récente');
  unmount();
});

test('lost read clears values immediately and sequence regression is unavailable', async () => {
  const client = { synchronization: jest.fn().mockResolvedValueOnce(payload(2))
    .mockRejectedValueOnce(new Error('DS absent')).mockResolvedValueOnce(payload(1)) };
  const { unmount } = render(<SupervisionSynchronization client={client} />);
  await flush(); await advance(1000);
  expect(screen.getByRole('alert')).toHaveTextContent('DS absent');
  expect(screen.getByLabelText('SuperVision ctr0 délai')).toHaveTextContent('—');
  await advance(1000);
  expect(screen.getByRole('alert')).toHaveTextContent('Séquence SuperVision antérieure');
  unmount();
});

test('a slow read does not overlap and elapsed HTTP time consumes age', async () => {
  let resolve;
  const client = { synchronization: jest.fn().mockImplementation(() => new Promise((finish) => { resolve = finish; })) };
  const { unmount } = render(<SupervisionSynchronization client={client} />);
  await advance(3000);
  expect(client.synchronization).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(payload()); });
  expect(screen.getByRole('status', { name: /synchronisation SuperVision$/ })).toHaveTextContent('Mémoire périmée');
  unmount();
});

test('unmount aborts read and disabled panel makes no request', async () => {
  const client = { synchronization: jest.fn().mockImplementation(() => new Promise(() => {})) };
  const first = render(<SupervisionSynchronization client={client} />);
  const signal = client.synchronization.mock.calls[0][0];
  first.unmount();
  expect(signal.aborted).toBe(true);
  await advance(10000);
  expect(client.synchronization).toHaveBeenCalledTimes(1);
  const second = render(<SupervisionSynchronization client={client} enabled={false} />);
  await flush();
  expect(client.synchronization).toHaveBeenCalledTimes(1);
  second.unmount();
});
