(function attachHardwareApprovalTransport(windowObject, documentObject) {
  'use strict';

  const APPROVAL_HEADER = 'X-PYCONLYSE-HARDWARE-APPROVAL';
  const CSRF_HEADER = 'X-CSRF-TOKEN';
  const CSRF_COOKIE_NAME = 'csrf_access_token';
  const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);
  const NONCE_PATTERN = /^[0-9a-f]{64}$/;
  const APPROVAL_CONCURRENCY_ERROR = 'Concurrent hardware approval requests are not allowed.';
  let pendingNonce = null;
  let transientApprovedDispatch = null;
  let statusElement = null;

  function updateStatus(message) {
    if (statusElement) {
      statusElement.textContent = message;
    }
  }

  function readCsrfToken() {
    const prefix = `${CSRF_COOKIE_NAME}=`;
    const entry = documentObject.cookie.split(';')
      .map((cookie) => cookie.trim())
      .find((cookie) => cookie.startsWith(prefix));
    if (!entry) return null;
    const value = entry.slice(prefix.length);
    if (!value) return null;
    try {
      return decodeURIComponent(value);
    } catch (_error) {
      return value;
    }
  }

  function isUnsafeSameOrigin(url, options) {
    const method = String(options.method || 'GET').toUpperCase();
    if (SAFE_METHODS.has(method)) return false;
    try {
      return new URL(url, windowObject.location.origin).origin === windowObject.location.origin;
    } catch (_error) {
      return false;
    }
  }

  function armNonce(value) {
    if (typeof value !== 'string' || !NONCE_PATTERN.test(value)) {
      pendingNonce = null;
      updateStatus('Hardware approval cleared: enter exactly 64 lowercase hexadecimal characters.');
      return false;
    }
    pendingNonce = value;
    updateStatus('Hardware approval armed for one mutation attempt.');
    return true;
  }

  function installControl() {
    const control = documentObject.createElement('form');
    control.setAttribute('aria-label', 'Hardware approval');
    control.style.cssText = 'margin:12px 0;padding:12px;border:1px solid #888;background:#fff;color:#111;display:flex;gap:8px;align-items:center;flex-wrap:wrap;';
    control.innerHTML = '<label for="hardware-approval-nonce">Hardware approval nonce</label><input id="hardware-approval-nonce" autocomplete="off" spellcheck="false"><button type="submit">Arm one mutation</button><button type="button">Clear approval</button><output aria-live="polite"></output>';
    const input = control.querySelector('input');
    const clearButton = control.querySelector('button[type="button"]');
    statusElement = control.querySelector('output');
    control.addEventListener('submit', (event) => {
      event.preventDefault();
      if (armNonce(input.value)) input.value = '';
    });
    clearButton.addEventListener('click', () => {
      pendingNonce = null;
      input.value = '';
      updateStatus('Hardware approval cleared.');
    });
    documentObject.body.insertBefore(control, documentObject.body.firstChild);
  }

  function queueApprovedRequest(url, requestOptions) {
    return new Promise((resolve, reject) => {
      const request = { url, requestOptions, resolve, reject };
      if (transientApprovedDispatch) {
        transientApprovedDispatch.requests.push(request);
        return;
      }

      const dispatch = { requests: [request] };
      transientApprovedDispatch = dispatch;
      Promise.resolve().then(() => {
        if (transientApprovedDispatch === dispatch) {
          transientApprovedDispatch = null;
        }

        if (dispatch.requests.length !== 1) {
          dispatch.requests.forEach(({ reject: rejectRequest }) => {
            rejectRequest(new Error(APPROVAL_CONCURRENCY_ERROR));
          });
          return;
        }

        try {
          dispatch.requests[0].resolve(windowObject.fetch(url, requestOptions));
        } catch (error) {
          dispatch.requests[0].reject(error);
        }
      });
    });
  }

  windowObject.hardwareApprovalFetch = function hardwareApprovalFetch(url, options = {}) {
    const unsafeSameOrigin = isUnsafeSameOrigin(url, options);
    const headers = new Headers(options.headers || {});
    const hadApprovalHeader = headers.has(APPROVAL_HEADER);
    headers.delete(APPROVAL_HEADER);
    let changedHeaders = hadApprovalHeader;

    if (unsafeSameOrigin) {
      const csrfToken = readCsrfToken();
      if (csrfToken) {
        headers.set(CSRF_HEADER, csrfToken);
        changedHeaders = true;
      }
      if (transientApprovedDispatch) {
        return queueApprovedRequest(url, changedHeaders ? { ...options, headers } : options);
      }
      if (pendingNonce) {
        const nonce = pendingNonce;
        pendingNonce = null;
        headers.set(APPROVAL_HEADER, nonce);
        changedHeaders = true;
        updateStatus('Hardware approval consumed by a mutation attempt.');
        return queueApprovedRequest(url, { ...options, headers });
      }
    }

    const requestOptions = changedHeaders ? { ...options, headers } : options;
    return windowObject.fetch(url, requestOptions);
  };

  installControl();
}(window, document));
