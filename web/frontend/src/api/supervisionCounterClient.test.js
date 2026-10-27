import { supervisionCounterClient, SYNC_READ_DEADLINE_MS, MAX_SYNC_JSON_CHARS } from './supervisionCounterClient';
afterEach(() => { delete global.fetch; jest.useRealTimers(); });

test('only authenticated fixed same-origin GET is used', async () => {
  const value = { schema_version: 1 };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, text: async () => JSON.stringify(value) });
  expect(await supervisionCounterClient.synchronization()).toEqual(value);
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/telemetry/synchronization', {
    method: 'GET', credentials: 'include', cache: 'no-store', signal: expect.any(AbortSignal),
  });
});

test('hung read has5-second deadline and no implicit retry', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
  const result = supervisionCounterClient.synchronization().catch((error) => error);
  jest.advanceTimersByTime(SYNC_READ_DEADLINE_MS);
  expect((await result).message).toContain('5 s');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('oversized metadata and caller cancellation settle without commands', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, text: async () => 'x'.repeat(MAX_SYNC_JSON_CHARS + 1) });
  await expect(supervisionCounterClient.synchronization()).rejects.toThrow('volumineuse');
  fetch.mockImplementation(() => new Promise(() => {}));
  const controller = new AbortController();
  const result = supervisionCounterClient.synchronization(controller.signal).catch((error) => error);
  controller.abort();
  expect((await result).name).toBe('AbortError');
});
