import {
  fetchWithCsrfToken, getHardwareApprovalNonce, setHardwareApprovalNonce,
} from './csrfRequest';
import { CIRCULATION_CONFIRMATION, validCirculationConfirmationValue } from '../acquisitionCommandValue';

let mode = 'JWT_APPROVAL';

export function rememberAcquisitionApproval(view) {
  mode = view?.approval_mode === 'LOCAL_CONSOLE' ? 'LOCAL_CONSOLE' : 'JWT_APPROVAL';
}

export function usesLocalAcquisitionApproval() { return mode === 'LOCAL_CONSOLE'; }

// Called only by the explicit command-confirmation path. Polling never arms it.
export async function prepareAcquisitionApproval(command, signal) {
  if (mode !== 'LOCAL_CONSOLE') return null;
  try {
    if (command?.operation === CIRCULATION_CONFIRMATION && !validCirculationConfirmationValue(command.value)) {
      throw new Error('Incidents de refroidissement explicites et distincts requis.');
    }
    if (getHardwareApprovalNonce()) throw new Error('Une autre autorisation est déjà armée.');
    const response = await fetchWithCsrfToken('/api/elyse/acquisition/control/approvals', {
      method: 'POST', credentials: 'include', cache: 'no-store', signal,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(command),
    });
    const value = await response.json();
    if (!response.ok || value?.schema_version !== 1 || value.dispatch_attempted !== false
      || value.hardware_writes !== false || typeof value.nonce !== 'string'
      || !/^[0-9a-f]{64}$/.test(value.nonce)) {
      throw new Error(value?.error || 'Confirmation locale indisponible.');
    }
    if (!setHardwareApprovalNonce(value.nonce)) throw new Error('Autorisation locale invalide.');
    return null;
  } catch (error) {
    const message = error?.message || 'Confirmation locale indisponible.';
    // This endpoint never dispatches. Even a lost reply cannot actuate hardware.
    return { schema_version: 1, error: message, automatic_retry: false,
      receipt: { command_id: command.command_id, session_id: command.session_id,
        operation: command.operation, outcome: 'REJECTED', dispatch_attempted: false,
        hardware_acknowledged: false, automatic_retry: false, error: message } };
  }
}
