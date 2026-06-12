import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import { fetchSelection, updateSelectionConfig } from './api/treatmentClient';
import './css/TopSection.css';

const HEATMAP_MARGIN = { t: 24, r: 16, b: 48, l: 56 };

function clampCursor(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    return fallback;
  }
  return parsed;
}

function findClosestIndex(values, target) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }

  let bestIndex = 0;
  let bestDistance = Math.abs(values[0] - target);

  for (let index = 1; index < values.length; index += 1) {
    const distance = Math.abs(values[index] - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  }

  return bestIndex;
}

function interpolate(fromValue, toValue, ratio) {
  return fromValue + (toValue - fromValue) * ratio;
}

function SelectionHeatmap({ selection, onSelectRange }) {
  const shellRef = useRef(null);
  const plotRef = useRef(null);
  const dragStateRef = useRef(null);
  const visualSelectionRef = useRef(null);
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

  useEffect(() => {
    const plotNode = plotRef.current;
    if (!plotNode || !selection) {
      return undefined;
    }

    const { heatmap, kinetics } = selection;

    Plotly.newPlot(
      plotNode,
      [
        {
          z: heatmap.z,
          x: heatmap.wavelengths,
          y: heatmap.timedelays,
          type: 'heatmap',
          colorscale: 'Viridis',
        },
      ],
      {
        margin: HEATMAP_MARGIN,
        xaxis: { title: 'Wavelength, nm' },
        yaxis: { title: `Time delay, ${kinetics.time_scale || ''}`.trim() },
      },
      { responsive: true, displayModeBar: false }
    );

    const resizeObserver = new ResizeObserver(() => {
      Plotly.Plots.resize(plotNode);
      window.requestAnimationFrame(() => {
        const shellNode = shellRef.current;
        if (shellNode) {
          setMetrics(readPlotMetrics(shellNode.getBoundingClientRect()));
        }
      });
    });
    resizeObserver.observe(plotNode);

    window.requestAnimationFrame(() => {
      const shellNode = shellRef.current;
      if (shellNode) {
        setMetrics(readPlotMetrics(shellNode.getBoundingClientRect()));
      }
    });

    return () => {
      resizeObserver.disconnect();
      Plotly.purge(plotNode);
    };
  }, [readPlotMetrics, selection]);

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
    const wavelengths = selection?.heatmap?.wavelengths || [];
    const timedelays = selection?.heatmap?.timedelays || [];
    if (wavelengths.length === 0 || timedelays.length === 0) {
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

    const [x1, x2] = normalizePair(nextSelection.x1, nextSelection.x2, wavelengths.length);
    const [y1, y2] = normalizePair(nextSelection.y1, nextSelection.y2, timedelays.length);
    return { x1, x2, y1, y2 };
  };

  const xIndexFromPoint = (point) => {
    const wavelengths = selection?.heatmap?.wavelengths || [];
    if (wavelengths.length === 0 || !point) {
      return 0;
    }

    const xMin = Math.min(wavelengths[0], wavelengths[wavelengths.length - 1]);
    const xMax = Math.max(wavelengths[0], wavelengths[wavelengths.length - 1]);
    const ratio = (point.localX - point.xOffset) / Math.max(1, point.innerWidth);
    return findClosestIndex(wavelengths, interpolate(xMin, xMax, ratio));
  };

  const yIndexFromPoint = (point) => {
    const timedelays = selection?.heatmap?.timedelays || [];
    if (timedelays.length === 0 || !point) {
      return 0;
    }

    const yMin = Math.min(timedelays[0], timedelays[timedelays.length - 1]);
    const yMax = Math.max(timedelays[0], timedelays[timedelays.length - 1]);
    const ratio = (point.localY - point.yOffset) / Math.max(1, point.innerHeight);
    return findClosestIndex(timedelays, interpolate(yMin, yMax, 1 - ratio));
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

    dragStateRef.current = {
      axis,
      mode,
      point,
      selection: startSelection,
      startXIndex: xIndexFromPoint(point),
      startYIndex: yIndexFromPoint(point),
    };
    event.currentTarget.setPointerCapture(event.pointerId);
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
    const wavelengths = selection?.heatmap?.wavelengths || [];
    const timedelays = selection?.heatmap?.timedelays || [];
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
          wavelengths.length
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
          timedelays.length
        );
        nextSelection.y1 = y1;
        nextSelection.y2 = y2;
      }
    }

    const normalizedSelection = normalizeSelectionIndexes(nextSelection);
    if (normalizedSelection) {
      visualSelectionRef.current = normalizedSelection;
      setVisualSelection(normalizedSelection);
    }
  };

  const finishDrag = (event) => {
    if (!dragStateRef.current) {
      return;
    }

    dragStateRef.current = null;

    const nextSelection = normalizeSelectionIndexes(
      visualSelectionRef.current || visualSelection || selection.cursors
    );
    if (nextSelection && onSelectRange) {
      onSelectRange(nextSelection);
    }
  };

  const valueToX = (value) => {
    const wavelengths = selection?.heatmap?.wavelengths || [];
    if (!metrics || wavelengths.length === 0) {
      return HEATMAP_MARGIN.l;
    }
    const xMin = Math.min(wavelengths[0], wavelengths[wavelengths.length - 1]);
    const xMax = Math.max(wavelengths[0], wavelengths[wavelengths.length - 1]);
    if (xMax === xMin) {
      return metrics.xOffset;
    }
    return metrics.xOffset + ((value - xMin) / (xMax - xMin)) * metrics.innerWidth;
  };

  const valueToY = (value) => {
    const timedelays = selection?.heatmap?.timedelays || [];
    if (!metrics || timedelays.length === 0) {
      return HEATMAP_MARGIN.t;
    }
    const yMin = Math.min(timedelays[0], timedelays[timedelays.length - 1]);
    const yMax = Math.max(timedelays[0], timedelays[timedelays.length - 1]);
    if (yMax === yMin) {
      return metrics.yOffset;
    }
    return metrics.yOffset + (1 - (value - yMin) / (yMax - yMin)) * metrics.innerHeight;
  };

  const buildRegionStyle = () => {
    if (!metrics || !visualSelection) {
      return null;
    }

    const wavelengths = selection?.heatmap?.wavelengths || [];
    const timedelays = selection?.heatmap?.timedelays || [];
    const xStart = valueToX(wavelengths[visualSelection.x1]);
    const xEnd = valueToX(wavelengths[visualSelection.x2]);
    const yStart = valueToY(timedelays[visualSelection.y1]);
    const yEnd = valueToY(timedelays[visualSelection.y2]);

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
                  handleRegionPointerDown(event, 'y', 'start');
                }}
              />
              <span
                className="selection-region-handle selection-region-handle-end"
                onPointerDown={(event) => {
                  event.stopPropagation();
                  handleRegionPointerDown(event, 'y', 'end');
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

    Plotly.newPlot(
      plotNode,
      [
        {
          x,
          y,
          type: 'scatter',
          mode: 'lines',
          line: { color: '#dc2626', width: 2 },
        },
      ],
      {
        margin: { t: 28, r: 16, b: 40, l: 48 },
        title,
        xaxis: { title: xTitle },
        yaxis: { title: 'Intensity' },
      },
      { responsive: true, displayModeBar: false }
    );

    const resizeObserver = new ResizeObserver(() => {
      Plotly.Plots.resize(plotNode);
    });
    resizeObserver.observe(plotNode);

    return () => {
      resizeObserver.disconnect();
      Plotly.purge(plotNode);
    };
  }, [className, title, x, xTitle, y]);

  return <div className={className} ref={ref}></div>;
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

    setDraft((current) => ({
      ...current,
      x1: nextSelection.x1,
      x2: nextSelection.x2,
      y1: nextSelection.y1,
      y2: nextSelection.y2,
    }));

    setIsSaving(true);
    try {
      await updateSelectionConfig(treatmentSessionId, {
        active_data_type: draft.activeDataType || selection.active_data_type,
        map_index: clampCursor(draft.mapIndex, selection.map_index),
        selection: nextSelection,
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
              />
            </div>
          </div>
          <div className="right-column">
            <div className="vertical-layout">
              <LinePlot
                className="xy-plot kinetics-plot"
                x={selection.kinetics.x}
                y={selection.kinetics.y}
                title="Kinetics"
                xTitle={`Time Delay, ${selection.kinetics.time_scale || ''}`.trim()}
              />
              <LinePlot
                className="xy-plot spectrum-plot"
                x={selection.spectrum.x}
                y={selection.spectrum.y}
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
