import { useEffect, useState } from 'react';
import { acqRuntimeClient, ageAcqRuntime, validateAcqRuntime } from './api/acqRuntimeClient';

const initial = { payload: null, failure: '', elapsed: 0, sessionChanged: false, retrySeconds: 0 };

// Latest-only, no overlapping requests and no retained measurements after failure.
export default function useAcqRuntime(client = acqRuntimeClient) {
  const [state, setState] = useState(initial);
  useEffect(() => {
    setState(initial);
    const abort = new AbortController();
    let timer;
    let receivedAt = null;
    let previousSession = null;
    let failures = 0;
    let sessionChanged = false;
    const poll = async () => {
      try {
        if (typeof client?.status !== 'function') throw new Error('Client Python Acquisition indisponible.');
        const payload = validateAcqRuntime(await client.status(abort.signal));
        if (abort.signal.aborted) return;
        sessionChanged = sessionChanged || Boolean(previousSession && payload.session_id && previousSession !== payload.session_id);
        if (payload.session_id) previousSession = payload.session_id;
        receivedAt = performance.now();
        failures = 0;
        setState({ payload: ageAcqRuntime(payload, 0), failure: '', elapsed: 0, sessionChanged, retrySeconds: 0 });
      } catch (error) {
        if (abort.signal.aborted) return;
        receivedAt = null;
        failures = Math.min(failures + 1, 5);
        setState({ payload: null, failure: error.message || 'Lecture Python Acquisition indisponible.',
          elapsed: 0, sessionChanged, retrySeconds: Math.min(30, 2 ** failures) });
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(poll, failures ? Math.min(30000, (2 ** failures) * 1000) : 1000);
      }
    };
    poll();
    const clock = setInterval(() => {
      if (receivedAt === null) return;
      const elapsed = Math.max(0, (performance.now() - receivedAt) / 1000);
      setState((old) => ({ ...old, elapsed, payload: ageAcqRuntime(old.payload, elapsed) }));
    }, 250);
    return () => { abort.abort(); clearTimeout(timer); clearInterval(clock); };
  }, [client]);
  return state;
}
