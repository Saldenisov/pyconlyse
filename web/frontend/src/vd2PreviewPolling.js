// One request at a time; absolute deadlines prevent timer/rendering delays
// accumulating on every cycle. Slow reads never create a catch-up queue.
export function startPreviewPolling(readFrame, period = 190) {
  let stopped = false;
  let timer;
  let due = performance.now();
  const poll = async () => {
    await readFrame();
    if (stopped) return;
    const now = performance.now();
    due = Math.max(due + period, now);
    timer = window.setTimeout(poll, Math.max(0, due - now));
  };
  poll();
  return () => { stopped = true; window.clearTimeout(timer); };
}
