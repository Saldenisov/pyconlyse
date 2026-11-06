import { useEffect, useRef, useState } from 'react';

// Geometry belongs to this tab. Only the server computes kinetics and ΔI/I₀.
export function useVd2AlignmentReadout(frameId, context, region, windows) {
  const selection = JSON.stringify({ region, windows });
  const key = JSON.stringify([context, selection]);
  const autoKey = JSON.stringify([context, JSON.stringify({ region, windows: null })]);
  const frame = useRef(frameId);
  frame.current = frameId;
  const [result, setResult] = useState(null);
  const [failure, setFailure] = useState(null);
  const enabled = Boolean(frameId && context && region);
  useEffect(() => {
    if (!enabled) return undefined;
    let request = null;
    let attempted = null;
    let disposed = false;
    const read = async () => {
      const id = frame.current;
      if (!id || request || id === attempted) return;
      attempted = id;
      const controller = new AbortController();
      request = controller;
      const startedAt = performance.now();
      const timeout = window.setTimeout(() => controller.abort(), 3000);
      let status;
      try {
        const params = new URLSearchParams({ frame: id, selection });
        const response = await fetch(`/api/pump-probe-vd2/alignment/readout?${params}`, {
          credentials: 'include', cache: 'no-store', signal: controller.signal,
        });
        status = response.status;
        if (!response.ok && response.status === 404 && !response.headers?.get('Content-Type')?.includes('application/json')) {
          throw new Error('Alignment readout requires the updated Web server.');
        }
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Alignment readout unavailable.');
        if (payload.version !== 1 || payload.profile?.frameId !== id) throw new Error('Invalid Alignment readout response.');
        const receivedAt = performance.now();
        if (!disposed) {
          setResult({ key, context, payload, receivedAt, transit: receivedAt - startedAt,
            receivedWallAt: Date.now() });
          setFailure(null);
        }
      } catch (error) {
        if (!disposed) {
          if (controller.signal.aborted || error instanceof TypeError) attempted = null;
          setFailure({ key, message: controller.signal.aborted ? 'Alignment readout timed out.' : error.message,
            invalid: status === 422 });
        }
      } finally {
        window.clearTimeout(timeout);
        request = null;
      }
    };
    // Allow an in-flight request to finish while preview advances. Edits
    // supersede the request immediately and are debounced during cursor drags.
    const debounce = window.setTimeout(() => { read(); timer = window.setInterval(read, 40); }, 80);
    let timer;
    return () => { disposed = true; window.clearTimeout(debounce); window.clearInterval(timer); request?.abort(); };
  }, [enabled, key, context, selection]);
  const matches = result?.key === key || (result?.key === autoKey &&
    JSON.stringify(result.payload.windows) === JSON.stringify(windows));
  return {
    result: enabled && matches && !(failure?.key === key && failure.invalid) ? result : null,
    profile: enabled && result?.context === context ? result.payload.profile : null,
    error: enabled && failure?.key === key ? failure.message : '',
  };
}
