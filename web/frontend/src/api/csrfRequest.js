const CSRF_COOKIE_NAME = 'csrf_access_token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);
const HARDWARE_APPROVAL_HEADER = 'X-PYCONLYSE-HARDWARE-APPROVAL';
const HARDWARE_APPROVAL_NONCE = /^[0-9a-f]{64}$/;
export const HARDWARE_APPROVAL_CONCURRENCY_ERROR = 'Concurrent hardware approval requests are not allowed.';

let pendingHardwareApprovalNonce = null;
let transientHardwareApprovalDispatch = null;
const hardwareApprovalListeners = new Set();

function notifyHardwareApprovalStatus(status) {
  hardwareApprovalListeners.forEach((listener) => {
    try {
      listener(status);
    } catch (_error) {
      // Approval transport must not be interrupted by UI listeners.
    }
  });
}

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

function appendHardwareApprovalHeader(headers, nonce) {
  const result = removeHardwareApprovalHeader(headers);

  if (typeof Headers !== 'undefined' && result instanceof Headers) {
    result.set(HARDWARE_APPROVAL_HEADER, nonce);
    return result;
  }

  result[HARDWARE_APPROVAL_HEADER] = nonce;
  return result;
}

function removeHardwareApprovalHeader(headers) {
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    const result = new Headers(headers);
    result.delete(HARDWARE_APPROVAL_HEADER);
    return result;
  }

  const result = { ...(headers || {}) };
  Object.keys(result).forEach((key) => {
    if (key.toLowerCase() === HARDWARE_APPROVAL_HEADER.toLowerCase()) {
      delete result[key];
    }
  });
  return result;
}

function hasHardwareApprovalHeader(headers) {
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    return headers.has(HARDWARE_APPROVAL_HEADER);
  }

  return Object.keys(headers || {}).some(
    (key) => key.toLowerCase() === HARDWARE_APPROVAL_HEADER.toLowerCase()
  );
}

function isUnsafeSameOriginRequest(url, options) {
  const method = String(options.method || 'GET').toUpperCase();
  return !SAFE_METHODS.has(method) && isSameOrigin(url);
}

export function withCsrfToken(url, options = {}) {
  if (!isUnsafeSameOriginRequest(url, options)) {
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

export function fetchWithCsrfToken(url, options = {}) {
  let requestOptions = withCsrfToken(url, options);
  if (hasHardwareApprovalHeader(requestOptions.headers)) {
    requestOptions = {
      ...requestOptions,
      headers: removeHardwareApprovalHeader(requestOptions.headers),
    };
  }
  return fetch(url, requestOptions);
}

export function setHardwareApprovalNonce(nonce) {
  if (typeof nonce !== 'string' || !HARDWARE_APPROVAL_NONCE.test(nonce)) {
    pendingHardwareApprovalNonce = null;
    notifyHardwareApprovalStatus('cleared');
    return false;
  }

  pendingHardwareApprovalNonce = nonce;
  notifyHardwareApprovalStatus('armed');
  return true;
}

export function clearHardwareApprovalNonce() {
  pendingHardwareApprovalNonce = null;
  notifyHardwareApprovalStatus('cleared');
}

export function getHardwareApprovalNonce() {
  return pendingHardwareApprovalNonce;
}

export function isHardwareApprovalConcurrencyError(error) {
  return error?.message === HARDWARE_APPROVAL_CONCURRENCY_ERROR;
}

function queueApprovedHardwareRequest(url, requestOptions) {
  return new Promise((resolve, reject) => {
    const request = { url, requestOptions, resolve, reject };
    if (transientHardwareApprovalDispatch) {
      transientHardwareApprovalDispatch.requests.push(request);
      return;
    }

    const dispatch = { requests: [request] };
    transientHardwareApprovalDispatch = dispatch;
    Promise.resolve().then(() => {
      if (transientHardwareApprovalDispatch === dispatch) {
        transientHardwareApprovalDispatch = null;
      }

      if (dispatch.requests.length !== 1) {
        dispatch.requests.forEach(({ reject: rejectRequest }) => {
          rejectRequest(new Error(HARDWARE_APPROVAL_CONCURRENCY_ERROR));
        });
        return;
      }

      try {
        dispatch.requests[0].resolve(fetch(url, requestOptions));
      } catch (error) {
        dispatch.requests[0].reject(error);
      }
    });
  });
}

export function fetchWithHardwareApproval(url, options = {}) {
  const isUnsafeSameOrigin = isUnsafeSameOriginRequest(url, options);
  let requestOptions = withCsrfToken(url, options);
  if (hasHardwareApprovalHeader(requestOptions.headers)) {
    requestOptions = {
      ...requestOptions,
      headers: removeHardwareApprovalHeader(requestOptions.headers),
    };
  }
  if (isUnsafeSameOrigin && transientHardwareApprovalDispatch) {
    return queueApprovedHardwareRequest(url, requestOptions);
  }
  if (isUnsafeSameOrigin && pendingHardwareApprovalNonce) {
    const nonce = pendingHardwareApprovalNonce;
    pendingHardwareApprovalNonce = null;
    notifyHardwareApprovalStatus('consumed');
    requestOptions = {
      ...requestOptions,
      headers: appendHardwareApprovalHeader(requestOptions.headers, nonce),
    };
    return queueApprovedHardwareRequest(url, requestOptions);
  }

  return fetch(url, requestOptions);
}

export function subscribeHardwareApprovalStatus(listener) {
  hardwareApprovalListeners.add(listener);
  return () => hardwareApprovalListeners.delete(listener);
}
