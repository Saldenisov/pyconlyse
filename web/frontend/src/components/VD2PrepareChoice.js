import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';

const choices = [
  ['previous', 'Previous camera configuration'],
  ['alignment', 'Return to Alignment'],
  ['point', 'Previous measurement point'],
  ['default', 'Standard preparation · 1 us on cold startup'],
];

export default function VD2PrepareChoice({onCancel, onConfirm}) {
  const [options, setOptions] = useState(null);
  const [selected, setSelected] = useState('alignment');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const cancel = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    cancel.current?.focus();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    let active = true;
    (async () => {
      try {
        const response = await fetch('/api/pump-probe-vd2/recovery/options', {credentials: 'include', signal: controller.signal});
        if(response.status===404)throw new Error('Saved camera configurations require a Web update.');
        const payload = await response.json();
        if (!response.ok || !payload.success || !payload.options) throw new Error(payload.error || 'Saved camera configurations require a Web update.');
        if (active) {setOptions(payload.options); setSelected(payload.options.previous ? 'previous' : 'alignment');}
      } catch (cause) {
        if (active) {setError(cause.name === 'AbortError' ? 'Saved camera configurations timed out.' : cause.message); setSelected('default');}
      } finally {clearTimeout(timer); if (active) setLoading(false);}
    })();
    return () => {active = false; controller.abort(); clearTimeout(timer); previous?.focus();};
  }, []);
  const confirm = () => {
    if (loading || (selected !== 'default' && !options)) return;
    onConfirm(selected === 'default' ? undefined : {restore_mode: selected, restore_id: options[selected]?.id || null});
  };
  const keyDown = event => {
    if (event.key === 'Escape') {event.preventDefault(); onCancel();}
    if (event.key === 'Tab') {
      const elements = Array.from(event.currentTarget.querySelectorAll('button:not(:disabled),input:not(:disabled)'));
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
    }
  };
  return createPortal(<div className="experiment-confirmation-backdrop">
    <section className="experiment-shutdown-confirmation experiment-restore-choice" role="dialog" aria-modal="true"
      aria-labelledby="vd2-prepare-choice-title" onKeyDown={keyDown}>
      <h2 id="vd2-prepare-choice-title">Prepare VD2 · return to</h2>
      {loading && <p role="status">Reading saved camera configurations…</p>}
      {error && <p role="alert">{error} Standard preparation is available; no saved settings will be applied.</p>}
      {choices.map(([key, label]) => {
        const saved = options?.[key];
        const disabled = loading || (['previous', 'point'].includes(key) && !saved) || (key === 'alignment' && !options);
        return <label key={key} className={`experiment-restore-option${disabled ? ' is-disabled' : ''}`}>
          <input type="radio" name="vd2-return-to" value={key} checked={selected === key} disabled={disabled}
            onChange={() => setSelected(key)} />
          <span>{label}<small>{saved
            ? `${saved.settings.time_range} · ${saved.settings.streak_mode} · ${new Date(saved.created_at).toLocaleString()}`
            : key === 'alignment' ? '1 us · saved regions in this browser' : key === 'default' ? 'Keep current settings if already ready' : 'No saved return point yet'}</small></span>
        </label>;
      })}
      <p>Camera settings are verified after recovery. Acquisition stays stopped. Shutters, magnets and stages are not restored.</p>
      <div className="experiment-confirmation-actions">
        <button ref={cancel} type="button" className="experiment-confirmation-cancel" onClick={onCancel}>Cancel</button>
        <button type="button" className="experiment-prepare-button" disabled={loading} onClick={confirm}>Prepare VD2</button>
      </div>
    </section>
  </div>, document.body);
}
