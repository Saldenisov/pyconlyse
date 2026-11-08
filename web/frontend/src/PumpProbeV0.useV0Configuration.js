import { useCallback, useEffect, useMemo } from 'react';
import { SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM, SAMPLE_STAGE_SPEED_MM_PER_SEC, pumpProbeRequest, clamp, parseDelayPointsText, settingsToApi, hardwareConfigToApi, hardwareConfigFromApi } from './pump-probe-v0/shared';

export function useV0Configuration({
  settings, setSettings, hardwareConfig, setHardwareConfig, deviceConfig,
  setDeviceConfig, samplePositionMm, setSamplePositionMm, sampleTargetMm,
  setSampleTargetMm, samplePositionsMm, setSamplePositionsMm, fallbackRun, backendState,
  setBackendState, setBackendError, setConfigurationError, setActionError, setRunBusy,
  runBusyRef, setTangoRunPreview, setDelayImportError, localIndex, setLocalIndex,
  localRunning, setSelectedWavelengthRange, setSelectedDelayRange, setPlotRevision,
  netioOpen, sampleName, setSampleName, dataBrowserOpen, dataRoot, dataPath,
  dataSelectedPath, setDataSelectedPath, dataTopPath, setDataTopPath, dataFolderName,
  setDataFolderName, dataLoading, loadedOdDataset, setLoadedOdDataset, odDisplayOwner,
  setOdDisplayOwner, odDisplayEpochRef, setSourceOdDataset, treatmentPreview,
  setTreatmentPreview, setTreatmentOpen, rawDataset, setRawDataset, derivedSources,
  setDeriveBusy, setDeriveError, deriveControllerRef, setSpectraViewMode,
  refreshRequestRef, configQueueRef, configRequestRef, desiredConfigRef,
  stateMutationRevisionRef, refreshState, postAndRefresh, loadNetioOutputs,
  loadTangoStates, loadDataPath, createRunFolder,
}) {
  const deriveDatasets = useCallback(async (method) => {
    if (derivedSources.length < 2) return;
    deriveControllerRef.current?.abort();
    const controller = new AbortController(); deriveControllerRef.current = controller;
    const epoch = ++odDisplayEpochRef.current;
    setDeriveBusy(true); setDeriveError(''); setTreatmentOpen(false);
    try {
      const payload = await pumpProbeRequest('/data/derive', {
        method: 'POST', signal: controller.signal,
        body: JSON.stringify({ method, sources: derivedSources.map(({ path, source_sha256 }) => ({ path, source_sha256 })) }),
      });
      if (epoch !== odDisplayEpochRef.current) return;
      if (!payload.source_spec || !payload.heatmap?.length || payload.delays?.length !== payload.heatmap.length
          || !payload.heatmap.every((row) => row.length === payload.wavelengths?.length)) throw new Error('Derived result has inconsistent data or axes.');
      setSourceOdDataset(payload); setLoadedOdDataset(payload); setTreatmentPreview(null);
      setOdDisplayOwner('file'); setRawDataset(payload.channels?.length ? payload : null);
      setSpectraViewMode(payload.channels?.length ? 'raw' : 'current');
      setSelectedWavelengthRange(null); setSelectedDelayRange(null); setLocalIndex(0);
      setPlotRevision((value) => value + 1);
    } catch (error) {
      if (epoch === odDisplayEpochRef.current && error.name !== 'AbortError') setDeriveError(error.message);
    } finally {
      if (deriveControllerRef.current === controller) { deriveControllerRef.current = null; setDeriveBusy(false); }
    }
  }, [derivedSources]);

  const handleSettingChange = useCallback((key, value) => {
    setSettings((current) => {
      if (key === 'delayPointsPs') {
        if (!value?.length) {
          return {
            ...current,
            delayPointsPs: null,
            delayMode: 'generated',
          };
        }
        return {
          ...current,
          delayPointsPs: value,
          delayMode: 'custom',
          pointCount: value.length,
          scanStartPs: value[0],
          delayStepPs: value.length > 1 ? value[1] - value[0] : current.delayStepPs,
        };
      }
      const next = { ...current, [key]: value };
      if (key === 'pointCount') {
        next.pointCount = clamp(Number(value) || 2, 2, 400);
      }
      if (key === 'scanStartPs' || key === 'delayStepPs' || key === 'pointCount') {
        next.delayPointsPs = null;
        next.delayMode = 'generated';
      }
      return next;
    });
    if (key === 'pointCount') {
      setLocalIndex((index) => Math.min(index, Number(value) - 1));
    }
  }, []);

  const handleDelayPointsLoad = useCallback((text) => {
    try {
      const points = parseDelayPointsText(text, settings.realZeroPs);
      handleSettingChange('delayPointsPs', points);
      setDelayImportError('');
    } catch (error) {
      setDelayImportError(error.message);
    }
  }, [handleSettingChange, settings.realZeroPs]);

  const handleHardwareModeChange = useCallback((mode) => {
    setHardwareConfig((current) => ({
      ...current,
      controlMode: mode === 'tango' ? 'tango' : 'emulator',
    }));
  }, []);

  const handleConfigLoad = useCallback((text) => {
    try {
      const parsed = JSON.parse(text);
      const loadedSettings = parsed.settings || parsed;
      setSettings((current) => ({
        ...current,
        ...loadedSettings,
        delayMode: loadedSettings.delayPointsPs?.length ? 'custom' : 'generated',
      }));
      if (parsed.devices) {
        setDeviceConfig((current) => ({ ...current, ...parsed.devices }));
      }
      if (parsed.hardwareConfig || parsed.hardware) {
        setHardwareConfig((current) => ({
          ...current,
          ...hardwareConfigFromApi(parsed.hardwareConfig || parsed.hardware),
        }));
      }
      if (parsed.sampleStage) {
        setSamplePositionMm(clamp(Number(parsed.sampleStage.positionMm) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
        setSampleTargetMm(clamp(Number(parsed.sampleStage.targetMm) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
        const loadedPositions = parsed.sampleStage.positionsMm || parsed.sampleStage.markersMm;
        if (Array.isArray(loadedPositions)) {
          setSamplePositionsMm(loadedPositions.map((value) => (
            clamp(Number(value) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM)
          )));
        }
      }
      if (parsed.data) {
        setSampleName(String(parsed.data.sampleName || ''));
        setDataSelectedPath(String(parsed.data.selectedPath || ''));
        setDataTopPath(String(parsed.data.topPath || parsed.data.selectedPath || ''));
        setDataFolderName(String(parsed.data.folderName || ''));
      }
      setBackendError('');
    } catch (error) {
      setBackendError(`Config load failed: ${error.message}`);
    }
  }, []);

  const handleConfigSave = useCallback(() => {
    const payload = {
      version: 1,
      experiment: 'pump-probe-v0',
      settings,
      hardwareConfig,
      hardware: hardwareConfigToApi(hardwareConfig, deviceConfig),
      devices: deviceConfig,
      sampleStage: {
        positionMm: samplePositionMm,
        targetMm: sampleTargetMm,
        positionsMm: samplePositionsMm,
      },
      data: {
        sampleName,
        root: dataRoot,
        selectedPath: dataSelectedPath,
        topPath: dataTopPath,
        folderName: dataFolderName,
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'pump-probe-v0-config.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }, [dataFolderName, dataRoot, dataSelectedPath, dataTopPath, deviceConfig, hardwareConfig, sampleName, samplePositionMm, samplePositionsMm, sampleTargetMm, settings]);

  const moveSampleStage = useCallback((positionMmValue) => {
    const next = clamp(Number(positionMmValue) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM);
    setSampleTargetMm(next);
    if (hardwareConfig.controlMode === 'tango') {
      setBackendState((current) => (current ? {
        ...current,
        sample_set_position_mm: next,
        sample_stage_moving: true,
      } : current));
      postAndRefresh('/sample-stage/move', { position_mm: next });
    }
  }, [hardwareConfig.controlMode, postAndRefresh]);

  const setSampleMarker = useCallback((index, positionMmValue) => {
    setSamplePositionsMm((current) => current.map((marker, markerIndex) => (
      markerIndex === index ? clamp(positionMmValue, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM) : marker
    )));
  }, []);

  const stopSampleStage = useCallback(() => {
    if (hardwareConfig.controlMode === 'tango') {
      postAndRefresh('/sample-stage/stop');
      return;
    }
    setSampleTargetMm(samplePositionMm);
  }, [hardwareConfig.controlMode, postAndRefresh, samplePositionMm]);

  useEffect(() => {
    if (hardwareConfig.controlMode === 'tango') {
      return undefined;
    }
    let lastTime = performance.now();
    const timerId = window.setInterval(() => {
      const now = performance.now();
      const elapsedSec = Math.max(0, (now - lastTime) / 1000);
      lastTime = now;
      setSamplePositionMm((current) => {
        const distance = sampleTargetMm - current;
        const maxStep = SAMPLE_STAGE_SPEED_MM_PER_SEC * elapsedSec;
        if (Math.abs(distance) <= maxStep) {
          return sampleTargetMm;
        }
        return current + Math.sign(distance) * maxStep;
      });
    }, 50);
    return () => window.clearInterval(timerId);
  }, [hardwareConfig.controlMode, sampleTargetMm]);

  useEffect(() => {
    refreshState();
    const timerId = window.setInterval(refreshState, 250);
    return () => {
      window.clearInterval(timerId);
      refreshRequestRef.current.controller?.abort();
    };
  }, [refreshState]);

  const configurationPayload = useMemo(() => ({
    ...settingsToApi(settings),
    hardware_config: hardwareConfigToApi(hardwareConfig, deviceConfig),
  }), [settings, hardwareConfig, deviceConfig]);
  desiredConfigRef.current = configurationPayload;

  const queueConfiguration = useCallback((payload) => {
    const signature = JSON.stringify(payload);
    const previous = configRequestRef.current;
    if (previous?.signature === signature && previous.status !== 'rejected') {
      return previous.promise;
    }
    const pending = { signature, status: 'pending', promise: null };
    // Serialize writes: an older request cannot finish after the latest ACK.
    pending.promise = configQueueRef.current.catch(() => {}).then(async () => {
      try {
        const state = await pumpProbeRequest('/config', {
          method: 'POST', body: JSON.stringify(payload),
        });
        pending.status = 'fulfilled';
        if (signature === JSON.stringify(desiredConfigRef.current)) {
          stateMutationRevisionRef.current += 1;
          setBackendState(state);
          setConfigurationError('');
        }
        return state;
      } catch (error) {
        pending.status = 'rejected';
        if (signature === JSON.stringify(desiredConfigRef.current)) setConfigurationError(error.message);
        throw error;
      }
    });
    configQueueRef.current = pending.promise;
    configRequestRef.current = pending;
    return pending.promise;
  }, []);

  const awaitLatestConfiguration = useCallback(async () => {
    // Settings may change while an older request is pending.
    while (true) {
      const payload = desiredConfigRef.current;
      const signature = JSON.stringify(payload);
      const state = await queueConfiguration(payload);
      if (signature === JSON.stringify(desiredConfigRef.current)) return state;
    }
  }, [queueConfiguration]);

  useEffect(() => {
    queueConfiguration(configurationPayload).catch(() => {});
  }, [configurationPayload, queueConfiguration]);

  useEffect(() => {
    if (netioOpen) {
      loadNetioOutputs();
      loadTangoStates();
    }
  }, [loadNetioOutputs, loadTangoStates, netioOpen]);

  useEffect(() => {
    if (dataBrowserOpen && !dataPath && !dataLoading) {
      loadDataPath(dataSelectedPath);
    }
  }, [dataBrowserOpen, dataLoading, dataPath, dataSelectedPath, loadDataPath]);

  const treatmentRequestEpoch = odDisplayEpochRef.current;
  const displayedOdDataset = odDisplayOwner === 'file' ? (treatmentPreview || loadedOdDataset) : null;
  const fileOdLoaded = Boolean(displayedOdDataset?.heatmap);
  const liveWavelengths = backendState?.wavelengths || fallbackRun.wavelengths;
  const wavelengths = fileOdLoaded ? displayedOdDataset.wavelengths : liveWavelengths;
  const visibleRawDataset = fileOdLoaded ? displayedOdDataset : rawDataset;
  const delays = fileOdLoaded ? displayedOdDataset.delays : (backendState?.delays || fallbackRun.delays);
  const heatmap = fileOdLoaded ? displayedOdDataset.heatmap : (backendState?.heatmap || fallbackRun.heatmap);
  const liveOd = backendState?.live_od || null;
  const currentIndex = fileOdLoaded ? localIndex : (backendState?.current_index ?? localIndex);
  const activeCurrentIndex = clamp(currentIndex, 0, Math.max(0, delays.length - 1));
  const running = backendState?.running ?? localRunning;
  const handleRun = useCallback(async (action = 'new') => {
    if (runBusyRef.current) return;
    setActionError('');
    if (running) {
      postAndRefresh('/run', { running: false });
      return;
    }
    runBusyRef.current = true;
    setRunBusy(true);
    try {
      await awaitLatestConfiguration();
      const savePath = action === 'continue' ? backendState?.run?.output_dir : await createRunFolder();
      const configured = await awaitLatestConfiguration();
      const payload = {
        running: true, run_action: action,
        ...(savePath ? { save_path: savePath } : {}), sample_name: sampleName,
      };
      if (configured?.control_mode === 'tango') {
        const preview = await pumpProbeRequest('/run/plan', { method: 'POST', body: JSON.stringify(payload) });
        setTangoRunPreview(preview);
        if (!preview.commissioned) throw new Error('Tango RAW profile requires BG_level verification for the configured Andor readout.');
        payload.plan_fingerprint = preview.fingerprint;
      }
      const startedState = await postAndRefresh('/run', payload);
      if (startedState?.running) {
        odDisplayEpochRef.current += 1;
        deriveControllerRef.current?.abort(); deriveControllerRef.current = null; setDeriveBusy(false);
        setOdDisplayOwner('live'); setSpectraViewMode('current'); setTreatmentOpen(false);
        setSelectedWavelengthRange(null); setSelectedDelayRange(null);
        setPlotRevision((value) => value + 1);
      }
    } catch (error) { setActionError(error.message); }
    finally { runBusyRef.current = false; setRunBusy(false); }
  }, [awaitLatestConfiguration, backendState, createRunFolder, postAndRefresh, running, sampleName]);

  return {
    deriveDatasets, handleSettingChange, handleDelayPointsLoad, handleHardwareModeChange,
    handleConfigLoad, handleConfigSave, moveSampleStage, setSampleMarker, stopSampleStage,
    treatmentRequestEpoch, displayedOdDataset, fileOdLoaded, liveWavelengths, wavelengths,
    visibleRawDataset, delays, heatmap, liveOd, currentIndex, activeCurrentIndex, running,
    handleRun,
  };
}
