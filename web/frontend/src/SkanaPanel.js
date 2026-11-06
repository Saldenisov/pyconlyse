import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import TreatmentError from './components/TreatmentError';
import { fetchSkanaDataset, importSkanaDataset, startSkanaJob, fetchSkanaJob,
  cancelSkanaJob, downloadSkanaResult } from './api/treatmentClient';
import './SkanaPanel.css';

const API = { dataset: fetchSkanaDataset, import: importSkanaDataset, start: startSkanaJob,
  status: fetchSkanaJob, cancel: cancelSkanaJob, download: downloadSkanaResult };
const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
const DEFAULT_SCHEME = 'A -> B ; 1 / 1.2\nc0_A_1 = 1 / 1\nc0_B_1 = 0 / 1\neps_A = 1 / 1\neps_B = 1 / 1';
const unknownUnit = (unit) => !unit || ['??', 'unknown', 'a.u.'].includes(unit);
const number = (value) => Number.isFinite(value) ? value.toPrecision(5) : 'not reported';
const sourcePreferenceKey = (sessionId) => `pyconlyse.treatment.skana.source.${sessionId}`;
function preferredSource(sessionId) {
  try { return window.sessionStorage.getItem(sourcePreferenceKey(sessionId)) === 'import' ? 'import' : 'od'; }
  catch (_error) { return 'od'; }
}

function AnalysisPlot({ traces, title, xLabel, yLabel }) {
  const element = useRef(null);
  const [failure, setFailure] = useState('');
  useEffect(() => {
    const target = element.current;
    let current = true;
    setFailure('');
    try {
      Promise.resolve(Plotly.react(target, traces, { title, margin: { t: 45, r: 15, b: 50, l: 65 },
        xaxis: { title: xLabel }, yaxis: { title: yLabel }, height: 300, autosize: true },
      { responsive: true, displaylogo: false })).catch((error) => { if (current) setFailure(error.message); });
    } catch (error) { setFailure(error.message); }
    return () => { current = false; Plotly.purge(target); };
  }, [traces, title, xLabel, yLabel]);
  return <section className="skana-plot" aria-label={title}>
    {failure && <TreatmentError message={`Plot unavailable: ${failure}`} />}
    <div ref={element} />
  </section>;
}

function ResultPlots({ result }) {
  const timeUnit = result.time_unit || 'unknown unit';
  const curves = (values, axis) => Array.from({ length: values?.[0]?.length || 0 }, (_, index) => ({
    x: axis, y: values.map((row) => row[index]), mode: 'lines', name: `Component ${index + 1}`,
  }));
  return <div className="skana-plots">
    {result.singular_values && <AnalysisPlot title="Singular values" xLabel="Component" yLabel="Singular value"
      traces={[{ x: result.singular_values.map((_, i) => i + 1), y: result.singular_values, type: 'bar' }]} />}
    <AnalysisPlot title="Spectral profiles" xLabel="Wavelength" yLabel="Profile amplitude"
      traces={curves(result.spectra, result.wavelengths)} />
    <AnalysisPlot title="Time profiles" xLabel={`Delay (${timeUnit})`} yLabel="Profile amplitude"
      traces={curves(result.concentrations, result.times)} />
    {[['data_preview', 'Data'], ['model_preview', 'Model'], ['residual_preview', 'Residuals: data − model']].map(([key, title]) =>
      result[key] && <AnalysisPlot key={key} title={title} xLabel="Wavelength" yLabel={`Delay (${timeUnit})`}
        traces={[{ type: 'heatmap', z: result[key].z, x: result[key].wavelengths, y: result[key].times,
          colorscale: key === 'residual_preview' ? 'RdBu' : 'Viridis', reversescale: key === 'residual_preview' }]} />)}
  </div>;
}

