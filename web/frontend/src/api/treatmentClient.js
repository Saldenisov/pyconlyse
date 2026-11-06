import { withCsrfToken } from './csrfRequest';

const DEFAULT_TIMEOUT_MS = 30000;
const LONG_TREATMENT_TIMEOUT_MS = 120000;
export const TREATMENT_AUTH_MESSAGE = 'The server rejected the request (HTTP 401). Check that Pyconlyse is running in local mode.';

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
    const message = response.status === 401
      ? TREATMENT_AUTH_MESSAGE
      : payload?.error || payload?.msg || `Request failed with status ${response.status}.`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return payload;
}

async function requestTreatment(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, withCsrfToken(url, {
      ...options,
      signal: controller.signal,
    }));
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
    '/api/treatment/session/compress-file/start',
    '/api/treatment/session/folder-set/start',
    '/api/treatment/session/compress-path',
    '/api/treatment/session/auto-assign',
    '/api/treatment/session/folder-set',
    '/api/treatment/average-noise',
    '/api/treatment/calc-abs',
    '/api/treatment/cleaning/save',
    '/api/treatment/queue',
    '/api/treatment/queue/folder-set',
    '/api/treatment/queue/run',
    '/api/treatment/stitch/od',
    '/api/treatment/stitch/od/preview',
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

export function startCompressionJob(sessionId, filePath) {
  return postTreatment(sessionId, '/api/treatment/session/compress-file/start', {
    file_path: filePath,
  });
}

export function fetchCompressionJob(sessionId, jobId) {
  return requestTreatment(
    `/api/treatment/session/compress-file/status/${encodeURIComponent(jobId)}`,
    {
      headers: buildHeaders(sessionId),
    }
  );
}

export function startFolderSetJob(sessionId, payload) {
  return postTreatment(sessionId, '/api/treatment/session/folder-set/start', payload);
}

export function fetchFolderSetJob(sessionId, jobId) {
  return requestTreatment(
    `/api/treatment/session/folder-set/status/${encodeURIComponent(jobId)}`,
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

export function fetchTreatmentQueue(sessionId) {
  return requestTreatment('/api/treatment/queue', {
    headers: buildHeaders(sessionId),
  });
}

export function enqueueTreatmentRecipe(sessionId, payload) {
  return postTreatment(sessionId, '/api/treatment/queue', payload);
}

export function enqueueStandardFolderTreatment(sessionId, payload) {
  return postTreatment(sessionId, '/api/treatment/queue/folder-set', payload);
}

export function runTreatmentQueue(sessionId) {
  return postTreatment(sessionId, '/api/treatment/queue/run');
}

export function removeTreatmentQueueJob(sessionId, jobId) {
  return requestTreatment(`/api/treatment/queue/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
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

// SK-Ana operates on session memory. Cancellation aborts this HTTP exchange;
// cancelling an already-created numerical job is an explicit separate request.
async function requestSkana(sessionId, path, { signal, body, ...options } = {}, download = false) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel);
  if (signal?.aborted) controller.abort();
  let timedOut = false;
  const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, DEFAULT_TIMEOUT_MS);
  const url = `/api/treatment/skana${path}`;
  try {
    const response = await fetch(url, withCsrfToken(url, {
      credentials: 'same-origin', ...options,
      headers: buildHeaders(sessionId, body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: controller.signal,
    }));
    if (download && response.ok) return await response.blob();
    return await parseResponse(response);
  } catch (error) {
    if (timedOut) throw new Error('SK-Ana request timed out after 30 seconds. Check job status before starting another fit.');
    throw error;
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

export const fetchSkanaDataset = (sessionId, source = 'od', signal) => requestSkana(
  sessionId, `/dataset?source=${encodeURIComponent(source)}`, { signal });
export const importSkanaDataset = (sessionId, payload, signal) => requestSkana(
  sessionId, '/import', { method: 'POST', body: payload, signal });
export const startSkanaJob = (sessionId, payload, signal) => requestSkana(
  sessionId, '/jobs', { method: 'POST', body: payload, signal });
export const fetchSkanaJob = (sessionId, jobId, signal) => requestSkana(
  sessionId, `/jobs/${encodeURIComponent(jobId)}`, { signal });
export const cancelSkanaJob = (sessionId, jobId, signal) => requestSkana(
  sessionId, `/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST', body: {}, signal });
export const downloadSkanaResult = (sessionId, jobId, format = 'json', signal) => requestSkana(
  sessionId, `/jobs/${encodeURIComponent(jobId)}/export?format=${encodeURIComponent(format)}`, { signal }, true);
