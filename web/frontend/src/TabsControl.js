import TreatmentError from './components/TreatmentError';
import { useTreatmentWorkspace } from "./TabsControl.useTreatmentWorkspace";
import { useTreatmentQueueAndRefresh } from "./TabsControl.useTreatmentQueueAndRefresh";
import { useTreatmentFileActions } from "./TabsControl.useTreatmentFileActions";
import { useTreatmentAnalysisAndTree } from "./TabsControl.useTreatmentAnalysisAndTree";
import { renderTreatmentSources } from "./TabsControl.renderTreatmentSources";
import { renderTreatmentWorkspace } from "./TabsControl.renderTreatmentWorkspace";

import './css/DataWindowVD2.css';


const TabsControl = ({ preview = null }) => {
  const {
    treeFirst, treatmentContext, treatmentSessionId, treatmentProfile,
    manifestProjectFolder, treatmentLayoutMode, isStudioLayout, requestSelectionRefresh,
    activeTab, setActiveTab, treatment, setTreatment, filesLayoutRef, queueWasRunningRef,
    folderQueueActiveRef, stitchAutoPreviewAttemptKeyRef,
    skipNextStitchCoefficientRefreshRef, filesLayout, folderTreeCache, setFolderTreeCache,
    fileSummaryCache, setFileSummaryCache, expandedFolders, setExpandedFolders,
    fileContextMenu, setFileContextMenu, folderContextMenu, setFolderContextMenu,
    detailFile, setDetailFile, selectedFolders, setSelectedFolders, folderSelectionAnchor,
    isFolderTreeOpen, setIsFolderTreeOpen, isSelectingFolderRoot, setIsSelectingFolderRoot,
    treeRoot, setTreeRoot, draftSaveFolder, setDraftSaveFolder, draftSaveFileName,
    setDraftSaveFileName, draftAllowedRoot, setDraftAllowedRoot, draftKineticsRanges,
    setDraftKineticsRanges, draftSpectraRanges, setDraftSpectraRanges,
    cleaningAngleThreshold, setCleaningAngleThreshold, cleaningSurfaceThreshold,
    setCleaningSurfaceThreshold, error, setError, operationMessage, setOperationMessage,
    selectionMessage, setSelectionMessage, cleaningSummary, setCleaningSummary,
    cleaningView, setCleaningView, pendingCleaningPreview, setPendingCleaningPreview,
    savedResultPath, setSavedResultPath, treatmentQueue, setTreatmentQueue, queueLabel,
    setQueueLabel, queueApplyCleaning, setQueueApplyCleaning, isQueueLoading,
    setIsQueueLoading, isCleaningViewLoading, setIsCleaningViewLoading, stitchFileA,
    setStitchFileA, stitchFileB, setStitchFileB, stitchOutputName, setStitchOutputName,
    stitchLeftScale, setStitchLeftScale, stitchLeftOffset, setStitchLeftOffset,
    stitchRightScale, setStitchRightScale, stitchRightOffset, setStitchRightOffset,
    stitchRightDelayShift, setStitchRightDelayShift, stitchLeftWavelengthStart,
    setStitchLeftWavelengthStart, stitchLeftWavelengthEnd, setStitchLeftWavelengthEnd,
    stitchRightWavelengthStart, setStitchRightWavelengthStart, stitchRightWavelengthEnd,
    setStitchRightWavelengthEnd, stitchRegionStart, setStitchRegionStart, stitchRegionEnd,
    setStitchRegionEnd, stitchRegions, setStitchRegions, stitchPreview, setStitchPreview,
    stitchSummary, setStitchSummary, isBusy, setIsBusy, profilePreset, isV0Profile,
    session, sourceFolder, cleaningFolders, persistedCleaningPreview, assignableDataTypes,
    canAverageNoise, assignedCleaningTypes, cleaningActiveDataType, cleaningSourcePath,
    cleaningOutputName, isOperationRunning, busyElapsedSeconds, filesGridTemplate,
    queueJobs, queueConvertibleHisDataTypes, queueOutputConfigured,
    queueSupportsCurrentRecipeCleaning, canApplyCleaningPreview,
    requireAppliedCleaningPreview, handleFilesColumnResizeStart, handleTreePointerDown,
    handleTreePointerMove, finishTreeResize, handleTreeResizeKey, refreshSession,
    refreshTreatmentQueue,
  } = useTreatmentWorkspace({
    preview,
  });

  const {
    handleQueueEnqueue, handleQueueStandardFolder, handleLoadFolderInputs,
    handleQueueRemove, loadFileSummary, refreshCleaningView, cacheFolderListing,
    refreshFolderListing, loadFolderTreeNode, applyPayload, handleConfigChange,
    handleReset, handleQueueRun,
  } = useTreatmentQueueAndRefresh({
    treeFirst, treatmentContext, treatmentSessionId, treatmentProfile,
    manifestProjectFolder, isStudioLayout, requestSelectionRefresh, activeTab,
    setActiveTab, treatment, setTreatment, queueWasRunningRef, folderQueueActiveRef,
    folderTreeCache, setFolderTreeCache, fileSummaryCache, setFileSummaryCache,
    expandedFolders, setExpandedFolders, setFileContextMenu, setFolderContextMenu,
    setIsFolderTreeOpen, isSelectingFolderRoot, treeRoot, setTreeRoot, setDraftSaveFolder,
    setDraftSaveFileName, setDraftAllowedRoot, cleaningAngleThreshold,
    cleaningSurfaceThreshold, setError, setOperationMessage, setCleaningView,
    setPendingCleaningPreview, treatmentQueue, setTreatmentQueue, queueLabel,
    setQueueLabel, queueApplyCleaning, setIsQueueLoading, setIsCleaningViewLoading,
    setIsBusy, profilePreset, session, sourceFolder, persistedCleaningPreview,
    assignedCleaningTypes, queueConvertibleHisDataTypes, queueOutputConfigured,
    queueSupportsCurrentRecipeCleaning, requireAppliedCleaningPreview,
    refreshTreatmentQueue,
  });

  const {
    handleAllowedRootChange, handleAllowedRootKeyDown, handleAssignFile, handlePreviewDat,
    handleManifestFolder, handleSetStitchFile, handleCompressFile, handleFolderTreeToggle,
    handleFolderTreeOpen, handleFileContextMenu, handleFolderContextMenu,
    handleTreeFolderClick, toggleBatchFolder, handleAverageNoise, handleCalcAbs,
    handleSave, handleCopySavedResultPath, handleCommitSaveFolder,
    handleCommitSaveFileName, formatExportRanges,
  } = useTreatmentFileActions({
    treeFirst, treatmentContext, treatmentSessionId, manifestProjectFolder,
    requestSelectionRefresh, setActiveTab, treatment, setTreatment, expandedFolders,
    setExpandedFolders, setFileContextMenu, setFolderContextMenu, selectedFolders,
    setSelectedFolders, folderSelectionAnchor, setIsFolderTreeOpen, isSelectingFolderRoot,
    setIsSelectingFolderRoot, setTreeRoot, draftSaveFolder, draftSaveFileName,
    draftAllowedRoot, setDraftAllowedRoot, setError, setOperationMessage,
    setSelectionMessage, setCleaningSummary, savedResultPath, setSavedResultPath,
    setStitchFileA, setStitchFileB, setStitchPreview, setStitchSummary, isBusy, setIsBusy,
    profilePreset, session, requireAppliedCleaningPreview, cacheFolderListing,
    refreshFolderListing, loadFolderTreeNode, applyPayload, handleConfigChange,
  });

  const {
    handleSelectionExport, handleV0QuickExport, handleCleaningTargetChange,
    handleCleaningThresholdChange, handleCleaningAction, handleStitchRegionsChange,
    refreshStitchPreview, handleRevertStitchFit, handleAddStitchRegion,
    handleRemoveStitchRegion, handleStitchOd, stitchOutputFolder, stitchOutputPath,
    stitchZoneMap, renderFolderTreeFiles, renderFolderTreeRows, explorerRoot,
    explorerRootListing, refreshVisibleFolders, stitchDatFiles,
  } = useTreatmentAnalysisAndTree({
    treeFirst, treatmentContext, treatmentSessionId, requestSelectionRefresh, activeTab,
    setTreatment, stitchAutoPreviewAttemptKeyRef, skipNextStitchCoefficientRefreshRef,
    folderTreeCache, fileSummaryCache, setFileSummaryCache, expandedFolders,
    selectedFolders, draftKineticsRanges, setDraftKineticsRanges, draftSpectraRanges,
    setDraftSpectraRanges, cleaningAngleThreshold, setCleaningAngleThreshold,
    cleaningSurfaceThreshold, setCleaningSurfaceThreshold, setError, setOperationMessage,
    setSelectionMessage, setCleaningSummary, setCleaningView, pendingCleaningPreview,
    setPendingCleaningPreview, treatmentQueue, isQueueLoading, stitchFileA, stitchFileB,
    stitchOutputName, setStitchOutputName, stitchLeftScale, stitchLeftOffset,
    stitchRightScale, setStitchRightScale, stitchRightOffset, setStitchRightOffset,
    stitchRightDelayShift, stitchLeftWavelengthStart, setStitchLeftWavelengthStart,
    stitchLeftWavelengthEnd, setStitchLeftWavelengthEnd, stitchRightWavelengthStart,
    setStitchRightWavelengthStart, stitchRightWavelengthEnd, setStitchRightWavelengthEnd,
    stitchRegionStart, setStitchRegionStart, stitchRegionEnd, setStitchRegionEnd,
    stitchRegions, setStitchRegions, stitchPreview, setStitchPreview, setStitchSummary,
    isBusy, setIsBusy, isV0Profile, session, sourceFolder, cleaningActiveDataType,
    cleaningSourcePath, canApplyCleaningPreview, refreshCleaningView, cacheFolderListing,
    refreshFolderListing, handlePreviewDat, handleFolderTreeToggle, handleFileContextMenu,
    handleFolderContextMenu, handleTreeFolderClick, toggleBatchFolder, formatExportRanges,
  });

  if (!session) {
    return (
      <div className="tabs-control">
        {error ? <TreatmentError message={error} /> : <p>Loading treatment session...</p>}
        <button onClick={refreshSession}>Retry</button>
      </div>
    );
  }

  const {
    sourceBrowser, detailSummary, QueuePanel, activeQueueJob, lastFolderJob,
  } = renderTreatmentSources({
    treeFirst, treatmentContext, isStudioLayout, treatment, fileSummaryCache,
    expandedFolders, fileContextMenu, setFileContextMenu, folderContextMenu, detailFile,
    setDetailFile, selectedFolders, setSelectedFolders, isFolderTreeOpen,
    isSelectingFolderRoot, draftAllowedRoot, setDraftAllowedRoot, setError, treatmentQueue,
    isQueueLoading, isBusy, isV0Profile, session, assignableDataTypes, queueJobs,
    handleQueueStandardFolder, handleLoadFolderInputs, loadFileSummary,
    handleAllowedRootChange, handleAllowedRootKeyDown, handleAssignFile, handlePreviewDat,
    handleManifestFolder, handleSetStitchFile, handleCompressFile, handleFolderTreeToggle,
    handleFolderTreeOpen, handleFolderContextMenu, handleTreeFolderClick,
    renderFolderTreeFiles, renderFolderTreeRows, explorerRoot, explorerRootListing,
    refreshVisibleFolders,
  });

  return renderTreatmentWorkspace({
    preview, treeFirst, treatmentProfile, treatmentLayoutMode, isStudioLayout, activeTab,
    setActiveTab, treatment, filesLayoutRef, filesLayout, detailFile, setDetailFile,
    draftSaveFolder, setDraftSaveFolder, draftSaveFileName, setDraftSaveFileName,
    draftKineticsRanges, setDraftKineticsRanges, draftSpectraRanges, setDraftSpectraRanges,
    cleaningAngleThreshold, cleaningSurfaceThreshold, error, operationMessage,
    selectionMessage, cleaningSummary, cleaningView, pendingCleaningPreview,
    savedResultPath, treatmentQueue, queueLabel, setQueueLabel, queueApplyCleaning,
    setQueueApplyCleaning, isQueueLoading, isCleaningViewLoading, stitchFileA,
    setStitchFileA, stitchFileB, setStitchFileB, stitchOutputName, setStitchOutputName,
    stitchLeftScale, setStitchLeftScale, stitchLeftOffset, setStitchLeftOffset,
    stitchRightScale, setStitchRightScale, stitchRightOffset, setStitchRightOffset,
    stitchRightDelayShift, setStitchRightDelayShift, stitchLeftWavelengthStart,
    setStitchLeftWavelengthStart, stitchLeftWavelengthEnd, setStitchLeftWavelengthEnd,
    stitchRightWavelengthStart, setStitchRightWavelengthStart, stitchRightWavelengthEnd,
    setStitchRightWavelengthEnd, stitchRegionStart, setStitchRegionStart, stitchRegionEnd,
    setStitchRegionEnd, stitchRegions, stitchPreview, stitchSummary, isBusy, isV0Profile,
    session, cleaningFolders, assignableDataTypes, canAverageNoise, assignedCleaningTypes,
    cleaningActiveDataType, cleaningSourcePath, cleaningOutputName, isOperationRunning,
    busyElapsedSeconds, filesGridTemplate, queueJobs, queueOutputConfigured,
    queueSupportsCurrentRecipeCleaning, canApplyCleaningPreview,
    handleFilesColumnResizeStart, handleTreePointerDown, handleTreePointerMove,
    finishTreeResize, handleTreeResizeKey, handleQueueEnqueue, handleQueueStandardFolder,
    handleQueueRemove, handleConfigChange, handleReset, handleQueueRun, handleAverageNoise,
    handleCalcAbs, handleSave, handleCopySavedResultPath, handleCommitSaveFolder,
    handleCommitSaveFileName, handleSelectionExport, handleV0QuickExport,
    handleCleaningTargetChange, handleCleaningThresholdChange, handleCleaningAction,
    handleStitchRegionsChange, refreshStitchPreview, handleRevertStitchFit,
    handleAddStitchRegion, handleRemoveStitchRegion, handleStitchOd, stitchOutputFolder,
    stitchOutputPath, stitchZoneMap, stitchDatFiles, sourceBrowser, detailSummary,
    QueuePanel, activeQueueJob, lastFolderJob,
  });
};

export default TabsControl;

export { summarizeFolderSetProgress } from "./TabsControl.PROFILE_PRESETS";
