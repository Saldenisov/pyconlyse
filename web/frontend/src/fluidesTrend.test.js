import { emptyTrend, nextFluidesTrend, temperaturePaths, TREND_MAX_POINTS, TREND_WINDOW_MS } from './fluidesTrend';

const BASE = Date.parse('2026-10-16T14:00:00Z');
function telemetry(sequence = 1, ms = 0, session = 'one') {
  const data = Array(64).fill(0); data[0] = 20.5; data[8] = 20.9;
  return { elapsed: 0, failure: '', payload: { observed_utc: new Date(BASE + ms).toISOString(), stale_after_seconds: 2,
    snapshot: { receiver_session: session, publications: { C1NI6071E: {
      sequence, received_utc_on_everest: new Date(BASE + ms).toISOString(), data, age_seconds: 0.1, stale: false,
      error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name: 'C1NI6071E', fields: Array(64).fill({ type: 'DBL' }) },
    } } } } };
}

test('adds real temperatures once per source packet, never elapsed-clock duplicates', () => {
  const t = telemetry();
  const state = nextFluidesTrend(emptyTrend(), t, BASE);
  expect(state.samples).toEqual([{ time: BASE, canon: 20.5, section: 20.9 }]);
  expect(nextFluidesTrend(state, { ...t, elapsed: 0.6 }, BASE + 600)).toBe(state);
});

test.each(['http', 'stale', 'schema', 'read'])('keeps explicit gaps, never zeros or a continuing line: %s', (reason) => {
  let state = nextFluidesTrend(emptyTrend(), telemetry(), BASE);
  const t = telemetry(2, 1000);
  if (reason === 'http') t.failure = 'HTTP failed';
  if (reason === 'stale') t.elapsed = 2;
  if (reason === 'schema') t.payload.snapshot.publications.C1NI6071E.data.pop();
  if (reason === 'read') t.payload.snapshot.publications.C1NI6071E.error.status = true;
  state = nextFluidesTrend(state, t, BASE + 2000);
  expect(state.paused).toBe(true);
  expect(state.samples[1]).toEqual({ time: BASE + 2000, canon: null, section: null });
  expect(nextFluidesTrend(state, t, BASE + 2100)).toBe(state);
  state = nextFluidesTrend(state, telemetry(3, 3000), BASE + 3000);
  expect(temperaturePaths(state.samples, 'canon', (x) => x - BASE, (y) => y)).toBe('M0.00,20.50  M3000.00,20.50');
});

test('breaks a line across a reception gap even without an intermediate failed HTTP poll', () => {
  let state = nextFluidesTrend(emptyTrend(), telemetry(), BASE);
  state = nextFluidesTrend(state, telemetry(2, 5000), BASE + 5000);
  expect(temperaturePaths(state.samples, 'section', (x) => x - BASE, (y) => y)).toBe('M0.00,20.90 M5000.00,20.90');
});

test('rejects invalid channel independently and draws the other real channel', () => {
  const t = telemetry(); t.payload.snapshot.publications.C1NI6071E.data[0] = NaN;
  const state = nextFluidesTrend(emptyTrend(), t, BASE);
  expect(state.samples[0]).toEqual({ time: BASE, canon: null, section: 20.9 });
});

test('resets buffer on receiver restart, sequence rollback or backward reception clock', () => {
  const state = nextFluidesTrend(emptyTrend(), telemetry(10), BASE);
  expect(nextFluidesTrend(state, telemetry(11, 1000, 'two'), BASE + 1000).samples).toHaveLength(1);
  expect(nextFluidesTrend(state, telemetry(1, 1000), BASE + 1000).samples).toHaveLength(1);
  expect(nextFluidesTrend(state, telemetry(11, -1000), BASE + 1000).samples).toHaveLength(1);
});

test('limits both count and time, and does not synthesize missing samples', () => {
  let state = emptyTrend();
  for (let i = 0; i < TREND_MAX_POINTS + 50; i += 1) state = nextFluidesTrend(state, telemetry(i, i * 1000), BASE + i * 1000);
  expect(state.samples).toHaveLength(TREND_MAX_POINTS);
  expect(state.samples[0].time).toBe(BASE + 50000);
  state = nextFluidesTrend(state, telemetry(TREND_MAX_POINTS + 50, TREND_WINDOW_MS * 3), BASE + TREND_WINDOW_MS * 3);
  expect(state.samples).toHaveLength(1);
});

test('retains thirty minutes in RAM and expires samples beyond that window', () => {
  expect(TREND_WINDOW_MS).toBe(30 * 60 * 1000);
  expect(TREND_MAX_POINTS).toBe(1800);
  let state = emptyTrend();
  for (let i = 0; i <= 6; i += 1) {
    const ms = i * 5 * 60 * 1000;
    state = nextFluidesTrend(state, telemetry(i, ms), BASE + ms);
  }
  expect(state.samples).toHaveLength(7);
  expect(state.samples[0].time).toBe(BASE);
  state = nextFluidesTrend(state, telemetry(7, TREND_WINDOW_MS + 1), BASE + TREND_WINDOW_MS + 1);
  expect(state.samples).toHaveLength(7);
  expect(state.samples[0].time).toBe(BASE + 5 * 60 * 1000);
});

test('does not invent a timestamp or samples for a missing session', () => {
  const t = telemetry(); delete t.payload.snapshot.receiver_session;
  expect(nextFluidesTrend(emptyTrend(), t, BASE).samples).toHaveLength(0);
  t.payload.snapshot.receiver_session = 'one';
  t.payload.observed_utc = 'invalid'; delete t.payload.snapshot.publications.C1NI6071E.received_utc_on_everest;
  expect(nextFluidesTrend(emptyTrend(), t, BASE).samples).toHaveLength(0);
});
