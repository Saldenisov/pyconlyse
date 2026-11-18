import { useEffect, useState } from 'react';
import { API_BASE, fetchVd2, ProfilePlot, roiBounds } from '../PumpProbeVD2.API_BASE';

const SPECTRAL_METHOD = 'pair_cubic_pool';
const METHODS = [
  [SPECTRAL_METHOD, 'Per-pair spectral correction'],
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

function odPoints(profile, axis) {
  return profile?.od_mod?.flatMap((y, index) => Number.isFinite(y)
    ? [{ x: profile[axis][index], y, error: profile.se_mod?.[index] }] : []) ?? [];
}

export default function VD2PairedCapture({
  available, directTango = false, run, settings, disabled, roi, preview, protocol, onUpdate, onStop, onBruit,
  cameraIdle, live, liveBlocked, onLive, correction, correctionRange, correctionFixed,
  referenceConfirmed, canFixCorrection, canConfirmReference,
  onChangeCorrection, onFixCorrection, onConfirmReference,
}) {
  const [mode, setMode] = useState('fixed');
  const [first, setFirst] = useState(true);
  const [pairs, setPairs] = useState(directTango ? '200' : '100');
  const [limit, setLimit] = useState(directTango ? '1000' : '');
  const [target, setTarget] = useState(directTango ? '1' : '2');
  const [trigger, setTrigger] = useState('external_rising');
  const [method, setMethod] = useState(directTango ? SPECTRAL_METHOD : 'lamp_matched');
  const [precisionAxis, setPrecisionAxis] = useState('kinetics');
  const [delayStart, setDelayStart] = useState('');
  const [delayEnd, setDelayEnd] = useState('');
  const [samSurface, setSamSurface] = useState('3');
  const [bruitAttempt, setBruitAttempt] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const active = Boolean(run?.active);
  const currentMode = active ? run.mode : mode;
  const showPrecision = active && currentMode === 'precision';
  const corrected = (active ? run.method : method) === SPECTRAL_METHOD;
  const kineticsPoints = odPoints(run?.kinetics, 'time');
  const spectrumPoints = odPoints(run?.spectrum, 'wavelength_nm');
  const delayRange = delayStart.trim() || delayEnd.trim() ? [Number(delayStart), Number(delayEnd)] : null;
  const validDelay = !delayRange || (delayStart.trim() && delayEnd.trim()
    && delayRange.every(Number.isFinite) && delayRange[0] < delayRange[1]);
  const targetMet = run?.precision_first_met_pair != null && Number.isFinite(run?.error_mod)
    && run.error_mod <= run.target_mod;
  const pairLimit = mode === 'precision' && !limit.trim() ? null : Number(mode === 'fixed' ? pairs : limit);
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
    sample_description: settings.sampleDescription || '',
    reuse_bruit: settings.reuseBruit === 'none' ? 'none' : 'latest',
    mode,
    first_map_with_electrons: first,
    pair_limit: pairLimit,
    target_mod: mode === 'precision' ? Number(target) : null,
    trigger_source: trigger,
    roi: selected,
    band: method === SPECTRAL_METHOD ? { ...band, delay_range: delayRange, precision_axis: precisionAxis } : band,
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
  const prepareBruit = () => {
    setBruitAttempt({ prior: protocol?.job_id });
    onBruit();
  };
  const recordBruit = () => directTango ? prepareBruit()
    : control('/parameter/streak_shutter', { value: 'Closed' }, prepareBruit);
  const resumePaired = async () => {
    setBruitAttempt(null);
    await start();
  };
  const resume = () => directTango ? resumePaired() : control('/alignment/open-shutters', {}, resumePaired);
  const locked = active || disabled || pending;
  const displayedCenter = active ? band?.center_nm : correctionRange.center ?? correction.center;
  const displayedBandwidth = active && band ? 2 * band.half_width_nm : correctionRange.bandwidth ?? correction.bandwidth;
  const validLimit = pairLimit === null || (Number.isInteger(pairLimit) && pairLimit >= 1 && pairLimit <= 10000);
  const cannotStart = locked || !cameraIdle || !settings.runName?.trim() || !validLimit
    || !band || !correctionFixed || !referenceConfirmed
    || (method.startsWith('sam_') && !(Number(samSurface) > 0 && Number(samSurface) <= 100))
    || (mode === 'precision' && !validTarget) || (corrected && !validDelay);
  return (
    <section className="vd2-phase-protocol" aria-label="Paired ABS/BASE acquisition">
      <header><h2>Paired ABS/BASE · 10 Hz</h2><small role="status">{run?.stage || STOP_LABELS[run?.stop_reason] || ''}</small></header>
      <div className="vd2-protocol-settings">
        <label><span>Stop condition</span><select value={currentMode} disabled={locked} onChange={event => setMode(event.target.value)}>
          <option value="fixed">Fixed pair count</option>
          <option value="precision">Target error</option>
        </select></label>
        <label><span>{currentMode === 'fixed' ? 'Pairs' : 'Pair limit'}</span><input type="number" min="1" max="10000" step="1"
          placeholder={currentMode === 'precision' ? 'No frame limit' : undefined}
          value={active ? run.pair_limit ?? '' : mode === 'fixed' ? pairs : limit} disabled={locked}
          onChange={event => (mode === 'fixed' ? setPairs : setLimit)(event.target.value)} /></label>
        {currentMode === 'fixed' && <small>{2 * (active ? run.pair_limit : pairLimit)} frames</small>}
        <label><span>5 Hz sync</span><select value={active ? run.trigger_source : trigger} disabled={locked} onChange={event => setTrigger(event.target.value)}>
          <option value="external_rising">External rising</option>
          <option value="external_falling">External falling</option>
          {!directTango && <option value="internal">Internal</option>}
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
        {corrected && currentMode === 'precision' && <label><span>Precision target for</span>
          <select value={active ? run.precision_axis : precisionAxis} disabled={locked}
            onChange={event => setPrecisionAxis(event.target.value)}>
            <option value="kinetics">Kinetics</option>
            <option value="spectrum">Spectrum</option>
            <option value="both">Kinetics and spectrum</option>
          </select>
        </label>}
      </div>
      <fieldset className={`vd2-spectral-correction vd2-spectral-range ${correctionFixed || active ? 'is-fixed' : ''}`}>
        <legend>{corrected ? 'OD wavelength range' : 'Spectral Correction Range'}</legend>
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
      {corrected && <fieldset className="vd2-spectral-correction">
        <legend>{directTango ? 'OD delay range (µs)' : 'OD delay range (camera units)'}</legend>
        <div className="vd2-protocol-settings">
          <label><span>Start delay</span><input type="number" step="any" placeholder="After reference"
            value={active ? run.delay_range?.[0] ?? '' : delayStart} disabled={locked}
            onChange={event => setDelayStart(event.target.value)} /></label>
          <label><span>End delay</span><input type="number" step="any" placeholder="End of trace"
            value={active ? run.delay_range?.[1] ?? '' : delayEnd} disabled={locked}
            onChange={event => setDelayEnd(event.target.value)} /></label>
        </div>
      </fieldset>}
      <fieldset className={`vd2-spectral-correction ${referenceConfirmed || active ? 'is-fixed' : ''}`}>
        <legend>Lamp reference</legend>
        <div className="vd2-protocol-settings">
          <label><span>Lamp reference rows</span><input type="number" min="1" step="1"
            value={active ? band?.monitor_rows ?? correction.monitorRows : correction.monitorRows}
            disabled={locked || referenceConfirmed} onChange={event => onChangeCorrection('monitorRows', event.target.value)} /></label>
          <button type="button" disabled={locked || (!referenceConfirmed && !canConfirmReference)}
            onClick={onConfirmReference}>{referenceConfirmed ? 'Edit' : 'Confirm'}</button>
        </div>
        {corrected && <small>Use rows before the signal.</small>}
      </fieldset>
      {correctionFixed && referenceConfirmed && live && <small>Stop Live before starting Measurement.</small>}
      <div className="vd2-phase-buttons">
        {!needsBruit && <button type="button" className="vd2-measure-button" disabled={cannotStart} onClick={start}>Measurement</button>}
        {(needsBruit ? !bruitReady : directTango) &&
          <button type="button" disabled={locked || !cameraIdle || !onBruit} onClick={recordBruit}>Record Bruit</button>}
        {needsBruit && bruitReady && <button type="button" disabled={cannotStart} onClick={resume}>Open shutters and continue</button>}
        {active && <button type="button" className="vd2-stop" disabled={pending || run.status === 'saving'} onClick={onStop}>Stop pairs</button>}
        {active && currentMode === 'precision' && <button type="button"
          disabled={pending || run.status === 'saving' || !validTarget || Number(target) === run.target_mod}
          onClick={() => send('target', { job_id: run.job_id, target_mod: Number(target) })}>Set target</button>}
      </div>
      {run?.job_id && <div aria-live="polite">
        {run.pairs_recorded}{run.pair_limit != null && ` / ${run.pair_limit}`} pairs
        {Number.isFinite(run.estimate_mod) && <span> · ΔOD {run.estimate_mod.toFixed(2)} mOD</span>}
        {run.mode === 'precision' && Number.isInteger(run.roi_pairs) && run.roi_pairs !== run.pairs_recorded
          && <span> · {run.roi_pairs} pairs used by estimator</span>}
        {run.mode === 'precision' && <span> · Maximum pointwise error {Number.isFinite(run.error_mod) ? run.error_mod.toFixed(2) + ' mOD' : 'estimating'}</span>}
        {targetMet && <strong className="vd2-precision-met"> · Target met at {run.precision_first_met_pair} pairs</strong>}
      </div>}
      {(kineticsPoints.length > 0 || spectrumPoints.length > 0 || showPrecision) && <section
        className={showPrecision ? 'vd2-paired-progress' : undefined}
        role={showPrecision ? 'dialog' : undefined}
        aria-label={showPrecision ? (run.method === SPECTRAL_METHOD ? 'Live OD' : 'Live OD kinetics') : undefined}>
        <div className={spectrumPoints.length ? 'vd2-paired-profiles' : undefined}>
          {kineticsPoints.length > 0 && <ProfilePlot title="OD kinetics (mOD)"
            summary={precisionSummary(run.kinetics_error_mod ?? (run.method !== SPECTRAL_METHOD ? run.error_mod : null))}
            axis={run.time_scale ? `Time (${run.time_scale})` : 'Time'} hideLegend scale={1}
            series={[{ id: 'od', index: 0, color: '#4c98da', points: kineticsPoints }]} />}
          {spectrumPoints.length > 0 && <ProfilePlot title="OD spectrum (mOD)"
            summary={precisionSummary(run.spectrum_error_mod)} axis="Wavelength (nm)" hideLegend scale={1}
            series={[{ id: 'od', index: 0, color: '#63cb90', points: spectrumPoints }]} />}
        </div>
        {!kineticsPoints.length && !spectrumPoints.length && <p role="status">{run.stage || 'Waiting for the first OD estimate'}</p>}
        {run.error_reference === 'fixed_bruit' && <small>Standard error with fixed Bruit reference</small>}
      </section>}
      {(error || run?.error) && <small role="alert">{error || run.error}</small>}
      {run?.manifest_warning && <small role="alert">{run.manifest_warning}</small>}
      {run?.export_warning && <small role="alert">{run.export_warning}</small>}
      {run?.h5_path && !active && <small title={run.h5_path}>{run.h5_path}</small>}
    </section>
  );
}

function precisionSummary(error) {
  return Number.isFinite(error) ? `Max SE ${error.toFixed(2)} mOD` : undefined;
}
