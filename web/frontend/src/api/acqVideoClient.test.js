import { acqVideoClient, VIDEO_READ_DEADLINE_MS, MAX_VIDEO_JSON_CHARS } from './acqVideoClient';

const body = { schema_version: 1, owner: 'supervision', available: false, frame: null };
const response = (value = body) => ({ ok: true, text: async () => JSON.stringify(value) });
afterEach(() => { delete global.fetch; jest.useRealTimers(); });

test('uses only fixed same-origin read-only endpoint with authenticated JWT cookies', async () => {
  global.fetch = jest.fn().mockResolvedValue(response());
  expect(await acqVideoClient.video()).toEqual(body);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/telemetry/video', {
    method: 'GET', credentials: 'include', cache: 'no-store', signal: expect.any(AbortSignal),
  });
});

test('bounds a hung fetch and never overlaps or retries it implicitly', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
  const waiting = acqVideoClient.video().catch((error) => error);
  jest.advanceTimersByTime(VIDEO_READ_DEADLINE_MS);
  expect((await waiting).message).toContain('5 s');
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

test('deadline includes response-body reading', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn().mockResolvedValue({ ok: true, text: () => new Promise(() => {}) });
  const waiting = acqVideoClient.video().catch((error) => error);
  await Promise.resolve();
  jest.advanceTimersByTime(VIDEO_READ_DEADLINE_MS);
  expect((await waiting).message).toContain('5 s');
});

test('external cancellation settles promptly even when an injected fetch ignores abort', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
  const controller = new AbortController();
  const waiting = acqVideoClient.video(controller.signal).catch((error) => error);
  controller.abort();
  expect((await waiting).name).toBe('AbortError');
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  expect(jest.getTimerCount()).toBe(0);
});

test('an already-aborted caller never sends a request', async () => {
  global.fetch = jest.fn();
  const controller = new AbortController(); controller.abort();
  await expect(acqVideoClient.video(controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(fetch).not.toHaveBeenCalled();
});

test('refuses oversized bodies/declared size before image decoding', async () => {
  const read = jest.fn();
  global.fetch = jest.fn().mockResolvedValue({ ok: true,
    headers: { get: () => String(MAX_VIDEO_JSON_CHARS + 1) }, text: read });
  await expect(acqVideoClient.video()).rejects.toThrow('volumineuse');
  expect(read).not.toHaveBeenCalled();
  fetch.mockResolvedValue({ ok: true, text: async () => 'x'.repeat(MAX_VIDEO_JSON_CHARS + 1) });
  await expect(acqVideoClient.video()).rejects.toThrow('volumineuse');
});

test('unauthorized or unavailable server response cannot become a current image', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 503,
    text: async () => JSON.stringify({ error: 'Video source unavailable' }) });
  await expect(acqVideoClient.video()).rejects.toThrow('Video source unavailable');
  expect(fetch).toHaveBeenCalledTimes(1);
});
