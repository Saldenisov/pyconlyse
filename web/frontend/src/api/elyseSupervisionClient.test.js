import { elyseSupervisionClient as client } from './elyseSupervisionClient';

beforeEach(() => { global.fetch = jest.fn(); });
afterEach(() => { jest.restoreAllMocks(); });
const ok = (extra = {}) => ({ ok: true, status: 200,
  json: async () => ({ schema_version: 1, execution_allowed: false, ...extra }) });

test('snapshot uses same-origin credentials', async () => {
  fetch.mockResolvedValue(ok());
  await client.snapshot();
  expect(fetch).toHaveBeenCalledWith('/api/elyse/supervision', expect.objectContaining({ credentials: 'include' }));
});
test('telemetry uses the fixed read-only endpoint with no command body', async () => {
  fetch.mockResolvedValue(ok());
  await client.telemetry();
  expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/telemetry', expect.objectContaining({ credentials: 'include' }));
  const options = fetch.mock.calls[0][1];
  expect(options.method).toBeUndefined();
  expect(options.body).toBeUndefined();
});
test('replay only targets the bounded API, includes CSRF and no hardware approval', async () => {
  document.cookie = 'csrf_access_token=csrf-test';
  fetch.mockResolvedValue(ok());
  await client.replay('machine_frequency', { new_value: 5 });
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe('/api/elyse/supervision/replay');
  expect(options.headers['X-CSRF-TOKEN']).toBe('csrf-test');
  expect(options.headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBeUndefined();
  expect(JSON.parse(options.body)).toEqual({ operation: 'machine_frequency', inputs: { new_value: 5 } });
  document.cookie = 'csrf_access_token=; Max-Age=0';
});
test('execution authority and wrong schema responses are rejected', async () => {
  fetch.mockResolvedValueOnce(ok({ execution_allowed: true })).mockResolvedValueOnce(ok({ schema_version: 2 }));
  await expect(client.snapshot()).rejects.toThrow('Contrat SuperVision incompatible');
  await expect(client.snapshot()).rejects.toThrow('Contrat SuperVision incompatible');
});
test('authentication and model-validation failures are shown', async () => {
  fetch.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) });
  await expect(client.snapshot()).rejects.toThrow('Authentification');
  fetch.mockResolvedValueOnce({ ok: false, status: 400, json: async () => ({ error: 'Required fields' }) });
  await expect(client.replay('monitoring', {})).rejects.toThrow('Required fields');
});
test('external cancellation is propagated to fetch', async () => {
  fetch.mockResolvedValue(ok());
  const abort = new AbortController();
  abort.abort();
  await client.snapshot(abort.signal);
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

test('business lifecycle uses guarded same-origin API with immutable intent ID', async () => {
  fetch.mockResolvedValue(ok());
  await client.business();
  await client.stageIntent({ intent_id: 'operator-1', page: 'Page HT', control: 'Marche HT' });
  await client.submitIntent('operator-1', 'revision-7');
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    '/api/elyse/supervision/business', '/api/elyse/supervision/business/intents',
    '/api/elyse/supervision/business/intents/operator-1/submit',
  ]);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ intent_id: 'operator-1', page: 'Page HT', control: 'Marche HT' });
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ expected_revision: 'revision-7' });
  expect(fetch.mock.calls.every(([, options]) => options.credentials === 'include')).toBe(true);
});

test('intent trace is an encoded readonly same-origin request', async () => {
  fetch.mockResolvedValue(ok());
  await client.intentTrace('saved/intent');
  expect(fetch).toHaveBeenCalledWith('/api/elyse/supervision/business/intents/saved%2Fintent/trace',
    expect.objectContaining({ credentials: 'include' }));
  expect(fetch.mock.calls[0][1].method).toBeUndefined();
  expect(fetch.mock.calls[0][1].body).toBeUndefined();
});
