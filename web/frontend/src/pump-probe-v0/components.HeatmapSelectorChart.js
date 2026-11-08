import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import { STAGE_MIN_MM, STAGE_MAX_MM, MM_PER_PS, clamp, formatStageMm, normalizeRange } from './shared';
import { PlotlyChart } from "./components.PlotPanel";

function HeatmapSelectorChart({
  data,
  layout,
  config,
  className,
  wavelengthRange,
  delayRange,
  onRangesChange,
  onInteraction,
  onPointerEnter,
  onPointerLeave,
}) {
  const nodeRef = useRef(null);
  const shellRef = useRef(null);
  const dragRef = useRef(null);
  const [metrics, setMetrics] = useState(null);

  const updateMetrics = useCallback(() => {
    const shell = shellRef.current;
    const node = nodeRef.current;
    if (!shell || !node?._fullLayout) {
      return;
    }
    const rect = shell.getBoundingClientRect();
    const xAxis = node._fullLayout.xaxis;
    const yAxis = node._fullLayout.yaxis;
    setMetrics({
      xOffset: Number.isFinite(xAxis?._offset) ? xAxis._offset : 64,
      yOffset: Number.isFinite(yAxis?._offset) ? yAxis._offset : 20,
      innerWidth: Number.isFinite(xAxis?._length) ? xAxis._length : Math.max(1, rect.width - 142),
      innerHeight: Number.isFinite(yAxis?._length) ? yAxis._length : Math.max(1, rect.height - 68),
    });
  }, []);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }
    Plotly.react(node, data, layout, config)
      .then(() => window.requestAnimationFrame(updateMetrics))
      .catch(() => undefined);
    return undefined;
  }, [data, layout, config, updateMetrics]);

  useEffect(() => {
    const shell = shellRef.current;
    const node = nodeRef.current;
    if (!shell || !node) {
      return undefined;
    }
    const resize = () => {
      Plotly.Plots.resize(node);
      window.requestAnimationFrame(updateMetrics);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(shell);
    return () => {
      resizeObserver.disconnect();
      try {
        Plotly.purge(node);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, [updateMetrics]);

  const xToPixel = useCallback((value) => {
    const xAxis = nodeRef.current?._fullLayout?.xaxis;
    if (!metrics || !xAxis?.l2p) {
      return 0;
    }
    return metrics.xOffset + xAxis.l2p(value);
  }, [metrics]);

  const yToPixel = useCallback((value) => {
    const yAxis = nodeRef.current?._fullLayout?.yaxis;
    if (!metrics || !yAxis?.l2p) {
      return 0;
    }
    return metrics.yOffset + yAxis.l2p(value);
  }, [metrics]);

  const pointerToValues = useCallback((event) => {
    const shell = shellRef.current;
    const node = nodeRef.current;
    const xAxis = node?._fullLayout?.xaxis;
    const yAxis = node?._fullLayout?.yaxis;
    if (!shell || !metrics || !xAxis?.p2l || !yAxis?.p2l) {
      return null;
    }
    const rect = shell.getBoundingClientRect();
    const localX = clamp(event.clientX - rect.left, metrics.xOffset, metrics.xOffset + metrics.innerWidth);
    const localY = clamp(event.clientY - rect.top, metrics.yOffset, metrics.yOffset + metrics.innerHeight);
    return {
      x: xAxis.p2l(localX - metrics.xOffset),
      y: yAxis.p2l(localY - metrics.yOffset),
    };
  }, [metrics]);

  const normalizeAxisRange = useCallback((range, axis) => {
    const fullRange = nodeRef.current?._fullLayout?.[axis]?.range;
    const normalized = normalizeRange(range);
    if (!normalized || !Array.isArray(fullRange)) {
      return normalized;
    }
    const limits = normalizeRange(fullRange);
    const minWidth = Math.abs(limits[1] - limits[0]) / 200;
    let [start, end] = normalized;
    if (end - start < minWidth) {
      end = start + minWidth;
    }
    const width = end - start;
    if (start < limits[0]) {
      start = limits[0];
      end = start + width;
    }
    if (end > limits[1]) {
      end = limits[1];
      start = end - width;
    }
    return [clamp(start, limits[0], limits[1]), clamp(end, limits[0], limits[1])];
  }, []);

  const beginDrag = (event, axis, mode) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    const point = pointerToValues(event);
    if (!point) {
      return;
    }
    dragRef.current = {
      axis,
      mode,
      point,
      wavelengthRange,
      delayRange,
      pointerId: event.pointerId,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    onInteraction?.();
  };

  const updateDrag = useCallback((event) => {
    const drag = dragRef.current;
    if (!drag) {
      return;
    }
    const point = pointerToValues(event);
    if (!point) {
      return;
    }
    let nextWavelengthRange = wavelengthRange;
    let nextDelayRange = delayRange;
    if (drag.axis === 'x') {
      const delta = point.x - drag.point.x;
      if (drag.mode === 'start') {
        nextWavelengthRange = [point.x, drag.wavelengthRange[1]];
      } else if (drag.mode === 'end') {
        nextWavelengthRange = [drag.wavelengthRange[0], point.x];
      } else {
        nextWavelengthRange = [drag.wavelengthRange[0] + delta, drag.wavelengthRange[1] + delta];
      }
      nextWavelengthRange = normalizeAxisRange(nextWavelengthRange, 'xaxis');
    } else {
      const delta = point.y - drag.point.y;
      if (drag.mode === 'start') {
        nextDelayRange = [point.y, drag.delayRange[1]];
      } else if (drag.mode === 'end') {
        nextDelayRange = [drag.delayRange[0], point.y];
      } else {
        nextDelayRange = [drag.delayRange[0] + delta, drag.delayRange[1] + delta];
      }
      nextDelayRange = normalizeAxisRange(nextDelayRange, 'yaxis');
    }
    onRangesChange(nextWavelengthRange, nextDelayRange);
    onInteraction?.();
  }, [delayRange, normalizeAxisRange, onInteraction, onRangesChange, pointerToValues, wavelengthRange]);

  const finishDrag = useCallback(() => {
    dragRef.current = null;
  }, []);

  useEffect(() => {
    window.addEventListener('pointermove', updateDrag);
    window.addEventListener('pointerup', finishDrag);
    window.addEventListener('pointercancel', finishDrag);
    return () => {
      window.removeEventListener('pointermove', updateDrag);
      window.removeEventListener('pointerup', finishDrag);
      window.removeEventListener('pointercancel', finishDrag);
    };
  }, [finishDrag, updateDrag]);

  const regionStyle = useMemo(() => {
    if (!metrics || !wavelengthRange || !delayRange) {
      return null;
    }
    const x0 = xToPixel(wavelengthRange[0]);
    const x1 = xToPixel(wavelengthRange[1]);
    const y0 = yToPixel(delayRange[0]);
    const y1 = yToPixel(delayRange[1]);
    return {
      x: {
        left: Math.min(x0, x1),
        top: metrics.yOffset,
        width: Math.max(4, Math.abs(x1 - x0)),
        height: metrics.innerHeight,
      },
      y: {
        left: metrics.xOffset,
        top: Math.min(y0, y1),
        width: metrics.innerWidth,
        height: Math.max(4, Math.abs(y1 - y0)),
      },
    };
  }, [delayRange, metrics, wavelengthRange, xToPixel, yToPixel]);

  return (
    <div
      className={`pp-selector-shell ${className || ''}`.trim()}
      ref={shellRef}
      onMouseEnter={onPointerEnter}
      onMouseLeave={onPointerLeave}
    >
      <div ref={nodeRef} className="pp-selector-plot" />
      <div className="pp-selector-overlay">
        {regionStyle && (
          <>
            <div
              className="pp-selector-region pp-selector-region-x"
              style={{
                left: `${regionStyle.x.left}px`,
                top: `${regionStyle.x.top}px`,
                width: `${regionStyle.x.width}px`,
                height: `${regionStyle.x.height}px`,
              }}
              onPointerDown={(event) => beginDrag(event, 'x', 'move')}
            >
              <span
                className="pp-selector-handle pp-selector-handle-start"
                onPointerDown={(event) => beginDrag(event, 'x', 'start')}
              />
              <span
                className="pp-selector-handle pp-selector-handle-end"
                onPointerDown={(event) => beginDrag(event, 'x', 'end')}
              />
            </div>
            <div
              className="pp-selector-region pp-selector-region-y"
              style={{
                left: `${regionStyle.y.left}px`,
                top: `${regionStyle.y.top}px`,
                width: `${regionStyle.y.width}px`,
                height: `${regionStyle.y.height}px`,
              }}
              onPointerDown={(event) => beginDrag(event, 'y', 'move')}
            >
              <span
                className="pp-selector-handle pp-selector-handle-start"
                onPointerDown={(event) => beginDrag(event, 'y', 'start')}
              />
              <span
                className="pp-selector-handle pp-selector-handle-end"
                onPointerDown={(event) => beginDrag(event, 'y', 'end')}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StageControl({
  positionMm,
  setPositionMm,
  stepPs,
  zeroMm,
  onPositionChange,
  onStop,
  onStepChange,
  onZeroChange,
  onOpenConfig,
}) {
  const railRef = useRef(null);
  const [draftPositionMm, setDraftPositionMm] = useState(positionMm);
  const [hasPendingMove, setHasPendingMove] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const carriagePercent = ((STAGE_MAX_MM - draftPositionMm) / (STAGE_MAX_MM - STAGE_MIN_MM)) * 100;
  const stageMoving = Math.abs(setPositionMm - positionMm) > 0.005;

  useEffect(() => {
    if (!hasPendingMove && !isDragging) {
      setDraftPositionMm(setPositionMm);
    }
  }, [hasPendingMove, isDragging, setPositionMm]);

  const setDraftPosition = useCallback((value) => {
    setDraftPositionMm(clamp(value, STAGE_MIN_MM, STAGE_MAX_MM));
    setHasPendingMove(true);
  }, []);

  const moveByStep = (direction) => {
    const deltaMm = -Number(stepPs || 0) * MM_PER_PS * direction;
    setDraftPosition(draftPositionMm + deltaMm);
  };
  const pointerToPosition = (event) => {
    const rail = railRef.current;
    if (!rail) {
      return null;
    }
    const rect = rail.getBoundingClientRect();
    const ratio = clamp((event.clientY - rect.top) / Math.max(1, rect.height), 0, 1);
    return STAGE_MAX_MM - ratio * (STAGE_MAX_MM - STAGE_MIN_MM);
  };
  const beginDrag = (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const nextPosition = pointerToPosition(event);
    if (nextPosition !== null) {
      setDraftPosition(nextPosition);
      setIsDragging(true);
    }
  };
  const updateDrag = (event) => {
    if (!isDragging) {
      return;
    }
    const nextPosition = pointerToPosition(event);
    if (nextPosition !== null) {
      setDraftPosition(nextPosition);
    }
  };
  const finishDrag = () => {
    setIsDragging(false);
  };
  const handleDlFieldChange = (value) => {
    const setText = String(value).split('/')[0] || '';
    const parsed = Number(setText.replace(',', '.'));
    if (Number.isFinite(parsed)) {
      setDraftPosition(parsed);
    }
  };
  const acceptMove = () => {
    onPositionChange(draftPositionMm);
    setHasPendingMove(false);
    setIsDragging(false);
  };
  const rejectMove = () => {
    setDraftPositionMm(setPositionMm);
    setHasPendingMove(false);
    setIsDragging(false);
  };
  const stopMove = () => {
    onStop();
    setDraftPositionMm(positionMm);
    setHasPendingMove(false);
    setIsDragging(false);
  };

  return (
    <section
      className="pp-stage-panel"
      onContextMenu={(event) => {
        event.preventDefault();
        onOpenConfig('delayLine');
      }}
    >
      <div
        className="pp-panel-title pp-device-title"
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenConfig('delayLine');
        }}
      >
        Delay line
      </div>
      <div className="pp-stage-readouts">
        <label>
          DL, set/real mm
          <input
            type="text"
            value={`${formatStageMm(draftPositionMm)}/${formatStageMm(positionMm)}`}
            onChange={(event) => handleDlFieldChange(event.target.value)}
          />
        </label>
        <label>
          step, ps
          <input
            type="number"
            value={stepPs}
            step="0.1"
            onChange={(event) => onStepChange(Number(event.target.value) || 0)}
          />
        </label>
        <label>
          zero, mm
          <input
            type="number"
            value={zeroMm}
            step="0.1"
            onChange={(event) => onZeroChange(Number(event.target.value) || 0)}
          />
        </label>
      </div>
      <div className="pp-stage">
        <div
          className="pp-stage-rail"
          ref={railRef}
          onPointerMove={updateDrag}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          {Array.from({ length: 17 }, (_value, index) => (
            <span key={index} className="pp-stage-bolt" style={{ top: `${5 + index * 5.6}%` }} />
          ))}
          <div
            className={`pp-stage-carriage ${hasPendingMove ? 'pp-stage-carriage-pending' : ''}`.trim()}
            style={{ top: `${clamp(carriagePercent, 0, 100)}%` }}
            onPointerDown={beginDrag}
            onPointerMove={updateDrag}
            onPointerUp={finishDrag}
            onPointerCancel={finishDrag}
          >
            <div className="pp-stage-mirror pp-stage-mirror-left" />
            <div className="pp-stage-mirror pp-stage-mirror-right" />
            <div className="pp-stage-beam pp-stage-beam-a" />
            <div className="pp-stage-beam pp-stage-beam-b" />
          </div>
        </div>
      </div>
      <div className="pp-stage-actions">
        <button type="button" onClick={() => moveByStep(-1)}>Move -</button>
        <button type="button" onClick={() => moveByStep(1)}>Move +</button>
        <button
          type="button"
          className="pp-stage-accept"
          disabled={!hasPendingMove}
          onClick={acceptMove}
        >
          Accept
        </button>
        <button
          type="button"
          className="pp-stage-reject"
          disabled={!hasPendingMove}
          onClick={rejectMove}
        >
          Reject
        </button>
        <button
          type="button"
          className="pp-stage-stop"
          disabled={!hasPendingMove && !stageMoving}
          onClick={stopMove}
        >
          Stop DL
        </button>
      </div>
      <div className="pp-stage-scale">
        <span>{STAGE_MAX_MM} mm</span>
        <span>{STAGE_MIN_MM} mm</span>
      </div>
    </section>
  );
}

function SettingsPanel({
  settings,
  hardwareConfig,
  onSettingChange,
  onHardwareModeChange,
  delayStats,
  delayPreviewData,
  delayPreviewLayout,
  delayPreviewConfig,
  onDelayPointsLoad,
  onConfigLoad,
  onConfigSave,
}) {
  const delayFileInputRef = useRef(null);
  const configFileInputRef = useRef(null);

  const readTextFile = async (event, handler) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }
    const text = await file.text();
    handler(text);
  };

  return (
    <section className="pp-settings-panel">
      <div className="pp-panel-title">Scan settings</div>
      <div className="pp-settings-grid">
        <label>
          OZ, ps
          <input
            type="number"
            value={settings.scanStartPs}
            onChange={(event) => onSettingChange('scanStartPs', Number(event.target.value) || 0)}
          />
        </label>
        <label>
          step, ps
          <input
            type="number"
            step="0.001"
            value={settings.delayStepPs}
            disabled={settings.delayMode === 'custom'}
            onChange={(event) => onSettingChange('delayStepPs', Number(event.target.value) || 0)}
          />
        </label>
        <label>
          # points
          <input
            type="number"
            min="2"
            max="400"
            value={settings.pointCount}
            disabled={settings.delayMode === 'custom'}
            onChange={(event) => onSettingChange('pointCount', clamp(Number(event.target.value) || 2, 2, 400))}
          />
        </label>
        <label>
          Kinetic, ps
          <output>{delayStats.kineticPs.toFixed(3)}</output>
        </label>
        <label>
          Total, ps
          <output>{delayStats.totalPs.toFixed(3)}</output>
        </label>
        <label>
          Real zero, ps
          <input
            type="number"
            value={settings.realZeroPs}
            onChange={(event) => onSettingChange('realZeroPs', Number(event.target.value) || 0)}
          />
        </label>
        <label>
          Pulses / point
          <input
            type="number"
            min="1"
            value={settings.pulsesPerPoint}
            onChange={(event) => onSettingChange('pulsesPerPoint', Number(event.target.value) || 1)}
          />
        </label>
        <label>
          mode
          <output>{settings.delayMode}</output>
        </label>
        <label>
          control
          <select
            value={hardwareConfig.controlMode}
            onChange={(event) => onHardwareModeChange(event.target.value)}
          >
            <option value="emulator">emulator</option>
            <option value="tango">tango</option>
          </select>
        </label>
      </div>
      <div className="pp-settings-actions">
        <button type="button" onClick={() => delayFileInputRef.current?.click()}>
          Load delays TXT
        </button>
        <button
          type="button"
          onClick={() => onSettingChange('delayPointsPs', null)}
          disabled={settings.delayMode !== 'custom'}
        >
          Generated
        </button>
        <button type="button" onClick={() => configFileInputRef.current?.click()}>
          Load config
        </button>
        <button type="button" onClick={onConfigSave}>
          Save config
        </button>
        <input
          ref={delayFileInputRef}
          type="file"
          accept=".txt,.dat,.csv"
          className="pp-hidden-file"
          onChange={(event) => readTextFile(event, onDelayPointsLoad)}
        />
        <input
          ref={configFileInputRef}
          type="file"
          accept=".json,.txt"
          className="pp-hidden-file"
          onChange={(event) => readTextFile(event, onConfigLoad)}
        />
      </div>
      <div className="pp-delay-preview">
        <PlotlyChart
          className="pp-plot pp-plot-delay-preview"
          data={delayPreviewData}
          layout={delayPreviewLayout}
          config={delayPreviewConfig}
        />
      </div>
    </section>
  );
}

export {
  HeatmapSelectorChart, StageControl, SettingsPanel,
};
