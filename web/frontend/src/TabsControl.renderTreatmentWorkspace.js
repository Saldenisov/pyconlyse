import TreatmentError from './components/TreatmentError';
import SkanaPanel from './SkanaPanel';
import { spectralSum, spectralIndividual, vd2OdLabels, vd2OdModes } from './treatmentOdModes';
import { MIN_TREE_WIDTH } from "./TabsControl.PROFILE_PRESETS";
import { MAX_TREE_WIDTH } from "./TabsControl.PROFILE_PRESETS";
import { ParametersZone } from "./TabsControl.PROFILE_PRESETS";
import { pathName } from "./TabsControl.PROFILE_PRESETS";
import { formatFileSize } from "./TabsControl.PROFILE_PRESETS";
import { formatWavelengthRange } from "./TabsControl.PROFILE_PRESETS";
import { formatTimeRange } from "./TabsControl.PROFILE_PRESETS";
import { formatFrameCount } from "./TabsControl.PROFILE_PRESETS";
import { AssignedPaths } from "./TabsControl.roleSelectionStatus";
import { CleaningKineticsPreview } from "./TabsControl.roleSelectionStatus";
import { StitchHeatmap } from "./TabsControl.roleSelectionStatus";
import { StitchProfilePlot } from "./TabsControl.roleSelectionStatus";

