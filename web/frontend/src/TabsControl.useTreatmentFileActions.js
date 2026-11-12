import { fetchCompressionJob, fetchFolderListing, postTreatment, startCompressionJob } from './api/treatmentClient';
import { isProjectManifest } from "./TabsControl.PROFILE_PRESETS";
import { shouldApplyAutoPreset } from "./TabsControl.PROFILE_PRESETS";
import { getParentFolder } from "./TabsControl.PROFILE_PRESETS";
import { pathName } from "./TabsControl.PROFILE_PRESETS";
import { summarizeFileCompression } from "./TabsControl.PROFILE_PRESETS";
import { summarizeCompressionProgress } from "./TabsControl.PROFILE_PRESETS";
import { wait } from "./TabsControl.PROFILE_PRESETS";

export function useTreatmentFileActions({
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
}) {
  const handleAllowedRootChange = async () => {
    const nextAllowedRoot = draftAllowedRoot.trim();
    if(manifestProjectFolder){
      if(!nextAllowedRoot||nextAllowedRoot===session.folder_path)return;
      const payload=await applyPayload(postTreatment(treatmentSessionId,'/api/treatment/session/folder',{folder_path:nextAllowedRoot}),true);
      if(payload){setTreeRoot(payload.session.folder_path);setDraftAllowedRoot(payload.session.folder_path);setIsFolderTreeOpen(true);}
      return;
    }
    if (!nextAllowedRoot || nextAllowedRoot === treatment.allowed_root) {
      return;
    }

    setError('');
    setIsBusy(true);
    try {
      let payload = await postTreatment(treatmentSessionId, '/api/treatment/session/root', {
        allowed_root: nextAllowedRoot,
      });
      if (treatmentContext?.initialFolder) {
        try {
          payload = await postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
            folder_path: treatmentContext.initialFolder,
          });
        } catch (err) {
          setError(`Cannot open selected folder: ${err.message}. Check Data Root.`);
        }
      }
      if (shouldApplyAutoPreset(payload.session, profilePreset)) {
        payload = await postTreatment(treatmentSessionId, '/api/treatment/session/config', profilePreset);
      }
      setTreatment(payload);
      setDraftAllowedRoot(payload.allowed_root || '');
      setCleaningSummary(null);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(payload.session.folder_path || payload.allowed_root);
      const rootPayload = await fetchFolderListing(treatmentSessionId, payload.allowed_root);
      cacheFolderListing(payload.allowed_root, rootPayload);
      setTreeRoot(payload.session.folder_path || payload.allowed_root || '');
      setIsSelectingFolderRoot(true);
      setIsFolderTreeOpen(true);
      setExpandedFolders((current) => {
        const next = new Set(current);
        next.add(payload.allowed_root);
        return next;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleAllowedRootKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleAllowedRootChange();
    }
  };

  const handleAssignFile = async (filePath, dataType = session?.selected_data_type) => {
    if (!session) {
      return;
    }
    if (!dataType) {
      return;
    }

    setError('');
    setOperationMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/cache-path', {
        data_type: dataType,
        file_path: filePath,
      });
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      const cachedPath = payload.cached_file?.cached_path || filePath;
      setOperationMessage(`Set to ${dataType}: ${cachedPath}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setFileContextMenu(null);
      setIsBusy(false);
    }
  };

  const handlePreviewDat = async filePath => {
    if (isBusy) return;
    setIsBusy(true); setError(''); setFileContextMenu(null);
    try {
      await postTreatment(treatmentSessionId, '/api/treatment/preview/dat', { file_path: filePath });
      requestSelectionRefresh?.();
      setOperationMessage(`Preview: ${pathName(filePath)}`);
    } catch (cause) { setError(cause.message); }
    finally { setIsBusy(false); }
  };
  const handleManifestFolder = async folder => {
    setFolderContextMenu(null); setIsBusy(true); setError('');
    try {
      const listing = await fetchFolderListing(treatmentSessionId, folder);
      const manifest = listing.files.find(isProjectManifest);
      if (!manifest) throw new Error('No vd2-manifest.json in this project folder.');
      treatmentContext?.onOpenManifest?.(manifest.path);
    } catch (cause) { setError(cause.message); }
    finally { setIsBusy(false); }
  };

  const handleSetStitchFile = (filePath, side) => {
    if (!filePath) {
      return;
    }
    if (side === 'A') {
      setStitchFileA(filePath);
    } else {
      setStitchFileB(filePath);
    }
    setStitchPreview(null);
    setStitchSummary(null);
    setFileContextMenu(null);
    setOperationMessage(`Set Stitch ${side}: ${pathName(filePath)}`);
  };

  const handleCompressFile = async (filePath) => {
    if (!session || !filePath) {
      return;
    }

    setError('');
    const suffix = String(filePath).split('?')[0].toLowerCase().split('.').pop();
    setOperationMessage(
      [
        `Convert/Compress started for ${pathName(filePath)}.`,
        'Reading source file...',
        'Writing H5 with gzip level 4...',
        suffix === 'his'
          ? 'HIS will be removed after H5 is verified.'
          : 'H5 will be overwritten in place.',
      ].join('\n')
    );
    setSelectionMessage('');
    setCleaningSummary(null);
    setFileContextMenu(null);
    setIsBusy(true);
    try {
      const started = await startCompressionJob(treatmentSessionId, filePath);
      let job = started.compression_job;
      setOperationMessage(summarizeCompressionProgress(job, filePath));
      let payload = null;
      while (job?.status === 'running') {
        await wait(500);
        const statusPayload = await fetchCompressionJob(treatmentSessionId, job.job_id);
        job = statusPayload.compression_job;
        setOperationMessage(summarizeCompressionProgress(job, filePath));
      }
      if (job?.status === 'error') {
        throw new Error(job.error || job.message || 'Convert/Compress failed.');
      }
      payload = job?.payload || { conversion: job?.conversion };
      setTreatment(payload);
      setOperationMessage(summarizeFileCompression(payload));
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(getParentFolder(filePath, treatment?.allowed_root));
    } catch (err) {
      setError(err.message);
      setOperationMessage(`Convert/Compress failed for ${pathName(filePath)}.`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleFolderTreeToggle = async (folderPath) => {
    if (!folderPath) {
      return;
    }
    const isExpanded = expandedFolders.has(folderPath);
    setExpandedFolders((current) => {
      const next = new Set(current);
      if (isExpanded) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });
    if (!isExpanded) {
      try {
        await loadFolderTreeNode(folderPath);
      } catch (err) {
        setError(err.message);
      }
    }
  };

  const handleExplorerFolderSelect = async (folderPath) => {
    if (!folderPath) {
      return;
    }
    if (!isSelectingFolderRoot) {
      await handleFolderTreeToggle(folderPath);
      return;
    }

    setError('');
    await applyPayload(
      postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
        folder_path: folderPath,
      }),
      true
    );
    setTreeRoot(folderPath);
    setSelectedFolders([]);
    folderSelectionAnchor.current = null;
    setIsSelectingFolderRoot(false);
    setExpandedFolders((current) => {
      const next = new Set(current);
      next.add(folderPath);
      return next;
    });
    try {
      await loadFolderTreeNode(folderPath);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFolderTreeOpen = async () => {
    if (!treatment?.allowed_root) {
      return;
    }

    setError('');
    setIsFolderTreeOpen(true);
    setIsSelectingFolderRoot(true);
    const root=manifestProjectFolder?(session?.folder_path||manifestProjectFolder):treatment.allowed_root;
    setTreeRoot(root);
    setExpandedFolders((current) => {
      const next = new Set(current);
      next.add(root);
      return next;
    });
    try {
      await loadFolderTreeNode(root);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFileContextMenu = (event, file) => {
    event.preventDefault();
    event.stopPropagation();
    if ((!treeFirst && !file.supported && !isProjectManifest(file)) || isBusy) {
      return;
    }
    setFolderContextMenu(null);
    const bounds = event.currentTarget.getBoundingClientRect();
    setFileContextMenu({
      file,
      x: event.clientX ?? bounds.left,
      y: event.clientY ?? bounds.bottom,
    });
  };

  const handleFolderContextMenu = (event, folder) => {
    event.preventDefault();
    event.stopPropagation();
    if (!folder?.path || isBusy) {
      return;
    }
    setFileContextMenu(null);
    const paths = selectedFolders.includes(folder.path) ? selectedFolders : [folder.path];
    if (treeFirst) setSelectedFolders(paths);
    setFolderContextMenu({
      folder,
      paths,
      x: event.clientX,
      y: event.clientY,
    });
  };

  const handleTreeFolderClick = (event, folderPath, siblings) => {
    if (!treeFirst || isSelectingFolderRoot) {
      handleExplorerFolderSelect(folderPath);
      return;
    }
    const anchor = siblings.indexOf(folderSelectionAnchor.current);
    const clicked = siblings.indexOf(folderPath);
    if (event.shiftKey && anchor >= 0) {
      setSelectedFolders(siblings.slice(Math.min(anchor, clicked), Math.max(anchor, clicked) + 1));
      return;
    }
    folderSelectionAnchor.current = folderPath;
    setSelectedFolders(current => event.ctrlKey || event.metaKey
      ? current.includes(folderPath) ? current.filter(path => path !== folderPath) : [...current, folderPath]
      : [folderPath]);
  };

  const toggleBatchFolder = (folderPath) => {
    setIsSelectingFolderRoot(false);
    folderSelectionAnchor.current = folderPath;
    setSelectedFolders(current => current.includes(folderPath)
      ? current.filter(path => path !== folderPath)
      : [...current, folderPath]);
  };

  const handleAverageNoise = async () => {
    setError('');
    setIsBusy(true);
    setOperationMessage('');
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/average-noise');
      setTreatment(payload);
      setOperationMessage('Noise averaged on the backend.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCalcAbs = async () => {
    if (requireAppliedCleaningPreview()) {
      return;
    }
    setError('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/calc-abs');
      setTreatment(payload);
      setSavedResultPath('');
      if (treeFirst) setActiveTab('files');
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      setOperationMessage('OD result calculated on the backend.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleSave = async () => {
    setError('');
    setIsBusy(true);
    try {
      const output = {};
      if (draftSaveFolder !== session.save_folder) output.save_folder = draftSaveFolder;
      if (draftSaveFileName !== session.save_file_name) output.save_file_name = draftSaveFileName;
      if (Object.keys(output).length) {
        await postTreatment(treatmentSessionId, '/api/treatment/session/config', output);
      }
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/save');
      setTreatment(payload);
      const savePath = String(payload?.saved?.save_path || '');
      setSavedResultPath(savePath);
      setOperationMessage(savePath ? `Result saved to ${savePath}` : 'Result saved on the backend.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCopySavedResultPath = async () => {
    if (!savedResultPath) {
      return;
    }
    try {
      await navigator.clipboard.writeText(savedResultPath);
      setError('');
      setOperationMessage('Result path copied.');
    } catch (_error) {
      setError('Could not copy the result path. Select and copy it manually.');
    }
  };

  const handleCommitSaveFolder = () => {
    if (!session || draftSaveFolder === session.save_folder) {
      return;
    }
    handleConfigChange({ save_folder: draftSaveFolder });
  };

  const handleCommitSaveFileName = () => {
    if (!session || draftSaveFileName === session.save_file_name) {
      return;
    }
    handleConfigChange({ save_file_name: draftSaveFileName });
  };

  const formatExportRanges = (ranges) =>
    (ranges || [])
      .map((item) => `${item.center} ${item.width}`)
      .join('; ');

  return {
    handleAllowedRootChange, handleAllowedRootKeyDown, handleAssignFile, handlePreviewDat,
    handleManifestFolder, handleSetStitchFile, handleCompressFile, handleFolderTreeToggle,
    handleFolderTreeOpen, handleFileContextMenu, handleFolderContextMenu,
    handleTreeFolderClick, toggleBatchFolder, handleAverageNoise, handleCalcAbs,
    handleSave, handleCopySavedResultPath, handleCommitSaveFolder,
    handleCommitSaveFileName, formatExportRanges,
  };
}
