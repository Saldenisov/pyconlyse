import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import { fetchSelection, updateSelectionConfig } from './api/treatmentClient';
import './css/TopSection.css';

const HEATMAP_MARGIN = { t: 14, r: 8, b: 8, l: 8 };
const HEATMAP_X_DOMAIN = [0.15, 0.83];
const HEATMAP_Y_DOMAIN = [0.18, 0.8];

function safePlot(plotNode, traces, layout, config) {
  if (!plotNode?.isConnected) {
    return Promise.resolve();
  }
  return Plotly.react(plotNode, traces, layout, config).catch(() => undefined);
}

function safeResize(plotNode) {
  if (!plotNode?.isConnected || !plotNode._fullLayout) {
    return;
  }
  try {
    Plotly.Plots.resize(plotNode);
  } catch (_error) {
    // Plotly can briefly lose internal layout while React/hot reload redraws.
  }
}

function safePurge(plotNode) {
  if (!plotNode) {
    return;
  }
  try {
    Plotly.purge(plotNode);
  } catch (_error) {
    // Ignore Plotly teardown races.
  }
}

function safeRestyle(plotNode, update) {
  if (!plotNode?.isConnected || !plotNode._fullLayout) {
    return Promise.resolve();
  }
  return Plotly.restyle(plotNode, update, [0]).catch(() => undefined);
}

function clampCursor(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    return fallback;
  }
  return parsed;
}

function interpolateValue(index, fullLength, values) {
  if (!values?.length) {
    return index;
  }
  if (values.length === 1 || fullLength <= 1) {
    return values[0];
  }

  const position = (Math.max(0, Math.min(fullLength - 1, index)) / (fullLength - 1)) *
    (values.length - 1);
  const left = Math.floor(position);
  const right = Math.min(values.length - 1, left + 1);
  const fraction = position - left;
  return values[left] + (values[right] - values[left]) * fraction;
}

function nearestFullIndex(value, fullLength, values) {
  if (!values?.length || fullLength <= 1) {
    return Math.max(0, Math.round(value || 0));
  }

  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  values.forEach((candidate, index) => {
    const distance = Math.abs(candidate - value);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });

  const ratio = values.length <= 1 ? 0 : nearestIndex / (values.length - 1);
  return Math.max(0, Math.min(fullLength - 1, Math.round(ratio * (fullLength - 1))));
}

