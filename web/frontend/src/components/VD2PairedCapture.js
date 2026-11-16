import { useEffect, useState } from 'react';
import { API_BASE, fetchVd2, ProfilePlot, roiBounds } from '../PumpProbeVD2.API_BASE';

const METHODS = [
  ['lamp_matched', 'Match BASE by lamp intensity'],
  ['sam_matched', 'SAM + matched BASE → OD of means'],
  ['mean_pair_od', 'Mean OD of adjacent pairs'],
  ['od_of_means', 'OD of mean ABS and BASE'],
  ['sam_od_of_means', 'SAM → OD of means'],
];

const STOP_LABELS = {
  precision_reached: 'Target reached',
  pair_count_reached: 'Pair count reached',
  pair_limit: 'Pair limit reached before the target',
  operator_stop: 'Stopped by operator',
};

export default function VD2PairedCapture({
  available, run, settings, disabled, roi, preview, protocol, onUpdate, onStop, onBruit,
  cameraIdle, live, liveBlocked, onLive, correction, correctionRange, correctionFixed,
  referenceConfirmed, canFixCorrection, canConfirmReference,
  onChangeCorrection, onFixCorrection, onConfirmReference,
}) {
  const [mode, setMode] = useState('fixed');
  const [first, setFirst] = useState(true);
  const [pairs, setPairs] = useState('200');
  const [limit, setLimit] = useState('5000');
  const [target, setTarget] = useState('2');
  const [trigger, setTrigger] = useState('external_rising');
  const [method, setMethod] = useState('lamp_matched');
  const [samSurface, setSamSurface] = useState('3');
  const [bruitAttempt, setBruitAttempt] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const active = Boolean(run?.active);
  const currentMode = active ? run.mode : mode;
  const pairLimit = Number(mode === 'fixed' ? pairs : limit);
  const validTarget = Number(target) > 0 && Number(target) <= 1000;
  const band = active ? run.band : correctionRange.band;
  const spectralBand = active ? band : correctionRange.spectralBand;
  const needsBruit = run?.status === 'bruit_required' && run.sample_name === settings.runName;
  const bruitReady = bruitAttempt && protocol?.job_id !== bruitAttempt.prior
    && protocol?.phase === 'BRUIT' && protocol?.sample_name === settings.runName && protocol?.status === 'completed';
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
    band,
    method,
    sam_surface_percent: method.startsWith('sam_') ? Number(samSurface) : 3,
  });
  const control = async (path, body, next) => {
    setPending(true);
    setError('');
    try {
      const response = await fetchVd2(API_BASE + path, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Shutter operation failed');
      await next();
    } catch (exc) {
      setError(exc.message);
    } finally {
      setPending(false);
    }
  };
  const recordBruit = () => control('/parameter/streak_shutter', { value: 'Closed' }, () => {
    setBruitAttempt({ prior: protocol?.job_id });
    onBruit();
  });
  const resume = () => control('/alignment/open-shutters', {}, async () => {
    setBruitAttempt(null);
    await start();
  });
  const locked = active || disabled || pending;
  const displayedCenter = active ? band?.center_nm : correctionRange.center ?? correction.center;
  const displayedBandwidth = active && band ? 2 * band.half_width_nm : correctionRange.bandwidth ?? correction.bandwidth;
  const cannotStart = locked || !cameraIdle || !settings.runName?.trim() || !Number.isInteger(pairLimit)
    || pairLimit < 1 || pairLimit > 10000 || !band || !correctionFixed || !referenceConfirmed
    || (method.startsWith('sam_') && !(Number(samSurface) > 0 && Number(samSurface) <= 100))
    || (mode === 'precision' && !validTarget);
  return (
    <section className="vd2-phase-protocol" aria-label="Paired ABS/BASE acquisition">
      <header><h2>Paired ABS/BASE · 10 Hz</h2><small role="status">{run?.stage || STOP_LABELS[run?.stop_reason] || ''}</small></header>
      <div className="vd2-protocol-settings">
        <label><span>Stop condition</span><select value={currentMode} disabled={locked} onChange={event => setMode(event.target.value)}>
          <option value="fixed">Fixed pair count</option>
          <option value="precision">Target error across kinetics</option>
        </select></label>
        <label><span>{currentMode === 'fixed' ? 'Pairs' : 'Pair limit'}</span><input type="number" min="1" max="10000" step="1"
          value={active ? run.pair_limit : mode === 'fixed' ? pairs : limit} disabled={locked}
          onChange={event => (mode === 'fixed' ? setPairs : setLimit)(event.target.value)} /></label>
        <label><span>5 Hz sync</span><select value={active ? run.trigger_source : trigger} disabled={locked} onChange={event => setTrigger(event.target.value)}>
          <option value="external_rising">External rising</option>
          <option value="external_falling">External falling</option>
          <option value="internal">Internal</option>
        </select></label>
        <div className="vd2-paired-live">
          <label><input type="checkbox" checked={active ? run.first_map_with_electrons : first}
            disabled={locked} onChange={event => setFirst(event.target.checked)} /> First frame with electrons</label>
          <button type="button" aria-pressed={live} disabled={locked || liveBlocked || (!live && !cameraIdle)}
            onClick={onLive}>Live</button>
        </div>
        <label><span>OD method</span><select value={active ? run.method : method} disabled={locked} onChange={event => setMethod(event.target.value)}>
          {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        {method.startsWith('sam_') && <label><span>SAM intensity tolerance (%)</span>
          <input type="number" min="0.1" max="100" step="any" value={samSurface} disabled={locked}
            onChange={event => setSamSurface(event.target.value)} /></label>}
        {currentMode === 'precision' && <label><span>Maximum error (mOD)</span>
          <input type="number" min="0.001" max="1000" step="any" value={target}
            disabled={pending || (active ? run.status === 'saving' : disabled)} onChange={event => setTarget(event.target.value)} />
        </label>}
      </div>
      <fieldset className={`vd2-spectral-correction ${correctionFixed || active ? 'is-fixed' : ''}`}>
        <legend>Spectral Correction Range</legend>
        <div className="vd2-protocol-settings">
          <label><span>Center (nm)</span><input type="number" min="1" step="any" value={displayedCenter ?? ''}
            disabled={locked || correctionFixed} onChange={event => onChangeCorrection('center', event.target.value)} /></label>
          <label><span>Bandwidth (nm)</span><input type="number" min="0.1" step="any" value={displayedBandwidth ?? ''}
            disabled={locked || correctionFixed} onChange={event => onChangeCorrection('bandwidth', event.target.value)} /></label>
          <button type="button" disabled={locked || (!correctionFixed && !canFixCorrection)}
            onClick={onFixCorrection}>{correctionFixed ? 'Unfix' : 'Fix'}</button>
        </div>
        {spectralBand && <small>
          {(spectralBand.center_nm - spectralBand.half_width_nm).toFixed(1)}–{(spectralBand.center_nm + spectralBand.half_width_nm).toFixed(1)} nm
        </small>}
        {!active && !correctionFixed && <small role="status">
          {correctionRange.span
            ? `Calibrated span ${correctionRange.min.toFixed(1)}–${correctionRange.max.toFixed(1)} nm${correctionRange.span < 100 ? ' (less than 100 nm)' : ''}`
            : 'Start Live to see the calibrated span.'}
          {correctionRange.span && !correctionRange.bounds && ' · Adjust the range to fit the calibrated image.'}
        </small>}
      </fieldset>
      <fieldset className={`vd2-spectral-correction ${referenceConfirmed || active ? 'is-fixed' : ''}`}>
        <legend>Lamp reference</legend>
        <div className="vd2-protocol-settings">
          <label><span>Lamp reference rows</span><input type="number" min="1" step="1"
            value={active ? band?.monitor_rows ?? correction.monitorRows : correction.monitorRows}
            disabled={locked || referenceConfirmed} onChange={event => onChangeCorrection('monitorRows', event.target.value)} /></label>
          <button type="button" disabled={locked || (!referenceConfirmed && !canConfirmReference)}
            onClick={onConfirmReference}>{referenceConfirmed ? 'Edit' : 'Confirm'}</button>
        </div>
      </fieldset>
      {correctionFixed && referenceConfirmed && live && <small>Stop Live before starting Measurement.</small>}
      <div className="vd2-phase-buttons">
        {!needsBruit && <button type="button" className="vd2-measure-button" disabled={cannotStart} onClick={start}>Measurement</button>}
        {needsBruit && !bruitReady && <button type="button" disabled={locked || !cameraIdle || !onBruit} onClick={recordBruit}>Record Bruit</button>}
        {needsBruit && bruitReady && <button type="button" disabled={cannotStart} onClick={resume}>Open shutters and continue</button>}
        {active && <button type="button" className="vd2-stop" disabled={pending || run.status === 'saving'} onClick={onStop}>Stop pairs</button>}
        {active && currentMode === 'precision' && <button type="button"
          disabled={pending || run.status === 'saving' || !validTarget || Number(target) === run.target_mod}
          onClick={() => send('target', { job_id: run.job_id, target_mod: Number(target) })}>Set target</button>}
      </div>
      {run?.job_id && <div aria-live="polite">
        {run.pairs_recorded} / {run.pair_limit} pairs
        {Number.isFinite(run.estimate_mod) && <span> · ΔOD {run.estimate_mod.toFixed(2)} mOD</span>}
        {run.mode === 'precision' && Number.isInteger(run.roi_pairs) && run.roi_pairs !== run.pairs_recorded
          && <span> · {run.roi_pairs} pairs used by estimator</span>}
        {run.mode === 'precision' && <span> · Maximum pointwise error {Number.isFinite(run.error_mod) ? run.error_mod.toFixed(2) + ' mOD' : 'estimating'}</span>}
      </div>}
      {run?.kinetics?.od_mod?.length > 1 && <ProfilePlot title="OD kinetics (mOD)"
        axis={run.time_scale ? `Time (${run.time_scale})` : 'Time'} hideLegend scale={1}
        series={[{ id: 'od', index: 0, color: '#4c98da',
          points: run.kinetics.od_mod.map((y, index) => ({ x: run.kinetics.time[index], y })) }]} />}
      {(error || run?.error) && <small role="alert">{error || run.error}</small>}
      {run?.manifest_warning && <small role="alert">{run.manifest_warning}</small>}
      {run?.h5_path && !active && <small title={run.h5_path}>{run.h5_path}</small>}
    </section>
  );
}
