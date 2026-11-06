// Same fixed web facade and authenticated JWT-cookie transport as the
// Acquisition client. This client has no command, direct XP or camera route.
export const VIDEO_READ_DEADLINE_MS = 5000;
export const MAX_VIDEO_JSON_CHARS = 1024 * 1024;
const VIDEO = '/api/elyse/acquisition/telemetry/video';

const channelQuery = (channel) => {
  if (channel === undefined || channel === null || channel === '') return '';
  if (!Number.isInteger(channel) || channel < 0 || channel > 0xFFFFFFFF) {
    throw new Error('Canal caméra entier non signé requis.');
  }
  return String(channel);
};

async function readJson(url, signal) {
  if (signal?.aborted) throw new DOMException('Lecture vidéo annulée', 'AbortError');
  const controller = new AbortController();
  let timer;
  let cancel;
  const cancelled = new Promise((resolve, reject) => {
    cancel = () => {
      controller.abort();
      reject(new DOMException('Lecture vidéo annulée', 'AbortError'));
    };
    signal?.addEventListener('abort', cancel, { once: true });
  });
  const deadline = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error('Lecture vidéo sans réponse après 5 s.'));
    }, VIDEO_READ_DEADLINE_MS);
  });
  const exchange = async () => {
    const response = await fetch(url, {
      method: 'GET', credentials: 'include', cache: 'no-store', signal: controller.signal,
    });
    const length = Number(response.headers?.get('Content-Length'));
    if (Number.isFinite(length) && length > MAX_VIDEO_JSON_CHARS) {
      controller.abort();
      throw new Error('Réponse vidéo trop volumineuse.');
    }
    const text = await response.text();
    if (typeof text !== 'string' || text.length > MAX_VIDEO_JSON_CHARS) {
      throw new Error('Réponse vidéo trop volumineuse.');
    }
    const value = JSON.parse(text);
    if (!response.ok) throw new Error(value?.error || `Lecture vidéo indisponible (HTTP ${response.status}).`);
    return value;
  };
  try { return await Promise.race([exchange(), deadline, cancelled]); }
  finally { clearTimeout(timer); signal?.removeEventListener('abort', cancel); }
}

function video(signal, { channel } = {}) {
  const selected = channelQuery(channel);
  return readJson(VIDEO + (selected ? `?channel=${selected}` : ''), signal);
}

function channels(signal) { return readJson(`${VIDEO}/channels`, signal); }

function subscribe({ onFrame, onError, signal, channel, targetFps = 25 } = {}) {
  if (typeof EventSource !== 'function') throw new Error('Flux vidéo indisponible dans ce navigateur.');
  if (typeof onFrame !== 'function' || ![25, 12.5].includes(targetFps)) {
    throw new Error('Récepteur vidéo et fréquence25 ou12.5Hz requis.');
  }
  const selected = channelQuery(channel);
  if (signal?.aborted) return () => {};
  const query = new URLSearchParams({ fps: String(targetFps) });
  if (selected !== '') query.set('channel', selected);
  const source = new EventSource(`${VIDEO}/stream?${query}`, { withCredentials: true });
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    source.close();
    source.removeEventListener('frame', receive);
    source.removeEventListener('status', receive);
    source.removeEventListener('error', failure);
    signal?.removeEventListener('abort', close);
  };
  const failure = () => {
    if (!closed) onError?.(new Error('Flux vidéo interrompu; reconnexion en cours.'));
  };
  const receive = (event) => {
    if (closed) return;
    try {
      if (typeof event.data !== 'string' || event.data.length > MAX_VIDEO_JSON_CHARS) {
        throw new Error('Réponse vidéo trop volumineuse.');
      }
      onFrame(JSON.parse(event.data));
    } catch (error) { onError?.(error); }
  };
  source.addEventListener('frame', receive);
  source.addEventListener('status', receive);
  source.addEventListener('error', failure);
  signal?.addEventListener('abort', close, { once: true });
  return close;
}

export const acqVideoClient = Object.freeze({ video, channels, subscribe });
