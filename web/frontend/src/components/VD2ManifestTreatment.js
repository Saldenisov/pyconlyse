import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchTreatmentQueue, postTreatment } from '../api/treatmentClient';
import { namespaceToken } from '../browserWorkspaceIdentity';
import { cleanServerPath } from '../serverPaths';
import VD2FolderPicker from './VD2FolderPicker';
import { spectralSum, spectralIndividual, vd2OdLabels } from '../treatmentOdModes';
import { SelectionHeatmap } from '../TopSection';

export default function VD2ManifestTreatment({ initialManifest = '', initialSample='', sessionId: suppliedSession, onLoaded, dialog = false, onClose }) {
  const [fallbackSession] = useState(()=>`manifest-${namespaceToken()}`);
  const sessionId=suppliedSession||fallbackSession;
  const [path, setPath] = useState(initialManifest);
  const [plan, setPlan] = useState(null);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [queue, setQueue] = useState(null);
  const [queueError,setQueueError]=useState('');
  const [notice, setNotice] = useState('');
  const [clean, setClean] = useState(true);
  const [calcMode, setCalcMode] = useState(spectralSum);
  const [references, setReferences] = useState({});
  const [absPreview, setAbsPreview] = useState(null);
  const usesReference = calcMode !== 'averaged';
  const alive=useRef(true),sequence=useRef(0),loadedPath=useRef('');
  const dialogNode = useRef(null);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(() => {
    if (!dialog) return undefined;
    const previous = document.activeElement;
    dialogNode.current?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, [dialog]);
  const dialogKeys = event => {
    if (event.key === 'Escape' && !busy) { event.preventDefault(); onClose?.(); }
    if (event.key !== 'Tab') return;
    const controls = [...dialogNode.current.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),summary')]
      .filter(element => element.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogNode.current)) {
      event.preventDefault(); last?.focus();
    } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialogNode.current)) {
      event.preventDefault(); first?.focus();
    }
  };
  const [thresholds, setThresholds] = useState({ angle: '1', surface: '1' });
  const load = useCallback(async manifestPath => {
    const cleanPath=cleanServerPath(manifestPath),epoch=++sequence.current;
    setPath(cleanPath);
    setBusy(true); setError(''); setNotice(''); setPlan(null); setSelected([]);
    setReferences({}); setAbsPreview(null);
    try {
      const response = await postTreatment(sessionId, '/api/treatment/manifest/vd2', { manifest_path: cleanPath });
      if(!alive.current||epoch!==sequence.current)return;
      setPlan(response.manifest);
      const canonical=cleanServerPath(response.manifest.manifest_path||cleanPath);
      loadedPath.current=canonical;setPath(canonical);
      setSelected(response.manifest.samples.filter(sample => sample.ready&&(!initialSample||sample.name===initialSample)).map(sample => sample.name));
      onLoaded?.(response.manifest);
    } catch (cause) { if(alive.current&&epoch===sequence.current)setError(cause.message); }
    finally { if(alive.current&&epoch===sequence.current)setBusy(false); }
  }, [sessionId,initialSample,onLoaded]);
  useEffect(() => { const clean=cleanServerPath(initialManifest);if(clean&&clean!==loadedPath.current)load(clean); }, [initialManifest, load]);
  useEffect(()=>{
    let active=true;
    fetchTreatmentQueue(sessionId)?.then(payload=>{if(active&&payload?.queue){setQueue(payload.queue);setQueueError('');}})
      .catch(cause=>{if(active)setQueueError(`Saved manifest jobs: ${cause.message}`);});
    return()=>{active=false;};
  },[sessionId]);
  useEffect(() => {
    if (!queue?.running && !queue?.pending_count) return undefined;
    let alive = true;
    let active = false;
    const timer = window.setInterval(async () => {
      if (active) return;
      active = true;
      try {
        const response = await fetchTreatmentQueue(sessionId);
        if (alive) { setQueue(response.queue); setError(''); }
      } catch (cause) { if (alive) setError(cause.message); }
      finally { active = false; }
    }, 1000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [queue?.running, queue?.pending_count, sessionId]);
  const calculate = async mode => {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await postTreatment(sessionId, '/api/treatment/manifest/vd2/queue', {
        manifest_path: plan.manifest_path, samples: selected, mode, clean, calc_mode: calcMode,
        ...(usesReference ? { spectral_references: references } : {}),
        angle_threshold: Number(thresholds.angle), surface_threshold: Number(thresholds.surface),
      });
      if (alive.current) {
        setQueue(response.queue);
        if (mode === 'new' && !response.queue_jobs?.length) setNotice('All selected results are current.');
        else if (response.skipped_samples?.length) setNotice(`${response.skipped_samples.length} current results skipped.`);
      }
    } catch (cause) { if (alive.current) setError(cause.message); }
    finally { if (alive.current) setBusy(false); }
  };
  const previewAbs = async sample => {
    setBusy(true); setError(''); setAbsPreview(null);
    try {
      const response = await postTreatment(sessionId, '/api/treatment/manifest/vd2/abs-preview', {
        manifest_path: plan.manifest_path, sample,
      });
      if (alive.current) setAbsPreview({ sample, selection: response.selection });
    } catch (cause) {
      if (alive.current) setError(cause.message);
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const needsReference = mode => usesReference && selected.some(name =>
    !references[name] && (mode === 'all' || !plan.samples.find(sample => sample.name === name)?.result_path));
  const content = <>
    {(!plan || !dialog) && <div role="group" aria-label="Load VD2 manifest" className="vd2-manifest-path">
      <div><span>Manifest JSON path</span><VD2FolderPicker kind="manifest" value={path} disabled={busy}
        onChange={value=>{setPath(value);setPlan(null);setSelected([]);}} onChoose={value=>load(value)} /></div>
      <button type="button" disabled={busy || !path.trim()} onClick={()=>load(path)}>Load manifest</button>
    </div>}
    {error && <p role="alert">{error}</p>}
    {queueError&&<p role="alert">{queueError}</p>}
    {notice && <p role="status">{notice}</p>}
    {plan && <>
      <div className="vd2-manifest-samples">
        {plan.samples.map(sample => <div key={sample.name}><label>
          <input type="checkbox" disabled={busy || !sample.ready} checked={selected.includes(sample.name)}
            onChange={event => setSelected(current => event.target.checked ? [...current, sample.name] : current.filter(name => name !== sample.name))} />
          <strong>{sample.name}</strong>{!sample.ready && ` · ${sample.error}`}
          {sample.description && <small>{sample.description}</small>}
        </label>
          {usesReference && sample.ready && selected.includes(sample.name) && <button type="button"
            disabled={busy || queue?.running} onClick={() => previewAbs(sample.name)}>
            {references[sample.name] ? 'Edit ABS window' : 'Draw ABS window'} · {sample.name}
          </button>}
          {usesReference && references[sample.name] && <small>
            Rows {references[sample.name].start + 1}–{references[sample.name].stop}
          </small>}
        </div>)}
      </div>
      {usesReference && absPreview && <section className="manifest-abs-reference">
        <p>Drag along the time axis to mark the pre-pulse window for {absPreview.sample}.</p>
        <SelectionHeatmap selection={absPreview.selection} fillPanel drawingReference
          reference={references[absPreview.sample]} onReference={range => {
            setReferences(current => ({ ...current, [absPreview.sample]: {
              ...range, source: absPreview.selection.spectral_reference_source,
            } }));
            setAbsPreview(null);
          }} />
      </section>}
      <div className="vd2-manifest-actions">
        <label>Calculation mode
          <select value={calcMode} disabled={busy || queue?.running} onChange={event => setCalcMode(event.target.value)}>
            {[spectralSum, spectralIndividual, 'averaged'].map(mode => (
              <option key={mode} value={mode}>{vd2OdLabels[mode]}</option>
            ))}
          </select>
        </label>
        <button type="button" disabled={busy || !selected.length || queue?.running || needsReference('new')} onClick={() => calculate('new')}>Calculate new only</button>
        <button type="button" disabled={busy || !selected.length || queue?.running || needsReference('all')} onClick={() => calculate('all')}>Recalculate all</button>
        <label><input type="checkbox" checked={clean} onChange={event => setClean(event.target.checked)} disabled={busy || queue?.running} /> SAM cleaning</label>
        <details className="treatment-advanced-settings">
        <summary>Cleaning settings</summary>
        <div className="treatment-settings-fields">
        <label>SAM angle (°)<input aria-label="SAM angle" type="number" min="0.001" step="any" value={thresholds.angle} onChange={event => setThresholds(current => ({ ...current, angle: event.target.value }))} /></label>
        <label>SAM surface (%)<input aria-label="SAM surface" type="number" min="0.001" step="any" value={thresholds.surface} onChange={event => setThresholds(current => ({ ...current, surface: event.target.value }))} /></label>
        <button type="button" onClick={() => setThresholds({ angle: '1', surface: '1' })}>Reset SAM defaults</button>
        </div>
        </details>
      </div>
    </>}
    {queue?.jobs?.length > 0 && <ul aria-label="Manifest treatment jobs">
      {queue.jobs.map(job => <li key={job.job_id}>{job.label || job.recipe?.label} · {job.status} · {job.phase}
        {job.error && <strong role="alert"> · {job.error}</strong>}
        {job.saved?.save_path && <span> · {job.saved.save_path}</span>}
        {Object.entries(job.preparation?.cleaned || {}).map(([role, summary]) => (
          <small key={role}> · {role}: {summary.cleaned_measurements}/{summary.source_measurements} kept</small>
        ))}
      </li>)}
    </ul>}
  </>;
  return dialog ? <div className="treatment-dialog-backdrop"><section ref={dialogNode} tabIndex="-1" onKeyDown={dialogKeys} role="dialog" aria-modal="true"
    aria-label="Calculate according to manifest" className="treatment-manifest-dialog">
    <header><h2>Project manifest</h2><button type="button" onClick={onClose} disabled={busy} aria-label="Close manifest">×</button></header>
    {content}</section></div> : <details className="vd2-manifest-treatment" open={Boolean(initialManifest)||Boolean(plan) || undefined}>
    <summary>VD2 project manifest</summary>{content}</details>;
}
