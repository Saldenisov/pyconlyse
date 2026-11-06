import { act, renderHook, waitFor } from '@testing-library/react';
import useSupervisionHistory, { mergeHistory } from './useSupervisionHistory';
import { temperaturePaths } from './fluidesTrend';

beforeEach(() => localStorage.clear());

test('deduplicates receipts, keeps sessions distinct, clips the selected window', () => {
  const now = 1800000000000;
  const first = { time: now - 1000, session: 'a', receipt: '1', canon: 20 };
  const samples = mergeHistory([first], [{ ...first, canon: 21 }, { ...first, session: 'b' },
    { ...first, receipt: 'old', time: now - 31 * 60000 }], 30, now);
  expect(samples).toHaveLength(2);
  expect(samples[0].canon).toBe(21);
});

test('faster polling retains the history window and picks actual latest samples, not invented averages', () => {
  const now = 1800000000000;
  const incoming = Array.from({ length: 2400 }, (_, i) => ({ time: now - 1200000 + i * 500,
    session: 'receiver', receipt: String(i), canon: i }));
  const samples = mergeHistory([], incoming, 30, now);
  expect(samples).toHaveLength(1200);
  expect(samples[0]).toEqual(incoming[1]);
  expect(samples.at(-1)).toEqual(incoming.at(-1));
  expect(samples.at(-1).time - samples[0].time).toBe(1199000);
});

test('receiver session changes and explicit gaps never draw connected segments', () => {
  const path = temperaturePaths([{ time: 0, canon: 20, session: 'a' }, { time: 1000, canon: 21, session: 'b' },
    { time: 1500, canon: null, session: 'gap' }, { time: 2000, canon: 22, session: 'b' }], 'canon', (x) => x, (y) => y);
  expect(path).not.toContain('L');
});

test('remount restores server SQLite samples, not a new empty browser curve', async () => {
  const now = Date.now();
  const client = { history: jest.fn().mockResolvedValue({ storage: 'server_sqlite', samples: [
    { time: now - 1000, session: 'a', receipt: '2', canon: 20.5, section: 21.1 }], error: '' }) };
  const telemetry = { payload: null, elapsed: 0, failure: '' };
  const first = renderHook(() => useSupervisionHistory(client, telemetry, true));
  await waitFor(() => expect(first.result.current.samples).toHaveLength(1));
  first.unmount();
  const restored = renderHook(() => useSupervisionHistory(client, telemetry, true));
  await waitFor(() => expect(restored.result.current.storage).toBe('server_sqlite'));
  expect(restored.result.current.samples[0].canon).toBe(20.5);
  expect(client.history).toHaveBeenCalledTimes(2);
  restored.unmount();
});

test('history-window preference survives remount and requests the selected server window', async () => {
  const client = { history: jest.fn().mockResolvedValue({ storage: 'server_sqlite', samples: [], error: '' }) };
  const telemetry = { payload: null, elapsed: 0, failure: '' };
  const view = renderHook(() => useSupervisionHistory(client, telemetry, true));
  await waitFor(() => expect(view.result.current.storage).toBe('server_sqlite'));
  expect(view.result.current.minutes).toBe(30);
  act(() => view.result.current.changeMinutes(120));
  await waitFor(() => expect(client.history).toHaveBeenLastCalledWith(120, expect.any(AbortSignal)));
  view.unmount();
  const restored = renderHook(() => useSupervisionHistory(client, telemetry, true));
  expect(restored.result.current.minutes).toBe(120);
  await waitFor(() => expect(client.history).toHaveBeenLastCalledWith(120, expect.any(AbortSignal)));
  restored.unmount();
});
