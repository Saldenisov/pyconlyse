import TreatmentPanel from './pump-probe-v0/TreatmentPanel';
import DerivedSourcePanel from './pump-probe-v0/DerivedSourcePanel';
import { NETIO_POWER_CHANNELS, HARDWARE_TANGO_SERVERS, displayPathTail } from './pump-probe-v0/shared';
import { PlotPanel, SampleStageControl, DeviceConfigModal, DataBrowserWindow, HardwareModal, PlotlyChart, HeatmapSelectorChart, StageControl, SettingsPanel } from './pump-probe-v0/components';

export function renderV0Workspace({
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
}) {
  return (
    <main className="pp-page">
      <header className="pp-header">
        <div>
          <h1>V0 Pump-Probe</h1>
          <div className="pp-subtitle">DLIII-V0 / Andor CCD / pulse radiolysis</div>
        </div>
        <SampleStageControl
          positionMm={sampleDisplayPositionMm}
          targetMm={sampleDisplayTargetMm}
          positions={samplePositionsMm}
          onMove={moveSampleStage}
          onStop={stopSampleStage}
          onMarkerMove={setSampleMarker}
          onOpenConfig={setDeviceConfigKey}
        />
        <div className="pp-run-controls">
          <button
            type="button"
            className={`pp-device-pill ${netioAnyOn ? 'pp-device-powered' : ''}`}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setNetioOpen(true);
            }}
            onClick={() => setNetioOpen(true)}
          >
            Hardware
          </button>
          <button
            type="button"
            className={hardwareInitStatus?.success ? 'pp-action-ok' : ''}
            disabled={hardwareInitLoading}
            onClick={() => runHardwareInitialization(true)}
            title="Check Tango servers, NETIO power, OWIS axes, DG645 recall 8, and DAQmx counter"
          >
            {hardwareInitLoading ? 'Init...' : 'Initialize HW'}
          </button>
          <button
            type="button"
            disabled={runBusy || backendState?.run?.status === 'stopping'}
            onClick={() => handleRun('new')}
          >
            {runBusy ? 'Preparing...' : running ? 'Stop' : backendState?.run?.status === 'stopping' ? 'Stopping...' : 'Start'}
          </button>
          {!running && backendState?.run?.resume_available && (
            <button type="button" disabled={runBusy} onClick={() => handleRun('continue')}>Continue</button>
          )}
          {(running || backendState?.run?.resume_available) && (
            <button type="button" onClick={() => postAndRefresh('/run', { running: false, run_action: 'cancel' })}>Cancel run</button>
          )}
          <button
            type="button"
            className={faradayClosed ? 'pp-action-ok' : 'pp-action-warn'}
            onClick={() => {
              const nextClosed = !faradayClosed;
              setLocalFaradayClosed(nextClosed);
              setLocalElectronState(nextClosed ? 'OFF' : 'ON');
              postAndRefresh('/faraday', { closed: nextClosed });
            }}
          >
            Faraday {faradayClosed ? 'closed' : 'open'}
          </button>
          <button type="button" onClick={() => postAndRefresh('/crystal/move')}>
            Move Crystal
          </button>
          <button
            type="button"
            className={realTime ? 'pp-action-warn' : ''}
            onClick={() => {
              postAndRefresh('/realtime', { enabled: !realTime });
            }}
          >
            Real time {realTime ? 'on' : 'off'}
          </button>
          <button
            type="button"
            onClick={() => {
              setLocalIndex(0);
              setLocalElectronState('OFF');
              postAndRefresh('/reset');
            }}
          >
            Reset
          </button>
          <div className="pp-data-strip">
            <div className="pp-data-fields">
              <input
                type="text"
                value={sampleName}
                onChange={(event) => setSampleName(event.target.value)}
                placeholder="Sample name"
                aria-label="Sample name"
              />
              <input
                type="text"
                value={dataFolderName}
                onChange={(event) => setDataFolderName(event.target.value)}
                placeholder="Folder"
                aria-label="Folder"
              />
            </div>
            <button
              type="button"
              onClick={() => {
                setDataBrowserOpen(true);
                loadDataPath(dataSelectedPath || dataPath || dataRoot);
              }}
            >
              Files
            </button>
            <span title={dataTopPath || 'No top folder selected'}>
              {dataTopPath ? displayPathTail(dataTopPath) : 'no top folder'}
            </span>
          </div>
        </div>
      </header>

      <section className="pp-status-strip">
        <div><span>control</span>{activeControlMode}</div>
        <div><span>delay</span>{(delays[activeCurrentIndex] || 0).toFixed(2)} ps</div>
        <div><span>position</span>{positionMm.toFixed(3)} mm</div>
        <div><span>state</span>electrons {electronState}</div>
        <div><span>point</span>{activeCurrentIndex + 1} / {delays.length}</div>
        <div><span>pulses</span>{backendState?.total_pulses ?? 0} @ {backendState?.accelerator_hz ?? 5} Hz</div>
        <div>
          <span>spectrometer</span>
          {backendState?.spectrometer_frames ?? 0} @ {backendState?.spectrometer_hz ?? 15} Hz
          / burst {backendState?.spectrometer_burst ?? 3}
        </div>
        <div className="pp-counter-status">
          <span>counter</span>
          <i className={`pp-counter-led ${counterActive ? 'pp-counter-led-active' : ''}`} />
          {daqCounter.value ?? '-'} @ {counterRateHz.toFixed(2)} Hz
        </div>
        <div><span>run</span>{backendState?.run?.status || 'idle'}</div>
      </section>
      {[...new Set([configurationError, actionError, backendError].filter(Boolean))].map((message) => (
        <div className="pp-api-error" role="alert" key={message}>{message}</div>
      ))}
      {delayImportError ? <div className="pp-api-error" role="alert">{delayImportError}</div> : null}
      {backendState?.hardware_error ? <div className="pp-api-error">{backendState.hardware_error}</div> : null}
      {activeControlMode === 'tango' && tangoRunPreview ? (
        <div className="pp-run-profile" role="status">
          RAW: track 1 → I, track 2 → II; BG_level = {tangoRunPreview.plan?.profile?.background_level};
          {' '}{tangoRunPreview.commissioned ? 'profile verified' : 'profile requires verification'}.
          {' '}Rejected cycles: {backendState?.run?.rejected_cycles || 0}.
        </div>
      ) : null}
      {hardwareInitStatus ? (
        <section className={`pp-hw-init ${hardwareInitStatus.success ? 'pp-hw-init-ok' : 'pp-hw-init-fail'}`}>
          <div className="pp-hw-init-head">
            <strong>{hardwareInitStatus.message || (hardwareInitStatus.success ? 'Hardware initialized' : 'Hardware initialization failed')}</strong>
            <span>{failedHardwareChecks.length ? `${failedHardwareChecks.length} problem(s)` : 'all checks OK'}</span>
            {!hardwareInitStatus.success ? (
              <button type="button" disabled={hardwareInitLoading} onClick={() => runHardwareInitialization(true)}>
                Resolve automatically
              </button>
            ) : null}
          </div>
          <div className="pp-hw-init-list">
            {hardwareChecks.map((check) => (
              <div key={`${check.label}-${check.device || check.axis || check.output_id || ''}`} className={check.ok ? 'pp-hw-check-ok' : 'pp-hw-check-fail'}>
                <b>{check.ok ? 'OK' : 'ERR'}</b>
                <span>{check.label}</span>
                <small>{check.detail}</small>
              </div>
            ))}
          </div>
          {hardwareInitStatus.recommendation ? <p>{hardwareInitStatus.recommendation}</p> : null}
        </section>
      ) : null}
      <section className="pp-selection-strip">
        <div><span>wavelength range</span>{selectedWavelengthLabel}</div>
        <div><span>delay range</span>{selectedDelayLabel}</div>
        <button
          type="button"
          onClick={() => {
            setSelectedWavelengthRange(null);
            setSelectedDelayRange(null);
            setPlotRevision((value) => value + 1);
          }}
        >
          Clear ranges
        </button>
      </section>

      <DerivedSourcePanel sources={derivedSources} busy={deriveBusy} error={deriveError}
        onDerive={deriveDatasets}
        onRemove={(index) => updateDerivedSources((current) => current.filter((_source, i) => i !== index))}
        onClear={() => updateDerivedSources([])}
        onMove={(index, offset) => updateDerivedSources((current) => {
          const next = [...current]; const target = index + offset;
          if (target >= 0 && target < next.length) [next[index], next[target]] = [next[target], next[index]];
          return next;
        })} />
      <section className="pp-layout">
        <div className="pp-left-column">
          <PlotPanel
            title={spectraTitle}
            className="pp-panel-fill"
            actions={(
              <div className="pp-panel-toggle">
                <button
                  type="button"
                  className={spectraViewMode === 'current' ? 'pp-panel-toggle-active' : ''}
                  onClick={() => setSpectraViewMode('current')}
                >
                  Current
                </button>
                <button
                  type="button"
                  className={spectraViewMode === 'raw' ? 'pp-panel-toggle-active' : ''}
                  onClick={() => setSpectraViewMode('raw')}
                  disabled={!visibleRawDataset?.channels?.length}
                >
                  Raw
                </button>
              </div>
            )}
          >
            <PlotlyChart
              className="pp-plot pp-plot-spectra"
              data={spectraData}
              layout={spectraLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
          </PlotPanel>

          <PlotPanel title="Current OD" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-od"
              data={odSpectrumData}
              layout={odSpectrumLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
          </PlotPanel>
        </div>

        <div className="pp-center-grid">
          <PlotPanel title={`OD heatmap · ${fileOdLoaded ? currentOdSource : 'Live'}`} className="pp-panel-fill" actions={(
            <div className="pp-panel-toggle">
              {['live', 'file'].map((owner) => (
                <button key={owner} type="button"
                  aria-pressed={odDisplayOwner === owner}
                  className={odDisplayOwner === owner ? 'pp-panel-toggle-active' : ''}
                  disabled={owner === 'file' && !loadedOdDataset}
                  onClick={() => {
                    odDisplayEpochRef.current += 1;
                    setTreatmentOpen(false);
                    setOdDisplayOwner(owner);
                    setSelectedWavelengthRange(null);
                    setSelectedDelayRange(null);
                    setPlotRevision((value) => value + 1);
                  }}>
                  {owner === 'live' ? 'Live OD' : 'File OD'}
                </button>
              ))}
              <button type="button" className="pp-icon-button" disabled={!fileOdLoaded || !sourceOdDataset}
                onClick={() => setTreatmentOpen(true)}>Corrections</button>
            </div>
          )}>
            <HeatmapSelectorChart
              className="pp-plot pp-plot-heatmap"
              data={heatmapData}
              layout={heatmapLayout}
              config={heatmapConfig}
              wavelengthRange={activeWavelengthRange}
              delayRange={activeDelayRange}
              onRangesChange={(nextWavelengthRange, nextDelayRange) => {
                setSelectedWavelengthRange(nextWavelengthRange);
                setSelectedDelayRange(nextDelayRange);
              }}
              {...plotInteractionProps}
            />
          </PlotPanel>

          <PlotPanel title="Kinetics" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-kinetics"
              data={kineticsData}
              layout={kineticsLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
            <div className="pp-kinetics-floating-actions">
              <div className="pp-kinetics-actions">
                <button
                  type="button"
                  className="pp-icon-button"
                  title={`Add kinetics: ${selectedWavelengthLabel}`}
                  onClick={addKineticTrace}
                >
                  + Kinetic
                </button>
                {savedKinetics.length ? (
                  <button
                    type="button"
                    className="pp-icon-button"
                    title="Clear saved kinetics"
                    onClick={() => setSavedKinetics([])}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="pp-kinetic-chip-row">
                  {savedKinetics.map((trace) => (
                    <button
                      key={trace.id}
                      type="button"
                      className="pp-kinetic-chip"
                      title={`${trace.label}: ${trace.wavelengthLabel} / ${trace.source}`}
                      onClick={() => removeKineticTrace(trace.id)}
                    >
                      <span style={{ background: trace.color }} />
                      {trace.label} x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </PlotPanel>

          <PlotPanel title="OD spectrum" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-od"
              data={odSpectrumData}
              layout={odSpectrumLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
            <div className="pp-spectrum-floating-actions">
              <div className="pp-kinetics-actions">
                <button
                  type="button"
                  className="pp-icon-button"
                  title={`Add OD spectrum: ${selectedDelayLabel}`}
                  onClick={addOdSpectrumTrace}
                >
                  + Spectrum
                </button>
                {savedOdSpectra.length ? (
                  <button
                    type="button"
                    className="pp-icon-button"
                    title="Clear saved OD spectra"
                    onClick={() => setSavedOdSpectra([])}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="pp-kinetic-chip-row">
                  {savedOdSpectra.map((trace) => (
                    <button
                      key={trace.id}
                      type="button"
                      className="pp-kinetic-chip"
                      title={`${trace.label}: ${trace.delayLabel} / ${trace.source}`}
                      onClick={() => removeOdSpectrumTrace(trace.id)}
                    >
                      <span style={{ background: trace.color }} />
                      {trace.label} x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </PlotPanel>

          <SettingsPanel
            settings={settings}
            hardwareConfig={hardwareConfig}
            onSettingChange={handleSettingChange}
            onHardwareModeChange={handleHardwareModeChange}
            delayStats={delayStats}
            delayPreviewData={delayPreviewData}
            delayPreviewLayout={delayPreviewLayout}
            delayPreviewConfig={delayPreviewConfig}
            onDelayPointsLoad={handleDelayPointsLoad}
            onConfigLoad={handleConfigLoad}
            onConfigSave={handleConfigSave}
          />
        </div>

        <aside className="pp-right-column">
          <StageControl
            positionMm={positionMm}
            setPositionMm={setPositionMm}
            stepPs={stepPs}
            zeroMm={zeroMm}
            onPositionChange={(value) => {
              setBackendState((current) => (current ? { ...current, set_position_mm: value, stage_moving: true } : current));
              postAndRefresh('/stage/move', { position_mm: value });
            }}
            onStop={() => {
              setBackendState((current) => (current ? {
                ...current,
                set_position_mm: current.position_mm,
                stage_moving: false,
              } : current));
              postAndRefresh('/stage/stop');
            }}
            onStepChange={setStepPs}
            onZeroChange={setZeroMm}
            onOpenConfig={setDeviceConfigKey}
          />
        </aside>
      </section>
      {treatmentOpen && sourceOdDataset && (
        <TreatmentPanel key={`${sourceOdDataset.path}:${sourceOdDataset.source_sha256}`}
          source={sourceOdDataset} applied={loadedOdDataset}
          selection={{ wavelength_pixels: [Math.min(...safeWavelengthIndexes), Math.max(...safeWavelengthIndexes)],
            delay_pixels: [Math.min(...safeDelayIndexes), Math.max(...safeDelayIndexes)] }}
          onPreview={(preview) => {
            if (treatmentRequestEpoch === odDisplayEpochRef.current) {
              setTreatmentPreview(preview);
              if (preview || treatmentPreview) {
                setSelectedWavelengthRange(null); setSelectedDelayRange(null); setLocalIndex(0);
                setPlotRevision((value) => value + 1);
              }
            }
          }}
          onApply={(applied) => {
            if (treatmentRequestEpoch === odDisplayEpochRef.current) {
              setLoadedOdDataset(applied); setSelectedWavelengthRange(null); setSelectedDelayRange(null); setLocalIndex(0);
              setPlotRevision((value) => value + 1);
            }
          }}
          onClose={() => { setTreatmentPreview(null); setTreatmentOpen(false); }} />
      )}
      <DeviceConfigModal
        deviceKey={deviceConfigKey}
        config={deviceConfig}
        onChange={setDeviceConfig}
        samplePositions={samplePositionsMm}
        onSamplePositionsChange={setSamplePositionsMm}
        onClose={() => setDeviceConfigKey(null)}
      />
      <HardwareModal
        open={netioOpen}
        channels={NETIO_POWER_CHANNELS}
        devices={netioDevices}
        tangoServers={HARDWARE_TANGO_SERVERS}
        tangoStates={tangoStates}
        loading={netioLoading}
        tangoLoading={tangoLoading}
        error={netioError}
        tangoError={tangoError}
        onClose={closeHardwareModal}
        onRefresh={() => {
          loadNetioOutputs();
          loadTangoStates();
        }}
        onToggle={toggleNetioChannel}
        onBulkPower={setNecessaryHardwarePower}
        onStartTango={(server) => controlTangoServer(server, 'start')}
        onRestartTango={(server) => controlTangoServer(server, 'restart')}
      />
      <DataBrowserWindow
        open={dataBrowserOpen}
        sampleName={sampleName}
        root={dataRoot}
        path={dataPath}
        parent={dataParent}
        entries={dataEntries}
        loading={dataLoading}
        error={dataError}
        selectedPath={dataSelectedPath}
        topPath={dataTopPath}
        onClose={() => setDataBrowserOpen(false)}
        onRefresh={() => loadDataPath(dataPath || dataRoot)}
        onOpenPath={(pathValue) => loadDataPath(pathValue || dataRoot)}
        onSelectPath={setDataSelectedPath}
        onSetTopFolder={(pathValue) => setDataTopPath(pathValue || dataRoot)}
        onLoadFile={loadDataFile}
        onCreateFolder={createSampleFolder}
      />
    </main>
  );
}
