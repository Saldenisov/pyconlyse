import { useCallback, useEffect, useRef, useState } from 'react';
import { frameRateFromSamples } from './frameDisplayRateMath';

export function createFrameDisplayMeter(stride = 1) {
  let times = [];
  let lastIdentity;
  return {
    reset() { times = []; lastIdentity = undefined; },
    record(identity, now) {
      if (identity === undefined || identity === null || identity === lastIdentity) return;
      lastIdentity = identity;
      times = [...times.filter(at => now - at <= 3000 * stride), now];
    },
    rate(now) {
      return frameRateFromSamples(times, now, stride);
    },
  };
}

// Call only after successful Canvas output, with a stable identity for the
// displayed frame. LUT/overlay redraws and cached responses are not new frames.
export default function useFrameDisplayRate(streamKey, enabled = true, stride = 1) {
  const meter = useRef(null);
  if (!meter.current) meter.current = createFrameDisplayMeter(stride);
  const currentStream = useRef(streamKey);
  currentStream.current = streamKey;
  const active = useRef(enabled);
  active.current = enabled;
  const [sample, setSample] = useState({ stream: streamKey, hz: 0 });
  useEffect(() => {
    meter.current = createFrameDisplayMeter(stride);
    setSample({ stream: streamKey, hz: 0 });
  }, [streamKey, enabled, stride]);
  useEffect(() => {
    if (!enabled) return undefined;
    const timer = setInterval(() => setSample({ stream: streamKey, hz: meter.current.rate(performance.now()) }), 250);
    return () => clearInterval(timer);
  }, [streamKey, enabled]);
  const frameDisplayed = useCallback((identity, source) => {
    if (!active.current || (source !== undefined && currentStream.current !== source)) return;
    const now = performance.now();
    meter.current.record(identity, now);
    setSample({ stream: currentStream.current, hz: meter.current.rate(now) });
  }, []);
  return { hz: enabled && sample.stream === streamKey ? sample.hz : 0, frameDisplayed };
}
