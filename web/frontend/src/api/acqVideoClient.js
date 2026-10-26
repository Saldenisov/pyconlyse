// Same fixed web facade and authenticated JWT-cookie transport as the
// Acquisition client. This client has no command, direct XP or camera route.
export const VIDEO_READ_DEADLINE_MS = 5000;
export const MAX_VIDEO_JSON_CHARS = 1024 * 1024;
const VIDEO = '/api/elyse/acquisition/telemetry/video';

async function video(signal) {
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
    const response = await fetch(VIDEO, {
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

export const acqVideoClient = Object.freeze({ video });
