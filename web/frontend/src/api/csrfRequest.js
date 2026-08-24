const CSRF_COOKIE_NAME = 'csrf_access_token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

function readCsrfToken() {
  if (typeof document === 'undefined') {
    return null;
  }

  const cookiePrefix = `${CSRF_COOKIE_NAME}=`;
  const entry = document.cookie
    .split(';')
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(cookiePrefix));

  if (!entry) {
    return null;
  }

  const value = entry.slice(cookiePrefix.length);
  if (!value) {
    return null;
  }

  try {
    return decodeURIComponent(value);
  } catch (_error) {
    return value;
  }
}

function isSameOrigin(url) {
  if (typeof window === 'undefined' || !window.location?.origin) {
    return false;
  }

  try {
    return new URL(url, window.location.origin).origin === window.location.origin;
  } catch (_error) {
    return false;
  }
}

function appendCsrfHeader(headers, token) {
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    const result = new Headers(headers);
    result.set('X-CSRF-TOKEN', token);
    return result;
  }

  const result = { ...(headers || {}) };
  Object.keys(result).forEach((key) => {
    if (key.toLowerCase() === 'x-csrf-token') {
      delete result[key];
    }
  });
  result['X-CSRF-TOKEN'] = token;
  return result;
}

export function withCsrfToken(url, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  if (SAFE_METHODS.has(method) || !isSameOrigin(url)) {
    return options;
  }

  const token = readCsrfToken();
  if (!token) {
    return options;
  }

  return {
    ...options,
    headers: appendCsrfHeader(options.headers, token),
  };
}
