import { acqRuntimeClient, ACQ_RUNTIME_URL, ACQ_RUNTIME_BANKS, ageAcqRuntime, validateAcqRuntime } from './acqRuntimeClient';

function payload() {
  return { schema_version: 1, source: 'xp_python_acquisition_runtime', execution_allowed: false, hardware_writes: false,
    quality: 'FRESH', session_id: 'a'.repeat(32), build_id: 'b'.repeat(64), runtime_state: 'RUNNING', state_revision: 0,
    bridge_stale: false, bridge_age_seconds: 0.1, source_stale: false, source_age_seconds: 0.2,
    source_stale_after_seconds: 2, bridge_stale_after_seconds: 3,
    snapshot: { runtime: { runtime_protocol_version: 2, session_id: 'a'.repeat(32), build_id: 'b'.repeat(64),
      state_revision: 0, state: 'RUNNING', recovery: { required: false, reason: '', protection_active: false },
      latest: { source: 'python_daqmx_acquisition', simulated: false,
        banks: Object.fromEntries(ACQ_RUNTIME_BANKS.map(([name, count, kind]) => [name, {
          kind, values: Array(count).fill(kind === 'digital_input' ? false : 0),
        }])) } } } };
}
beforeEach(() => { jest.useFakeTimers(); global.fetch = jest.fn(); });
afterEach(() => { jest.useRealTimers(); jest.restoreAllMocks(); delete global.fetch; });

test('uses only authenticated same-origin read-only endpoint, no cached transport', async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => payload() });
  expect((await acqRuntimeClient.status()).quality).toBe('FRESH');
  expect(global.fetch).toHaveBeenCalledWith(ACQ_RUNTIME_URL,
    expect.objectContaining({ method: 'GET', credentials: 'include', cache: 'no-store' }));
  expect(global.fetch.mock.calls[0][1].headers).toBeUndefined();
});

test.each([401, 403])('fails closed on HTTP %s authentication failure', async (status) => {
  global.fetch.mockResolvedValue({ ok: false, status });
  await expect(acqRuntimeClient.status()).rejects.toThrow('Authentification PyConlyse requise.');
});

test('fails closed on HTTP failure without importing older LabVIEW measurements', async () => {
  global.fetch.mockResolvedValue({ ok: false, status: 503 });
  await expect(acqRuntimeClient.status()).rejects.toThrow('HTTP 503');
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test.each([
  ['wrong source', (data) => { data.source = 'labview'; }],
  ['commands allowed', (data) => { data.execution_allowed = true; }],
  ['writes allowed', (data) => { data.hardware_writes = true; }],
  ['legacy protocol', (data) => { data.snapshot.runtime.runtime_protocol_version = 1; }],
  ['wrong session', (data) => { data.snapshot.runtime.session_id = 'c'.repeat(32); }],
  ['invalid build', (data) => { data.build_id = 'unversioned'; }],
  ['revision coercion', (data) => { data.snapshot.runtime.state_revision = '0'; }],
  ['wrapper revision mismatch', (data) => { data.state_revision = 1; }],
  ['wrapper revision coercion', (data) => { data.state_revision = '0'; }],
  ['unsafe wrapper revision', (data) => { data.state_revision = Number.MAX_SAFE_INTEGER + 1; }],
  ['missing wrapper revision', (data) => { delete data.state_revision; }],
  ['NI stale', (data) => { data.source_stale = true; }],
  ['fresh recovery', (data) => { data.snapshot.runtime.recovery.required = true; }],
  ['fresh demo', (data) => { data.snapshot.runtime.latest.simulated = true; }],
  ['nonfinite age', (data) => { data.source_age_seconds = NaN; }],
  ['missing bank', (data) => { delete data.snapshot.runtime.latest.banks.C5_DIO96_DI; }],
  ['wrong input type', (data) => { data.snapshot.runtime.latest.banks.C3_DIO96_DI.values[0] = 0; }],
  ['nonfinite input', (data) => { data.snapshot.runtime.latest.banks.C1_NI6071E_AI.values[0] = Infinity; }],
])('rejects %s contract before showing values', (label, change) => {
  const data = payload(); change(data);
  expect(() => validateAcqRuntime(data)).toThrow('Contrat Python Acquisition incompatible');
});

test('strips nonfresh values and stale locally even when server does not answer again', () => {
  const data = payload();
  expect(ageAcqRuntime(data, 1).snapshot.runtime.latest).not.toBeNull();
  const stale = ageAcqRuntime(data, 1.8);
  expect(stale.quality).toBe('STALE');
  expect(stale.snapshot.runtime.latest).toBeNull();
  data.quality = 'FAULT';
  expect(validateAcqRuntime(data).snapshot.runtime.latest).toBeNull();
  data.quality = 'INCOMPATIBLE';
  expect(validateAcqRuntime(data).snapshot).toBeNull();
});

test('times out after 5 seconds even if fetch ignores abort and never resolves', async () => {
  global.fetch.mockImplementation(() => new Promise(() => {}));
  const request = acqRuntimeClient.status();
  const rejected = request.catch((error) => error);
  jest.advanceTimersByTime(5000);
  expect((await rejected).message).toContain('sans réponse après 5 s');
  expect(global.fetch.mock.calls[0][1].signal.aborted).toBe(true);
  expect(jest.getTimerCount()).toBe(0);
});

test('external cancellation aborts request immediately and clears timeout', async () => {
  global.fetch.mockImplementation(() => new Promise(() => {}));
  const abort = new AbortController();
  const request = acqRuntimeClient.status(abort.signal);
  const rejected = request.catch((error) => error);
  abort.abort();
  expect(await rejected).toHaveProperty('name', 'AbortError');
  expect(global.fetch.mock.calls[0][1].signal.aborted).toBe(true);
  expect(jest.getTimerCount()).toBe(0);
});

test.each(['HTTP', 'JSON'])('accounts for a 2.5 s delayed %s response before exposing measurements', async (phase) => {
  const data = payload();
  data.snapshot.runtime.age_seconds = 0.2;
  Object.freeze(data.snapshot.runtime);
  const response = { ok: true, json: () => phase === 'JSON'
    ? new Promise((resolve) => setTimeout(() => resolve(data), 2500)) : Promise.resolve(data) };
  global.fetch.mockImplementation(() => phase === 'HTTP'
    ? new Promise((resolve) => setTimeout(() => resolve(response), 2500)) : Promise.resolve(response));
  const request = acqRuntimeClient.status();
  await Promise.resolve();
  await Promise.resolve();
  jest.advanceTimersByTime(2500);
  const received = await request;
  expect(received.source_age_seconds).toBeCloseTo(2.7);
  expect(received.bridge_age_seconds).toBeCloseTo(2.6);
  expect(received.quality).toBe('STALE');
  expect(received.snapshot.runtime.latest).toBeNull();
  expect(data.snapshot.runtime.latest).not.toBeNull();
  expect(data.snapshot.runtime.age_seconds).toBe(0.2);
  expect(data.source_age_seconds).toBe(0.2);
});

test.each([-1, NaN, Infinity])('fails closed when monotonic request duration is invalid (%s)', async (elapsed) => {
  let now = 100;
  jest.spyOn(performance, 'now').mockImplementation(() => now);
  global.fetch.mockResolvedValue({ ok: true, json: async () => payload() });
  const request = acqRuntimeClient.status();
  now = 100 + elapsed;
  await expect(request).rejects.toThrow('Durée de transport Python Acquisition invalide');
});
