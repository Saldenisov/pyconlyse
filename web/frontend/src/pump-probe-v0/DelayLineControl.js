import React, { useEffect, useRef, useState } from 'react';
import { STAGE_MIN_MM, STAGE_MAX_MM } from './shared';

export default function DelayLineControl({ positionMm, targetMm, disabled, onMove, onStop }) {
  const [draft, setDraft] = useState(String(targetMm ?? positionMm));
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const inFlight = useRef(false);
  useEffect(() => {
    if (!dirty && !pending) setDraft(String(targetMm ?? positionMm));
  }, [targetMm, positionMm, dirty, pending]);

  const move = async event => {
    event.preventDefault();
    if (disabled || inFlight.current) return;
    const value = Number(draft);
    if (!draft.trim() || !Number.isFinite(value) || value < STAGE_MIN_MM || value > STAGE_MAX_MM) {
      setError(`Enter a target between ${STAGE_MIN_MM} and ${STAGE_MAX_MM} mm`);
      return;
    }
    inFlight.current = true; setPending(true); setError('');
    try {
      const result = await onMove(value);
      if (result) setDirty(false);
    } catch (failure) {
      setError(failure.message || 'Move was not accepted');
    } finally {
      inFlight.current = false; setPending(false);
    }
  };
  return <section className="pp-delay-line-control" aria-label="OWIS delay line">
    <h2 className="pp-alignment-heading">OWIS delay line</h2>
    <form onSubmit={move}>
      <label>Target, mm<input type="number" step="any" min={STAGE_MIN_MM} max={STAGE_MAX_MM}
        aria-label="OWIS delay target mm" value={draft} disabled={disabled || pending}
        onChange={event => { setDraft(event.target.value); setDirty(true); setError(''); }} /></label>
      <button type="submit" disabled={disabled || pending}>{pending ? 'Sending…' : 'Move to position'}</button>
      <button type="button" onClick={onStop}>Stop</button>
    </form>
    <small>Current: {Number(positionMm).toFixed(3)} mm</small>
    {error && <p role="alert">{error}</p>}
  </section>;
}
