import fs from 'fs';
import path from 'path';
import { fireEvent } from '@testing-library/react';

const transportPath = path.resolve(process.cwd(), 'public/hardwareApprovalTransport.js');
const transportSource = fs.readFileSync(transportPath, 'utf8');
const standalonePages = [
  'basler_camera.html',
  'test_camera_api.html',
  'test_ds_itest_psu.html',
  'test_netio_pdu.html',
  'test_owis_ps90.html',
  'test_standa_motors.html',
];

function armNonce(value) {
  const control = document.querySelector('[aria-label="Hardware approval"]');
  fireEvent.change(control.querySelector('input'), { target: { value } });
  fireEvent.submit(control);
}

function lastRequestHeaders() {
  return window.fetch.mock.calls[window.fetch.mock.calls.length - 1][1].headers;
}

describe('standalone hardware approval transport', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
    window.Headers = Headers;
    window.fetch = jest.fn().mockResolvedValue({ ok: true });
    window.eval(transportSource);
  });

  test('accepts only exact lowercase nonce values without generating a replacement', () => {
    armNonce('A'.repeat(64));

    expect(document.querySelector('output').textContent).toMatch(/exactly 64 lowercase hexadecimal/);
    window.hardwareApprovalFetch('/api/device/test/command/start', {
      method: 'POST',
      headers: { 'X-PYCONLYSE-HARDWARE-APPROVAL': 'forged' },
    });
    expect(lastRequestHeaders().get('X-PYCONLYSE-HARDWARE-APPROVAL')).toBeNull();
  });

  test('adds CSRF and exact approval headers while replacing a forged header', async () => {
    document.cookie = 'csrf_access_token=csrf%20token; path=/';
    const nonce = 'a'.repeat(64);
    armNonce(nonce);

    await window.hardwareApprovalFetch('/api/device/test/command/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-pyconlyse-hardware-approval': 'forged',
      },
    });

    const headers = lastRequestHeaders();
    expect(headers.get('X-CSRF-TOKEN')).toBe('csrf token');
    expect(headers.get('X-PYCONLYSE-HARDWARE-APPROVAL')).toBe(nonce);
    expect(document.querySelector('output').textContent).toBe('Hardware approval consumed by a mutation attempt.');
  });

  test.each([
    ['rejects', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['throws', () => { throw new Error('fetch threw'); }],
  ])('consumes nonce before a fetch attempt that %s', async (_label, implementation) => {
    armNonce('b'.repeat(64));
    window.fetch.mockImplementation(implementation);

    try {
      await window.hardwareApprovalFetch('/api/device/test/command/start', { method: 'POST' });
    } catch (_error) {
      // Consumption happens before both rejected and synchronous fetch failures.
    }

    expect(document.querySelector('output').textContent).toBe('Hardware approval consumed by a mutation attempt.');
    window.fetch.mockResolvedValue({ ok: true });
    window.hardwareApprovalFetch('/api/device/test/command/start', { method: 'POST' });
    expect(lastRequestHeaders()).toBeUndefined();
  });

  test('fails closed for same-turn approval fan-out, then permits a freshly armed request', async () => {
    armNonce('d'.repeat(64));

    const requests = [
      window.hardwareApprovalFetch('/api/device/one/command/start', { method: 'POST' }),
      window.hardwareApprovalFetch('/api/device/two/command/start', { method: 'POST' }),
    ];

    expect(window.fetch).not.toHaveBeenCalled();
    const results = await Promise.allSettled(requests);
    results.forEach((result) => {
      expect(result.status).toBe('rejected');
      expect(result.reason.message).toMatch(/concurrent hardware approval requests/i);
    });
    expect(window.fetch).not.toHaveBeenCalled();

    const freshNonce = 'e'.repeat(64);
    armNonce(freshNonce);
    await window.hardwareApprovalFetch('/api/device/one/command/start', { method: 'POST' });

    expect(window.fetch).toHaveBeenCalledTimes(1);
    expect(lastRequestHeaders().get('X-PYCONLYSE-HARDWARE-APPROVAL')).toBe(freshNonce);
  });

  test('does not consume nonce for safe or cross-origin requests', async () => {
    const nonce = 'c'.repeat(64);
    armNonce(nonce);

    window.hardwareApprovalFetch('/api/device/test/attributes', { method: 'GET' });
    expect(window.fetch).toHaveBeenLastCalledWith('/api/device/test/attributes', { method: 'GET' });
    window.hardwareApprovalFetch('https://outside.example/api/device/test', { method: 'POST' });
    expect(window.fetch).toHaveBeenLastCalledWith('https://outside.example/api/device/test', { method: 'POST' });

    await window.hardwareApprovalFetch('/api/device/test/command/start', { method: 'POST' });
    expect(lastRequestHeaders().get('X-PYCONLYSE-HARDWARE-APPROVAL')).toBe(nonce);
  });

  test('is referenced by every standalone page and leaves no raw fetch calls', () => {
    standalonePages.forEach((page) => {
      const source = fs.readFileSync(path.resolve(process.cwd(), '..', page), 'utf8');
      expect(source).toContain('/hardwareApprovalTransport.js');
      expect(source).not.toMatch(/\bfetch\(/);
    });
  });
});
