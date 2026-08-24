import { fetchJsonWithRetry, pumpProbeRequest } from './shared';
import {
  clearHardwareApprovalNonce,
  getHardwareApprovalNonce,
  setHardwareApprovalNonce,
} from '../api/csrfRequest';

const originalFetch = global.fetch;

function successfulResponse(payload = { success: true }) {
  return { ok: true, status: 200, json: jest.fn().mockResolvedValue(payload) };
}

describe('pump-probe V0 request helpers', () => {
  beforeEach(() => {
    clearHardwareApprovalNonce();
    global.fetch = jest.fn().mockResolvedValue(successfulResponse());
    document.cookie = 'csrf_access_token=v0%20token; path=/';
  });

  afterEach(() => {
    clearHardwareApprovalNonce();
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

  test.each([
    ['/config', { control_mode: 'emulator' }],
    ['/hardware-config', { control_mode: 'emulator' }],
    ['/hardware/preflight', {}],
    ['/faraday', { closed: true }],
    ['/crystal/move', {}],
    ['/reset', {}],
    ['/run', { running: false }],
    ['/realtime', { enabled: false }],
  ])('preserves approval for non-hardware V0 POST %s', async (path, payload) => {
    const nonce = 'a'.repeat(64);
    setHardwareApprovalNonce(nonce);
    const body = typeof payload === 'string' ? payload : JSON.stringify(payload);

    await pumpProbeRequest(path, { method: 'POST', body });

    expect(global.fetch.mock.calls[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBeUndefined();
    expect(getHardwareApprovalNonce()).toBe(nonce);
  });

  test.each([
    ['/hardware/initialize', {}],
    ['/run', { running: true }],
    ['/realtime', { enabled: true }],
    ['/stage/move', { position_mm: 1 }],
    ['/stage/stop', {}],
    ['/sample-stage/move', { position_mm: 1 }],
    ['/sample-stage/stop', {}],
    ['/run', {}],
    ['/realtime', {}],
  ])('consumes approval for hardware-capable V0 POST %s', async (path, payload) => {
    const nonce = 'b'.repeat(64);
    setHardwareApprovalNonce(nonce);

    await pumpProbeRequest(path, { method: 'POST', body: JSON.stringify(payload) });

    expect(global.fetch.mock.calls[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe(nonce);
    expect(getHardwareApprovalNonce()).toBeNull();
  });

  test.each([
    ['/run', {}],
    ['/realtime', {}],
    ['/run', { body: '{not json' }],
    ['/realtime', { body: '{not json' }],
    ['/run', { body: { running: false } }],
    ['/realtime', { body: { enabled: false } }],
  ])('consumes approval unless %s body explicitly disables the action', async (path, requestOptions) => {
    const nonce = 'f'.repeat(64);
    setHardwareApprovalNonce(nonce);

    await pumpProbeRequest(path, { method: 'POST', ...requestOptions });

    expect(global.fetch.mock.calls[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe(nonce);
    expect(getHardwareApprovalNonce()).toBeNull();
  });

  test('fails closed without retrying a same-turn generic device fan-out', async () => {
    setHardwareApprovalNonce('c'.repeat(64));

    const results = await Promise.allSettled([
      fetchJsonWithRetry('/api/device/v0/one/command/start', { method: 'POST' }),
      fetchJsonWithRetry('/api/device/v0/two/command/start', { method: 'POST' }),
    ]);

    expect(results.map((result) => result.status)).toEqual(['rejected', 'rejected']);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('does not retry a transient generic device failure after consuming approval', async () => {
    const nonce = 'd'.repeat(64);
    global.fetch.mockRejectedValue(new Error('Connection request was delayed'));
    setHardwareApprovalNonce(nonce);

    await expect(fetchJsonWithRetry('/api/device/v0/one/command/start', { method: 'POST' }))
      .rejects.toThrow('Connection request was delayed');

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch.mock.calls[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe(nonce);
    expect(getHardwareApprovalNonce()).toBeNull();
  });
});
