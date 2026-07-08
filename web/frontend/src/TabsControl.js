import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import {
  fetchCleaningView,
  fetchCompressionJob,
  fetchFileSummary,
  fetchFolderListing,
  fetchFolderSetJob,
  fetchTreatmentSession,
  postTreatment,
  startCompressionJob,
  startFolderSetJob,
  updateSelectionConfig,
} from './api/treatmentClient';
import './css/DataWindowVD2.css';

const PROFILE_PRESETS = {
  V0: {
    exp_type: 'HIS+NOISE',
    selected_data_type: 'ABS+BASE',
    calc_mode: 'individual',
    first_map_with_electrons: true,
  },
  VD2: {
    exp_type: 'ABS+BASE+NOISE',
    selected_data_type: 'ABS',
    calc_mode: 'averaged',
    first_map_with_electrons: true,
  },
};
const REQUIRED_DATA_TYPES = {
  HIS: ['ABS+BASE+NOISE'],
  'HIS+NOISE': ['ABS+BASE', 'NOISE'],
  'ABS+BASE+NOISE': ['ABS', 'BASE', 'NOISE'],
};
const FILES_LAYOUT_STORAGE_KEY = 'pyconlyse.treatment.filesLayout';
const DEFAULT_FILES_LAYOUT = {
  parameters: 300,
  selected: 320,
};

function clampNumber(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function readFilesLayout() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(FILES_LAYOUT_STORAGE_KEY) || '{}');
    return {
      parameters: clampNumber(Number(saved.parameters) || DEFAULT_FILES_LAYOUT.parameters, 240, 520),
      selected: clampNumber(Number(saved.selected) || DEFAULT_FILES_LAYOUT.selected, 260, 520),
    };
  } catch (_error) {
    return DEFAULT_FILES_LAYOUT;
  }
}

function saveFilesLayout(layout) {
  try {
    window.localStorage.setItem(FILES_LAYOUT_STORAGE_KEY, JSON.stringify(layout));
  } catch (_error) {
    // localStorage may be unavailable in private or restricted browser contexts.
  }
}

function requiredDataTypesForExpType(expType) {
  return REQUIRED_DATA_TYPES[String(expType || '').trim().toUpperCase()] || [];
}

function shouldApplyAutoPreset(sessionState, preset) {
  if (!sessionState || !preset) {
    return false;
  }
  const assignedPaths = Object.keys(sessionState.paths || {});
  if (assignedPaths.length > 0) {
    return false;
  }
  return (
    sessionState.exp_type !== preset.exp_type ||
    sessionState.selected_data_type !== preset.selected_data_type
  );
}

const ParametersZone = ({
  session,
  expTypes,
  dataTypes,
  calcModes,
  draftSaveFolder,
  draftSaveFileName,
  onConfigChange,
  onDraftSaveFolderChange,
  onDraftSaveFileNameChange,
  onCommitSaveFolder,
  onCommitSaveFileName,
  onReset,
  profileName,
}) => {
  const isAbsBaseNoiseMode = session.exp_type === 'ABS+BASE+NOISE';

  return (
    <div className="parameters-zone">
      <div className="parameters-zone-header">
        <h3>Treatment Session</h3>
        <span>
          Profile: <strong>{profileName}</strong>
        </span>
      </div>
      <div className="parameter-field">
        <label>Experiment Type:</label>
        <select
          value={session.exp_type}
          onChange={(event) => onConfigChange({ exp_type: event.target.value })}
        >
          {expTypes.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="parameter-field">
        <label>Assign As:</label>
        <select
          value={session.selected_data_type}
          onChange={(event) =>
            onConfigChange({ selected_data_type: event.target.value })
          }
        >
          {dataTypes.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="parameter-field">
        <label>Calculation Mode:</label>
        <select
          value={session.calc_mode}
          disabled={isAbsBaseNoiseMode}
          onChange={(event) => onConfigChange({ calc_mode: event.target.value })}
        >
          {(isAbsBaseNoiseMode ? ['averaged'] : calcModes).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="parameter-checkbox">
        <label>
          <input
            type="checkbox"
            checked={session.first_map_with_electrons}
            disabled={isAbsBaseNoiseMode}
            onChange={(event) =>
              onConfigChange({
                first_map_with_electrons: event.target.checked,
              })
            }
          />
          First map with electrons
        </label>
      </div>
      <div className="parameter-field parameter-field-wide">
        <label>Save Folder:</label>
        <input
          type="text"
          value={draftSaveFolder}
          onChange={(event) => onDraftSaveFolderChange(event.target.value)}
          onBlur={onCommitSaveFolder}
          placeholder="Select a folder inside the treatment root"
        />
      </div>
      <div className="parameter-field parameter-field-wide">
        <label>Save File Name:</label>
        <input
          type="text"
          value={draftSaveFileName}
          onChange={(event) => onDraftSaveFileNameChange(event.target.value)}
          onBlur={onCommitSaveFileName}
          placeholder="result.dat"
        />
      </div>
      <div className="parameter-actions">
        <button onClick={onReset}>Reset Session</button>
      </div>
    </div>
  );
};

function getParentFolder(folderPath, allowedRoot) {
  if (!folderPath || !allowedRoot || folderPath === allowedRoot) {
    return null;
  }

  const trimmed = folderPath.replace(/[\\/]+$/, '');
  const lastSeparator = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  if (lastSeparator < 0) {
    return null;
  }

  const parent = trimmed.slice(0, lastSeparator);
  if (!parent || parent.length < allowedRoot.length) {
    return allowedRoot;
  }
  return parent;
}

function getPathParent(pathValue) {
  const trimmed = String(pathValue || '').replace(/[\\/]+$/, '');
  const lastSeparator = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  if (lastSeparator < 0) {
    return '';
  }
  return trimmed.slice(0, lastSeparator);
}

function joinPath(folderPath, fileName) {
  const folder = String(folderPath || '').replace(/[\\/]+$/, '');
  const name = String(fileName || '').replace(/^[\\/]+/, '');
  if (!folder || !name) {
    return '';
  }
  const separator = folder.includes('\\') && !folder.includes('/') ? '\\' : '/';
  return `${folder}${separator}${name}`;
}

function pathName(folderPath) {
  const trimmed = String(folderPath || '').replace(/[\\/]+$/, '');
  const lastSeparator = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  const name = lastSeparator >= 0 ? trimmed.slice(lastSeparator + 1) : trimmed;
  try {
    return decodeURIComponent(name);
  } catch (_error) {
    return name;
  }
}

function pathStem(filePath) {
  const name = pathName(filePath);
  const dotIndex = name.lastIndexOf('.');
  return dotIndex > 0 ? name.slice(0, dotIndex) : name;
}

function h5NameForPath(filePath) {
  const stem = pathStem(filePath);
  return stem ? `${stem}.h5` : '';
}

function stitchedNameForPaths(firstPath, secondPath, stitchedMap = null) {
  const firstStem = pathStem(firstPath);
  const secondStem = pathStem(secondPath);
  if (!firstStem && !secondStem) {
    return 'stitched_od.dat';
  }
  if (!firstStem || !secondStem) {
    return `${firstStem || secondStem}_stitched.dat`;
  }
  const firstParts = firstStem.split(/[_\-\s]+/);
  const secondParts = secondStem.split(/[_\-\s]+/);
  const sharedParts = [];
  for (let index = 0; index < Math.min(firstParts.length, secondParts.length); index += 1) {
    if (firstParts[index] !== secondParts[index]) {
      break;
    }
    sharedParts.push(firstParts[index]);
  }
  const sharedStem = sharedParts.join('_') || `${firstStem}_${secondStem}`;
  const wavelengthMin = stitchedMap?.wavelength_min;
  const wavelengthMax = stitchedMap?.wavelength_max;
  if (Number.isFinite(Number(wavelengthMin)) && Number.isFinite(Number(wavelengthMax))) {
    return `${sharedStem}_${Number(wavelengthMin).toFixed(0)}-${Number(wavelengthMax).toFixed(0)}nm_stitched.dat`;
  }
  return `${sharedStem}_stitched.dat`;
}

function stitchRegionsToShapes(regions, side = 'left') {
  return (regions || []).map((region) => ({
    type: 'rect',
    name: 'stitch-region',
    xref: 'x',
    yref: 'y',
    x0: region[`${side}_wavelength_start`] ?? region.wavelength_start,
    x1: region[`${side}_wavelength_end`] ?? region.wavelength_end,
    y0: region.delay_start,
    y1: region.delay_end,
    fillcolor: 'rgba(250, 204, 21, 0.16)',
    line: { color: 'rgba(250, 204, 21, 0.95)', width: 1.5 },
  }));
}

function shapesToStitchRegions(shapes, previousRegions = [], side = 'left') {
  return (shapes || [])
    .filter((shape) => shape?.type === 'rect' && shape.xref === 'x' && shape.yref === 'y')
    .map((shape, index) => {
      const previous = previousRegions[index] || {};
      const next = {
        ...previous,
        [`${side}_wavelength_start`]: Number(shape.x0),
        [`${side}_wavelength_end`]: Number(shape.x1),
        delay_start: Number(shape.y0),
        delay_end: Number(shape.y1),
        label: previous.label || `Region ${index + 1}`,
      };
      const otherSide = side === 'left' ? 'right' : 'left';
      if (next[`${otherSide}_wavelength_start`] === undefined) {
        next[`${otherSide}_wavelength_start`] = Number(shape.x0);
      }
      if (next[`${otherSide}_wavelength_end`] === undefined) {
        next[`${otherSide}_wavelength_end`] = Number(shape.x1);
      }
      return next;
    })
    .filter((region) => (
      Number.isFinite(region[`${side}_wavelength_start`]) &&
      Number.isFinite(region[`${side}_wavelength_end`]) &&
      Number.isFinite(region.delay_start) &&
      Number.isFinite(region.delay_end)
    ));
}

function cropHeatmapMap(map, wavelengthRange, delayRange) {
  if (!map) {
    return map;
  }
  const x = map.x || [];
  const y = map.y || [];
  const z = map.z || [];
  const xMin = Number(wavelengthRange?.[0]);
  const xMax = Number(wavelengthRange?.[1]);
  const yMin = Number(delayRange?.[0]);
  const yMax = Number(delayRange?.[1]);
  const xIndices = x
    .map((value, index) => ({ value: Number(value), index }))
    .filter(({ value }) => (
      !Number.isFinite(xMin) ||
      !Number.isFinite(xMax) ||
      (value >= Math.min(xMin, xMax) && value <= Math.max(xMin, xMax))
    ))
    .map(({ index }) => index);
  const yIndices = y
    .map((value, index) => ({ value: Number(value), index }))
    .filter(({ value }) => (
      !Number.isFinite(yMin) ||
      !Number.isFinite(yMax) ||
      (value >= Math.min(yMin, yMax) && value <= Math.max(yMin, yMax))
    ))
    .map(({ index }) => index);
  if (xIndices.length === 0 || yIndices.length === 0) {
    return map;
  }
  let croppedZ = z;
  if (z.length === x.length) {
    croppedZ = xIndices.map((xIndex) => yIndices.map((yIndex) => z[xIndex]?.[yIndex]));
  } else if (z.length === y.length) {
    croppedZ = yIndices.map((yIndex) => xIndices.map((xIndex) => z[yIndex]?.[xIndex]));
  }
  return {
    ...map,
    x: xIndices.map((index) => x[index]),
    y: yIndices.map((index) => y[index]),
    z: croppedZ,
  };
}

function sortStitchDatFiles(files) {
  return [...(files || [])].sort((first, second) => {
    return String(first.name || '').localeCompare(String(second.name || ''));
  });
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return '...';
  }
  const units = ['B', 'KB', 'MB', 'GB'];
  let scaled = value;
  let unitIndex = 0;
  while (scaled >= 1024 && unitIndex < units.length - 1) {
    scaled /= 1024;
    unitIndex += 1;
  }
  const digits = scaled >= 10 || unitIndex === 0 ? 0 : 1;
  return `${scaled.toFixed(digits)}${units[unitIndex]}`;
}

function formatSignedFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value === 0) {
    return '0B';
  }
  return `${value > 0 ? '+' : '-'}${formatFileSize(Math.abs(value))}`;
}

