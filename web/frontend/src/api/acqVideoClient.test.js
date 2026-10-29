import { acqVideoClient, VIDEO_READ_DEADLINE_MS, MAX_VIDEO_JSON_CHARS } from './acqVideoClient';

const body = { schema_version: 1, owner: 'supervision', available: false, frame: null };
const response = (value = body) => ({ ok: true, text: async () => JSON.stringify(value) });
afterEach(() => { delete global.fetch; delete global.EventSource; jest.useRealTimers(); });

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

test('channel selection is a bounded passive read and cannot select a device or URL', async () => {
  global.fetch = jest.fn().mockResolvedValue(response());
  await acqVideoClient.video(undefined, { channel: 0 });
  expect(fetch.mock.calls[0][0]).toBe('/api/elyse/acquisition/telemetry/video?channel=0');
  expect(() => acqVideoClient.video(undefined, { channel: 'http://other' })).toThrow('Canal');
  expect(() => acqVideoClient.video(undefined, { channel: true })).toThrow('Canal');
});

test('SSE delivers frame/status events, retains one connection and closes on cancellation', () => {
  const listeners = {};
  const close = jest.fn();
  global.EventSource = jest.fn().mockImplementation(() => ({
    addEventListener: (name, action) => { listeners[name] = action; },
    removeEventListener: jest.fn(), close,
  }));
  const onFrame = jest.fn(); const onError = jest.fn();
  const controller = new AbortController();
  const stop = acqVideoClient.subscribe({ onFrame, onError, signal: controller.signal,
    channel: 2, targetFps: 12.5 });
  expect(EventSource).toHaveBeenCalledWith('/api/elyse/acquisition/telemetry/video/stream?fps=12.5&channel=2',
    { withCredentials: true });
  listeners.frame({ data: JSON.stringify(body) });
  listeners.status({ data: JSON.stringify(body) });
  expect(onFrame).toHaveBeenCalledTimes(2);
  listeners.error();
  expect(onError).toHaveBeenCalledTimes(1);
  controller.abort(); stop();
  expect(close).toHaveBeenCalledTimes(1);
  listeners.frame({ data: JSON.stringify(body) });
  expect(onFrame).toHaveBeenCalledTimes(2);
});

test('SSE rejects oversized event and permits explicit25Hz without a one-second timer', () => {
  const listeners = {};
  global.EventSource = jest.fn().mockImplementation(() => ({
    addEventListener: (name, action) => { listeners[name] = action; },
    removeEventListener: jest.fn(), close: jest.fn(),
  }));
  const onFrame = jest.fn(); const onError = jest.fn();
  const stop = acqVideoClient.subscribe({ onFrame, onError, targetFps: 25 });
  listeners.frame({ data: 'x'.repeat(MAX_VIDEO_JSON_CHARS + 1) });
  expect(onFrame).not.toHaveBeenCalled();
  expect(onError).toHaveBeenCalledTimes(1);
  expect(EventSource).toHaveBeenCalledTimes(1);
  stop();
});
