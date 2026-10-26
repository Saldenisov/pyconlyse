import { acqTelemetryClient, ACQUISITION_TOPOLOGY, READ_DEADLINE_MS } from './acqTelemetryClient';
import { clearHardwareApprovalNonce, getHardwareApprovalNonce, setHardwareApprovalNonce } from './csrfRequest';

afterEach(() => {
  delete global.fetch; clearHardwareApprovalNonce(); document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
});

test('only the fixed read-only standard-bank web route is used', async () => {
  const value = { schema_version: 1, expected_banks: ['C1NI6071E'] };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => value });
  const signal = new AbortController().signal;
  expect(await acqTelemetryClient.telemetry(signal)).toBe(value);
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/telemetry', {
    method: 'GET', credentials: 'include', cache: 'no-store', signal: expect.any(AbortSignal),
  });
});

test('a rejected or incompatible response is not displayed as fresh data', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, json: async () => ({ error: 'unavailable' }) });
  await expect(acqTelemetryClient.telemetry()).rejects.toThrow('unavailable');
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ schema_version: 0 }) });
  await expect(acqTelemetryClient.telemetry()).rejects.toThrow('incompatible');
});

const control = () => ({ schema_version: 1, mode: 'XP_CONTROL', source_selected: true,
  session_id: 'a'.repeat(32), revision: 7, capabilities: { 'ht_voltage.set': { enabled: true, reason: '' } }, commands: [] });
const command = () => ({ command_id: 'b'.repeat(32), session_id: 'a'.repeat(32), expected_revision: 7,
  operation: 'ht_voltage.set', operator_confirmed: true, value: 8.75 });
const receipt = (request) => ({ schema_version: 1, receipt: { command_id: request.command_id,
  session_id: request.session_id, operation: request.operation, outcome: 'QUEUED',
  hardware_acknowledged: false, automatic_retry: false } });
const authorizationRefusal = (request, code = 'hardware_approval_required') => ({ schema_version: 1,
  code, error: 'Hardware approval declined before dispatch', automatic_retry: false,
  receipt: { command_id: request.command_id, session_id: request.session_id, operation: request.operation,
    outcome: 'REJECTED', hardware_acknowledged: false, automatic_retry: false,
    dispatch_attempted: false, error: 'Hardware approval declined before dispatch' } });

test('water observation uses existing command facade with exact episode IDs', async () => {
  const request = { ...command(), operation: 'cooling.confirm_circulation', value: { incident_ids: ['1'.repeat(32)] } };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => receipt(request) });
  await acqTelemetryClient.command(request);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/elyse/acquisition/control/commands');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
});

test('invalid water observation neither transmits nor consumes an approval', async () => {
  global.fetch = jest.fn(); setHardwareApprovalNonce('c'.repeat(64));
  await expect(acqTelemetryClient.command({ ...command(), operation: 'cooling.confirm_circulation',
    value: { incident_ids: [] } })).rejects.toThrow('Incidents de refroidissement');
  expect(fetch).not.toHaveBeenCalled(); expect(getHardwareApprovalNonce()).toBe('c'.repeat(64));
});

test('structured synchronization preserves exact parameters and uses same command facade', async () => {
  const request = { ...command(), operation: 'counter_timing.set', value: { counter: 2, delay_us: 1.25, width_us: 3.5 } };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => receipt(request) });
  await acqTelemetryClient.command(request);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/elyse/acquisition/control/commands');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
});

test('invalid synchronization does not consume approval or transmit', async () => {
  global.fetch = jest.fn(); setHardwareApprovalNonce('c'.repeat(64));
  await expect(acqTelemetryClient.command({ ...command(), operation: 'counter_timing.set',
    value: { counter: 8, delay_us: 1, width_us: 2 } })).rejects.toThrow('Compteur C10');
  expect(fetch).not.toHaveBeenCalled();
  expect(getHardwareApprovalNonce()).toBe('c'.repeat(64));
});

test('a correlated first-attempt source-change refusal is known not dispatched, never retried', async () => {
  const request = command();
  const refused = authorizationRefusal(request, 'acquisition_pre_dispatch_rejected');
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 409, json: async () => refused });
  expect((await acqTelemetryClient.command(request)).receipt.outcome).toBe('REJECTED');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('control status uses fixed authenticated web GET, never a direct XP path', async () => {
  const value = control(), signal = new AbortController().signal;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => value });
  expect(await acqTelemetryClient.controlState(signal)).toBe(value);
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/control', {
    method: 'GET', credentials: 'include', cache: 'no-store', signal: expect.any(AbortSignal),
  });
});

