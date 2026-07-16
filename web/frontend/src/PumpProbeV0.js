import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './css/PumpProbeV0.css';
import {
  STAGE_MIN_MM, STAGE_MAX_MM, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM,
  SAMPLE_STAGE_SPEED_MM_PER_SEC, DEFAULT_SAMPLE_POSITIONS_MM, MM_PER_PS, API_BASE,
  pumpProbeRequest, compactHardwareError, fetchJsonWithRetry, clamp, indexesInRange,
  averageRows, averageColumns, nearestIndex, rangeAround,
  buildSyntheticRun, makeCurrentSpectra, DEFAULT_SETTINGS, DEFAULT_HARDWARE_CONFIG,
  DEFAULT_DEVICE_CONFIG, NETIO_POWER_CHANNELS, HARDWARE_TANGO_SERVERS, devicePath,
  normalizeNetioOutputs, activeDelayPoints, parseDelayPointsText, displayPathTail, settingsToApi,
  hardwareConfigToApi, hardwareConfigFromApi,
} from './pump-probe-v0/shared';
import {
  PlotPanel, SampleStageControl, DeviceConfigModal, DataBrowserWindow, HardwareModal,
  PlotlyChart, HeatmapSelectorChart, StageControl, SettingsPanel,
} from './pump-probe-v0/components';

