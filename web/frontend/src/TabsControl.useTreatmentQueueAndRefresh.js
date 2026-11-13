import { useCallback, useEffect } from 'react';
import { fetchCleaningView, fetchFileSummary, fetchFolderListing, fetchTreatmentSession, enqueueStandardFolderTreatment, enqueueTreatmentRecipe, postTreatment, removeTreatmentQueueJob, runTreatmentQueue } from './api/treatmentClient';
import { sessionBackupKey } from "./TabsControl.PROFILE_PRESETS";
import { isEmptyTreatmentSession } from "./TabsControl.PROFILE_PRESETS";
import { hasRecoverableTreatmentWork } from "./TabsControl.PROFILE_PRESETS";
import { readSessionBackup } from "./TabsControl.PROFILE_PRESETS";
import { requiredDataTypesForExpType } from "./TabsControl.PROFILE_PRESETS";
import { shouldApplyAutoPreset } from "./TabsControl.PROFILE_PRESETS";
import { spectralSum } from "./treatmentOdModes";
import { pathName } from "./TabsControl.PROFILE_PRESETS";
import { mergeTreatmentQueue } from "./TabsControl.PROFILE_PRESETS";
import { folderPathChain } from "./TabsControl.PROFILE_PRESETS";

export function useTreatmentQueueAndRefresh({
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
}) {
  const handleQueueEnqueue = async () => {
    if (requireAppliedCleaningPreview()) {
      return;
    }
    if (!queueOutputConfigured) {
      setError('Set Save Folder and Save File Name before adding a queue recipe.');
      return;
    }
    if (queueApplyCleaning && !queueSupportsCurrentRecipeCleaning) {
      setError('Use Set/Convert/Clean/Calc for automatic SAM cleaning of paired inputs.');
      return;
    }

    const dataTypes = assignedCleaningTypes.filter((dataType) => session?.paths?.[dataType]);
    const cleaning = queueApplyCleaning
      ? {
          state: 'pending',
          enabled: true,
          angle_threshold: Number.parseFloat(cleaningAngleThreshold),
          surface_threshold: Number.parseFloat(cleaningSurfaceThreshold),
          data_types: dataTypes,
        }
      : { state: 'not_requested', enabled: false, data_types: [] };

    setError('');
    setIsQueueLoading(true);
    try {
      const payload = await enqueueTreatmentRecipe(treatmentSessionId, {
        label: queueLabel.trim() || pathName(session?.folder_path) || 'Treatment recipe',
        profile: treatmentProfile,
        convert_to_h5: queueConvertibleHisDataTypes.length > 0 ? queueConvertibleHisDataTypes : false,
        cleaning,
      });
      setTreatmentQueue((current) => mergeTreatmentQueue(current, payload?.queue));
      setQueueLabel('');
      setOperationMessage(
        `Current recipe ${payload?.started ? 'started' : 'queued behind active work'}.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsQueueLoading(false);
    }
  };

  const handleQueueStandardFolder = async (
    folderPath,
    { label, convert, clean, calculate, returnToFiles = true }
  ) => {
    const folders = Array.isArray(folderPath) ? folderPath : [folderPath];
    if (!folders[0] || (treeFirst && folderQueueActiveRef.current)) {
      return;
    }
    if (treeFirst) {
      folderQueueActiveRef.current = true;
      setIsQueueLoading(true);
      if (returnToFiles) setActiveTab('files');
    }
    const target = folders.length === 1 ? pathName(folders[0]) : `${folders.length} folders`;
    setError('');
    setFolderContextMenu(null);
    setOperationMessage(`Starting ${label} for ${target}…`);
    try {
      const payload = await enqueueStandardFolderTreatment(treatmentSessionId, {
        ...(treeFirst ? { folder_paths: folders, output_naming: 'sample',
          exp_type: shouldApplyAutoPreset(session, profilePreset) ? profilePreset.exp_type : session.exp_type }
          : { folder_path: folders[0] }),
        label: folders.length === 1 ? pathName(folders[0]) || label : undefined,
        profile: treatmentProfile,
        convert,
        clean,
        calculate,
        angle_threshold: Number(cleaningAngleThreshold),
        surface_threshold: Number(cleaningSurfaceThreshold),
      });
      const saveTarget = payload?.queue_job?.recipe?.save_target;
      if (saveTarget) {
        setDraftSaveFolder(saveTarget.save_folder || '');
        setDraftSaveFileName(saveTarget.save_file_name || '');
        setTreatment((current) => current ? {
          ...current,
          session: {
            ...current.session,
            save_folder: saveTarget.save_folder || '',
            save_file_name: saveTarget.save_file_name || '',
          },
        } : current);
      }
      queueWasRunningRef.current = true;
      setTreatmentQueue((current) => mergeTreatmentQueue(current, payload?.queue));
      // A short Set can finish before its enqueue response reaches the browser.
      if (!payload?.queue?.running) await refreshTreatmentQueue();
      setOperationMessage(
        `${label} ${payload?.started ? 'started' : 'queued'} for ${target}.`
      );
    } catch (err) {
      setOperationMessage('');
      setError(err.message);
    } finally {
      if (treeFirst) {
        folderQueueActiveRef.current = false;
        setIsQueueLoading(false);
      }
    }
  };

  const handleLoadFolderInputs = async () => {
    if (!sourceFolder || isSelectingFolderRoot || folderQueueActiveRef.current) return;
    folderQueueActiveRef.current = true;
    setIsQueueLoading(true);
    try {
      await handleQueueStandardFolder(sourceFolder, {
        label: 'Load folder inputs', convert: true, clean: false, calculate: false,
      });
    } finally {
      folderQueueActiveRef.current = false;
      setIsQueueLoading(false);
    }
  };

  const handleQueueRemove = async (jobId) => {
    if (!jobId) {
      return;
    }
    setError('');
    setIsQueueLoading(true);
    try {
      const payload = await removeTreatmentQueueJob(treatmentSessionId, jobId);
      setTreatmentQueue(payload?.queue || { running: false, jobs: [] });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsQueueLoading(false);
    }
  };

  const loadFileSummary = useCallback(
    async (file) => {
      if (!file?.path || !['.his', '.h5', '.dat'].includes(String(file.suffix || '').toLowerCase())) {
        return;
      }
      if (fileSummaryCache[file.path]) {
        return;
      }

      setFileSummaryCache((current) => ({
        ...current,
        [file.path]: { loading: true },
      }));
      try {
        const payload = await fetchFileSummary(treatmentSessionId, file.path);
        setFileSummaryCache((current) => ({
          ...current,
          [file.path]: payload.file_summary || {},
        }));
      } catch (err) {
        setFileSummaryCache((current) => ({
          ...current,
          [file.path]: { error: err.message },
        }));
      }
    },
    [fileSummaryCache, treatmentSessionId]
  );

  const refreshCleaningView = useCallback(async () => {
    setIsCleaningViewLoading(true);
    try {
      const payload = await fetchCleaningView(treatmentSessionId);
      setCleaningView(payload.cleaning_view);
      return payload.cleaning_view;
    } catch (err) {
      setCleaningView(null);
      return null;
    } finally {
      setIsCleaningViewLoading(false);
    }
  }, [treatmentSessionId]);

  const cacheFolderListing = useCallback((folderPath, payload) => {
    if (!folderPath) {
      return;
    }
    setFolderTreeCache((current) => ({
      ...current,
      [folderPath]: {
        folders: payload.folders || [],
        files: payload.files || [],
      },
    }));
  }, []);

  const refreshFolderListing = useCallback(
    async (folderPath) => {
      if (!folderPath) {
        return;
      }

      const payload = await fetchFolderListing(treatmentSessionId, folderPath);
      cacheFolderListing(folderPath, payload);
    },
    [cacheFolderListing, treatmentSessionId]
  );

  const loadFolderTreeNode = useCallback(
    async (folderPath) => {
      if (!folderPath || folderTreeCache[folderPath]) {
        return;
      }
      const payload = await fetchFolderListing(treatmentSessionId, folderPath);
      cacheFolderListing(folderPath, payload);
    },
    [cacheFolderListing, folderTreeCache, treatmentSessionId]
  );

  const ensureFolderTreePath = useCallback(
    async (folderPath, allowedRoot) => {
      const chain = folderPathChain(folderPath, allowedRoot);
      if (chain.length === 0) {
        return;
      }

      setExpandedFolders((current) => {
        const next = new Set(current);
        chain.forEach((path) => next.add(path));
        return next;
      });

      await Promise.all(
        chain.map(async (path) => {
          const payload = await fetchFolderListing(treatmentSessionId, path);
          cacheFolderListing(path, payload);
        })
      );
    },
    [cacheFolderListing, treatmentSessionId]
  );

  useEffect(() => {
    let cancelled = false;

    const loadSession = async () => {
      let presetError = null;
      let restoreError = null;
      try {
        let payload = await fetchTreatmentSession(treatmentSessionId);
        if (cancelled) return;
        if (payload.session_persistence === 'sqlite' && isEmptyTreatmentSession(payload.session)) {
          const backup = readSessionBackup(treatmentSessionId);
          if (hasRecoverableTreatmentWork(backup)) {
            try {
              payload = await postTreatment(treatmentSessionId, '/api/treatment/session/restore', {
                session: backup,
              });
            } catch (err) {
              restoreError = err;
              if (!cancelled) setError(`Saved treatment session could not be restored: ${err.message}`);
            }
          }
        }
        if (treatmentContext?.initialFolder && payload.session.folder_path !== treatmentContext.initialFolder) {
          try {
            payload = await postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
              folder_path: treatmentContext.initialFolder,
            });
            if (!cancelled) {
              setTreeRoot(treatmentContext.initialFolder);
              setIsFolderTreeOpen(true);
            }
          } catch (err) {
            // Keep Data Root controls available when a linked folder cannot be selected.
            if (!cancelled) setError(`Cannot open selected folder: ${err.message}. Check Data Root.`);
          }
        }
        if (shouldApplyAutoPreset(payload.session, profilePreset)) {
          try {
            payload = await postTreatment(
              treatmentSessionId,
              '/api/treatment/session/config',
              profilePreset
            );
          } catch (err) {
            // Keep the readable session available when applying the preset fails.
            presetError = err;
            if (!cancelled) setError(err.message);
          }
        }

        if (!cancelled) {
          setTreatment(payload);
          if (requestSelectionRefresh) {
            requestSelectionRefresh();
          }
        }

        if (!cancelled && payload.session.folder_path) {
          await refreshFolderListing(payload.session.folder_path);
          await ensureFolderTreePath(payload.session.folder_path, payload.allowed_root);
        }
        if (
          !cancelled &&
          payload.allowed_root &&
          payload.allowed_root !== payload.session.folder_path
        ) {
          const rootPayload = await fetchFolderListing(treatmentSessionId, payload.allowed_root);
          if (!cancelled) {
            cacheFolderListing(payload.allowed_root, rootPayload);
          }
        }
      } catch (err) {
        if (!cancelled) {
          // A subsequent folder error must not hide authentication recovery.
          setError(restoreError?.message || presetError?.message || err.message);
        }
      }
    };

    loadSession();

    return () => {
      cancelled = true;
    };
  }, [
    cacheFolderListing,
    ensureFolderTreePath,
    profilePreset,
    refreshFolderListing,
    requestSelectionRefresh,
    treatmentSessionId,
    treatmentContext?.initialFolder,
  ]);

  useEffect(() => {
    if (!isStudioLayout) {
      return undefined;
    }
    let cancelled = false;
    const isCurrent = () => !cancelled;
    refreshTreatmentQueue(isCurrent).catch((err) => {
      if (!cancelled) {
        setError(err.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [isStudioLayout, refreshTreatmentQueue, treatmentSessionId]);

  useEffect(() => {
    if (!isStudioLayout || !treatmentQueue?.running) {
      return undefined;
    }
    let cancelled = false;
    let timeoutId;
    const poll = async () => {
      try {
        await refreshTreatmentQueue(() => !cancelled);
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
      if (!cancelled) {
        timeoutId = window.setTimeout(poll, 1500);
      }
    };
    timeoutId = window.setTimeout(poll, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [isStudioLayout, refreshTreatmentQueue, treatmentQueue?.running]);

  useEffect(() => {
    if (activeTab === 'cleaning') {
      refreshCleaningView();
    }
  }, [activeTab, refreshCleaningView, session?.active_data_type, session?.paths]);

  useEffect(() => {
    const closeContextMenu = () => {
      setFileContextMenu(null);
      setFolderContextMenu(null);
    };
    window.addEventListener('click', closeContextMenu);
    window.addEventListener('keydown', closeContextMenu);
    return () => {
      window.removeEventListener('click', closeContextMenu);
      window.removeEventListener('keydown', closeContextMenu);
    };
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }
    setDraftSaveFolder(session.save_folder || '');
    setDraftSaveFileName(session.save_file_name || '');
    setDraftAllowedRoot(manifestProjectFolder?(session.folder_path||manifestProjectFolder):(treatment?.allowed_root || ''));
  }, [session, treatment?.allowed_root,manifestProjectFolder]);

  useEffect(() => {
    if (!persistedCleaningPreview) {
      return;
    }
    setPendingCleaningPreview((current) => {
      if (
        current &&
        !current.backend &&
        current.dataType === persistedCleaningPreview.dataType &&
        current.sourcePath === persistedCleaningPreview.sourcePath
      ) {
        return current;
      }
      return persistedCleaningPreview;
    });
  }, [persistedCleaningPreview]);

  useEffect(() => {
    if (!treeRoot && (session?.folder_path || treatment?.allowed_root)) {
      setTreeRoot(session?.folder_path || treatment?.allowed_root || '');
    }
  }, [session?.folder_path, treatment?.allowed_root, treeRoot]);

  useEffect(() => {
    const rootsToExpand = [treatment?.allowed_root, session?.folder_path].filter(Boolean);
    if (rootsToExpand.length === 0) {
      return;
    }
    setExpandedFolders((current) => {
      const next = new Set(current);
      rootsToExpand.forEach((folderPath) => next.add(folderPath));
      return next;
    });
  }, [session?.folder_path, treatment?.allowed_root]);

  useEffect(() => {
    if (treeFirst) return;
    const visibleFiles = [];
    Object.entries(folderTreeCache).forEach(([folderPath, listing]) => {
      if (folderPath !== treeRoot && !expandedFolders.has(folderPath)) {
        return;
      }
      (listing.files || []).forEach((file) => {
        const suffix = String(file.suffix || '').toLowerCase();
        if (suffix === '.his' || suffix === '.h5') {
          visibleFiles.push(file);
        }
      });
    });
    visibleFiles.slice(0, 40).forEach((file) => {
      loadFileSummary(file);
    });
  }, [expandedFolders, fileSummaryCache, folderTreeCache, loadFileSummary, treeRoot, treeFirst]);

  const applyPayload = async (requestPromise, refreshListing = false) => {
    setError('');
    setIsBusy(true);
    try {
      const payload = await requestPromise;
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      if (refreshListing && payload.session.folder_path) {
        await refreshFolderListing(payload.session.folder_path);
      }
      return payload;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setIsBusy(false);
    }
  };

  const handleConfigChange = (patch) => {
    if (!session) {
      return;
    }
    const normalizedPatch = { ...patch };
    const nextExpType = normalizedPatch.exp_type || session.exp_type;
    const nextRequired = requiredDataTypesForExpType(nextExpType);

    if (!Object.prototype.hasOwnProperty.call(normalizedPatch, 'selected_data_type')) {
      if (nextRequired.length > 0 && !nextRequired.includes(session.selected_data_type)) {
        normalizedPatch.selected_data_type = nextRequired[0];
      }
    }

    if (
      Object.prototype.hasOwnProperty.call(normalizedPatch, 'exp_type')
      && !Object.prototype.hasOwnProperty.call(normalizedPatch, 'calc_mode')
    ) {
      normalizedPatch.calc_mode = treatmentProfile === 'VD2' && nextExpType !== 'HIS'
        ? spectralSum : nextExpType === 'HIS' || nextExpType === 'ABS+BASE+NOISE' ? 'averaged' : 'individual';
    }

    applyPayload(postTreatment(treatmentSessionId, '/api/treatment/session/config', normalizedPatch));
  };

  const handleReset = async () => {
    const payload = await applyPayload(
      postTreatment(treatmentSessionId, '/api/treatment/session/reset'), true
    );
    if (payload) {
      try {
        window.localStorage.removeItem(sessionBackupKey(treatmentSessionId));
      } catch (_error) {
        // The server-side reset already succeeded.
      }
    }
  };

  const handleQueueRun = async () => {
    setError('');
    setIsQueueLoading(true);
    try {
      const payload = await runTreatmentQueue(treatmentSessionId);
      setTreatmentQueue(payload?.queue || { running: false, jobs: [] });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsQueueLoading(false);
    }
  };

  return {
    handleQueueEnqueue, handleQueueStandardFolder, handleLoadFolderInputs,
    handleQueueRemove, loadFileSummary, refreshCleaningView, cacheFolderListing,
    refreshFolderListing, loadFolderTreeNode, applyPayload, handleConfigChange,
    handleReset, handleQueueRun,
  };
}
