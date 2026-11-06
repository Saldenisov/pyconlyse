import { supervisionDiagnosticsClient, DIAGNOSTICS_READ_DEADLINE_MS } from './supervisionDiagnosticsClient';
import { clearHardwareApprovalNonce, getHardwareApprovalNonce, setHardwareApprovalNonce } from './csrfRequest';

const value = { schema_version: 1, execution_allowed: false, hardware_writes: false, cameras: [] };
const reply = (body = value, ok = true) => ({ ok, status: ok ? 200 : 503,
  headers: { get: () => null }, text: async () => JSON.stringify(body) });
beforeEach(() => { global.fetch = jest.fn().mockResolvedValue(reply()); });
afterEach(() => { delete global.fetch; jest.useRealTimers(); clearHardwareApprovalNonce(); });

test('GET uses authenticated same-origin facade and bounds camera identifier in query', async () => {
  await supervisionDiagnosticsClient.snapshot(undefined, 'ni1409:2');
  expect(fetch).toHaveBeenCalledWith('/api/elyse/supervision/diagnostics?camera_id=ni1409%3A2',
    expect.objectContaining({ method: 'GET', credentials: 'include', cache: 'no-store' }));
});

test('save sends exact observed identity/revision and CSRF without consuming hardware approval', async () => {
  document.cookie = 'csrf_access_token=diagnostics-test';
  setHardwareApprovalNonce('a'.repeat(64));
  const request = { camera_id: 'ni1409:2', frame_identity: 'source/capture/1/2', expected_revision: 0, radius_px: 8 };
  await supervisionDiagnosticsClient.saveReference(request);
  const [, options] = fetch.mock.calls[0];
  expect(options.method).toBe('POST');
  expect(JSON.parse(options.body)).toEqual(request);
  expect(options.headers['X-CSRF-TOKEN']).toBe('diagnostics-test');
  expect(options.headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBeUndefined();
  expect(getHardwareApprovalNonce()).toBe('a'.repeat(64));
});

test('physical execution contract or server persistence rejection is refused', async () => {
  fetch.mockResolvedValueOnce(reply({ ...value, execution_allowed: true }));
  await expect(supervisionDiagnosticsClient.snapshot()).rejects.toThrow('Contrat diagnostic incompatible');
  fetch.mockResolvedValueOnce(reply({ error: 'centre non enregistré' }, false));
  await expect(supervisionDiagnosticsClient.saveReference({})).rejects.toThrow('centre non enregistré');
});

test('deadline aborts stalled request, so no request can silently outlive five seconds', async () => {
  jest.useFakeTimers();
  fetch.mockImplementation(() => new Promise(() => {}));
  const pending = supervisionDiagnosticsClient.snapshot();
  const expected = expect(pending).rejects.toThrow('5 s');
  jest.advanceTimersByTime(DIAGNOSTICS_READ_DEADLINE_MS);
  await expected;
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});