function formatWavelengthRange(summary) {
  const low = Number(summary?.wavelength_min);
  const high = Number(summary?.wavelength_max);
  if (!Number.isFinite(low) || !Number.isFinite(high)) {
    return '...';
  }
  return `${Math.round(low)}-${Math.round(high)}nm`;
}

function formatAxisValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return '';
  }
  if (Math.abs(numeric) >= 100 || Number.isInteger(numeric)) {
    return String(Math.round(numeric));
  }
  return String(Number(numeric.toFixed(3)));
}

function formatTimeRange(summary) {
  const low = Number(summary?.timedelay_min);
  const high = Number(summary?.timedelay_max);
  const unit = summary?.time_scale || '';
  if (!Number.isFinite(low) || !Number.isFinite(high)) {
    return unit || '...';
  }
  if (Math.abs(low - high) < Number.EPSILON) {
    return `${formatAxisValue(low)}${unit}`;
  }
  return `${formatAxisValue(low)}-${formatAxisValue(high)}${unit}`;
}

function formatFrameCount(summary) {
  const current = Number(summary?.number_maps);
  const original = Number(summary?.original_number_maps);
  if (!Number.isFinite(current) || current <= 0) {
    return '...';
  }
  if (Number.isFinite(original) && original > current) {
    return `${Math.round(current)}/${Math.round(original)}`;
  }
  return String(Math.round(current));
}

function summarizeFolderSet(payload, label, folderPath) {
  const folderSet = payload.folder_set || {};
  const assignedTypes = Object.keys(folderSet.assigned || {});
  const conversions = Object.values(folderSet.conversions || {});
  const cleanedTypes = Object.keys(folderSet.cleaned || {});
  const converted = conversions.filter((item) => item.converted && !item.overwritten);
  const overwritten = conversions.filter((item) => item.overwritten);
  const reused = conversions.filter((item) => item.converted === false);
  const deletedHisCount = conversions.filter((item) => item.deleted_source).length;
  const changedFiles = conversions.filter((item) => item.converted || item.overwritten);
  const sourceBytes = changedFiles.reduce(
    (total, item) => total + Number(item.source_size_bytes || 0),
    0
  );
  const outputBytes = changedFiles.reduce(
    (total, item) => total + Number(item.output_size_bytes || 0),
    0
  );
  const spaceChange = outputBytes - sourceBytes;
  const lines = [`${label} completed for ${pathName(folderPath)}.`];

  if (assignedTypes.length) {
    lines.push(`Assigned: ${assignedTypes.join(', ')}.`);
  }
  if (conversions.length) {
    lines.push(
      `Converted HIS: ${converted.length}; overwritten H5: ${overwritten.length}; reused H5: ${reused.length}; removed HIS: ${deletedHisCount}.`
    );
  }
  if (changedFiles.length) {
    const percent = sourceBytes
      ? `${((spaceChange / sourceBytes) * 100).toFixed(1)}%`
      : '0.0%';
    lines.push(
      `Disk: ${formatFileSize(sourceBytes)} source -> ${formatFileSize(outputBytes)} H5 (${formatSignedFileSize(spaceChange)}, ${percent}).`
    );
    lines.push('H5 raw_data compression: gzip level 4; file can still grow if source is already compact.');
  }
  if (cleanedTypes.length) {
    lines.push(`Cleaned: ${cleanedTypes.join(', ')}.`);
  }
  if (folderSet.auto_calculated) {
    lines.push('OD calculated and displayed.');
  }
  if (folderSet.auto_calc_error) {
    lines.push(`OD calculation skipped: ${folderSet.auto_calc_error}`);
  }
  return lines.join('\n');
}

function summarizeFileCompression(payload, dataType = '') {
  const conversion = payload.conversion || {};
  const lines = [dataType ? `Set to ${dataType} + Compress completed.` : 'Convert/Compress completed.'];
  if (conversion.overwritten) {
    lines.push(`Overwritten H5: ${pathName(conversion.output_path)}.`);
  } else if (conversion.converted) {
    lines.push(`${pathName(conversion.source_path)} -> ${pathName(conversion.output_path)}.`);
  } else {
    lines.push(`Reused existing H5: ${pathName(conversion.output_path)}.`);
  }
  lines.push(`Removed HIS: ${conversion.deleted_source ? 'yes' : 'no'}.`);
  lines.push(
    `Disk: ${formatFileSize(conversion.source_size_bytes)} -> ${formatFileSize(conversion.output_size_bytes)} (${formatSignedFileSize(conversion.space_change_bytes)}, ${Number(conversion.space_change_percent || 0).toFixed(1)}%).`
  );
  lines.push('H5 raw_data compression: gzip level 4.');
  if (dataType) {
    lines.push(`Assigned source: ${payload.session?.path_sources?.[dataType] || conversion.output_path || ''}.`);
  } else {
    lines.push(`Output: ${conversion.output_path || ''}.`);
  }
  return lines.join('\n');
}

function summarizeCompressionProgress(job, filePath) {
  const current = Number(job?.current_bytes || 0);
  const total = Number(job?.total_bytes || 0);
  const percent = total > 0 ? ` (${Math.min(100, (current / total) * 100).toFixed(1)}%)` : '';
  const lines = [
    `Convert/Compress running for ${pathName(filePath)}.`,
    job?.message || 'Working...',
  ];
  if (job?.phase === 'convert' && total > 0) {
    lines.push(`${current} / ${total} maps${percent}`);
  } else if (total > 0) {
    lines.push(`${formatFileSize(current)} / ${formatFileSize(total)}${percent}`);
  }
  if (job?.phase === 'convert' && total === 0) {
    lines.push('This step may not show byte progress while H5 is being rewritten.');
  }
  return lines.join('\n');
}

