import { fetchJsonWithRetry, pumpProbeRequest } from './shared';

const originalFetch = global.fetch;

function successfulResponse(payload = { success: true }) {
  return { ok: true, status: 200, json: jest.fn().mockResolvedValue(payload) };
}

describe('pump-probe V0 request helpers', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue(successfulResponse());
    document.cookie = 'csrf_access_token=v0%20token; path=/';
  });

  afterEach(() => {
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });

  test('pumpProbeRequest adds CSRF while preserving mutation body and headers', async () => {
    const body = JSON.stringify({ action: 'initialize' });
    await pumpProbeRequest('/hardware/initialize', {
      method: 'POST',
      headers: { 'X-Request-Id': 'v0-1' },
      body,
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-v0/hardware/initialize', {
      method: 'POST',
      headers: { 'X-Request-Id': 'v0-1', 'X-CSRF-TOKEN': 'v0 token' },
      credentials: 'include',
      body,
    });
  });

  test('fetchJsonWithRetry adds CSRF to mutation requests', async () => {
    const body = JSON.stringify({ args: [1, 0] });
    await fetchJsonWithRetry('/api/device/v0/pdu/command/set_channels_states', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/device/v0/pdu/command/set_channels_states',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-TOKEN': 'v0 token',
        },
        body,
      }
    );
  });

  test('pumpProbeRequest leaves GET request free of a CSRF header', async () => {
    await pumpProbeRequest('/state', { headers: { 'X-Request-Id': 'v0-2' } });

    expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-v0/state', {
      headers: { 'X-Request-Id': 'v0-2' },
      credentials: 'include',
    });
  });
});