export default function SkanaPanel({ client = API, sessionId: suppliedId, refreshToken: suppliedRefresh }) {
  const context = useContext(TreatmentContext);
  const sessionId = suppliedId ?? context?.treatmentSessionId ?? '';
  const refreshToken = suppliedRefresh ?? context?.selectionRefreshToken ?? 0;
  const [sourceChoice, setSourceChoice] = useState(() => ({ sessionId, value: preferredSource(sessionId) }));
  const source = sourceChoice.sessionId === sessionId ? sourceChoice.value : preferredSource(sessionId);
  const setSource = (value) => setSourceChoice({ sessionId, value });
  const [reload, setReload] = useState(0);
  const [dataset, setDataset] = useState(null);
  const [method, setMethod] = useState('svd');
  const [rank, setRank] = useState(2);
  const [maxIterations, setMaxIterations] = useState(1000);
  const [tolerance, setTolerance] = useState('0.000001');
  const [initialization, setInitialization] = useState('svd');
  const [nonnegativeC, setNonnegativeC] = useState(true);
  const [nonnegativeS, setNonnegativeS] = useState(true);
  const [individualSigns, setIndividualSigns] = useState(false);
  const [signs, setSigns] = useState({});
  const [normalization, setNormalization] = useState('intensity');
  const [scheme, setScheme] = useState(DEFAULT_SCHEME);
  const [kineticNonnegative, setKineticNonnegative] = useState(false);
  const [globalGenerations, setGlobalGenerations] = useState(0);
  const [kineticTimeUnit, setKineticTimeUnit] = useState('');
  const [orientation, setOrientation] = useState('time_rows');
  const [importUnit, setImportUnit] = useState('??');
  const [file, setFile] = useState(null);
  const [reading, setReading] = useState(false);
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [failure, setFailure] = useState('');
  const [message, setMessage] = useState('');
  const [starting, setStarting] = useState(false);
  const generation = useRef(0);
  const controllers = useRef(new Set());
  const currentJob = useRef(null);
  const currentJobSession = useRef(sessionId);
  const timer = useRef(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const exchange = useCallback(async (callback) => {
    const abort = new AbortController(); controllers.current.add(abort);
    try { return await callback(abort.signal); }
    finally { controllers.current.delete(abort); }
  }, []);
  const poll = useCallback(async function readJob(id, version) {
    if (version !== generation.current) return;
    try {
      const payload = await exchange((signal) => client.status(sessionId, id, signal));
      if (version !== generation.current) return;
      setJob(payload.job);
      if (payload.job.status === 'completed') { setResult(payload.result); currentJob.current = null; }
      else if (payload.job.status === 'failed') { setFailure(payload.job.error || 'Analysis failed.'); currentJob.current = null; }
      else if (payload.job.status === 'cancelled') { setMessage('Analysis cancelled; no result applied.'); currentJob.current = null; }
      else timer.current = setTimeout(() => readJob(id, version), 750);
    } catch (error) {
      if (version === generation.current && error.name !== 'AbortError') {
        setFailure(`${error.message} Job may still be running; cancel it before starting another fit.`);
        timer.current = setTimeout(() => readJob(id, version), 2000);
      }
    }
  }, [client, sessionId, exchange]);
  useEffect(() => {
    try { window.sessionStorage.setItem(sourcePreferenceKey(sessionId), source); }
    catch (_error) { /* In-memory selection remains usable when storage is unavailable. */ }
  }, [sessionId, source]);
  useEffect(() => {
    const activeControllers = controllers.current;
    const version = ++generation.current;
    clearTimeout(timer.current);
    activeControllers.forEach((abort) => abort.abort());
    activeControllers.clear();
    const previousJob = currentJob.current;
    currentJob.current = null;
    if (previousJob) client.cancel(currentJobSession.current, previousJob).catch(() => {});
    setDataset(null); setResult(null); setJob(null); setFailure(''); setMessage(''); setReading(true); setStarting(false);
    setKineticTimeUnit('');
    const abort = new AbortController(); activeControllers.add(abort);
    client.dataset(sessionId, source, abort.signal).then((payload) => {
      if (!payload.dataset || typeof payload.dataset.ready !== 'boolean') throw new Error('SK-Ana dataset response is incompatible.');
      if (!abort.signal.aborted && version === generation.current) {
        setDataset(payload.dataset);
        if (payload.dataset.ready && payload.dataset.shape?.length === 2) {
          const limit = Math.min(10, ...payload.dataset.shape);
          setRank((previous) => Math.max(1, Math.min(Number(previous) || 2, limit)));
        }
        const latest = payload.latest_job;
        if (payload.dataset.ready && typeof latest?.id === 'string' && latest.id && latest.source === source
            && latest.fingerprint === payload.dataset.fingerprint) {
          currentJob.current = latest.id; currentJobSession.current = sessionId;
          setJob(latest);
          if (['svd', 'mcr_als', 'target'].includes(latest.method)) setMethod(latest.method);
          setMessage('Restored previous analysis for this matrix. Controls configure the next run.');
          poll(latest.id, version);
        }
      }
    }).catch((error) => {
      if (!abort.signal.aborted && version === generation.current) setFailure(error.message || 'Dataset unavailable.');
    }).finally(() => {
      activeControllers.delete(abort);
      if (version === generation.current && !abort.signal.aborted) setReading(false);
    });
    return () => {
      generation.current += 1;
      clearTimeout(timer.current);
      activeControllers.forEach((controller) => controller.abort()); activeControllers.clear();
      // Leaving this tab stops browser polling, not the server analysis. A
      // remount restores the matching job from dataset.latest_job.
    };
  }, [client, sessionId, source, refreshToken, reload, poll]);

  const busy = starting || (job && !TERMINAL.has(job.status));
  const options = () => {
    const components = Number(rank);
    const rankLimit = Math.min(10, ...(dataset?.shape || [10]));
    if (method !== 'target' && (!Number.isInteger(components) || components < 1 || components > rankLimit)) {
      throw new Error(`Choose 1..${rankLimit} components for this matrix.`);
    }
    if (method === 'svd') return { rank: components, max_rank: 10 };
    if (method === 'mcr_als') {
      if (!Number.isInteger(Number(maxIterations)) || Number(maxIterations) < 1 || Number(maxIterations) > 5000
          || !Number.isFinite(Number(tolerance)) || Number(tolerance) <= 0) {
        throw new Error('Use 1..5000 iterations and a finite positive convergence threshold.');
      }
      return { n_components: components, maxiter: Number(maxIterations),
        thresh: Number(tolerance), init_method: initialization, nonneg_c: nonnegativeC,
        nonneg_s: individualSigns ? Array.from({ length: components }, (_, i) => signs[i] !== false) : nonnegativeS,
        norm_s: normalization !== 'none', norm_mode: normalization === 'none' ? 'intensity' : normalization };
    }
    if (!Number.isInteger(Number(globalGenerations)) || Number(globalGenerations) < 0 || Number(globalGenerations) > 100) {
      throw new Error('Global generations must be an integer from 0 to 100.');
    }
    return { scheme, nonnegative_s: kineticNonnegative, global_generations: Number(globalGenerations),
      population_factor: 15, tol: 1e-8,
      ...(unknownUnit(dataset?.time_unit) && kineticTimeUnit.trim() ? { time_unit: kineticTimeUnit.trim() } : {}) };
  };
  const run = async () => {
    if (!dataset?.ready || busy) return;
    const version = ++generation.current;
    clearTimeout(timer.current);
    setFailure(''); setMessage(''); setResult(null); setStarting(true);
    try {
      const payload = await exchange((signal) => client.start(sessionId,
        { source, fingerprint: dataset.fingerprint, method, options: options() }, signal));
      if (version !== generation.current) {
        if (mounted.current && payload.job?.id) client.cancel(sessionId, payload.job.id).catch(() => {});
        return;
      }
      setJob(payload.job); currentJob.current = payload.job.id; currentJobSession.current = sessionId;
      await poll(payload.job.id, version);
    } catch (error) {
      if (version === generation.current && error.name !== 'AbortError') setFailure(error.message || 'Could not start analysis.');
    } finally { if (version === generation.current) setStarting(false); }
  };
  const cancel = async () => {
    if (!currentJob.current) return;
    const version = generation.current;
    setMessage('Cancellation requested. A running numerical solve may finish before its result is discarded.');
    try {
      const payload = await exchange((signal) => client.cancel(sessionId, currentJob.current, signal));
      if (version === generation.current) {
        setJob(payload.job);
        if (TERMINAL.has(payload.job.status)) {
          generation.current += 1;
          clearTimeout(timer.current);
          controllers.current.forEach((controller) => controller.abort());
          controllers.current.clear();
          currentJob.current = null; setResult(null); setStarting(false);
        }
      }
    } catch (error) { if (version === generation.current && error.name !== 'AbortError') setFailure(error.message); }
  };
  const upload = async () => {
    if (!file || busy) return;
    if (file.size > 16 * 1024 * 1024) { setFailure('Matrix text file must be at most 16 MiB.'); return; }
    const version = generation.current;
    setReading(true); setFailure(''); setResult(null);
    try {
      const text = await file.text();
      if (version !== generation.current) return;
      await exchange((signal) => client.import(sessionId, { text, filename: file.name, time_unit: importUnit,
        orientation }, signal));
      if (version !== generation.current) return;
      if (source !== 'import') setSource('import'); else setReload((value) => value + 1);
    } catch (error) {
      if (version === generation.current && error.name !== 'AbortError') setFailure(error.message || 'Could not import matrix.');
    } finally { if (version === generation.current) setReading(false); }
  };
  const download = async (format) => {
    const id = job?.id;
    if (!id || !result) return;
    const version = generation.current;
    try {
      const blob = await exchange((signal) => client.download(sessionId, id, format, signal));
      if (version !== generation.current) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url;
      anchor.download = `skana-${id}.${format === 'csv' ? 'zip' : 'json'}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { if (version === generation.current && error.name !== 'AbortError') setFailure(error.message); }
  };
  return <section className="skana-panel" aria-label="SK-Ana spectrokinetic analysis">
    <h2>SK-Ana · Spectrokinetic analysis</h2>
    <p>Python SK-Ana engine · fitting uses the full matrix. Source treatment data remains unchanged.</p>
    <TreatmentError message={failure} />
    {message && <p role="status">{message}</p>}
    <fieldset disabled={busy || reading} className="skana-source"><legend>Analysis matrix</legend>
      <label>Source<select value={source} onChange={(event) => setSource(event.target.value)}>
        <option value="od">Current calculated OD</option><option value="import">Imported matrix</option>
      </select></label>
      <button type="button" onClick={() => setReload((value) => value + 1)}>Refresh matrix</button>
      <label>Matrix text file<input type="file" accept=".dat,.csv,.txt" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
      <label>Table orientation<select value={orientation} onChange={(event) => setOrientation(event.target.value)}>
        <option value="time_rows">Time rows · wavelength header (Pyconlyse OD)</option>
        <option value="wavelength_rows">Wavelength rows · delay header (SK-Ana)</option>
      </select></label>
      <label>Imported time unit<input value={importUnit} onChange={(event) => setImportUnit(event.target.value)} /></label>
      <button type="button" onClick={upload} disabled={!file}>Import matrix</button>
    </fieldset>
    {reading && <p role="status">Loading full-resolution matrix…</p>}
    {dataset?.ready ? <p>{dataset.label || dataset.source} · {dataset.shape?.[0]} delays × {dataset.shape?.[1]} wavelengths
      {' · time unit: '}{dataset.time_unit || 'unknown'} · signal: {dataset.signal_unit || 'unspecified'}</p>
      : !reading && <p>No analysis matrix available. Calculate OD in Treatment, then refresh, or import a text matrix.</p>}
    {dataset?.warnings?.map((warning, index) => <p className="skana-warning" role="alert" key={index}>{warning}</p>)}
    {dataset?.ready && dataset.preview && <AnalysisPlot title="Input matrix preview" xLabel="Wavelength"
      yLabel={`Delay (${dataset.time_unit || 'unknown unit'})`} traces={[{ type: 'heatmap', z: dataset.preview.z,
        x: dataset.preview.wavelengths, y: dataset.preview.times, colorscale: 'Viridis' }]} />}
    <fieldset disabled={busy || !dataset?.ready || reading} className="skana-options"><legend>Analysis</legend>
      <label>Method<select value={method} onChange={(event) => { setMethod(event.target.value); setResult(null); }}>
        <option value="svd">SVD</option><option value="mcr_als">MCR-ALS</option><option value="target">Kinetic model · Bayesian MAP</option>
      </select></label>
      {method !== 'target' && <label>Components<input type="number" min="1" max={Math.min(10, ...(dataset?.shape || [10]))}
        value={rank} onChange={(event) => setRank(event.target.value)} /></label>}
      {method === 'mcr_als' && <>
        <label>Maximum iterations<input type="number" min="1" max="5000" value={maxIterations} onChange={(e) => setMaxIterations(e.target.value)} /></label>
        <label>Convergence threshold<input type="number" min="0" step="any" value={tolerance} onChange={(e) => setTolerance(e.target.value)} /></label>
        <label>Initialization<select value={initialization} onChange={(e) => setInitialization(e.target.value)}>
          <option value="svd">|SVD|</option><option value="pca">PCA</option><option value="nmf">NMF</option><option value="seq">Sequential</option>
        </select></label>
        <label><input type="checkbox" checked={nonnegativeC} onChange={(e) => setNonnegativeC(e.target.checked)} />Nonnegative time profiles</label>
        <label><input type="checkbox" checked={individualSigns} onChange={(e) => setIndividualSigns(e.target.checked)} />Per-component spectral constraints</label>
        {individualSigns ? Array.from({ length: Math.min(10, Math.max(0, Number(rank) || 0)) }, (_, i) =>
          <label key={i}><input type="checkbox" checked={signs[i] !== false} onChange={(e) => setSigns({ ...signs, [i]: e.target.checked })} />Spectrum {i + 1} nonnegative</label>)
          : <label><input type="checkbox" checked={nonnegativeS} onChange={(e) => setNonnegativeS(e.target.checked)} />Nonnegative spectra</label>}
        <label>Spectral normalization<select value={normalization} onChange={(e) => setNormalization(e.target.value)}>
          <option value="intensity">Maximum absolute intensity</option><option value="l1">L1</option><option value="none">None</option>
        </select></label>
      </>}
      {method === 'target' && <>
        <label className="skana-wide">Reaction scheme<textarea rows="6" value={scheme} onChange={(e) => setScheme(e.target.value)} /></label>
        <p className="skana-wide">Rates use the input time and concentration units. A factor of 1 fixes a parameter; larger factors specify SK-Ana log-parameter priors.</p>
        {unknownUnit(dataset?.time_unit) && <label>Explicit kinetic time unit<input value={kineticTimeUnit} onChange={(e) => setKineticTimeUnit(e.target.value)} placeholder="e.g. ps" /></label>}
        <label><input type="checkbox" checked={kineticNonnegative} onChange={(e) => setKineticNonnegative(e.target.checked)} />Nonnegative kinetic-model spectra</label>
        <label>Global generations (0 = local only)<input type="number" min="0" max="100" value={globalGenerations} onChange={(e) => setGlobalGenerations(e.target.value)} /></label>
      </>}
      <button type="button" onClick={run} disabled={method === 'target' && unknownUnit(dataset?.time_unit) && !kineticTimeUnit.trim()}>Run analysis</button>
    </fieldset>
    {busy && <div className="skana-job"><p role="status">Analysis {job?.status || 'starting'}…</p>
      <button type="button" onClick={cancel} disabled={!job?.id || job.cancel_requested}>Request cancellation</button></div>}
    {result && <section aria-label="SK-Ana results">
      <h3>{result.method} result</h3>
      {result.converged === false && <p className="skana-warning" role="alert">Convergence was not reached. Inspect diagnostics before interpreting this fit.</p>}
      {(result.warnings || []).map((warning, index) => <p className="skana-warning" role="alert" key={index}>{warning}</p>)}
      <p>Lack of fit: {number(result.lof_percent)}% · RMSE: {number(result.rmse)}
        {' · iterations: '}{result.iterations ?? 'not reported by engine'}</p>
      <p>Plot heatmaps may be sampled for display; fitting and downloads retain full resolution. Residuals = data − model.</p>
      <ResultPlots result={result} />
      <button type="button" onClick={() => download('json')}>Download result JSON</button>{' '}
      <button type="button" onClick={() => download('csv')}>Download CSV archive</button>
      <details><summary>Fit parameters and diagnostics</summary><pre>{JSON.stringify({ parameters: result.parameters,
        scheme: result.scheme, diagnostics: result.diagnostics, engine: result.engine }, null, 2)}</pre></details>
    </section>}
  </section>;
}
