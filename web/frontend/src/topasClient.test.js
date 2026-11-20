import { readTopas, sendTopas } from './topasClient';
import { fetchWithHardwareApproval } from './api/csrfRequest';
jest.mock('./api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));
const originalFetch = global.fetch;
const originalCrypto = global.crypto;
beforeEach(() => { global.crypto = { getRandomValues: values => { values.fill(7); return values; } }; });
afterEach(() => { global.fetch = originalFetch; global.crypto = originalCrypto; jest.clearAllMocks(); });

test('reads cached Tango snapshot through the existing device API', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, value: '{"fresh":true,"data":{}}' }) });
  const abort = new AbortController();
  expect(await readTopas(abort.signal)).toEqual({ fresh: true, data: {} });
  expect(global.fetch).toHaveBeenCalledWith('/api/device/manip%2Flaser%2Ftopas_t21082/attribute/snapshot_json',
    expect.objectContaining({ cache: 'no-store', signal: abort.signal }));
});

test('hardware request contains one stable deduplication ID and uses approval transport', async () => {
  fetchWithHardwareApproval.mockResolvedValue({ ok: true, json: async () => ({ success: true, result: 'id' }) });
  await sendTopas('set_wavelength', [600, 'SH-SIG']);
  expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1);
  const [url, options] = fetchWithHardwareApproval.mock.calls[0];
  expect(url).toContain('/command/SubmitOperation');
  const value = JSON.parse(JSON.parse(options.body).args);
  expect(value).toEqual({ request_id: expect.stringMatching(/^[a-f0-9]{32}$/), command: 'set_wavelength', arguments: [600, 'SH-SIG'] });
});