function SelectionHeatmap({ selection, onSelectRange, onPreviewRange }) {
  const shellRef = useRef(null);
  const plotRef = useRef(null);
  const dragStateRef = useRef(null);
  const visualSelectionRef = useRef(null);
  const pendingPreviewRef = useRef(null);
  const previewFrameRef = useRef(null);
  const [metrics, setMetrics] = useState(null);
  const [visualSelection, setVisualSelection] = useState(null);

  const readPlotMetrics = useCallback((rect) => {
    const plotNode = plotRef.current;
    const xAxis = plotNode?._fullLayout?.xaxis;
    const yAxis = plotNode?._fullLayout?.yaxis;
    const xOffset = Number.isFinite(xAxis?._offset) ? xAxis._offset : HEATMAP_MARGIN.l;
    const yOffset = Number.isFinite(yAxis?._offset) ? yAxis._offset : HEATMAP_MARGIN.t;
    const innerWidth = Number.isFinite(xAxis?._length)
      ? xAxis._length
      : rect.width - HEATMAP_MARGIN.l - HEATMAP_MARGIN.r;
    const innerHeight = Number.isFinite(yAxis?._length)
      ? yAxis._length
      : rect.height - HEATMAP_MARGIN.t - HEATMAP_MARGIN.b;

    return {
      width: rect.width,
      height: rect.height,
      xOffset,
      yOffset,
      innerWidth: Math.max(1, innerWidth),
      innerHeight: Math.max(1, innerHeight),
    };
  }, []);

  useEffect(() => {
    if (dragStateRef.current) {
      return;
    }
    if (!selection?.cursors) {
      visualSelectionRef.current = null;
      setVisualSelection(null);
      return;
    }

    const nextVisualSelection = {
      x1: selection.cursors.x1,
      x2: selection.cursors.x2,
      y1: selection.cursors.y1,
      y2: selection.cursors.y2,
    };
    visualSelectionRef.current = nextVisualSelection;
    setVisualSelection(nextVisualSelection);
  }, [selection]);

  useEffect(() => () => {
    if (previewFrameRef.current) {
      window.cancelAnimationFrame(previewFrameRef.current);
    }
  }, []);

  const schedulePreview = (nextSelection) => {
    if (!onPreviewRange) {
      return;
    }

    pendingPreviewRef.current = nextSelection;
    if (previewFrameRef.current) {
      return;
    }

    previewFrameRef.current = window.requestAnimationFrame(() => {
      previewFrameRef.current = null;
      if (pendingPreviewRef.current) {
        onPreviewRange(pendingPreviewRef.current);
      }
    });
  };

  useEffect(() => {
    const shellNode = shellRef.current;
    if (!shellNode) {
      return undefined;
    }

    const updateMetrics = () => {
      const rect = shellNode.getBoundingClientRect();
      setMetrics(readPlotMetrics(rect));
    };

    updateMetrics();
    const resizeObserver = new ResizeObserver(updateMetrics);
    resizeObserver.observe(shellNode);
    return () => resizeObserver.disconnect();
  }, [readPlotMetrics]);

  const heatmapForPlot = selection?.heatmap;
  const timeScaleForPlot = selection?.kinetics?.time_scale || '';
  const updateMetricsFromShell = useCallback(() => {
    const shellNode = shellRef.current;
    if (shellNode) {
      setMetrics(readPlotMetrics(shellNode.getBoundingClientRect()));
    }
  }, [readPlotMetrics]);

  useEffect(() => {
    const plotNode = plotRef.current;
    if (!plotNode || !heatmapForPlot) {
      return undefined;
    }

    safePlot(
      plotNode,
      [
        {
          z: heatmapForPlot.z,
          x: heatmapForPlot.wavelengths,
          y: heatmapForPlot.timedelays,
          type: 'heatmap',
          colorscale: 'Viridis',
          colorbar: {
            x: 0.9,
            y: 0.49,
            len: 0.62,
            thickness: 22,
          },
        },
      ],
      {
        margin: HEATMAP_MARGIN,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#e5e7eb' },
        xaxis: {
          domain: HEATMAP_X_DOMAIN,
          title: 'Wavelength, nm',
          gridcolor: 'rgba(148, 163, 184, 0.26)',
          zerolinecolor: 'rgba(148, 163, 184, 0.35)',
          fixedrange: true,
        },
        yaxis: {
          domain: HEATMAP_Y_DOMAIN,
          title: `Time delay, ${timeScaleForPlot}`.trim(),
          gridcolor: 'rgba(148, 163, 184, 0.26)',
          zerolinecolor: 'rgba(148, 163, 184, 0.35)',
          fixedrange: true,
        },
        dragmode: false,
      },
      {
        responsive: true,
        displayModeBar: false,
        doubleClick: false,
        scrollZoom: false,
      }
    );

    const resizeObserver = new ResizeObserver(() => {
      safeResize(plotNode);
      window.requestAnimationFrame(updateMetricsFromShell);
    });
    resizeObserver.observe(plotNode);

    window.requestAnimationFrame(updateMetricsFromShell);

    return () => {
      resizeObserver.disconnect();
      safePurge(plotNode);
    };
  }, [
    heatmapForPlot,
    readPlotMetrics,
    timeScaleForPlot,
    updateMetricsFromShell,
  ]);

  const getClampedLocalPoint = (event) => {
    const shellNode = shellRef.current;
    if (!shellNode) {
      return null;
    }

    const rect = shellNode.getBoundingClientRect();
    const plotMetrics = readPlotMetrics(rect);
    const { xOffset, yOffset, innerWidth, innerHeight } = plotMetrics;
    if (innerWidth <= 0 || innerHeight <= 0) {
      return null;
    }

    const localX = Math.min(
      Math.max(event.clientX - rect.left, xOffset),
      xOffset + innerWidth
    );
    const localY = Math.min(
      Math.max(event.clientY - rect.top, yOffset),
      yOffset + innerHeight
    );

    return {
      localX,
      localY,
      xOffset,
      yOffset,
      innerWidth,
      innerHeight,
      rectWidth: rect.width,
      rectHeight: rect.height,
    };
  };

  const normalizeSelectionIndexes = (nextSelection) => {
    const xLength = selection?.file_info?.wavelengths_length || 0;
    const yLength = selection?.file_info?.timedelays_length || 0;
    if (xLength === 0 || yLength === 0) {
      return null;
    }

    const normalizePair = (start, end, length) => {
      let left = Math.max(0, Math.min(length - 1, start));
      let right = Math.max(0, Math.min(length - 1, end));
      if (left > right) {
        [left, right] = [right, left];
      }
      if (left === right) {
        if (right < length - 1) {
          right += 1;
        } else if (left > 0) {
          left -= 1;
        }
      }
      return [left, right];
    };

    const [x1, x2] = normalizePair(nextSelection.x1, nextSelection.x2, xLength);
    const [y1, y2] = normalizePair(nextSelection.y1, nextSelection.y2, yLength);
    return { x1, x2, y1, y2 };
  };

  const xIndexFromPoint = (point) => {
    const xLength = selection?.file_info?.wavelengths_length || 0;
    if (xLength === 0 || !point) {
      return 0;
    }

    const xAxis = plotRef.current?._fullLayout?.xaxis;
    const xValues = selection?.heatmap?.wavelengths || [];
    if (xAxis?.p2l && xValues.length > 0) {
      return nearestFullIndex(xAxis.p2l(point.localX - point.xOffset), xLength, xValues);
    }

    const ratio = (point.localX - point.xOffset) / Math.max(1, point.innerWidth);
    return Math.round(Math.max(0, Math.min(1, ratio)) * (xLength - 1));
  };

  const yIndexFromPoint = (point) => {
    const yLength = selection?.file_info?.timedelays_length || 0;
    if (yLength === 0 || !point) {
      return 0;
    }

    const yAxis = plotRef.current?._fullLayout?.yaxis;
    const yValues = selection?.heatmap?.timedelays || [];
    if (yAxis?.p2l && yValues.length > 0) {
      return nearestFullIndex(yAxis.p2l(point.localY - point.yOffset), yLength, yValues);
    }

    const ratio = (point.localY - point.yOffset) / Math.max(1, point.innerHeight);
    return Math.round((1 - Math.max(0, Math.min(1, ratio))) * (yLength - 1));
  };

  const clampMovedRange = (start, end, delta, length) => {
    const width = Math.max(1, end - start);
    const nextStart = Math.max(0, Math.min(length - 1 - width, start + delta));
    return [nextStart, nextStart + width];
  };

  const handleRegionPointerDown = (event, axis, mode) => {
    if (event.button !== 0) {
      return;
    }

    event.preventDefault();
    const point = getClampedLocalPoint(event);
    if (!point) {
      return;
    }

    const startSelection = visualSelection || {
      x1: selection.cursors.x1,
      x2: selection.cursors.x2,
      y1: selection.cursors.y1,
      y2: selection.cursors.y2,
    };

    const captureTarget = event.currentTarget;
    dragStateRef.current = {
      axis,
      mode,
      point,
      pointerId: event.pointerId,
      captureTarget,
      selection: startSelection,
      startXIndex: xIndexFromPoint(point),
      startYIndex: yIndexFromPoint(point),
    };
    captureTarget.setPointerCapture?.(event.pointerId);
  };

  const handlePointerMove = (event) => {
    if (!dragStateRef.current) {
      return;
    }

    const point = getClampedLocalPoint(event);
    if (!point) {
      return;
    }

    const dragState = dragStateRef.current;
    const startSelection = dragState.selection;
    const xLength = selection?.file_info?.wavelengths_length || 0;
    const yLength = selection?.file_info?.timedelays_length || 0;
    let nextSelection = { ...startSelection };

    if (dragState.axis === 'x') {
      const nextIndex = xIndexFromPoint(point);
      if (dragState.mode === 'start') {
        nextSelection.x1 = nextIndex;
      } else if (dragState.mode === 'end') {
        nextSelection.x2 = nextIndex;
      } else {
        const [x1, x2] = clampMovedRange(
          startSelection.x1,
          startSelection.x2,
          nextIndex - dragState.startXIndex,
          xLength
        );
        nextSelection.x1 = x1;
        nextSelection.x2 = x2;
      }
    } else {
      const nextIndex = yIndexFromPoint(point);
      if (dragState.mode === 'start') {
        nextSelection.y1 = nextIndex;
      } else if (dragState.mode === 'end') {
        nextSelection.y2 = nextIndex;
      } else {
        const [y1, y2] = clampMovedRange(
          startSelection.y1,
          startSelection.y2,
          nextIndex - dragState.startYIndex,
          yLength
        );
        nextSelection.y1 = y1;
        nextSelection.y2 = y2;
      }
    }

    const normalizedSelection = normalizeSelectionIndexes(nextSelection);
    if (normalizedSelection) {
      visualSelectionRef.current = normalizedSelection;
      setVisualSelection(normalizedSelection);
      schedulePreview(normalizedSelection);
    }
  };

  const finishDrag = (event) => {
    const dragState = dragStateRef.current;
    if (!dragState) {
      return;
    }

    const captureTarget = dragState.captureTarget;
    if (
      captureTarget?.hasPointerCapture?.(dragState.pointerId) &&
      (!event?.pointerId || event.pointerId === dragState.pointerId)
    ) {
      captureTarget.releasePointerCapture(dragState.pointerId);
    }
    dragStateRef.current = null;

    const nextSelection = normalizeSelectionIndexes(
      visualSelectionRef.current || visualSelection || selection.cursors
    );
    if (nextSelection && onSelectRange) {
      onSelectRange(nextSelection);
    }
  };

  useEffect(() => {
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', finishDrag);
    window.addEventListener('pointercancel', finishDrag);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', finishDrag);
      window.removeEventListener('pointercancel', finishDrag);
    };
  });

  const valueToX = (value) => {
    const xLength = selection?.file_info?.wavelengths_length || 0;
    if (!metrics || xLength === 0) {
      return HEATMAP_MARGIN.l;
    }
    if (xLength <= 1) {
      return metrics.xOffset;
    }
    const xAxis = plotRef.current?._fullLayout?.xaxis;
    if (xAxis?.l2p) {
      return metrics.xOffset + xAxis.l2p(
        interpolateValue(value, xLength, selection?.heatmap?.wavelengths || [])
      );
    }
    return metrics.xOffset + (value / (xLength - 1)) * metrics.innerWidth;
  };

  const valueToY = (value) => {
    const yLength = selection?.file_info?.timedelays_length || 0;
    if (!metrics || yLength === 0) {
      return HEATMAP_MARGIN.t;
    }
    if (yLength <= 1) {
      return metrics.yOffset;
    }
    const yAxis = plotRef.current?._fullLayout?.yaxis;
    if (yAxis?.l2p) {
      return metrics.yOffset + yAxis.l2p(
        interpolateValue(value, yLength, selection?.heatmap?.timedelays || [])
      );
    }
    return metrics.yOffset + (1 - value / (yLength - 1)) * metrics.innerHeight;
  };

  const buildRegionStyle = () => {
    if (!metrics || !visualSelection) {
      return null;
    }

    const xStart = valueToX(visualSelection.x1);
    const xEnd = valueToX(visualSelection.x2);
    const yStart = valueToY(visualSelection.y1);
    const yEnd = valueToY(visualSelection.y2);

    return {
      x: {
        left: Math.min(xStart, xEnd),
        top: metrics.yOffset,
        width: Math.max(6, Math.abs(xEnd - xStart)),
        height: metrics.innerHeight,
      },
      y: {
        left: metrics.xOffset,
        top: Math.min(yStart, yEnd),
        width: metrics.innerWidth,
        height: Math.max(6, Math.abs(yEnd - yStart)),
      },
    };
  };

  const regionStyle = buildRegionStyle();

  return (
    <div className="selection-heatmap-shell" ref={shellRef}>
      <div className="imshow-graph" ref={plotRef}></div>
      <div
        className="selection-overlay"
        onPointerMove={handlePointerMove}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
      >
        {regionStyle && (
          <>
            <div
              className="selection-region selection-region-x"
              style={{
                left: `${regionStyle.x.left}px`,
                top: `${regionStyle.x.top}px`,
                width: `${regionStyle.x.width}px`,
                height: `${regionStyle.x.height}px`,
              }}
              onPointerDown={(event) => handleRegionPointerDown(event, 'x', 'move')}
            >
              <span
                className="selection-region-handle selection-region-handle-start"
                onPointerDown={(event) => {
                  event.stopPropagation();
                  handleRegionPointerDown(event, 'x', 'start');
                }}
              />
              <span
                className="selection-region-handle selection-region-handle-end"
                onPointerDown={(event) => {
                  event.stopPropagation();
                  handleRegionPointerDown(event, 'x', 'end');
                }}
              />
            </div>
            <div
              className="selection-region selection-region-y"
              style={{
                left: `${regionStyle.y.left}px`,
                top: `${regionStyle.y.top}px`,
                width: `${regionStyle.y.width}px`,
                height: `${regionStyle.y.height}px`,
              }}
              onPointerDown={(event) => handleRegionPointerDown(event, 'y', 'move')}
            >
              <span
                className="selection-region-handle selection-region-handle-start"
                onPointerDown={(event) => {
                  event.stopPropagation();
                  handleRegionPointerDown(event, 'y', 'end');
                }}
              />
              <span
                className="selection-region-handle selection-region-handle-end"
                onPointerDown={(event) => {
                  event.stopPropagation();
                  handleRegionPointerDown(event, 'y', 'start');
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function LinePlot({ x, y, title, xTitle, className }) {
  const ref = useRef(null);

  useEffect(() => {
    const plotNode = ref.current;
    if (!plotNode) {
      return undefined;
    }

    safePlot(
      plotNode,
      [
        {
          x: [],
          y: [],
          type: 'scatter',
          mode: 'lines',
          line: { color: '#dc2626', width: 2 },
        },
      ],
      {
        margin: { t: 28, r: 16, b: 40, l: 48 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#e5e7eb' },
        title,
        xaxis: {
          title: xTitle,
          gridcolor: 'rgba(148, 163, 184, 0.26)',
          zerolinecolor: 'rgba(148, 163, 184, 0.35)',
        },
        yaxis: {
          title: 'Intensity',
          gridcolor: 'rgba(148, 163, 184, 0.26)',
          zerolinecolor: 'rgba(148, 163, 184, 0.35)',
        },
      },
      { responsive: true, displayModeBar: false }
    );

    const resizeObserver = new ResizeObserver(() => {
      safeResize(plotNode);
    });
    resizeObserver.observe(plotNode);

    return () => {
      resizeObserver.disconnect();
      safePurge(plotNode);
    };
  }, [className, title, xTitle]);

  useEffect(() => {
    const plotNode = ref.current;
    if (!plotNode) {
      return;
    }
    safeRestyle(plotNode, { x: [x], y: [y] });
  }, [x, y]);

  return <div className={className} ref={ref}></div>;
}

function clampSampleIndex(fullIndex, fullLength, sampleLength) {
  if (sampleLength <= 1 || fullLength <= 1) {
    return 0;
  }
  const ratio = Math.max(0, Math.min(1, fullIndex / (fullLength - 1)));
  return Math.round(ratio * (sampleLength - 1));
}

function mean(values) {
  const finiteValues = values.filter((value) => Number.isFinite(value));
  if (finiteValues.length === 0) {
    return null;
  }
  return finiteValues.reduce((total, value) => total + value, 0) / finiteValues.length;
}

function buildPreviewCurves(selection, selectedRange) {
  const z = selection?.heatmap?.z || [];
  const wavelengths = selection?.heatmap?.wavelengths || [];
  const timedelays = selection?.heatmap?.timedelays || [];
  const xLength = selection?.file_info?.wavelengths_length || wavelengths.length;
  const yLength = selection?.file_info?.timedelays_length || timedelays.length;

  if (!selectedRange || z.length === 0 || wavelengths.length === 0 || timedelays.length === 0) {
    return null;
  }

  const x1 = clampSampleIndex(selectedRange.x1, xLength, wavelengths.length);
  const x2 = clampSampleIndex(selectedRange.x2, xLength, wavelengths.length);
  const y1 = clampSampleIndex(selectedRange.y1, yLength, timedelays.length);
  const y2 = clampSampleIndex(selectedRange.y2, yLength, timedelays.length);
  const xStart = Math.min(x1, x2);
  const xEnd = Math.max(x1, x2);
  const yStart = Math.min(y1, y2);
  const yEnd = Math.max(y1, y2);

  const kinetics = z.map((row) => mean((row || []).slice(xStart, xEnd + 1)) ?? 0);
  const spectrum = wavelengths.map((_, colIndex) => {
    const values = [];
    for (let rowIndex = yStart; rowIndex <= yEnd; rowIndex += 1) {
      values.push(z[rowIndex]?.[colIndex]);
    }
    return mean(values) ?? 0;
  });

  return {
    kinetics: {
      x: timedelays,
      y: kinetics,
      time_scale: selection.kinetics?.time_scale || '',
    },
    spectrum: {
      x: wavelengths,
      y: spectrum,
    },
  };
}

const TopSection = () => {
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const selectionRefreshToken = treatmentContext?.selectionRefreshToken || 0;
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;

  const [selection, setSelection] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [previewRange, setPreviewRange] = useState(null);
  const [draft, setDraft] = useState({
    activeDataType: '',
    mapIndex: 0,
    x1: 0,
    x2: 1,
    y1: 0,
    y2: 1,
  });

  useEffect(() => {
    let cancelled = false;

    setIsLoading(true);
    fetchSelection(treatmentSessionId)
      .then((payload) => {
        if (cancelled) {
          return;
        }

        const nextSelection = payload.selection;
        setSelection(nextSelection);
        setDraft({
          activeDataType: nextSelection.active_data_type,
          mapIndex: nextSelection.map_index,
          x1: nextSelection.cursors.x1,
          x2: nextSelection.cursors.x2,
          y1: nextSelection.cursors.y1,
          y2: nextSelection.cursors.y2,
        });
        setPreviewRange(null);
        setError('');
      })
      .catch((err) => {
        if (!cancelled) {
          setSelection(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectionRefreshToken, treatmentSessionId]);

  const applySelection = async () => {
    setIsSaving(true);
    try {
      await updateSelectionConfig(treatmentSessionId, {
        active_data_type: draft.activeDataType,
        map_index: clampCursor(draft.mapIndex, 0),
        selection: {
          x1: clampCursor(draft.x1, 0),
          x2: clampCursor(draft.x2, 1),
          y1: clampCursor(draft.y1, 0),
          y2: clampCursor(draft.y2, 1),
        },
      });
      setError('');
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleHeatmapSelection = async (nextSelection) => {
    if (!selection) {
      return;
    }

    setPreviewRange(null);
    setDraft((current) => ({
      ...current,
      x1: nextSelection.x1,
      x2: nextSelection.x2,
      y1: nextSelection.y1,
      y2: nextSelection.y2,
    }));
    setSelection((current) =>
      current
        ? {
            ...current,
            cursors: nextSelection,
          }
        : current
    );

    setIsSaving(true);
    try {
      await updateSelectionConfig(treatmentSessionId, {
        active_data_type: draft.activeDataType || selection.active_data_type,
        map_index: clampCursor(draft.mapIndex, selection.map_index),
        selection: nextSelection,
      });
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleHeatmapPreview = (nextSelection) => {
    setPreviewRange(nextSelection);
    setDraft((current) => ({
      ...current,
      x1: nextSelection.x1,
      x2: nextSelection.x2,
      y1: nextSelection.y1,
      y2: nextSelection.y2,
    }));
  };

  const stepMap = async (direction) => {
    if (!selection) {
      return;
    }

    const nextMapIndex = Math.max(
      0,
      Math.min(
        selection.file_info.number_maps - 1,
        clampCursor(draft.mapIndex, selection.map_index) + direction
      )
    );

    setDraft((current) => ({
      ...current,
      mapIndex: String(nextMapIndex),
    }));

    setIsSaving(true);
    try {
      await updateSelectionConfig(treatmentSessionId, {
        active_data_type: draft.activeDataType,
        map_index: nextMapIndex,
        selection: {
          x1: clampCursor(draft.x1, 0),
          x2: clampCursor(draft.x2, 1),
          y1: clampCursor(draft.y1, 0),
          y2: clampCursor(draft.y2, 1),
        },
      });
      setError('');
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const renderContent = () => {
    if (isLoading) {
      return <p>Loading selection preview...</p>;
    }

    if (!selection) {
      return (
        <div style={{ padding: '16px' }}>
          <p>{error || 'Assign an input file in the Files tab to start previewing treatment data.'}</p>
        </div>
      );
    }

    const previewCurves = buildPreviewCurves(selection, previewRange);
    const shownKinetics = previewCurves?.kinetics || selection.kinetics;
    const shownSpectrum = previewCurves?.spectrum || selection.spectrum;

    return (
      <>
        <div className="selection-controls">
          <label>
            Data
            <select
              value={draft.activeDataType}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  activeDataType: event.target.value,
                }))
              }
            >
              {selection.assigned_data_types.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Map
            <input
              type="number"
              min="0"
              max={Math.max(0, selection.file_info.number_maps - 1)}
              value={draft.mapIndex}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  mapIndex: event.target.value,
                }))
              }
            />
          </label>
          <button
            onClick={() => stepMap(-1)}
            disabled={isSaving || selection.file_info.number_maps <= 1}
          >
            Prev
          </button>
          <button
            onClick={() => stepMap(1)}
            disabled={isSaving || selection.file_info.number_maps <= 1}
          >
            Next
          </button>
          <button onClick={applySelection} disabled={isSaving}>
            {isSaving ? 'Applying...' : 'Apply'}
          </button>
        </div>
        <div className="selection-path">{selection.file_info.file_path}</div>
        {error && <p>{error}</p>}
        <div className="top-plot-grid">
          <div className="left-column">
            <div className="imshow-wrapper">
              <SelectionHeatmap
                selection={selection}
                onSelectRange={handleHeatmapSelection}
                onPreviewRange={handleHeatmapPreview}
              />
            </div>
          </div>
          <div className="right-column">
            <div className="vertical-layout">
              <LinePlot
                className="xy-plot kinetics-plot"
                x={shownKinetics.x}
                y={shownKinetics.y}
                title="Kinetics"
                xTitle={`Time Delay, ${shownKinetics.time_scale || ''}`.trim()}
              />
              <LinePlot
                className="xy-plot spectrum-plot"
                x={shownSpectrum.x}
                y={shownSpectrum.y}
                title="Spectrum"
                xTitle="Wavelength, nm"
              />
            </div>
          </div>
        </div>
      </>
    );
  };

  return <div className="top-section-container">{renderContent()}</div>;
};

export default TopSection;
