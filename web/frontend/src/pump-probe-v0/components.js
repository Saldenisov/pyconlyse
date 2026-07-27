import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import {
  SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM, STAGE_MIN_MM, STAGE_MAX_MM, MM_PER_PS,
  clamp, formatStageMm, formatBytes, displayPathTail, normalizeRange, parseDelayPointsText,
} from './shared';

// Presentational V0 panels. State and hardware actions remain in PumpProbeV0.
function PlotPanel({ title, children, className = '', actions = null }) {
  return (
    <section className={`pp-panel ${className}`.trim()}>
      <div className="pp-panel-title">
        <span>{title}</span>
        {actions ? <div className="pp-panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

function SampleStageControl({
  positionMm,
  targetMm,
  positions,
  onMove,
  onStop,
  onMarkerMove,
  onOpenConfig,
}) {
  const [draftMm, setDraftMm] = useState(targetMm);
  const percent = ((positionMm - SAMPLE_STAGE_MIN_MM) / (SAMPLE_STAGE_MAX_MM - SAMPLE_STAGE_MIN_MM)) * 100;

  useEffect(() => {
    setDraftMm(targetMm);
  }, [targetMm]);

  const handleSetRealChange = (value) => {
    const setText = String(value).split('/')[0] || '';
    const parsed = Number(setText.replace(',', '.'));
    if (Number.isFinite(parsed)) {
      setDraftMm(clamp(parsed, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
    }
  };

  const moveTo = (value) => {
    const next = clamp(value, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM);
    setDraftMm(next);
    onMove(next);
  };

  return (
    <section
      className="pp-sample-stage"
      onContextMenu={(event) => {
        event.preventDefault();
        onOpenConfig('sampleStage');
      }}
    >
      <div
        className="pp-device-title"
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenConfig('sampleStage');
        }}
      >
        Sample translation stage
      </div>
      <div className="pp-sample-stage-row">
        <div className="pp-sample-rail">
          <div className="pp-sample-scale">
            <span>{SAMPLE_STAGE_MIN_MM}</span>
            <span>{SAMPLE_STAGE_MAX_MM} mm</span>
          </div>
          <div
            className="pp-sample-carriage"
            style={{ left: `${clamp(percent, 0, 100)}%` }}
          />
          {positions.map((marker, index) => (
            <button
              key={index}
              type="button"
              className="pp-sample-marker"
              style={{ left: `${((marker - SAMPLE_STAGE_MIN_MM) / (SAMPLE_STAGE_MAX_MM - SAMPLE_STAGE_MIN_MM)) * 100}%` }}
              title={`P${index + 1}: ${formatStageMm(marker)} mm`}
              onClick={() => moveTo(marker)}
              onContextMenu={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onMarkerMove(index, positionMm);
              }}
            />
          ))}
        </div>
        <label className="pp-sample-set">
          set/real mm
          <input
            type="text"
            value={`${formatStageMm(draftMm)}/${formatStageMm(positionMm)}`}
            onChange={(event) => handleSetRealChange(event.target.value)}
          />
        </label>
        <div className="pp-sample-move-stack">
          <button type="button" onClick={() => moveTo(draftMm)}>
            Move
          </button>
          <button type="button" onClick={onStop}>
            Stop
          </button>
        </div>
      </div>
      <div className="pp-sample-marker-row">
        {positions.map((marker, index) => (
          <button
            key={index}
            type="button"
            onClick={() => moveTo(marker)}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onMarkerMove(index, positionMm);
            }}
          >
            P{index + 1} {formatStageMm(marker)}
          </button>
        ))}
      </div>
    </section>
  );
}

