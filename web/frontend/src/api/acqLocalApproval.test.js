import { prepareAcquisitionApproval, rememberAcquisitionApproval } from './acqLocalApproval';
import { clearHardwareApprovalNonce, getHardwareApprovalNonce } from './csrfRequest';

const command = { command_id: 'b'.repeat(32), session_id: 'a'.repeat(32),
  expected_revision: 3, operation: 'modulator.general.start', operator_confirmed: true, value: null };

afterEach(() => {
  delete global.fetch; clearHardwareApprovalNonce(); rememberAcquisitionApproval({});
});

test('normal JWT path does not issue a local approval or arm a nonce', async () => {
  global.fetch = jest.fn();
  expect(await prepareAcquisitionApproval(command)).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
  expect(getHardwareApprovalNonce()).toBeNull();
});

test('local console issues exactly one approval for the unchanged command after confirmation', async () => {
  rememberAcquisitionApproval({ approval_mode: 'LOCAL_CONSOLE' });
  expect(getHardwareApprovalNonce()).toBeNull();
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({
    schema_version: 1, nonce: 'c'.repeat(64), dispatch_attempted: false, hardware_writes: false,
  }) });
  expect(await prepareAcquisitionApproval(command)).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(command);
  expect(getHardwareApprovalNonce()).toBe('c'.repeat(64));
});

test('lost approval response is a known non-dispatch rejection and never retried', async () => {
  rememberAcquisitionApproval({ approval_mode: 'LOCAL_CONSOLE' });
  global.fetch = jest.fn().mockRejectedValue(new Error('offline'));
  const value = await prepareAcquisitionApproval(command);
  expect(value.receipt).toMatchObject({ command_id: command.command_id, outcome: 'REJECTED',
    dispatch_attempted: false, automatic_retry: false, hardware_acknowledged: false });
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(getHardwareApprovalNonce()).toBeNull();
});

test('local water confirmation approval binds the unchanged incident IDs', async () => {
  rememberAcquisitionApproval({ approval_mode: 'LOCAL_CONSOLE' });
  const request = { ...command, operation: 'cooling.confirm_circulation', value: { incident_ids: ['1'.repeat(32)] } };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({
    schema_version: 1, nonce: 'c'.repeat(64), dispatch_attempted: false, hardware_writes: false,
  }) });
  expect(await prepareAcquisitionApproval(request)).toBeNull();
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
  expect(getHardwareApprovalNonce()).toBe('c'.repeat(64));
});

test('invalid local water confirmation cannot create an approval', async () => {
  rememberAcquisitionApproval({ approval_mode: 'LOCAL_CONSOLE' }); global.fetch = jest.fn();
  const rejected = await prepareAcquisitionApproval({ ...command, operation: 'cooling.confirm_circulation', value: { incident_ids: [] } });
  expect(rejected.receipt.dispatch_attempted).toBe(false);
  expect(fetch).not.toHaveBeenCalled(); expect(getHardwareApprovalNonce()).toBeNull();
});
