import { decodeSupervisionU8Frame, decodeSupervisionVideo, grayscaleRgba, MAX_U8_BYTES } from './acquisitionVideoU8';

function frame(values = [0, 17, 128, 255]) {
  return { source: 'python_supervision_ni1409', simulated: false, sequence: 1,
    sequence_interpretation: 'software grab observation, not hardware frame counter',
    capture_session_id: 'c'.repeat(32), observed_utc: '2026-10-26T12:00:00+00:00',
    sample_elapsed_seconds: 0.01, source_age_seconds: 0.1, width: values.length, height: 1,
    pixel_type: 'U8', encoding: 'base64_raw_row_major',
    data: Buffer.from(values).toString('base64'), channel: 2,
    processing: 'raw_grab_before_legacy_interlace_bcg_profiles', hardware_acknowledged: false };
}

function payload(value = frame()) {
  const { data, sample_elapsed_seconds, source_age_seconds, sequence_interpretation, simulated, ...metadata } = value;
  return { schema_version: 1, owner: 'supervision', available: true, stale: false,
    session_id: 'a'.repeat(32), source_mode: value.source.startsWith('labview') ? 'LABVIEW_BRIDGE' : 'PYTHON_NATIVE',
    age_seconds: 0.2, ...metadata, frame: value };
}

test('decodes raw row-major U8 and maps black/midtones/white to opaque grayscale exactly', () => {
  const raw = { ...frame(), width: 2, height: 2 };
  const value = decodeSupervisionU8Frame(raw);
  expect(value.width).toBe(2); expect(value.height).toBe(2);
  expect([...value.pixels]).toEqual([0, 17, 128, 255]);
  expect([...grayscaleRgba(value.pixels)]).toEqual([
    0, 0, 0, 255, 17, 17, 17, 255, 128, 128, 128, 255, 255, 255, 255, 255,
  ]);
});

test('accepts the complete 512KiB boundary without recursive regex or hidden rescaling', () => {
  const bytes = Uint8Array.from({ length: MAX_U8_BYTES }, (_, index) => index % 256);
  const value = decodeSupervisionU8Frame({ ...frame(bytes), width: 1024, height: 512 });
  expect(value.pixels.byteLength).toBe(MAX_U8_BYTES);
  expect(value.pixels[511]).toBe(255);
  expect(value.pixels[MAX_U8_BYTES - 1]).toBe(255);
  expect(grayscaleRgba(value.pixels).byteLength).toBe(MAX_U8_BYTES * 4);
  expect(() => decodeSupervisionU8Frame({ ...frame(), width: MAX_U8_BYTES + 1 })).toThrow('Géométrie');
});

test.each([0, -1, 1.5, NaN, Infinity, true, '2'])('rejects invalid geometry before decoding: %s', (width) => {
  expect(() => decodeSupervisionU8Frame({ ...frame(), width })).toThrow('Géométrie');
});

test.each([
  { pixel_type: 'U16' }, { encoding: 'base64' }, { data: 'ABGA/w=' },
  { data: 'ABGA w==' }, { data: 'ABGA_w==' }, { data: '====AAAA' },
  { data: 'ABGA/w==\n' }, { data: 123 },
])('rejects other pixel formats, malformed base64 and geometry/byte-count mismatches', (change) => {
  expect(() => decodeSupervisionU8Frame({ ...frame(), ...change })).toThrow();
});

test('validates canonical base64 padding bits rather than silently changing bytes', () => {
  expect([...decodeSupervisionU8Frame(frame([102])).pixels]).toEqual([102]);
  expect(() => decodeSupervisionU8Frame({ ...frame([102]), data: 'Zh==' })).toThrow('canonique');
  expect([...decodeSupervisionU8Frame(frame([102, 111])).pixels]).toEqual([102, 111]);
  expect(() => decodeSupervisionU8Frame({ ...frame([102, 111]), data: 'Zm9=' })).toThrow('canonique');
});

test.each([
  { source: 'arbitrary_camera' }, { simulated: true }, { hardware_acknowledged: true },
  { sequence: 0 }, { sequence: Number.MAX_SAFE_INTEGER + 1 }, { capture_session_id: 'other' },
  { channel: 4 }, { sample_elapsed_seconds: Infinity }, { source_age_seconds: -1 },
  { observed_utc: 'not UTC' }, { processing: 'invented_processed_image' },
])('rejects unqualified or ambiguous image identity/metadata', (change) => {
  expect(() => decodeSupervisionU8Frame({ ...frame(), ...change })).toThrow();
});

test('retains separate native/VI source-run and camera capture identities', () => {
  const native = decodeSupervisionVideo(payload());
  const vi = { ...frame(), source: 'labview_supervision_ni1409', source_session_id: 'b'.repeat(32) };
  const bridged = decodeSupervisionVideo(payload(vi));
  expect(native.state).toBe('CURRENT');
  expect(bridged.frame.sourceSessionId).toBe('b'.repeat(32));
  expect(bridged.identity).not.toBe(native.identity);
  expect(() => decodeSupervisionU8Frame({ ...vi, source_session_id: undefined })).toThrow();
  expect(() => decodeSupervisionVideo({ ...payload(vi), source_session_id: 'd'.repeat(32) })).toThrow('externe');
});

test('unavailable and stale snapshots have no decoded image; stale is never current', () => {
  expect(decodeSupervisionVideo({ schema_version: 1, owner: 'supervision', available: false, frame: null }).state)
    .toBe('UNAVAILABLE');
  expect(decodeSupervisionVideo({ schema_version: 1, owner: 'supervision', available: false,
    stale: true, sequence: 5, age_seconds: 2.4, frame: null }).state).toBe('STALE');
  expect(decodeSupervisionVideo({ ...payload(), age_seconds: 1.999 }).state).toBe('CURRENT');
  expect(decodeSupervisionVideo({ ...payload(), age_seconds: 2 }).state).toBe('STALE');
  expect(() => decodeSupervisionVideo({ ...payload(), available: false })).toThrow('indisponible');
});

test.each([
  { owner: 'acquisition' }, { schema_version: 0 }, { stale: true }, { available: 'yes' },
  { session_id: 'unknown' }, { width: 3 }, { sequence: 2 }, { capture_session_id: 'd'.repeat(32) },
  { age_seconds: Infinity }, { source_mode: 'LABVIEW_BRIDGE' },
])('rejects mismatched outer owner/capture/freshness metadata', (change) => {
  expect(() => decodeSupervisionVideo({ ...payload(), ...change })).toThrow();
});

test('RGBA conversion cannot allocate from arbitrary unbounded/non-U8 values', () => {
  expect(() => grayscaleRgba([])).toThrow();
  expect(() => grayscaleRgba(new Uint8Array())).toThrow();
  expect(() => grayscaleRgba(new Uint8Array(MAX_U8_BYTES + 1))).toThrow();
});
