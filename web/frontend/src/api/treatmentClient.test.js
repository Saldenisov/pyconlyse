import {
  TREATMENT_AUTH_MESSAGE,
  fetchCleaningView,
  fetchCompressionJob,
  fetchFileSummary,
  fetchFolderSetJob,
  fetchFolderListing,
  fetchSelection,
  fetchTreatmentPreview,
  fetchTreatmentQueue,
  enqueueStandardFolderTreatment,
  enqueueTreatmentRecipe,
  postTreatment,
  removeTreatmentQueueJob,
  runTreatmentQueue,
  startCompressionJob,
  startFolderSetJob,
  fetchTreatmentSession,
  updateSelectionConfig,
  fetchSkanaDataset,
  importSkanaDataset,
  startSkanaJob,
  fetchSkanaJob,
  cancelSkanaJob,
  downloadSkanaResult,
} from './treatmentClient';
import {
  clearHardwareApprovalNonce,
  getHardwareApprovalNonce,
  setHardwareApprovalNonce,
} from './csrfRequest';

const originalFetch = global.fetch;

describe('SK-Ana session request contracts', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200,
      json: async () => ({ success: true }), blob: async () => new Blob(['{}']) });
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });
  afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });

  test('matrix reads are same-origin and session-specific', async () => {
    await fetchSkanaDataset('s-one', 'od');
    expect(fetch).toHaveBeenCalledWith('/api/treatment/skana/dataset?source=od', expect.objectContaining({
      credentials: 'same-origin', headers: { 'X-Treatment-Session-Id': 's-one' }, signal: expect.any(AbortSignal) }));
    expect(fetch.mock.calls[0][1].body).toBeUndefined();
  });
  test('import/start/cancel preserve JSON and CSRF without hardware approval', async () => {
    document.cookie = 'csrf_access_token=skana-token; path=/';
    await importSkanaDataset('s-one', { text: '0 400\n0 1', orientation: 'time_rows' });
    await startSkanaJob('s-one', { method: 'svd', fingerprint: 'first', source: 'od', options: { rank: 2 } });
    await fetchSkanaJob('s-one', 'job/one');
    await cancelSkanaJob('s-one', 'job/one');
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/treatment/skana/import', '/api/treatment/skana/jobs',
      '/api/treatment/skana/jobs/job%2Fone', '/api/treatment/skana/jobs/job%2Fone/cancel']);
    expect(fetch.mock.calls[1][1].headers).toEqual({ 'X-Treatment-Session-Id': 's-one', 'Content-Type': 'application/json',
      'X-CSRF-TOKEN': 'skana-token' });
    expect(JSON.parse(fetch.mock.calls[1][1].body).fingerprint).toBe('first');
    expect(fetch.mock.calls.every(([, options]) => !options.headers['X-PYCONLYSE-HARDWARE-APPROVAL'])).toBe(true);
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });
  test('external abort reaches fetch and downloads remain blobs', async () => {
    const abort = new AbortController();
    await fetchSkanaDataset('s-one', 'od', abort.signal);
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(false);
    const blob = await downloadSkanaResult('s-one', 'job-one', 'csv');
    expect(blob).toBeInstanceOf(Blob);
    expect(fetch.mock.calls[1][0]).toBe('/api/treatment/skana/jobs/job-one/export?format=csv');
    const alreadyAborted = new AbortController(); alreadyAborted.abort();
    await fetchSkanaJob('s-one', 'job-one', alreadyAborted.signal);
    expect(fetch.mock.calls[2][1].signal.aborted).toBe(true);
  });
  test('request abort stays cancellation, not an invented timeout', async () => {
    const abort = new AbortController();
    fetch.mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(Object.assign(new Error('Cancelled'), { name: 'AbortError' })));
    }));
    const pending = fetchSkanaJob('s-one', 'job-one', abort.signal);
    abort.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError', message: 'Cancelled' });
  });
});

