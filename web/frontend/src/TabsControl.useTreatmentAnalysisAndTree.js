import React, { useCallback, useEffect, useMemo } from 'react';
import { fetchFolderListing, postTreatment, updateSelectionConfig } from './api/treatmentClient';
import { isProjectManifest } from "./TabsControl.PROFILE_PRESETS";
import { getPathParent } from "./TabsControl.PROFILE_PRESETS";
import { joinPath } from "./TabsControl.PROFILE_PRESETS";
import { pathName } from "./TabsControl.PROFILE_PRESETS";
import { stitchedNameForPaths } from "./TabsControl.PROFILE_PRESETS";
import { cropHeatmapMap } from "./TabsControl.PROFILE_PRESETS";
import { sortStitchDatFiles } from "./TabsControl.PROFILE_PRESETS";
import { formatFileSize } from "./TabsControl.PROFILE_PRESETS";
import { formatWavelengthRange } from "./TabsControl.PROFILE_PRESETS";
import { formatTimeRange } from "./TabsControl.PROFILE_PRESETS";
import { formatFrameCount } from "./TabsControl.PROFILE_PRESETS";
import { folderPathChain } from "./TabsControl.PROFILE_PRESETS";

export function useTreatmentAnalysisAndTree({
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
}) {
  const handleSelectionExport = async (userType) => {
    const ranges = userType === 'kinetics' ? draftKineticsRanges : draftSpectraRanges;

    setError('');
    setSelectionMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/selection/export', {
        user_type: userType,
        ranges,
      });

      setTreatment(payload);
      const normalizedRanges = formatExportRanges(payload.exported.ranges);
      if (userType === 'kinetics') {
        setDraftKineticsRanges(normalizedRanges);
      } else {
        setDraftSpectraRanges(normalizedRanges);
      }

      setSelectionMessage(
        `${userType} exported to ${payload.exported.output_path}`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleV0QuickExport = async () => {
    const kineticsRanges = draftKineticsRanges || '500+-10; 600+-5';
    const spectraRanges = draftSpectraRanges || '1+-0.5; 3+-1';
    let kineticsOutputPath = '';

    setError('');
    setSelectionMessage('');
    setIsBusy(true);
    try {
      const kineticsPayload = await postTreatment(
        treatmentSessionId,
        '/api/treatment/selection/export',
        {
          user_type: 'kinetics',
          ranges: kineticsRanges,
        }
      );
      kineticsOutputPath = kineticsPayload.exported.output_path;
      setDraftKineticsRanges(formatExportRanges(kineticsPayload.exported.ranges));

      const spectraPayload = await postTreatment(
        treatmentSessionId,
        '/api/treatment/selection/export',
        {
          user_type: 'spectra',
          ranges: spectraRanges,
        }
      );
      setTreatment(spectraPayload);
      setDraftSpectraRanges(formatExportRanges(spectraPayload.exported.ranges));
      setSelectionMessage(
        `V0 quick export completed: kinetics -> ${kineticsOutputPath}; spectra -> ${spectraPayload.exported.output_path}`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCleaningTargetChange = async (dataType) => {
    if (!dataType || dataType === session?.active_data_type) {
      return;
    }
    if (pendingCleaningPreview && pendingCleaningPreview.dataType !== dataType) {
      setError(
        `Apply or reset the ${pendingCleaningPreview.dataType} cleaning preview before selecting another role.`
      );
      return;
    }

    setError('');
    setOperationMessage('');
    setCleaningSummary(null);
    setIsBusy(true);
    try {
      const payload = await updateSelectionConfig(treatmentSessionId, {
        active_data_type: dataType,
        map_index: 0,
        selection: {},
      });
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshCleaningView();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCleaningThresholdChange = (field, value) => {
    if (field === 'angle') {
      setCleaningAngleThreshold(value);
    } else {
      setCleaningSurfaceThreshold(value);
    }
    if (pendingCleaningPreview) {
      setPendingCleaningPreview((current) => current && {
        ...current,
        invalidated: true,
      });
      setOperationMessage('Cleaning preview invalidated after threshold change. Preview cleaning again before applying a mask to H5.');
    }
  };

  const handleCleaningAction = async (mode) => {
    if (
      mode === 'analyze' &&
      pendingCleaningPreview &&
      pendingCleaningPreview.dataType !== cleaningActiveDataType
    ) {
      setError(
        `Apply or reset the ${pendingCleaningPreview.dataType} cleaning preview before previewing another role.`
      );
      return;
    }
    if (
      mode === 'save' &&
      !canApplyCleaningPreview
    ) {
      setError('Preview cleaning again with the current thresholds before applying a map selection to H5.');
      return;
    }
    setError('');
    setSelectionMessage('');
    setIsBusy(true);

    try {
      let payload;
      if (mode === 'reset') {
        payload = await postTreatment(treatmentSessionId, '/api/treatment/cleaning/reset');
      } else if (mode === 'restore') {
        payload = await postTreatment(treatmentSessionId, '/api/treatment/cleaning/restore');
      } else {
        payload = await postTreatment(
          treatmentSessionId,
          mode === 'analyze' ? '/api/treatment/cleaning/sam' : '/api/treatment/cleaning/save',
          {
            angle_threshold: Number.parseFloat(cleaningAngleThreshold),
            surface_threshold: Number.parseFloat(cleaningSurfaceThreshold),
            output_file_name: '',
          }
        );
      }

      if (mode === 'reset') {
        setCleaningSummary(null);
        setPendingCleaningPreview(null);
        if (payload.cleaning_view) {
          setCleaningView(payload.cleaning_view);
        } else {
          refreshCleaningView();
        }
        setOperationMessage(
          payload.cleaning.discarded_measurements
            ? `Cleaning state reset for ${payload.cleaning.file_path}.`
            : 'Cleaning state was already empty.'
        );
      } else if (mode === 'restore') {
        setTreatment(payload);
        setCleaningSummary(payload.cleaning);
        setPendingCleaningPreview(null);
        if (payload.cleaning_view) {
          setCleaningView(payload.cleaning_view);
        }
        if (payload.cleaning?.output_path) {
          setFileSummaryCache((current) => {
            const next = { ...current };
            delete next[payload.cleaning.output_path];
            return next;
          });
        }
        setOperationMessage(
          payload.cleaning?.restored
            ? `Re-included ${payload.cleaning.restored_measurements} maps for processing.`
            : 'All raw maps are already included.'
        );
        if (requestSelectionRefresh) {
          requestSelectionRefresh();
        }
      } else {
        setCleaningSummary(payload.cleaning);
        if (payload.cleaning_view) {
          setCleaningView(payload.cleaning_view);
        }
        if (mode === 'save') {
          setTreatment(payload);
          setPendingCleaningPreview(null);
          setOperationMessage(
            `Cleaned H5 saved to ${payload.cleaning.output_path} and assigned as ${payload.cleaning.assigned_data_type || session?.active_data_type || 'active file'}.`
          );
          if (requestSelectionRefresh) {
            requestSelectionRefresh();
          }
          refreshCleaningView();
        } else if (payload.cleaning.state_updated === false) {
          setPendingCleaningPreview(null);
          setOperationMessage(payload.cleaning.warning || 'No measurements passed the thresholds.');
        } else if (payload.cleaning.source_measurements !== payload.cleaning.original_measurements) {
          setPendingCleaningPreview({
            dataType: cleaningActiveDataType,
            sourcePath: cleaningSourcePath,
            angleThreshold: cleaningAngleThreshold,
            surfaceThreshold: cleaningSurfaceThreshold,
          });
          setOperationMessage(
            `Cleaning preview prepared from ${payload.cleaning.source_measurements} currently included maps. Apply mask to H5 before calculating OD.`
          );
        } else {
          setPendingCleaningPreview({
            dataType: cleaningActiveDataType,
            sourcePath: cleaningSourcePath,
            angleThreshold: cleaningAngleThreshold,
            surfaceThreshold: cleaningSurfaceThreshold,
          });
          setOperationMessage('Cleaning preview prepared from original file maps. Apply mask to H5 before calculating OD.');
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const stitchRequestPayload = () => ({
    file_a: stitchFileA,
    file_b: stitchFileB,
    time_regions: stitchRegions,
    left_scale: Number.parseFloat(stitchLeftScale),
    left_offset: Number.parseFloat(stitchLeftOffset),
    right_scale: Number.parseFloat(stitchRightScale),
    right_offset: Number.parseFloat(stitchRightOffset),
    right_delay_shift_pixels: Number.parseInt(stitchRightDelayShift, 10) || 0,
  });

  const syncStitchRegionInputs = useCallback((region) => {
    if (!region) {
      return;
    }
    setStitchLeftWavelengthStart(String(region.left_wavelength_start ?? region.wavelength_start ?? ''));
    setStitchLeftWavelengthEnd(String(region.left_wavelength_end ?? region.wavelength_end ?? ''));
    setStitchRightWavelengthStart(String(region.right_wavelength_start ?? region.wavelength_start ?? ''));
    setStitchRightWavelengthEnd(String(region.right_wavelength_end ?? region.wavelength_end ?? ''));
    setStitchRegionStart(String(region.delay_start ?? ''));
    setStitchRegionEnd(String(region.delay_end ?? ''));
  }, []);

  const handleStitchRegionsChange = useCallback((regions) => {
    setStitchRegions(regions);
    syncStitchRegionInputs(regions?.[regions.length - 1]);
  }, [syncStitchRegionInputs]);

  const refreshStitchPreview = async (fitRight = false, silent = false, auto = false, coefficientOverrides = null) => {
    setError('');
    if (!silent) {
      setOperationMessage('');
    }
    if (!stitchFileA || !stitchFileB) {
      setError('Select two OD DAT files.');
      return;
    }
    const attemptKey = `${stitchFileA}|${stitchFileB}`;
    if (auto) {
      if (stitchAutoPreviewAttemptKeyRef.current === attemptKey) {
        return;
      }
      stitchAutoPreviewAttemptKeyRef.current = attemptKey;
    } else {
      stitchAutoPreviewAttemptKeyRef.current = '';
    }
    if (!silent) {
      setIsBusy(true);
    }
    try {
      const requestPayload = {
        ...stitchRequestPayload(),
        ...(coefficientOverrides || {}),
        fit_right: fitRight,
      };
      if (fitRight) {
        requestPayload.right_scale = 1;
        requestPayload.right_offset = 0;
      }
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/stitch/od/preview', requestPayload);
      const preview = payload.stitch_preview;
      if (stitchRegions.length === 0 && preview.overlap_range && preview.timedelay_min !== null && preview.timedelay_max !== null) {
        const defaultRegion = {
          left_wavelength_start: preview.overlap_range[0],
          left_wavelength_end: preview.overlap_range[1],
          right_wavelength_start: preview.overlap_range[0],
          right_wavelength_end: preview.overlap_range[1],
          delay_start: preview.timedelay_min,
          delay_end: preview.timedelay_max,
          label: 'Region 1',
        };
        setStitchRegions([defaultRegion]);
        syncStitchRegionInputs(defaultRegion);
      }
      setStitchPreview(preview);
      if (preview.suggested_output_file_name && stitchOutputName === 'stitched_od.dat') {
        setStitchOutputName(preview.suggested_output_file_name);
      }
      if (preview.fit) {
        skipNextStitchCoefficientRefreshRef.current = true;
        setStitchRightScale(String(Number(preview.fit.right_scale).toPrecision(8)));
        setStitchRightOffset(String(Number(preview.fit.right_offset).toPrecision(8)));
      }
      if (!silent) {
        setOperationMessage(
          fitRight
            ? `Right map fitted by integrated profile: scale ${Number(preview.coefficients.right_scale).toPrecision(6)}.`
            : coefficientOverrides
              ? 'Stitch fit reverted.'
              : 'Stitch pair loaded.'
        );
      }
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) {
        setIsBusy(false);
      }
    }
  };

  const handleRevertStitchFit = () => {
    skipNextStitchCoefficientRefreshRef.current = true;
    setStitchRightScale('1');
    setStitchRightOffset('0');
    refreshStitchPreview(false, false, false, { right_scale: 1, right_offset: 0 });
  };

  const handleAddStitchRegion = () => {
    const leftWavelengthStart = Number.parseFloat(stitchLeftWavelengthStart);
    const leftWavelengthEnd = Number.parseFloat(stitchLeftWavelengthEnd);
    const rightWavelengthStart = Number.parseFloat(stitchRightWavelengthStart);
    const rightWavelengthEnd = Number.parseFloat(stitchRightWavelengthEnd);
    const delayStart = Number.parseFloat(stitchRegionStart);
    const delayEnd = Number.parseFloat(stitchRegionEnd);
    if (
      !Number.isFinite(leftWavelengthStart) ||
      !Number.isFinite(leftWavelengthEnd) ||
      !Number.isFinite(rightWavelengthStart) ||
      !Number.isFinite(rightWavelengthEnd) ||
      !Number.isFinite(delayStart) ||
      !Number.isFinite(delayEnd)
    ) {
      setError('Left/right wavelength and delay bounds must be numeric.');
      return;
    }
    setError('');
    setStitchRegions((current) => [
      ...current,
      {
        left_wavelength_start: leftWavelengthStart,
        left_wavelength_end: leftWavelengthEnd,
        right_wavelength_start: rightWavelengthStart,
        right_wavelength_end: rightWavelengthEnd,
        delay_start: delayStart,
        delay_end: delayEnd,
        label: `Region ${current.length + 1}`,
      },
    ]);
  };

  const handleRemoveStitchRegion = (indexToRemove) => {
    setStitchRegions((current) => current.filter((_item, index) => index !== indexToRemove));
  };

  const handleStitchOd = async () => {
    setError('');
    setOperationMessage('');
    setStitchSummary(null);
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/stitch/od', {
        ...stitchRequestPayload(),
        output_folder: stitchOutputFolder,
        output_file_name: stitchOutputName,
        fit: stitchPreview?.fit || null,
      });
      setTreatment(payload);
      setStitchSummary(payload.stitched);
      setOperationMessage(`Stitched OD saved to ${payload.stitched.output_path}.`);
      if (stitchOutputFolder) {
        try {
          await refreshFolderListing(stitchOutputFolder);
        } catch (_refreshError) {
          // Saving succeeded; tree refresh is best effort for remote shares.
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const activeStitchRegion = stitchRegions[stitchRegions.length - 1] || stitchRegions[0] || null;
  const stitchOutputFolder = getPathParent(stitchFileA) || session?.save_folder || session?.folder_path || '';
  const stitchOutputPath = joinPath(stitchOutputFolder, stitchOutputName);
  const stitchZoneMap = useMemo(() => {
    if (!stitchPreview?.stitched) {
      return null;
    }
    const delayRange = activeStitchRegion
      ? [activeStitchRegion.delay_start, activeStitchRegion.delay_end]
      : [stitchPreview.timedelay_min, stitchPreview.timedelay_max];
    return cropHeatmapMap(stitchPreview.stitched, stitchPreview.overlap_range, delayRange);
  }, [activeStitchRegion, stitchPreview]);

  const renderFolderTreeFiles = (files, level = 1) =>
    (files || []).map((file) => {
      const summary = fileSummaryCache[file.path] || {};
      const frames = formatFrameCount(summary);
      const timeRange = formatTimeRange(summary);
      const wavelengths = formatWavelengthRange(summary);
      return (
        <div
          key={file.path}
          className={`explorer-tree-file-row ${file.supported || isProjectManifest(file) ? '' : 'is-disabled'}`}
          style={{ paddingLeft: `${treeFirst ? level * 10 + 13 : level * 14 + 28}px` }}
          onContextMenu={isV0Profile ? undefined : (event) => handleFileContextMenu(event, file)}
          title={treeFirst ? file.name : file.path}
        >
          <button
            className="explorer-tree-file-name"
            onDoubleClick={() => {
              if (String(file.suffix).toLowerCase() === '.dat') handlePreviewDat(file.path);
              else if (isProjectManifest(file)) treatmentContext?.onOpenManifest?.(file.path);
            }}
            onKeyDown={treeFirst ? event => {
              if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) handleFileContextMenu(event, file);
            } : undefined}
            disabled={(!treeFirst && !file.supported && !isProjectManifest(file)) || isBusy}
          >
            {file.name}
          </button>
          {!treeFirst && <><span className="explorer-file-meta explorer-file-size" title={`Size: ${formatFileSize(file.size_bytes)}`}>
            S:{formatFileSize(file.size_bytes)}
          </span>
          <span className="explorer-file-meta explorer-file-frames" title={`Frames: ${frames}`}>
            F:{frames}
          </span>
          <span className="explorer-file-meta explorer-file-time" title={`Time: ${timeRange}`}>
            T:{timeRange}
          </span>
          <span className="explorer-file-meta explorer-file-wavelength" title={`Wavelength: ${wavelengths}`}>
            W:{wavelengths}
          </span>
          </>}
        </div>
      );
    });

  const renderFolderTreeRows = (folders, level = 1) =>
    (folders || []).map((folder) => {
      const isExpanded = expandedFolders.has(folder.path);
      const cachedListing = folderTreeCache[folder.path];
      const isSelected = treeFirst ? selectedFolders.includes(folder.path) : session.folder_path === folder.path;
      const folderName = folder.name || pathName(folder.path);

      return (
        <React.Fragment key={folder.path}>
          <div
            className={`explorer-tree-row ${treeFirst ? 'with-folder-selection ' : ''}${isSelected ? 'is-selected' : ''}`}
            style={{ paddingLeft: `${level * (treeFirst ? 10 : 14)}px` }}
            onContextMenu={isV0Profile ? undefined : (event) => handleFolderContextMenu(event, folder)}
          >
            <button
              className="explorer-tree-toggle"
              onClick={() => handleFolderTreeToggle(folder.path)}
              aria-label={isExpanded ? 'Collapse folder' : 'Expand folder'}
            >
              {isExpanded ? 'v' : '>'}
            </button>
            {treeFirst && <input type="checkbox" className="explorer-folder-checkbox"
              aria-label={`Select ${folderName} for batch`} checked={isSelected}
              disabled={isBusy || isQueueLoading || treatmentQueue?.running}
              onChange={() => toggleBatchFolder(folder.path)} />}
            <button
              className="explorer-tree-name"
              onClick={(event) => handleTreeFolderClick(event, folder.path, folders.map(item => item.path))}
              aria-pressed={treeFirst ? isSelected : undefined}
              title={folder.path}
            >
              {folderName}
            </button>
          </div>
          {isExpanded && cachedListing && (
            <>
              {renderFolderTreeRows(cachedListing.folders, level + 1)}
              {renderFolderTreeFiles(cachedListing.files, level + 1)}
            </>
          )}
        </React.Fragment>
      );
    });

  const explorerRoot = sourceFolder;
  const explorerRootListing = folderTreeCache[explorerRoot] || { folders: [], files: [] };
  const refreshVisibleFolders = useCallback(async (isCurrent = () => true) => {
    const paths = [explorerRoot, ...Array.from(expandedFolders).filter(path =>
      path !== explorerRoot && folderPathChain(path, explorerRoot).length > 0)];
    await Promise.all(paths.filter(Boolean).map(async path => {
      const listing = await fetchFolderListing(treatmentSessionId, path);
      if (isCurrent()) cacheFolderListing(path, listing);
    }));
  }, [cacheFolderListing, expandedFolders, explorerRoot, treatmentSessionId]);

  useEffect(() => {
    if (!treeFirst || !explorerRoot) return undefined;
    let active = true;
    let timer;
    const poll = async () => {
      try { await refreshVisibleFolders(() => active); }
      catch (_error) { /* Keep the current listing during a transient read failure. */ }
      if (active) timer = window.setTimeout(poll, 5000);
    };
    timer = window.setTimeout(poll, 5000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [explorerRoot, refreshVisibleFolders, treeFirst]);
  const stitchDatFiles = useMemo(() => {
    const byPath = new Map();
    Object.values(folderTreeCache).forEach((listing) => {
      (listing?.files || []).forEach((file) => {
        if (String(file.suffix || '').toLowerCase() === '.dat') {
          byPath.set(file.path, file);
        }
      });
    });
    return sortStitchDatFiles(Array.from(byPath.values()));
  }, [folderTreeCache]);

  useEffect(() => {
    if (activeTab !== 'stitch' || !stitchFileA || !stitchFileB || stitchPreview || isBusy) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      refreshStitchPreview(false, true, true);
    }, 250);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, stitchFileA, stitchFileB, stitchPreview, isBusy]);

  useEffect(() => {
    if (!stitchFileA || !stitchFileB || stitchOutputName !== 'stitched_od.dat') {
      return;
    }
    setStitchOutputName(stitchedNameForPaths(stitchFileA, stitchFileB, stitchPreview?.stitched));
  }, [stitchFileA, stitchFileB, stitchOutputName, stitchPreview]);

  useEffect(() => {
    if (!stitchPreview || isBusy || !stitchFileA || !stitchFileB) {
      return undefined;
    }
    if (skipNextStitchCoefficientRefreshRef.current) {
      skipNextStitchCoefficientRefreshRef.current = false;
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      refreshStitchPreview(false, true, false);
    }, 600);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    stitchLeftScale,
    stitchLeftOffset,
    stitchRightScale,
    stitchRightOffset,
    stitchRightDelayShift,
    stitchRegions,
    stitchFileA,
    stitchFileB,
  ]);

  return {
    handleSelectionExport, handleV0QuickExport, handleCleaningTargetChange,
    handleCleaningThresholdChange, handleCleaningAction, handleStitchRegionsChange,
    refreshStitchPreview, handleRevertStitchFit, handleAddStitchRegion,
    handleRemoveStitchRegion, handleStitchOd, stitchOutputFolder, stitchOutputPath,
    stitchZoneMap, renderFolderTreeFiles, renderFolderTreeRows, explorerRoot,
    explorerRootListing, refreshVisibleFolders, stitchDatFiles,
  };
}
