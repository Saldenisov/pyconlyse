import { useVd2AcquisitionState } from "./PumpProbeVD2.useVd2AcquisitionState";
import { useVd2AcquisitionActions } from "./PumpProbeVD2.useVd2AcquisitionActions";
import { renderVd2Acquisition } from "./PumpProbeVD2.renderVd2Acquisition";

import './css/PumpProbeVD2.css';


function PumpProbeVD2() {
  const {
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
  } = useVd2AcquisitionState();

  const {
    writeParameter, runCommand, refreshAll, updateProtocolSetting, startProtocolPhase,
    beginGuidedRun, chooseGuidedRun, cancelPreparedPhase, prepareProtocolPhase,
    startProtocolPhaseImmediately, preparationRemaining, updateLutRange, autoscaleLut,
    previewPoint, beginRoi, updateRoi, completeRoi, removeRoi, values,
    alignmentControlsBlocked, acquisitionIdle, acquisitionReadError,
    acquisitionReadDeferred, awaitingCameraState, readIssues, statusClass,
    showPreviousError, showNextError, dismissError, clearErrors, copyError, updatePairedCapture,
  } = useVd2AcquisitionActions({
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
  });

  return renderVd2Acquisition({
    state, preview, previewAvailable, errors, activeErrorId, previewError,
    setAlignmentAverage, setLiveAverageReadError, setPreviewEnabled, busy, activeTab,
    setActiveTab, calibration, calibrationUpdating, calibrationError, previewStream,
    alignmentRegion, setAlignmentRegion, alignmentMemoryError, imageRight, setImageRight,
    imageWidth, setImageWidth, dragPanel, setDragPanel, lutPalette, setLutPalette,
    lutRange, roiTool, setRoiTool, rois, setRois, roiMemoryError, linkRois, setLinkRois,
    selectedRoiId, setSelectedRoiId, drawingRoi, setDrawingRoi, protocol,
    protocolHardwareActive, protocolSaving, projectError, protocolSettings, project,
    serverWorkspace, preparedPhase, guidedRun, guidedChoice, setGuidedChoice,
    guidedMessage, protocolStarting, repeatConflict, setRepeatConflict,
    alignmentMeasurements, previewPaused, previewCanvas, previewOverlay, loadPreview,
    previewTiming, previewFresh, previewStride, previewHz, alignment, alignmentContext,
    resizeImage, writeParameter, runCommand, refreshAll, updateProtocolSetting,
    startProtocolPhase, beginGuidedRun, chooseGuidedRun, cancelPreparedPhase,
    prepareProtocolPhase, startProtocolPhaseImmediately, preparationRemaining,
    updateLutRange, autoscaleLut, previewPoint, beginRoi, updateRoi, completeRoi,
    removeRoi, values, alignmentControlsBlocked, acquisitionIdle, acquisitionReadError,
    acquisitionReadDeferred, awaitingCameraState, readIssues, statusClass,
    showPreviousError, showNextError, dismissError, clearErrors, copyError, updatePairedCapture,
  });
}

export default PumpProbeVD2;

export { Vd2PhaseProtocol } from "./PumpProbeVD2.API_BASE";

export { RoiProfiles } from "./PumpProbeVD2.API_BASE";

export { updateRoisFromBounds } from "./PumpProbeVD2.API_BASE";

export { EditableField } from "./PumpProbeVD2.API_BASE";

export { TIME_RANGES } from "./PumpProbeVD2.API_BASE";

export { refreshVd2Passive } from "./PumpProbeVD2.API_BASE";

export { fetchVd2 } from "./PumpProbeVD2.API_BASE";