export function renderTreatmentWorkspace({
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
}) {
  const odModes = vd2OdModes(session.exp_type, treatment.calc_modes || [], session.calc_mode);
  const missingReference = [spectralSum, spectralIndividual].includes(session.calc_mode) && !session.spectral_reference;
  const odModePicker = !isV0Profile && odModes.length > 1 && (
    <label className="treatment-experiment-type">Calculation mode
      <select value={session.calc_mode} disabled={isBusy || treatmentQueue?.running}
        onChange={event => handleConfigChange({ calc_mode: event.target.value })}>
        {odModes.map(mode => <option key={mode} value={mode}>{vd2OdLabels[mode]}</option>)}
      </select>
    </label>
  );
  const phaseOption = ['HIS', 'HIS+NOISE'].includes(session.exp_type) && (
    <div className="parameter-checkbox">
      <label>
        <input type="checkbox" checked={session.first_map_with_electrons}
          disabled={isBusy || treatmentQueue?.running}
          onChange={event => handleConfigChange({ first_map_with_electrons: event.target.checked })} />
        First frame with electrons
      </label>
    </div>
  );
  return (
    <div className={`tabs-control${treeFirst ? ' treatment-tree-first' : ''}`}>
      {treeFirst && <div className="treatment-tree-and-preview" style={{ '--tree-width': `${filesLayout.tree}px` }}>
        {sourceBrowser}
        <div className="treatment-tree-separator" role="separator" tabIndex={0} aria-label="Resize folders"
          aria-orientation="vertical" aria-valuemin={MIN_TREE_WIDTH} aria-valuemax={MAX_TREE_WIDTH} aria-valuenow={filesLayout.tree}
          onPointerDown={handleTreePointerDown} onPointerMove={handleTreePointerMove}
          onLostPointerCapture={finishTreeResize} onKeyDown={handleTreeResizeKey} />
        {preview}
      </div>}
      {detailFile && <div className="treatment-dialog-backdrop">
        <section role="dialog" aria-modal="true" aria-label="File details" className="treatment-manifest-dialog"
          onKeyDown={event => { if (event.key === 'Escape') setDetailFile(null); }}>
          <header><h2>{detailFile.name}</h2><button type="button" autoFocus aria-label="Close file details" onClick={() => setDetailFile(null)}>×</button></header>
          <dl className="treatment-file-details">
            <dt>Path</dt><dd>{detailFile.path}</dd>
            <dt>Size</dt><dd>{formatFileSize(detailFile.size_bytes)}</dd>
            {detailSummary && !detailSummary.loading && !detailSummary.error && <>
              <dt>Frames</dt><dd>{formatFrameCount(detailSummary)}</dd>
              <dt>Time</dt><dd>{formatTimeRange(detailSummary)}</dd>
              <dt>Wavelength</dt><dd>{formatWavelengthRange(detailSummary)}</dd>
            </>}
          </dl>
          {detailSummary?.loading && <p role="status">Reading file details…</p>}
          {detailSummary?.error && <TreatmentError message={detailSummary.error} />}
        </section>
      </div>}
      {!isV0Profile && (
        <div className="tabs">
          {treeFirst ? <label className="treatment-experiment-type">Experiment type
            <select aria-label="Experiment type" disabled={isBusy || treatmentQueue?.running}
              value={session.exp_type} onChange={event => handleConfigChange({ exp_type: event.target.value })}>
              {(treatment.exp_types || []).map(type => <option key={type} value={type}>{type}</option>)}
            </select>
          </label> : <button
            className={activeTab === 'files' ? 'is-active' : ''}
            onClick={() => setActiveTab('files')}
            aria-pressed={activeTab === 'files'}
          >
            {isStudioLayout ? 'Treatment' : 'Files'}
          </button>}
          {treeFirst && phaseOption}
          {treeFirst && odModePicker}
          {treeFirst && missingReference && session.ready_for_calc && <small>Draw a pre-pulse window on the ABS preview.</small>}
          {treeFirst && <button type="button" onClick={handleCalcAbs}
            disabled={isBusy || isQueueLoading || treatmentQueue?.running || !session.ready_for_calc || missingReference || Boolean(pendingCleaningPreview)}>
            Calculate OD
          </button>}
          <button
            className={activeTab === 'cleaning' ? 'is-active' : ''}
            onClick={() => setActiveTab(treeFirst && activeTab === 'cleaning' ? 'files' : 'cleaning')}
            aria-pressed={activeTab === 'cleaning'}
            disabled={isBusy || (treeFirst && treatmentQueue?.running)}
          >
            {treeFirst && activeTab === 'cleaning' ? 'Close Cleaning' : 'Cleaning'}
          </button>
          {treeFirst && <button type="button" className={activeTab === 'skana' ? 'is-active' : ''}
            onClick={() => setActiveTab(activeTab === 'skana' ? 'files' : 'skana')}
            aria-pressed={activeTab === 'skana'} disabled={isBusy}>
            SK-Ana
          </button>}
          <details className="treatment-more-tools"
            open={(treeFirst ? activeTab === 'stitch' : ['stitch', 'info', 'skana'].includes(activeTab)) || undefined}>
          <summary>{treeFirst ? 'Tools' : 'More tools'}</summary>
          <div>
          <button
            className={`secondary-tab ${activeTab === 'stitch' ? 'is-active' : ''}`}
            onClick={() => setActiveTab(treeFirst && activeTab === 'stitch' ? 'files' : 'stitch')}
            aria-pressed={activeTab === 'stitch'}
            disabled={isBusy}
          >
            Stitch
          </button>
          {!treeFirst && <><button
            className={activeTab === 'info' ? 'is-active' : ''}
            onClick={() => setActiveTab(treeFirst && activeTab === 'info' ? 'files' : 'info')}
            aria-pressed={activeTab === 'info'}
          >
            Info
          </button>
          <button type="button" className={activeTab === 'skana' ? 'is-active' : ''}
            onClick={() => setActiveTab('skana')} aria-pressed={activeTab === 'skana'} disabled={isBusy}>
            SK-Ana
          </button></>}
          </div>
          </details>
        </div>
      )}
      {treeFirst && !isV0Profile && <details className="treatment-manual-inputs">
        <summary>Manual inputs · {assignedCleaningTypes.length}/{assignableDataTypes.length}</summary>
        <p>For older projects, right-click each input file and choose its role
          {assignableDataTypes.length > 0 && ` (${assignableDataTypes.map(type => `Set ${type}`).join(', ')})`}.
          Then click Calculate OD.
          {assignableDataTypes.includes('ABS') && ' ABS is the absorption file.'}</p>
        <AssignedPaths session={session} />
      </details>}
      <TreatmentError message={error} />
      {treeFirst && treatmentQueue?.running && <p className="treatment-tree-status" role="status">
        {activeQueueJob?.label || 'Processing folders'} · {activeQueueJob?.phase || 'running'}
      </p>}
      {treeFirst && lastFolderJob?.status === 'failed' && (
        <TreatmentError message={`${lastFolderJob.label}: ${lastFolderJob.error || lastFolderJob.message}`} />
      )}
      {treeFirst && !treatmentQueue?.running && lastFolderJob?.status === 'completed' && (
        <p className="treatment-tree-status" role="status">{lastFolderJob.label} · completed</p>
      )}
                  {operationMessage && (
                  <p className={`treatment-operation-message ${isOperationRunning ? 'is-active' : ''}`}>
                    {isOperationRunning && (
                        <span className="treatment-operation-live">
                          <span className="treatment-operation-spinner" aria-hidden="true"></span>
                          <span>{busyElapsedSeconds}s</span>
                        </span>
                      )}
                      {operationMessage}
                    </p>
                  )}
      <div className="tab-content">
        {activeTab === 'skana' && <SkanaPanel />}
        {activeTab === 'files' && (
          <div
            className={`files-tab horizontal-layout ${isV0Profile ? 'is-v0-profile' : ''}`}
            ref={filesLayoutRef}
            style={isV0Profile || isStudioLayout ? undefined : { gridTemplateColumns: filesGridTemplate }}
          >
            {!treeFirst && sourceBrowser}
            {!isV0Profile && (
              <>
                {!treeFirst && <div
                  className="column-resizer roles-resizer"
                  role="separator"
                  aria-label="Resize processing controls"
                  onMouseDown={(event) => handleFilesColumnResizeStart('selected', event)}
                />}
                {(!treeFirst || queueJobs.length > 0) && <div className="zone raw-data-kinetics">
                  {!treeFirst && <>
                  <details className="treatment-assigned-inputs">
                    <summary>Input files · {Object.keys(session.paths || {}).length} assigned</summary>
                    <AssignedPaths session={session} />
                  </details>
                  <section className="treatment-step">
                    <h3>2 Cleaning</h3>
                    <button type="button" onClick={() => setActiveTab('cleaning')} disabled={isBusy || !assignedCleaningTypes.length}>Review cleaning</button>
                    <span>{pendingCleaningPreview ? 'Preview needs review' : 'Inspect and apply map selection'}</span>
                  </section>
                  <section className="treatment-step">
                    <h3>3 Calculate</h3>
                    {phaseOption}
                    {odModePicker}
                    <button onClick={handleCalcAbs} disabled={isBusy || !session.ready_for_calc || missingReference || Boolean(pendingCleaningPreview)}>
                      Calculate OD
                    </button>
                    <span>{session.result_ready ? 'Result ready to save' : session.ready_for_calc ? vd2OdLabels[session.calc_mode] : 'Assign the required input files'}</span>
                  </section>
                  {pendingCleaningPreview && (
                    <div className="treatment-cleaning-pending" role="status">
                      <strong>Cleaning preview not applied</strong>
                      <span>
                        {pendingCleaningPreview.stale
                          ? `${pendingCleaningPreview.dataType} has a backend cleaning preview. Preview again with the current thresholds before applying it.`
                          : `${pendingCleaningPreview.dataType} still uses its previous H5 map selection for processing.`}
                      </span>
                    </div>
                  )}
                  {savedResultPath && (
                    <div className="treatment-save-receipt" role="status">
                      <strong>Result saved</strong>
                      <code title={savedResultPath}>{savedResultPath}</code>
                      <button type="button" onClick={handleCopySavedResultPath}>
                        Copy path
                      </button>
                    </div>
                  )}
                  </>}
                  {isStudioLayout && (
                    <QueuePanel className="treatment-queue" aria-labelledby="treatment-queue-heading">
                      {treeFirst ? <summary id="treatment-queue-heading">Queue · {queueJobs.length} jobs</summary> : <div className="treatment-queue-heading">
                        <h4 id="treatment-queue-heading">Queue</h4>
                        <span className={`treatment-queue-status ${treatmentQueue?.running ? 'is-running' : ''}`}>
                          {treatmentQueue?.running ? 'Running' : 'Idle'}
                        </span>
                      </div>}
                      {!treeFirst && <details className="treatment-batch-options">
                        <summary>Batch options</summary>
                      <input
                        className="treatment-queue-label-input"
                        type="text"
                        aria-label="Queue label"
                        value={queueLabel}
                        onChange={(event) => setQueueLabel(event.target.value)}
                        placeholder={pathName(session.folder_path) || 'Sample name'}
                        disabled={isQueueLoading || isBusy}
                      />
                      <label
                        className="treatment-queue-option"
                        title={
                          queueSupportsCurrentRecipeCleaning
                            ? `Use current SAM thresholds for ${assignedCleaningTypes.join(', ')}.`
                            : 'Used for automatic cleaning when queuing a folder.'
                        }
                      >
                        <input
                          type="checkbox"
                          checked={queueApplyCleaning}
                          onChange={(event) => setQueueApplyCleaning(event.target.checked)}
                          disabled={isQueueLoading || isBusy}
                        />
                        SAM cleaning
                      </label>
                      <div className="treatment-queue-actions">
                        <button
                          type="button"
                          onClick={handleQueueEnqueue}
                          disabled={
                            isQueueLoading ||
                            isBusy ||
                            !session.ready_for_calc ||
                            !queueOutputConfigured ||
                            Boolean(pendingCleaningPreview)
                          }
                        >
                          Add recipe
                        </button>
                      </div>
                      </details>}
                      {!treatmentQueue?.running && Number(treatmentQueue?.pending_count || 0) > 0 && (
                        <button type="button" onClick={handleQueueRun} disabled={isQueueLoading || isBusy}>Resume queue</button>
                      )}
                      {queueJobs.length > 0 ? (
                        <ol className="treatment-queue-jobs" aria-live="polite">
                          {queueJobs.map((job) => (
                            <li key={job.job_id || `${job.label}-${job.created_at || ''}`} className={`is-${job.status || 'queued'}`}>
                              <div>
                                <strong>{job.label || job.recipe?.label || 'Treatment recipe'}</strong>
                                <span>{job.status || 'queued'} · {job.phase || 'queued'}</span>
                              </div>
                              {job.status === 'queued' && job.job_id && (
                                <button
                                  type="button"
                                  className="treatment-queue-remove"
                                  onClick={() => handleQueueRemove(job.job_id)}
                                  disabled={isQueueLoading}
                                >
                                  Remove
                                </button>
                              )}
                              {job.error && <p role="alert">{job.error}</p>}
                              {(job.message || job.preparation) && <details className="treatment-job-details">
                              <summary>Processing details</summary>
                              {job.message && <p>{job.message}</p>}
                              {Object.entries(
                                job.preparation?.folder_set?.cleaned || job.preparation?.cleaned || {}
                              ).map(([role, summary]) => {
                                const total = Number(summary?.original_measurements);
                                const kept = Number(summary?.cleaned_measurements);
                                const removed = Number(summary?.removed_measurements);
                                if (!Number.isFinite(total) || !Number.isFinite(kept) || !Number.isFinite(removed)) {
                                  return null;
                                }
                                return (
                                  <p key={`cleaned-${role}`}>
                                    {role}: {kept}/{total} maps retained · {removed} removed
                                    {total > 0 ? ` (${(removed / total * 100).toFixed(1)}%)` : ''}
                                  </p>
                                );
                              })}
                              {job.preparation?.folder_set?.map_policy === 'all_raw_maps' && (
                                <>
                                  <p>Uncleaned calculation · all raw maps used; saved H5 masks unchanged.</p>
                                  {Object.entries(job.preparation.folder_set.map_counts || {}).map(([role, counts]) => (
                                    <p key={`raw-${role}`}>
                                      {role}: {counts.used_count}/{counts.total_count} raw maps used
                                      {counts.stored_mask_included_count < counts.total_count
                                        ? ` · prior mask ${counts.stored_mask_included_count}/${counts.total_count} ignored`
                                        : ''}
                                    </p>
                                  ))}
                                </>
                              )}
                              </details>}
                              {(job.saved?.save_path || job.result?.save_path) && (
                                <code>{job.saved?.save_path || job.result?.save_path}</code>
                              )}
                            </li>
                          ))}
                        </ol>
                      ) : null}
                    </QueuePanel>
                  )}
                </div>}
              </>
            )}
            {!isV0Profile && (!treeFirst || session.result_ready) && (
              <>
                <div className="zone parameters">
                  <ParametersZone
                    session={session}
                    expTypes={treatment.exp_types}
                    dataTypes={assignableDataTypes}
                    calcModes={treatment.calc_modes}
                    draftSaveFolder={draftSaveFolder}
                    draftSaveFileName={draftSaveFileName}
                    onConfigChange={handleConfigChange}
                    onDraftSaveFolderChange={setDraftSaveFolder}
                    onDraftSaveFileNameChange={setDraftSaveFileName}
                    onCommitSaveFolder={handleCommitSaveFolder}
                    onCommitSaveFileName={handleCommitSaveFileName}
                    onReset={handleReset}
                    profileName={treatmentProfile}
                    layoutMode={treatmentLayoutMode}
                    onSave={handleSave}
                    onAverageNoise={handleAverageNoise}
                    canAverageNoise={canAverageNoise}
                    compact={treeFirst}
                    busy={isBusy || (treeFirst && treatmentQueue?.running)}
                  />
                </div>
                {!treeFirst && <div
                  className="column-resizer source-resizer"
                  role="separator"
                  aria-label="Resize source files"
                  onMouseDown={(event) => handleFilesColumnResizeStart('parameters', event)}
                />}
              </>
            )}
          </div>
        )}
        {activeTab === 'cleaning' && (
          <div className="tab-panel cleaning-tab">
            <div className="cleaning-main">
              <CleaningKineticsPreview view={cleaningView} />
              <div className="cleaning-controls">
                {isCleaningViewLoading && <p>Loading cleaning preview...</p>}
                <div role="group" aria-label="Cleaning input files" className="cleaning-role-switch">
                  {assignableDataTypes.map(dataType => {
                    const source = session.path_sources?.[dataType] || session.paths?.[dataType];
                    const label = { ABS: 'Absorption', BASE: 'Base', NOISE: 'Bruit / Noise' }[dataType] || dataType;
                    return <button key={dataType} type="button" aria-pressed={cleaningActiveDataType === dataType}
                      disabled={isBusy || !source} title={source || `${label}: no file assigned. Set the sample folder in Treatment.`}
                      onClick={() => handleCleaningTargetChange(dataType)}>
                      {label}<small>{source ? pathName(source) : 'Not assigned'}</small>
                    </button>;
                  })}
                </div>
                <details className="treatment-advanced-settings">
                <summary>Cleaning settings</summary>
                <div className="treatment-settings-fields">
                <label>
                  Clean File
                  <select
                    value={cleaningActiveDataType}
                    onChange={(event) => handleCleaningTargetChange(event.target.value)}
                    disabled={isBusy || assignedCleaningTypes.length === 0}
                  >
                    {assignedCleaningTypes.length === 0 && (
                      <option value="">No assigned files</option>
                    )}
                    {assignedCleaningTypes.map((dataType) => {
                      const sourcePath = session.path_sources?.[dataType] || session.paths?.[dataType] || '';
                      return (
                        <option key={dataType} value={dataType}>
                          {dataType} - {pathName(sourcePath)}
                        </option>
                      );
                    })}
                  </select>
                </label>
                <label>
                  SAM angle (°)
                  <input
                    type="number"
                    min="0.01"
                    step="0.1"
                    value={cleaningAngleThreshold}
                    onChange={(event) => handleCleaningThresholdChange('angle', event.target.value)}
                  />
                </label>
                <label>
                  Surface deviation (%)
                  <input
                    type="number"
                    min="0.01"
                    step="0.1"
                    value={cleaningSurfaceThreshold}
                    onChange={(event) => handleCleaningThresholdChange('surface', event.target.value)}
                  />
                </label>
                <button type="button" disabled={isBusy} onClick={() => {
                  handleCleaningThresholdChange('angle', '1');
                  handleCleaningThresholdChange('surface', '1');
                }}>Reset SAM defaults</button>
                <label>
                  Output H5 Name
                  <input
                    type="text"
                    value={cleaningOutputName}
                    readOnly
                    placeholder="source-name.h5"
                  />
                </label>
                </div>
                </details>
                {treeFirst && assignedCleaningTypes.length === 0 && !cleaningFolders.length && (
                  <p>Select a sample folder in the file tree to start cleaning.</p>
                )}
                <div className="cleaning-actions">
                  {treeFirst && assignedCleaningTypes.length === 0 && (
                    <button type="button"
                      disabled={isBusy || isQueueLoading || treatmentQueue?.running || !cleaningFolders.length}
                      onClick={() => handleQueueStandardFolder(cleaningFolders, {
                        label: 'Clean', convert: true, clean: true, calculate: false, returnToFiles: false,
                      })}>
                      Clean session
                    </button>
                  )}
                  <button onClick={() => handleCleaningAction('analyze')} disabled={isBusy || !cleaningActiveDataType}>
                    Preview cleaning
                  </button>
                  <button onClick={() => handleCleaningAction('reset')} disabled={isBusy}>
                    Reset preview
                  </button>
                  <details className="treatment-advanced-settings">
                    <summary>Recovery options</summary>
                    <button onClick={() => handleCleaningAction('restore')} disabled={isBusy || !String(cleaningSourcePath || '').toLowerCase().endsWith('.h5')}>
                      Restore raw-map selection
                    </button>
                  </details>
                  <button
                    onClick={() => handleCleaningAction('save')}
                    disabled={
                      isBusy ||
                      !canApplyCleaningPreview
                    }
                  >
                    Apply mask to H5
                  </button>
                </div>
                {pendingCleaningPreview && (
                  <p className="cleaning-preview-notice" role="status">
                    {pendingCleaningPreview.stale || pendingCleaningPreview.invalidated
                      ? `Preview for ${pendingCleaningPreview.dataType} must be refreshed with the current thresholds before it can be applied. Calculate OD remains blocked until you apply or reset it.`
                      : `Preview for ${pendingCleaningPreview.dataType} is not applied. Calculate OD is blocked until you apply its mask to H5 or reset the preview.`}
                  </p>
                )}
              </div>
            </div>
              {cleaningSummary && (
                <div className="cleaning-summary">
                  <p>
                    <strong>File:</strong> {cleaningSummary.file_path || session.active_data_type || 'n/a'}
                  </p>
                  <p>
                    <strong>This Pass:</strong> {cleaningSummary.cleaned_measurements} / {cleaningSummary.source_measurements}
                    {' | '}
                    <strong>Pass Retention:</strong> {cleaningSummary.pass_retention_rate.toFixed(1)}%
                  </p>
                  <p>
                    <strong>Overall Retained:</strong> {cleaningSummary.cleaned_measurements} / {cleaningSummary.original_measurements}
                    {' | '}
                    <strong>Removed:</strong> {cleaningSummary.removed_measurements}
                    {' | '}
                    <strong>Overall Retention:</strong> {cleaningSummary.retention_rate.toFixed(1)}%
                  </p>
                  <p>
                    <strong>Angle:</strong> {cleaningSummary.sam_angle_min.toFixed(3)} .. {cleaningSummary.sam_angle_max.toFixed(3)}
                    {' | '}
                    <strong>Mean:</strong> {cleaningSummary.sam_angle_mean.toFixed(3)}
                  </p>
                  {cleaningSummary.state_updated === false && cleaningSummary.warning && (
                    <p>{cleaningSummary.warning}</p>
                  )}
                  {cleaningSummary.output_path && (
                    <p>
                      <strong>Saved:</strong> {cleaningSummary.output_path}
                    </p>
                  )}
                </div>
              )}
          </div>
        )}
        {activeTab === 'stitch' && (
          <div className="tab-panel stitch-tab">
            <div className="stitch-controls">
              <div className="stitch-control-grid stitch-control-grid-wide">
                <label>
                  OD Map A
                  <input
                    list="stitch-dat-files"
                    type="text"
                    value={stitchFileA}
                    onChange={(event) => setStitchFileA(event.target.value)}
                    placeholder="smb://.../first.dat"
                  />
                </label>
                <label>
                  OD Map B
                  <input
                    list="stitch-dat-files"
                    type="text"
                    value={stitchFileB}
                    onChange={(event) => setStitchFileB(event.target.value)}
                    placeholder="smb://.../second.dat"
                  />
                </label>
              </div>
              <datalist id="stitch-dat-files">
                {stitchDatFiles.map((file) => (
                  <option key={file.path} value={file.path}>
                    {file.name}
                  </option>
                ))}
              </datalist>
              <div className="stitch-control-grid">
                <label>
                  Left Scale
                  <input type="number" step="0.0001" value={stitchLeftScale} onChange={(event) => setStitchLeftScale(event.target.value)} />
                </label>
                <label>
                  Left Offset
                  <input type="number" step="0.0001" value={stitchLeftOffset} onChange={(event) => setStitchLeftOffset(event.target.value)} />
                </label>
                <label>
                  Right Scale
                  <input type="number" step="0.0001" value={stitchRightScale} onChange={(event) => setStitchRightScale(event.target.value)} />
                </label>
                <label>
                  Right Offset
                  <input type="number" step="0.0001" value={stitchRightOffset} onChange={(event) => setStitchRightOffset(event.target.value)} />
                </label>
                <label>
                  Right Y Shift px
                  <input type="number" step="1" value={stitchRightDelayShift} onChange={(event) => setStitchRightDelayShift(event.target.value)} />
                </label>
              </div>
              <div className="stitch-control-grid">
                <label>
                  Left W Start
                  <input type="number" step="any" value={stitchLeftWavelengthStart} onChange={(event) => setStitchLeftWavelengthStart(event.target.value)} />
                </label>
                <label>
                  Left W End
                  <input type="number" step="any" value={stitchLeftWavelengthEnd} onChange={(event) => setStitchLeftWavelengthEnd(event.target.value)} />
                </label>
                <label>
                  Right W Start
                  <input type="number" step="any" value={stitchRightWavelengthStart} onChange={(event) => setStitchRightWavelengthStart(event.target.value)} />
                </label>
                <label>
                  Right W End
                  <input type="number" step="any" value={stitchRightWavelengthEnd} onChange={(event) => setStitchRightWavelengthEnd(event.target.value)} />
                </label>
              </div>
              <div className="stitch-control-grid">
                <label>
                  T Start
                  <input type="number" step="any" value={stitchRegionStart} onChange={(event) => setStitchRegionStart(event.target.value)} />
                </label>
                <label>
                  T End
                  <input type="number" step="any" value={stitchRegionEnd} onChange={(event) => setStitchRegionEnd(event.target.value)} />
                </label>
              </div>
              <div className="stitch-control-grid">
                <button onClick={handleAddStitchRegion} disabled={isBusy}>
                  Add Region
                </button>
                <button onClick={() => refreshStitchPreview(true)} disabled={isBusy || !stitchFileA || !stitchFileB}>
                  Fit Right
                </button>
                <button onClick={handleRevertStitchFit} disabled={isBusy || !stitchPreview || !stitchFileA || !stitchFileB}>
                  Revert
                </button>
              </div>
              {stitchRegions.length > 0 && (
                <div className="stitch-region-list">
                  {stitchRegions.map((region, index) => (
                    <button key={`${region.left_wavelength_start}-${region.right_wavelength_start}-${region.delay_start}-${index}`} onClick={() => handleRemoveStitchRegion(index)}>
                      {region.label}: L {Number(region.left_wavelength_start).toFixed(1)}-{Number(region.left_wavelength_end).toFixed(1)}, R {Number(region.right_wavelength_start).toFixed(1)}-{Number(region.right_wavelength_end).toFixed(1)}, T {Number(region.delay_start).toFixed(3)}-{Number(region.delay_end).toFixed(3)} x
                    </button>
                  ))}
                </div>
              )}
              <label>
                Output DAT Name
                <input
                  type="text"
                  value={stitchOutputName}
                  onChange={(event) => setStitchOutputName(event.target.value)}
                  placeholder="stitched_od.dat"
                />
              </label>
              <div className="stitch-actions">
                <button onClick={() => refreshStitchPreview(false)} disabled={isBusy || !stitchFileA || !stitchFileB}>
                  Load Pair
                </button>
                <button onClick={handleStitchOd} disabled={isBusy || !stitchPreview || !stitchFileA || !stitchFileB}>
                  OK and Save
                </button>
              </div>
              <div className="stitch-summary">
                <p>
                  <strong>Save Folder:</strong> {stitchOutputFolder || 'Not set'}
                </p>
                <p>
                  <strong>Output Path:</strong> {stitchOutputPath || 'Not set'}
                </p>
                <p>
                  <strong>Visible DAT files:</strong> {stitchDatFiles.length}
                </p>
                {stitchPreview && (
                  <>
                    <p>
                      <strong>Axis Overlap:</strong> {(stitchPreview.axis_overlap_range || stitchPreview.overlap_range)?.[0]}-{(stitchPreview.axis_overlap_range || stitchPreview.overlap_range)?.[1]} nm
                    </p>
                    <p>
                      <strong>Trusted Overlap:</strong> {stitchPreview.overlap_range?.[0]}-{stitchPreview.overlap_range?.[1]} nm
                    </p>
                  </>
                )}
                {stitchPreview?.fit && (
                  <p>
                    <strong>Fit:</strong> scale {Number(stitchPreview.fit.right_scale).toPrecision(6)}
                    {Number.isFinite(stitchPreview.fit.correlation)
                      ? ` | corr ${Number(stitchPreview.fit.correlation).toFixed(3)}`
                      : ''}
                    {Number.isFinite(stitchPreview.fit.relative_rmse)
                      ? ` | rel RMSE ${Number(stitchPreview.fit.relative_rmse).toFixed(3)}`
                      : ''}
                  </p>
                )}
                <p>
                  <strong>Right Y Shift:</strong> {Number.parseInt(stitchRightDelayShift, 10) || 0} px
                </p>
                {stitchSummary && (
                  <>
                    <p>
                      <strong>Saved:</strong> {stitchSummary.output_path}
                    </p>
                    {stitchSummary.manifest_path && (
                      <p>
                        <strong>Manifest:</strong> {stitchSummary.manifest_path}
                      </p>
                    )}
                    <p>
                      <strong>W:</strong> {Number(stitchSummary.wavelength_min).toFixed(1)}-{Number(stitchSummary.wavelength_max).toFixed(1)} nm
                      {' | '}
                      <strong>Delays:</strong> {stitchSummary.timedelays}
                      {' | '}
                      <strong>Rows:</strong> {stitchSummary.rows}
                    </p>
                  </>
                )}
                {!stitchSummary && (
                  <p>
                    <strong>Status:</strong> Not saved yet
                  </p>
                )}
              </div>
            </div>
            <div className="stitch-preview">
              {stitchPreview ? (
                <div className="stitch-map-grid">
                  <StitchHeatmap
                    map={stitchPreview.left}
                    title="Left / Short Wavelengths"
                    overlapRange={stitchPreview.axis_overlap_range || stitchPreview.overlap_range}
                    regions={stitchRegions}
                    regionSide="left"
                    onRegionsChange={handleStitchRegionsChange}
                  />
                  <StitchHeatmap
                    map={stitchPreview.right}
                    title="Right / Long Wavelengths"
                    overlapRange={stitchPreview.axis_overlap_range || stitchPreview.overlap_range}
                    regions={stitchRegions}
                    regionSide="right"
                    onRegionsChange={handleStitchRegionsChange}
                  />
                  <StitchProfilePlot
                    spectra={stitchPreview.spectra}
                    title="Selected Profiles"
                    mode="selected"
                  />
                  <StitchProfilePlot
                    spectra={stitchPreview.spectra}
                    title="Overlap Fit Profiles"
                    mode="overlap"
                  />
                  <StitchHeatmap
                    map={stitchZoneMap || stitchPreview.stitched}
                    title="Stitching Zone"
                    overlapRange={null}
                    regions={[]}
                  />
                  <StitchHeatmap
                    map={stitchPreview.stitched}
                    title="Stitched Map"
                    overlapRange={null}
                    regions={[]}
                  />
                </div>
              ) : (
                <div className="stitch-preview-empty">Load pair to preview maps and spectra.</div>
              )}
            </div>
          </div>
        )}
        {!treeFirst && activeTab === 'info' && (
          <div className="tab-panel">
            <p>
              <strong>Allowed Root:</strong> {treatment.allowed_root}
            </p>
            <p>
              <strong>Root Available:</strong>{' '}
              {treatment.allowed_root_exists ? 'Yes' : 'No'}
            </p>
            <p>
              <strong>Save Target:</strong>{' '}
              {session.save_folder && session.save_file_name
                ? `${session.save_folder}/${session.save_file_name}`
                : 'Not set'}
            </p>
          </div>
        )}
        {activeTab === 'selection' && (
          <div className="tab-panel">
            <p>
              <strong>Profile:</strong> {treatmentProfile}
              {' | '}
              {treatmentProfile === 'V0'
                ? 'Preset uses HIS+NOISE for legacy V0 flow.'
                : 'Preset uses ABS+BASE+NOISE for VD2 flow.'}
            </p>
            <p>
              Export averaged traces from the active file and current map using
              desktop-style ranges such as <code>500+-10; 600+-5</code>.
            </p>
            <p>
              <strong>Active Data:</strong> {session.active_data_type || 'Not selected'}
              {' | '}
              <strong>Map:</strong> {session.map_index || 0}
            </p>
            {treatmentProfile === 'V0' && (
              <div style={{ marginBottom: '12px' }}>
                <button onClick={handleV0QuickExport} disabled={isBusy}>
                  Quick Export Both (V0)
                </button>
              </div>
            )}
            <div style={{ display: 'grid', gap: '12px', maxWidth: '720px' }}>
              <label>
                Kinetics Ranges
                <input
                  type="text"
                  value={draftKineticsRanges}
                  onChange={(event) => setDraftKineticsRanges(event.target.value)}
                  placeholder="500+-10; 600+-5"
                  style={{ width: '100%' }}
                />
              </label>
              <button
                onClick={() => handleSelectionExport('kinetics')}
                disabled={isBusy}
              >
                Get Kinetics
              </button>
              <label>
                Spectra Ranges
                <input
                  type="text"
                  value={draftSpectraRanges}
                  onChange={(event) => setDraftSpectraRanges(event.target.value)}
                  placeholder="1+-0.5; 3+-1"
                  style={{ width: '100%' }}
                />
              </label>
              <button
                onClick={() => handleSelectionExport('spectra')}
                disabled={isBusy}
              >
                Get Spectra
              </button>
              {selectionMessage && <p>{selectionMessage}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
