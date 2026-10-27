// Fixed same-origin observer route. No commands or direct XP transport.
export const SYNC_READ_DEADLINE_MS = 5000;
export const MAX_SYNC_JSON_CHARS = 16 * 1024;
const ROUTE = '/api/elyse/acquisition/telemetry/synchronization';

async function synchronization(signal) {
  if (signal?.aborted) throw new DOMException('Lecture annulée', 'AbortError');
  const controller = new AbortController();
  let timer;
  let cancel;
  const cancelled = new Promise((resolve, reject) => {
    cancel = () => { controller.abort(); reject(new DOMException('Lecture annulée', 'AbortError')); };
    signal?.addEventListener('abort', cancel, { once: true });
  });
  const deadline = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      controller.abort(); reject(new Error('Lecture SuperVision sans réponse après 5 s.'));
    }, SYNC_READ_DEADLINE_MS);
  });
  const exchange = async () => {
    const response = await fetch(ROUTE, {
      method: 'GET', credentials: 'include', cache: 'no-store', signal: controller.signal,
    });
    const length = Number(response.headers?.get('Content-Length'));
    if (Number.isFinite(length) && length > MAX_SYNC_JSON_CHARS) throw new Error('Réponse synchronisation trop volumineuse.');
    const text = await response.text();
    if (typeof text !== 'string' || text.length > MAX_SYNC_JSON_CHARS) throw new Error('Réponse synchronisation trop volumineuse.');
    const value = JSON.parse(text);
    if (!response.ok) throw new Error(value?.error || 'Lecture SuperVision indisponible.');
    return value;
  };
  try { return await Promise.race([exchange(), deadline, cancelled]); }
  finally { clearTimeout(timer); signal?.removeEventListener('abort', cancel); }
}

export const supervisionCounterClient = Object.freeze({ synchronization });