function summarizeFolderSetProgress(job, label, folderPath) {
  const current = Number(job?.current_items || 0);
  const total = Number(job?.total_items || 0);
  const files = Object.entries(job?.files || {});
  const lines = [
    `${label} running for ${pathName(folderPath)}.`,
    job?.message || 'Working...',
  ];

  if (total > 0) {
    lines.push(`${current}/${total}`);
  }
  files.forEach(([dataType, item]) => {
    const source = item?.output_path || item?.source_path || '';
    const status = item?.status || 'queued';
    const phase = item?.phase ? `/${item.phase}` : '';
    const itemCurrent = Number(item?.current || 0);
    const itemTotal = Number(item?.total || 0);
    const itemPercent = itemTotal > 0
      ? ` (${Math.min(100, (itemCurrent / itemTotal) * 100).toFixed(1)}%)`
      : '';
    let progress = '';
    if (itemTotal > 0 && item?.phase === 'convert') {
      progress = ` ${itemCurrent}/${itemTotal} maps${itemPercent}`;
    } else if (itemTotal > 0) {
      progress = ` ${formatFileSize(itemCurrent)}/${formatFileSize(itemTotal)}${itemPercent}`;
    }
    const message = item?.message ? ` - ${item.message}` : '';
    lines.push(`${dataType}: ${status}${phase}${progress}${message}${source ? ` - ${pathName(source)}` : ''}`);
  });
  if (job?.phase === 'converting') {
    lines.push('H5 raw_data compression: gzip level 4.');
  }
  return lines.join('\n');
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function folderPathChain(folderPath, allowedRoot) {
  if (!folderPath || !allowedRoot) {
    return [];
  }

  const chain = [];
  let current = String(folderPath).replace(/[\\/]+$/, '');
  const root = String(allowedRoot).replace(/[\\/]+$/, '');
  const seen = new Set();

  while (current && !seen.has(current)) {
    seen.add(current);
    chain.unshift(current);
    if (current === root) {
      break;
    }
    const parent = getParentFolder(current, root);
    if (!parent || parent === current) {
      break;
    }
    current = parent;
  }

  if (chain[0] !== root) {
    chain.unshift(root);
  }
  return chain;
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
          {dataPaths.map(([dataType, filePath]) => (
            <div key={dataType} className="assigned-path-row">
              <span>{dataType}</span>
              <span>{filePath}</span>
            </div>
          ))}
        </div>
      )}
      {noisePath && (
        <div className="assigned-path-row">
          <span>NOISE</span>
          <span>{noisePath}</span>
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

const TabsControl = () => {
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const treatmentProfile = String(treatmentContext?.treatmentProfile || 'VD2').toUpperCase();
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;
  const [activeTab, setActiveTab] = useState('files');
  const [treatment, setTreatment] = useState(null);
  const filesLayoutRef = useRef(null);
  const stitchAutoPreviewAttemptKeyRef = useRef('');
  const skipNextStitchCoefficientRefreshRef = useRef(false);
  const [filesLayout, setFilesLayout] = useState(readFilesLayout);
  const [folderTreeCache, setFolderTreeCache] = useState({});
  const [fileSummaryCache, setFileSummaryCache] = useState({});
  const [expandedFolders, setExpandedFolders] = useState(() => new Set());
  const [fileContextMenu, setFileContextMenu] = useState(null);
  const [folderContextMenu, setFolderContextMenu] = useState(null);
  const [isFolderTreeOpen, setIsFolderTreeOpen] = useState(false);
  const [isSelectingFolderRoot, setIsSelectingFolderRoot] = useState(false);
  const [treeRoot, setTreeRoot] = useState('');
  const [draftSaveFolder, setDraftSaveFolder] = useState('');
  const [draftSaveFileName, setDraftSaveFileName] = useState('');
  const [draftAllowedRoot, setDraftAllowedRoot] = useState('');
  const [draftKineticsRanges, setDraftKineticsRanges] = useState('');
  const [draftSpectraRanges, setDraftSpectraRanges] = useState('');
  const [cleaningAngleThreshold, setCleaningAngleThreshold] = useState('1.0');
  const [cleaningSurfaceThreshold, setCleaningSurfaceThreshold] = useState('1.0');
  const [error, setError] = useState('');
  const [operationMessage, setOperationMessage] = useState('');
  const [selectionMessage, setSelectionMessage] = useState('');
  const [cleaningSummary, setCleaningSummary] = useState(null);
  const [cleaningView, setCleaningView] = useState(null);
  const [isCleaningViewLoading, setIsCleaningViewLoading] = useState(false);
  const [stitchFileA, setStitchFileA] = useState('');
  const [stitchFileB, setStitchFileB] = useState('');
  const [stitchOutputName, setStitchOutputName] = useState('stitched_od.dat');
  const [stitchLeftScale, setStitchLeftScale] = useState('1');
  const [stitchLeftOffset, setStitchLeftOffset] = useState('0');
  const [stitchRightScale, setStitchRightScale] = useState('1');
  const [stitchRightOffset, setStitchRightOffset] = useState('0');
  const [stitchRightDelayShift, setStitchRightDelayShift] = useState('0');
  const [stitchLeftWavelengthStart, setStitchLeftWavelengthStart] = useState('');
  const [stitchLeftWavelengthEnd, setStitchLeftWavelengthEnd] = useState('');
  const [stitchRightWavelengthStart, setStitchRightWavelengthStart] = useState('');
  const [stitchRightWavelengthEnd, setStitchRightWavelengthEnd] = useState('');
  const [stitchRegionStart, setStitchRegionStart] = useState('');
  const [stitchRegionEnd, setStitchRegionEnd] = useState('');
  const [stitchRegions, setStitchRegions] = useState([]);
  const [stitchPreview, setStitchPreview] = useState(null);
  const [stitchSummary, setStitchSummary] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [busyStartedAt, setBusyStartedAt] = useState(null);
  const [busyNow, setBusyNow] = useState(Date.now());
  const profilePreset = PROFILE_PRESETS[treatmentProfile] || PROFILE_PRESETS.VD2;
  const isV0Profile = treatmentProfile === 'V0';

  const session = treatment ? treatment.session : null;
  const requiredDataTypes =
    session?.required_data_types || requiredDataTypesForExpType(session?.exp_type);
  const assignableDataTypes =
    requiredDataTypes && requiredDataTypes.length > 0 ? requiredDataTypes : treatment?.data_types || [];
  const canAverageNoise = requiredDataTypes.includes('NOISE');
  const assignedCleaningTypes = assignableDataTypes.filter((dataType) => session?.paths?.[dataType]);
  const cleaningActiveDataType =
    assignedCleaningTypes.includes(session?.active_data_type)
      ? session.active_data_type
      : assignedCleaningTypes[0] || '';
  const cleaningSourcePath =
    cleaningActiveDataType
      ? (session?.path_sources?.[cleaningActiveDataType] || session?.paths?.[cleaningActiveDataType] || '')
      : '';
  const cleaningOutputName = h5NameForPath(cleaningSourcePath);
  const busyElapsedSeconds =
    isBusy && busyStartedAt ? Math.max(0, Math.floor((busyNow - busyStartedAt) / 1000)) : 0;
  const filesGridTemplate = `${filesLayout.parameters}px 6px minmax(620px, 1fr) 6px ${filesLayout.selected}px`;

  const handleFilesColumnResizeStart = useCallback((edge, event) => {
    event.preventDefault();
    const containerWidth =
      filesLayoutRef.current?.getBoundingClientRect().width || window.innerWidth || 1280;
    const startX = event.clientX;
    const startLayout = { ...filesLayout };
    const minTree = 620;
    const gutters = 12;
    const minParameters = 240;
    const maxParameters = Math.max(
      minParameters,
      containerWidth - startLayout.selected - minTree - gutters
    );
    const minSelected = 260;
    const maxSelected = Math.max(
      minSelected,
      containerWidth - startLayout.parameters - minTree - gutters
    );
    let nextLayout = startLayout;

    const onMove = (moveEvent) => {
      const delta = moveEvent.clientX - startX;
      nextLayout = {
        parameters:
          edge === 'parameters'
            ? clampNumber(startLayout.parameters + delta, minParameters, maxParameters)
            : startLayout.parameters,
        selected:
          edge === 'selected'
            ? clampNumber(startLayout.selected - delta, minSelected, maxSelected)
            : startLayout.selected,
      };
      setFilesLayout(nextLayout);
    };

    const onUp = () => {
      saveFilesLayout(nextLayout);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [filesLayout]);

  useEffect(() => {
    if (!isBusy) {
      return undefined;
    }
    if (!busyStartedAt) {
      setBusyStartedAt(Date.now());
    }
    const timerId = window.setInterval(() => setBusyNow(Date.now()), 1000);
    return () => window.clearInterval(timerId);
  }, [busyStartedAt, isBusy]);

  useEffect(() => {
    if (!isBusy) {
      setBusyStartedAt(null);
    }
  }, [isBusy]);

  useEffect(() => {
    if (activeTab === 'selection' || (isV0Profile && activeTab !== 'files')) {
      setActiveTab('files');
    }
  }, [activeTab, isV0Profile]);

  const refreshSession = async () => {
    const payload = await fetchTreatmentSession(treatmentSessionId);
    setTreatment(payload);
    if (requestSelectionRefresh) {
      requestSelectionRefresh();
    }
    return payload;
  };

  const loadFileSummary = useCallback(
    async (file) => {
      if (!file?.path || !['.his', '.h5'].includes(String(file.suffix || '').toLowerCase())) {
        return;
      }
      if (fileSummaryCache[file.path]) {
        return;
      }

      setFileSummaryCache((current) => ({
        ...current,
        [file.path]: { loading: true },
      }));
      try {
        const payload = await fetchFileSummary(treatmentSessionId, file.path);
        setFileSummaryCache((current) => ({
          ...current,
          [file.path]: payload.file_summary || {},
        }));
      } catch (err) {
        setFileSummaryCache((current) => ({
          ...current,
          [file.path]: { error: err.message },
        }));
      }
    },
    [fileSummaryCache, treatmentSessionId]
  );

  const refreshCleaningView = useCallback(async () => {
    if (!treatmentSessionId) {
      return null;
    }

    setIsCleaningViewLoading(true);
    try {
      const payload = await fetchCleaningView(treatmentSessionId);
      setCleaningView(payload.cleaning_view);
      return payload.cleaning_view;
    } catch (err) {
      setCleaningView(null);
      return null;
    } finally {
      setIsCleaningViewLoading(false);
    }
  }, [treatmentSessionId]);

  const cacheFolderListing = useCallback((folderPath, payload) => {
    if (!folderPath) {
      return;
    }
    setFolderTreeCache((current) => ({
      ...current,
      [folderPath]: {
        folders: payload.folders || [],
        files: payload.files || [],
      },
    }));
  }, []);

  const refreshFolderListing = useCallback(
    async (folderPath) => {
      if (!folderPath) {
        return;
      }

      const payload = await fetchFolderListing(treatmentSessionId, folderPath);
      cacheFolderListing(folderPath, payload);
    },
    [cacheFolderListing, treatmentSessionId]
  );

  const loadFolderTreeNode = useCallback(
    async (folderPath) => {
      if (!folderPath || folderTreeCache[folderPath]) {
        return;
      }
      const payload = await fetchFolderListing(treatmentSessionId, folderPath);
      cacheFolderListing(folderPath, payload);
    },
    [cacheFolderListing, folderTreeCache, treatmentSessionId]
  );

  const ensureFolderTreePath = useCallback(
    async (folderPath, allowedRoot) => {
      const chain = folderPathChain(folderPath, allowedRoot);
      if (chain.length === 0) {
        return;
      }

      setExpandedFolders((current) => {
        const next = new Set(current);
        chain.forEach((path) => next.add(path));
        return next;
      });

      await Promise.all(
        chain.map(async (path) => {
          const payload = await fetchFolderListing(treatmentSessionId, path);
          cacheFolderListing(path, payload);
        })
      );
    },
    [cacheFolderListing, treatmentSessionId]
  );

  useEffect(() => {
    let cancelled = false;

    const loadSession = async () => {
      try {
        let payload = await fetchTreatmentSession(treatmentSessionId);
        if (shouldApplyAutoPreset(payload.session, profilePreset)) {
          payload = await postTreatment(
            treatmentSessionId,
            '/api/treatment/session/config',
            profilePreset
          );
        }

        if (!cancelled) {
          setTreatment(payload);
          if (requestSelectionRefresh) {
            requestSelectionRefresh();
          }
        }

        if (!cancelled && payload.session.folder_path) {
          await refreshFolderListing(payload.session.folder_path);
          await ensureFolderTreePath(payload.session.folder_path, payload.allowed_root);
        }
        if (
          !cancelled &&
          payload.allowed_root &&
          payload.allowed_root !== payload.session.folder_path
        ) {
          const rootPayload = await fetchFolderListing(treatmentSessionId, payload.allowed_root);
          if (!cancelled) {
            cacheFolderListing(payload.allowed_root, rootPayload);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
    };

    loadSession();

    return () => {
      cancelled = true;
    };
  }, [
    cacheFolderListing,
    ensureFolderTreePath,
    profilePreset,
    refreshFolderListing,
    requestSelectionRefresh,
    treatmentSessionId,
  ]);

  useEffect(() => {
    if (activeTab === 'cleaning') {
      refreshCleaningView();
    }
  }, [activeTab, refreshCleaningView, session?.active_data_type, session?.paths]);

  useEffect(() => {
    const closeContextMenu = () => {
      setFileContextMenu(null);
      setFolderContextMenu(null);
    };
    window.addEventListener('click', closeContextMenu);
    window.addEventListener('keydown', closeContextMenu);
    return () => {
      window.removeEventListener('click', closeContextMenu);
      window.removeEventListener('keydown', closeContextMenu);
    };
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }
    setDraftSaveFolder(session.save_folder || '');
    setDraftSaveFileName(session.save_file_name || '');
    setDraftAllowedRoot(treatment?.allowed_root || '');
  }, [session, treatment?.allowed_root]);

  useEffect(() => {
    if (!treeRoot && (session?.folder_path || treatment?.allowed_root)) {
      setTreeRoot(session?.folder_path || treatment?.allowed_root || '');
    }
  }, [session?.folder_path, treatment?.allowed_root, treeRoot]);

  useEffect(() => {
    const rootsToExpand = [treatment?.allowed_root, session?.folder_path].filter(Boolean);
    if (rootsToExpand.length === 0) {
      return;
    }
    setExpandedFolders((current) => {
      const next = new Set(current);
      rootsToExpand.forEach((folderPath) => next.add(folderPath));
      return next;
    });
  }, [session?.folder_path, treatment?.allowed_root]);

  useEffect(() => {
    const visibleFiles = [];
    Object.entries(folderTreeCache).forEach(([folderPath, listing]) => {
      if (folderPath !== treeRoot && !expandedFolders.has(folderPath)) {
        return;
      }
      (listing.files || []).forEach((file) => {
        const suffix = String(file.suffix || '').toLowerCase();
        if (suffix === '.his' || suffix === '.h5') {
          visibleFiles.push(file);
        }
      });
    });
    visibleFiles.slice(0, 40).forEach((file) => {
      loadFileSummary(file);
    });
  }, [expandedFolders, fileSummaryCache, folderTreeCache, loadFileSummary, treeRoot]);

  const applyPayload = async (requestPromise, refreshListing = false) => {
    setError('');
    setIsBusy(true);
    try {
      const payload = await requestPromise;
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      if (refreshListing && payload.session.folder_path) {
        await refreshFolderListing(payload.session.folder_path);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleConfigChange = (patch) => {
    if (!session) {
      return;
    }
    const normalizedPatch = { ...patch };
    const nextExpType = normalizedPatch.exp_type || session.exp_type;
    const nextRequired = requiredDataTypesForExpType(nextExpType);

    if (!Object.prototype.hasOwnProperty.call(normalizedPatch, 'selected_data_type')) {
      if (nextRequired.length > 0 && !nextRequired.includes(session.selected_data_type)) {
        normalizedPatch.selected_data_type = nextRequired[0];
      }
    }

    if (
      nextExpType === 'ABS+BASE+NOISE' &&
      Object.prototype.hasOwnProperty.call(normalizedPatch, 'exp_type')
    ) {
      normalizedPatch.calc_mode = 'averaged';
    }

    applyPayload(postTreatment(treatmentSessionId, '/api/treatment/session/config', normalizedPatch));
  };

  const handleReset = () =>
    applyPayload(postTreatment(treatmentSessionId, '/api/treatment/session/reset'), true);

  const handleAllowedRootChange = async () => {
    const nextAllowedRoot = draftAllowedRoot.trim();
    if (!nextAllowedRoot || nextAllowedRoot === treatment.allowed_root) {
      return;
    }

    setError('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/root', {
        allowed_root: nextAllowedRoot,
      });
      setTreatment(payload);
      setDraftAllowedRoot(payload.allowed_root || '');
      setCleaningSummary(null);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(payload.session.folder_path || payload.allowed_root);
      const rootPayload = await fetchFolderListing(treatmentSessionId, payload.allowed_root);
      cacheFolderListing(payload.allowed_root, rootPayload);
      setTreeRoot(payload.allowed_root || '');
      setIsSelectingFolderRoot(true);
      setIsFolderTreeOpen(true);
      setExpandedFolders((current) => {
        const next = new Set(current);
        next.add(payload.allowed_root);
        return next;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleAllowedRootKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleAllowedRootChange();
    }
  };

  const handleAssignFile = async (filePath, dataType = session?.selected_data_type) => {
    if (!session) {
      return;
    }
    if (!dataType) {
      return;
    }

    setError('');
    setOperationMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/cache-path', {
        data_type: dataType,
        file_path: filePath,
      });
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      const cachedPath = payload.cached_file?.cached_path || filePath;
      setOperationMessage(`Set to ${dataType}: ${cachedPath}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setFileContextMenu(null);
      setIsBusy(false);
    }
  };

  const handleSetStitchFile = (filePath, side) => {
    if (!filePath) {
      return;
    }
    if (side === 'A') {
      setStitchFileA(filePath);
    } else {
      setStitchFileB(filePath);
    }
    setStitchPreview(null);
    setStitchSummary(null);
    setFileContextMenu(null);
    setOperationMessage(`Set Stitch ${side}: ${pathName(filePath)}`);
  };

  const handleCompressFile = async (filePath) => {
    if (!session || !filePath) {
      return;
    }

    setError('');
    const suffix = String(filePath).split('?')[0].toLowerCase().split('.').pop();
    setOperationMessage(
      [
        `Convert/Compress started for ${pathName(filePath)}.`,
        'Reading source file...',
        'Writing H5 with gzip level 4...',
        suffix === 'his'
          ? 'HIS will be removed after H5 is verified.'
          : 'H5 will be overwritten in place.',
      ].join('\n')
    );
    setSelectionMessage('');
    setCleaningSummary(null);
    setFileContextMenu(null);
    setIsBusy(true);
    try {
      const started = await startCompressionJob(treatmentSessionId, filePath);
      let job = started.compression_job;
      setOperationMessage(summarizeCompressionProgress(job, filePath));
      let payload = null;
      while (job?.status === 'running') {
        await wait(500);
        const statusPayload = await fetchCompressionJob(treatmentSessionId, job.job_id);
        job = statusPayload.compression_job;
        setOperationMessage(summarizeCompressionProgress(job, filePath));
      }
      if (job?.status === 'error') {
        throw new Error(job.error || job.message || 'Convert/Compress failed.');
      }
      payload = job?.payload || { conversion: job?.conversion };
      setTreatment(payload);
      setOperationMessage(summarizeFileCompression(payload));
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(getParentFolder(filePath, treatment?.allowed_root));
    } catch (err) {
      setError(err.message);
      setOperationMessage(`Convert/Compress failed for ${pathName(filePath)}.`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleFolderTreeToggle = async (folderPath) => {
    if (!folderPath) {
      return;
    }
    const isExpanded = expandedFolders.has(folderPath);
    setExpandedFolders((current) => {
      const next = new Set(current);
      if (isExpanded) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });
    if (!isExpanded) {
      try {
        await loadFolderTreeNode(folderPath);
      } catch (err) {
        setError(err.message);
      }
    }
  };

  const handleExplorerFolderSelect = async (folderPath) => {
    if (!folderPath) {
      return;
    }
    if (!isSelectingFolderRoot) {
      await handleFolderTreeToggle(folderPath);
      return;
    }

    setError('');
    await applyPayload(
      postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
        folder_path: folderPath,
      }),
      true
    );
    setTreeRoot(folderPath);
    setIsSelectingFolderRoot(false);
    setExpandedFolders((current) => {
      const next = new Set(current);
      next.add(folderPath);
      return next;
    });
    try {
      await loadFolderTreeNode(folderPath);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFolderTreeOpen = async () => {
    if (!treatment?.allowed_root) {
      return;
    }

    setError('');
    setIsFolderTreeOpen(true);
    setIsSelectingFolderRoot(true);
    setTreeRoot(treatment.allowed_root);
    setExpandedFolders((current) => {
      const next = new Set(current);
      next.add(treatment.allowed_root);
      return next;
    });
    try {
      await loadFolderTreeNode(treatment.allowed_root);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFileContextMenu = (event, file) => {
    event.preventDefault();
    event.stopPropagation();
    if (!file.supported || isBusy) {
      return;
    }
    setFolderContextMenu(null);
    setFileContextMenu({
      file,
      x: event.clientX,
      y: event.clientY,
    });
  };

  const handleFolderContextMenu = (event, folder) => {
    event.preventDefault();
    event.stopPropagation();
    if (!folder?.path || isBusy) {
      return;
    }
    setFileContextMenu(null);
    setFolderContextMenu({
      folder,
      x: event.clientX,
      y: event.clientY,
    });
  };

  const handleFolderSet = async (folderPath, convert = false, clean = false) => {
    if (!folderPath) {
      return;
    }

    setError('');
    const label = clean ? 'Set/Convert/Clean' : convert ? 'Set/Convert' : 'Set';
    setOperationMessage(`${label} started for ${pathName(folderPath)}.`);
    setIsBusy(true);
    try {
      const started = await startFolderSetJob(treatmentSessionId, {
        folder_path: folderPath,
        convert,
        clean,
        angle_threshold: Number(cleaningAngleThreshold),
        surface_threshold: Number(cleaningSurfaceThreshold),
      });
      let job = started.folder_set_job;
      setOperationMessage(summarizeFolderSetProgress(job, label, folderPath));
      while (job?.status === 'running') {
        await wait(500);
        const statusPayload = await fetchFolderSetJob(treatmentSessionId, job.job_id);
        job = statusPayload.folder_set_job;
        setOperationMessage(summarizeFolderSetProgress(job, label, folderPath));
      }
      if (job?.status === 'error') {
        throw new Error(job.error || job.message || `${label} failed.`);
      }
      const payload = job?.payload || { folder_set: job?.folder_set };
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(folderPath);
      setExpandedFolders((current) => {
        const next = new Set(current);
        next.add(folderPath);
        return next;
      });
      setOperationMessage(summarizeFolderSet(payload, label, folderPath));
    } catch (err) {
      setError(err.message);
      setOperationMessage(`${label} failed for ${pathName(folderPath)}.`);
    } finally {
      setFolderContextMenu(null);
      setIsBusy(false);
    }
  };

  const handleAverageNoise = async () => {
    setError('');
    setIsBusy(true);
    setOperationMessage('');
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/average-noise');
      setTreatment(payload);
      setOperationMessage('Noise averaged on the backend.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCalcAbs = async () => {
    setError('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/calc-abs');
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      setOperationMessage('OD result calculated on the backend.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleSave = async () => {
    setError('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/save');
      setTreatment(payload);
      setOperationMessage(`Result saved to ${payload.saved.save_path}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCommitSaveFolder = () => {
    if (!session || draftSaveFolder === session.save_folder) {
      return;
    }
    handleConfigChange({ save_folder: draftSaveFolder });
  };

  const handleCommitSaveFileName = () => {
    if (!session || draftSaveFileName === session.save_file_name) {
      return;
    }
    handleConfigChange({ save_file_name: draftSaveFileName });
  };

  const formatExportRanges = (ranges) =>
    (ranges || [])
      .map((item) => `${item.center} ${item.width}`)
      .join('; ');

  const handleSelectionExport = async (userType) => {
    const ranges = userType === 'kinetics' ? draftKineticsRanges : draftSpectraRanges;

    setError('');
    setSelectionMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/selection/export', {
        user_type: userType,
        ranges,
      });

      setTreatment(payload);
      const normalizedRanges = formatExportRanges(payload.exported.ranges);
      if (userType === 'kinetics') {
        setDraftKineticsRanges(normalizedRanges);
      } else {
        setDraftSpectraRanges(normalizedRanges);
      }

      setSelectionMessage(
        `${userType} exported to ${payload.exported.output_path}`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleV0QuickExport = async () => {
    const kineticsRanges = draftKineticsRanges || '500+-10; 600+-5';
    const spectraRanges = draftSpectraRanges || '1+-0.5; 3+-1';
    let kineticsOutputPath = '';

    setError('');
    setSelectionMessage('');
    setIsBusy(true);
    try {
      const kineticsPayload = await postTreatment(
        treatmentSessionId,
        '/api/treatment/selection/export',
        {
          user_type: 'kinetics',
          ranges: kineticsRanges,
        }
      );
      kineticsOutputPath = kineticsPayload.exported.output_path;
      setDraftKineticsRanges(formatExportRanges(kineticsPayload.exported.ranges));

      const spectraPayload = await postTreatment(
        treatmentSessionId,
        '/api/treatment/selection/export',
        {
          user_type: 'spectra',
          ranges: spectraRanges,
        }
      );
      setTreatment(spectraPayload);
      setDraftSpectraRanges(formatExportRanges(spectraPayload.exported.ranges));
      setSelectionMessage(
        `V0 quick export completed: kinetics -> ${kineticsOutputPath}; spectra -> ${spectraPayload.exported.output_path}`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCleaningTargetChange = async (dataType) => {
    if (!dataType || dataType === session?.active_data_type) {
      return;
    }

    setError('');
    setOperationMessage('');
    setCleaningSummary(null);
    setIsBusy(true);
    try {
      const payload = await updateSelectionConfig(treatmentSessionId, {
        active_data_type: dataType,
        map_index: 0,
        selection: {},
      });
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshCleaningView();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCleaningAction = async (mode) => {
    setError('');
    setSelectionMessage('');
    setIsBusy(true);

    try {
      let payload;
      if (mode === 'reset') {
        payload = await postTreatment(treatmentSessionId, '/api/treatment/cleaning/reset');
      } else if (mode === 'restore') {
        payload = await postTreatment(treatmentSessionId, '/api/treatment/cleaning/restore');
      } else {
        payload = await postTreatment(
          treatmentSessionId,
          mode === 'analyze' ? '/api/treatment/cleaning/sam' : '/api/treatment/cleaning/save',
          {
            angle_threshold: Number.parseFloat(cleaningAngleThreshold),
            surface_threshold: Number.parseFloat(cleaningSurfaceThreshold),
            output_file_name: '',
          }
        );
      }

      if (mode === 'reset') {
        setCleaningSummary(null);
        if (payload.cleaning_view) {
          setCleaningView(payload.cleaning_view);
        } else {
          refreshCleaningView();
        }
        setOperationMessage(
          payload.cleaning.discarded_measurements
            ? `Cleaning state reset for ${payload.cleaning.file_path}.`
            : 'Cleaning state was already empty.'
        );
      } else if (mode === 'restore') {
        setTreatment(payload);
        setCleaningSummary(payload.cleaning);
        if (payload.cleaning_view) {
          setCleaningView(payload.cleaning_view);
        }
        if (payload.cleaning?.output_path) {
          setFileSummaryCache((current) => {
            const next = { ...current };
            delete next[payload.cleaning.output_path];
            return next;
          });
        }
        setOperationMessage(
          payload.cleaning?.restored
            ? `Denoising restored ${payload.cleaning.restored_measurements} maps into raw_data.`
            : 'No deleted maps were stored in this H5.'
        );
        if (requestSelectionRefresh) {
          requestSelectionRefresh();
        }
      } else {
        setCleaningSummary(payload.cleaning);
        if (payload.cleaning_view) {
          setCleaningView(payload.cleaning_view);
        }
        if (mode === 'save') {
          setTreatment(payload);
          setOperationMessage(
            `Cleaned H5 saved to ${payload.cleaning.output_path} and assigned as ${payload.cleaning.assigned_data_type || session?.active_data_type || 'active file'}.`
          );
          if (requestSelectionRefresh) {
            requestSelectionRefresh();
          }
          refreshCleaningView();
        } else if (payload.cleaning.state_updated === false) {
          setOperationMessage(payload.cleaning.warning || 'No measurements passed the thresholds.');
        } else if (payload.cleaning.source_measurements !== payload.cleaning.original_measurements) {
          setOperationMessage(
            `SAM pass applied to ${payload.cleaning.source_measurements} already-cleaned maps.`
          );
        } else {
          setOperationMessage('SAM cleaning pass applied to the original file maps.');
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const stitchRequestPayload = () => ({
    file_a: stitchFileA,
    file_b: stitchFileB,
    time_regions: stitchRegions,
    left_scale: Number.parseFloat(stitchLeftScale),
    left_offset: Number.parseFloat(stitchLeftOffset),
    right_scale: Number.parseFloat(stitchRightScale),
    right_offset: Number.parseFloat(stitchRightOffset),
    right_delay_shift_pixels: Number.parseInt(stitchRightDelayShift, 10) || 0,
  });

  const syncStitchRegionInputs = useCallback((region) => {
    if (!region) {
      return;
    }
    setStitchLeftWavelengthStart(String(region.left_wavelength_start ?? region.wavelength_start ?? ''));
    setStitchLeftWavelengthEnd(String(region.left_wavelength_end ?? region.wavelength_end ?? ''));
    setStitchRightWavelengthStart(String(region.right_wavelength_start ?? region.wavelength_start ?? ''));
    setStitchRightWavelengthEnd(String(region.right_wavelength_end ?? region.wavelength_end ?? ''));
    setStitchRegionStart(String(region.delay_start ?? ''));
    setStitchRegionEnd(String(region.delay_end ?? ''));
  }, []);

  const handleStitchRegionsChange = useCallback((regions) => {
    setStitchRegions(regions);
    syncStitchRegionInputs(regions?.[regions.length - 1]);
  }, [syncStitchRegionInputs]);

  const refreshStitchPreview = async (fitRight = false, silent = false, auto = false, coefficientOverrides = null) => {
    setError('');
    if (!silent) {
      setOperationMessage('');
    }
    if (!stitchFileA || !stitchFileB) {
      setError('Select two OD DAT files.');
      return;
    }
    const attemptKey = `${stitchFileA}|${stitchFileB}`;
    if (auto) {
      if (stitchAutoPreviewAttemptKeyRef.current === attemptKey) {
        return;
      }
      stitchAutoPreviewAttemptKeyRef.current = attemptKey;
    } else {
      stitchAutoPreviewAttemptKeyRef.current = '';
    }
    if (!silent) {
      setIsBusy(true);
    }
    try {
      const requestPayload = {
        ...stitchRequestPayload(),
        ...(coefficientOverrides || {}),
        fit_right: fitRight,
      };
      if (fitRight) {
        requestPayload.right_scale = 1;
        requestPayload.right_offset = 0;
      }
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/stitch/od/preview', requestPayload);
      const preview = payload.stitch_preview;
      if (stitchRegions.length === 0 && preview.overlap_range && preview.timedelay_min !== null && preview.timedelay_max !== null) {
        const defaultRegion = {
          left_wavelength_start: preview.overlap_range[0],
          left_wavelength_end: preview.overlap_range[1],
          right_wavelength_start: preview.overlap_range[0],
          right_wavelength_end: preview.overlap_range[1],
          delay_start: preview.timedelay_min,
          delay_end: preview.timedelay_max,
          label: 'Region 1',
        };
        setStitchRegions([defaultRegion]);
        syncStitchRegionInputs(defaultRegion);
      }
      setStitchPreview(preview);
      if (preview.suggested_output_file_name && stitchOutputName === 'stitched_od.dat') {
        setStitchOutputName(preview.suggested_output_file_name);
      }
      if (preview.fit) {
        skipNextStitchCoefficientRefreshRef.current = true;
        setStitchRightScale(String(Number(preview.fit.right_scale).toPrecision(8)));
        setStitchRightOffset(String(Number(preview.fit.right_offset).toPrecision(8)));
      }
      if (!silent) {
        setOperationMessage(
          fitRight
            ? `Right map fitted by integrated profile: scale ${Number(preview.coefficients.right_scale).toPrecision(6)}.`
            : coefficientOverrides
              ? 'Stitch fit reverted.'
              : 'Stitch pair loaded.'
        );
      }
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) {
        setIsBusy(false);
      }
    }
  };

  const handleRevertStitchFit = () => {
    skipNextStitchCoefficientRefreshRef.current = true;
    setStitchRightScale('1');
    setStitchRightOffset('0');
    refreshStitchPreview(false, false, false, { right_scale: 1, right_offset: 0 });
  };

  const handleAddStitchRegion = () => {
    const leftWavelengthStart = Number.parseFloat(stitchLeftWavelengthStart);
    const leftWavelengthEnd = Number.parseFloat(stitchLeftWavelengthEnd);
    const rightWavelengthStart = Number.parseFloat(stitchRightWavelengthStart);
    const rightWavelengthEnd = Number.parseFloat(stitchRightWavelengthEnd);
    const delayStart = Number.parseFloat(stitchRegionStart);
    const delayEnd = Number.parseFloat(stitchRegionEnd);
    if (
      !Number.isFinite(leftWavelengthStart) ||
      !Number.isFinite(leftWavelengthEnd) ||
      !Number.isFinite(rightWavelengthStart) ||
      !Number.isFinite(rightWavelengthEnd) ||
      !Number.isFinite(delayStart) ||
      !Number.isFinite(delayEnd)
    ) {
      setError('Left/right wavelength and delay bounds must be numeric.');
      return;
    }
    setError('');
    setStitchRegions((current) => [
      ...current,
      {
        left_wavelength_start: leftWavelengthStart,
        left_wavelength_end: leftWavelengthEnd,
        right_wavelength_start: rightWavelengthStart,
        right_wavelength_end: rightWavelengthEnd,
        delay_start: delayStart,
        delay_end: delayEnd,
        label: `Region ${current.length + 1}`,
      },
    ]);
  };

  const handleRemoveStitchRegion = (indexToRemove) => {
    setStitchRegions((current) => current.filter((_item, index) => index !== indexToRemove));
  };

  const handleStitchOd = async () => {
    setError('');
    setOperationMessage('');
    setStitchSummary(null);
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/stitch/od', {
        ...stitchRequestPayload(),
        output_folder: stitchOutputFolder,
        output_file_name: stitchOutputName,
        fit: stitchPreview?.fit || null,
      });
      setTreatment(payload);
      setStitchSummary(payload.stitched);
      setOperationMessage(`Stitched OD saved to ${payload.stitched.output_path}.`);
      if (stitchOutputFolder) {
        try {
          await refreshFolderListing(stitchOutputFolder);
        } catch (_refreshError) {
          // Saving succeeded; tree refresh is best effort for remote shares.
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const activeStitchRegion = stitchRegions[stitchRegions.length - 1] || stitchRegions[0] || null;
  const stitchOutputFolder = getPathParent(stitchFileA) || session?.save_folder || session?.folder_path || '';
  const stitchOutputPath = joinPath(stitchOutputFolder, stitchOutputName);
  const stitchZoneMap = useMemo(() => {
    if (!stitchPreview?.stitched) {
      return null;
    }
    const delayRange = activeStitchRegion
      ? [activeStitchRegion.delay_start, activeStitchRegion.delay_end]
      : [stitchPreview.timedelay_min, stitchPreview.timedelay_max];
    return cropHeatmapMap(stitchPreview.stitched, stitchPreview.overlap_range, delayRange);
  }, [activeStitchRegion, stitchPreview]);

  const renderFolderTreeFiles = (files, level = 1) =>
    (files || []).map((file) => {
      const summary = fileSummaryCache[file.path] || {};
      const frames = formatFrameCount(summary);
      const timeRange = formatTimeRange(summary);
      const wavelengths = formatWavelengthRange(summary);
      return (
        <div
          key={file.path}
          className={`explorer-tree-file-row ${file.supported ? '' : 'is-disabled'}`}
          style={{ paddingLeft: `${level * 14 + 28}px` }}
          onContextMenu={isV0Profile ? undefined : (event) => handleFileContextMenu(event, file)}
          title={file.path}
        >
          <button
            className="explorer-tree-file-name"
            onContextMenu={isV0Profile ? undefined : (event) => handleFileContextMenu(event, file)}
            disabled={!file.supported || isBusy}
          >
            {file.name}
          </button>
          <span className="explorer-file-meta">S:{formatFileSize(file.size_bytes)}</span>
          <span className="explorer-file-meta">F:{frames}</span>
          <span className="explorer-file-meta">T:{timeRange}</span>
          <span className="explorer-file-meta">W:{wavelengths}</span>
        </div>
      );
    });

  const renderFolderTreeRows = (folders, level = 1) =>
    (folders || []).map((folder) => {
      const isExpanded = expandedFolders.has(folder.path);
      const cachedListing = folderTreeCache[folder.path];
      const isSelected = session.folder_path === folder.path;

      return (
        <React.Fragment key={folder.path}>
          <div
            className={`explorer-tree-row ${isSelected ? 'is-selected' : ''}`}
            style={{ paddingLeft: `${level * 14}px` }}
            onContextMenu={isV0Profile ? undefined : (event) => handleFolderContextMenu(event, folder)}
          >
            <button
              className="explorer-tree-toggle"
              onClick={() => handleFolderTreeToggle(folder.path)}
              aria-label={isExpanded ? 'Collapse folder' : 'Expand folder'}
            >
              {isExpanded ? 'v' : '>'}
            </button>
            <button
              className="explorer-tree-name"
              onClick={() => handleExplorerFolderSelect(folder.path)}
              title={folder.path}
            >
              {folder.name || pathName(folder.path)}
            </button>
          </div>
          {isExpanded && cachedListing && (
            <>
              {renderFolderTreeRows(cachedListing.folders, level + 1)}
              {renderFolderTreeFiles(cachedListing.files, level + 1)}
            </>
          )}
        </React.Fragment>
      );
    });

  const explorerRoot = treeRoot || session?.folder_path || treatment?.allowed_root || '';
  const explorerRootListing = folderTreeCache[explorerRoot] || { folders: [], files: [] };
  const stitchDatFiles = useMemo(() => {
    const byPath = new Map();
    Object.values(folderTreeCache).forEach((listing) => {
      (listing?.files || []).forEach((file) => {
        if (String(file.suffix || '').toLowerCase() === '.dat') {
          byPath.set(file.path, file);
        }
      });
    });
    return sortStitchDatFiles(Array.from(byPath.values()));
  }, [folderTreeCache]);

  useEffect(() => {
    if (activeTab !== 'stitch' || !stitchFileA || !stitchFileB || stitchPreview || isBusy) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      refreshStitchPreview(false, true, true);
    }, 250);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, stitchFileA, stitchFileB, stitchPreview, isBusy]);

  useEffect(() => {
    if (!stitchFileA || !stitchFileB || stitchOutputName !== 'stitched_od.dat') {
      return;
    }
    setStitchOutputName(stitchedNameForPaths(stitchFileA, stitchFileB, stitchPreview?.stitched));
  }, [stitchFileA, stitchFileB, stitchOutputName, stitchPreview]);

  useEffect(() => {
    if (!stitchPreview || isBusy || !stitchFileA || !stitchFileB) {
      return undefined;
    }
    if (skipNextStitchCoefficientRefreshRef.current) {
      skipNextStitchCoefficientRefreshRef.current = false;
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      refreshStitchPreview(false, true, false);
    }, 600);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    stitchLeftScale,
    stitchLeftOffset,
    stitchRightScale,
    stitchRightOffset,
    stitchRightDelayShift,
    stitchRegions,
    stitchFileA,
    stitchFileB,
  ]);

  if (!session) {
    return (
      <div className="tabs-control">
        <p>{error || 'Loading treatment session...'}</p>
        <button onClick={refreshSession}>Retry</button>
      </div>
    );
  }

  return (
    <div className="tabs-control">
      {!isV0Profile && (
        <div className="tabs">
          <button onClick={() => setActiveTab('files')}>Files</button>
          <button onClick={() => setActiveTab('cleaning')} disabled={isBusy}>
            Cleaning
          </button>
          <button onClick={() => setActiveTab('stitch')} disabled={isBusy}>
            Stitch
          </button>
          <button onClick={() => setActiveTab('info')}>Info</button>
        </div>
      )}
      <div className="tab-content">
        {activeTab === 'files' && (
          <div
            className={`files-tab horizontal-layout ${isV0Profile ? 'is-v0-profile' : ''}`}
            ref={filesLayoutRef}
            style={isV0Profile ? undefined : { gridTemplateColumns: filesGridTemplate }}
          >
            {!isV0Profile && (
              <>
                <div className="zone parameters">
                  <ParametersZone
                    session={session}
                    expTypes={treatment.exp_types}
                    dataTypes={assignableDataTypes}
                    calcModes={treatment.calc_modes}
                    draftSaveFolder={draftSaveFolder}
                    draftSaveFileName={draftSaveFileName}
                    onConfigChange={handleConfigChange}
                    onDraftSaveFolderChange={setDraftSaveFolder}
                    onDraftSaveFileNameChange={setDraftSaveFileName}
                    onCommitSaveFolder={handleCommitSaveFolder}
                    onCommitSaveFileName={handleCommitSaveFileName}
                    onReset={handleReset}
                    profileName={treatmentProfile}
                  />
                </div>
                <div
                  className="column-resizer"
                  role="separator"
                  aria-label="Resize Treatment Session"
                  onMouseDown={(event) => handleFilesColumnResizeStart('parameters', event)}
                />
              </>
            )}
            <div className="zone files-folder">
              <div className="data-root-control">
                <label>
                  Data Root
                  <input
                    type="text"
                    value={draftAllowedRoot}
                    onChange={(event) => setDraftAllowedRoot(event.target.value)}
                    onBlur={handleAllowedRootChange}
                    onKeyDown={handleAllowedRootKeyDown}
                    placeholder={treatment.allowed_root || 'E:/Data/DATA_VD2'}
                  />
                </label>
              </div>
              <div className="folder-selection-header">
                <button onClick={handleFolderTreeOpen} disabled={isBusy || !explorerRoot}>
                  Select Folder
                </button>
              </div>
              {error && <p className="treatment-error">{error}</p>}
              {isFolderTreeOpen && (
              <div className="explorer-panel">
                <div className="explorer-tree" role="tree">
                  <div
                    className={`explorer-tree-row ${
                      session.folder_path === explorerRoot ? 'is-selected' : ''
                    }`}
                    onContextMenu={
                      isV0Profile
                        ? undefined
                        : (event) =>
                            handleFolderContextMenu(event, {
                              name: pathName(explorerRoot) || explorerRoot,
                              path: explorerRoot,
                            })
                    }
                  >
                    <button
                      className="explorer-tree-toggle"
                      onClick={() => handleFolderTreeToggle(explorerRoot)}
                      aria-label="Expand root"
                    >
                      {expandedFolders.has(explorerRoot) ? 'v' : '>'}
                    </button>
                    <button
                      className="explorer-tree-name"
                      onClick={() => handleExplorerFolderSelect(explorerRoot)}
                      title={explorerRoot}
                    >
                      {pathName(explorerRoot) || explorerRoot}
                    </button>
                  </div>
                  {(expandedFolders.has(explorerRoot) || session.folder_path === explorerRoot) &&
                    (
                      <>
                        {renderFolderTreeRows(explorerRootListing.folders, 1)}
                        {renderFolderTreeFiles(explorerRootListing.files, 1)}
                      </>
                    )}
                </div>
              </div>
              )}
              {!isV0Profile && fileContextMenu && (
                <div
                  className="file-context-menu"
                  style={{ left: fileContextMenu.x, top: fileContextMenu.y }}
                  onClick={(event) => event.stopPropagation()}
                >
                  {['ABS', 'BASE', 'NOISE'].map((dataType) => (
                    <button
                      key={dataType}
                      onClick={() => handleAssignFile(fileContextMenu.file.path, dataType)}
                      disabled={isBusy}
                    >
                      Set {dataType}
                    </button>
                  ))}
                  <div className="file-context-menu-separator" />
                  <button
                    onClick={() => handleCompressFile(fileContextMenu.file.path)}
                    disabled={isBusy}
                  >
                    Convert/Compress
                  </button>
                  {String(fileContextMenu.file.suffix || '').toLowerCase() === '.dat' && (
                    <>
                      <div className="file-context-menu-separator" />
                      <div className="file-context-submenu">
                        <button type="button" disabled={isBusy}>
                          Stitch
                        </button>
                        <div className="file-context-submenu-panel">
                          <button
                            onClick={() => handleSetStitchFile(fileContextMenu.file.path, 'A')}
                            disabled={isBusy}
                          >
                            Stitch A
                          </button>
                          <button
                            onClick={() => handleSetStitchFile(fileContextMenu.file.path, 'B')}
                            disabled={isBusy}
                          >
                            Stitch B
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
              {!isV0Profile && folderContextMenu && (
                <div
                  className="file-context-menu"
                  style={{ left: folderContextMenu.x, top: folderContextMenu.y }}
                  onClick={(event) => event.stopPropagation()}
                >
                  <button
                    onClick={() => handleFolderSet(folderContextMenu.folder.path, true)}
                    disabled={isBusy}
                  >
                    Set/Convert
                  </button>
                  <button
                    onClick={() => handleFolderSet(folderContextMenu.folder.path, true, true)}
                    disabled={isBusy}
                  >
                    Set/Convert/Clean
                  </button>
                  <button
                    onClick={() => handleFolderSet(folderContextMenu.folder.path, false)}
                    disabled={isBusy}
                  >
                    Set
                  </button>
                </div>
              )}
            </div>
            {!isV0Profile && (
              <>
                <div
                  className="column-resizer"
                  role="separator"
                  aria-label="Resize Selected Files"
                  onMouseDown={(event) => handleFilesColumnResizeStart('selected', event)}
                />
                <div className="zone raw-data-kinetics">
                  <h3>Selected Files</h3>
                  <AssignedPaths session={session} />
                  <div style={{ marginTop: '15px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <button onClick={handleAverageNoise} disabled={isBusy || !canAverageNoise}>
                      Average Noise
                    </button>
                    <button onClick={handleCalcAbs} disabled={isBusy || !session.ready_for_calc}>
                      Calculate OD
                    </button>
                    <button onClick={handleSave} disabled={isBusy || !session.result_ready}>
                      Save Result
                    </button>
                  </div>
                  {operationMessage && (
                    <p className={`treatment-operation-message ${isBusy ? 'is-active' : ''}`}>
                      {isBusy && (
                        <span className="treatment-operation-live">
                          <span className="treatment-operation-spinner" aria-hidden="true"></span>
                          <span>{busyElapsedSeconds}s</span>
                        </span>
                      )}
                      {operationMessage}
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        )}
        {activeTab === 'cleaning' && (
          <div className="tab-panel cleaning-tab">
            <div className="cleaning-main">
              <CleaningKineticsPreview view={cleaningView} />
              <div className="cleaning-controls">
                {isCleaningViewLoading && <p>Loading cleaning preview...</p>}
                <label>
                  Clean File
                  <select
                    value={cleaningActiveDataType}
                    onChange={(event) => handleCleaningTargetChange(event.target.value)}
                    disabled={isBusy || assignedCleaningTypes.length === 0}
                  >
                    {assignedCleaningTypes.length === 0 && (
                      <option value="">No assigned files</option>
                    )}
                    {assignedCleaningTypes.map((dataType) => {
                      const sourcePath = session.path_sources?.[dataType] || session.paths?.[dataType] || '';
                      return (
                        <option key={dataType} value={dataType}>
                          {dataType} - {pathName(sourcePath)}
                        </option>
                      );
                    })}
                  </select>
                </label>
                <label>
                  Angle Threshold (degrees)
                  <input
                    type="number"
                    min="0.01"
                    step="0.1"
                    value={cleaningAngleThreshold}
                    onChange={(event) => setCleaningAngleThreshold(event.target.value)}
                  />
                </label>
                <label>
                  Surface Threshold (%)
                  <input
                    type="number"
                    min="0.01"
                    step="0.1"
                    value={cleaningSurfaceThreshold}
                    onChange={(event) => setCleaningSurfaceThreshold(event.target.value)}
                  />
                </label>
                <label>
                  Output H5 Name
                  <input
                    type="text"
                    value={cleaningOutputName}
                    readOnly
                    placeholder="source-name.h5"
                  />
                </label>
                <div className="cleaning-actions">
                  <button onClick={() => handleCleaningAction('analyze')} disabled={isBusy}>
                    Clean
                  </button>
                  <button onClick={() => handleCleaningAction('reset')} disabled={isBusy}>
                    Reset
                  </button>
                  <button onClick={() => handleCleaningAction('restore')} disabled={isBusy || !String(cleaningSourcePath || '').toLowerCase().endsWith('.h5')}>
                    Restore H5
                  </button>
                  <button onClick={() => handleCleaningAction('save')} disabled={isBusy}>
                    Clean and Save
                  </button>
                </div>
              </div>
            </div>
              {cleaningSummary && (
                <div className="cleaning-summary">
                  <p>
                    <strong>File:</strong> {cleaningSummary.file_path || session.active_data_type || 'n/a'}
                  </p>
                  <p>
                    <strong>This Pass:</strong> {cleaningSummary.cleaned_measurements} / {cleaningSummary.source_measurements}
                    {' | '}
                    <strong>Pass Retention:</strong> {cleaningSummary.pass_retention_rate.toFixed(1)}%
                  </p>
                  <p>
                    <strong>Overall Retained:</strong> {cleaningSummary.cleaned_measurements} / {cleaningSummary.original_measurements}
                    {' | '}
                    <strong>Overall Retention:</strong> {cleaningSummary.retention_rate.toFixed(1)}%
                  </p>
                  <p>
                    <strong>Angle:</strong> {cleaningSummary.sam_angle_min.toFixed(3)} .. {cleaningSummary.sam_angle_max.toFixed(3)}
                    {' | '}
                    <strong>Mean:</strong> {cleaningSummary.sam_angle_mean.toFixed(3)}
                  </p>
                  {cleaningSummary.state_updated === false && cleaningSummary.warning && (
                    <p>{cleaningSummary.warning}</p>
                  )}
                  {cleaningSummary.output_path && (
                    <p>
                      <strong>Saved:</strong> {cleaningSummary.output_path}
                    </p>
                  )}
                </div>
              )}
          </div>
        )}
        {activeTab === 'stitch' && (
          <div className="tab-panel stitch-tab">
            {error && <p className="treatment-error">{error}</p>}
            <div className="stitch-controls">
              <div className="stitch-control-grid stitch-control-grid-wide">
                <label>
                  OD Map A
                  <input
                    list="stitch-dat-files"
                    type="text"
                    value={stitchFileA}
                    onChange={(event) => setStitchFileA(event.target.value)}
                    placeholder="smb://.../first.dat"
                  />
                </label>
                <label>
                  OD Map B
                  <input
                    list="stitch-dat-files"
                    type="text"
                    value={stitchFileB}
                    onChange={(event) => setStitchFileB(event.target.value)}
                    placeholder="smb://.../second.dat"
                  />
                </label>
              </div>
              <datalist id="stitch-dat-files">
                {stitchDatFiles.map((file) => (
                  <option key={file.path} value={file.path}>
                    {file.name}
                  </option>
                ))}
              </datalist>
              <div className="stitch-control-grid">
                <label>
                  Left Scale
                  <input type="number" step="0.0001" value={stitchLeftScale} onChange={(event) => setStitchLeftScale(event.target.value)} />
                </label>
                <label>
                  Left Offset
                  <input type="number" step="0.0001" value={stitchLeftOffset} onChange={(event) => setStitchLeftOffset(event.target.value)} />
                </label>
                <label>
                  Right Scale
                  <input type="number" step="0.0001" value={stitchRightScale} onChange={(event) => setStitchRightScale(event.target.value)} />
                </label>
                <label>
                  Right Offset
                  <input type="number" step="0.0001" value={stitchRightOffset} onChange={(event) => setStitchRightOffset(event.target.value)} />
                </label>
                <label>
                  Right Y Shift px
                  <input type="number" step="1" value={stitchRightDelayShift} onChange={(event) => setStitchRightDelayShift(event.target.value)} />
                </label>
              </div>
              <div className="stitch-control-grid">
                <label>
                  Left W Start
                  <input type="number" step="any" value={stitchLeftWavelengthStart} onChange={(event) => setStitchLeftWavelengthStart(event.target.value)} />
                </label>
                <label>
                  Left W End
                  <input type="number" step="any" value={stitchLeftWavelengthEnd} onChange={(event) => setStitchLeftWavelengthEnd(event.target.value)} />
                </label>
                <label>
                  Right W Start
                  <input type="number" step="any" value={stitchRightWavelengthStart} onChange={(event) => setStitchRightWavelengthStart(event.target.value)} />
                </label>
                <label>
                  Right W End
                  <input type="number" step="any" value={stitchRightWavelengthEnd} onChange={(event) => setStitchRightWavelengthEnd(event.target.value)} />
                </label>
              </div>
              <div className="stitch-control-grid">
                <label>
                  T Start
                  <input type="number" step="any" value={stitchRegionStart} onChange={(event) => setStitchRegionStart(event.target.value)} />
                </label>
                <label>
                  T End
                  <input type="number" step="any" value={stitchRegionEnd} onChange={(event) => setStitchRegionEnd(event.target.value)} />
                </label>
              </div>
              <div className="stitch-control-grid">
                <button onClick={handleAddStitchRegion} disabled={isBusy}>
                  Add Region
                </button>
                <button onClick={() => refreshStitchPreview(true)} disabled={isBusy || !stitchFileA || !stitchFileB}>
                  Fit Right
                </button>
                <button onClick={handleRevertStitchFit} disabled={isBusy || !stitchPreview || !stitchFileA || !stitchFileB}>
                  Revert
                </button>
              </div>
              {stitchRegions.length > 0 && (
                <div className="stitch-region-list">
                  {stitchRegions.map((region, index) => (
                    <button key={`${region.left_wavelength_start}-${region.right_wavelength_start}-${region.delay_start}-${index}`} onClick={() => handleRemoveStitchRegion(index)}>
                      {region.label}: L {Number(region.left_wavelength_start).toFixed(1)}-{Number(region.left_wavelength_end).toFixed(1)}, R {Number(region.right_wavelength_start).toFixed(1)}-{Number(region.right_wavelength_end).toFixed(1)}, T {Number(region.delay_start).toFixed(3)}-{Number(region.delay_end).toFixed(3)} x
                    </button>
                  ))}
                </div>
              )}
              <label>
                Output DAT Name
                <input
                  type="text"
                  value={stitchOutputName}
                  onChange={(event) => setStitchOutputName(event.target.value)}
                  placeholder="stitched_od.dat"
                />
              </label>
              <div className="stitch-actions">
                <button onClick={() => refreshStitchPreview(false)} disabled={isBusy || !stitchFileA || !stitchFileB}>
                  Load Pair
                </button>
                <button onClick={handleStitchOd} disabled={isBusy || !stitchPreview || !stitchFileA || !stitchFileB}>
                  OK and Save
                </button>
              </div>
              <div className="stitch-summary">
                <p>
                  <strong>Save Folder:</strong> {stitchOutputFolder || 'Not set'}
                </p>
                <p>
                  <strong>Output Path:</strong> {stitchOutputPath || 'Not set'}
                </p>
                <p>
                  <strong>Visible DAT files:</strong> {stitchDatFiles.length}
                </p>
                {stitchPreview && (
                  <>
                    <p>
                      <strong>Axis Overlap:</strong> {(stitchPreview.axis_overlap_range || stitchPreview.overlap_range)?.[0]}-{(stitchPreview.axis_overlap_range || stitchPreview.overlap_range)?.[1]} nm
                    </p>
                    <p>
                      <strong>Trusted Overlap:</strong> {stitchPreview.overlap_range?.[0]}-{stitchPreview.overlap_range?.[1]} nm
                    </p>
                  </>
                )}
                {stitchPreview?.fit && (
                  <p>
                    <strong>Fit:</strong> scale {Number(stitchPreview.fit.right_scale).toPrecision(6)}
                    {Number.isFinite(stitchPreview.fit.correlation)
                      ? ` | corr ${Number(stitchPreview.fit.correlation).toFixed(3)}`
                      : ''}
                    {Number.isFinite(stitchPreview.fit.relative_rmse)
                      ? ` | rel RMSE ${Number(stitchPreview.fit.relative_rmse).toFixed(3)}`
                      : ''}
                  </p>
                )}
                <p>
                  <strong>Right Y Shift:</strong> {Number.parseInt(stitchRightDelayShift, 10) || 0} px
                </p>
                {stitchSummary && (
                  <>
                    <p>
                      <strong>Saved:</strong> {stitchSummary.output_path}
                    </p>
                    {stitchSummary.manifest_path && (
                      <p>
                        <strong>Manifest:</strong> {stitchSummary.manifest_path}
                      </p>
                    )}
                    <p>
                      <strong>W:</strong> {Number(stitchSummary.wavelength_min).toFixed(1)}-{Number(stitchSummary.wavelength_max).toFixed(1)} nm
                      {' | '}
                      <strong>Delays:</strong> {stitchSummary.timedelays}
                      {' | '}
                      <strong>Rows:</strong> {stitchSummary.rows}
                    </p>
                  </>
                )}
                {!stitchSummary && (
                  <p>
                    <strong>Status:</strong> Not saved yet
                  </p>
                )}
              </div>
            </div>
            <div className="stitch-preview">
              {stitchPreview ? (
                <div className="stitch-map-grid">
                  <StitchHeatmap
                    map={stitchPreview.left}
                    title="Left / Short Wavelengths"
                    overlapRange={stitchPreview.axis_overlap_range || stitchPreview.overlap_range}
                    regions={stitchRegions}
                    regionSide="left"
                    onRegionsChange={handleStitchRegionsChange}
                  />
                  <StitchHeatmap
                    map={stitchPreview.right}
                    title="Right / Long Wavelengths"
                    overlapRange={stitchPreview.axis_overlap_range || stitchPreview.overlap_range}
                    regions={stitchRegions}
                    regionSide="right"
                    onRegionsChange={handleStitchRegionsChange}
                  />
                  <StitchProfilePlot
                    spectra={stitchPreview.spectra}
                    title="Selected Profiles"
                    mode="selected"
                  />
                  <StitchProfilePlot
                    spectra={stitchPreview.spectra}
                    title="Overlap Fit Profiles"
                    mode="overlap"
                  />
                  <StitchHeatmap
                    map={stitchZoneMap || stitchPreview.stitched}
                    title="Stitching Zone"
                    overlapRange={null}
                    regions={[]}
                  />
                  <StitchHeatmap
                    map={stitchPreview.stitched}
                    title="Stitched Map"
                    overlapRange={null}
                    regions={[]}
                  />
                </div>
              ) : (
                <div className="stitch-preview-empty">Load pair to preview maps and spectra.</div>
              )}
            </div>
          </div>
        )}
        {activeTab === 'info' && (
          <div className="tab-panel">
            <p>
              <strong>Allowed Root:</strong> {treatment.allowed_root}
            </p>
            <p>
              <strong>Root Available:</strong>{' '}
              {treatment.allowed_root_exists ? 'Yes' : 'No'}
            </p>
            <p>
              <strong>Save Target:</strong>{' '}
              {session.save_folder && session.save_file_name
                ? `${session.save_folder}/${session.save_file_name}`
                : 'Not set'}
            </p>
          </div>
        )}
        {activeTab === 'selection' && (
          <div className="tab-panel">
            <p>
              <strong>Profile:</strong> {treatmentProfile}
              {' | '}
              {treatmentProfile === 'V0'
                ? 'Preset uses HIS+NOISE for legacy V0 flow.'
                : 'Preset uses ABS+BASE+NOISE for VD2 flow.'}
            </p>
            <p>
              Export averaged traces from the active file and current map using
              desktop-style ranges such as <code>500+-10; 600+-5</code>.
            </p>
            <p>
              <strong>Active Data:</strong> {session.active_data_type || 'Not selected'}
              {' | '}
              <strong>Map:</strong> {session.map_index || 0}
            </p>
            {treatmentProfile === 'V0' && (
              <div style={{ marginBottom: '12px' }}>
                <button onClick={handleV0QuickExport} disabled={isBusy}>
                  Quick Export Both (V0)
                </button>
              </div>
            )}
            <div style={{ display: 'grid', gap: '12px', maxWidth: '720px' }}>
              <label>
                Kinetics Ranges
                <input
                  type="text"
                  value={draftKineticsRanges}
                  onChange={(event) => setDraftKineticsRanges(event.target.value)}
                  placeholder="500+-10; 600+-5"
                  style={{ width: '100%' }}
                />
              </label>
              <button
                onClick={() => handleSelectionExport('kinetics')}
                disabled={isBusy}
              >
                Get Kinetics
              </button>
              <label>
                Spectra Ranges
                <input
                  type="text"
                  value={draftSpectraRanges}
                  onChange={(event) => setDraftSpectraRanges(event.target.value)}
                  placeholder="1+-0.5; 3+-1"
                  style={{ width: '100%' }}
                />
              </label>
              <button
                onClick={() => handleSelectionExport('spectra')}
                disabled={isBusy}
              >
                Get Spectra
              </button>
              {selectionMessage && <p>{selectionMessage}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TabsControl;