test.each([
  { ...control(), source_selected: 'yes' }, { ...control(), session_id: 'old' },
  { ...control(), revision: 1.1 }, { ...control(), capabilities: [] },
  { ...control(), capabilities: { 'ht_voltage.set': { enabled: 'yes', reason: '' } } },
])('malformed or incompatible control state fails closed', async (value) => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => value });
  await expect(acqTelemetryClient.controlState()).rejects.toThrow('incompatible');
});

test('legacy read-only status and missing unqualified beamline capabilities remain representable', async () => {
  const value = { schema_version: 1, mode: 'LABVIEW_READ_ONLY', source_selected: false, capabilities: {}, commands: [] };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => value });
  expect(await acqTelemetryClient.controlState()).toEqual(value);
});

test.each([
  { ...control(), source_mode: 'LABVIEW_BRIDGE' },
  { ...control(), source_mode: 'other-server' },
  { ...control(), topology: { ...ACQUISITION_TOPOLOGY, tango_device: 'other/acq/control' } },
  { ...control(), topology: { ...ACQUISITION_TOPOLOGY, remote_initialization_enabled: true } },
])('incompatible single-device source/topology cannot grant control', async (value) => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => value });
  await expect(acqTelemetryClient.controlState()).rejects.toThrow('incompatible');
});

test.each(['telemetry', 'controlState', 'coolingSafety'])('hung %s read has bounded deadline and a subsequent explicit read can recover', async (method) => {
  jest.useFakeTimers();
  try {
    global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
    const pending = acqTelemetryClient[method]().catch((error) => error);
    jest.advanceTimersByTime(READ_DEADLINE_MS);
    expect((await pending).message).toContain('5 s');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    const value = method === 'controlState' ? control() : method === 'telemetry'
      ? { schema_version: 1, expected_banks: [] }
      : { schema_version: 1, execution_allowed: false, hardware_writes: false, cooling_safety: { schema_version: 1 } };
    fetch.mockResolvedValue({ ok: true, json: async () => value });
    expect(await acqTelemetryClient[method]()).toEqual(value);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
  } finally { jest.useRealTimers(); }
});

test('read cancellation propagates without consuming an armed actuation approval', async () => {
  setHardwareApprovalNonce('c'.repeat(64));
  const external = new AbortController();
  global.fetch = jest.fn().mockImplementation((url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')));
  }));
  const pending = acqTelemetryClient.telemetry(external.signal).catch((error) => error);
  external.abort();
  expect((await pending).name).toBe('AbortError');
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  const request = command();
  fetch.mockResolvedValue({ ok: true, json: async () => receipt(request) });
  await acqTelemetryClient.command(request);
  expect(fetch.mock.calls[1][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe('c'.repeat(64));
});

test('a read deadline includes a hung JSON body and an already cancelled read is never sent', async () => {
  jest.useFakeTimers();
  try {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => new Promise(() => {}) });
    const pending = acqTelemetryClient.controlState().catch((error) => error);
    jest.advanceTimersByTime(READ_DEADLINE_MS);
    expect((await pending).message).toContain('5 s');
    const cancelled = new AbortController(); cancelled.abort();
    await expect(acqTelemetryClient.controlState(cancelled.signal)).rejects.toHaveProperty('name', 'AbortError');
    expect(fetch).toHaveBeenCalledTimes(1);
  } finally { jest.useRealTimers(); }
});

test('explicit HT command preserves numeric value, cookie CSRF and operator-armed approval', async () => {
  document.cookie = 'csrf_access_token=csrf-test; path=/';
  setHardwareApprovalNonce('c'.repeat(64));
  const request = command();
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => receipt(request) });
  expect((await acqTelemetryClient.command(request)).receipt.outcome).toBe('QUEUED');
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/control/commands', {
    method: 'POST', credentials: 'include', cache: 'no-store', body: JSON.stringify(request), signal: expect.any(AbortSignal),
    headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': 'csrf-test',
      'X-PYCONLYSE-HARDWARE-APPROVAL': 'c'.repeat(64) },
  });
  expect(JSON.parse(fetch.mock.calls[0][1].body).value).toBe(8.75);
});

