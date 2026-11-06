import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

const API = '/api/pump-probe-vd2/live/rolling-average';

export default function VD2LiveAverage({ disabled = false, children, onReadError, onReadback }) {
  const [current, setCurrent] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [frames, setFrames] = useState('');
  const [pending, setPending] = useState(false);
  const [readError, setReadError] = useState('');
  const [actionError, setActionError] = useState('');
  const dirty = useRef(false);
  const alive = useRef(false);
  const active = useRef(false);
  const generation = useRef(0);
  const writing = useRef(false);
  const editVersion = useRef(0);
  const editTimer = useRef(null);
  const applyReadback = useCallback(payload => {
    setCurrent(payload);
    onReadback?.(payload);
    if (!dirty.current) { setEnabled(payload.enabled); setFrames(String(payload.frames)); }
    setReadError('');
    onReadError?.('');
  }, [onReadError, onReadback]);
  const refresh = useCallback(async () => {
    if (active.current || writing.current) return;
    active.current = true;
    const started = generation.current;
    try {
      const response = await fetch(API, { credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success || typeof payload.enabled !== 'boolean' || !Number.isInteger(payload.frames)
          || payload.frames < 2 || payload.frames > 255) throw new Error(payload.error || 'Live rolling average unavailable');
      if (alive.current && started === generation.current) applyReadback(payload);
    } catch (error) {
      if (alive.current && started === generation.current) {
        setCurrent(null); onReadback?.(null); setReadError(error.message); onReadError?.(error.message);
      }
    } finally { active.current = false; }
  }, [applyReadback, onReadError, onReadback]);
  useEffect(() => {
    alive.current = true;
    if (disabled) return () => { alive.current = false; window.clearTimeout(editTimer.current); };
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { alive.current = false; window.clearInterval(timer); window.clearTimeout(editTimer.current); };
  // Fluctuating Live status must not cancel an operator's pending frame edit.
  }, [refresh, disabled]);
  const save = async (nextEnabled = enabled, nextFrames = frames) => {
    window.clearTimeout(editTimer.current);
    if (disabled || writing.current || !current) return;
    const count = Number(nextFrames);
    if (!Number.isInteger(count) || count < 2 || count > 255) { setActionError('Choose 2–255 frames.'); return; }
    if (current.enabled === nextEnabled && current.frames === count) {
      dirty.current = false; setActionError(''); return;
    }
    writing.current = true;
    const version = editVersion.current;
    setPending(true);
    generation.current += 1;
    setActionError('');
    active.current = true;
    try {
      const response = await fetchWithHardwareApproval(API, { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: nextEnabled, frames: count }) });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Could not apply Live rolling average');
      if (payload.enabled !== nextEnabled || payload.frames !== count) throw new Error('Rolling average readback differs from the requested settings.');
      if (alive.current) { if (editVersion.current === version) dirty.current = false; applyReadback(payload); }
    } catch (error) {
      if (alive.current) { setCurrent(null); onReadback?.(null); setActionError(error.message); }
    } finally {
      active.current = false;
      writing.current = false;
      if (alive.current) setPending(false);
    }
  };
  return <form className="vd2-live-average" aria-label="Live rolling average" onSubmit={event => { event.preventDefault(); save(); }}>
    <label><input type="checkbox" checked={enabled} disabled={disabled || pending || !current}
      onChange={event => { const next = event.target.checked; dirty.current = true; editVersion.current += 1; setEnabled(next); save(next); }} />Rolling average</label>
    <label>Frames<input aria-label="Rolling average frames" type="number" min="2" max="255" step="1"
      value={frames} title="Applies automatically" disabled={disabled || pending || !current}
      onChange={event => {
        const next = event.target.value;
        dirty.current = true; editVersion.current += 1; setFrames(next);
        window.clearTimeout(editTimer.current);
        editTimer.current = window.setTimeout(() => save(enabled, next), 400);
      }} /></label>
    {children}
    <output aria-live="polite">{pending ? 'Applying…' : current ? `Current: ${current.enabled ? 'On' : 'Off'} · ${current.frames} frames` : 'Unavailable'}</output>
    {dirty.current && !pending && <small>Not applied</small>}
    {readError && <span role="alert">{readError}</span>}{actionError && <span role="alert">{actionError}</span>}
  </form>;
}
