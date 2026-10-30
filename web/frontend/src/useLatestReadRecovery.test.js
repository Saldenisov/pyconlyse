import { act, renderHook } from '@testing-library/react';
import { TELEMETRY_READ_DEADLINE_MS, useLatestRead } from './useAcquisitionTelemetry';

async function advance(ms) {
  await act(async () => { await Promise.resolve(); });
  for (let t = 0; t < ms; t += 25) {
    await act(async () => { jest.advanceTimersByTime(Math.min(25, ms - t)); });
  }
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test('aborts a stuck read and recovers automatically with one request at a time', async () => {
  let active = 0, maximum = 0;
  const client = { telemetry: jest.fn()
    .mockResolvedValueOnce({ sequence: 1 })
    .mockImplementationOnce(signal => {
      active += 1; maximum = Math.max(maximum, active);
      return new Promise((resolve, reject) => signal.addEventListener('abort', () => {
        active -= 1;
        reject(new Error('aborted'));
      }, { once: true }));
    })
    .mockImplementation(() => {
      active += 1; maximum = Math.max(maximum, active);
      return Promise.resolve({ sequence: 3 }).finally(() => { active -= 1; });
    }) };
  const view = renderHook(() => useLatestRead(client, 'telemetry'));
  await advance(500 + TELEMETRY_READ_DEADLINE_MS);
  expect(client.telemetry.mock.calls[1][0].aborted).toBe(true);
  expect(view.result.current.failure).toMatch(/Délai/);
  expect(view.result.current.payload).toEqual({ sequence: 1 });
  await advance(25);
  expect(view.result.current.payload).toEqual({ sequence: 3 });
  expect(view.result.current.failure).toBe('');
  expect(maximum).toBe(1);
  view.unmount();
});

test('an abort-ignoring client cannot overlap reads or freshen data with a late response', async () => {
  let settle;
  const client = { telemetry: jest.fn()
    .mockResolvedValueOnce({ sequence: 1 })
    .mockImplementationOnce(() => new Promise(resolve => { settle = resolve; }))
    .mockResolvedValue({ sequence: 3 }) };
  const view = renderHook(() => useLatestRead(client, 'telemetry'));
  await advance(500 + TELEMETRY_READ_DEADLINE_MS + 1000);
  expect(client.telemetry).toHaveBeenCalledTimes(2);
  expect(view.result.current.failure).toMatch(/Délai/);
  const elapsed = view.result.current.elapsed;
  await act(async () => { settle({ sequence: 2 }); });
  expect(view.result.current.payload).toEqual({ sequence: 1 });
  expect(view.result.current.failure).toMatch(/Délai/);
  expect(view.result.current.elapsed).toBe(elapsed);
  await advance(25);
  expect(client.telemetry).toHaveBeenCalledTimes(3);
  expect(view.result.current.payload).toEqual({ sequence: 3 });
  view.unmount();
});

test('cleanup cancels an active deadline and suppresses recovery after unmount', async () => {
  const client = { telemetry: jest.fn(signal => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  })) };
  const view = renderHook(() => useLatestRead(client, 'telemetry'));
  await advance(1000);
  view.unmount();
  await advance(TELEMETRY_READ_DEADLINE_MS * 2);
  expect(client.telemetry.mock.calls[0][0].aborted).toBe(true);
  expect(client.telemetry).toHaveBeenCalledTimes(1);
});

test('slow successful reads retain the cadence without overlapping or timing out', async () => {
  const starts = [];
  let active = 0, maximum = 0;
  const client = { telemetry: jest.fn(() => {
    starts.push(performance.now());
    active += 1; maximum = Math.max(maximum, active);
    return new Promise(resolve => setTimeout(() => {
      active -= 1;
      resolve({ sequence: starts.length });
    }, 850));
  }) };
  const view = renderHook(() => useLatestRead(client, 'telemetry'));
  await advance(3500);
  expect(starts.map(t => t - starts[0])).toEqual([0, 875, 1750, 2625, 3500]);
  expect(maximum).toBe(1);
  expect(view.result.current.failure).toBe('');
  view.unmount();
});
