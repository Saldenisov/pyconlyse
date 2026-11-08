import { useV0HardwareAndFiles } from "./PumpProbeV0.useV0HardwareAndFiles";
import { useV0Configuration } from "./PumpProbeV0.useV0Configuration";
import { useV0PlotState } from "./PumpProbeV0.useV0PlotState";
import { renderV0Workspace } from "./PumpProbeV0.renderV0Workspace";

import './css/PumpProbeV0.css';


// Coordinates V0 state, API calls, and data selection. Panels live in pump-probe-v0/components.
function PumpProbeV0() {
  const {
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
  } = useV0HardwareAndFiles();
  const {
    deriveDatasets, handleSettingChange, handleDelayPointsLoad, handleHardwareModeChange,
    handleConfigLoad, handleConfigSave, moveSampleStage, setSampleMarker, stopSampleStage,
    treatmentRequestEpoch, displayedOdDataset, fileOdLoaded, liveWavelengths, wavelengths,
    visibleRawDataset, delays, heatmap, liveOd, currentIndex, activeCurrentIndex, running,
    handleRun,
  } = useV0Configuration({
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
  });
  const {
    realTime, faradayClosed, electronState, positionMm, setPositionMm, activeControlMode,
    daqCounter, counterActive, counterRateHz, hardwareChecks, failedHardwareChecks,
    sampleDisplayPositionMm, sampleDisplayTargetMm, netioAnyOn, delayStats,
    activeWavelengthRange, activeDelayRange, safeWavelengthIndexes, safeDelayIndexes,
    selectedWavelengthLabel, selectedDelayLabel, currentOdSource, addKineticTrace,
    removeKineticTrace, addOdSpectrumTrace, removeOdSpectrumTrace, spectraData,
    spectraTitle, spectraLayout, odSpectrumData, odSpectrumLayout, kineticsData,
    kineticsLayout, heatmapData, heatmapLayout, heatmapConfig, delayPreviewData,
    delayPreviewLayout, delayPreviewConfig, chartConfig, plotInteractionProps,
  } = useV0PlotState({
    settings, hardwareConfig, samplePositionMm, sampleTargetMm, backendState,
    setLocalIndex, localRunning, localPositionMm, setLocalPositionMm, localElectronState,
    setLocalElectronState, localFaradayClosed, selectedWavelengthRange, selectedDelayRange,
    plotRevision, netioDevices, hardwareInitStatus, treatmentPreview, spectraViewMode,
    savedKinetics, setSavedKinetics, kineticCounter, setKineticCounter, savedOdSpectra,
    setSavedOdSpectra, odSpectrumCounter, setOdSpectrumCounter, displayedOdDataset,
    fileOdLoaded, liveWavelengths, wavelengths, visibleRawDataset, delays, heatmap, liveOd,
    currentIndex, activeCurrentIndex,
  });

  return renderV0Workspace({
    settings, hardwareConfig, deviceConfig, setDeviceConfig, deviceConfigKey,
    setDeviceConfigKey, samplePositionsMm, setSamplePositionsMm, backendState,
    setBackendState, backendError, configurationError, actionError, runBusy,
    tangoRunPreview, delayImportError, setLocalIndex, stepPs, setStepPs, zeroMm, setZeroMm,
    setLocalElectronState, setLocalFaradayClosed, setSelectedWavelengthRange,
    setSelectedDelayRange, setPlotRevision, netioOpen, setNetioOpen, netioDevices,
    netioLoading, netioError, tangoStates, tangoLoading, tangoError, hardwareInitStatus,
    hardwareInitLoading, sampleName, setSampleName, dataBrowserOpen, setDataBrowserOpen,
    dataRoot, dataPath, dataParent, dataEntries, dataSelectedPath, setDataSelectedPath,
    dataTopPath, setDataTopPath, dataFolderName, setDataFolderName, dataLoading, dataError,
    loadedOdDataset, setLoadedOdDataset, odDisplayOwner, setOdDisplayOwner,
    odDisplayEpochRef, sourceOdDataset, treatmentPreview, setTreatmentPreview,
    treatmentOpen, setTreatmentOpen, derivedSources, deriveBusy, deriveError,
    spectraViewMode, setSpectraViewMode, savedKinetics, setSavedKinetics, savedOdSpectra,
    setSavedOdSpectra, closeHardwareModal, postAndRefresh, runHardwareInitialization,
    loadNetioOutputs, toggleNetioChannel, setNecessaryHardwarePower, loadTangoStates,
    controlTangoServer, loadDataPath, createSampleFolder, loadDataFile,
    updateDerivedSources, deriveDatasets, handleSettingChange, handleDelayPointsLoad,
    handleHardwareModeChange, handleConfigLoad, handleConfigSave, moveSampleStage,
    setSampleMarker, stopSampleStage, treatmentRequestEpoch, fileOdLoaded,
    visibleRawDataset, delays, activeCurrentIndex, running, handleRun, realTime,
    faradayClosed, electronState, positionMm, setPositionMm, activeControlMode, daqCounter,
    counterActive, counterRateHz, hardwareChecks, failedHardwareChecks,
    sampleDisplayPositionMm, sampleDisplayTargetMm, netioAnyOn, delayStats,
    activeWavelengthRange, activeDelayRange, safeWavelengthIndexes, safeDelayIndexes,
    selectedWavelengthLabel, selectedDelayLabel, currentOdSource, addKineticTrace,
    removeKineticTrace, addOdSpectrumTrace, removeOdSpectrumTrace, spectraData,
    spectraTitle, spectraLayout, odSpectrumData, odSpectrumLayout, kineticsData,
    kineticsLayout, heatmapData, heatmapLayout, heatmapConfig, delayPreviewData,
    delayPreviewLayout, delayPreviewConfig, chartConfig, plotInteractionProps,
  });
}

export default PumpProbeV0;
