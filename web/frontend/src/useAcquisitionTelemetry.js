import { useEffect, useState } from 'react';

export const TELEMETRY_POLL_MS = 500;

// Latest-only READ requests. A slow response consumes the polling period rather
// than adding another full period afterwards. Schedule only after settlement:
// even a hung request must never create overlapping requests or a catch-up burst.
export function useLatestRead(client, method, enabled = true, revision = 0) {
  const [state, setState] = useState({ payload: null, failure: '', elapsed: 0 });
  useEffect(() => {
    setState({ payload: null, failure: '', elapsed: 0 });
    if (!enabled) return undefined;
    if (typeof client?.[method] !== 'function') {
      setState({ payload: null, failure: 'Client de télémétrie indisponible.', elapsed: 0 });
      return undefined;
    }
    const abort = new AbortController();
    let timer;
    let receivedAt = null;
    const poll = async () => {
      const startedAt = performance.now();
      try {
        const payload = await client[method](abort.signal);
        if (!abort.signal.aborted) {
          receivedAt = performance.now();
          setState({ payload, failure: '', elapsed: 0 });
        }
      } catch (error) {
        if (!abort.signal.aborted) setState((old) => ({ ...old, failure: error.message || 'Lecture indisponible' }));
      } finally {
        if (!abort.signal.aborted) {
          const duration = Math.max(0, performance.now() - startedAt);
          timer = setTimeout(poll, Math.max(25, TELEMETRY_POLL_MS - duration));
        }
      }
    };
    poll();
    const clock = setInterval(() => {
      if (receivedAt !== null) setState((old) => ({ ...old, elapsed: Math.max(0, (performance.now() - receivedAt) / 1000) }));
    }, 250);
    return () => { abort.abort(); clearTimeout(timer); clearInterval(clock); };
  }, [client, method, enabled, revision]);
  return state;
}

// One latest-only poller feeds the header, live panels and raw diagnostics.
export default function useAcquisitionTelemetry(client, enabled = true, revision = 0) {
  return useLatestRead(client, 'telemetry', enabled, revision);
}
