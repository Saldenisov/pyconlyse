import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import useVd2ServerWorkspace from './useVd2ServerWorkspace';
import { workspaceHeaders } from './browserWorkspaceIdentity';
import useFrameDisplayRate from './useFrameDisplayRate';
import { AlignmentSignalBuffer } from './vd2AlignmentSearch';
import { startPreviewPolling } from './vd2PreviewPolling';
import { createPreviewFreshnessClock } from './vd2PreviewFreshness';
import { alignmentRegionGeometry } from './vd2RoiMath';
import { ALIGNMENT_REGION_KEY, DEFAULT_ALIGNMENT_REGION, useVd2Memory, validAcquisitionRois, validAlignmentRegion } from './vd2AlignmentMemory';
import { previewShouldPoll, protocolHardwareBusy, protocolSaveActive } from './vd2AlignmentMath';
import { API_BASE } from "./PumpProbeVD2.API_BASE";
import { fetchVd2 } from "./PumpProbeVD2.API_BASE";
import { defaultVd2RunName } from "./PumpProbeVD2.API_BASE";
import { clamp } from "./PumpProbeVD2.API_BASE";
import { drawPreview } from "./PumpProbeVD2.API_BASE";

export function useVd2AcquisitionState() {
  const [state, setState] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewClock, setPreviewClock] = useState(() => performance.now());
  const [previewAvailable, setPreviewAvailable] = useState(false);
  const previewIdentity = useRef(null);
  const [errors, setErrors] = useState([]);
  const [readFailures, setReadFailures] = useState({});
  const [activeErrorId, setActiveErrorId] = useState(null);
  const [previewError, setPreviewError] = useState('');
  const [alignmentAverage, setAlignmentAverage] = useState(null);
  const previewPaint = useRef({});
  const [liveAverageReadError, setLiveAverageReadError] = useState('');
  const [previewEnabled, setPreviewEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState(() => new URLSearchParams(window.location.search).get('tab') === 'alignment' ? 'alignment' : 'acquisition');
  const [calibration, setCalibration] = useState(null);
  const [calibrationUpdating, setCalibrationUpdating] = useState(false);
  const [calibrationError, setCalibrationError] = useState('');
  const [calibrationAttempt, setCalibrationAttempt] = useState(0);
  const [previewStream, setPreviewStream] = useState('last_frame');
  const [alignmentRegion,setAlignmentRegion,alignmentMemoryError]=useVd2Memory(ALIGNMENT_REGION_KEY,DEFAULT_ALIGNMENT_REGION,validAlignmentRegion,true);
  const [imageRight, setImageRight] = useState(() => {
    try { return window.localStorage.getItem('pyconlyse.vd2.imageRight') === 'true'; } catch (_error) { return false; }
  });
  const [imageWidth, setImageWidth] = useState(() => {
    try { return clamp(Number(window.localStorage.getItem('pyconlyse.vd2.imageWidth')) || 560, 320, 760); } catch (_error) { return 560; }
  });
  const [dragPanel, setDragPanel] = useState(false);
  const [lutPalette, setLutPalette] = useState('rainbow');
  const [lutRange, setLutRange] = useState({ minimum: 0, maximum: 255 });
  const [roiTool, setRoiTool] = useState('vertical');
  const roiMemoryKey=preview?.width>0&&preview?.height>0?`pyconlyse.vd2.acquisition.rois.v1:${preview.width}x${preview.height}`:null;
  const [rois,setRois,roiMemoryError]=useVd2Memory(roiMemoryKey,[],validAcquisitionRois);
  const [linkRois, setLinkRois] = useState(false);
  const [selectedRoiId, setSelectedRoiId] = useState(null);
  const [drawingRoi, setDrawingRoi] = useState(null);
  const [protocol, setProtocol] = useState(null);
  const protocolHardwareActive=protocolHardwareBusy(protocol),protocolSaving=protocolSaveActive(protocol);
  const [projectReadback, setProjectReadback] = useState(null);
  const [projectError, setProjectError] = useState('');
  const [protocolSettings, setProtocolSettings] = useState(() => ({
    framesPerHis: '100',
    outputRoot: 'E:\\DATA_VD2',
    runName: defaultVd2RunName(),
    sampleDescription: '',
    reuseBruit: 'latest',
  }));
  const project = projectReadback?.root === protocolSettings.outputRoot ? projectReadback.data : null;
  const serverWorkspace=useVd2ServerWorkspace(protocolSettings,setProtocolSettings);
  const returnContext=useRef({});
  returnContext.current={view:activeTab,windowId:serverWorkspace.windowId};
  const restoreJob=useRef(new URLSearchParams(window.location.search).get('restore_job'));
  const [preparedPhase, setPreparedPhase] = useState(null);
  const [guidedRun, setGuidedRun] = useState(null);
  const [guidedChoice, setGuidedChoice] = useState(null);
  const [guidedMessage, setGuidedMessage] = useState('');
  const [preparationTick, setPreparationTick] = useState(Date.now());
  const [protocolStarting, setProtocolStarting] = useState(false);
  const protocolStartActive=useRef(false);
  const protocolAlive=useRef(true),phasePlanAbort=useRef(null);
  const [repeatConflict,setRepeatConflict]=useState(null);
  useEffect(()=>{protocolAlive.current=true;return()=>{protocolAlive.current=false;phasePlanAbort.current?.abort();};},[]);
  const alignmentMeasurements = useMemo(() => new AlignmentSignalBuffer(), []);
  const requestActive = useRef(false);
  const stateReadEpoch = useRef(0);
  const protocolRequestActive = useRef(false);
  const previewRequestActive = useRef(false);
  const previewPaused = useRef(false);
  const previewReadComplete = useRef(Promise.resolve());
  const previewFreshness = useMemo(() => createPreviewFreshnessClock(), []);
  const previewController = useRef(null);
  const previewCanvas = useRef(null);
  const previewOverlay = useRef(null);
  const nextRoiId = useRef(1);
  const phaseClickTimer = useRef(null);
  const errorSequence = useRef(0);
  const lastPollError = useRef({ state: '', protocol: '' });

  const reportError = useCallback((message, source = 'Control', scope = null) => {
    const text = String(message || '').trim();
    if (!text) return;
    if (scope) setReadFailures(current => current[scope] === text ? current : { ...current, [scope]: text });
    const id = `${Date.now()}-${++errorSequence.current}`;
    setErrors((current) => [...current, {
      id,
      source,
      scope,
      message: text,
      timestamp: Date.now(),
    }].slice(-50));
    setActiveErrorId(id);
  }, []);

  const resolveReadErrors = useCallback(scope => {
    setReadFailures(current => current[scope] ? { ...current, [scope]: '' } : current);
    setErrors(current => current.some(entry => entry.scope === scope)
      ? current.filter(entry => entry.scope !== scope) : current);
  }, []);

  useEffect(() => {
    const identity=restoreJob.current;
    if(!serverWorkspace.ready||!identity)return undefined;
    let active=true;
    const key=`pyconlyse.vd2.restored-job:${identity}`;
    try {if(window.sessionStorage.getItem(key))return undefined;}catch(_error){/* Restore once for this mount. */}
    (async()=>{
      try {
        const response=await fetch(`${API_BASE}/lifecycle`,{credentials:'include'});
        const payload=await response.json(),job=payload.job;
        if(!response.ok||!payload.success||job?.job_id!==identity||job?.status!=='completed'||!job.result?.restored)throw new Error('Saved camera restoration is no longer the latest completed job; interface unchanged.');
        if(!active)return;
        const ui=job.result.restored.ui;
        if(ui?.form)setProtocolSettings(ui.form);
        setActiveTab(ui?.tab==='alignment'?'alignment':'acquisition');
        restoreJob.current=null;
        try{window.sessionStorage.setItem(key,'1');}catch(_error){/* Current mount still restored. */}
      }catch(cause){if(active){restoreJob.current=null;reportError(cause.message,'Interface restore');}}
    })();
    return()=>{active=false;};
  },[serverWorkspace.ready,reportError]);

  const reportPollError = useCallback((message, request) => {
    const text = String(message || '').trim();
    if (!text || lastPollError.current[request] === text) return;
    lastPollError.current[request] = text;
    reportError(text, 'Background check', request);
  }, [reportError]);

  useEffect(() => {
    if (!errors.length) {
      setActiveErrorId(null);
      return;
    }
    if (!errors.some((entry) => entry.id === activeErrorId)) {
      setActiveErrorId(errors[errors.length - 1].id);
    }
  }, [activeErrorId, errors]);

  const loadState = useCallback(async () => {
    if (requestActive.current || protocolStartActive.current) return;
    requestActive.current = true;
    const epoch = stateReadEpoch.current;
    try {
      const context=returnContext.current;
      const headers={'X-VD2-View':context.view,...(context.windowId?workspaceHeaders(context.windowId):{})};
      const response = await fetch(`${API_BASE}/state`, { credentials: 'include',headers });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read VD2 state');
      if (epoch !== stateReadEpoch.current) return;
      if (payload.state_deferred) {
        setState(current => ({
          ...current, ...payload,
          attribute_errors: { ...current?.attribute_errors, ...payload.attribute_errors },
        }));
        return;
      }
      setState(payload);
      if(payload.recovery_warning)reportPollError(payload.recovery_warning,'recovery');
      else {lastPollError.current.recovery='';resolveReadErrors('recovery');}
      lastPollError.current.state = '';
      if (!Object.keys(payload.attribute_errors || {}).length) resolveReadErrors('state');
    } catch (requestError) {
      if (epoch === stateReadEpoch.current) reportPollError(requestError.message, 'state');
    } finally {
      requestActive.current = false;
    }
  }, [reportPollError, resolveReadErrors]);

  useEffect(() => {
    loadState();
    const interval = window.setInterval(loadState, 2500);
    return () => window.clearInterval(interval);
  }, [loadState]);

  const loadProtocol = useCallback(async () => {
    if (protocolRequestActive.current) return;
    protocolRequestActive.current = true;
    try {
      const response = await fetch(`${API_BASE}/protocol/state`, { credentials: 'include' });
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read VD2 protocol');
      setProtocol(payload);
      lastPollError.current.protocol = '';
      resolveReadErrors('protocol');
    } catch (requestError) {
      reportPollError(requestError.message, 'protocol');
    } finally {
      protocolRequestActive.current = false;
    }
  }, [reportPollError, resolveReadErrors]);

  useEffect(() => {
    loadProtocol();
    const interval = window.setInterval(loadProtocol, 1200);
    return () => window.clearInterval(interval);
  }, [loadProtocol]);

  const projectConversionState=(protocol?.processing_jobs||[]).map(job=>`${job.job_id}:${job.status}`).join('|');
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE}/protocol/project?${new URLSearchParams({ output_root: protocolSettings.outputRoot })}`,
          { credentials: 'include', signal: controller.signal });
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Project manifest unavailable');
        if (!controller.signal.aborted) { setProjectReadback({ root: protocolSettings.outputRoot, data: payload }); setProjectError(''); }
      } catch (error) {
        if (!controller.signal.aborted) { setProjectReadback(null); setProjectError(error.message); }
      }
    }, 450);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [protocolSettings.outputRoot, protocol?.completed_at, protocol?.paired?.completed_at,
    protocol?.acquisition_active, projectConversionState]);

  const loadPreview = useCallback(async () => {
    if (previewRequestActive.current || previewPaused.current || protocolStartActive.current) return;
    previewRequestActive.current = true;
    let finishRead;
    previewReadComplete.current = new Promise(resolve => { finishRead = resolve; });
    const controller = new AbortController();
    previewController.current = controller;
    let expired = false;
    const timeout = window.setTimeout(() => { expired = true; controller.abort(); }, 8000);
    const startedAt = performance.now();
    try {
      const response = await fetch(`${API_BASE}/preview`, { credentials: 'include', cache: 'no-store', signal: controller.signal });
      const payload = await response.json();
      if (expired) throw new Error('Live preview read timed out.');
      if (controller.signal.aborted || previewPaused.current) return;
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to read live frame');
      if (!payload.frame_available && payload.stream_state === 'waiting_for_frame') return;
      const identity = payload.received_at;
      const previous = previewIdentity.current;
      if (identity && previous && (identity === previous || Date.parse(identity) < Date.parse(previous))) return;
      setPreviewStream(payload.stream_state || 'acquiring');
      setPreviewAvailable(Boolean(payload.frame_available));
      setPreviewError('');
      if (payload.stream_state === 'no_valid_image') {
        setCalibration(null);
        setCalibrationError('');
      }
      if (!payload.frame_available) {
        previewFreshness.invalidate('No current image returned by the server.');
        return;
      }
      const now = performance.now();
      previewFreshness.observe(payload, { serverDate: response.headers?.get?.('Date'), startedAt, receivedAt: now });
      previewIdentity.current = identity;
      setPreviewClock(now);
      setPreview(payload);
      setCalibration(payload.calibration || null);
      setPreviewError('');
    } catch (requestError) {
      if ((controller.signal.aborted && !expired) || previewPaused.current) return;
      const message = expired ? 'Live preview read timed out.' : requestError.message;
      previewFreshness.invalidate(message);
      setPreviewAvailable(false);
      setPreviewError(message);
    } finally {
      window.clearTimeout(timeout);
      previewController.current = null;
      previewRequestActive.current = false;
      finishRead();
    }
  }, [previewFreshness]);

  const previewPolling = previewShouldPoll(activeTab, state, protocol, previewEnabled);
  useEffect(() => {
    if (
      !['acquisition', 'alignment'].includes(activeTab)
      || !previewEnabled
      || (!previewPolling && (!state?.connected || !state?.application_running))
      || protocolSaving
    ) return undefined;
    if (!previewPolling) { loadPreview(); return undefined; }
    const stop = startPreviewPolling(loadPreview);
    return () => { stop(); previewController.current?.abort(); };
  }, [
    activeTab,
    loadPreview,
    previewEnabled,
    state?.application_running,
    state?.connected,
    state?.remoteex_status,
    protocol?.status,
    protocolSaving,
    previewPolling,
  ]);

  useEffect(() => {
    const timer = window.setInterval(() => setPreviewClock(performance.now()), 500);
    return () => { window.clearInterval(timer); previewController.current?.abort(); };
  }, []);
  const previewTiming = previewFreshness.status(previewClock);
  const previewFresh = previewAvailable && !previewError && previewTiming.fresh;
  const previewStride = activeTab === 'alignment' && previewPolling
    && String(state?.acquisition_mode).toLowerCase() === 'live' && alignmentAverage?.enabled
    ? alignmentAverage.frames : 1;
  const { hz: previewHz, frameDisplayed } = useFrameDisplayRate('vd2',
    ['acquisition', 'alignment'].includes(activeTab) && previewEnabled, previewStride);

  useEffect(() => {
    const canvas = previewCanvas.current;
    if (!canvas || !preview) return;
    const paint = previewPaint.current;
    const frame = paint.frame;
    const newFrame = preview !== paint.latest;
    const contextChanged = canvas !== paint.canvas || previewStride !== paint.stride
      || preview.width !== frame?.width || preview.height !== frame?.height
      || preview.calibration_key !== frame?.calibration_key;
    if (newFrame) {
      paint.latest = preview;
      paint.pending = (paint.pending || 0) + 1;
    }
    // Pace the canvas only. Alignment readout still uses the full server stream.
    const next = contextChanged || paint.pending >= previewStride ? preview : frame;
    if (!contextChanged && next === frame && paint.palette === lutPalette && paint.range === lutRange) return;
    if (drawPreview(canvas, next, lutPalette, lutRange.minimum, lutRange.maximum)) {
      if (next === preview) paint.pending = 0;
      Object.assign(paint, { frame: next, canvas, stride: previewStride, palette: lutPalette, range: lutRange });
      canvas.dataset.frameReceivedAt = next.received_at || '';
      canvas.dataset.frameDrawnAt = performance.now().toFixed(3);
      frameDisplayed(next.received_at || next);
    }
  }, [lutPalette, lutRange, preview, previewStride, activeTab, frameDisplayed]);

  useEffect(() => {
    try {
      window.localStorage.setItem('pyconlyse.vd2.imageRight', String(imageRight));
      window.localStorage.setItem('pyconlyse.vd2.imageWidth', String(imageWidth));
    } catch (_error) { /* Keep the in-memory layout. */ }
  }, [imageRight, imageWidth]);

  const calibrationKey = previewAvailable ? preview?.calibration_key : null;
  const calibrationAvailable = Boolean(previewAvailable && preview?.calibration);
  useEffect(() => {
    if (activeTab !== 'alignment' || !calibrationKey || calibrationAvailable
        || !state?.connected || !state?.application_running
        || protocolHardwareActive) return undefined;
    let disposed = false;
    let timer;
    const controller = new AbortController();
    setCalibrationUpdating(true);
    (async () => {
      try {
        const response = await fetchVd2(`${API_BASE}/alignment/calibration`, {
          method: 'POST', credentials: 'include', signal: controller.signal,
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Calibration unavailable');
        if (!disposed) setCalibrationError('');
        if (payload.stream_state === 'no_valid_image') {
          if (!disposed) {
            setPreviewAvailable(false);
            setPreviewStream('no_valid_image');
            setCalibration(null);
            setCalibrationError('');
          }
          return;
        }
        // Only preview may pair axes with a frame; a late response cannot label
        // an old frame with the calibration of a newly selected wavelength.
        if (!disposed) await loadPreview();
      } catch (error) {
        if (!disposed) setCalibrationError(error.message);
      } finally {
        if (!disposed) {
          setCalibrationUpdating(false);
          timer = window.setTimeout(() => setCalibrationAttempt(value => value + 1), 5000);
        }
      }
    })();
    return () => {
      disposed = true;
      controller.abort();
      window.clearTimeout(timer);
      setCalibrationUpdating(false);
    };
  }, [activeTab, calibrationKey, calibrationAvailable, calibrationAttempt, loadPreview,
    state?.connected, state?.application_running, protocolHardwareActive]);
  const alignment = useMemo(() => alignmentRegionGeometry(calibration, alignmentRegion), [calibration, alignmentRegion]);
  const alignmentContext = !alignment.error && preview?.calibration &&
    JSON.stringify([preview.calibration_key, preview.measurement_key || preview.intensity_key, alignmentRegion]);
  const resizeImage = event => {
    event.preventDefault();
    const start = event.clientX;
    const size = imageWidth;
    const move = e => setImageWidth(clamp(size + (e.clientX - start) * (imageRight ? -1 : 1), 320, 760));
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  return {
    state, setState, preview, previewAvailable, errors, setErrors, readFailures,
    activeErrorId, setActiveErrorId, previewError, setPreviewError, setAlignmentAverage,
    liveAverageReadError, setLiveAverageReadError, setPreviewEnabled, busy, setBusy,
    activeTab, setActiveTab, calibration, calibrationUpdating, calibrationError,
    setCalibrationAttempt, previewStream, setPreviewStream, alignmentRegion,
    setAlignmentRegion, alignmentMemoryError, imageRight, setImageRight, imageWidth,
    setImageWidth, dragPanel, setDragPanel, lutPalette, setLutPalette, lutRange,
    setLutRange, roiTool, setRoiTool, rois, setRois, roiMemoryError, linkRois, setLinkRois,
    selectedRoiId, setSelectedRoiId, drawingRoi, setDrawingRoi, protocol, setProtocol,
    protocolHardwareActive, protocolSaving, projectError, protocolSettings,
    setProtocolSettings, project, serverWorkspace, preparedPhase, setPreparedPhase,
    guidedRun, setGuidedRun, guidedChoice, setGuidedChoice, guidedMessage,
    setGuidedMessage, preparationTick, setPreparationTick, protocolStarting,
    setProtocolStarting, protocolStartActive, protocolAlive, phasePlanAbort,
    repeatConflict, setRepeatConflict, alignmentMeasurements, stateReadEpoch,
    previewPaused, previewReadComplete, previewController, previewCanvas, previewOverlay,
    nextRoiId, phaseClickTimer, lastPollError, reportError, resolveReadErrors, loadPreview,
    previewTiming, previewFresh, previewStride, previewHz, alignment, alignmentContext,
    resizeImage,
  };
}
