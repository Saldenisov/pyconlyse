import { isProjectManifest } from "./TabsControl.PROFILE_PRESETS";
import { pathName } from "./TabsControl.PROFILE_PRESETS";

export function renderTreatmentSources({
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
}) {
  const dataLocation = (
      <details className="treatment-source-settings">
        <summary>Data location</summary>
      <div className="data-root-control">
        <label>
          Data Root
          <input
            type="text"
            value={draftAllowedRoot}
            onChange={(event) => setDraftAllowedRoot(event.target.value)}
            onBlur={handleAllowedRootChange}
            onKeyDown={handleAllowedRootKeyDown}
            placeholder={treatment.allowed_root || 'E:/Data/DATA_VD2'}
          />
        </label>
      </div>
      </details>
  );
  const sourceBrowser = (
    <div className="zone files-folder">
      {!treeFirst && <>
        {isStudioLayout ? <div className="zone-heading"><h3>1 Source</h3></div> : <h3>Files</h3>}
        <code className="treatment-selected-folder" title={explorerRoot}>{explorerRoot || 'No folder selected'}</code>
        {dataLocation}
      </>}
      <div className="folder-selection-header">
        <button onClick={handleFolderTreeOpen} disabled={!explorerRoot || (treeFirst && (isQueueLoading || treatmentQueue?.running))}>
          Select Folder
        </button>
        {treeFirst && <button type="button" aria-label="Refresh tree" title="Refresh tree"
          onClick={() => refreshVisibleFolders().catch(cause => setError(cause.message))}>↻</button>}
        {treeFirst && selectedFolders.length > 0 && (
          <button type="button" aria-label={`Run selected folders (${selectedFolders.length})`}
            title="Calculate and save the selected measurement folders"
            disabled={isBusy || isQueueLoading || treatmentQueue?.running}
            onClick={() => handleQueueStandardFolder(selectedFolders, {
              label: 'Calculate & save', convert: false, clean: false, calculate: true,
            })}>
            Run ({selectedFolders.length})
          </button>
        )}
        {!treeFirst && !isV0Profile && <button type="button" disabled={!explorerRoot || isSelectingFolderRoot || isBusy || isQueueLoading || treatmentQueue?.running}
          onClick={handleLoadFolderInputs}>
          Load folder inputs
        </button>}
        {!treeFirst && !isV0Profile && <button type="button" onClick={() => treatmentContext?.onOpenManifest?.('')}
          disabled={isBusy || !treatmentContext?.onOpenManifest}>Open manifest…</button>}
      </div>
      {treeFirst && isSelectingFolderRoot && <small role="status">Open a folder by name, or tick folders to run together.</small>}
      {isFolderTreeOpen && (
      <div className="explorer-panel">
        <div className="explorer-tree" role="tree" aria-label="Files" onKeyDown={treeFirst ? event => {
          if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
            event.preventDefault();
            setSelectedFolders(explorerRootListing.folders.map(folder => folder.path));
          }
        } : undefined}>
          <div
            className={`explorer-tree-row ${
                  (treeFirst ? selectedFolders.includes(explorerRoot) : session.folder_path === explorerRoot) ? 'is-selected' : ''
            }`}
            onContextMenu={
              isV0Profile
                ? undefined
                : (event) =>
                    handleFolderContextMenu(event, {
                      name: pathName(explorerRoot) || explorerRoot,
                      path: explorerRoot,
                    })
            }
          >
            <button
              className="explorer-tree-toggle"
              onClick={() => handleFolderTreeToggle(explorerRoot)}
              aria-label="Expand root"
            >
              {expandedFolders.has(explorerRoot) ? 'v' : '>'}
            </button>
            <button
              className="explorer-tree-name"
              onClick={event => handleTreeFolderClick(event, explorerRoot, [explorerRoot])}
              title={explorerRoot}
            >
              {pathName(explorerRoot) || explorerRoot}
            </button>
          </div>
          {(expandedFolders.has(explorerRoot) || session.folder_path === explorerRoot) &&
            (
              <>
                {renderFolderTreeRows(explorerRootListing.folders, 1)}
                {renderFolderTreeFiles(explorerRootListing.files, 1)}
              </>
            )}
        </div>
      </div>
      )}
      {!isV0Profile && fileContextMenu && (
        <div
          className="file-context-menu"
          style={{ left: fileContextMenu.x, top: fileContextMenu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          {treeFirst && <button type="button" onClick={() => {
            const file = fileContextMenu.file;
            setDetailFile(file);
            setFileContextMenu(null);
            loadFileSummary(file);
          }}>Details</button>}
          {isProjectManifest(fileContextMenu.file) ? <button type="button" onClick={() => {
            treatmentContext?.onOpenManifest?.(fileContextMenu.file.path); setFileContextMenu(null);
          }}>Calculate according to manifest…</button> : fileContextMenu.file.supported && <>
          {String(fileContextMenu.file.suffix).toLowerCase() === '.dat' && <button type="button"
            onClick={() => handlePreviewDat(fileContextMenu.file.path)}>Open in Preview</button>}
          {(treeFirst ? assignableDataTypes : ['ABS', 'BASE', 'NOISE']).map((dataType) => (
            <button
              key={dataType}
              onClick={() => handleAssignFile(fileContextMenu.file.path, dataType)}
                disabled={isBusy || (treeFirst && treatmentQueue?.running)}
            >
              Set {dataType}
            </button>
          ))}
          <div className="file-context-menu-separator" />
          <button
            onClick={() => handleCompressFile(fileContextMenu.file.path)}
              disabled={isBusy || (treeFirst && treatmentQueue?.running)}
          >
            Convert/Compress
          </button>
          {String(fileContextMenu.file.suffix || '').toLowerCase() === '.dat' && (
            <>
              <div className="file-context-menu-separator" />
              <div className="file-context-submenu">
                <button type="button" disabled={isBusy}>
                  Stitch
                </button>
                <div className="file-context-submenu-panel">
                  <button
                    onClick={() => handleSetStitchFile(fileContextMenu.file.path, 'A')}
                    disabled={isBusy}
                  >
                    Stitch A
                  </button>
                  <button
                    onClick={() => handleSetStitchFile(fileContextMenu.file.path, 'B')}
                    disabled={isBusy}
                  >
                    Stitch B
                  </button>
                </div>
              </div>
            </>
          )}
          </>}
        </div>
      )}
      {!isV0Profile && folderContextMenu && (
        <div
          className="file-context-menu"
          style={{ left: folderContextMenu.x, top: folderContextMenu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          {folderContextMenu.paths.length > 1 && <p className="treatment-menu-count">{folderContextMenu.paths.length} folders</p>}
          <button type="button" disabled={isBusy || folderContextMenu.paths.length !== 1} onClick={() => handleManifestFolder(folderContextMenu.folder.path)}>
            Calculate according to manifest…
          </button>
          {treeFirst ? [
            ['Set', false, false, false],
            ['Convert', true, false, false],
            ['Clean', true, true, false],
            ['Calculate & save', false, false, true],
            ['Clean, calculate & save', true, true, true],
          ].map(([label, convert, clean, calculate]) => (
            <button key={label} type="button" disabled={isBusy || isQueueLoading || treatmentQueue?.running}
              onClick={() => handleQueueStandardFolder(folderContextMenu.paths, { label, convert, clean, calculate })}>
              {label}
            </button>
          )) : <>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert',
              convert: true,
              clean: false,
              calculate: false,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert/Clean',
              convert: true,
              clean: true,
              calculate: false,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert/Clean
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert/Calc (all maps)',
              convert: true,
              clean: false,
              calculate: true,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert/Calc (all maps)
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert/Clean/Calc',
              convert: true,
              clean: true,
              calculate: true,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert/Clean/Calc
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set',
              convert: false,
              clean: false,
              calculate: false,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set
          </button>
          </>}
        </div>
      )}
    </div>
  );
  const detailSummary = detailFile && fileSummaryCache[detailFile.path];
  const QueuePanel = treeFirst ? 'details' : 'section';
  const activeQueueJob = queueJobs.find(job => job.status === 'running');
  const lastFolderJob = [...queueJobs].reverse().find(job => job.recipe?.kind === 'standard_folder_set');

  return {
    sourceBrowser, detailSummary, QueuePanel, activeQueueJob, lastFolderJob,
  };
}