function DeviceConfigModal({
  deviceKey,
  config,
  onChange,
  samplePositions,
  onSamplePositionsChange,
  onClose,
}) {
  if (!deviceKey) {
    return null;
  }
  const device = config[deviceKey];
  if (!device) {
    return null;
  }
  const setDeviceField = (field, value) => {
    onChange({
      ...config,
      [deviceKey]: {
        ...device,
        [field]: value,
      },
    });
  };

  return (
    <div className="pp-modal-backdrop" onClick={onClose}>
      <section className="pp-device-modal" onClick={(event) => event.stopPropagation()}>
        <div className="pp-device-modal-title">
          <span>{device.label}</span>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <div className="pp-device-status">
          <div><span>Tango server</span>{device.enabled ? 'EMULATOR ONLINE' : 'DISABLED'}</div>
          <div><span>Device state</span>{device.enabled ? 'ON / READY' : 'OFFLINE'}</div>
          {deviceKey === 'spectrometer' && (
            <div><span>Power</span>{device.powerOn ? 'NETIO ON' : 'NETIO OFF'}</div>
          )}
        </div>
        <label>
          {deviceKey === 'delayLine' || deviceKey === 'sampleStage' ? 'OWIS aggregator' : 'Tango device'}
          <input
            type="text"
            value={device.tangoDevice || ''}
            onChange={(event) => setDeviceField('tangoDevice', event.target.value)}
          />
        </label>
        {(deviceKey === 'delayLine' || deviceKey === 'sampleStage') && (
          <>
            <label>
              axis
              <input
                type="number"
                min="1"
                max="4"
                value={device.axis || 1}
                onChange={(event) => setDeviceField('axis', Number(event.target.value) || 1)}
              />
            </label>
            <label>
              axis device
              <input
                type="text"
                value={device.backendDeviceName || ''}
                onChange={(event) => setDeviceField('backendDeviceName', event.target.value)}
              />
            </label>
            <label>
              hardware label
              <input
                type="text"
                value={device.hardwareLabel || ''}
                onChange={(event) => setDeviceField('hardwareLabel', event.target.value)}
              />
            </label>
          </>
        )}
        {deviceKey === 'spectrometer' && (
          <label>
            NETIO power device
            <input
              type="text"
              value={device.netioDevice || ''}
              onChange={(event) => setDeviceField('netioDevice', event.target.value)}
            />
          </label>
        )}
        {deviceKey === 'sampleStage' && (
          <label>
            positions, mm
            <textarea
              value={samplePositions.join('\n')}
              onChange={(event) => {
                const nextPositions = parseDelayPointsText(event.target.value)
                  .map((value) => clamp(value, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
                if (nextPositions.length) {
                  onSamplePositionsChange(nextPositions);
                }
              }}
            />
          </label>
        )}
        <div className="pp-device-modal-actions">
          <button type="button" onClick={() => setDeviceField('enabled', !device.enabled)}>
            {device.enabled ? 'Disable' : 'Enable'}
          </button>
          {deviceKey === 'spectrometer' && (
            <button type="button" onClick={() => setDeviceField('powerOn', !device.powerOn)}>
              Power {device.powerOn ? 'off' : 'on'}
            </button>
          )}
          <button type="button">Reload config</button>
          <button type="button">Restart Tango</button>
        </div>
      </section>
    </div>
  );
}

function DataBrowserWindow({
  open,
  sampleName,
  root,
  path,
  parent,
  entries,
  loading,
  error,
  selectedPath,
  topPath,
  onClose,
  onRefresh,
  onOpenPath,
  onSelectPath,
  onSetTopFolder,
  onLoadFile,
  onCreateFolder,
}) {
  if (!open) {
    return null;
  }

  return (
    <section className="pp-data-window">
      <div className="pp-device-modal-title">
        <span>Data</span>
        <button type="button" onClick={onClose}>Close</button>
      </div>
      <div className="pp-data-paths">
        <div><span>root</span>{root || 'DATA_VD'}</div>
        <div><span>current</span>{path || root || 'DATA_VD'}</div>
        <div><span>top folder</span>{topPath || 'not selected'}</div>
        {selectedPath ? <div><span>selected</span>{selectedPath}</div> : null}
      </div>
      <div className="pp-data-actions">
        <button type="button" onClick={() => onOpenPath(root)} disabled={!root || loading}>Root</button>
        <button type="button" onClick={() => onOpenPath(parent)} disabled={!parent || loading}>Up</button>
        <button type="button" onClick={onRefresh} disabled={loading}>Refresh</button>
        <button
          type="button"
          onClick={() => onSetTopFolder(path || root)}
          disabled={!(path || root) || loading}
        >
          Set top folder
        </button>
        <button
          type="button"
          onClick={() => onCreateFolder(sampleName)}
          disabled={!sampleName.trim() || loading}
        >
          New sample
        </button>
      </div>
      {error ? <div className="pp-hardware-error">{error}</div> : null}
      <div className="pp-data-list">
        {loading ? <div className="pp-data-empty">Loading...</div> : null}
        {!loading && entries.length === 0 ? <div className="pp-data-empty">Empty</div> : null}
        {!loading && entries.map((entry) => (
          <button
            type="button"
            key={entry.path}
            className={`pp-data-row ${entry.is_dir ? 'pp-data-row-dir' : ''}`}
            onDoubleClick={() => {
              if (entry.is_dir) {
                onOpenPath(entry.path);
              } else {
                onLoadFile(entry.path);
              }
            }}
            onClick={() => {
              onSelectPath(entry.path);
            }}
          >
            <strong>{entry.is_dir ? 'DIR' : 'FILE'}</strong>
            <span>{entry.name}</span>
            <small>{entry.is_file ? formatBytes(entry.size_bytes) : displayPathTail(entry.path)}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function HardwareModal({
  open,
  channels,
  devices,
  tangoServers,
  tangoStates,
  loading,
  tangoLoading,
  error,
  tangoError,
  onClose,
  onRefresh,
  onToggle,
  onBulkPower,
  onStartTango,
  onRestartTango,
}) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const channelState = (channel) => {
    const output = devices[channel.device]?.outputs?.find((item) => item.id === channel.outputId);
    return output ? Number(output.state) === 1 : null;
  };

  return (
    <div className="pp-modal-backdrop" onClick={onClose}>
      <section className="pp-hardware-modal" onClick={(event) => event.stopPropagation()}>
        <div className="pp-device-modal-title">
          <span>Hardware</span>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <div className="pp-hardware-content">
          <div className="pp-hardware-toolbar">
            <button type="button" onClick={() => onBulkPower(true)} disabled={loading}>
              Turn all necessary ON
            </button>
            <button type="button" onClick={() => onBulkPower(false)} disabled={loading}>
              Turn all OFF
            </button>
            <button type="button" onClick={onRefresh} disabled={loading}>
              Refresh
            </button>
          </div>
          {error ? <div className="pp-hardware-error">{error}</div> : null}
          {tangoError ? <div className="pp-hardware-error">{tangoError}</div> : null}
          <div className="pp-hardware-columns">
          <div className="pp-hardware-column">
            <div className="pp-hardware-section-title">NETIO</div>
            <div className="pp-hardware-list">
              {channels.map((channel) => {
                const isOn = channelState(channel);
                return (
                  <button
                    key={channel.key}
                    type="button"
                    className={`pp-hardware-toggle ${isOn ? 'pp-hardware-toggle-on' : ''}`}
                    onClick={() => onToggle(channel, !isOn)}
                    disabled={loading || isOn === null}
                  >
                    <span>{channel.label}</span>
                    <small>{channel.device} / out {channel.outputId}</small>
                    <strong>{isOn === null ? 'UNKNOWN' : (isOn ? 'ON' : 'OFF')}</strong>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="pp-hardware-column">
            <div className="pp-hardware-section-title">Tango</div>
            <div className="pp-tango-list">
              {tangoServers.map((server) => {
                const status = server.device ? tangoStates[server.device] : { state: 'NOT CONFIGURED', ok: false };
                return (
                  <div key={server.key} className={`pp-tango-row ${status?.ok ? 'pp-tango-row-ok' : ''}`}>
                    <div>
                      <span>{server.label}</span>
                      <small>{server.device || server.note}</small>
                      {status?.error ? <em>{status.error}</em> : null}
                    </div>
                    <strong>{tangoLoading ? '...' : (status?.state || 'UNKNOWN')}</strong>
                    <button
                      type="button"
                      onClick={() => onStartTango(server)}
                      disabled={!server.device || tangoLoading}
                    >
                      Start
                    </button>
                    <button
                      type="button"
                      onClick={() => onRestartTango(server)}
                      disabled={!server.device || tangoLoading}
                    >
                      Restart
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function PlotlyChart({
  data,
  layout,
  config,
  className,
  onInteraction,
  onSelected,
  onPointerEnter,
  onPointerLeave,
}) {
  const nodeRef = useRef(null);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }
    Plotly.react(node, data, layout, config).catch(() => undefined);
    return undefined;
  }, [data, layout, config]);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }

    const resize = () => {
      Plotly.Plots.resize(node);
    };
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      try {
        Plotly.purge(node);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, []);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node || !node.on) {
      return undefined;
    }
    const interactionEvents = [
      'plotly_hover',
      'plotly_unhover',
      'plotly_selecting',
      'plotly_selected',
      'plotly_relayouting',
      'plotly_relayout',
    ];
    if (onInteraction) {
      interactionEvents.forEach((eventName) => node.on(eventName, onInteraction));
    }
    if (onSelected) {
      node.on('plotly_selected', onSelected);
    }
    return () => {
      if (node.removeListener) {
        if (onInteraction) {
          interactionEvents.forEach((eventName) => {
            node.removeListener(eventName, onInteraction);
          });
        }
        if (onSelected) {
          node.removeListener('plotly_selected', onSelected);
        }
      }
    };
  }, [onInteraction, onSelected]);

  return (
    <div
      ref={nodeRef}
      className={className}
      onMouseEnter={onPointerEnter}
      onMouseLeave={onPointerLeave}
    />
  );
}

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


export { PlotPanel, SampleStageControl, DeviceConfigModal, DataBrowserWindow, HardwareModal, PlotlyChart, HeatmapSelectorChart, StageControl, SettingsPanel };
