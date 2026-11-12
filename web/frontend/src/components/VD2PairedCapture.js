import { useEffect, useState } from 'react';
import { API_BASE, fetchVd2, roiBounds } from '../PumpProbeVD2.API_BASE';

const STOP_LABELS = {
  precision_reached: 'Target reached',
  pair_count_reached: 'Pair count reached',
  pair_limit: 'Pair limit reached before the target',
  operator_stop: 'Stopped by operator',
};

export default function VD2PairedCapture({ available, run, settings, disabled, roi, preview, onUpdate, onStop }) {
  const [mode, setMode] = useState('fixed');
  const [first, setFirst] = useState(true);
  const [pairs, setPairs] = useState('200');
  const [limit, setLimit] = useState('5000');
  const [target, setTarget] = useState('2');
  const [trigger, setTrigger] = useState('external_rising');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const active = Boolean(run?.active);
  const currentMode = active ? run.mode : mode;
  const pairLimit = Number(mode === 'fixed' ? pairs : limit);
  const validTarget = Number(target) > 0 && Number(target) <= 1000;
  const selected = roi && preview?.width > 0 && preview?.height > 0 ? {
    ...Object.fromEntries(Object.entries(roiBounds(roi, preview.width, preview.height))
      .map(([key, value]) => [key, Math.round(value)])),
    width: preview.width, height: preview.height,
  } : null;

  useEffect(() => {
    if (run?.active && run?.mode === 'precision') setTarget(String(run.target_mod));
  }, [run?.active, run?.mode, run?.target_mod]);

  if (!available) return null;
  const send = async (action, body) => {
    setPending(true);
    setError('');
    try {
      const response = await fetchVd2(API_BASE + '/paired/' + action, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Paired acquisition request failed');
      onUpdate(payload.paired);
    } catch (exc) {
      setError(exc.message);
    } finally {
      setPending(false);
    }
  };
  const start = () => send('start', {
    output_root: settings.outputRoot,
    sample_name: settings.runName,
    reuse_bruit: settings.reuseBruit === 'none' ? 'none' : 'latest',
    mode,
    first_map_with_electrons: first,
    pair_limit: pairLimit,
    target_mod: mode === 'precision' ? Number(target) : null,
    trigger_source: trigger,
    roi: selected,
  });
  const locked = active || disabled || pending;
  const cannotStart = locked || !settings.runName?.trim() || !Number.isInteger(pairLimit)
    || pairLimit < 1 || pairLimit > 10000 || (mode === 'precision' && (!selected || !validTarget));
  return (
    <section className="vd2-phase-protocol" aria-label="Paired ABS/BASE acquisition">
      <header><h2>Paired ABS/BASE · 10 Hz</h2><small role="status">{run?.stage || STOP_LABELS[run?.stop_reason] || ''}</small></header>
      <div className="vd2-protocol-settings">
        <label><span>Stop condition</span><select value={currentMode} disabled={locked} onChange={event => setMode(event.target.value)}>
          <option value="fixed">Fixed pair count</option>
          <option value="precision">Target ROI error</option>
        </select></label>
        <label><span>{currentMode === 'fixed' ? 'Pairs' : 'Pair limit'}</span><input type="number" min="1" max="10000" step="1"
          value={active ? run.pair_limit : mode === 'fixed' ? pairs : limit} disabled={locked}
          onChange={event => (mode === 'fixed' ? setPairs : setLimit)(event.target.value)} /></label>
        <label><span>5 Hz sync</span><select value={active ? run.trigger_source : trigger} disabled={locked} onChange={event => setTrigger(event.target.value)}>
          <option value="external_rising">External rising</option>
          <option value="external_falling">External falling</option>
          <option value="internal">Internal</option>
        </select></label>
        <label><input type="checkbox" checked={active ? run.first_map_with_electrons : first}
          disabled={locked} onChange={event => setFirst(event.target.checked)} /> First frame with electrons</label>
        {currentMode === 'precision' && <label><span>Target error (mOD)</span>
          <input type="number" min="0.001" max="1000" step="any" value={target}
            disabled={pending || (active ? run.status === 'saving' : disabled)} onChange={event => setTarget(event.target.value)} />
        </label>}
      </div>
      {mode === 'precision' && !active && !selected && <small>Select a region on the Acquisition image.</small>}
      <div className="vd2-phase-buttons">
        <button type="button" className="vd2-measure-button" disabled={cannotStart} onClick={start}>Measure pairs</button>
        {active && <button type="button" className="vd2-stop" disabled={pending || run.status === 'saving'} onClick={onStop}>Stop pairs</button>}
        {active && currentMode === 'precision' && <button type="button"
          disabled={pending || run.status === 'saving' || !validTarget || Number(target) === run.target_mod}
          onClick={() => send('target', { job_id: run.job_id, target_mod: Number(target) })}>Set target</button>}
      </div>
      {run?.job_id && <div aria-live="polite">
        {run.pairs_recorded} / {run.pair_limit} pairs
        {Number.isFinite(run.estimate_mod) && <span> · ΔOD {run.estimate_mod.toFixed(2)} mOD</span>}
        {run.mode === 'precision' && Number.isInteger(run.roi_pairs) && run.roi_pairs !== run.pairs_recorded
          && <span> · {run.roi_pairs} contiguous ROI pairs</span>}
        {run.mode === 'precision' && <span> · ROI error {Number.isFinite(run.error_mod) ? run.error_mod.toFixed(2) + ' mOD' : 'estimating'}</span>}
      </div>}
      {(error || run?.error) && <small role="alert">{error || run.error}</small>}
      {run?.manifest_warning && <small role="alert">{run.manifest_warning}</small>}
      {run?.h5_path && !active && <small title={run.h5_path}>{run.h5_path}</small>}
    </section>
  );
}
