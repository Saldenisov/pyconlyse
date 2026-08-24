import {
  clearHardwareApprovalNonce,
  fetchWithHardwareApproval,
  getHardwareApprovalNonce,
  setHardwareApprovalNonce,
  subscribeHardwareApprovalStatus,
} from './csrfRequest';

const originalFetch = global.fetch;

describe('hardware approval request transport', () => {
  beforeEach(() => {
    clearHardwareApprovalNonce();
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
    global.fetch = jest.fn(() => Promise.resolve({ ok: true }));
  });

  afterEach(() => {
    clearHardwareApprovalNonce();
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
  });

  test.each([
    ['uppercase', 'A'.repeat(64)],
    ['short', 'a'.repeat(63)],
    ['non-hex', `${'a'.repeat(63)}g`],
    ['non-string', null],
  ])('rejects %s nonce values without generating a replacement', (_label, nonce) => {
    expect(setHardwareApprovalNonce(nonce)).toBe(false);
    expect(getHardwareApprovalNonce()).toBeNull();
  });

  test('clears a previously armed nonce when an invalid replacement is supplied', () => {
    expect(setHardwareApprovalNonce('a'.repeat(64))).toBe(true);
    expect(setHardwareApprovalNonce('invalid')).toBe(false);
    expect(getHardwareApprovalNonce()).toBeNull();
  });

  test('adds operator nonce with CSRF then consumes it before a successful mutation', async () => {
    document.cookie = 'csrf_access_token=csrf%20token; path=/';
    const nonce = 'a'.repeat(64);
    expect(setHardwareApprovalNonce(nonce)).toBe(true);

    await fetchWithHardwareApproval('/api/device/test/command/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/device/test/command/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-TOKEN': 'csrf token',
        'X-PYCONLYSE-HARDWARE-APPROVAL': nonce,
      },
    });
    expect(getHardwareApprovalNonce()).toBeNull();
  });

  test('consumes operator nonce when fetch rejects', async () => {
    const statuses = [];
    const unsubscribe = subscribeHardwareApprovalStatus((status) => statuses.push(status));
    global.fetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    const nonce = 'b'.repeat(64);
    setHardwareApprovalNonce(nonce);

    await expect(fetchWithHardwareApproval('/api/device/test/command/start', { method: 'POST' }))
      .rejects.toThrow('Failed to fetch');

    expect(getHardwareApprovalNonce()).toBeNull();
    expect(statuses).toEqual(['armed', 'consumed']);
    unsubscribe();
  });

  test('consumes operator nonce when fetch throws synchronously', async () => {
    const statuses = [];
    const unsubscribe = subscribeHardwareApprovalStatus((status) => statuses.push(status));
    global.fetch.mockImplementation(() => { throw new Error('fetch threw'); });
    setHardwareApprovalNonce('b'.repeat(64));

    await expect(fetchWithHardwareApproval('/api/device/test/command/start', { method: 'POST' }))
      .rejects.toThrow('fetch threw');
    expect(getHardwareApprovalNonce()).toBeNull();
    expect(statuses).toEqual(['armed', 'consumed']);
    unsubscribe();
  });

  test('fails closed for same-turn approval fan-out, then permits a freshly armed request', async () => {
    const nonce = 'd'.repeat(64);
    setHardwareApprovalNonce(nonce);

    const requests = [
      fetchWithHardwareApproval('/api/device/one/command/start', { method: 'POST' }),
      fetchWithHardwareApproval('/api/device/two/command/start', { method: 'POST' }),
    ];

    expect(global.fetch).not.toHaveBeenCalled();
    const results = await Promise.allSettled(requests);
    results.forEach((result) => {
      expect(result.status).toBe('rejected');
      expect(result.reason.message).toMatch(/concurrent hardware approval requests/i);
    });
    expect(global.fetch).not.toHaveBeenCalled();
    expect(getHardwareApprovalNonce()).toBeNull();

    setHardwareApprovalNonce('e'.repeat(64));
    await fetchWithHardwareApproval('/api/device/one/command/start', { method: 'POST' });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch.mock.calls[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL'])
      .toBe('e'.repeat(64));
  });

  test('replaces caller-supplied approval header and preserves Headers input', async () => {
    document.cookie = 'csrf_access_token=csrf%20token; path=/';
    const headers = new Headers({
      'Content-Type': 'application/json',
      'X-PYCONLYSE-HARDWARE-APPROVAL': 'forged',
    });
    const nonce = 'f'.repeat(64);
    setHardwareApprovalNonce(nonce);

    await fetchWithHardwareApproval('/api/device/test/command/start', { method: 'POST', headers });

    const requestHeaders = global.fetch.mock.calls[0][1].headers;
    expect(requestHeaders).toBeInstanceOf(Headers);
    expect(requestHeaders.get('X-CSRF-TOKEN')).toBe('csrf token');
    expect(requestHeaders.get('X-PYCONLYSE-HARDWARE-APPROVAL')).toBe(nonce);
    expect(headers.get('X-PYCONLYSE-HARDWARE-APPROVAL')).toBe('forged');
  });

  test('strips caller-supplied approval header without an armed nonce', async () => {
    await fetchWithHardwareApproval('/api/device/test/command/start', {
      method: 'POST',
      headers: { 'x-pyconlyse-hardware-approval': 'forged' },
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/device/test/command/start', {
      method: 'POST',
      headers: {},
    });
  });

  test('does not attach or consume nonce for safe or cross-origin requests', async () => {
    const nonce = 'c'.repeat(64);
    setHardwareApprovalNonce(nonce);

    await fetchWithHardwareApproval('/api/device/test/attributes', { method: 'GET' });
    expect(global.fetch).toHaveBeenLastCalledWith('/api/device/test/attributes', { method: 'GET' });
    expect(getHardwareApprovalNonce()).toBe(nonce);

    await fetchWithHardwareApproval('https://outside.example/api/device/test', { method: 'POST' });
    expect(global.fetch).toHaveBeenLastCalledWith('https://outside.example/api/device/test', { method: 'POST' });
    expect(getHardwareApprovalNonce()).toBe(nonce);
  });
});
