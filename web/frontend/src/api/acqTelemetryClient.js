import { fetchWithHardwareApproval } from './csrfRequest';

// Both channels use the fixed web facade. No browser-side XP/NI/PSP path.
const CONTROL = '/api/elyse/acquisition/control';
const NONDISPATCHED_AUTHORIZATION = Object.freeze({
  403: 'hardware_not_authorized', 409: 'hardware_approval_invalid', 428: 'hardware_approval_required',
});
const validIdentity = (value) => typeof value?.session_id === 'string'
  && /^[0-9a-f]{32}$/.test(value.session_id) && Number.isSafeInteger(value.revision) && value.revision >= 0;

function validControl(value) {
  if (value?.schema_version !== 1 || typeof value.source_selected !== 'boolean'
    || !value.capabilities || typeof value.capabilities !== 'object' || Array.isArray(value.capabilities)
    || !Array.isArray(value.commands)) return false;
  if (value.source_selected && (value.mode !== 'XP_CONTROL' || !validIdentity(value))) return false;
  return Object.values(value.capabilities).every((item) => typeof item?.enabled === 'boolean' && typeof item.reason === 'string');
}

export const acqTelemetryClient = Object.freeze({
  async telemetry(signal) {
    const response = await fetch('/api/elyse/acquisition/telemetry', {
      method: 'GET', credentials: 'include', cache: 'no-store', signal,
    });
    const value = await response.json();
    if (!response.ok || value.schema_version !== 1 || !Array.isArray(value.expected_banks)) {
      throw new Error(value.error || 'Contrat de télémétrie Acquisition incompatible.');
    }
    return value;
  },
  async controlState(signal) {
    const response = await fetch(CONTROL, {
      method: 'GET', credentials: 'include', cache: 'no-store', signal,
    });
    const value = await response.json();
    if (!response.ok || !validControl(value)) {
      throw new Error(value.error || 'Contrat de commandes Acquisition incompatible.');
    }
    return value;
  },
  async command(command) {
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
      const nonDispatched = !response.ok && NONDISPATCHED_AUTHORIZATION[response.status] === value?.code
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
