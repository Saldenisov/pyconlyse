import { fetchWithCsrfToken } from './csrfRequest';

const ROOT = '/api/elyse/supervision/diagnostics';
export const DIAGNOSTICS_READ_DEADLINE_MS = 5000;
const MAX_JSON_CHARS = 512 * 1024;

async function exchange(path, options = {}) {
  const controller = new AbortController();
  let timer;
  let cancel;
  if (options.signal?.aborted) throw new DOMException('Lecture annulée', 'AbortError');
  const cancelled = new Promise((resolve, reject) => {
    cancel = () => {
      controller.abort();
      reject(new DOMException('Lecture annulée', 'AbortError'));
    };
    options.signal?.addEventListener('abort', cancel, { once: true });
  });
  const deadline = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error('Diagnostic sans réponse après 5 s.'));
    }, DIAGNOSTICS_READ_DEADLINE_MS);
  });
  const request = async () => {
    const response = await fetchWithCsrfToken(`${ROOT}${path}`, {
      method: 'GET', credentials: 'include', cache: 'no-store', ...options,
      signal: controller.signal,
    });
    const length = Number(response.headers?.get('Content-Length'));
    if (Number.isFinite(length) && length > MAX_JSON_CHARS) throw new Error('Diagnostic trop volumineux.');
    const text = await response.text();
    if (typeof text !== 'string' || text.length > MAX_JSON_CHARS) throw new Error('Diagnostic trop volumineux.');
    const value = JSON.parse(text);
    if (!response.ok) throw new Error(value?.error || `Diagnostic indisponible (HTTP ${response.status}).`);
    if (value?.schema_version !== 1 || value.execution_allowed !== false
      || value.hardware_writes !== false || !Array.isArray(value.cameras)) {
      throw new Error('Contrat diagnostic incompatible.');
    }
    return value;
  };
  try { return await Promise.race([request(), deadline, cancelled]); }
  finally { clearTimeout(timer); options.signal?.removeEventListener('abort', cancel); }
}

export const supervisionDiagnosticsClient = Object.freeze({
  snapshot: (signal, cameraId) => exchange(cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : '', { signal }),
  saveReference: (value, signal) => exchange('/reference', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value),
  }),
  setMode: (value, signal) => exchange('/mode', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value),
  }),
});
