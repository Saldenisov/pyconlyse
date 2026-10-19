import { fetchWithCsrfToken } from './csrfRequest';

const ROOT = '/api/elyse/supervision';

async function request(url, options) {
  const controller = new AbortController();
  const externalSignal = options?.signal;
  const cancel = () => controller.abort();
  externalSignal?.addEventListener('abort', cancel);
  if (externalSignal?.aborted) controller.abort();
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
  try {
    const response = await fetchWithCsrfToken(url, { credentials: 'include', ...options, signal: controller.signal });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(response.status === 401
        ? 'Authentification PyConlyse requise.'
        : payload.error || `HTTP ${response.status}`);
    }
    if (payload.execution_allowed !== false || payload.schema_version !== 1) {
      throw new Error('Contrat SuperVision incompatible : aucune commande autorisée.');
    }
    return payload;
  } catch (error) {
    if (timedOut) throw new Error('Backend SuperVision sans réponse après 15 s.');
    throw error;
  } finally {
    clearTimeout(timeout);
    externalSignal?.removeEventListener('abort', cancel);
  }
}

export const elyseSupervisionClient = {
  telemetry: (signal) => request('/api/elyse/acquisition/telemetry', { signal }),
  snapshot: (signal) => request(ROOT, { signal }),
  business: (signal) => request(`${ROOT}/business`, { signal }),
  intentTrace: (intentId, signal) => request(`${ROOT}/business/intents/${encodeURIComponent(intentId)}/trace`, { signal }),
  stageIntent: (intent, signal) => request(`${ROOT}/business/intents`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(intent),
  }),
  submitIntent: (intentId, expectedRevision, signal) => request(`${ROOT}/business/intents/${encodeURIComponent(intentId)}/submit`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_revision: expectedRevision }),
  }),
  replay: (operation, inputs, signal) => request(`${ROOT}/replay`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operation, inputs }),
  }),
};
