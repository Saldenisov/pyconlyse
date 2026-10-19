import { DISPLAY_RULES, projectDisplay } from './elyseLiveProjection';

export const TREND_WINDOW_MINUTES = 30;
export const TREND_WINDOW_MS = TREND_WINDOW_MINUTES * 60 * 1000;
export const TREND_MAX_POINTS = TREND_WINDOW_MINUTES * 60;
export const TREND_GAP_MS = 2500;
const RULES = [5, 22].map((field) => DISPLAY_RULES.find((r) => r.page === 'fluides' && r.target_field === field));
export const emptyTrend = () => ({ session: null, samples: [], lastKey: null, lastSequence: null, paused: true });

// Bounded display buffer only. No storage API, backend writes, interpolation,
// zero substitution, or reconstruction of samples missed by browser polling.
export function nextFluidesTrend(previous, telemetry, now) {
  const { payload, elapsed, failure } = telemetry;
  const session = payload?.snapshot?.receiver_session;
  if (!session) return previous;
  const bank = payload.snapshot.publications?.C1NI6071E;
  const sequence = bank?.sequence;
  let state = previous.session !== session ? { ...emptyTrend(), session } : previous;
  if (Number.isSafeInteger(sequence) && Number.isSafeInteger(state.lastSequence)
      && sequence < state.lastSequence) state = { ...emptyTrend(), session };
  const rows = RULES.map((rule) => projectDisplay(rule, payload, elapsed, failure));
  const valid = rows.some((r) => r.quality === 'FRESH');
  const time = Date.parse(bank?.received_utc_on_everest || payload.observed_utc);
  const key = `${sequence}:${bank?.received_utc_on_everest || payload.observed_utc}`;
  if (!valid || !Number.isFinite(time)) {
    if (state.paused) return state;
    const samples = [...state.samples, { time: now, canon: null, section: null }]
      .filter((s) => s.time >= now - TREND_WINDOW_MS).slice(-TREND_MAX_POINTS);
    return { ...state, samples, paused: true };
  }
  if (key === state.lastKey) return state;
  const last = state.samples[state.samples.length - 1];
  const samples = last && time <= last.time ? [] : state.samples;
  const sample = { time,
    canon: rows[0].quality === 'FRESH' ? rows[0].value : null,
    section: rows[1].quality === 'FRESH' ? rows[1].value : null };
  return { session, lastKey: key, lastSequence: sequence, paused: false,
    samples: [...samples, sample].filter((s) => s.time >= time - TREND_WINDOW_MS).slice(-TREND_MAX_POINTS) };
}

export function temperaturePaths(samples, series, x, y) {
  let connected = false;
  let lastTime = null;
  return samples.map((s) => {
    if (!Number.isFinite(s[series])) { connected = false; lastTime = null; return ''; }
    const command = connected && s.time - lastTime <= TREND_GAP_MS ? 'L' : 'M';
    connected = true;
    lastTime = s.time;
    return `${command}${x(s.time).toFixed(2)},${y(s[series]).toFixed(2)}`;
  }).join(' ');
}
