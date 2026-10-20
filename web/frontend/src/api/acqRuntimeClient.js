import { fetchWithCsrfToken } from './csrfRequest';

export const ACQ_RUNTIME_URL = '/api/elyse/acquisition/runtime';
export const ACQ_RUNTIME_TIMEOUT_MS = 5000;
export const ACQ_RUNTIME_BANKS = [
  ['C1_NI6071E_AI', 64, 'analog_input'], ['C2_NI6071E_AI', 64, 'analog_input'],
  ['C11_NI6220_AI', 16, 'analog_input'], ['C3_DIO96_DI', 56, 'digital_input'],
  ['C4_DIO96_DI', 64, 'digital_input'], ['C5_DIO96_DI', 56, 'digital_input'],
];
const QUALITIES = new Set(['FRESH', 'STALE', 'UNAVAILABLE', 'INCOMPATIBLE', 'RECOVERY_REQUIRED', 'IDLE', 'EXECUTING', 'FAULT']);
const SESSION = /^[0-9a-f]{32}$/;
const BUILD = /^[0-9a-f]{64}$/;

function incompatible() {
  return new Error('Contrat Python Acquisition incompatible ; mesures masquées.');
}

// A different source or an unsafe contract must never inherit LabVIEW values.
export function validateAcqRuntime(payload) {
  if (!payload || payload.schema_version !== 1 || payload.source !== 'xp_python_acquisition_runtime'
      || payload.execution_allowed !== false || payload.hardware_writes !== false || !QUALITIES.has(payload.quality)) {
    throw incompatible();
  }
  if (['UNAVAILABLE', 'INCOMPATIBLE'].includes(payload.quality)) {
    return { ...payload, snapshot: null };
  }
  const raw = payload.snapshot?.runtime;
  if (!raw || raw.runtime_protocol_version !== 2 || !SESSION.test(raw.session_id || '')
      || !BUILD.test(raw.build_id || '') || raw.session_id !== payload.session_id || raw.build_id !== payload.build_id
      || !Number.isSafeInteger(raw.state_revision) || raw.state_revision < 0
      || !Number.isSafeInteger(payload.state_revision) || payload.state_revision < 0
      || raw.state_revision !== payload.state_revision
      || !raw.recovery || typeof raw.recovery.required !== 'boolean' || typeof raw.recovery.protection_active !== 'boolean'
      || typeof raw.recovery.reason !== 'string'
      || typeof payload.bridge_stale !== 'boolean' || typeof payload.source_stale !== 'boolean'
      || typeof raw.state !== 'string' || raw.state !== payload.runtime_state) {
    throw incompatible();
  }
  if (payload.quality === 'FRESH' && (payload.bridge_stale || payload.source_stale || raw.recovery.required
      || raw.state !== 'RUNNING' || !Number.isFinite(payload.bridge_age_seconds) || payload.bridge_age_seconds < 0
      || !Number.isFinite(payload.source_age_seconds) || payload.source_age_seconds < 0
      || !raw.latest || raw.latest.source !== 'python_daqmx_acquisition' || raw.latest.simulated !== false)) {
    throw incompatible();
  }
  if (payload.quality === 'FRESH' && !ACQ_RUNTIME_BANKS.every(([name, count, kind]) => {
    const bank = raw.latest.banks?.[name];
    return bank?.kind === kind && Array.isArray(bank.values) && bank.values.length === count
      && bank.values.every((value) => kind === 'digital_input' ? typeof value === 'boolean'
        : typeof value === 'number' && Number.isFinite(value));
  })) throw incompatible();
  return payload.quality === 'FRESH' ? payload : hideAcqRuntimeMeasurements(payload);
}

export function hideAcqRuntimeMeasurements(payload, quality = payload?.quality) {
  if (!payload) return null;
  return { ...payload, quality, snapshot: payload.snapshot ? { ...payload.snapshot, measurements_hidden: true,
    runtime: payload.snapshot.runtime ? { ...payload.snapshot.runtime, latest: null } : null } : null };
}

export function ageAcqRuntime(payload, elapsed) {
  if (!payload || payload.quality !== 'FRESH') return payload;
  const sourceLimit = Number.isFinite(payload.source_stale_after_seconds) && payload.source_stale_after_seconds > 0
    ? Math.min(2, payload.source_stale_after_seconds) : 2;
  const bridgeLimit = Number.isFinite(payload.bridge_stale_after_seconds) && payload.bridge_stale_after_seconds > 0
    ? Math.min(3, payload.bridge_stale_after_seconds) : 3;
  if (payload.source_age_seconds + elapsed >= sourceLimit || payload.bridge_age_seconds + elapsed >= bridgeLimit) {
    return hideAcqRuntimeMeasurements({ ...payload, source_stale: true }, 'STALE');
  }
  return payload;
}

function abortError() {
  const error = new Error('Lecture annulée.');
  error.name = 'AbortError';
  return error;
}

async function status(signal) {
  const startedAt = performance.now();
  const controller = new AbortController();
  let timeout;
  let cancel;
  const interrupted = new Promise((resolve, reject) => {
    cancel = () => { controller.abort(); reject(abortError()); };
    signal?.addEventListener('abort', cancel);
    if (signal?.aborted) cancel();
    timeout = setTimeout(() => {
      controller.abort();
      reject(new Error('Python Acquisition sans réponse après 5 s.'));
    }, ACQ_RUNTIME_TIMEOUT_MS);
  });
  const request = async () => {
    if (signal?.aborted) throw abortError();
    const response = await fetchWithCsrfToken(ACQ_RUNTIME_URL, {
      method: 'GET', credentials: 'include', cache: 'no-store', signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(response.status === 401 || response.status === 403
        ? 'Authentification PyConlyse requise.' : `Python Acquisition indisponible · HTTP ${response.status}.`);
    }
    const payload = validateAcqRuntime(await response.json());
    const elapsed = (performance.now() - startedAt) / 1000;
    if (!Number.isFinite(elapsed) || elapsed < 0) {
      throw new Error('Durée de transport Python Acquisition invalide ; mesures masquées.');
    }
    // Conservative HTTP + JSON allowance, not clock synchronization. Preserve
    // raw server fields; only the browser-facing envelope ages are extended.
    return ageAcqRuntime({ ...payload,
      source_age_seconds: Number.isFinite(payload.source_age_seconds) ? payload.source_age_seconds + elapsed : payload.source_age_seconds,
      bridge_age_seconds: Number.isFinite(payload.bridge_age_seconds) ? payload.bridge_age_seconds + elapsed : payload.bridge_age_seconds,
    }, 0);
  };
  try { return await Promise.race([request(), interrupted]); }
  finally { clearTimeout(timeout); signal?.removeEventListener('abort', cancel); }
}

export const acqRuntimeClient = Object.freeze({ status });
