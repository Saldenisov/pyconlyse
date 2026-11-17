import { useCallback, useEffect, useRef, useState } from 'react';
import { drawPreview, fetchVd2 } from '../PumpProbeVD2.API_BASE';
import { startPreviewPolling } from '../vd2PreviewPolling';

const API = '/api/pump-probe-vd2/dcam';

async function readDcam(action, options) {
  const response = await fetchVd2(API + action, options);
  const payload = await response.json();
  if (!response.ok || !payload.success) throw new Error(payload.error || 'DCAM request failed');
  return payload;
}

export default function VD2DcamReadout() {
  const [state, setState] = useState(null);
  const [requestActive, setRequestActive] = useState(false);
  const [lastBlank, setLastBlank] = useState(null);
  const [error, setError] = useState('');
  const [frameError, setFrameError] = useState('');
  const [received, setReceived] = useState(null);
  const [now, setNow] = useState(Date.now);
  const canvas = useRef(null);
  const lastStamp = useRef(null);

  const refresh = useCallback(async () => {
    try {
      setState(await readDcam('/state', { cache: 'no-store' }));
    } catch (failure) {
      setError(failure.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 1500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const live = Boolean(state?.live);
  useEffect(() => {
    if (!live) return undefined;
    const controller = new AbortController();
    const stop = startPreviewPolling(async () => {
      try {
        const { frame } = await readDcam('/preview', { signal: controller.signal, cache: 'no-store' });
        if (!controller.signal.aborted && frame && frame.received_at !== lastStamp.current
            && drawPreview(canvas.current, frame, 'grayscale', 0, 255)) {
          lastStamp.current = frame.received_at;
          setReceived(Date.now());
          setNow(Date.now());
          setFrameError('');
        }
      } catch (failure) {
        if (!controller.signal.aborted) setFrameError(failure.message);
      }
    }, 120);
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => {
      controller.abort();
      stop();
      window.clearInterval(timer);
      lastStamp.current = null;
    };
  }, [live]);

  async function run(action) {
    setRequestActive(true);
    setError('');
    try {
      const payload = await readDcam(action, { method: 'POST', credentials: 'include' });
      if (action === '/blank') setLastBlank(payload);
      await refresh();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setRequestActive(false);
    }
  }

  const busy = requestActive || state?.operation?.status === 'running';
  return (
    <main className="vd2-page">
      <a href="/pump-probe-vd2">VD2</a>
      <h1>VD2 DCAM dark readout</h1>
      <p>Sensor Live and raw blanks. Calibrated streak measurements require C13410 control.</p>
      <div className="vd2-live-actions" role="group" aria-label="DCAM controls">
        <button type="button" disabled={busy || !state || state.owned} onClick={() => run('/prepare')}>Prepare DCAM</button>
        <button type="button" disabled={busy || !state?.ready || live} onClick={() => {
          setReceived(null);
          setFrameError('');
          run('/live');
        }}>Live On</button>
        <button type="button" disabled={busy || !live} onClick={() => run('/stop')}>Live Off</button>
        <button type="button" disabled={busy || !state?.ready || live} onClick={() => run('/blank')}>Record dark blank</button>
        <button type="button" disabled={busy || !state?.owned} onClick={() => run('/unprepare')}>Unprepare DCAM</button>
      </div>
      <p role="status">{state?.operation?.status === 'running' ? state.operation.phase
        : live ? (received === null || now - received > 1500 ? 'Waiting for a new frame' : 'DCAM Live')
          : state?.ready ? state.model : state?.owned ? 'DCAM ownership retained. Unprepare to release.' : 'DCAM off'}</p>
      {(error || state?.operation?.error || (live && frameError)) &&
        <p role="alert">{error || state?.operation?.error || frameError}</p>}
      <div className="vd2-preview-canvas-wrap">
        <canvas className="vd2-preview-canvas" ref={canvas} aria-label="DCAM sensor preview" />
      </div>
      {lastBlank && <p role="status">Saved {lastBlank.shape[0]} raw frames · {lastBlank.output}</p>}
    </main>
  );
}
