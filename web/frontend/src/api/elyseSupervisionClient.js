import { fetchWithCsrfToken, fetchWithHardwareApproval } from './csrfRequest';
import { rememberAcquisitionApproval, prepareAcquisitionApproval, usesLocalAcquisitionApproval } from './acqLocalApproval';

const ROOT = '/api/elyse/supervision';

async function controlRequest(path, options) {
  const abort = new AbortController();
  const cancel = () => abort.abort();
  options?.signal?.addEventListener('abort', cancel);
  if (options?.signal?.aborted) abort.abort();
  const timeout = setTimeout(cancel, 10000);
  try {
    const exchange = path === '/commands' ? fetchWithHardwareApproval : fetchWithCsrfToken;
    const response = await exchange(`/api/elyse/acquisition/control${path}`, {
      credentials: 'include', ...options, signal: abort.signal,
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
    if (value.schema_version !== 1 || (path === '' && (value.mode !== 'XP_CONTROL'
      || typeof value.capabilities !== 'object'))) throw new Error('Contrat commandes Python incompatible.');
    if (path !== '' && (!value.receipt || value.receipt.hardware_acknowledged !== false)) {
      throw new Error('Résultat Acquisition non qualifié ; ne pas renvoyer.');
    }
    if (path === '') rememberAcquisitionApproval(value);
    return value;
  } finally { clearTimeout(timeout); options?.signal?.removeEventListener('abort', cancel); }
}

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
  controlState: (signal) => controlRequest('', { signal }),
  command: async (command) => {
    if (usesLocalAcquisitionApproval()) {
      const abort = new AbortController();
      const timer = setTimeout(() => abort.abort(), 5000);
      let refused;
      try { refused = await prepareAcquisitionApproval(command, abort.signal); }
      finally { clearTimeout(timer); }
      if (refused) return refused;
      if (abort.signal.aborted) throw new Error('Confirmation interrompue avant envoi.');
    }
    return controlRequest('/commands', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(command) });
  },
  history: (minutes, signal) => request(`${ROOT}/workspace/history?minutes=${encodeURIComponent(minutes)}`, { signal }),
  errorJournal: ({ day = '', cursor = '' } = {}, signal) => request(
    `${ROOT}/workspace/errors?${new URLSearchParams({ day, cursor, limit: '100' })}`, { signal }),
  synchronizationDraft: (signal) => request(`${ROOT}/workspace/synchronization`, { signal }),
  saveSynchronizationDraft: (values, expectedRevision, signal) => request(`${ROOT}/workspace/synchronization`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values, expected_revision: expectedRevision }),
  }),
  coolingSafety: (signal) => request('/api/elyse/acquisition/telemetry/cooling', { signal }),
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