test.each([null, undefined, '', '8', NaN, Infinity, -1, 21])('invalid HT value is rejected before any POST: %s', async (value) => {
  global.fetch = jest.fn();
  await expect(acqTelemetryClient.command({ ...command(), value })).rejects.toThrow('explicite et finie');
  expect(fetch).not.toHaveBeenCalled();
});

test('uncertain or incompatible response never retries a command', async () => {
  const request = command(), wrong = receipt(request);
  wrong.receipt.command_id = 'd'.repeat(32);
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => wrong });
  await expect(acqTelemetryClient.command(request)).rejects.toThrow('incompatible ou non confirmé');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('10 s command deadline aborts transport, retains exact numeric intent and never retries', async () => {
  jest.useFakeTimers();
  try {
    const request = command();
    global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
    const pending = acqTelemetryClient.command(request).catch((error) => error);
    jest.advanceTimersByTime(10000);
    const error = await pending;
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toContain('UNKNOWN, pas une annulation Acquisition');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
    jest.advanceTimersByTime(60000);
    expect(fetch).toHaveBeenCalledTimes(1);
  } finally { jest.useRealTimers(); }
});

test.each([[403, 'hardware_not_authorized'], [409, 'hardware_approval_invalid'], [428, 'hardware_approval_required']])(
  'only exact correlated nondispatched authorization proof is accepted for HTTP %s/%s', async (status, code) => {
    const request = command(), value = authorizationRefusal(request, code);
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status, json: async () => value });
    expect(await acqTelemetryClient.command(request)).toBe(value);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

test.each([
  ['generic400', 400, (value) => value], ['generic401', 401, (value) => value],
  ['server500', 500, (value) => value], ['generic409', 409, (value) => ({ ...value, code: 'revision_changed' })],
  ['wrong status/code pair', 409, (value) => value],
  ['unknown hardware code', 428, (value) => ({ ...value, code: 'hardware_approval_expired' })],
  ['wrong schema', 428, (value) => ({ ...value, schema_version: 0 })],
  ['missing top retry proof', 428, (value) => ({ ...value, automatic_retry: undefined })],
  ['top retry true', 428, (value) => ({ ...value, automatic_retry: true })],
  ['missing dispatch proof', 428, (value) => ({ ...value, receipt: { ...value.receipt, dispatch_attempted: undefined } })],
  ['dispatch already attempted', 428, (value) => ({ ...value, receipt: { ...value.receipt, dispatch_attempted: true } })],
  ['uncertain outcome', 428, (value) => ({ ...value, receipt: { ...value.receipt, outcome: 'INDETERMINATE' } })],
  ['queued outcome', 428, (value) => ({ ...value, receipt: { ...value.receipt, outcome: 'QUEUED' } })],
  ['different command ID', 428, (value) => ({ ...value, receipt: { ...value.receipt, command_id: 'd'.repeat(32) } })],
  ['different session', 428, (value) => ({ ...value, receipt: { ...value.receipt, session_id: 'd'.repeat(32) } })],
  ['different operation', 428, (value) => ({ ...value, receipt: { ...value.receipt, operation: 'modulator.general.stop' } })],
  ['missing hardware proof', 428, (value) => ({ ...value, receipt: { ...value.receipt, hardware_acknowledged: undefined } })],
  ['hardware acknowledgement true', 428, (value) => ({ ...value, receipt: { ...value.receipt, hardware_acknowledged: true } })],
  ['missing receipt retry proof', 428, (value) => ({ ...value, receipt: { ...value.receipt, automatic_retry: undefined } })],
  ['receipt retry true', 428, (value) => ({ ...value, receipt: { ...value.receipt, automatic_retry: true } })],
  ['different error proof', 428, (value) => ({ ...value, receipt: { ...value.receipt, error: 'Another error' } })],
  ['missing receipt', 428, (value) => ({ ...value, receipt: undefined })],
])('non2xx never reconciles a missing or mismatched proof: %s', async (_name, status, mutate) => {
  const request = command(), value = mutate(authorizationRefusal(request));
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status, json: async () => value });
  await expect(acqTelemetryClient.command(request)).rejects.toThrow();
  expect(fetch).toHaveBeenCalledTimes(1);
});
