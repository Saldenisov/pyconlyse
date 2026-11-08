import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist';
import { stitchRegionsToShapes } from "./TabsControl.PROFILE_PRESETS";
import { shapesToStitchRegions } from "./TabsControl.PROFILE_PRESETS";

function roleSelectionStatus(session, dataType) {
  const selections =
    session?.map_selections ||
    session?.map_selection ||
    session?.cleaning_selections ||
    {};
  const selection = selections?.[dataType];

  if (!selection || typeof selection !== 'object') {
    return null;
  }

  const included = Number(selection.included_count ?? selection.included ?? selection.kept_count);
  const total = Number(selection.total_count ?? selection.total ?? selection.original_count);
  const isApplied = selection.applied ?? selection.persisted ?? selection.saved;
  const method = String(selection.method || '').trim().toLowerCase();

  return {
    included: Number.isFinite(included) ? included : null,
    total: Number.isFinite(total) ? total : null,
    isApplied: typeof isApplied === 'boolean' ? isApplied : null,
    method,
  };
}

function backendCleaningPreview(session) {
  const preview = session?.cleaning_preview;
  if (!preview?.ready) {
    return null;
  }

  const paths = session?.paths || {};
  const sources = session?.path_sources || {};
  const requestedType = String(preview.data_type || '').trim();
  const dataType =
    (requestedType && paths[requestedType] && requestedType) ||
    Object.keys(paths).find(
      (role) => paths[role] === preview.file_path || sources[role] === preview.file_path
    );

  if (!dataType) {
    return null;
  }

  return {
    dataType,
    sourcePath: sources[dataType] || paths[dataType] || '',
    backend: true,
    stale: true,
    invalidated: true,
    sourceMeasurements: preview.source_measurements,
    cleanedMeasurements: preview.cleaned_measurements,
  };
}

function MapSelectionStatus({ selection }) {
  if (!selection) {
    return null;
  }

  const hasCounts = selection.included !== null && selection.total !== null;
  const allMapsIncluded =
    hasCounts && selection.included === selection.total &&
    (selection.method === 'all' || selection.isApplied === false);
  const text = allMapsIncluded
    ? 'Raw · all maps included'
    : hasCounts
      ? `${selection.included} / ${selection.total} maps included${selection.isApplied === true ? ' · Applied mask' : ''}`
      : selection.isApplied === false
        ? 'No persisted H5 map selection'
        : 'Map selection available';

  return (
    <small className={`assigned-path-selection ${selection.isApplied === false && !allMapsIncluded ? 'is-pending' : ''}`}>
      {text}
    </small>
  );
}

const AssignedPaths = ({ session }) => {
  const paths = session.paths || {};
  const dataPaths = ['ABS', 'BASE', 'ABS+BASE', 'ABS+BASE+NOISE']
    .filter((dataType) => paths[dataType])
    .map((dataType) => [dataType, paths[dataType]]);
  const noisePath = paths.NOISE;

  if (dataPaths.length === 0 && !noisePath) {
    return <p>No input files assigned yet.</p>;
  }

  return (
    <div className="assigned-paths">
      {dataPaths.length > 0 && (
        <div className="assigned-path-group">
          <strong>Data</strong>
          {dataPaths.map(([dataType, filePath]) => {
            const selection = roleSelectionStatus(session, dataType);
            return (
              <div key={dataType} className="assigned-path-row">
                <span>{dataType}</span>
                <span>
                  {filePath}
                  <MapSelectionStatus selection={selection} />
                </span>
              </div>
            );
          })}
        </div>
      )}
      {noisePath && (
        <div className="assigned-path-row">
          <span>NOISE</span>
          <span>
            {noisePath}
            <MapSelectionStatus selection={roleSelectionStatus(session, 'NOISE')} />
          </span>
        </div>
      )}
      {Object.entries(paths)
        .filter(([dataType]) => (
          !['ABS', 'BASE', 'ABS+BASE', 'ABS+BASE+NOISE', 'NOISE'].includes(dataType)
        ))
        .map(([dataType, filePath]) => (
          <div key={dataType} className="assigned-path-row">
            <strong>{dataType}:</strong> {filePath}
          </div>
        ))}
    </div>
  );
};