// Coordinates V0 state, API calls, and data selection. Panels live in pump-probe-v0/components.
function PumpProbeV0() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [hardwareConfig, setHardwareConfig] = useState(DEFAULT_HARDWARE_CONFIG);
  const [deviceConfig, setDeviceConfig] = useState(DEFAULT_DEVICE_CONFIG);
  const [deviceConfigKey, setDeviceConfigKey] = useState(null);
  const [samplePositionMm, setSamplePositionMm] = useState(0);
  const [sampleTargetMm, setSampleTargetMm] = useState(0);
  const [samplePositionsMm, setSamplePositionsMm] = useState(DEFAULT_SAMPLE_POSITIONS_MM);
  const plannedDelays = useMemo(() => activeDelayPoints(settings), [settings]);
  const fallbackRun = useMemo(() => buildSyntheticRun(plannedDelays.length), [plannedDelays.length]);
  const [backendState, setBackendState] = useState(null);
  const [backendError, setBackendError] = useState('');
  const [localIndex, setLocalIndex] = useState(0);
  const localRunning = false;
  const [localPositionMm, setLocalPositionMm] = useState(0);
  const [stepPs, setStepPs] = useState(1);
  const [zeroMm, setZeroMm] = useState(0);
  const [localElectronState, setLocalElectronState] = useState('OFF');
  const [localFaradayClosed, setLocalFaradayClosed] = useState(true);
  const [selectedWavelengthRange, setSelectedWavelengthRange] = useState(null);
  const [selectedDelayRange, setSelectedDelayRange] = useState(null);
  const [plotRevision, setPlotRevision] = useState(0);
  const [netioOpen, setNetioOpen] = useState(false);
  const [netioDevices, setNetioDevices] = useState({});
  const [netioLoading, setNetioLoading] = useState(false);
  const [netioError, setNetioError] = useState('');
  const [tangoStates, setTangoStates] = useState({});
  const [tangoLoading, setTangoLoading] = useState(false);
  const [tangoError, setTangoError] = useState('');
  const [hardwareInitStatus, setHardwareInitStatus] = useState(null);
  const [hardwareInitLoading, setHardwareInitLoading] = useState(false);
  const [sampleName, setSampleName] = useState('');
  const [dataBrowserOpen, setDataBrowserOpen] = useState(false);
  const [dataRoot, setDataRoot] = useState('');
  const [dataPath, setDataPath] = useState('');
  const [dataParent, setDataParent] = useState('');
  const [dataEntries, setDataEntries] = useState([]);
  const [dataSelectedPath, setDataSelectedPath] = useState('');
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState('');
  const [loadedOdDataset, setLoadedOdDataset] = useState(null);
  const [rawDataset, setRawDataset] = useState(null);
  const [spectraViewMode, setSpectraViewMode] = useState('current');
  const [savedKinetics, setSavedKinetics] = useState([]);
  const [kineticCounter, setKineticCounter] = useState(1);
  const [savedOdSpectra, setSavedOdSpectra] = useState([]);
  const [odSpectrumCounter, setOdSpectrumCounter] = useState(1);
  const refreshRequestRef = useRef({ inFlight: false, controller: null });

  const closeHardwareModal = useCallback(() => {
    setNetioOpen(false);
    setNetioError('');
    setTangoError('');
  }, []);

  const refreshState = useCallback(async () => {
    if (refreshRequestRef.current.inFlight) {
      return;
    }
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 2000);
    refreshRequestRef.current = { inFlight: true, controller };
    try {
      const state = await pumpProbeRequest('/state', { signal: controller.signal });
      setBackendState(state);
      setBackendError('');
    } catch (error) {
      if (error.name !== 'AbortError') {
        setBackendError(error.message);
      }
    } finally {
      window.clearTimeout(timeoutId);
      if (refreshRequestRef.current.controller === controller) {
        refreshRequestRef.current = { inFlight: false, controller: null };
      }
    }
  }, []);

  const postAndRefresh = useCallback(async (path, payload = {}) => {
    try {
      const state = await pumpProbeRequest(path, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setBackendState(state);
      setBackendError('');
      return state;
    } catch (error) {
      setBackendError(error.message);
      return null;
    }
  }, []);

  const runHardwareInitialization = useCallback(async (fix = true) => {
    setHardwareInitLoading(true);
    try {
      const status = await pumpProbeRequest(fix ? '/hardware/initialize' : '/hardware/preflight', {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setHardwareInitStatus(status);
      setBackendError(status.success ? '' : (status.recommendation || status.message || 'Hardware initialization failed'));
      await refreshState();
      return status;
    } catch (error) {
      setHardwareInitStatus({ success: false, message: error.message, checks: [] });
      setBackendError(error.message);
      return null;
    } finally {
      setHardwareInitLoading(false);
    }
  }, [refreshState]);

  const loadNetioOutputs = useCallback(async () => {
    const deviceNames = [...new Set(NETIO_POWER_CHANNELS.map((channel) => channel.device))];
    setNetioLoading(true);
    setNetioError('');
    const entries = [];
    const errors = [];
    await Promise.all(deviceNames.map(async (deviceName) => {
      try {
        const payload = await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
          credentials: 'include',
        });
        entries.push([deviceName, {
          state: payload.state,
          outputs: normalizeNetioOutputs(payload.outputs),
        }]);
      } catch (error) {
        errors.push(`${deviceName}: ${error.message}`);
      }
    }));
    if (entries.length) {
      setNetioDevices((current) => ({ ...current, ...Object.fromEntries(entries) }));
    }
    setNetioError(compactHardwareError(errors));
    setNetioLoading(false);
  }, []);

  const toggleNetioChannel = useCallback(async (channel, enabled) => {
    const currentDevice = netioDevices[channel.device];
    if (!currentDevice?.outputs?.length) {
      setNetioError(`No output table for ${channel.device}`);
      return;
    }

    const nextStates = currentDevice.outputs.map((output) => (
      output.id === channel.outputId ? (enabled ? 1 : 0) : output.state
    ));

    setNetioLoading(true);
    setNetioError('');
    try {
      await fetchJsonWithRetry(`/api/device/${devicePath(channel.device)}/command/set_channels_states`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: nextStates }),
      });

      const verifyPayload = await fetchJsonWithRetry(`/api/device/${devicePath(channel.device)}/pdu/outputs`, {
        credentials: 'include',
      });
      setNetioDevices((current) => ({
        ...current,
        [channel.device]: {
          state: verifyPayload.state,
          outputs: normalizeNetioOutputs(verifyPayload.outputs),
        },
      }));
    } catch (error) {
      setNetioError(error.message);
    } finally {
      setNetioLoading(false);
    }
  }, [netioDevices]);

  const setNecessaryHardwarePower = useCallback(async (enabled) => {
    const deviceNames = [...new Set(NETIO_POWER_CHANNELS.map((channel) => channel.device))];
    setNetioLoading(true);
    setNetioError('');
    const entries = [];
    const errors = [];
    await Promise.all(deviceNames.map(async (deviceName) => {
      try {
        const readPayload = await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
          credentials: 'include',
        });

        const targetOutputIds = new Set(
          NETIO_POWER_CHANNELS
            .filter((channel) => channel.device === deviceName)
            .map((channel) => channel.outputId)
        );
        const currentOutputs = normalizeNetioOutputs(readPayload.outputs);
        const nextStates = currentOutputs.map((output) => (
          targetOutputIds.has(output.id) ? (enabled ? 1 : 0) : output.state
        ));

        await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/command/set_channels_states`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ args: nextStates }),
        });

        const verifyPayload = await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
          credentials: 'include',
        });
        entries.push([deviceName, {
          state: verifyPayload.state,
          outputs: normalizeNetioOutputs(verifyPayload.outputs),
        }]);
      } catch (error) {
        errors.push(`${deviceName}: ${error.message}`);
      }
    }));
    if (entries.length) {
      setNetioDevices((current) => ({ ...current, ...Object.fromEntries(entries) }));
    }
    setNetioError(compactHardwareError(errors));
    setNetioLoading(false);
  }, []);

  const loadTangoStates = useCallback(async () => {
    const servers = HARDWARE_TANGO_SERVERS.filter((server) => server.device);
    setTangoLoading(true);
    setTangoError('');
    try {
      const entries = await Promise.all(servers.map(async (server) => {
        try {
          const payload = await fetchJsonWithRetry(`/api/device/${devicePath(server.device)}/state`, {
            credentials: 'include',
          });
          return [server.device, {
            ok: true,
            state: String(payload.state || 'UNKNOWN').replace(/^DevState\./, ''),
            status: payload.status || '',
          }];
        } catch (error) {
          return [server.device, {
            ok: false,
            state: 'OFFLINE',
            error: error.message,
          }];
        }
      }));
      setTangoStates(Object.fromEntries(entries));
    } catch (error) {
      setTangoError(error.message);
    } finally {
      setTangoLoading(false);
    }
  }, []);

  const controlTangoServer = useCallback(async (server, action) => {
    if (!server.device) {
      return;
    }
    setTangoLoading(true);
    setTangoError('');
    try {
      const response = await fetch('/api/server/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ action, device_name: server.device }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to ${action} ${server.label}`);
      }
      await loadTangoStates();
    } catch (error) {
      setTangoError(error.message);
    } finally {
      setTangoLoading(false);
    }
  }, [loadTangoStates]);

  const loadDataPath = useCallback(async (nextPath = '') => {
    setDataLoading(true);
    setDataError('');
    try {
      const query = nextPath ? `?path=${encodeURIComponent(nextPath)}` : '';
      const response = await fetch(`${API_BASE}/data/list${query}`, {
        credentials: 'include',
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to list data path (${response.status})`);
      }
      setDataRoot(payload.root || '');
      setDataPath(payload.path || payload.root || '');
      setDataParent(payload.parent || payload.root || '');
      setDataEntries(payload.entries || []);
      if (!dataSelectedPath && payload.path) {
        setDataSelectedPath(payload.path);
      }
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, [dataSelectedPath]);

  const createSampleFolder = useCallback(async (name) => {
    const folderName = String(name || '').trim();
    if (!folderName) {
      return;
    }
    setDataLoading(true);
    setDataError('');
    try {
      const response = await fetch(`${API_BASE}/data/folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ parent: dataPath || dataRoot, name: folderName }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to create folder (${response.status})`);
      }
      setDataSelectedPath(payload.path);
      await loadDataPath(payload.path);
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, [dataPath, dataRoot, loadDataPath]);

  const loadDataFile = useCallback(async (filePath) => {
    if (!filePath) {
      return;
    }
    setDataLoading(true);
    setDataError('');
    try {
      const response = await fetch(`${API_BASE}/data/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ path: filePath }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to load data file (${response.status})`);
      }
      setDataSelectedPath(payload.path || filePath);
      if (payload.kind === 'od') {
        setLoadedOdDataset(payload);
        setSelectedWavelengthRange(null);
        setSelectedDelayRange(null);
        setPlotRevision((value) => value + 1);
      } else if (payload.kind === 'raw') {
        setRawDataset(payload);
        setSpectraViewMode('raw');
      }
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, []);

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
    const points = parseDelayPointsText(text).slice(0, 400);
    if (points.length >= 2) {
      handleSettingChange('delayPointsPs', points);
    } else {
      setBackendError('Delay TXT must contain at least 2 numeric rows.');
    }
  }, [handleSettingChange]);

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
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'pump-probe-v0-config.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }, [dataRoot, dataSelectedPath, deviceConfig, hardwareConfig, sampleName, samplePositionMm, samplePositionsMm, sampleTargetMm, settings]);

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

  useEffect(() => {
    postAndRefresh('/config', {
      ...settingsToApi(settings),
      hardware_config: hardwareConfigToApi(hardwareConfig, deviceConfig),
    });
  }, [settings, hardwareConfig, deviceConfig, postAndRefresh]);

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

  const fileOdLoaded = loadedOdDataset?.kind === 'od';
  const wavelengths = fileOdLoaded ? loadedOdDataset.wavelengths : (backendState?.wavelengths || fallbackRun.wavelengths);
  const delays = fileOdLoaded ? loadedOdDataset.delays : (backendState?.delays || fallbackRun.delays);
  const heatmap = fileOdLoaded ? loadedOdDataset.heatmap : (backendState?.heatmap || fallbackRun.heatmap);
  const liveOd = backendState?.live_od || null;
  const currentIndex = backendState?.current_index ?? localIndex;
  const activeCurrentIndex = clamp(currentIndex, 0, Math.max(0, delays.length - 1));
  const running = backendState?.running ?? localRunning;
  const realTime = backendState?.real_time ?? false;
  const faradayClosed = backendState?.faraday_closed ?? localFaradayClosed;
  const electronState = backendState?.electron_state || localElectronState;
  const positionMm = backendState?.position_mm ?? localPositionMm;
  const setPositionMm = backendState?.set_position_mm ?? localPositionMm;
  const activeControlMode = hardwareConfig.controlMode || backendState?.control_mode || 'emulator';
  const daqCounter = backendState?.daq_counter || {};
  const counterActive = Boolean(daqCounter.active);
  const counterRateHz = Number(daqCounter.rate_hz || 0);
  const hardwareChecks = hardwareInitStatus?.checks || [];
  const failedHardwareChecks = hardwareChecks.filter((check) => !check.ok);
  const sampleDisplayPositionMm = activeControlMode === 'tango'
    ? (backendState?.sample_position_mm ?? samplePositionMm)
    : samplePositionMm;
  const sampleDisplayTargetMm = activeControlMode === 'tango'
    ? (backendState?.sample_set_position_mm ?? sampleTargetMm)
    : sampleTargetMm;
  const netioAnyOn = NETIO_POWER_CHANNELS.some((channel) => (
    netioDevices[channel.device]?.outputs?.some((output) => (
      output.id === channel.outputId && Number(output.state) === 1
    ))
  ));
  const delayStats = useMemo(() => {
    const finiteDelays = delays.filter((value) => Number.isFinite(value));
    if (!finiteDelays.length) {
      return { pointCount: 0, kineticPs: 0, totalPs: 0 };
    }
    const minDelay = Math.min(...finiteDelays);
    const maxDelay = Math.max(...finiteDelays);
    return {
      pointCount: finiteDelays.length,
      kineticPs: Math.max(0, maxDelay),
      totalPs: maxDelay - minDelay,
    };
  }, [delays]);

  useEffect(() => {
    if (backendState || !localRunning) {
      return undefined;
    }
    const timerId = window.setInterval(() => {
      setLocalIndex((value) => (value + 1) % delays.length);
      setLocalElectronState(localFaradayClosed ? 'OFF' : 'ON');
    }, 200);
    return () => window.clearInterval(timerId);
  }, [backendState, localRunning, localFaradayClosed, delays.length]);

  useEffect(() => {
    if (backendState) {
      return;
    }
    const delayPs = delays[currentIndex] || 0;
    setLocalPositionMm(clamp(-(delayPs + settings.realZeroPs) * MM_PER_PS, STAGE_MIN_MM, STAGE_MAX_MM));
  }, [backendState, currentIndex, delays, settings.realZeroPs]);

  const spectra = useMemo(
    () => backendState?.spectra || makeCurrentSpectra(wavelengths, activeCurrentIndex, electronState),
    [backendState, wavelengths, activeCurrentIndex, electronState]
  );

  const completedHeatmap = backendState || fileOdLoaded
    ? heatmap
    : heatmap.map((row, index) => (
      index <= activeCurrentIndex ? row : row.map(() => null)
    ));
  const kineticWavelength = 445;
  const kineticIndex = wavelengths.reduce((bestIndex, wavelength, index) => (
    Math.abs(wavelength - kineticWavelength) < Math.abs(wavelengths[bestIndex] - kineticWavelength)
      ? index
      : bestIndex
  ), 0);
  const delayStep = Math.abs((delays[1] ?? delays[0] + 1) - (delays[0] ?? 0)) || 1;
  const defaultWavelengthRange = rangeAround(wavelengths, wavelengths[kineticIndex], 10);
  const defaultDelayRange = rangeAround(delays, delays[activeCurrentIndex] || delays[0] || 0, delayStep);
  const activeWavelengthRange = selectedWavelengthRange || defaultWavelengthRange;
  const activeDelayRange = selectedDelayRange || defaultDelayRange;
  const selectedWavelengthIndexes = indexesInRange(wavelengths, activeWavelengthRange);
  const selectedDelayIndexes = indexesInRange(delays, activeDelayRange);
  const safeWavelengthIndexes = selectedWavelengthIndexes.length
    ? selectedWavelengthIndexes
    : [kineticIndex];
  const safeDelayIndexes = selectedDelayIndexes.length
    ? selectedDelayIndexes
    : [activeCurrentIndex];
  const selectedRowsOd = averageRows(heatmap, safeDelayIndexes);
  const selectedRowsHaveData = selectedRowsOd.some((value) => value !== null && value !== undefined);
  const selectedOd = (selectedRowsHaveData ? selectedRowsOd : (liveOd || selectedRowsOd))
    .map((value) => value ?? 0);
  const kineticTrace = averageColumns(heatmap, safeWavelengthIndexes);
  const selectedWavelengthLabel = `${activeWavelengthRange[0].toFixed(1)}-${activeWavelengthRange[1].toFixed(1)} nm`;
  const selectedDelayLabel = `${activeDelayRange[0].toFixed(2)}-${activeDelayRange[1].toFixed(2)} ps`;
  const rawDelayIndexes = rawDataset?.delays?.length
    ? indexesInRange(rawDataset.delays, activeDelayRange)
    : [];
  const rawSafeDelayIndexes = rawDelayIndexes.length
    ? rawDelayIndexes
    : (rawDataset?.delays?.length
      ? [nearestIndex(rawDataset.delays, (activeDelayRange[0] + activeDelayRange[1]) / 2)]
      : []);
  const showRawSpectra = spectraViewMode === 'raw' && rawDataset?.channels?.length;
  const rawColors = ['#f1c84b', '#33c5ff', '#f05d5e', '#c798ff', '#7ee787', '#ff9f43'];
  const savedKineticColors = ['#33c5ff', '#f1c84b', '#c798ff', '#ff9f43', '#7ee787', '#ff6b9a', '#9fb7ff'];
  const currentOdSource = fileOdLoaded
    ? (loadedOdDataset.file_name || 'OD file')
    : 'live';

  const addKineticTrace = () => {
    const nextIndex = kineticCounter;
    const nextColor = savedKineticColors[(nextIndex - 1) % savedKineticColors.length];
    setSavedKinetics((current) => ([
      ...current,
      {
        id: `kinetic-${Date.now()}-${nextIndex}`,
        label: `K${nextIndex}`,
        source: currentOdSource,
        wavelengthRange: [...activeWavelengthRange],
        wavelengthLabel: selectedWavelengthLabel,
        x: [...delays],
        y: kineticTrace.map((value) => (value ?? null)),
        color: nextColor,
      },
    ]));
    setKineticCounter((value) => value + 1);
  };

  const removeKineticTrace = (id) => {
    setSavedKinetics((current) => current.filter((trace) => trace.id !== id));
  };

  const addOdSpectrumTrace = () => {
    const nextIndex = odSpectrumCounter;
    const nextColor = savedKineticColors[(nextIndex - 1) % savedKineticColors.length];
    setSavedOdSpectra((current) => ([
      ...current,
      {
        id: `od-spectrum-${Date.now()}-${nextIndex}`,
        label: `S${nextIndex}`,
        source: currentOdSource,
        delayRange: [...activeDelayRange],
        delayLabel: selectedDelayLabel,
        x: [...wavelengths],
        y: selectedOd.map((value) => (value ?? null)),
        color: nextColor,
      },
    ]));
    setOdSpectrumCounter((value) => value + 1);
  };

  const removeOdSpectrumTrace = (id) => {
    setSavedOdSpectra((current) => current.filter((trace) => trace.id !== id));
  };

  const plotTheme = {
    paper_bgcolor: '#11151b',
    plot_bgcolor: '#07090d',
    font: { color: '#d9dde4', family: 'Segoe UI, Arial, sans-serif' },
    margin: { l: 58, r: 18, t: 20, b: 48 },
    uirevision: `pump-probe-v0-${plotRevision}`,
    dragmode: 'zoom',
    xaxis: {
      gridcolor: '#26313b',
      zerolinecolor: '#59636d',
      title: { text: 'Wavelength, nm' },
    },
    yaxis: {
      gridcolor: '#26313b',
      zerolinecolor: '#59636d',
    },
  };

  const spectraData = showRawSpectra
    ? rawDataset.channels.map((channel, index) => ({
      x: rawDataset.wavelengths,
      y: averageRows(channel.values || [], rawSafeDelayIndexes).map((value) => value ?? 0),
      type: 'scatter',
      mode: 'lines',
      name: channel.label || channel.key,
      line: { color: rawColors[index % rawColors.length], width: index < 3 ? 2 : 1.5 },
    }))
    : [
      {
        x: wavelengths,
        y: spectra.signal,
        type: 'scatter',
        mode: 'lines',
        name: 'Is',
        line: { color: '#f05d5e', width: 2 },
      },
      {
        x: wavelengths,
        y: spectra.reference,
        type: 'scatter',
        mode: 'lines',
        name: 'Ir',
        line: { color: '#33c5ff', width: 2 },
      },
      ...(spectra.background_available === false ? [] : [{
        x: wavelengths,
        y: spectra.background,
        type: 'scatter',
        mode: 'lines',
        name: 'BG',
        line: { color: '#f1c84b', width: 1.5 },
      }]),
    ];
  const spectraTitle = showRawSpectra
    ? `Raw spectrum (${rawDataset.file_name || 'ZIP'})`
    : 'Current spectra';

  const spectraLayout = {
    ...plotTheme,
    yaxis: { ...plotTheme.yaxis, title: { text: 'Amplitude' } },
    legend: { orientation: 'h', y: 1.16, x: 0 },
  };

  const savedOdSpectrumData = savedOdSpectra.map((trace) => ({
    x: trace.x,
    y: trace.y,
    type: 'scatter',
    mode: 'lines',
    name: `${trace.label} ${trace.delayLabel}`,
    line: { color: trace.color, width: 1.8, dash: 'dot' },
    hovertemplate: `${trace.label}<br>%{x:.1f} nm<br>OD=%{y:.5f}<extra>${trace.source}</extra>`,
  }));
  const odSpectrumData = [
    ...savedOdSpectrumData,
    {
      x: wavelengths,
      y: selectedOd,
      type: 'scatter',
      mode: 'lines',
      name: `selection ${selectedDelayLabel}`,
      line: { color: '#7ee787', width: 2.4 },
    },
  ];

  const odSpectrumLayout = {
    ...plotTheme,
    yaxis: { ...plotTheme.yaxis, title: { text: 'delta O.D.' }, range: [-0.006, 0.006], fixedrange: true },
  };

  const savedKineticsData = savedKinetics.map((trace) => ({
    x: trace.x,
    y: trace.y,
    type: 'scatter',
    mode: 'lines',
    name: `${trace.label} ${trace.wavelengthLabel}`,
    line: { color: trace.color, width: 1.8, dash: 'dot' },
    hovertemplate: `${trace.label}<br>%{x:.2f} ps<br>OD=%{y:.5f}<extra>${trace.source}</extra>`,
  }));
  const kineticsData = [
    ...savedKineticsData,
    {
      x: delays,
      y: kineticTrace,
      type: 'scatter',
      mode: 'lines',
      name: `selection ${selectedWavelengthLabel}`,
      line: { color: '#f05d5e', width: 2.4 },
    },
    {
      x: [delays[activeCurrentIndex]],
      y: [kineticTrace[activeCurrentIndex]],
      type: 'scatter',
      mode: 'markers',
      name: 'current',
      marker: { color: '#f1c84b', size: 9 },
    },
  ];

  const kineticsLayout = {
    ...plotTheme,
    xaxis: { ...plotTheme.xaxis, title: { text: 'Time delay, ps' } },
    yaxis: { ...plotTheme.yaxis, title: { text: 'delta O.D.' }, range: [-0.18, 0.28] },
    legend: { orientation: 'h', y: 1.16, x: 0 },
  };

  const heatmapData = [
    {
      x: wavelengths,
      y: delays,
      z: completedHeatmap,
      type: 'heatmap',
      colorscale: [
        [0, '#13294b'],
        [0.35, '#1f8f7a'],
        [0.55, '#f0d34f'],
        [1, '#e6462e'],
      ],
      zmin: -0.12,
      zmax: 0.25,
      colorbar: { title: 'delta O.D.' },
      hovertemplate: 'wl=%{x:.1f} nm<br>delay=%{y:.2f} ps<br>OD=%{z:.4f}<extra></extra>',
    },
  ];

  const heatmapLayout = {
    ...plotTheme,
    dragmode: false,
    margin: { l: 64, r: 78, t: 20, b: 48 },
    xaxis: {
      ...plotTheme.xaxis,
      range: [wavelengths[0], wavelengths[wavelengths.length - 1]],
      fixedrange: true,
    },
    yaxis: {
      ...plotTheme.yaxis,
      title: { text: 'Time delay, ps' },
      range: [delays[0], delays[delays.length - 1]],
      fixedrange: true,
    },
  };
  const heatmapConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    doubleClick: false,
    scrollZoom: false,
  }), []);
  const delayPreviewData = [
    {
      x: delays.map((_delay, index) => index + 1),
      y: delays,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'delay',
      line: { color: '#33c5ff', width: 1.5 },
      marker: { color: '#f1c84b', size: 3 },
      hovertemplate: 'point=%{x}<br>delay=%{y:.3f} ps<extra></extra>',
    },
  ];
  const delayPreviewLayout = {
    ...plotTheme,
    margin: { l: 48, r: 12, t: 8, b: 34 },
    xaxis: { ...plotTheme.xaxis, title: { text: 'Point' }, fixedrange: true },
    yaxis: { ...plotTheme.yaxis, title: { text: 'Delay, ps' }, fixedrange: true },
    showlegend: false,
  };
  const delayPreviewConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    scrollZoom: false,
  }), []);
  const chartConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: true,
    modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d', 'resetScale2d'],
    scrollZoom: true,
  }), []);
  const plotInteractionProps = {
  };

  return (
    <main className="pp-page">
      <header className="pp-header">
        <div>
          <h1>V0 Pump-Probe</h1>
          <div className="pp-subtitle">DLIII-V0 / Andor CCD / pulse radiolysis</div>
        </div>
        <SampleStageControl
          positionMm={sampleDisplayPositionMm}
          targetMm={sampleDisplayTargetMm}
          positions={samplePositionsMm}
          onMove={moveSampleStage}
          onStop={stopSampleStage}
          onMarkerMove={setSampleMarker}
          onOpenConfig={setDeviceConfigKey}
        />
        <div className="pp-run-controls">
          <button
            type="button"
            className={`pp-device-pill ${netioAnyOn ? 'pp-device-powered' : ''}`}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setNetioOpen(true);
            }}
            onClick={() => setNetioOpen(true)}
          >
            Hardware
          </button>
          <button
            type="button"
            className={hardwareInitStatus?.success ? 'pp-action-ok' : ''}
            disabled={hardwareInitLoading}
            onClick={() => runHardwareInitialization(true)}
            title="Check Tango servers, NETIO power, OWIS axes, DG645 recall 8, and DAQmx counter"
          >
            {hardwareInitLoading ? 'Init...' : 'Initialize HW'}
          </button>
          <button
            type="button"
            onClick={() => {
              postAndRefresh('/run', { running: !running });
            }}
          >
            {running ? 'Stop' : 'Start'}
          </button>
          <button
            type="button"
            className={faradayClosed ? 'pp-action-ok' : 'pp-action-warn'}
            onClick={() => {
              const nextClosed = !faradayClosed;
              setLocalFaradayClosed(nextClosed);
              setLocalElectronState(nextClosed ? 'OFF' : 'ON');
              postAndRefresh('/faraday', { closed: nextClosed });
            }}
          >
            Faraday {faradayClosed ? 'closed' : 'open'}
          </button>
          <button type="button" onClick={() => postAndRefresh('/crystal/move')}>
            Move Crystal
          </button>
          <button
            type="button"
            className={realTime ? 'pp-action-warn' : ''}
            onClick={() => {
              postAndRefresh('/realtime', { enabled: !realTime });
            }}
          >
            Real time {realTime ? 'on' : 'off'}
          </button>
          <button
            type="button"
            onClick={() => {
              setLocalIndex(0);
              setLocalElectronState('OFF');
              postAndRefresh('/reset');
            }}
          >
            Reset
          </button>
          <div className="pp-data-strip">
            <input
              type="text"
              value={sampleName}
              onChange={(event) => setSampleName(event.target.value)}
              placeholder="sample name"
            />
            <button
              type="button"
              onClick={() => {
                setDataBrowserOpen(true);
                loadDataPath(dataSelectedPath || dataPath || dataRoot);
              }}
            >
              Files
            </button>
            <span title={dataSelectedPath || 'No data folder selected'}>
              {dataSelectedPath ? displayPathTail(dataSelectedPath) : 'no folder'}
            </span>
          </div>
        </div>
      </header>

      <section className="pp-status-strip">
        <div><span>control</span>{activeControlMode}</div>
        <div><span>delay</span>{(delays[activeCurrentIndex] || 0).toFixed(2)} ps</div>
        <div><span>position</span>{positionMm.toFixed(3)} mm</div>
        <div><span>state</span>electrons {electronState}</div>
        <div><span>point</span>{activeCurrentIndex + 1} / {delays.length}</div>
        <div><span>pulses</span>{backendState?.total_pulses ?? 0} @ {backendState?.accelerator_hz ?? 5} Hz</div>
        <div>
          <span>spectrometer</span>
          {backendState?.spectrometer_frames ?? 0} @ {backendState?.spectrometer_hz ?? 15} Hz
          / burst {backendState?.spectrometer_burst ?? 3}
        </div>
        <div className="pp-counter-status">
          <span>counter</span>
          <i className={`pp-counter-led ${counterActive ? 'pp-counter-led-active' : ''}`} />
          {daqCounter.value ?? '-'} @ {counterRateHz.toFixed(2)} Hz
        </div>
      </section>
      {backendError ? <div className="pp-api-error">{backendError}</div> : null}
      {backendState?.hardware_error ? <div className="pp-api-error">{backendState.hardware_error}</div> : null}
      {hardwareInitStatus ? (
        <section className={`pp-hw-init ${hardwareInitStatus.success ? 'pp-hw-init-ok' : 'pp-hw-init-fail'}`}>
          <div className="pp-hw-init-head">
            <strong>{hardwareInitStatus.message || (hardwareInitStatus.success ? 'Hardware initialized' : 'Hardware initialization failed')}</strong>
            <span>{failedHardwareChecks.length ? `${failedHardwareChecks.length} problem(s)` : 'all checks OK'}</span>
            {!hardwareInitStatus.success ? (
              <button type="button" disabled={hardwareInitLoading} onClick={() => runHardwareInitialization(true)}>
                Resolve automatically
              </button>
            ) : null}
          </div>
          <div className="pp-hw-init-list">
            {hardwareChecks.map((check) => (
              <div key={`${check.label}-${check.device || check.axis || check.output_id || ''}`} className={check.ok ? 'pp-hw-check-ok' : 'pp-hw-check-fail'}>
                <b>{check.ok ? 'OK' : 'ERR'}</b>
                <span>{check.label}</span>
                <small>{check.detail}</small>
              </div>
            ))}
          </div>
          {hardwareInitStatus.recommendation ? <p>{hardwareInitStatus.recommendation}</p> : null}
        </section>
      ) : null}
      <section className="pp-selection-strip">
        <div><span>wavelength range</span>{selectedWavelengthLabel}</div>
        <div><span>delay range</span>{selectedDelayLabel}</div>
        <button
          type="button"
          onClick={() => {
            setSelectedWavelengthRange(null);
            setSelectedDelayRange(null);
            setPlotRevision((value) => value + 1);
          }}
        >
          Clear ranges
        </button>
      </section>

      <section className="pp-layout">
        <div className="pp-left-column">
          <PlotPanel
            title={spectraTitle}
            className="pp-panel-fill"
            actions={(
              <div className="pp-panel-toggle">
                <button
                  type="button"
                  className={spectraViewMode === 'current' ? 'pp-panel-toggle-active' : ''}
                  onClick={() => setSpectraViewMode('current')}
                >
                  Current
                </button>
                <button
                  type="button"
                  className={spectraViewMode === 'raw' ? 'pp-panel-toggle-active' : ''}
                  onClick={() => setSpectraViewMode('raw')}
                  disabled={!rawDataset}
                >
                  Raw
                </button>
              </div>
            )}
          >
            <PlotlyChart
              className="pp-plot pp-plot-spectra"
              data={spectraData}
              layout={spectraLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
          </PlotPanel>

          <PlotPanel title="Current OD" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-od"
              data={odSpectrumData}
              layout={odSpectrumLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
          </PlotPanel>
        </div>

        <div className="pp-center-grid">
          <PlotPanel title="OD heatmap" className="pp-panel-fill">
            <HeatmapSelectorChart
              className="pp-plot pp-plot-heatmap"
              data={heatmapData}
              layout={heatmapLayout}
              config={heatmapConfig}
              wavelengthRange={activeWavelengthRange}
              delayRange={activeDelayRange}
              onRangesChange={(nextWavelengthRange, nextDelayRange) => {
                setSelectedWavelengthRange(nextWavelengthRange);
                setSelectedDelayRange(nextDelayRange);
              }}
              {...plotInteractionProps}
            />
          </PlotPanel>

          <PlotPanel title="Kinetics" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-kinetics"
              data={kineticsData}
              layout={kineticsLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
            <div className="pp-kinetics-floating-actions">
              <div className="pp-kinetics-actions">
                <button
                  type="button"
                  className="pp-icon-button"
                  title={`Add kinetics: ${selectedWavelengthLabel}`}
                  onClick={addKineticTrace}
                >
                  + Kinetic
                </button>
                {savedKinetics.length ? (
                  <button
                    type="button"
                    className="pp-icon-button"
                    title="Clear saved kinetics"
                    onClick={() => setSavedKinetics([])}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="pp-kinetic-chip-row">
                  {savedKinetics.map((trace) => (
                    <button
                      key={trace.id}
                      type="button"
                      className="pp-kinetic-chip"
                      title={`${trace.label}: ${trace.wavelengthLabel} / ${trace.source}`}
                      onClick={() => removeKineticTrace(trace.id)}
                    >
                      <span style={{ background: trace.color }} />
                      {trace.label} x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </PlotPanel>

          <PlotPanel title="OD spectrum" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-od"
              data={odSpectrumData}
              layout={odSpectrumLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
            <div className="pp-spectrum-floating-actions">
              <div className="pp-kinetics-actions">
                <button
                  type="button"
                  className="pp-icon-button"
                  title={`Add OD spectrum: ${selectedDelayLabel}`}
                  onClick={addOdSpectrumTrace}
                >
                  + Spectrum
                </button>
                {savedOdSpectra.length ? (
                  <button
                    type="button"
                    className="pp-icon-button"
                    title="Clear saved OD spectra"
                    onClick={() => setSavedOdSpectra([])}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="pp-kinetic-chip-row">
                  {savedOdSpectra.map((trace) => (
                    <button
                      key={trace.id}
                      type="button"
                      className="pp-kinetic-chip"
                      title={`${trace.label}: ${trace.delayLabel} / ${trace.source}`}
                      onClick={() => removeOdSpectrumTrace(trace.id)}
                    >
                      <span style={{ background: trace.color }} />
                      {trace.label} x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </PlotPanel>

          <SettingsPanel
            settings={settings}
            hardwareConfig={hardwareConfig}
            onSettingChange={handleSettingChange}
            onHardwareModeChange={handleHardwareModeChange}
            delayStats={delayStats}
            delayPreviewData={delayPreviewData}
            delayPreviewLayout={delayPreviewLayout}
            delayPreviewConfig={delayPreviewConfig}
            onDelayPointsLoad={handleDelayPointsLoad}
            onConfigLoad={handleConfigLoad}
            onConfigSave={handleConfigSave}
          />
        </div>

        <aside className="pp-right-column">
          <StageControl
            positionMm={positionMm}
            setPositionMm={setPositionMm}
            stepPs={stepPs}
            zeroMm={zeroMm}
            onPositionChange={(value) => {
              setBackendState((current) => (current ? { ...current, set_position_mm: value, stage_moving: true } : current));
              postAndRefresh('/stage/move', { position_mm: value });
            }}
            onStop={() => {
              setBackendState((current) => (current ? {
                ...current,
                set_position_mm: current.position_mm,
                stage_moving: false,
              } : current));
              postAndRefresh('/stage/stop');
            }}
            onStepChange={setStepPs}
            onZeroChange={setZeroMm}
            onOpenConfig={setDeviceConfigKey}
          />
        </aside>
      </section>
      <DeviceConfigModal
        deviceKey={deviceConfigKey}
        config={deviceConfig}
        onChange={setDeviceConfig}
        samplePositions={samplePositionsMm}
        onSamplePositionsChange={setSamplePositionsMm}
        onClose={() => setDeviceConfigKey(null)}
      />
      <HardwareModal
        open={netioOpen}
        channels={NETIO_POWER_CHANNELS}
        devices={netioDevices}
        tangoServers={HARDWARE_TANGO_SERVERS}
        tangoStates={tangoStates}
        loading={netioLoading}
        tangoLoading={tangoLoading}
        error={netioError}
        tangoError={tangoError}
        onClose={closeHardwareModal}
        onRefresh={() => {
          loadNetioOutputs();
          loadTangoStates();
        }}
        onToggle={toggleNetioChannel}
        onBulkPower={setNecessaryHardwarePower}
        onStartTango={(server) => controlTangoServer(server, 'start')}
        onRestartTango={(server) => controlTangoServer(server, 'restart')}
      />
      <DataBrowserWindow
        open={dataBrowserOpen}
        sampleName={sampleName}
        root={dataRoot}
        path={dataPath}
        parent={dataParent}
        entries={dataEntries}
        loading={dataLoading}
        error={dataError}
        selectedPath={dataSelectedPath}
        onClose={() => setDataBrowserOpen(false)}
        onRefresh={() => loadDataPath(dataPath || dataRoot)}
        onOpenPath={(pathValue) => loadDataPath(pathValue || dataRoot)}
        onSelectPath={setDataSelectedPath}
        onLoadFile={loadDataFile}
        onCreateFolder={createSampleFolder}
      />
    </main>
  );
}

export default PumpProbeV0;
