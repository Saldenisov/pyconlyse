// One request at a time; absolute deadlines prevent timer/rendering delays
// accumulating on every cycle. Slow reads never create a catch-up queue.
export function startPreviewPolling(readFrame, period = 190, retryWaiting = false) {
  let stopped = false;
  let timer;
  let due = performance.now();
  let retries = 0;
  const poll = async (retry = false) => {
    const result = await readFrame();
    if (stopped) return;
    const now = performance.now();
    if (!retry) {
      due = Math.max(due + period, now);
      retries = 0;
    }
    const remaining = Math.max(0, due - now);
    const backoff = 20 * (retries + 1);
    const retryable = result === true || (retryWaiting && result === 'waiting_for_frame');
    if (retryable && retries < 3 && backoff < remaining) {
      retries += 1;
      timer = window.setTimeout(() => poll(true), backoff);
    } else {
      timer = window.setTimeout(poll, remaining);
    }
  };
  poll();
  return () => { stopped = true; window.clearTimeout(timer); };
}
