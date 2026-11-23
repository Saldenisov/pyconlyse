import React from 'react';
import { PlotPanel, PlotlyChart } from './components';

export default function CurrentMonitor({
  variant = 'compact', className = '', spectraTitle, spectraData, spectraLayout,
  odSpectrumData, odSpectrumLayout, chartConfig, plotInteractionProps,
  spectraViewMode, onSpectraViewChange, hasRaw, realTime, onToggleRealTime,
}) {
  return <section className={`pp-current-monitor pp-current-monitor-${variant} ${className}`.trim()}
    aria-label="Current spectra and OD">
    <PlotPanel title={spectraTitle} className="pp-panel-fill" actions={
      <div className="pp-panel-toggle">
        <button type="button" className={spectraViewMode === 'current' ? 'pp-panel-toggle-active' : ''}
          onClick={() => onSpectraViewChange('current')}>Current</button>
        <button type="button" className={spectraViewMode === 'raw' ? 'pp-panel-toggle-active' : ''}
          onClick={() => onSpectraViewChange('raw')} disabled={!hasRaw}>Raw</button>
      </div>
    }>
      <div className="pp-current-plot">
        <PlotlyChart className="pp-plot pp-plot-spectra" data={spectraData}
          layout={spectraLayout} config={chartConfig} {...plotInteractionProps} />
        <button type="button" aria-pressed={realTime}
          className={`pp-current-realtime ${realTime ? 'pp-action-warn' : ''}`}
          onClick={onToggleRealTime}>Real time {realTime ? 'on' : 'off'}</button>
      </div>
    </PlotPanel>
    <PlotPanel title="Current OD" className="pp-panel-fill">
      <div className="pp-current-od-plot">
        <PlotlyChart className="pp-plot pp-plot-od" data={odSpectrumData}
          layout={odSpectrumLayout} config={chartConfig} {...plotInteractionProps} />
      </div>
    </PlotPanel>
  </section>;
}
