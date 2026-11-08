import { useEffect, useMemo } from 'react';
import { heatmapAxis, selectionAround, physicalSelection } from './pump-probe-v0/heatmapAxes';
import { STAGE_MIN_MM, STAGE_MAX_MM, MM_PER_PS, clamp, indexesInRange, averageRows, averageColumns, nearestIndex, makeCurrentSpectra, NETIO_POWER_CHANNELS } from './pump-probe-v0/shared';

export function useV0PlotState({
  settings, hardwareConfig, samplePositionMm, sampleTargetMm, backendState,
  setLocalIndex, localRunning, localPositionMm, setLocalPositionMm, localElectronState,
  setLocalElectronState, localFaradayClosed, selectedWavelengthRange, selectedDelayRange,
  plotRevision, netioDevices, hardwareInitStatus, treatmentPreview, spectraViewMode,
  savedKinetics, setSavedKinetics, kineticCounter, setKineticCounter, savedOdSpectra,
  setSavedOdSpectra, odSpectrumCounter, setOdSpectrumCounter, displayedOdDataset,
  fileOdLoaded, liveWavelengths, wavelengths, visibleRawDataset, delays, heatmap, liveOd,
  currentIndex, activeCurrentIndex,
}) {
  const realTime = backendState?.real_time ?? false;
  const faradayClosed = backendState?.faraday_closed ?? localFaradayClosed;
  const electronState = backendState?.electron_state || localElectronState;
  const positionMm = backendState?.position_mm ?? localPositionMm;
  const setPositionMm = backendState?.set_position_mm ?? localPositionMm;
  const activeControlMode = hardwareConfig.controlMode || backendState?.control_mode || 'emulator';
  const daqCounter = backendState?.daq_counter || {};
  const counterActive = Boolean(daqCounter.active);
  const counterRateHz = Number(daqCounter.rate_hz || 0);
  const hardwareChecks = hardwareInitStatus?.checks || [];
  const failedHardwareChecks = hardwareChecks.filter((check) => !check.ok);
  const sampleDisplayPositionMm = activeControlMode === 'tango'
    ? (backendState?.sample_position_mm ?? samplePositionMm)
    : samplePositionMm;
  const sampleDisplayTargetMm = activeControlMode === 'tango'
    ? (backendState?.sample_set_position_mm ?? sampleTargetMm)
    : sampleTargetMm;
  const netioAnyOn = NETIO_POWER_CHANNELS.some((channel) => (
    netioDevices[channel.device]?.outputs?.some((output) => (
      output.id === channel.outputId && Number(output.state) === 1
    ))
  ));
  const delayStats = useMemo(() => {
    const finiteDelays = delays.filter((value) => Number.isFinite(value));
    if (!finiteDelays.length) {
      return { pointCount: 0, kineticPs: 0, totalPs: 0 };
    }
    const minDelay = Math.min(...finiteDelays);
    const maxDelay = Math.max(...finiteDelays);
    return {
      pointCount: finiteDelays.length,
      kineticPs: Math.max(0, maxDelay),
      totalPs: maxDelay - minDelay,
    };
  }, [delays]);

  useEffect(() => {
    if (backendState || !localRunning) {
      return undefined;
    }
    const timerId = window.setInterval(() => {
      setLocalIndex((value) => (value + 1) % delays.length);
      setLocalElectronState(localFaradayClosed ? 'OFF' : 'ON');
    }, 200);
    return () => window.clearInterval(timerId);
  }, [backendState, localRunning, localFaradayClosed, delays.length]);

  useEffect(() => {
    if (backendState) {
      return;
    }
    const delayPs = delays[currentIndex] || 0;
    setLocalPositionMm(clamp(-(delayPs + settings.realZeroPs) * MM_PER_PS, STAGE_MIN_MM, STAGE_MAX_MM));
  }, [backendState, currentIndex, delays, settings.realZeroPs]);

  const spectra = useMemo(
    () => backendState?.spectra || makeCurrentSpectra(liveWavelengths, activeCurrentIndex, electronState),
    [backendState, liveWavelengths, activeCurrentIndex, electronState]
  );

  const completedHeatmap = backendState || fileOdLoaded
    ? heatmap
    : heatmap.map((row, index) => (
      index <= activeCurrentIndex ? row : row.map(() => null)
    ));
  const kineticWavelength = 445;
  const kineticIndex = wavelengths.reduce((bestIndex, wavelength, index) => (
    Math.abs(wavelength - kineticWavelength) < Math.abs(wavelengths[bestIndex] - kineticWavelength)
      ? index
      : bestIndex
  ), 0);
  const delayStep = Math.abs((delays[1] ?? delays[0] + 1) - (delays[0] ?? 0)) || 1;
  const wavelengthAxis = heatmapAxis(wavelengths);
  const delayAxis = heatmapAxis(delays);
  const defaultWavelengthRange = selectionAround(wavelengthAxis, kineticIndex, wavelengthAxis.positional ? 0.49 : 10);
  const defaultDelayRange = selectionAround(delayAxis, activeCurrentIndex, delayAxis.positional ? 0.49 : delayStep);
  const activeWavelengthRange = selectedWavelengthRange || defaultWavelengthRange;
  const activeDelayRange = selectedDelayRange || defaultDelayRange;
  const selectedWavelengthIndexes = indexesInRange(wavelengthAxis.coordinates, activeWavelengthRange);
  const selectedDelayIndexes = indexesInRange(delayAxis.coordinates, activeDelayRange);
  const safeWavelengthIndexes = selectedWavelengthIndexes.length
    ? selectedWavelengthIndexes
    : [kineticIndex];
  const safeDelayIndexes = selectedDelayIndexes.length
    ? selectedDelayIndexes
    : [activeCurrentIndex];
  const selectedRowsOd = averageRows(heatmap, safeDelayIndexes);
  const selectedRowsHaveData = selectedRowsOd.some((value) => value !== null && value !== undefined);
  const selectedOd = fileOdLoaded ? selectedRowsOd : (selectedRowsHaveData ? selectedRowsOd : (liveOd || selectedRowsOd));
  const kineticTrace = averageColumns(heatmap, safeWavelengthIndexes);
  const selectedPhysicalWavelengths = physicalSelection(wavelengths, safeWavelengthIndexes);
  const selectedPhysicalDelays = physicalSelection(delays, safeDelayIndexes);
  const selectedWavelengthLabel = `${selectedPhysicalWavelengths[0].toFixed(1)}-${selectedPhysicalWavelengths[1].toFixed(1)} nm${wavelengthAxis.positional ? `; pixels ${safeWavelengthIndexes[0]}-${safeWavelengthIndexes[safeWavelengthIndexes.length - 1]}` : ''}`;
  const selectedDelayLabel = `${selectedPhysicalDelays[0].toFixed(2)}-${selectedPhysicalDelays[1].toFixed(2)} ps${delayAxis.positional ? `; rows ${safeDelayIndexes[0]}-${safeDelayIndexes[safeDelayIndexes.length - 1]}` : ''}`;
  const rawDelayIndexes = fileOdLoaded ? safeDelayIndexes : visibleRawDataset?.delays?.length
    ? indexesInRange(visibleRawDataset.delays, selectedPhysicalDelays)
    : [];
  const rawSafeDelayIndexes = rawDelayIndexes.length
    ? rawDelayIndexes
    : (visibleRawDataset?.delays?.length
      ? [nearestIndex(visibleRawDataset.delays, (selectedPhysicalDelays[0] + selectedPhysicalDelays[1]) / 2)]
      : []);
  const showRawSpectra = spectraViewMode === 'raw' && visibleRawDataset?.channels?.length;
  const rawColors = ['#f1c84b', '#33c5ff', '#f05d5e', '#c798ff', '#7ee787', '#ff9f43'];
  const savedKineticColors = ['#33c5ff', '#f1c84b', '#c798ff', '#ff9f43', '#7ee787', '#ff6b9a', '#9fb7ff'];
  const currentOdSource = fileOdLoaded
    ? `${displayedOdDataset.file_name || 'OD file'}${treatmentPreview ? ' (preview)' : ''}`
    : 'live';

  const addKineticTrace = () => {
    const nextIndex = kineticCounter;
    const nextColor = savedKineticColors[(nextIndex - 1) % savedKineticColors.length];
    setSavedKinetics((current) => ([
      ...current,
      {
        id: `kinetic-${Date.now()}-${nextIndex}`,
        label: `K${nextIndex}`,
        source: currentOdSource,
        wavelengthRange: [...activeWavelengthRange],
        wavelengthLabel: selectedWavelengthLabel,
        x: [...delays],
        y: kineticTrace.map((value) => (value ?? null)),
        color: nextColor,
      },
    ]));
    setKineticCounter((value) => value + 1);
  };

  const removeKineticTrace = (id) => {
    setSavedKinetics((current) => current.filter((trace) => trace.id !== id));
  };

  const addOdSpectrumTrace = () => {
    const nextIndex = odSpectrumCounter;
    const nextColor = savedKineticColors[(nextIndex - 1) % savedKineticColors.length];
    setSavedOdSpectra((current) => ([
      ...current,
      {
        id: `od-spectrum-${Date.now()}-${nextIndex}`,
        label: `S${nextIndex}`,
        source: currentOdSource,
        delayRange: [...activeDelayRange],
        delayLabel: selectedDelayLabel,
        x: [...wavelengths],
        y: selectedOd.map((value) => (value ?? null)),
        color: nextColor,
      },
    ]));
    setOdSpectrumCounter((value) => value + 1);
  };

  const removeOdSpectrumTrace = (id) => {
    setSavedOdSpectra((current) => current.filter((trace) => trace.id !== id));
  };

  const plotTheme = {
    paper_bgcolor: '#11151b',
    plot_bgcolor: '#07090d',
    font: { color: '#d9dde4', family: 'Segoe UI, Arial, sans-serif' },
    margin: { l: 58, r: 18, t: 20, b: 48 },
    uirevision: `pump-probe-v0-${plotRevision}`,
    dragmode: 'zoom',
    xaxis: {
      gridcolor: '#26313b',
      zerolinecolor: '#59636d',
      title: { text: 'Wavelength, nm' },
    },
    yaxis: {
      gridcolor: '#26313b',
      zerolinecolor: '#59636d',
    },
  };

  const spectraData = showRawSpectra
    ? visibleRawDataset.channels.map((channel, index) => ({
      x: visibleRawDataset.wavelengths,
      y: averageRows(channel.values || [], rawSafeDelayIndexes),
      type: 'scatter',
      mode: 'lines',
      name: channel.label || channel.key,
      line: { color: rawColors[index % rawColors.length], width: index < 3 ? 2 : 1.5 },
    }))
    : [
      {
        x: liveWavelengths,
        y: spectra.signal,
        type: 'scatter',
        mode: 'lines',
        name: 'Is',
        line: { color: '#f05d5e', width: 2 },
      },
      {
        x: liveWavelengths,
        y: spectra.reference,
        type: 'scatter',
        mode: 'lines',
        name: 'Ir',
        line: { color: '#33c5ff', width: 2 },
      },
      ...(spectra.background_available === false ? [] : [{
        x: liveWavelengths,
        y: spectra.background,
        type: 'scatter',
        mode: 'lines',
        name: 'BG',
        line: { color: '#f1c84b', width: 1.5 },
      }]),
    ];
  const spectraTitle = showRawSpectra
    ? `Raw spectrum (${visibleRawDataset.file_name || 'ZIP'})`
    : 'Current spectra';

  const spectraLayout = {
    ...plotTheme,
    yaxis: { ...plotTheme.yaxis, title: { text: 'Amplitude' } },
    legend: { orientation: 'h', y: 1.16, x: 0 },
  };

  const savedOdSpectrumData = savedOdSpectra.map((trace) => ({
    x: trace.x,
    y: trace.y,
    type: 'scatter',
    mode: 'lines',
    name: `${trace.label} ${trace.delayLabel}`,
    line: { color: trace.color, width: 1.8, dash: 'dot' },
    hovertemplate: `${trace.label}<br>%{x:.1f} nm<br>OD=%{y:.5f}<extra>${trace.source}</extra>`,
  }));
  const odSpectrumData = [
    ...savedOdSpectrumData,
    {
      x: wavelengths,
      y: selectedOd,
      type: 'scatter',
      mode: 'lines',
      name: `selection ${selectedDelayLabel}`,
      line: { color: '#7ee787', width: 2.4 },
    },
  ];

  const odSpectrumLayout = {
    ...plotTheme,
    yaxis: { ...plotTheme.yaxis, title: { text: 'delta O.D.' }, range: [-0.006, 0.006], fixedrange: true },
  };

  const savedKineticsData = savedKinetics.map((trace) => ({
    x: trace.x,
    y: trace.y,
    type: 'scatter',
    mode: 'lines',
    name: `${trace.label} ${trace.wavelengthLabel}`,
    line: { color: trace.color, width: 1.8, dash: 'dot' },
    hovertemplate: `${trace.label}<br>%{x:.2f} ps<br>OD=%{y:.5f}<extra>${trace.source}</extra>`,
  }));
  const kineticsData = [
    ...savedKineticsData,
    {
      x: delays,
      y: kineticTrace,
      type: 'scatter',
      mode: 'lines',
      name: `selection ${selectedWavelengthLabel}`,
      line: { color: '#f05d5e', width: 2.4 },
    },
    {
      x: [delays[activeCurrentIndex]],
      y: [kineticTrace[activeCurrentIndex]],
      type: 'scatter',
      mode: 'markers',
      name: 'current',
      marker: { color: '#f1c84b', size: 9 },
    },
  ];

  const kineticsLayout = {
    ...plotTheme,
    xaxis: { ...plotTheme.xaxis, title: { text: 'Time delay, ps' } },
    yaxis: { ...plotTheme.yaxis, title: { text: 'delta O.D.' }, range: [-0.18, 0.28] },
    legend: { orientation: 'h', y: 1.16, x: 0 },
  };

  const heatmapData = [
    {
      x: wavelengthAxis.coordinates,
      y: delayAxis.coordinates,
      z: completedHeatmap,
      customdata: delays.map((delay, row) => wavelengths.map((wavelength, column) =>
        [wavelength, delay, column, row, displayedOdDataset?.source_row_indices?.[row] ?? row])),
      type: 'heatmap',
      colorscale: [
        [0, '#13294b'],
        [0.35, '#1f8f7a'],
        [0.55, '#f0d34f'],
        [1, '#e6462e'],
      ],
      zmin: -0.12,
      zmax: 0.25,
      colorbar: { title: 'delta O.D.' },
      hovertemplate: 'wl=%{customdata[0]:.1f} nm<br>delay=%{customdata[1]:.2f} ps<br>pixel=%{customdata[2]}, row=%{customdata[3]} (source %{customdata[4]})<br>OD=%{z:.4f}<extra></extra>',
    },
  ];

  const heatmapLayout = {
    ...plotTheme,
    dragmode: false,
    margin: { l: 64, r: 78, t: 20, b: 48 },
    xaxis: {
      ...plotTheme.xaxis,
      range: wavelengthAxis.range,
      ...wavelengthAxis.ticks,
      title: { text: wavelengthAxis.positional ? 'Wavelength, nm [pixel]' : 'Wavelength, nm' },
      fixedrange: true,
    },
    yaxis: {
      ...plotTheme.yaxis,
      title: { text: delayAxis.positional ? 'Time delay, ps [row]' : 'Time delay, ps' },
      range: delayAxis.range,
      ...delayAxis.ticks,
      fixedrange: true,
    },
  };
  const heatmapConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    doubleClick: false,
    scrollZoom: false,
  }), []);
  const delayPreviewData = [
    {
      x: delays.map((_delay, index) => index + 1),
      y: delays,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'delay',
      line: { color: '#33c5ff', width: 1.5 },
      marker: { color: '#f1c84b', size: 3 },
      hovertemplate: 'point=%{x}<br>delay=%{y:.3f} ps<extra></extra>',
    },
  ];
  const delayPreviewLayout = {
    ...plotTheme,
    margin: { l: 48, r: 12, t: 8, b: 34 },
    xaxis: { ...plotTheme.xaxis, title: { text: 'Point' }, fixedrange: true },
    yaxis: { ...plotTheme.yaxis, title: { text: 'Delay, ps' }, fixedrange: true },
    showlegend: false,
  };
  const delayPreviewConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    scrollZoom: false,
  }), []);
  const chartConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: true,
    modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d', 'resetScale2d'],
    scrollZoom: true,
  }), []);
  const plotInteractionProps = {
  };

  return {
    realTime, faradayClosed, electronState, positionMm, setPositionMm, activeControlMode,
    daqCounter, counterActive, counterRateHz, hardwareChecks, failedHardwareChecks,
    sampleDisplayPositionMm, sampleDisplayTargetMm, netioAnyOn, delayStats,
    activeWavelengthRange, activeDelayRange, safeWavelengthIndexes, safeDelayIndexes,
    selectedWavelengthLabel, selectedDelayLabel, currentOdSource, addKineticTrace,
    removeKineticTrace, addOdSpectrumTrace, removeOdSpectrumTrace, spectraData,
    spectraTitle, spectraLayout, odSpectrumData, odSpectrumLayout, kineticsData,
    kineticsLayout, heatmapData, heatmapLayout, heatmapConfig, delayPreviewData,
    delayPreviewLayout, delayPreviewConfig, chartConfig, plotInteractionProps,
  };
}
