import { DISPLAY_RULES, ACQ_TIMING, formatDisplay, projectDisplay, readBankField } from './elyseLiveProjection';

export function liveFixture() {
  const banks = [['C1NI6071E', 64, 'DBL'], ['C2NI6071E', 64, 'DBL'], ['VAM-A', 64, 'DBL'],
    ['C3_IN_DIO96', 56, 'Boolean'], ['C4_IN_DIO96', 64, 'Boolean'], ['EPS', 77, 'Boolean'],
    ['C1011NI6602', 33, 'DBL']];
  return { quality: 'FRESH', stale_after_seconds: 2, snapshot: { receiver_session: 'test-session',
    publications: Object.fromEntries(banks.map(([bank, size, type]) => [bank, {
      data: Array(size).fill(type === 'Boolean' ? false : 0), age_seconds: 0.1, stale: false,
      error: { status: false, code: 0, source: '' }, lv_type: { type: 'LvVariant', contained_type: {
        type: 'Cluster', name: bank === 'C1011NI6602' ? 'C10-11 NI6602' : bank,
        fields: Array.from({ length: size }, (_, index) => ({ name: String(index), type })),
      } },
    }])) } };
}

test('pressure uses active VAM calibration, preserves negative values and distinguishes native filters', () => {
  const payload = liveFixture();
  payload.snapshot.publications['VAM-A'].data[12] = 0.0052;
  const guide = projectDisplay(DISPLAY_RULES.find((r) => r.id === 'vide:3'), payload);
  expect(guide.value).toBeCloseTo(-1.04e-8, 15);
  expect(guide.unit).toBe('mbar');
  expect(guide.temporal_equivalence).toBe(true);
  for (const id of ['vide:9', 'vide:12']) {
    expect(DISPLAY_RULES.find((r) => r.id === id)).toMatchObject({ native_filter_samples: 30, temporal_equivalence: false });
  }
  expect(formatDisplay(guide.value, guide.unit)).toBe('-1,04e-8');
});

test('uses measured temperatures, 14 modulator readouts and explicit focal scales', () => {
  const payload = liveFixture();
  payload.snapshot.publications.C1NI6071E.data[0] = 9.96;
  expect(projectDisplay(DISPLAY_RULES.find((r) => r.id === 'fluides:5'), payload).value).toBe(9.96);
  expect(DISPLAY_RULES.filter((r) => r.page === 'modulateur' && r.kind === 'number')).toHaveLength(14);
  for (const [id, index, scale] of [['modulateur:42', 5, 3], ['modulateur:43', 13, 4.11], ['modulateur:44', 6, 4.14]]) {
    payload.snapshot.publications.C2NI6071E.data[index] = 2;
    expect(projectDisplay(DISPLAY_RULES.find((r) => r.id === id), payload).value).toBe(2 * scale);
  }
});

test('distinguishes false from unknown and refuses unavailable, stale and read-error data', () => {
  const payload = liveFixture();
  const rule = DISPLAY_RULES.find((r) => r.id === 'modulateur:54');
  expect(projectDisplay(rule, payload).value).toBe(false);
  expect(projectDisplay(rule, payload, 2).quality).toBe('STALE');
  expect(projectDisplay(rule, payload, 0, 'network failed').value).toBeNull();
  payload.snapshot.publications.EPS.error.code = 42;
  expect(projectDisplay(rule, payload).quality).toBe('READ_ERROR');
  delete payload.snapshot.publications.EPS;
  expect(projectDisplay(rule, payload).quality).toBe('MISSING');
});

test.each(['OFF', 'FAULT', 'UNKNOWN', null])('rejects retained banks when receiver state is explicitly %p', (state) => {
  const payload = liveFixture();
  payload.server_state = state;
  expect(readBankField(payload, 'C4_IN_DIO96', 0, 'boolean'))
    .toMatchObject({ quality: 'UNAVAILABLE', value: null });
});

