import { withCsrfToken } from './csrfRequest';

describe('withCsrfToken', () => {
  beforeEach(() => {
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });

  test('adds the CSRF cookie value to unsafe same-origin requests only', () => {
    document.cookie = 'csrf_access_token=csrf%20value; path=/';

    expect(
      withCsrfToken('/api/device/test/command/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    ).toEqual({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-TOKEN': 'csrf value',
      },
    });
  });

  test.each([
    ['safe request', '/api/device/test/attributes', { method: 'GET' }],
    ['cross-origin request', 'https://outside.example/api/device/test', { method: 'POST' }],
  ])('does not send CSRF token for %s', (_label, url, options) => {
    document.cookie = 'csrf_access_token=csrf-token; path=/';

    expect(withCsrfToken(url, options)).toEqual(options);
  });

  test('uses no other cookie when CSRF cookie is absent', () => {
    document.cookie = 'session_token=not-a-csrf-token; path=/';

    expect(
      withCsrfToken('/api/server/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    ).toEqual({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  test('uses malformed CSRF cookie value without decoding it', () => {
    document.cookie = 'csrf_access_token=%E0%A4%A; path=/';

    expect(withCsrfToken('/api/server/control', { method: 'POST' })).toEqual({
      method: 'POST',
      headers: { 'X-CSRF-TOKEN': '%E0%A4%A' },
    });
  });

  test('clones Headers input before adding the CSRF token', () => {
    document.cookie = 'csrf_access_token=csrf-token; path=/';
    const headers = new Headers({ 'Content-Type': 'application/json' });

    const request = withCsrfToken('/api/server/control', {
      method: 'POST',
      headers,
    });

    expect(request.headers).toBeInstanceOf(Headers);
    expect(request.headers).not.toBe(headers);
    expect(headers.get('X-CSRF-TOKEN')).toBeNull();
    expect(request.headers.get('Content-Type')).toBe('application/json');
    expect(request.headers.get('X-CSRF-TOKEN')).toBe('csrf-token');
  });

  test('replaces an existing CSRF header regardless of casing', () => {
    document.cookie = 'csrf_access_token=fresh-token; path=/';

    expect(
      withCsrfToken('/api/server/control', {
        method: 'POST',
        headers: { 'x-csrf-token': 'stale-token' },
      })
    ).toEqual({
      method: 'POST',
      headers: { 'X-CSRF-TOKEN': 'fresh-token' },
    });
  });

  test('does not add a CSRF token when URL is invalid', () => {
    document.cookie = 'csrf_access_token=csrf-token; path=/';
    const options = { method: 'POST', headers: { 'Content-Type': 'application/json' } };

    expect(withCsrfToken('http://[invalid', options)).toBe(options);
  });
});
