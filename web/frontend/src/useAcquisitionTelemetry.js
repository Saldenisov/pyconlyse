import { useEffect, useState } from 'react';

// One latest-only poller can feed the header, live panels and raw diagnostics.
export default function useAcquisitionTelemetry(client, enabled = true, revision = 0) {
  const [state, setState] = useState({ payload: null, failure: '', elapsed: 0 });
  useEffect(() => {
    setState({ payload: null, failure: '', elapsed: 0 });
    if (!enabled) return undefined;
    if (typeof client?.telemetry !== 'function') {
      setState({ payload: null, failure: 'Client de télémétrie indisponible.', elapsed: 0 });
      return undefined;
    }
    const abort = new AbortController();
    let timer;
    let receivedAt = null;
    const poll = async () => {
      try {
        const payload = await client.telemetry(abort.signal);
        if (!abort.signal.aborted) {
          receivedAt = performance.now();
          setState({ payload, failure: '', elapsed: 0 });
        }
      } catch (error) {
        if (!abort.signal.aborted) setState((old) => ({ ...old, failure: error.message || 'Lecture indisponible' }));
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(poll, 1000);
      }
    };
    poll();
    const clock = setInterval(() => {
      if (receivedAt !== null) setState((old) => ({ ...old, elapsed: Math.max(0, (performance.now() - receivedAt) / 1000) }));
    }, 250);
    return () => { abort.abort(); clearTimeout(timer); clearInterval(clock); };
  }, [client, enabled, revision]);
  return state;
}
