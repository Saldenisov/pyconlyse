import { useEffect, useState } from 'react';

export const TELEMETRY_POLL_MS = 500;
export const TELEMETRY_READ_DEADLINE_MS = 3000;
const READ_TIMEOUT = 'Délai de lecture dépassé (3 s). Nouvelle tentative automatique.';

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
    let disposed = false;
    let activeRequest;
    let deadline;
    let timer;
    let receivedAt = null;
    const poll = async () => {
      const startedAt = performance.now();
      const request = new AbortController();
      activeRequest = request;
      let timedOut = false;
      deadline = setTimeout(() => {
        timedOut = true;
        request.abort();
        if (!disposed) setState((old) => ({ ...old, failure: READ_TIMEOUT }));
      }, TELEMETRY_READ_DEADLINE_MS);
      try {
        const payload = await client[method](request.signal);
        if (!disposed && !request.signal.aborted) {
          receivedAt = performance.now();
          setState({ payload, failure: '', elapsed: 0 });
        }
      } catch (error) {
        if (!disposed) setState((old) => ({ ...old,
          failure: timedOut ? READ_TIMEOUT : error.message || 'Lecture indisponible' }));
      } finally {
        clearTimeout(deadline);
        // Native fetch settles when aborted. A client ignoring cancellation must
        // still settle before another read starts; never overlap or accept it late.
        if (!disposed) {
          const duration = Math.max(0, performance.now() - startedAt);
          timer = setTimeout(poll, Math.max(25, TELEMETRY_POLL_MS - duration));
        }
      }
    };
    poll();
    const clock = setInterval(() => {
      if (receivedAt !== null) setState((old) => ({ ...old, elapsed: Math.max(0, (performance.now() - receivedAt) / 1000) }));
    }, 250);
    return () => {
      disposed = true;
      activeRequest?.abort();
      clearTimeout(deadline);
      clearTimeout(timer);
      clearInterval(clock);
    };
  }, [client, method, enabled, revision]);
  return state;
}

// One latest-only poller feeds the header, live panels and raw diagnostics.
export default function useAcquisitionTelemetry(client, enabled = true, revision = 0) {
  return useLatestRead(client, 'telemetry', enabled, revision);
}
