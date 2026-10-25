import { fetchWithHardwareApproval } from './csrfRequest';
import { validSyncValue } from '../acquisitionCommandValue';

// Both channels use the fixed web facade. No browser-side XP/NI/PSP path.
const CONTROL = '/api/elyse/acquisition/control';
const TELEMETRY = '/api/elyse/acquisition/telemetry';
export const ACQUISITION_TOPOLOGY = Object.freeze({
  xp_host: '10.20.30.10', tango_device: 'elyse/acquisition/telemetry',
  telemetry_and_commands_same_device: true, remote_initialization_enabled: false,
});
export const READ_DEADLINE_MS = 5000;
const NONDISPATCHED_CODES = Object.freeze({
  403: ['hardware_not_authorized'],
  409: ['hardware_approval_invalid', 'acquisition_pre_dispatch_rejected'],
  428: ['hardware_approval_required'],
});
const validIdentity = (value) => typeof value?.session_id === 'string'
  && /^[0-9a-f]{32}$/.test(value.session_id) && Number.isSafeInteger(value.revision) && value.revision >= 0;

function validControl(value) {
  if (value?.schema_version !== 1 || typeof value.source_selected !== 'boolean'
    || !value.capabilities || typeof value.capabilities !== 'object' || Array.isArray(value.capabilities)
    || !Array.isArray(value.commands)) return false;
  if (value.source_selected && (value.mode !== 'XP_CONTROL' || !validIdentity(value))) return false;
  if (value.source_mode !== undefined && !['PYTHON_NATIVE', 'LABVIEW_BRIDGE', 'TRANSITION_OR_FAULT', 'UNKNOWN'].includes(value.source_mode)) return false;
  if (value.source_selected && value.source_mode !== undefined && value.source_mode !== 'PYTHON_NATIVE') return false;
  if (value.topology !== undefined && Object.entries(ACQUISITION_TOPOLOGY)
    .some(([key, expected]) => value.topology?.[key] !== expected)) return false;
  return Object.values(value.capabilities).every((item) => typeof item?.enabled === 'boolean' && typeof item.reason === 'string');
}

// A timed-out READ may be polled again. A timed-out command is NEVER retried.
// The deadline includes JSON decoding, not only receipt of response headers.
async function readJson(url, signal) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal?.aborted) throw new DOMException('Read cancelled', 'AbortError');
  signal?.addEventListener('abort', cancel);
  let timeout;
  const deadline = new Promise((resolve, reject) => {
    timeout = setTimeout(() => {
      controller.abort();
      reject(new Error('Lecture Acquisition sans réponse après 5 s.'));
    }, READ_DEADLINE_MS);
  });
  const exchange = async () => {
    const response = await fetch(url, {
      method: 'GET', credentials: 'include', cache: 'no-store', signal: controller.signal,
    });
    return { response, value: await response.json() };
  };
  try { return await Promise.race([exchange(), deadline]); }
  finally { clearTimeout(timeout); signal?.removeEventListener('abort', cancel); }
}

export const acqTelemetryClient = Object.freeze({
  async telemetry(signal) {
    const { response, value } = await readJson(TELEMETRY, signal);
    if (!response.ok || value.schema_version !== 1 || !Array.isArray(value.expected_banks)) {
      throw new Error(value.error || 'Contrat de télémétrie Acquisition incompatible.');
    }
    return value;
  },
  async controlState(signal) {
    const { response, value } = await readJson(CONTROL, signal);
    if (!response.ok || !validControl(value)) {
      throw new Error(value.error || 'Contrat de commandes Acquisition incompatible.');
    }
    return value;
  },
  async coolingSafety(signal) {
    const { response, value } = await readJson(`${TELEMETRY}/cooling`, signal);
    if (!response.ok || value?.schema_version !== 1 || value.execution_allowed !== false
      || value.hardware_writes !== false || value.cooling_safety?.schema_version !== 1) {
      throw new Error(value?.error || 'Alarme refroidissement Acquisition indisponible.');
    }
    return value;
  },
  async command(command) {
    if (command?.operation === 'counter_timing.set' && !validSyncValue(command.value)) {
      throw new Error('Compteur C10, délai et largeur explicites et valides requis.');
    }
    if (command?.operation === 'ht_voltage.set' && (typeof command.value !== 'number'
      || !Number.isFinite(command.value) || command.value < 0 || command.value > 20)) {
      throw new Error('Consigne HT explicite et finie de 0 à 20 kV requise.');
    }
    const controller = new AbortController();
    let timeout;
    const deadline = new Promise((resolve, reject) => {
      timeout = setTimeout(() => {
        controller.abort();
        reject(new Error('Délai de réponse dépassé (10 s) : résultat UNKNOWN, pas une annulation Acquisition.'));
      }, 10000);
    });
    const exchange = async () => {
      const response = await fetchWithHardwareApproval(`${CONTROL}/commands`, {
        method: 'POST', credentials: 'include', cache: 'no-store', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(command),
      });
      const value = await response.json();
      const nonDispatched = !response.ok && NONDISPATCHED_CODES[response.status]?.includes(value?.code)
        && value?.automatic_retry === false && value?.receipt?.outcome === 'REJECTED'
        && value?.receipt?.dispatch_attempted === false && typeof value?.error === 'string'
        && value.error.length > 0 && value.receipt.error === value.error;
      if ((!response.ok && !nonDispatched) || value?.schema_version !== 1 || !value.receipt
        || value.receipt.command_id !== command.command_id || value.receipt.session_id !== command.session_id
        || value.receipt.operation !== command.operation
        || !['QUEUED', 'EXECUTING', 'COMPLETED', 'FAILED', 'REJECTED', 'INTERRUPTED', 'INDETERMINATE'].includes(value.receipt.outcome)
        || value.receipt.hardware_acknowledged !== false || value.receipt.automatic_retry !== false) {
        throw new Error(value?.error || 'Accusé de commande Acquisition incompatible ou non confirmé.');
      }
      return value;
    };
    try { return await Promise.race([exchange(), deadline]); }
    finally { clearTimeout(timeout); }
  },
});
