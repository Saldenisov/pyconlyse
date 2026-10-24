import { elyseSupervisionClient } from './elyseSupervisionClient';
import { acqTelemetryClient } from './acqTelemetryClient';
import { setHardwareApprovalNonce, clearHardwareApprovalNonce } from './csrfRequest';

afterEach(() => { delete global.fetch; clearHardwareApprovalNonce(); });

test('the existing rich panels use exactly the canonical Acquisition methods, not a second command transport', () => {
  ['telemetry', 'controlState', 'command', 'coolingSafety'].forEach((name) => {
    expect(elyseSupervisionClient[name]).toBe(acqTelemetryClient[name]);
  });
});

test('compatibility command carries approval once and never falls back to Supervision or XP', async () => {
  const request = { command_id: 'b'.repeat(32), session_id: 'a'.repeat(32), expected_revision: 2,
    operation: 'prema.start', value: null, operator_confirmed: true };
  setHardwareApprovalNonce('c'.repeat(64));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ schema_version: 1,
    receipt: { ...request, outcome: 'QUEUED', automatic_retry: false, hardware_acknowledged: false } }) });
  expect((await elyseSupervisionClient.command(request)).receipt.outcome).toBe('QUEUED');
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/elyse/acquisition/control/commands');
  expect(fetch.mock.calls[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe('c'.repeat(64));
});

test('a Supervision preview result is never promoted to hardware execution or Acquisition fallback', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ schema_version: 1, execution_allowed: true }) });
  await expect(elyseSupervisionClient.replay('page_command', {})).rejects.toThrow('aucune commande autorisée');
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/elyse/supervision/replay');
});

test.each(['stageIntent', 'submitIntent'])('retired %s dispatch never sends a legacy request', async (method) => {
  global.fetch = jest.fn();
  await expect(elyseSupervisionClient[method]({ operation: 'General Marche' })).rejects.toThrow('désactivée');
  expect(fetch).not.toHaveBeenCalled();
});
