import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DEFAULT_SAMPLE_POSITIONS_MM, API_BASE, pumpProbeRequest, compactHardwareError, fetchJsonWithRetry, buildSyntheticRun, DEFAULT_SETTINGS, DEFAULT_HARDWARE_CONFIG, DEFAULT_DEVICE_CONFIG, NETIO_POWER_CHANNELS, HARDWARE_TANGO_SERVERS, devicePath, normalizeNetioOutputs, activeDelayPoints } from './pump-probe-v0/shared';

export function useV0HardwareAndFiles() {
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
  const [configurationError, setConfigurationError] = useState('');
  const [actionError, setActionError] = useState('');
  const [runBusy, setRunBusy] = useState(false);
  const runBusyRef = useRef(false);
  const [tangoRunPreview, setTangoRunPreview] = useState(null);
  const [delayImportError, setDelayImportError] = useState('');
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
  const [dataTopPath, setDataTopPath] = useState('');
  const [dataFolderName, setDataFolderName] = useState('');
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState('');
  const [loadedOdDataset, setLoadedOdDataset] = useState(null);
  const [odDisplayOwner, setOdDisplayOwner] = useState('live');
  const odDisplayEpochRef = useRef(0);
  const [sourceOdDataset, setSourceOdDataset] = useState(null);
  const [treatmentPreview, setTreatmentPreview] = useState(null);
  const [treatmentOpen, setTreatmentOpen] = useState(false);
  const [rawDataset, setRawDataset] = useState(null);
  const [derivedSources, setDerivedSources] = useState([]);
  const [deriveBusy, setDeriveBusy] = useState(false);
  const [deriveError, setDeriveError] = useState('');
  const deriveControllerRef = useRef(null);
  const [spectraViewMode, setSpectraViewMode] = useState('current');
  const [savedKinetics, setSavedKinetics] = useState([]);
  const [kineticCounter, setKineticCounter] = useState(1);
  const [savedOdSpectra, setSavedOdSpectra] = useState([]);
  const [odSpectrumCounter, setOdSpectrumCounter] = useState(1);
  const refreshRequestRef = useRef({ inFlight: false, controller: null });
  const configQueueRef = useRef(Promise.resolve());
  const configRequestRef = useRef(null);
  const desiredConfigRef = useRef(null);
  const stateMutationRevisionRef = useRef(0);
  useEffect(() => () => {
    odDisplayEpochRef.current += 1;
    deriveControllerRef.current?.abort();
  }, []);

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
    const mutationRevision = stateMutationRevisionRef.current;
    const timeoutId = window.setTimeout(() => controller.abort(), 2000);
    refreshRequestRef.current = { inFlight: true, controller };
    try {
      const state = await pumpProbeRequest('/state', { signal: controller.signal });
      if (mutationRevision === stateMutationRevisionRef.current) {
        setBackendState(state);
        setBackendError('');
      }
    } catch (error) {
      if (error.name !== 'AbortError' && mutationRevision === stateMutationRevisionRef.current) {
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
    setActionError('');
    try {
      const state = await pumpProbeRequest(path, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      stateMutationRevisionRef.current += 1;
      setBackendState(state);
      setBackendError('');
      return state;
    } catch (error) {
      setActionError(error.message);
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
      if (!dataTopPath && payload.root) {
        setDataTopPath(payload.root);
      }
      if (!dataSelectedPath && payload.path) {
        setDataSelectedPath(payload.path);
      }
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, [dataSelectedPath, dataTopPath]);

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

  const createRunFolder = useCallback(async () => {
    const folderName = dataFolderName.trim();
    if (!folderName) {
      throw new Error('Enter a Folder name before starting a run');
    }
    const parent = dataTopPath || dataPath || dataRoot;
    if (!parent) {
      throw new Error('Choose a Top folder in Files before starting a run');
    }
    const response = await fetch(`${API_BASE}/data/folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ parent, name: folderName }),
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || `Failed to create Folder (${response.status})`);
    }
    setDataSelectedPath(payload.path);
    return payload.path;
  }, [dataFolderName, dataPath, dataRoot, dataTopPath]);

  const loadDataFile = useCallback(async (filePath) => {
    if (!filePath) {
      return;
    }
    deriveControllerRef.current?.abort();
    deriveControllerRef.current = null;
    setDeriveBusy(false);
    const loadEpoch = ++odDisplayEpochRef.current;
    setDataLoading(true);
    setDataError('');
    try {
      const payload = await pumpProbeRequest('/data/load', {
        method: 'POST',
        body: JSON.stringify({ path: filePath }),
      });
      if (loadEpoch !== odDisplayEpochRef.current) return;
      setDataSelectedPath(payload.path || filePath);
      setTreatmentPreview(null);
      setTreatmentOpen(false);
      if (payload.heatmap) {
        setSourceOdDataset(payload);
        if (!payload.source_spec) {
          setDerivedSources((current) => current.some((item) => item.path === payload.path && item.source_sha256 === payload.source_sha256)
            ? current : [...current, { path: payload.path, source_sha256: payload.source_sha256, file_name: payload.file_name }]);
        }
        setLoadedOdDataset(payload);
        setOdDisplayOwner('file');
        setSelectedWavelengthRange(null);
        setSelectedDelayRange(null);
        setPlotRevision((value) => value + 1);
      } else {
        setSourceOdDataset(null);
        setLoadedOdDataset(null);
        setOdDisplayOwner('live');
      }
      setRawDataset(payload.channels?.length ? payload : null);
      setSpectraViewMode(payload.channels?.length ? 'raw' : 'current');
    } catch (error) {
      if (loadEpoch === odDisplayEpochRef.current) setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, []);

  const updateDerivedSources = (update) => {
    if (deriveControllerRef.current) {
      odDisplayEpochRef.current += 1;
      deriveControllerRef.current.abort();
      deriveControllerRef.current = null;
      setDeriveBusy(false);
    }
    setDerivedSources(update);
    setDeriveError('');
  };

  return {
    settings, setSettings, hardwareConfig, setHardwareConfig, deviceConfig,
    setDeviceConfig, deviceConfigKey, setDeviceConfigKey, samplePositionMm,
    setSamplePositionMm, sampleTargetMm, setSampleTargetMm, samplePositionsMm,
    setSamplePositionsMm, fallbackRun, backendState, setBackendState, backendError,
    setBackendError, configurationError, setConfigurationError, actionError,
    setActionError, runBusy, setRunBusy, runBusyRef, tangoRunPreview, setTangoRunPreview,
    delayImportError, setDelayImportError, localIndex, setLocalIndex, localRunning,
    localPositionMm, setLocalPositionMm, stepPs, setStepPs, zeroMm, setZeroMm,
    localElectronState, setLocalElectronState, localFaradayClosed, setLocalFaradayClosed,
    selectedWavelengthRange, setSelectedWavelengthRange, selectedDelayRange,
    setSelectedDelayRange, plotRevision, setPlotRevision, netioOpen, setNetioOpen,
    netioDevices, netioLoading, netioError, tangoStates, tangoLoading, tangoError,
    hardwareInitStatus, hardwareInitLoading, sampleName, setSampleName, dataBrowserOpen,
    setDataBrowserOpen, dataRoot, dataPath, dataParent, dataEntries, dataSelectedPath,
    setDataSelectedPath, dataTopPath, setDataTopPath, dataFolderName, setDataFolderName,
    dataLoading, dataError, loadedOdDataset, setLoadedOdDataset, odDisplayOwner,
    setOdDisplayOwner, odDisplayEpochRef, sourceOdDataset, setSourceOdDataset,
    treatmentPreview, setTreatmentPreview, treatmentOpen, setTreatmentOpen, rawDataset,
    setRawDataset, derivedSources, deriveBusy, setDeriveBusy, deriveError, setDeriveError,
    deriveControllerRef, spectraViewMode, setSpectraViewMode, savedKinetics,
    setSavedKinetics, kineticCounter, setKineticCounter, savedOdSpectra, setSavedOdSpectra,
    odSpectrumCounter, setOdSpectrumCounter, refreshRequestRef, configQueueRef,
    configRequestRef, desiredConfigRef, stateMutationRevisionRef, closeHardwareModal,
    refreshState, postAndRefresh, runHardwareInitialization, loadNetioOutputs,
    toggleNetioChannel, setNecessaryHardwarePower, loadTangoStates, controlTangoServer,
    loadDataPath, createSampleFolder, createRunFolder, loadDataFile, updateDerivedSources,
  };
}
