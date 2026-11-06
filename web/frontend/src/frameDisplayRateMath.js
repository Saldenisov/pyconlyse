export function frameRateFromSamples(times, now, stride = 1) {
  const recent = times.filter(at => now - at <= 3000 * stride);
  if (recent.length < 2) return 0;
  const last = recent[recent.length - 1];
  if (now - last >= 1500 * stride) return 0;
  const span = last - recent[0];
  const interval = span / (recent.length - 1);
  // Time between frames is expected, not a missing frame. Decay only once the
  // next delivery is overdue, then reach zero if the stream stops.
  const overdue = Math.max(0, now - last - interval);
  return (recent.length - 1) * 1000 / Math.max(1, span + overdue);
}
