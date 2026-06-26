const DEFAULT_TIMEOUT_MS = 30000;
const LONG_TREATMENT_TIMEOUT_MS = 120000;

function buildHeaders(sessionId, baseHeaders = {}) {
  const headers = { ...baseHeaders };
  if (sessionId) {
    headers['X-Treatment-Session-Id'] = sessionId;
  }
  return headers;
}

async function parseResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }

  if (!response.ok || payload?.success === false) {
    const message = payload?.error || `Request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return payload;
}

async function requestTreatment(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return parseResponse(response);
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutMs / 1000} seconds.`);
    }
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error(`Failed to fetch ${url}. Check backend connection.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export function fetchTreatmentSession(sessionId) {
  return requestTreatment('/api/treatment/session', {
    headers: buildHeaders(sessionId),
  });
}

export function postTreatment(sessionId, url, body = {}) {
  const timeoutMs = [
    '/api/treatment/session/cache-path',
    '/api/treatment/session/compress-file',
    '/api/treatment/session/compress-path',
    '/api/treatment/session/auto-assign',
    '/api/treatment/session/folder-set',
    '/api/treatment/average-noise',
    '/api/treatment/calc-abs',
    '/api/treatment/cleaning/save',
    '/api/treatment/save',
  ].includes(url)
    ? LONG_TREATMENT_TIMEOUT_MS
    : DEFAULT_TIMEOUT_MS;

  return requestTreatment(
    url,
    {
      method: 'POST',
      headers: buildHeaders(sessionId, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    },
    timeoutMs
  );
}

export function fetchFolderListing(sessionId, folderPath) {
  return requestTreatment(
    `/api/treatment/files?folder=${encodeURIComponent(folderPath)}`,
    {
      headers: buildHeaders(sessionId),
    }
  );
}

export function fetchTreatmentPreview(sessionId, dataType) {
  return requestTreatment(
    `/api/treatment/preview?data_type=${encodeURIComponent(dataType)}&map_index=0`,
    {
      headers: buildHeaders(sessionId),
    }
  );
}

export function fetchFileSummary(sessionId, filePath) {
  return requestTreatment(
    `/api/treatment/file-summary?file_path=${encodeURIComponent(filePath)}`,
    {
      headers: buildHeaders(sessionId),
    },
    LONG_TREATMENT_TIMEOUT_MS
  );
}

export function fetchSelection(sessionId) {
  return requestTreatment('/api/treatment/selection', {
    headers: buildHeaders(sessionId),
  });
}

export function fetchCleaningView(sessionId) {
  return requestTreatment('/api/treatment/cleaning/view', {
    headers: buildHeaders(sessionId),
  });
}

export function updateSelectionConfig(sessionId, payload) {
  return requestTreatment('/api/treatment/session/selection', {
    method: 'POST',
    headers: buildHeaders(sessionId, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });
}
