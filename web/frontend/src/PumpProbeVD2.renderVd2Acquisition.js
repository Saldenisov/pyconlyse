import VD2TranslationStages, { VD2SampleHolder } from './components/VD2TranslationStages';
import VD2PDUControl from './components/VD2PDUControl';
import VD2RoiEditor from './components/VD2RoiEditor';
import VD2LiveAverage from './components/VD2LiveAverage';
import VD2PairedCapture from './components/VD2PairedCapture';
import VD2ReadDiagnostics from './components/VD2ReadDiagnostics';
import FrameDisplayRate from './components/FrameDisplayRate';
import { alignmentRegionFromBounds } from './vd2RoiMath';
import { AlignmentKinetics, AlignmentRegion, VD2AlignmentMagnets } from './components/VD2Alignment';
import { CARDS } from "./PumpProbeVD2.API_BASE";
import { ParameterCard } from "./PumpProbeVD2.API_BASE";
import { ROI_TOOLS } from "./PumpProbeVD2.API_BASE";
import { clamp } from "./PumpProbeVD2.API_BASE";
import { LutControl } from "./PumpProbeVD2.API_BASE";
import { roiBounds } from "./PumpProbeVD2.API_BASE";
import { roiColor } from "./PumpProbeVD2.API_BASE";
import { updateRoisFromBounds } from "./PumpProbeVD2.API_BASE";
import { RoiProfiles } from "./PumpProbeVD2.API_BASE";
import { Vd2PhaseProtocol } from "./PumpProbeVD2.API_BASE";
import { Vd2PhaseDialog } from "./PumpProbeVD2.API_BASE";
import { Vd2RepeatDialog } from "./PumpProbeVD2.API_BASE";
import { Vd2ErrorTray } from "./PumpProbeVD2.Vd2ErrorTray";

