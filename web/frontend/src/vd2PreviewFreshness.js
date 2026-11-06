// Compare source timestamps only with the HTTP server's clock. Elapsed time
// stays on the browser's monotonic clock, independent of its wall-clock offset.
export function createPreviewFreshnessClock(maxAgeMs = 1500) {
  let frame = null;
  let failure = '';
  return {
    observe(payload, { serverDate, startedAt, receivedAt }) {
      const id = payload.received_at;
      if (id && id === frame?.id) return;
      const sourceAt = Date.parse(id);
      // Some WSGI/proxy pairs send Date twice; Fetch joins those fields.
      const dates = String(serverDate || '').match(/\b[A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} GMT\b/g) || [];
      const serverAt = Math.max(...dates.map(value => Date.parse(value)));
      const duration = receivedAt - startedAt;
      const verified = Boolean(id) && Number.isFinite(sourceAt) && Number.isFinite(serverAt)
        && Number.isFinite(duration) && duration >= 0 && sourceAt <= serverAt + 1000;
      // HTTP Date has one-second precision. Use its upper bound and the whole
      // round trip so delayed/cached images are never made younger on receipt.
      frame = { id, receivedAt, ageMs: verified ? Math.max(0, serverAt + 1000 - sourceAt) + duration : null };
      failure = verified ? '' : 'Frame age could not be verified from server time.';
    },
    invalidate(reason) { failure = reason || 'No current frame.'; },
    status(now) {
      const ageMs = frame?.ageMs === null || !frame ? null : frame.ageMs + Math.max(0, now - frame.receivedAt);
      const fresh = !failure && ageMs !== null && ageMs < maxAgeMs;
      return { fresh, ageMs, reason: failure || (ageMs === null ? 'Waiting for a frame.'
        : fresh ? '' : `Latest received frame age bound: ${(ageMs / 1000).toFixed(1)} s.`) };
    },
  };
}
