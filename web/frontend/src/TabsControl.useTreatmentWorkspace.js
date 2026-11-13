import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { TreatmentContext } from './DataWindowVD2';
import { fetchTreatmentQueue, fetchTreatmentSession } from './api/treatmentClient';
import { PROFILE_PRESETS } from "./TabsControl.PROFILE_PRESETS";
import { CLEANING_DRAFT_STORAGE_PREFIX } from "./TabsControl.PROFILE_PRESETS";
import { FOLDER_TREE_OPEN_STORAGE_PREFIX } from "./TabsControl.PROFILE_PRESETS";
import { MIN_TREE_WIDTH } from "./TabsControl.PROFILE_PRESETS";
import { MAX_TREE_WIDTH } from "./TabsControl.PROFILE_PRESETS";
import { clampNumber } from "./TabsControl.PROFILE_PRESETS";
import { readFilesLayout } from "./TabsControl.PROFILE_PRESETS";
import { saveFilesLayout } from "./TabsControl.PROFILE_PRESETS";
import { saveSessionBackup } from "./TabsControl.PROFILE_PRESETS";
import { readCleaningDraft } from "./TabsControl.PROFILE_PRESETS";
import { requiredDataTypesForExpType } from "./TabsControl.PROFILE_PRESETS";
import { h5NameForPath } from "./TabsControl.PROFILE_PRESETS";
import { backendCleaningPreview } from "./TabsControl.roleSelectionStatus";

