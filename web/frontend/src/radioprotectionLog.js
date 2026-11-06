import { useEffect, useRef } from 'react';
import { DISPLAY_RULES, projectDisplay } from './elyseLiveProjection';

const RULES = DISPLAY_RULES.filter((r) => r.page === 'radioprotection');

// Local diagnostic events only, not the native SUP journal or a safety audit.
// Retain only one 12-bit snapshot; no array of history, files, storage or POST.
export function nextRadioprotectionLog(previous, telemetry) {
  const { payload, elapsed, failure } = telemetry;
  const session = payload?.snapshot?.receiver_session;
  if (!session || !payload.snapshot.publications?.C4_IN_DIO96) return { state: previous, events: [] };
  const rows = RULES.map((r) => projectDisplay(r, payload, elapsed, failure));
  const quality = rows.find((r) => r.quality !== 'FRESH')?.quality || 'FRESH';
  const observed = payload.observed_utc || null;
  if (quality !== 'FRESH') return {
    state: { session, quality, values: null },
    events: previous?.quality === quality && previous.session === session ? []
      : [{ kind: 'quality', observed_utc: observed, receiver_session: session, quality }],
  };
  const values = rows.map((r) => r.value);
  const sameSession = previous?.session === session && previous.quality === 'FRESH';
  const events = sameSession ? rows.flatMap((r, index) => r.value === previous.values[index] ? [] : [{
    kind: 'observed_change', observed_utc: observed, receiver_session: session,
    source: `${r.bank}[${r.index}]`, field: r.label, before: previous.values[index], after: r.value,
  }]) : [{ kind: 'snapshot', observed_utc: observed, receiver_session: session,
    values: Object.fromEntries(rows.map((r) => [`${r.bank}[${r.index}]`, r.value])) }];
  return { state: { session, quality, values }, events };
}

export function useRadioprotectionLog(telemetry) {
  const previous = useRef(null);
  const { payload, elapsed, failure } = telemetry;
  useEffect(() => {
    const next = nextRadioprotectionLog(previous.current, { payload, elapsed, failure });
    previous.current = next.state;
    next.events.forEach((event) => console.info('[ELYSE Radioprotection · observation seulement]', event));
  }, [payload, elapsed, failure]);
}
