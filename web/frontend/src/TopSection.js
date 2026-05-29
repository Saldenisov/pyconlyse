import React, { useContext, useEffect, useRef, useState } from 'react';
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
  const [dragRect, setDragRect] = useState(null);

  useEffect(() => {
    const plotNode = plotRef.current;
    if (!plotNode || !selection) {
      return undefined;
    }

    const { heatmap, cursors, kinetics } = selection;

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
        shapes: [
          {
            type: 'line',
            x0: cursors.x1_value,
            x1: cursors.x1_value,
            y0: heatmap.timedelays[0],
            y1: heatmap.timedelays[heatmap.timedelays.length - 1],
            line: { color: '#ef4444', width: 2 },
          },
          {
            type: 'line',
            x0: cursors.x2_value,
            x1: cursors.x2_value,
            y0: heatmap.timedelays[0],
            y1: heatmap.timedelays[heatmap.timedelays.length - 1],
            line: { color: '#ef4444', width: 2 },
          },
          {
            type: 'line',
            x0: heatmap.wavelengths[0],
            x1: heatmap.wavelengths[heatmap.wavelengths.length - 1],
            y0: cursors.y1_value,
            y1: cursors.y1_value,
            line: { color: '#f97316', width: 2 },
          },
          {
            type: 'line',
            x0: heatmap.wavelengths[0],
            x1: heatmap.wavelengths[heatmap.wavelengths.length - 1],
            y0: cursors.y2_value,
            y1: cursors.y2_value,
            line: { color: '#f97316', width: 2 },
          },
        ],
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
  }, [selection]);

  const getClampedLocalPoint = (event) => {
    const shellNode = shellRef.current;
    if (!shellNode) {
      return null;
    }

    const rect = shellNode.getBoundingClientRect();
    const innerWidth = rect.width - HEATMAP_MARGIN.l - HEATMAP_MARGIN.r;
    const innerHeight = rect.height - HEATMAP_MARGIN.t - HEATMAP_MARGIN.b;
    if (innerWidth <= 0 || innerHeight <= 0) {
      return null;
    }

    const localX = Math.min(
      Math.max(event.clientX - rect.left, HEATMAP_MARGIN.l),
      rect.width - HEATMAP_MARGIN.r
    );
    const localY = Math.min(
      Math.max(event.clientY - rect.top, HEATMAP_MARGIN.t),
      rect.height - HEATMAP_MARGIN.b
    );

    return {
      localX,
      localY,
      innerWidth,
      innerHeight,
      rectWidth: rect.width,
      rectHeight: rect.height,
    };
  };

  const toSelectionIndexes = (startPoint, endPoint) => {
    const wavelengths = selection?.heatmap?.wavelengths || [];
    const timedelays = selection?.heatmap?.timedelays || [];
    if (wavelengths.length === 0 || timedelays.length === 0) {
      return null;
    }

    const xMin = Math.min(wavelengths[0], wavelengths[wavelengths.length - 1]);
    const xMax = Math.max(wavelengths[0], wavelengths[wavelengths.length - 1]);
    const yMin = Math.min(timedelays[0], timedelays[timedelays.length - 1]);
    const yMax = Math.max(timedelays[0], timedelays[timedelays.length - 1]);

    const startXRatio =
      (startPoint.localX - HEATMAP_MARGIN.l) / Math.max(1, startPoint.innerWidth);
    const endXRatio =
      (endPoint.localX - HEATMAP_MARGIN.l) / Math.max(1, endPoint.innerWidth);
    const startYRatio =
      (startPoint.localY - HEATMAP_MARGIN.t) / Math.max(1, startPoint.innerHeight);
    const endYRatio =
      (endPoint.localY - HEATMAP_MARGIN.t) / Math.max(1, endPoint.innerHeight);

    const startXValue = interpolate(xMin, xMax, startXRatio);
    const endXValue = interpolate(xMin, xMax, endXRatio);
    const startYValue = interpolate(yMin, yMax, 1 - startYRatio);
    const endYValue = interpolate(yMin, yMax, 1 - endYRatio);

    const x1 = findClosestIndex(wavelengths, startXValue);
    const x2 = findClosestIndex(wavelengths, endXValue);
    const y1 = findClosestIndex(timedelays, startYValue);
    const y2 = findClosestIndex(timedelays, endYValue);

    return {
      x1: Math.min(x1, x2),
      x2: Math.max(x1, x2),
      y1: Math.min(y1, y2),
      y2: Math.max(y1, y2),
    };
  };

  const handlePointerDown = (event) => {
    if (event.button !== 0) {
      return;
    }

    const point = getClampedLocalPoint(event);
    if (!point) {
      return;
    }

    dragStateRef.current = point;
    setDragRect({
      left: point.localX,
      top: point.localY,
      width: 1,
      height: 1,
    });

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

    const startPoint = dragStateRef.current;
    setDragRect({
      left: Math.min(startPoint.localX, point.localX),
      top: Math.min(startPoint.localY, point.localY),
      width: Math.max(1, Math.abs(point.localX - startPoint.localX)),
      height: Math.max(1, Math.abs(point.localY - startPoint.localY)),
    });
  };

  const finishDrag = (event) => {
    if (!dragStateRef.current) {
      return;
    }

    const startPoint = dragStateRef.current;
    const endPoint = getClampedLocalPoint(event) || startPoint;
    dragStateRef.current = null;
    setDragRect(null);

    const nextSelection = toSelectionIndexes(startPoint, endPoint);
    if (nextSelection && onSelectRange) {
      onSelectRange(nextSelection);
    }
  };

  return (
    <div className="selection-heatmap-shell" ref={shellRef}>
      <div className="imshow-graph" ref={plotRef}></div>
      <div
        className="selection-overlay"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
      >
        {dragRect && (
          <div
            className="selection-rect"
            style={{
              left: `${dragRect.left}px`,
              top: `${dragRect.top}px`,
              width: `${dragRect.width}px`,
              height: `${dragRect.height}px`,
            }}
          />
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
          <label>
            x1
            <input
              type="number"
              min="0"
              max={Math.max(0, selection.file_info.wavelengths_length - 1)}
              value={draft.x1}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  x1: event.target.value,
                }))
              }
            />
          </label>
          <label>
            x2
            <input
              type="number"
              min="0"
              max={Math.max(0, selection.file_info.wavelengths_length - 1)}
              value={draft.x2}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  x2: event.target.value,
                }))
              }
            />
          </label>
          <label>
            y1
            <input
              type="number"
              min="0"
              max={Math.max(0, selection.file_info.timedelays_length - 1)}
              value={draft.y1}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  y1: event.target.value,
                }))
              }
            />
          </label>
          <label>
            y2
            <input
              type="number"
              min="0"
              max={Math.max(0, selection.file_info.timedelays_length - 1)}
              value={draft.y2}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  y2: event.target.value,
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
