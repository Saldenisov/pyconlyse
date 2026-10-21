import { acqTelemetryClient } from './acqTelemetryClient';

afterEach(() => { delete global.fetch; });

test('only the fixed read-only standard-bank web route is used', async () => {
  const value = { schema_version: 1, expected_banks: ['C1NI6071E'] };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => value });
  const signal = new AbortController().signal;
  expect(await acqTelemetryClient.telemetry(signal)).toBe(value);
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/telemetry', {
    method: 'GET', credentials: 'include', cache: 'no-store', signal,
  });
});

test('a rejected or incompatible response is not displayed as fresh data', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, json: async () => ({ error: 'unavailable' }) });
  await expect(acqTelemetryClient.telemetry()).rejects.toThrow('unavailable');
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ schema_version: 0 }) });
  await expect(acqTelemetryClient.telemetry()).rejects.toThrow('incompatible');
});