export function useTreatmentWorkspace({
  preview,
}) {
  const treeFirst = Boolean(preview);
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const treatmentProfile = String(treatmentContext?.treatmentProfile || 'VD2').toUpperCase();
  const manifestProjectFolder=treatmentContext?.manifestProjectFolder||'';
  const treatmentLayoutMode = treatmentContext?.treatmentLayoutMode || 'classic';
  const isStudioLayout = treatmentLayoutMode === 'studio';
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const saved = window.localStorage.getItem(`pyconlyse.treatment.activeTab.${treatmentSessionId}`);
      return !saved || (treeFirst && saved === 'info') ? 'files' : saved;
    } catch (_error) {
      return 'files';
    }
  });
  const [treatment, setTreatment] = useState(null);
  const referenceSession = treatmentContext?.referenceSession;
  useEffect(() => {
    if (referenceSession?.session_id === treatmentSessionId) setTreatment(referenceSession);
  }, [referenceSession, treatmentSessionId]);
  const filesLayoutRef = useRef(null);
  const treeResizeRef = useRef(null);
  const queueWasRunningRef = useRef(false);
  const folderQueueActiveRef = useRef(false);
  const stitchAutoPreviewAttemptKeyRef = useRef('');
  const skipNextStitchCoefficientRefreshRef = useRef(false);
  const [filesLayout, setFilesLayout] = useState(readFilesLayout);
  const [folderTreeCache, setFolderTreeCache] = useState({});
  const [fileSummaryCache, setFileSummaryCache] = useState({});
  const [expandedFolders, setExpandedFolders] = useState(() => new Set());
  const [fileContextMenu, setFileContextMenu] = useState(null);
  const [folderContextMenu, setFolderContextMenu] = useState(null);
  const [detailFile, setDetailFile] = useState(null);
  const [selectedFolders, setSelectedFolders] = useState([]);
  const folderSelectionAnchor = useRef(null);
  const [isFolderTreeOpen, setIsFolderTreeOpen] = useState(() => {
    try {
      return window.localStorage.getItem(`${FOLDER_TREE_OPEN_STORAGE_PREFIX}${treatmentSessionId}`)
        === 'true' || treeFirst;
    } catch (_error) {
      return treeFirst;
    }
  });
  const [isSelectingFolderRoot, setIsSelectingFolderRoot] = useState(false);
  const [treeRoot, setTreeRoot] = useState('');
  const [draftSaveFolder, setDraftSaveFolder] = useState('');
  const [draftSaveFileName, setDraftSaveFileName] = useState('');
  const [draftAllowedRoot, setDraftAllowedRoot] = useState('');
  const [draftKineticsRanges, setDraftKineticsRanges] = useState('');
  const [draftSpectraRanges, setDraftSpectraRanges] = useState('');
  const [cleaningAngleThreshold, setCleaningAngleThreshold] = useState(
    () => readCleaningDraft(treatmentSessionId, 'angle')
  );
  const [cleaningSurfaceThreshold, setCleaningSurfaceThreshold] = useState(
    () => readCleaningDraft(treatmentSessionId, 'surface')
  );
  const [error, setError] = useState('');
  const [operationMessage, setOperationMessage] = useState('');
  const [selectionMessage, setSelectionMessage] = useState('');
  const [cleaningSummary, setCleaningSummary] = useState(null);
  const [cleaningView, setCleaningView] = useState(null);
  const [pendingCleaningPreview, setPendingCleaningPreview] = useState(null);
  const [savedResultPath, setSavedResultPath] = useState('');
  const [treatmentQueue, setTreatmentQueue] = useState(null);
  const [queueLabel, setQueueLabel] = useState('');
  const [queueApplyCleaning, setQueueApplyCleaning] = useState(true);
  const [isQueueLoading, setIsQueueLoading] = useState(false);
  const [isCleaningViewLoading, setIsCleaningViewLoading] = useState(false);
  const [stitchFileA, setStitchFileA] = useState('');
  const [stitchFileB, setStitchFileB] = useState('');
  const [stitchOutputName, setStitchOutputName] = useState('stitched_od.dat');
  const [stitchLeftScale, setStitchLeftScale] = useState('1');
  const [stitchLeftOffset, setStitchLeftOffset] = useState('0');
  const [stitchRightScale, setStitchRightScale] = useState('1');
  const [stitchRightOffset, setStitchRightOffset] = useState('0');
  const [stitchRightDelayShift, setStitchRightDelayShift] = useState('0');
  const [stitchLeftWavelengthStart, setStitchLeftWavelengthStart] = useState('');
  const [stitchLeftWavelengthEnd, setStitchLeftWavelengthEnd] = useState('');
  const [stitchRightWavelengthStart, setStitchRightWavelengthStart] = useState('');
  const [stitchRightWavelengthEnd, setStitchRightWavelengthEnd] = useState('');
  const [stitchRegionStart, setStitchRegionStart] = useState('');
  const [stitchRegionEnd, setStitchRegionEnd] = useState('');
  const [stitchRegions, setStitchRegions] = useState([]);
  const [stitchPreview, setStitchPreview] = useState(null);
  const [stitchSummary, setStitchSummary] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [busyStartedAt, setBusyStartedAt] = useState(null);
  const [busyNow, setBusyNow] = useState(Date.now());
  const profilePreset = PROFILE_PRESETS[treatmentProfile] || PROFILE_PRESETS.VD2;
  const isV0Profile = treatmentProfile === 'V0';

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `pyconlyse.treatment.activeTab.${treatmentSessionId}`,
        activeTab
      );
    } catch (_error) {
      // Treatment remains usable when localStorage is unavailable.
    }
  }, [activeTab, treatmentSessionId]);

  const session = treatment ? treatment.session : null;
  const sourceFolder = treeRoot || session?.folder_path || treatment?.allowed_root || '';
  const cleaningFolders = selectedFolders.length > 0
    ? selectedFolders
    : sourceFolder && sourceFolder !== treatment?.allowed_root ? [sourceFolder] : [];

  useEffect(() => {
    saveSessionBackup(treatmentSessionId, session);
  }, [session, treatmentSessionId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `${FOLDER_TREE_OPEN_STORAGE_PREFIX}${treatmentSessionId}`,
        String(isFolderTreeOpen)
      );
    } catch (_error) {
      // Server-side folder selection remains available without browser storage.
    }
  }, [isFolderTreeOpen, treatmentSessionId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `${CLEANING_DRAFT_STORAGE_PREFIX}${treatmentSessionId}.angle`,
        cleaningAngleThreshold
      );
      window.localStorage.setItem(
        `${CLEANING_DRAFT_STORAGE_PREFIX}${treatmentSessionId}.surface`,
        cleaningSurfaceThreshold
      );
    } catch (_error) {
      // The server-side treatment session remains usable.
    }
  }, [cleaningAngleThreshold, cleaningSurfaceThreshold, treatmentSessionId]);
  const persistedCleaningPreview = useMemo(() => backendCleaningPreview(session), [session]);
  const requiredDataTypes =
    session?.required_data_types || requiredDataTypesForExpType(session?.exp_type);
  const assignableDataTypes =
    requiredDataTypes && requiredDataTypes.length > 0 ? requiredDataTypes : treatment?.data_types || [];
  const canAverageNoise = requiredDataTypes.includes('NOISE');
  const assignedCleaningTypes = assignableDataTypes.filter((dataType) => session?.paths?.[dataType]);
  const cleaningActiveDataType =
    assignedCleaningTypes.includes(session?.active_data_type)
      ? session.active_data_type
      : assignedCleaningTypes[0] || '';
  const cleaningSourcePath =
    cleaningActiveDataType
      ? (session?.path_sources?.[cleaningActiveDataType] || session?.paths?.[cleaningActiveDataType] || '')
      : '';
  const cleaningOutputName = h5NameForPath(cleaningSourcePath);
  const isOperationRunning = isBusy;
  const busyElapsedSeconds =
    isOperationRunning && busyStartedAt ? Math.max(0, Math.floor((busyNow - busyStartedAt) / 1000)) : 0;
  const filesGridTemplate = `${filesLayout.parameters}px 6px minmax(620px, 1fr) 6px ${filesLayout.selected}px`;
  const queueJobs = Array.isArray(treatmentQueue?.jobs) ? treatmentQueue.jobs : [];
  const queueHisDataTypes = assignedCleaningTypes.filter((dataType) =>
    String(session?.path_sources?.[dataType] || session?.paths?.[dataType] || '').toLowerCase().endsWith('.his')
  );
  const queueConvertibleHisDataTypes = queueHisDataTypes.filter((dataType) =>
    ['ABS', 'BASE', 'NOISE'].includes(dataType)
  );
  const queueOutputConfigured = Boolean(session?.save_folder && session?.save_file_name);
  const queueSupportsCurrentRecipeCleaning =
    assignedCleaningTypes.length > 0 &&
    assignedCleaningTypes.every((dataType) => ['ABS', 'BASE', 'NOISE'].includes(dataType));
  const canApplyCleaningPreview = Boolean(
    pendingCleaningPreview &&
    !pendingCleaningPreview.backend &&
    !pendingCleaningPreview.stale &&
    !pendingCleaningPreview.invalidated &&
    pendingCleaningPreview.dataType === cleaningActiveDataType &&
    pendingCleaningPreview.angleThreshold === cleaningAngleThreshold &&
    pendingCleaningPreview.surfaceThreshold === cleaningSurfaceThreshold
  );

  const requireAppliedCleaningPreview = useCallback(() => {
    if (!pendingCleaningPreview) {
      return false;
    }
    setActiveTab('cleaning');
    setError(
      `Cleaning preview for ${pendingCleaningPreview.dataType} is not applied. Apply mask to H5 or reset the preview before calculating OD.`
    );
    return true;
  }, [pendingCleaningPreview]);

  const handleFilesColumnResizeStart = useCallback((edge, event) => {
    event.preventDefault();
    const containerWidth =
      filesLayoutRef.current?.getBoundingClientRect().width || window.innerWidth || 1280;
    const startX = event.clientX;
    const startLayout = { ...filesLayout };
    const minTree = 620;
    const gutters = 12;
    const minParameters = 240;
    const maxParameters = Math.max(
      minParameters,
      containerWidth - startLayout.selected - minTree - gutters
    );
    const minSelected = 260;
    const maxSelected = Math.max(
      minSelected,
      containerWidth - startLayout.parameters - minTree - gutters
    );
    let nextLayout = startLayout;

    const onMove = (moveEvent) => {
      const delta = moveEvent.clientX - startX;
      nextLayout = {
        ...startLayout,
        parameters:
          edge === 'parameters'
            ? clampNumber(startLayout.parameters + delta, minParameters, maxParameters)
            : startLayout.parameters,
        selected:
          edge === 'selected'
            ? clampNumber(startLayout.selected - delta, minSelected, maxSelected)
            : startLayout.selected,
      };
      setFilesLayout(nextLayout);
    };

    const onUp = () => {
      saveFilesLayout(nextLayout);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [filesLayout]);

  const resizeTree = (separator, requestedWidth) => {
    const maxWidth = Math.min(MAX_TREE_WIDTH, Math.floor(separator.parentElement.clientWidth * 0.38));
    const tree = clampNumber(Math.round(requestedWidth), MIN_TREE_WIDTH, maxWidth);
    const layout = { ...filesLayout, tree };
    setFilesLayout(layout);
    return layout;
  };

  const handleTreePointerDown = (event) => {
    if (event.button !== 0 || !event.isPrimary) return;
    const separator = event.currentTarget;
    treeResizeRef.current = {
      x: event.clientX,
      width: separator.previousElementSibling.getBoundingClientRect().width,
    };
    separator.setPointerCapture(event.pointerId);
  };

  const handleTreePointerMove = (event) => {
    const drag = treeResizeRef.current;
    if (drag && event.currentTarget.hasPointerCapture(event.pointerId)) {
      drag.layout = resizeTree(event.currentTarget, drag.width + event.clientX - drag.x);
    }
  };

  const finishTreeResize = () => {
    const layout = treeResizeRef.current?.layout;
    treeResizeRef.current = null;
    if (layout) saveFilesLayout(layout);
  };

  const handleTreeResizeKey = (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const separator = event.currentTarget;
    const width = separator.previousElementSibling.getBoundingClientRect().width;
    saveFilesLayout(resizeTree(separator, width + (event.key === 'ArrowLeft' ? -16 : 16)));
  };

  useEffect(() => {
    if (!isOperationRunning) {
      return undefined;
    }
    if (!busyStartedAt) {
      setBusyStartedAt(Date.now());
    }
    const timerId = window.setInterval(() => setBusyNow(Date.now()), 1000);
    return () => window.clearInterval(timerId);
  }, [busyStartedAt, isOperationRunning]);

  useEffect(() => {
    if (!isOperationRunning) {
      setBusyStartedAt(null);
    }
  }, [isOperationRunning]);

  useEffect(() => {
    if (activeTab === 'selection' || (isV0Profile && activeTab !== 'files')) {
      setActiveTab('files');
    }
  }, [activeTab, isV0Profile]);

  const refreshSession = async () => {
    const payload = await fetchTreatmentSession(treatmentSessionId);
    setTreatment(payload);
    if (requestSelectionRefresh) {
      requestSelectionRefresh();
    }
    return payload;
  };

  const refreshTreatmentQueue = useCallback(async (isCurrent = () => true) => {
    const payload = await fetchTreatmentQueue(treatmentSessionId);
    if (isCurrent()) {
      const queue = payload?.queue || { running: false, jobs: [] };
      const finished = queueWasRunningRef.current && !queue.running;
      // Fetch before publishing running=false. Publishing it first cleans up
      // the poll effect and cancels its own pending session read.
      if (finished) {
        const sessionPayload = await fetchTreatmentSession(treatmentSessionId);
        if (isCurrent()) {
          setTreatment(sessionPayload);
          requestSelectionRefresh?.();
        }
      }
      if (isCurrent()) {
        queueWasRunningRef.current = Boolean(queue.running);
        setTreatmentQueue(queue);
      }
    }
    return payload;
  }, [requestSelectionRefresh, treatmentSessionId]);

  return {
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
  };
}