test.each(['RECEIVER_NOT_READY', 'UNAVAILABLE'])('rejects retained banks when envelope quality is %s', (quality) => {
  const payload = liveFixture();
  payload.quality = quality;
  expect(readBankField(payload, 'C1NI6071E', 0, 'number'))
    .toMatchObject({ quality: 'UNAVAILABLE', value: null });
});

test.each([NaN, Infinity, -Infinity, -0.1, null, '0'])('invalid elapsed time %p never makes bank fresh', (elapsed) => {
  expect(readBankField(liveFixture(), 'C4_IN_DIO96', 0, 'boolean', elapsed))
    .toMatchObject({ quality: 'UNAVAILABLE', value: null });
});

test.each(['INCOMPLETE', 'READ_ERROR', 'STALE'])('global %s does not hide an independently fresh bank', (quality) => {
  const payload = liveFixture();
  payload.server_state = 'ON';
  payload.quality = quality;
  payload.snapshot.publications.EPS.error = { status: true, code: 42, source: 'Other bank' };
  payload.snapshot.publications.C2NI6071E.stale = true;
  delete payload.snapshot.publications['VAM-A'];
  expect(readBankField(payload, 'C4_IN_DIO96', 0, 'boolean'))
    .toMatchObject({ quality: 'FRESH', value: false, age: 0.1 });
  expect(readBankField(payload, 'EPS', 0, 'boolean').quality).toBe('READ_ERROR');
  expect(readBankField(payload, 'C2NI6071E', 0, 'number').quality).toBe('STALE');
  expect(readBankField(payload, 'VAM-A', 0, 'number').quality).toBe('MISSING');
});

test.each([null, {}, { nonfinite: 'NaN' }, '0', true, Infinity, NaN])('rejects malformed numeric %p rather than coercing to zero', (value) => {
  const payload = liveFixture();
  payload.snapshot.publications['VAM-A'].data[12] = value;
  expect(projectDisplay(DISPLAY_RULES.find((r) => r.id === 'vide:3'), payload).quality).toBe('VALUE_ERROR');
});

test('requires exact bank shape, identity and field type; never treats receiver ON as measurement health', () => {
  const payload = liveFixture();
  payload.snapshot.publications.C1NI6071E.data.pop();
  expect(readBankField(payload, 'C1NI6071E', 0, 'number').quality).toBe('SCHEMA_ERROR');
  payload.snapshot.publications.C2NI6071E.lv_type.contained_type.name = 'wrong bank';
  expect(readBankField(payload, 'C2NI6071E', 0, 'number').value).toBeNull();
});

test('uses the native base-10 attenuation formula only in its finite real domain', () => {
  const payload = liveFixture();
  const rule = DISPLAY_RULES.find((r) => r.id === 'hf:0');
  payload.snapshot.publications.C1NI6071E.data[44] = 3.6;
  const cosine = Math.cos((2 * 3.1416 / 360) * (1.2087 * 3.6 ** 3 - 6.5232 * 3.6 ** 2 - 15.097 * 3.6 + 86.932));
  expect(projectDisplay(rule, payload).value).toBeCloseTo(-20 * Math.log10(cosine), 12);
  expect(projectDisplay(rule, payload).value).not.toBeCloseTo(-20 * Math.log(cosine), 3);
  payload.snapshot.publications.C1NI6071E.data[44] = -1;
  expect(projectDisplay(rule, payload)).toMatchObject({ quality: 'VALUE_ERROR', value: null });
  payload.snapshot.publications.C1NI6071E.data[44] = 1e308;
  expect(projectDisplay(rule, payload)).toMatchObject({ quality: 'VALUE_ERROR', value: null });
});

test('does not silently include SUP-owned C11 values or execute arbitrary formulas', () => {
  expect(ACQ_TIMING).toHaveLength(16);
  expect(ACQ_TIMING.every((r) => r.index < 16)).toBe(true);
  expect(projectDisplay({ bank: 'VAM-A', index: 0, kind: 'number', transform: 'eval' }, liveFixture()).quality).toBe('UNQUALIFIED');
});
