import policy from './coolingTemperaturePolicy.json';

export { policy as TEMPERATURE_POLICY };
const freshState = () => ({ samples: [], setpoint: null, pending: null, clearing: null, active: false,
  detail: {}, lastKey: null, lastTime: null });
export const newTemperatureWatch = () => Object.fromEntries(['CANON', 'SECTION'].map((name) => [name, freshState()]));

// Raw endpoint deviations, not an averaged temperature or a physical trip.
export function observeTemperature(watch, operating, readings, now) {
  const quality = {};
  Object.keys(watch).forEach((name) => {
    let state = watch[name];
    if (operating === false) { watch[name] = freshState(); quality[name] = 'DISARMED'; return; }
    const reading = readings?.[name];
    if (operating !== true || !reading || !Number.isFinite(reading.temperature) || !Number.isFinite(reading.setpoint)) {
      state.pending = null; state.clearing = null; quality[name] = 'UNKNOWN'; return;
    }
    const { temperature, setpoint, key, session } = reading;
    quality[name] = 'FRESH';
    if ((state.setpoint !== null && Math.abs(setpoint - state.setpoint) >= policy.setpoint_change_c)
      || (state.session !== undefined && session !== state.session)) { state = freshState(); watch[name] = state; }
    state.session = session; state.setpoint = setpoint;
    const deviation = temperature - setpoint;
    state.samples = state.samples.filter((s) => s.time >= now - policy.window_seconds);
    const last = state.samples[state.samples.length - 1];
    if (key !== state.lastKey && (!last || now - last.time >= 1)) {
      state.samples.push({ time: now, deviation }); state.lastKey = key;
    }
    if (state.lastTime !== null && now - state.lastTime > 2) { state.pending = null; state.clearing = null; }
    state.lastTime = now;
    const earlier = state.samples.filter((s) => now - s.time >= policy.minimum_span_seconds).map((s) => s.deviation);
    const rise = earlier.length ? deviation - Math.min(...earlier) : null;
    const qualifies = deviation >= policy.excess_c && rise !== null && rise >= policy.rise_c;
    if (!state.active) {
      if (qualifies) {
        if (state.pending === null) state.pending = now;
        if (now - state.pending >= policy.persistence_seconds) state.active = true;
      } else state.pending = null;
    }
    if (state.active) {
      if (deviation <= policy.excess_c - policy.clear_margin_c) {
        if (state.clearing === null) state.clearing = now;
        if (now - state.clearing >= policy.clear_seconds) { state.active = false; state.pending = null; state.clearing = null; }
      } else state.clearing = null;
    }
    state.detail = { circuit: name, temperature_c: temperature, setpoint_c: setpoint,
      deviation_c: deviation, rise_c: rise, window_seconds: policy.window_seconds };
  });
  return { warnings: Object.entries(watch).filter(([, s]) => s.active)
    .map(([name, s]) => ({ ...s.detail, quality: quality[name] })), quality };
}
