import { useCallback, useEffect, useMemo } from 'react';
import { fetchWithCsrfToken } from './api/csrfRequest';
import { DEFERRED_ACQUISITION_READ } from './components/VD2ReadDiagnostics';
import { protocolHardwareBusy } from './vd2AlignmentMath';
import { API_BASE } from "./PumpProbeVD2.API_BASE";
import { fetchVd2 } from "./PumpProbeVD2.API_BASE";
import { PHASE_PROTOCOLS } from "./PumpProbeVD2.API_BASE";
import { clamp } from "./PumpProbeVD2.API_BASE";
import { roiBounds } from "./PumpProbeVD2.API_BASE";

export function useVd2AcquisitionActions({
  state, setState, preview, errors, setErrors, readFailures, activeErrorId,
  setActiveErrorId, previewError, setPreviewError, liveAverageReadError,
  setPreviewEnabled, busy, setBusy, calibrationError, setCalibrationAttempt,
  setPreviewStream, setLutRange, roiTool, rois, setRois, setSelectedRoiId, drawingRoi,
  setDrawingRoi, protocol, setProtocol, protocolHardwareActive, protocolSettings,
  setProtocolSettings, project, preparedPhase, setPreparedPhase, guidedRun, setGuidedRun,
  setGuidedChoice, setGuidedMessage, preparationTick, setPreparationTick,
  protocolStarting, setProtocolStarting, protocolStartActive, protocolAlive,
  phasePlanAbort, setRepeatConflict, stateReadEpoch, previewPaused, previewReadComplete,
  previewController, previewOverlay, nextRoiId, phaseClickTimer, lastPollError,
  reportError, resolveReadErrors, loadPreview,
}) {
  const updatePairedCapture = useCallback((paired) => {
    setProtocol(current => ({ ...current, paired, acquisition_active: paired.active,
      acquisition_phase: paired.status }));
    if (paired.active) {
      previewPaused.current = false;
      setPreviewEnabled(true);
    }
  }, [setProtocol, setPreviewEnabled, previewPaused]);

  const runRequest = useCallback(async (path, body) => {
    const stopping = ['/command/StopAcquisition', '/command/StopSequence', '/command/StopApplication',
      '/command/ShutdownRemoteEx', '/command/Disconnect'].includes(path);
    const wasPaused = previewPaused.current;
    if (stopping) {
      previewPaused.current = true;
      previewController.current?.abort();
    }
    setBusy(true);
    try {
      const url = `${API_BASE}${path}`;
      const response = await fetchVd2(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        const failure = new Error(payload.error || 'Control request failed');
        if (payload.code === 'READBACK_UNAVAILABLE' && payload.command_acknowledged === true) failure.scope = 'state';
        throw failure;
      }
      if (payload.paired) {
        updatePairedCapture(payload.paired);
        return;
      }
      setState(payload);
      if (['/command/StartLive', '/command/StartSequence', '/command/Acquire', '/command/AcquireSingle'].includes(path)) {
        previewPaused.current = false;
        setPreviewEnabled(true);
        setPreviewError('');
      }
      if (stopping) {
        stateReadEpoch.current += 1;
        setPreviewEnabled(false);
        setPreviewStream('last_frame');
        setPreviewError('');
      }
    } catch (requestError) {
      if (stopping) {
        if (requestError.scope === 'state') {
          stateReadEpoch.current += 1;
          setPreviewEnabled(false);
          setPreviewStream('last_frame');
        } else {
          previewPaused.current = wasPaused;
        }
      }
      reportError(requestError.message, 'Control', requestError.scope || null);
    } finally {
      setBusy(false);
    }
  }, [reportError, updatePairedCapture]);

  const writeParameter = useCallback((name, value) => runRequest(`/parameter/${name}`, { value }), [runRequest]);
  const runCommand = useCallback((name) => {
    if (name === 'StopAcquisition' && protocol?.paired?.active) {
      return runRequest('/paired/stop', { job_id: protocol.paired.job_id });
    }
    return runRequest('/command/' + name);
  }, [protocol?.paired, runRequest]);
  const refreshAll = useCallback(async () => {
    setBusy(true);
    try {
      const response = await fetchVd2(`${API_BASE}/refresh`, { method: 'POST', credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Could not reconnect VD2');
      // Ignore state reads started before this verified reconnection. Their
      // late failures must not restore a notification that Refresh resolved.
      stateReadEpoch.current += 1;
      setState(payload);
      lastPollError.current.state = '';
      if (!Object.keys(payload.attribute_errors || {}).length) resolveReadErrors('state');
      resolveReadErrors('connection');
      previewPaused.current = false;
      setPreviewEnabled(true);
      // A connected control link does not prove that the image/axes recovered.
      // Let their own successful reads clear their respective errors.
      await previewReadComplete.current;
      if (payload.connected && payload.application_running) await loadPreview();
      setCalibrationAttempt(value => value + 1);
    } catch (error) {
      reportError(error.message, 'Refresh connection', 'connection');
    } finally {
      setBusy(false);
    }
  }, [loadPreview, reportError, resolveReadErrors]);
  const updateProtocolSetting = useCallback((name, value) => {
    setProtocolSettings((current) => ({ ...current, [name]: value }));
  }, []);

  const startProtocolPhase = useCallback(async (phase,resolution=null) => {
    if(protocolStartActive.current)return;
    protocolStartActive.current=true;
    setProtocolStarting(true);
    try {
      const body=resolution?.body||{
        phase,frames_per_his:protocolSettings.framesPerHis,output_root:protocolSettings.outputRoot,run_name:protocolSettings.runName,
        sample_description:protocolSettings.sampleDescription||'',
        reuse_bruit:guidedRun?.reuse ?? (protocolSettings.reuseBruit==='none'?'none':'latest'),
      };
      let choice=resolution?.choice;
      if(!choice) {
        const abort=new AbortController();phasePlanAbort.current=abort;
        const timer=window.setTimeout(()=>abort.abort(),10000);
        let planned;
        try {planned=await fetchWithCsrfToken(`${API_BASE}/protocol/plan`,{method:'POST',credentials:'include',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
        finally {window.clearTimeout(timer);phasePlanAbort.current=null;}
        if(planned.status===404)throw new Error('Measurement overwrite options need Web reload. No acquisition was started.');
        const plan=await planned.json();
        if(!protocolAlive.current)return;
        if(!planned.ok||!plan.success)throw new Error(plan.error||'Unable to review the measurement folder');
        if (plan.conflict && guidedRun) {
          if (guidedRun.jobs.length || !plan.choices?.new_folder) throw new Error('This phase destination changed. Review the project before continuing.');
          choice = plan.choices.new_folder;
        } else if(plan.conflict) {setPreparedPhase(null);setRepeatConflict({body,plan});return;}
        else choice=plan.choices?.record;
      }
      if(!choice?.token)throw new Error('A reviewed acquisition destination is required');
      const url = `${API_BASE}/protocol/start`;
      const options = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({...body,destination_token:choice.token}),
      };
      let response, payload;
      for (let attempt = 0; attempt <= 3; attempt += 1) {
        if (!protocolAlive.current) return;
        response = await fetchVd2(url, options);
        payload = await response.json();
        // The server emits this code before consuming the plan or calling Tango.
        if (response.status !== 409 || payload.code !== 'VD2_CONTROL_LOCKED' || attempt === 3) break;
        await new Promise(resolve => window.setTimeout(resolve, 250 * (attempt + 1)));
      }
      if (!protocolAlive.current) return;
      if (response.status === 409 && payload.code === 'VD2_CONTROL_LOCKED') {
        reportError(payload.error, `Start ${phase}`);
        return;
      }
      if (!response.ok || !payload.success) throw new Error(payload.error || `Could not start ${phase}`);
      setProtocol(payload);
      setProtocolSettings(current=>({...current,runName:payload.sample_name||choice.run_name}));
      if (guidedRun) {
        setGuidedRun(run => run && ({ ...run, jobs: [...run.jobs, payload.job_id] }));
        setGuidedMessage(`${PHASE_PROTOCOLS[phase].label} acquisition started.`);
      }
      setRepeatConflict(null);
      setPreparedPhase(null);
      previewPaused.current = false;
      setPreviewEnabled(true);
      setPreviewError('');
    } catch (requestError) {
      if(!protocolAlive.current)return;
      setRepeatConflict(null);setPreparedPhase(null);
      if (guidedRun) {setGuidedRun(null);setGuidedMessage('Measurement stopped. Check the phase status before trying again.');}
      reportError(requestError.message, `Start ${phase}`);
    } finally {
      protocolStartActive.current=false;
      if(protocolAlive.current)setProtocolStarting(false);
    }
  }, [protocolSettings, reportError, guidedRun]);

  const beginGuidedRun = reuse => {
    setGuidedChoice(null);
    setGuidedMessage('Waiting for Absorption confirmation.');
    setGuidedRun({ reuse, phases: reuse === 'none' ? ['ABSORPTION', 'BASE', 'BRUIT'] : ['ABSORPTION', 'BASE'], jobs: [] });
    setPreparedPhase({ phase: 'ABSORPTION', readyAt: Date.now() });
  };
  const chooseGuidedRun = () => {
    if (!project) return;
    const own = project?.samples?.find(sample => sample.name === protocolSettings.runName)?.bruit_reference;
    const options = (project?.bruit_options || []).filter(item => item.status === 'completed');
    const candidate = options.find(item => item.id === own) || [...options].sort((a, b) => String(b.completed_at).localeCompare(String(a.completed_at)))[0];
    if (candidate) setGuidedChoice(candidate);
    else beginGuidedRun('none');
  };
  const cancelPreparedPhase = () => {
    setPreparedPhase(null);
    if (guidedRun) {setGuidedRun(null);setGuidedMessage('Measurement cancelled before the next phase.');}
  };
  useEffect(() => {
    if (!guidedRun?.jobs.length || !protocol) return;
    const jobs = new Map((protocol.processing_jobs || []).map(job => [job.job_id, job]));
    if (protocol.job_id) jobs.set(protocol.job_id, protocol);
    const completed = guidedRun.jobs.map(id => jobs.get(id));
    const failed = completed.find(job => job?.status === 'failed');
    if (failed) {
      setGuidedRun(null);
      setPreparedPhase(null);
      setGuidedMessage(`${failed.phase_label || failed.phase} failed. ${failed.error || 'Review the phase before retrying.'}`);
      return;
    }
    if (preparedPhase || protocolStarting || protocolHardwareBusy(protocol)) return;
    const last = completed.at(-1);
    if (!['queued', 'processing', 'completed'].includes(last?.status)) return;
    const phase = guidedRun.phases[guidedRun.jobs.length];
    if (phase) {
      setGuidedMessage(`Waiting for ${PHASE_PROTOCOLS[phase].label} confirmation.`);
      setPreparedPhase({ phase, readyAt: Date.now() + PHASE_PROTOCOLS[phase].preparationSeconds * 1000 });
    } else if (completed.every(job => job?.status === 'completed')) {
      setGuidedRun(null);
      setGuidedMessage('Measurement saved. All H5 files verified.');
    } else {
      setGuidedMessage('Waiting for H5 conversion and verification.');
    }
  }, [guidedRun, protocol, preparedPhase, protocolStarting]);

  const prepareProtocolPhase = useCallback((phase) => {
    window.clearTimeout(phaseClickTimer.current);
    phaseClickTimer.current = window.setTimeout(() => {
      setPreparedPhase({ phase, readyAt: Date.now() + PHASE_PROTOCOLS[phase].preparationSeconds * 1000 });
    }, 230);
  }, []);

  const startProtocolPhaseImmediately = useCallback((phase) => {
    window.clearTimeout(phaseClickTimer.current);
    startProtocolPhase(phase);
  }, [startProtocolPhase]);

  useEffect(() => () => window.clearTimeout(phaseClickTimer.current), []);

  useEffect(() => {
    if (!preparedPhase) return undefined;
    setPreparationTick(Date.now());
    window.requestAnimationFrame(() => document.querySelector('.vd2-phase-dialog')?.focus());
    const interval = window.setInterval(() => setPreparationTick(Date.now()), 200);
    return () => window.clearInterval(interval);
  }, [preparedPhase]);

  const preparationRemaining = preparedPhase
    ? Math.max(0, Math.ceil((preparedPhase.readyAt - preparationTick) / 1000))
    : 0;

  useEffect(() => {
    if (!preparedPhase || protocolStarting) return undefined;
    const onKeyDown = (event) => {
      const dialog = event.target?.closest?.('.vd2-phase-dialog');
      if (event.code !== 'Space' || !dialog || (event.target !== dialog && !event.target.hasAttribute('data-vd2-phase-start'))) return;
      event.preventDefault();
      if (!event.repeat) startProtocolPhase(preparedPhase.phase);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [preparedPhase, protocolStarting, startProtocolPhase]);

  const updateLutRange = useCallback((bound, value) => {
    setLutRange((previous) => {
      if (bound === 'minimum') {
        return { ...previous, minimum: Math.min(value, previous.maximum - 1) };
      }
      return { ...previous, maximum: Math.max(value, previous.minimum + 1) };
    });
  }, []);
  const autoscaleLut = useCallback(() => {
    if (!preview) return;
    setLutRange({
      minimum: clamp(Number(preview.minimum) || 0, 0, 254),
      maximum: clamp(Number(preview.maximum) || 255, 1, 255),
    });
  }, [preview]);
  const previewPoint = useCallback((event) => {
    const box = previewOverlay.current?.getBoundingClientRect();
    if (!box || !preview) return null;
    const scale = Math.min(box.width / preview.width, box.height / preview.height);
    return {
      x: clamp(Math.round((event.clientX - box.left - (box.width - preview.width * scale) / 2) / scale), 0, preview.width - 1),
      y: clamp(Math.round((event.clientY - box.top - (box.height - preview.height * scale) / 2) / scale), 0, preview.height - 1),
    };
  }, [preview]);
  const constrainRoi = useCallback((roi) => {
    if (!preview) return roi;
    if (roi.type === 'vertical') return { ...roi, y0: 0, y1: preview.height - 1 };
    if (roi.type === 'horizontal') return { ...roi, x0: 0, x1: preview.width - 1 };
    return roi;
  }, [preview]);
  const beginRoi = useCallback((event) => {
    if (!preview || event.button !== 0) return;
    const selected = event.target.dataset.roiId;
    if (selected) {
      setSelectedRoiId(selected);
      return;
    }
    const point = previewPoint(event);
    if (!point) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrawingRoi(constrainRoi({ type: roiTool, x0: point.x, y0: point.y, x1: point.x, y1: point.y }));
  }, [constrainRoi, preview, previewPoint, roiTool]);
  const updateRoi = useCallback((event) => {
    if (!drawingRoi) return;
    const point = previewPoint(event);
    if (point) setDrawingRoi((roi) => constrainRoi({ ...roi, x1: point.x, y1: point.y }));
  }, [constrainRoi, drawingRoi, previewPoint]);
  const completeRoi = useCallback((event) => {
    if (!drawingRoi || !preview) return;
    const point = previewPoint(event);
    const roi = constrainRoi({ ...drawingRoi, x1: point?.x ?? drawingRoi.x1, y1: point?.y ?? drawingRoi.y1 });
    const bounds = roiBounds(roi, preview.width, preview.height);
    const tooSmall = roi.type === 'vertical'
      ? bounds.x1 - bounds.x0 < 2
      : roi.type === 'horizontal'
        ? bounds.y1 - bounds.y0 < 2
        : bounds.x1 - bounds.x0 < 2 || bounds.y1 - bounds.y0 < 2;
    setDrawingRoi(null);
    if (tooSmall) return;
    while(rois.some(roi=>roi.id===`roi-${nextRoiId.current}`))nextRoiId.current+=1;
    const id = `roi-${nextRoiId.current++}`;
    setRois((current) => [...current, { ...roi, id }]);
    setSelectedRoiId(id);
  }, [constrainRoi, drawingRoi, preview, previewPoint,rois,setRois]);
  const removeRoi = useCallback((id) => {
    setRois((current) => current.filter((roi) => roi.id !== id));
    setSelectedRoiId((current) => current === id ? null : current);
  }, [setRois]);
  const values = state?.values || {};
  const alignmentControlsBlocked = busy || protocolStarting || !state?.connected || !state?.application_running
    || protocolHardwareActive;
  const acquisitionIdle = state?.acquisition_status === 'idle';
  const acquisitionReadError = state?.attribute_errors?.acquisition_status || '';
  const acquisitionReadDeferred = acquisitionReadError === DEFERRED_ACQUISITION_READ;
  const awaitingCameraState = state?.state_deferred && !state?.state;
  const readIssues = useMemo(() => ({
    status: { label: 'Camera status', message: state?.status || '' },
    acquisition: { label: 'Acquisition status', message: state?.attribute_errors?.acquisition_status || '' },
    preview: { label: 'Frame preview', message: previewError },
    calibration: { label: 'Calibration', message: calibrationError },
    averaging: { label: 'Rolling average read', message: liveAverageReadError },
    state: { label: 'State read', message: readFailures.state || '' },
    protocol: { label: 'Protocol read', message: readFailures.protocol || '' },
  }), [state, previewError, calibrationError, liveAverageReadError, readFailures]);
  const statusClass = state?.state === 'ON' || state?.state === 'RUNNING' ? 'online' : 'offline';
  const showPreviousError = () => {
    if (errors.length < 2) return;
    const activeIndex = Math.max(0, errors.findIndex((entry) => entry.id === activeErrorId));
    setActiveErrorId(errors[(activeIndex - 1 + errors.length) % errors.length].id);
  };
  const showNextError = () => {
    if (errors.length < 2) return;
    const activeIndex = Math.max(0, errors.findIndex((entry) => entry.id === activeErrorId));
    setActiveErrorId(errors[(activeIndex + 1) % errors.length].id);
  };
  const dismissError = (id) => setErrors((current) => current.filter((entry) => entry.id !== id));
  const clearErrors = () => setErrors([]);
  const copyError = async (message) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(message);
        return;
      }
      const textarea = document.createElement('textarea');
      textarea.value = message;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.append(textarea);
      textarea.select();
      const copied = document.execCommand('copy');
      textarea.remove();
      if (!copied) throw new Error('Browser refused clipboard access');
    } catch (clipboardError) {
      reportError(`Could not copy error: ${clipboardError.message}`, 'Copy error');
    }
  };

  return {
    writeParameter, runCommand, refreshAll, updateProtocolSetting, startProtocolPhase,
    beginGuidedRun, chooseGuidedRun, cancelPreparedPhase, prepareProtocolPhase,
    startProtocolPhaseImmediately, preparationRemaining, updateLutRange, autoscaleLut,
    previewPoint, beginRoi, updateRoi, completeRoi, removeRoi, values,
    alignmentControlsBlocked, acquisitionIdle, acquisitionReadError,
    acquisitionReadDeferred, awaitingCameraState, readIssues, statusClass,
    showPreviousError, showNextError, dismissError, clearErrors, copyError, updatePairedCapture,
  };
}