function CleaningKineticsPreview({ view }) {
  const plotRef = useRef(null);

  useEffect(() => {
    const plotNode = plotRef.current;
    if (!plotNode || !view) {
      return undefined;
    }

    const traces = [
      ...(view.traces || []).map((trace) => ({
        x: view.x || [],
        y: trace.y || [],
        type: 'scatter',
        mode: 'lines',
        line: { color: 'rgba(148, 163, 184, 0.34)', width: 1 },
        hoverinfo: 'skip',
        showlegend: false,
      })),
      {
        x: view.x || [],
        y: view.average || [],
        type: 'scatter',
        mode: 'lines',
        name: 'Average',
        line: { color: '#dc2626', width: 2.5 },
        showlegend: false,
      },
    ];

    Plotly.react(
      plotNode,
      traces,
      {
        margin: { t: 18, r: 16, b: 42, l: 54 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#e5e7eb' },
        xaxis: {
          title: `Time Delay, ${view.time_scale || ''}`.trim(),
          gridcolor: 'rgba(148, 163, 184, 0.24)',
          zerolinecolor: 'rgba(148, 163, 184, 0.36)',
        },
        yaxis: {
          title: 'Intensity',
          type: view.y_axis_type || 'linear',
          gridcolor: 'rgba(148, 163, 184, 0.24)',
          zerolinecolor: 'rgba(148, 163, 184, 0.36)',
        },
      },
      { responsive: true, displayModeBar: false }
    ).catch(() => undefined);

    const resizeObserver = new ResizeObserver(() => {
      if (plotNode?._fullLayout) {
        Plotly.Plots.resize(plotNode);
      }
    });
    resizeObserver.observe(plotNode);

    return () => {
      resizeObserver.disconnect();
      try {
        Plotly.purge(plotNode);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, [view]);

  if (!view) {
    return <div className="cleaning-preview-empty">Assign an input file to preview cleaning kinetics.</div>;
  }

  return (
    <div className="cleaning-preview">
      <div className="cleaning-preview-header">
        <span>{view.cleaned_state ? 'Cleaned kinetics preview' : 'Original kinetics preview'}</span>
        <span>
          {view.current_measurements} / {view.original_measurements} maps
          {view.shown_measurements < view.current_measurements
            ? `, showing ${view.shown_measurements}`
            : ''}
        </span>
      </div>
      <div className="cleaning-preview-plot" ref={plotRef}></div>
    </div>
  );
}

function StitchHeatmap({ map, title, overlapRange, regions = [], regionSide = 'left', onRegionsChange = null }) {
  const plotRef = useRef(null);

  useEffect(() => {
    const plotNode = plotRef.current;
    if (!plotNode || !map) {
      return undefined;
    }

    const shapes = overlapRange
      ? [{
          type: 'rect',
          name: 'stitch-overlap',
          xref: 'x',
          yref: 'paper',
          x0: overlapRange[0],
          x1: overlapRange[1],
          y0: 0,
          y1: 1,
          fillcolor: 'rgba(244, 114, 182, 0.12)',
          line: { color: 'rgba(244, 114, 182, 0.78)', width: 1 },
        }]
      : [];
    shapes.push(...stitchRegionsToShapes(regions, regionSide));

    Plotly.react(
      plotNode,
      [{
        x: map.x || [],
        y: map.y || [],
        z: map.z || [],
        type: 'heatmap',
        colorscale: 'Viridis',
        colorbar: { thickness: 10 },
        hovertemplate: 'W:%{x}<br>T:%{y}<br>OD:%{z}<extra></extra>',
      }],
      {
        title: { text: title, font: { size: 13 } },
        margin: { t: 34, r: 10, b: 42, l: 54 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#e5e7eb' },
        xaxis: { title: 'Wavelength, nm', gridcolor: 'rgba(148, 163, 184, 0.24)' },
        yaxis: { title: 'Delay', gridcolor: 'rgba(148, 163, 184, 0.24)' },
        shapes,
        dragmode: onRegionsChange ? 'drawrect' : 'zoom',
        newshape: {
          fillcolor: 'rgba(250, 204, 21, 0.16)',
          line: { color: 'rgba(250, 204, 21, 0.95)', width: 1.5 },
        },
      },
      {
        responsive: true,
        displayModeBar: true,
        editable: false,
        edits: onRegionsChange ? { shapePosition: true } : undefined,
        modeBarButtonsToAdd: onRegionsChange ? ['drawrect', 'eraseshape'] : [],
      }
    ).catch(() => undefined);

    const handleRelayout = (eventData) => {
      if (!onRegionsChange || !eventData) {
        return;
      }
      const shapeChanged = Object.keys(eventData).some((key) => key.startsWith('shapes'));
      if (!shapeChanged) {
        return;
      }
      window.setTimeout(() => {
        const editableShapes = (plotNode.layout?.shapes || []).filter((shape) => shape.yref === 'y');
        const nextRegions = shapesToStitchRegions(editableShapes, regions, regionSide);
        onRegionsChange(nextRegions);
      }, 0);
    };
    if (plotNode.on) {
      plotNode.on('plotly_relayout', handleRelayout);
    }

    const resizeObserver = new ResizeObserver(() => {
      if (plotNode?._fullLayout) {
        Plotly.Plots.resize(plotNode);
      }
    });
    resizeObserver.observe(plotNode);
    return () => {
      resizeObserver.disconnect();
      try {
        if (plotNode.removeListener) {
          plotNode.removeListener('plotly_relayout', handleRelayout);
        }
        Plotly.purge(plotNode);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, [map, overlapRange, regions, regionSide, onRegionsChange, title]);

  return <div className="stitch-heatmap" ref={plotRef} />;
}

function StitchProfilePlot({ spectra, title, mode = 'selected' }) {
  const plotRef = useRef(null);

  useEffect(() => {
    const plotNode = plotRef.current;
    if (!plotNode || !spectra) {
      return undefined;
    }

    const traces = [];
    spectra.forEach((region) => {
      if (mode === 'overlap') {
        traces.push(
          {
            x: region.left_overlap?.x || [],
            y: region.left_overlap?.y || [],
            type: 'scatter',
            mode: 'lines',
            name: `${region.label} left overlap`,
            line: { color: '#facc15', width: 2.8 },
          },
          {
            x: region.right_overlap?.x || [],
            y: region.right_overlap?.y || [],
            type: 'scatter',
            mode: 'lines',
            name: `${region.label} right overlap`,
            line: { color: '#38bdf8', width: 2.8 },
          }
        );
        return;
      }
      traces.push(
        {
          x: region.left_selected?.x || [],
          y: region.left_selected?.y || [],
          type: 'scatter',
          mode: 'lines',
          name: `${region.label} left selected`,
          line: { color: '#facc15', width: 2.2 },
        },
        {
          x: region.right_selected?.x || [],
          y: region.right_selected?.y || [],
          type: 'scatter',
          mode: 'lines',
          name: `${region.label} right selected`,
          line: { color: '#38bdf8', width: 2.2 },
        },
        {
          x: region.stitched_selected?.x || [],
          y: region.stitched_selected?.y || [],
          type: 'scatter',
          mode: 'lines',
          name: `${region.label} stitched`,
          line: { color: region.color || '#22c55e', width: 1.8, dash: 'dot' },
        }
      );
    });

    Plotly.react(
      plotNode,
      traces,
      {
        title: { text: title, font: { size: 13 } },
        margin: { t: 34, r: 16, b: 44, l: 54 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#e5e7eb' },
        xaxis: { title: 'Wavelength, nm', gridcolor: 'rgba(148, 163, 184, 0.24)' },
        yaxis: { title: 'OD', gridcolor: 'rgba(148, 163, 184, 0.24)' },
        legend: { orientation: 'h', y: -0.24 },
      },
      { responsive: true, displayModeBar: true }
    ).catch(() => undefined);

    const resizeObserver = new ResizeObserver(() => {
      if (plotNode?._fullLayout) {
        Plotly.Plots.resize(plotNode);
      }
    });
    resizeObserver.observe(plotNode);
    return () => {
      resizeObserver.disconnect();
      try {
        Plotly.purge(plotNode);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, [spectra, title, mode]);

  return <div className="stitch-profile" ref={plotRef} />;
}

export {
  roleSelectionStatus, backendCleaningPreview, MapSelectionStatus, AssignedPaths,
  CleaningKineticsPreview, StitchHeatmap, StitchProfilePlot,
};
