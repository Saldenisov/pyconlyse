// Pure codec for the separately published SuperVision NI1409 image.
// No DOM, network, NI access, rescaling or legacy profile/interlace processing.
export const MAX_U8_BYTES = 512 * 1024;
export const VIDEO_STALE_SECONDS = 2;
const ENCODING = 'base64_raw_row_major';
const SESSION = /^[0-9a-f]{32}$/;
const SOURCES = ['python_supervision_ni1409', 'labview_supervision_ni1409'];
const PROCESSING = 'raw_grab_before_legacy_interlace_bcg_profiles';
const nonnegative = (value) => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const positiveInteger = (value) => Number.isSafeInteger(value) && value > 0;
// Preserve observed U32 channel metadata without inferring a physical input range.
const uint32 = (value) => Number.isInteger(value) && value >= 0 && value <= 0xFFFFFFFF;
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function digit(code) {
  if (code >= 65 && code <= 90) return code - 65;
  if (code >= 97 && code <= 122) return code - 71;
  if (code >= 48 && code <= 57) return code + 4;
  if (code === 43) return 62;
  if (code === 47) return 63;
  return -1;
}

function decodeBase64(data, count) {
  const encodedLength = 4 * Math.ceil(count / 3);
  if (typeof data !== 'string' || data.length !== encodedLength) {
    throw new Error('Taille de l’image U8 incompatible avec sa géométrie.');
  }
  const padding = (3 - (count % 3)) % 3;
  const end = data.length - padding;
  // Validate before allocating. Avoid a repeated-regex-group stack growing
  // with a maximum-size image, and reject whitespace/alternate encodings.
  for (let index = 0; index < end; index += 1) {
    if (digit(data.charCodeAt(index)) < 0) throw new Error('Image U8 : base64 invalide.');
  }
  for (let index = end; index < data.length; index += 1) {
    if (data[index] !== '=') throw new Error('Image U8 : terminaison base64 invalide.');
  }
  if ((padding === 2 && (digit(data.charCodeAt(end - 1)) & 15) !== 0)
    || (padding === 1 && (digit(data.charCodeAt(end - 1)) & 3) !== 0)) {
    throw new Error('Image U8 : base64 non canonique.');
  }
  const pixels = new Uint8Array(count);
  let output = 0;
  for (let index = 0; index < data.length; index += 4) {
    const a = digit(data.charCodeAt(index));
    const b = digit(data.charCodeAt(index + 1));
    const c = index + 2 < end ? digit(data.charCodeAt(index + 2)) : 0;
    const d = index + 3 < end ? digit(data.charCodeAt(index + 3)) : 0;
    pixels[output++] = (a << 2) | (b >> 4);
    if (output < count) pixels[output++] = ((b & 15) << 4) | (c >> 2);
    if (output < count) pixels[output++] = ((c & 3) << 6) | d;
  }
  return pixels;
}

export function decodeSupervisionU8Frame(frame) {
  if (!object(frame) || !positiveInteger(frame.width) || !positiveInteger(frame.height)
    || frame.width > MAX_U8_BYTES || frame.height > MAX_U8_BYTES
    || frame.width * frame.height > MAX_U8_BYTES
    || frame.pixel_type !== 'U8' || frame.encoding !== ENCODING) {
    throw new Error('Géométrie ou format de l’image SuperVision incompatible.');
  }
  const bridge = frame.source === 'labview_supervision_ni1409';
  if (!SOURCES.includes(frame.source) || frame.simulated !== false
    || frame.hardware_acknowledged !== false || !SESSION.test(frame.capture_session_id)
    || (bridge && !SESSION.test(frame.source_session_id)) || !positiveInteger(frame.sequence)
    || !uint32(frame.channel)
    || frame.processing !== PROCESSING || !nonnegative(frame.sample_elapsed_seconds)
    || !nonnegative(frame.source_age_seconds)
    || frame.sequence_interpretation !== 'software grab observation, not hardware frame counter'
    || typeof frame.observed_utc !== 'string' || frame.observed_utc.length > 40
    || !frame.observed_utc.endsWith('+00:00') || !Number.isFinite(Date.parse(frame.observed_utc))) {
    throw new Error('Identité ou métadonnées de l’image SuperVision incompatibles.');
  }
  return { width: frame.width, height: frame.height, sequence: frame.sequence,
    captureSessionId: frame.capture_session_id, sourceSessionId: frame.source_session_id || null,
    source: frame.source, channel: frame.channel, observedUtc: frame.observed_utc,
    pixels: decodeBase64(frame.data, frame.width * frame.height) };
}

export function decodeSupervisionVideo(payload) {
  if (!object(payload) || payload.schema_version !== 1 || payload.owner !== 'supervision'
    || typeof payload.available !== 'boolean') {
    throw new Error('Contrat vidéo SuperVision incompatible.');
  }
  if (!payload.available) {
    if (payload.frame !== null) throw new Error('Image indisponible accompagnée de pixels inattendus.');
    return { state: payload.stale === true && positiveInteger(payload.sequence) ? 'STALE' : 'UNAVAILABLE',
      frame: null, age: nonnegative(payload.age_seconds) ? payload.age_seconds : null,
      stream: null, identity: null };
  }
  if (payload.stale !== false || !nonnegative(payload.age_seconds) || !SESSION.test(payload.session_id)) {
    throw new Error('Fraîcheur ou session vidéo SuperVision incompatible.');
  }
  const frame = decodeSupervisionU8Frame(payload.frame);
  const matching = ['capture_session_id', 'sequence', 'width', 'height', 'pixel_type',
    'encoding', 'channel', 'processing', 'observed_utc', 'source'];
  if (matching.some((key) => payload[key] !== payload.frame[key])
    || payload.hardware_acknowledged !== false
    || payload.source_mode !== (frame.source === 'labview_supervision_ni1409' ? 'LABVIEW_BRIDGE' : 'PYTHON_NATIVE')
    || (frame.sourceSessionId !== null && payload.source_session_id !== frame.sourceSessionId)) {
    throw new Error('Identité externe de l’image SuperVision incompatible.');
  }
  const stream = `${payload.session_id}:${frame.captureSessionId}:${frame.source}:${frame.sourceSessionId || ''}`;
  const age = Math.max(payload.age_seconds, payload.frame.source_age_seconds);
  return { state: age < VIDEO_STALE_SECONDS ? 'CURRENT' : 'STALE', frame, age, stream,
    identity: `${stream}:${frame.sequence}` };
}

export function grayscaleRgba(pixels) {
  if (!(pixels instanceof Uint8Array) || pixels.length === 0 || pixels.length > MAX_U8_BYTES) {
    throw new Error('Tableau U8 borné requis pour l’affichage.');
  }
  const rgba = new Uint8ClampedArray(pixels.length * 4);
  for (let index = 0; index < pixels.length; index += 1) {
    const offset = index * 4;
    rgba[offset] = pixels[index];
    rgba[offset + 1] = pixels[index];
    rgba[offset + 2] = pixels[index];
    rgba[offset + 3] = 255;
  }
  return rgba;
}
