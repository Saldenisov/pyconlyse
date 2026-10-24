// Compatibility for the existing rich ELYSE panels. Only inert preview/UI
// models retain the Supervision namespace. All Acquisition I/O delegates to
// the same canonical client, including approval and UNKNOWN-result handling.
import { fetchWithCsrfToken } from './csrfRequest';
import { acqTelemetryClient } from './acqTelemetryClient';

const ROOT = '/api/elyse/supervision';

async function retiredDispatcher() {
  throw new Error('Ancienne commande Supervision désactivée. Utiliser les commandes nommées Acquisition via Tango.');
}

async function previewRequest(url, options) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  options?.signal?.addEventListener('abort', cancel);
  if (options?.signal?.aborted) controller.abort();
  const timer = setTimeout(cancel, 15000);
  try {
    const response = await fetchWithCsrfToken(url, {
      credentials: 'include', ...options, signal: controller.signal,
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value?.error || `HTTP ${response.status}`);
    if (value?.schema_version !== 1 || value.execution_allowed !== false) {
      throw new Error('Modèle Supervision incompatible : aucune commande autorisée.');
    }
    return value;
  } finally { clearTimeout(timer); options?.signal?.removeEventListener('abort', cancel); }
}

export const elyseSupervisionClient = Object.freeze({
  telemetry: acqTelemetryClient.telemetry,
  controlState: acqTelemetryClient.controlState,
  command: acqTelemetryClient.command,
  coolingSafety: acqTelemetryClient.coolingSafety,
  history: (minutes, signal) => previewRequest(`${ROOT}/workspace/history?minutes=${encodeURIComponent(minutes)}`, { signal }),
  synchronizationDraft: (signal) => previewRequest(`${ROOT}/workspace/synchronization`, { signal }),
  saveSynchronizationDraft: (values, expectedRevision, signal) => previewRequest(`${ROOT}/workspace/synchronization`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values, expected_revision: expectedRevision }),
  }),
  snapshot: (signal) => previewRequest(ROOT, { signal }),
  business: (signal) => previewRequest(`${ROOT}/business`, { signal }),
  intentTrace: (intentId, signal) => previewRequest(`${ROOT}/business/intents/${encodeURIComponent(intentId)}/trace`, { signal }),
  stageIntent: retiredDispatcher,
  submitIntent: retiredDispatcher,
  replay: (operation, inputs, signal) => previewRequest(`${ROOT}/replay`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation, inputs }),
  }),
});
