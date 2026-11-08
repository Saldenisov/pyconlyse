import { useContext, useEffect, useState } from 'react';
import { TreatmentContext } from './DataWindowVD2';
import { fetchSelection, updateSelectionConfig } from './api/treatmentClient';
import { previewCurve } from './treatmentPreviewCurves';
import TreatmentError from './components/TreatmentError';
import { clampCursor } from "./TopSection.HEATMAP_MARGIN";
import { SelectionHeatmap } from "./TopSection.HEATMAP_MARGIN";
import { LinePlot } from "./TopSection.HEATMAP_MARGIN";
import { buildPreviewCurves } from "./TopSection.buildPreviewCurves";

import './css/TopSection.css';


const TopSection = ({ fillPanel = false }) => {
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const selectionRefreshToken = treatmentContext?.selectionRefreshToken || 0;
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;
  const comparisonCurves = treatmentContext?.comparisonCurves || [];
  const setComparisonCurves = treatmentContext?.setComparisonCurves;

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
          setError(err.message === 'Assign at least one input file before using selection tools'
            ? '' : err.message);
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
    setIsSaving(true);
    try {
      await updateSelectionConfig(treatmentSessionId, {
        active_data_type: draft.activeDataType || selection.active_data_type,
        map_index: clampCursor(draft.mapIndex, selection.map_index),
        selection: nextSelection,
      });
      setError('');
      requestSelectionRefresh?.();
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
          {error ? <><TreatmentError message={error} /><button type="button" onClick={requestSelectionRefresh}>Retry preview</button></> : (
            <p>Choose a folder or manifest, then assign input files to preview.</p>
          )}
        </div>
      );
    }

    const previewCurves = buildPreviewCurves(selection, previewRange);
    const shownKinetics = previewCurves?.kinetics || selection.kinetics;
    const shownSpectrum = previewCurves?.spectrum || selection.spectrum;
    const current = previewCurve(selection);
    const active = { ...current, kinetics: shownKinetics, spectrum: shownSpectrum };
    const pinned = comparisonCurves.some((curve) => curve.id === current.id);

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
          {setComparisonCurves && <button type="button" disabled={pinned || isSaving || Boolean(previewRange)}
            title="Keep the current kinetics and spectrum, then open another file or map to compare."
            onClick={() => setComparisonCurves((curves) => curves.some((curve) => curve.id === current.id) ? curves : [...curves, current])}>
            {pinned ? 'Curves added' : 'Add curves'}
          </button>}
        </div>
        <div className="selection-path">{selection.file_info.file_path}</div>
        {comparisonCurves.length > 0 && <div className="selection-controls" aria-label="Comparison curves">
          {comparisonCurves.map((curve) => <button type="button" key={curve.id}
            title={`${curve.path}\n${curve.ranges}`} aria-label={`Remove ${curve.label} · ${curve.ranges}`}
            onClick={() => setComparisonCurves((curves) => curves.filter((item) => item.id !== curve.id))}>
            {curve.label} ×
          </button>)}
          <button type="button" onClick={() => setComparisonCurves([])}>Clear comparison</button>
        </div>}
        <TreatmentError message={error} />
        <div className="top-plot-grid">
          <div className="left-column">
            <div className="imshow-wrapper">
              <SelectionHeatmap
                selection={selection}
                fillPanel={fillPanel}
                onSelectRange={handleHeatmapSelection}
                onPreviewRange={handleHeatmapPreview}
              />
            </div>
          </div>
          <div className="right-column">
            <div className="vertical-layout">
              <LinePlot
                className="xy-plot kinetics-plot"
                active={active}
                comparisons={comparisonCurves}
                kind="kinetics"
                title="Kinetics"
                xTitle={`Time Delay, ${shownKinetics.time_scale?.replace(/^\?+$/, '') || 'file units'}`}
              />
              <LinePlot
                className="xy-plot spectrum-plot"
                active={active}
                comparisons={comparisonCurves}
                kind="spectrum"
                title="Spectrum"
                xTitle="Wavelength, nm"
              />
            </div>
          </div>
        </div>
      </>
    );
  };

  return <div className={`top-section-container${!selection ? ' is-empty' : ''}`}>{renderContent()}</div>;
};

export default TopSection;