export function renderVd2Acquisition({
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
}) {
  return (
    <main className="vd2-page">
      <header className="vd2-header" aria-label="VD2 header">
        <div>
          <h1>Pump probe VD2</h1>
          <p className="vd2-subtitle">Streak-camera control and timing configuration</p>
        </div>
        <div className="vd2-statuses" aria-live="polite">
          {awaitingCameraState ? <span className="vd2-status">Camera status deferred</span> : <>
            <span className={`vd2-status ${statusClass}`}>Tango {state?.state || 'OFFLINE'}</span>
            <span className={`vd2-status ${state?.connected ? 'online' : 'offline'}`}>RemoteEx {state?.connected ? 'connected' : 'disconnected'}</span>
            <span className={`vd2-status ${state?.connected && state?.application_running ? 'online' : 'offline'}`}>HPD-TA {!state?.connected ? 'status unknown' : state?.application_running ? 'running' : 'stopped'}</span>
          </>}
        </div>
        <div className="vd2-header-actions">
          <button type="button" onClick={refreshAll} disabled={busy || protocolHardwareActive}>Refresh</button>
        </div>
      </header>

      <Vd2ErrorTray
        errors={errors}
        activeErrorId={activeErrorId}
        onPrevious={showPreviousError}
        onNext={showNextError}
        onCopy={copyError}
        onDismiss={dismissError}
        onClear={clearErrors}
      />

      {state?.status && <div className="vd2-startup-error" role="alert">{state.status}</div>}
      {acquisitionReadError && (acquisitionReadDeferred
        ? <div className="vd2-read-deferred" role="status">Acquisition status check deferred: another VD2 operation is in progress.</div>
        : <div className="vd2-startup-error" role="alert">Acquisition status unavailable: {acquisitionReadError}</div>)}
      {state && !awaitingCameraState && !state.connected && <div className="vd2-startup-error" role="alert">RemoteEx control link is disconnected. HPD-TA may still be running; its acquisition state is unknown. Reconnect before sending camera commands.</div>}
      <VD2ReadDiagnostics issues={readIssues} />
      {(alignmentMemoryError||roiMemoryError)&&<small role="alert">{alignmentMemoryError||roiMemoryError}</small>}

      <div className="vd2-tabs" role="tablist" aria-label="VD2 control views">
        <button type="button" role="tab" aria-selected={activeTab === 'acquisition'} className={activeTab === 'acquisition' ? 'is-active' : ''} onClick={() => setActiveTab('acquisition')}>Acquisition</button>
        <button type="button" role="tab" aria-selected={activeTab === 'hardware'} className={activeTab === 'hardware' ? 'is-active' : ''} onClick={() => setActiveTab('hardware')}>Hardware setup</button>
        <button type="button" role="tab" aria-selected={activeTab === 'delay-lines'} className={activeTab === 'delay-lines' ? 'is-active' : ''} onClick={() => setActiveTab('delay-lines')}>Delay Lines</button>
        <button type="button" role="tab" aria-selected={activeTab === 'pdu'} className={activeTab === 'pdu' ? 'is-active' : ''} onClick={() => setActiveTab('pdu')}>PDU</button>
        <button type="button" role="tab" aria-selected={activeTab === 'alignment'} className={activeTab === 'alignment' ? 'is-active' : ''} onClick={() => setActiveTab('alignment')}>Alignment</button>
      </div>

      {['acquisition', 'alignment'].includes(activeTab) && (
        <div className={`vd2-acquisition-workspace ${imageRight ? 'is-image-right' : ''} ${activeTab === 'alignment' ? 'is-alignment' : ''}`}
          style={{ '--vd2-image-width': `${imageWidth}px` }}
          onDragOver={event => { if (dragPanel) event.preventDefault(); }}
          onDrop={event => { if (dragPanel) { event.preventDefault(); const box = event.currentTarget.getBoundingClientRect(); setImageRight(event.clientX > box.left + box.width / 2); setDragPanel(false); } }}>
          <div className="vd2-acquisition-sidebar">
            {activeTab === 'alignment' ? <>
              <AlignmentRegion region={alignmentRegion} onChange={(key, value) => setAlignmentRegion(current => ({ ...current, [key]: value }))}
                calibrationUpdating={calibrationUpdating} calibrated={Boolean(calibration) && previewAvailable}
                calibrationError={previewStream === 'no_valid_image' ? '' : calibrationError || preview?.calibration_error || ''} />
              <VD2LiveAverage onReadError={setLiveAverageReadError} onReadback={setAlignmentAverage} disabled={alignmentControlsBlocked}>
                <button type="button" onClick={() => runCommand('StartLive')} disabled={alignmentControlsBlocked || !acquisitionIdle}>Live</button>
                <button type="button" className="vd2-stop" onClick={() => runCommand('StopAcquisition')} disabled={alignmentControlsBlocked || acquisitionIdle}>Stop</button>
              </VD2LiveAverage>
              <VD2AlignmentMagnets measurements={alignmentMeasurements} live={state?.acquisition_status === 'busy' && String(state?.acquisition_mode).toLowerCase() === 'live'} />
            </> : <>
            <section className="vd2-control-strip" aria-label="Acquisition controls">
              <div className="vd2-acquisition-actions">
                <button
                  type="button"
                  onClick={() => runCommand('StartLive')}
                  disabled={busy || protocolHardwareActive || !state?.application_running || state?.remoteex_status === 'starting'}
                >
                  Live
                </button>
                <button type="button" onClick={() => runCommand('AcquireSingle')} disabled={busy || protocolHardwareActive}>Single</button>
                <button type="button" onClick={() => runCommand('Acquire')} disabled={busy || protocolHardwareActive}>Acquire</button>
                <button type="button" onClick={() => runCommand('StartSequence')} disabled={busy || protocolHardwareActive}>Sequence</button>
                <button type="button" className="vd2-stop" onClick={() => runCommand('StopAcquisition')} disabled={busy}>Stop</button>
              </div>
              <VD2LiveAverage onReadError={setLiveAverageReadError} liveActive={state?.remoteex_status === 'busy'} disabled={busy || !state?.connected || !state?.application_running || protocolHardwareActive}>
                <label><span>Frames / HIS</span><input aria-label="Frames / HIS" type="number" min="1" max="100000" step="1" value={protocolSettings.framesPerHis}
                  disabled={!serverWorkspace.ready || busy || protocolStarting || Boolean(repeatConflict) || protocolHardwareActive} onChange={event => updateProtocolSetting('framesPerHis', event.target.value)} /></label>
              </VD2LiveAverage>
            </section>
            <Vd2PhaseProtocol
              protocol={protocol}
              project={project}
              settings={protocolSettings}
              disabled={!serverWorkspace.ready || busy || protocolStarting || Boolean(repeatConflict) || !state?.application_running || state?.remoteex_status === 'busy'}
              settingsDisabled={!serverWorkspace.ready || busy || protocolStarting || Boolean(repeatConflict) || Boolean(preparedPhase) || Boolean(guidedRun || guidedChoice)}
              serverWorkspace={serverWorkspace}
              onChange={updateProtocolSetting}
              onPhaseClick={prepareProtocolPhase}
              onPhaseDoubleClick={startProtocolPhaseImmediately}
              onMeasure={chooseGuidedRun}
              measurementUnavailable={!project}
              measuring={Boolean(guidedRun || guidedChoice)}
              measurementMessage={guidedMessage}
              sampleHolder={<VD2SampleHolder disabled={busy || protocolStarting || protocolHardwareActive} />}
            />
            <VD2PairedCapture available={protocol?.paired_available} run={protocol?.paired} settings={protocolSettings}
              disabled={!serverWorkspace.ready || busy || protocolStarting || protocolHardwareActive
                || Boolean(preparedPhase || guidedRun || guidedChoice) || !acquisitionIdle}
              roi={rois.find(roi => roi.id === selectedRoiId)} preview={preview} onUpdate={updatePairedCapture}
              onStop={() => runCommand('StopAcquisition')} />
            {projectError && <p role="alert" className="vd2-stage-error">{projectError}</p>}
            <section className="vd2-roi-analysis" aria-label="ROI analysis">
              <aside className="vd2-roi-list">
                <header><strong>Regions</strong><span>{rois.length}</span></header>
                <label className="vd2-roi-link"><input type="checkbox" checked={linkRois} onChange={event => setLinkRois(event.target.checked)} />Move together</label>
                {rois.length === 0 && <p>No regions</p>}
                {rois.map((roi, index) => {
                  const definition = ROI_TOOLS[roi.type];
                  return (
                    <div className={`vd2-roi-row ${roi.id === selectedRoiId ? 'is-selected' : ''}`} key={roi.id}>
                      <button type="button" className="vd2-roi-select" onClick={() => setSelectedRoiId(roi.id)}>
                        <i style={{ background: roiColor(index) }} />
                        <span>{index + 1}. {definition.label}</span>
                      </button>
                      <button type="button" className="vd2-roi-remove" title={`Remove ROI ${index + 1}`} aria-label={`Remove ROI ${index + 1}`} onClick={() => removeRoi(roi.id)}>×</button>
                    </div>
                  );
                })}
              </aside>
              <RoiProfiles preview={preview} rois={rois} selectedId={selectedRoiId} onSelect={setSelectedRoiId} />
            </section>
            </>}
          </div>

        <div className="vd2-panel-splitter" role="separator" aria-label="Resize live image" aria-orientation="vertical" tabIndex="0"
          aria-valuemin="320" aria-valuemax="760" aria-valuenow={imageWidth} onPointerDown={resizeImage}
          onKeyDown={event => { if (['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); setImageWidth(clamp(imageWidth + (event.key === 'ArrowRight' ? 20 : -20) * (imageRight ? -1 : 1), 320, 760)); } }} />
        <div className="vd2-image-column">
        <section className="vd2-preview" aria-label="Live streak-camera preview">
          <LutControl
            palette={lutPalette}
            range={lutRange}
            preview={preview}
            onPaletteChange={setLutPalette}
            onRangeChange={updateLutRange}
            onAutoscale={autoscaleLut}
          />
          <header>
            <div>
              <h2 draggable onDragStart={() => setDragPanel(true)} onDragEnd={() => setDragPanel(false)} title="Drag image panel to either side">↔ Live image</h2>
              <p>C13440-20CU display frame</p>
            </div>
            <div className="vd2-preview-meta">
              <span>{preview ? `${preview.width} x ${preview.height}` : 'Waiting for frame'}</span>
              <span>{previewStream === 'no_valid_image' ? (preview ? 'No current image · Previous frame' : 'Waiting for first frame')
                : protocolSaving ? protocol.status : state?.acquisition_status === 'busy' || previewStream === 'acquiring' ? 'Acquiring' : 'Last frame'}</span>
              {preview && <span>{preview.minimum} - {preview.maximum}</span>}
              <button type="button" onClick={() => { previewPaused.current = false; setPreviewEnabled(true); loadPreview(); }} disabled={busy}>Refresh frame</button>
              <button type="button" onClick={() => setImageRight(current => !current)} aria-label="Swap image and controls" title="Move image to the other side">↔</button>
            </div>
          </header>
          {previewError && <div className="vd2-preview-error" role="alert">{previewError}</div>}
          {!previewError && previewStream === 'no_valid_image' && <div className="vd2-preview-status" role="status">
            {state?.acquisition_status === 'busy' ? 'Waiting for a camera image.' : 'No image available yet. Start Live or acquire a frame.'}
          </div>}
          {activeTab === 'acquisition' && <div className="vd2-roi-tools" aria-label="ROI tools">
            <span>ROI integration</span>
            {Object.entries(ROI_TOOLS).map(([tool, definition]) => (
              <button
                type="button"
                key={tool}
                className={roiTool === tool ? 'is-active' : ''}
                onClick={() => setRoiTool(tool)}
                title={`${definition.profile} ROI`}
              >
                {definition.label}
              </button>
            ))}
            <span className="vd2-roi-hint">Drag on image. Select an ROI to view its profile.</span>
            <button type="button" className="vd2-roi-clear" onClick={() => { setRois([]); setSelectedRoiId(null); }} disabled={!rois.length}>Clear</button>
          </div>}
          <div className="vd2-preview-canvas-wrap">
            <div className="vd2-image-stage">
              <canvas ref={previewCanvas} className="vd2-preview-canvas" />
              <FrameDisplayRate hz={previewStride > 1 && !previewFresh ? 0 : previewHz} />
              {preview && (
                <svg
                  ref={previewOverlay}
                  className="vd2-roi-overlay"
                  viewBox={`0 0 ${preview.width} ${preview.height}`}
                  onPointerDown={activeTab === 'acquisition' ? beginRoi : undefined}
                  onPointerMove={activeTab === 'acquisition' ? updateRoi : undefined}
                  onPointerUp={activeTab === 'acquisition' ? completeRoi : undefined}
                  onPointerCancel={() => setDrawingRoi(null)}
                >
                  {activeTab === 'alignment' && alignment.bounds && <VD2RoiEditor bounds={alignment.bounds}
                    width={preview.width} height={preview.height} pointFromEvent={previewPoint} label="Alignment ROI"
                    onChange={bounds => setAlignmentRegion(alignmentRegionFromBounds(bounds, calibration))} />}
                  {(activeTab === 'acquisition' ? [...rois, ...(drawingRoi ? [{ ...drawingRoi, id: 'drawing' }] : [])] : []).map((roi, index) => {
                    const bounds = roiBounds(roi, preview.width, preview.height);
                    const definition = ROI_TOOLS[roi.type];
                    const selected = roi.id === selectedRoiId;
                    return (
                      <g key={roi.id} className={selected ? 'is-selected' : ''}>
                        {roi.id === 'drawing' ? <rect x={bounds.x0} y={bounds.y0}
                          width={Math.max(1, bounds.x1 - bounds.x0 + 1)} height={Math.max(1, bounds.y1 - bounds.y0 + 1)} stroke={definition.color} />
                          : <VD2RoiEditor bounds={bounds} width={preview.width} height={preview.height}
                            pointFromEvent={previewPoint} selected={selected} type={roi.type} color={roiColor(index)}
                            label={`${definition.profile} ROI ${index + 1}`} onSelect={() => setSelectedRoiId(roi.id)}
                            onChange={next => setRois(current => updateRoisFromBounds(current, roi.id, next, linkRois, preview.width, preview.height))} />}
                        {roi.id !== 'drawing' && <text x={bounds.x0 + 4} y={bounds.y0 + 15} fill={roiColor(index)}>{index + 1}</text>}
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
          </div>
        </section>
        {activeTab === 'alignment' && <AlignmentKinetics geometry={alignment} region={alignmentRegion} context={alignmentContext}
          frameId={preview?.received_at} fresh={previewFresh}
          freshnessMessage={previewError || previewTiming.reason} measurements={alignmentMeasurements} />}
        </div>
        </div>
      )}

      {activeTab === 'hardware' && (
        <>
          <div className="vd2-hardware-actions">
            <button
              type="button"
              onClick={() => runCommand('RefreshStatus')}
              disabled={busy || !state?.application_running || state?.remoteex_status === 'busy'}
            >
              Read hardware
            </button>
          </div>
          <section className="vd2-grid" aria-label="Hardware setup">
            {CARDS.map((card) => (
              <ParameterCard card={card} values={values} onApply={writeParameter} busy={busy || protocolHardwareActive} key={card.title} />
            ))}
          </section>
        </>
      )}
      {activeTab === 'delay-lines' && (
        <section className="vd2-delay-lines" aria-label="VD2 delay lines">
          <h2>Delay Lines</h2>
          <VD2TranslationStages showHeading={false} />
        </section>
      )}
      {activeTab === 'pdu' && <VD2PDUControl />}
      <Vd2PhaseDialog
        prepared={preparedPhase}
        remaining={preparationRemaining}
        starting={protocolStarting}
        onCancel={cancelPreparedPhase}
        onStart={startProtocolPhase}
      />
      {guidedChoice && <div className="vd2-modal-backdrop">
        <section className="vd2-phase-dialog" role="dialog" aria-modal="true" aria-label="Choose Bruit for this measurement">
          <header><h2>Do Measurement</h2></header>
          <p>Reuse Bruit from {guidedChoice.sample}? Camera settings are checked before acquisition.</p>
          <footer>
            <button type="button" onClick={() => setGuidedChoice(null)}>Cancel</button>
            <button type="button" onClick={() => beginGuidedRun('none')}>Record new Bruit</button>
            <button type="button" onClick={() => beginGuidedRun(guidedChoice.id)}>Absorption + Base · reuse Bruit</button>
          </footer>
        </section>
      </div>}
      <Vd2RepeatDialog conflict={repeatConflict} starting={protocolStarting} onCancel={()=>setRepeatConflict(null)}
        onChoose={choice=>startProtocolPhase(repeatConflict.body.phase,{body:repeatConflict.body,choice})} />
    </main>
  );
}
