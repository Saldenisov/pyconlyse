import { useCallback, useEffect, useMemo, useState } from 'react';
import { DISPLAY_RULES, projectDisplay } from './elyseLiveProjection';

const RULES = DISPLAY_RULES.filter((r) => (r.page === 'vide' && r.kind === 'number') || ['fluides:5', 'fluides:22'].includes(r.id));
export const HISTORY_WINDOWS = [5, 15, 30, 60, 120];
const key = (sample) => `${sample.session}:${sample.receipt}`;

export function mergeHistory(previous, incoming, minutes, now = Date.now()) {
  const merged = new Map();
  [...previous, ...incoming].forEach((sample) => {
    if (Number.isFinite(sample.time) && sample.time >= now - minutes * 60000
        && sample.time <= now + 1000 && typeof sample.session === 'string' && typeof sample.receipt === 'string') merged.set(key(sample), sample);
  });
  // Match the server's one-display-sample-per-second contract. Faster live
  // polling must not fill a 30-minute buffer in 15 minutes. Retain the latest
  // actual sample, its timestamp and receipt; never average or interpolate.
  const seconds = new Map();
  [...merged.values()].sort((a, b) => a.time - b.time).forEach((sample) => {
    seconds.set(`${sample.session}:${Math.floor(sample.time / 1000)}`, sample);
  });
  return [...seconds.values()].slice(-minutes * 60);
}

export function liveHistorySample(telemetry) {
  if (telemetry.failure) return null;
  const snapshot = telemetry.payload?.snapshot;
  if (!snapshot?.receiver_session || !Number.isSafeInteger(snapshot.received_this_process)) return null;
  const sample = { time: Date.parse(telemetry.payload.observed_utc), session: snapshot.receiver_session,
    receipt: String(snapshot.received_this_process), canon: null, section: null };
  if (!Number.isFinite(sample.time)) return null;
  RULES.forEach((rule) => {
    const row = projectDisplay(rule, telemetry.payload, telemetry.elapsed, telemetry.failure);
    sample[rule.id === 'fluides:5' ? 'canon' : rule.id === 'fluides:22' ? 'section' : rule.id] = row.value;
  });
  return RULES.some((rule) => Number.isFinite(sample[rule.id === 'fluides:5' ? 'canon' : rule.id === 'fluides:22' ? 'section' : rule.id])) ? sample : null;
}

export default function useSupervisionHistory(client, telemetry, enabled) {
  const { payload, failure, elapsed } = telemetry;
  const [minutes, setMinutes] = useState(() => {
    try { const saved = Number(localStorage.getItem('elyse.history.windowMinutes')); return HISTORY_WINDOWS.includes(saved) ? saved : 30; }
    catch { return 30; }
  });
  const [samples, setSamples] = useState([]);
  const [storage, setStorage] = useState('ram');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!enabled || typeof client.history !== 'function') return undefined;
    const abort = new AbortController();
    let timer;
    const read = async () => {
      try {
        const result = await client.history(minutes, abort.signal);
        if (!abort.signal.aborted) {
          if (!Array.isArray(result.samples) || result.storage !== 'server_sqlite') throw new Error('Contrat historique invalide');
          setSamples((old) => mergeHistory(old, result.samples, minutes));
          setStorage(result.storage); setError(result.error || '');
        }
      } catch (failure) {
        if (!abort.signal.aborted) setError(failure.message);
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(read, 5000);
      }
    };
    read();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [client, enabled, minutes]);
  useEffect(() => {
    const sample = liveHistorySample({ payload, failure, elapsed });
    if (sample) setSamples((old) => {
      const last = old[old.length - 1];
      return last && key(last) === key(sample) && last.time === sample.time
        ? old : mergeHistory(old, [sample], minutes);
    });
  }, [payload, failure, elapsed, minutes]);
  const changeMinutes = useCallback((value) => {
    if (!HISTORY_WINDOWS.includes(value)) return;
    setMinutes(value);
    setSamples((old) => mergeHistory(old, [], value));
    try { localStorage.setItem('elyse.history.windowMinutes', String(value)); } catch { /* Display preference, not authority. */ }
  }, []);
  const paused = Boolean(failure) || payload?.quality !== 'FRESH';
  return useMemo(() => ({ samples, storage, error, minutes, changeMinutes, paused }),
    [samples, storage, error, minutes, changeMinutes, paused]);
}