describe('treatmentClient request contracts', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
    clearHardwareApprovalNonce();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
    jest.useRealTimers();
  });

  test('fetchTreatmentSession includes session header and returns JSON payload', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true, session: 'abc' }),
    });

    await expect(fetchTreatmentSession('session-abc')).resolves.toEqual({
      success: true,
      session: 'abc',
    });
    expect(global.fetch).toHaveBeenCalledWith('/api/treatment/session', {
      headers: { 'X-Treatment-Session-Id': 'session-abc' },
      signal: expect.any(AbortSignal),
    });
  });

  test('postTreatment serializes body and uses long timeout for long-running route', async () => {
    jest.useFakeTimers();
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true }),
    });

    await postTreatment('s1', '/api/treatment/session/compress-file/start', {
      file_path: '/tmp/input.dat',
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/session/compress-file/start',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Treatment-Session-Id': 's1',
        },
        body: JSON.stringify({ file_path: '/tmp/input.dat' }),
        signal: expect.any(AbortSignal),
      })
    );
    expect(jest.getTimerCount()).toBe(0);
  });

  test('adds the current CSRF token to mutation requests without changing payload or headers', async () => {
    document.cookie = 'csrf_access_token=current%20token; path=/';
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true }),
    });

    await postTreatment('s1', '/api/treatment/save', { file_path: '/tmp/input.dat' });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/save',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Treatment-Session-Id': 's1',
          'X-CSRF-TOKEN': 'current token',
        },
        body: JSON.stringify({ file_path: '/tmp/input.dat' }),
      })
    );
  });

  test('treatment mutations preserve a pending hardware approval nonce', async () => {
    const nonce = 'a'.repeat(64);
    document.cookie = 'csrf_access_token=current%20token; path=/';
    setHardwareApprovalNonce(nonce);
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true }),
    });

    await postTreatment('s1', '/api/treatment/save', { file_path: '/tmp/input.dat' });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/save',
      expect.objectContaining({
        headers: expect.not.objectContaining({
          'X-PYCONLYSE-HARDWARE-APPROVAL': expect.anything(),
        }),
      })
    );
    expect(getHardwareApprovalNonce()).toBe(nonce);
  });

  test('converts failed responses and network failures to stable errors', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: jest.fn().mockResolvedValue({ error: 'backend unavailable' }),
    });
    await expect(fetchTreatmentSession()).rejects.toThrow('backend unavailable');

    global.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(fetchTreatmentSession()).rejects.toThrow(
      'Failed to fetch /api/treatment/session. Check backend connection.'
    );
  });

  test.each([
    { msg: 'Missing or invalid authentication credentials' },
    { msg: 'Token has expired' },
    null,
  ])('offers authentication recovery for a 401 response: %j', async (payload) => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: jest.fn().mockResolvedValue(payload),
    });
    await expect(postTreatment('sid', '/api/treatment/session/config')).rejects.toMatchObject({
      message: TREATMENT_AUTH_MESSAGE,
      status: 401,
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test('preserves server msg errors outside authentication failures', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: jest.fn().mockResolvedValue({ msg: 'Access denied' }),
    });
    await expect(fetchTreatmentSession()).rejects.toThrow('Access denied');
  });

  test('uses encoded query parameters and maps AbortError to timeout message', async () => {
    jest.useFakeTimers();
    global.fetch.mockImplementation((_url, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          const error = new Error('aborted');
          error.name = 'AbortError';
          reject(error);
        });
      })
    );

    const request = fetchFileSummary('s2', '/data/a b.dat');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/file-summary?file_path=%2Fdata%2Fa%20b.dat',
      expect.objectContaining({ headers: { 'X-Treatment-Session-Id': 's2' } })
    );
    jest.advanceTimersByTime(120000);
    await expect(request).rejects.toThrow('Request timed out after 120 seconds.');

    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true }),
    });
    await fetchFolderListing('s3', '/folder/a b');
    expect(global.fetch).toHaveBeenLastCalledWith(
      '/api/treatment/files?folder=%2Ffolder%2Fa%20b',
      expect.objectContaining({ headers: { 'X-Treatment-Session-Id': 's3' } })
    );
  });

  test.each([
    ['startCompressionJob', startCompressionJob, '/api/treatment/session/compress-file/start', 'POST'],
    ['startFolderSetJob', startFolderSetJob, '/api/treatment/session/folder-set/start', 'POST'],
    ['fetchCompressionJob', fetchCompressionJob, '/api/treatment/session/compress-file/status/job%2F1', 'GET'],
    ['fetchFolderSetJob', fetchFolderSetJob, '/api/treatment/session/folder-set/status/job%2F1', 'GET'],
    ['fetchTreatmentPreview', fetchTreatmentPreview, '/api/treatment/preview?data_type=raw%20data&map_index=0', 'GET'],
    ['fetchSelection', fetchSelection, '/api/treatment/selection', 'GET'],
    ['fetchCleaningView', fetchCleaningView, '/api/treatment/cleaning/view', 'GET'],
    ['fetchTreatmentQueue', fetchTreatmentQueue, '/api/treatment/queue', 'GET'],
    ['enqueueStandardFolderTreatment', enqueueStandardFolderTreatment, '/api/treatment/queue/folder-set', 'POST'],
    ['runTreatmentQueue', runTreatmentQueue, '/api/treatment/queue/run', 'POST'],
  ])('%s targets expected route', async (_name, wrapper, expectedUrl, method) => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true }),
    });
    const args = {
      startCompressionJob: ['sid', '/input.dat'],
      startFolderSetJob: ['sid', { folder: '/input' }],
      fetchCompressionJob: ['sid', 'job/1'],
      fetchFolderSetJob: ['sid', 'job/1'],
      fetchTreatmentPreview: ['sid', 'raw data'],
      fetchSelection: ['sid'],
      fetchCleaningView: ['sid'],
      fetchTreatmentQueue: ['sid'],
      enqueueStandardFolderTreatment: ['sid', { folder_path: '/input' }],
      runTreatmentQueue: ['sid'],
    }[_name];
    await wrapper(...args);
    expect(global.fetch).toHaveBeenCalledWith(
      expectedUrl,
      expect.objectContaining({
        ...(method === 'POST' ? { method: 'POST', body: expect.any(String) } : {}),
        headers: expect.objectContaining({ 'X-Treatment-Session-Id': 'sid' }),
        signal: expect.any(AbortSignal),
      })
    );
  });

  test('removeTreatmentQueueJob targets encoded queue job route', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true, queue: { jobs: [] } }),
    });

    await removeTreatmentQueueJob('sid', 'job/1');

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/queue/job%2F1',
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ 'X-Treatment-Session-Id': 'sid' }),
        signal: expect.any(AbortSignal),
      })
    );
  });

  test('enqueueTreatmentRecipe posts the complete immutable recipe payload', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({ success: true, queue: { jobs: [] } }),
    });
    const recipe = {
      label: 'run-001',
      cleaning: {
        state: 'pending',
        angle_threshold: 1.5,
        surface_threshold: 7,
        data_types: ['ABS'],
      },
    };

    await enqueueTreatmentRecipe('sid', recipe);

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/queue',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'X-Treatment-Session-Id': 'sid' }),
        body: JSON.stringify(recipe),
        signal: expect.any(AbortSignal),
      })
    );
  });

  test('updateSelectionConfig posts payload and parses non-JSON responses', async () => {
    document.cookie = 'csrf_access_token=selection-token; path=/';
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: jest.fn().mockRejectedValue(new SyntaxError('no content')),
    });
    await expect(updateSelectionConfig('sid', { mode: 'auto' })).resolves.toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/treatment/session/selection',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Treatment-Session-Id': 'sid',
          'X-CSRF-TOKEN': 'selection-token',
        },
        body: JSON.stringify({ mode: 'auto' }),
      })
    );

    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: jest.fn().mockRejectedValue(new SyntaxError('html error')),
    });
    await expect(fetchSelection('sid')).rejects.toThrow('Request failed with status 500.');
  });

  test('default-timeout wrappers abort after 30 seconds', async () => {
    jest.useFakeTimers();
    global.fetch.mockImplementation((_url, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          const error = new Error('aborted');
          error.name = 'AbortError';
          reject(error);
        });
      })
    );
    const request = fetchCompressionJob('sid', 'job-1');
    jest.advanceTimersByTime(30000);
    await expect(request).rejects.toThrow('Request timed out after 30 seconds.');
  });
});
