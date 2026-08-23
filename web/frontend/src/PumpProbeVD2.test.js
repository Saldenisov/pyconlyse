import { fetchVd2 } from './PumpProbeVD2';

const originalFetch = global.fetch;

describe('fetchVd2', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true });
    document.cookie = 'csrf_access_token=vd2%20token; path=/';
  });

  afterEach(() => {
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });

  test('adds CSRF to same-origin mutations and preserves request fields', () => {
    const body = JSON.stringify({ phase: 'BASE' });

    fetchVd2('/api/pump-probe-vd2/protocol/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'vd2-1' },
      credentials: 'include',
      body,
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-vd2/protocol/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-Id': 'vd2-1',
        'X-CSRF-TOKEN': 'vd2 token',
      },
      credentials: 'include',
      body,
    });
  });

  test('leaves GET request headers unchanged', () => {
    const options = { method: 'GET', headers: { 'X-Request-Id': 'vd2-2' } };

    fetchVd2('/api/pump-probe-vd2/state', options);

    expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-vd2/state', options);
  });
});
