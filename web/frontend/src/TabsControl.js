import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import Plotly from 'plotly.js-dist';
import TreatmentError from './components/TreatmentError';
import SkanaPanel from './SkanaPanel';
import { TreatmentContext } from './DataWindowVD2';
import {
  fetchCleaningView,
  fetchCompressionJob,
  fetchFileSummary,
  fetchFolderListing,
  fetchTreatmentQueue,
  fetchTreatmentSession,
  enqueueStandardFolderTreatment,
  enqueueTreatmentRecipe,
  postTreatment,
  removeTreatmentQueueJob,
  runTreatmentQueue,
  startCompressionJob,
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
const SESSION_BACKUP_STORAGE_PREFIX = 'pyconlyse.treatment.sessionBackup.';
const CLEANING_DRAFT_STORAGE_PREFIX = 'pyconlyse.treatment.cleaningDraft.';
const FOLDER_TREE_OPEN_STORAGE_PREFIX = 'pyconlyse.treatment.folderTreeOpen.';
const DEFAULT_FILES_LAYOUT = {
  parameters: 300,
  selected: 320,
  tree: 252,
};
const MIN_TREE_WIDTH = 180;
const MAX_TREE_WIDTH = 460;
const isProjectManifest = file => String(file?.name || pathName(file?.path || '')).toLowerCase() === 'vd2-manifest.json';

function clampNumber(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function readFilesLayout() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(FILES_LAYOUT_STORAGE_KEY) || '{}');
    return {
      parameters: clampNumber(Number(saved.parameters) || DEFAULT_FILES_LAYOUT.parameters, 240, 520),
      selected: clampNumber(Number(saved.selected) || DEFAULT_FILES_LAYOUT.selected, 260, 520),
      tree: clampNumber(Number(saved.tree) || DEFAULT_FILES_LAYOUT.tree, MIN_TREE_WIDTH, MAX_TREE_WIDTH),
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

function sessionBackupKey(sessionId) {
  return `${SESSION_BACKUP_STORAGE_PREFIX}${sessionId}`;
}

function isEmptyTreatmentSession(sessionState) {
  return sessionState?.status_label === 'Treatment session is ready.'
    && Object.keys(sessionState?.paths || {}).length === 0
    && !sessionState?.save_file_name;
}

function hasRecoverableTreatmentWork(sessionState) {
  return Object.keys(sessionState?.paths || {}).length > 0
    || Boolean(sessionState?.save_file_name)
    || Object.keys(sessionState?.selection || {}).length > 0
    || Boolean(sessionState?.cleaning_preview_request);
}

function readSessionBackup(sessionId) {
  try {
    return JSON.parse(window.localStorage.getItem(sessionBackupKey(sessionId)) || 'null');
  } catch (_error) {
    return null;
  }
}

function saveSessionBackup(sessionId, sessionState) {
  if (!sessionId || !hasRecoverableTreatmentWork(sessionState)) return;
  try {
    window.localStorage.setItem(sessionBackupKey(sessionId), JSON.stringify(sessionState));
  } catch (_error) {
    // The server-side session remains usable when browser storage is unavailable.
  }
}

function readCleaningDraft(sessionId, field) {
  try {
    return window.localStorage.getItem(`${CLEANING_DRAFT_STORAGE_PREFIX}${sessionId}.${field}`)
      || '1.0';
  } catch (_error) {
    return '1.0';
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
  // A restored or edited session can be meaningful before files are assigned.
  // Only an untouched session or a new folder link may receive defaults.
  if (sessionState.status_label && sessionState.status_label !== 'Treatment session is ready.'
      && !sessionState.status_label.startsWith('Folder selected:')) {
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
  layoutMode,
  onSave,
  onAverageNoise,
  canAverageNoise,
  compact = false,
  busy = false,
}) => {
  const isAbsBaseNoiseMode = session.exp_type === 'ABS+BASE+NOISE';

  return (
    <div className="parameters-zone">
      {(!compact || session.result_ready) && <>
      <div className="parameters-zone-header">
        <h3>{layoutMode === 'studio' ? '4 Save' : 'Treatment Session'}</h3>
        <span>
          Profile: <strong>{profileName}</strong>
        </span>
      </div>
      <div className="parameter-field parameter-field-wide">
        <label htmlFor="treatment-save-folder">Save Folder</label>
        <input id="treatment-save-folder" type="text" value={draftSaveFolder} disabled={busy}
          onChange={event => onDraftSaveFolderChange(event.target.value)} onBlur={onCommitSaveFolder}
          placeholder="Select a folder inside the treatment root" />
      </div>
      <div className="parameter-field parameter-field-wide">
        <label htmlFor="treatment-save-name">Save File Name</label>
        <input id="treatment-save-name" type="text" value={draftSaveFileName} disabled={busy}
          onChange={event => onDraftSaveFileNameChange(event.target.value)} onBlur={onCommitSaveFileName}
          placeholder="result.dat" />
      </div>
      {onSave && <button type="button" onPointerDown={event => event.preventDefault()} onClick={onSave} disabled={busy || !session.result_ready}>Save Result</button>}
      </>}
      {!compact && <details className="treatment-advanced-settings">
        <summary>Advanced settings</summary>
        <div className="treatment-settings-fields">
      <div className="parameter-field">
        <label>Experiment Type:</label>
        <select
          aria-label="Experiment type" disabled={busy}
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
          aria-label="Assign as" disabled={busy}
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
          aria-label="Calculation mode"
          value={session.calc_mode}
          disabled={busy || isAbsBaseNoiseMode}
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
            disabled={busy || isAbsBaseNoiseMode}
            onChange={(event) =>
              onConfigChange({
                first_map_with_electrons: event.target.checked,
              })
            }
          />
          First map with electrons
        </label>
      </div>
      <div className="parameter-actions">
        {onAverageNoise && <button type="button" onClick={onAverageNoise} disabled={busy || !canAverageNoise}>Average Noise</button>}
        <button onClick={onReset} disabled={busy}>Reset Session</button>
      </div>
        </div>
      </details>}
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

function mergeTreatmentQueue(current, incoming) {
  if (!incoming) {
    return current || { running: false, jobs: [] };
  }
  const statusRank = { queued: 0, running: 1, completed: 2, failed: 2 };
  const jobs = [...(current?.jobs || [])];
  const indices = new Map(jobs.map((job, index) => [job.job_id, index]));
  (incoming.jobs || []).forEach((job) => {
    const index = indices.get(job.job_id);
    if (index === undefined) {
      indices.set(job.job_id, jobs.length);
      jobs.push(job);
      return;
    }
    const previous = jobs[index];
    jobs[index] = (statusRank[previous?.status] || 0) > (statusRank[job?.status] || 0)
      ? previous
      : job;
  });
  return {
    ...(current || {}),
    ...incoming,
    running: Boolean(current?.running || incoming.running),
    jobs,
  };
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

export function summarizeFolderSetProgress(job, folderPath) {
  const current = Number(job?.current_items || 0);
  const total = Number(job?.total_items || 0);
  const files = Object.entries(job?.files || {});
  const messageMatch = String(job?.message || '').match(/^([A-Z+]+):.*?(\d+)\/(\d+)/);
  const activeFile = files.find(([, item]) => item?.status === 'running') || files[0];
  const [activeType, activeItem] = activeFile || [];
  const itemCurrent = Number(activeItem?.current || 0);
  const itemTotal = Number(activeItem?.total || 0);
  const phaseLabel = {
    checking: 'Checking',
    converting: 'Converting',
    assigning: 'Assigning',
    cleaning: 'Cleaning',
  }[job?.phase] || 'Working';
  const activeProgress = messageMatch
    ? `${messageMatch[1]} ${messageMatch[2]}/${messageMatch[3]}`
    : activeType && itemTotal > 0
      ? `${activeType} ${itemCurrent}/${itemTotal}`
      : activeType
        ? `${activeType} ${activeItem?.phase || activeItem?.status || ''}`.trim()
        : phaseLabel;
  const overallProgress = total > 0 ? `${current}/${total}` : '';
  return [pathName(folderPath), activeProgress, overallProgress].filter(Boolean).join(' · ');
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

const TabsControl = ({ preview = null }) => {
  const treeFirst = Boolean(preview);
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const treatmentProfile = String(treatmentContext?.treatmentProfile || 'VD2').toUpperCase();
  const manifestProjectFolder=treatmentContext?.manifestProjectFolder||'';
  const treatmentLayoutMode = treatmentContext?.treatmentLayoutMode || 'classic';
  const isStudioLayout = treatmentLayoutMode === 'studio';
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const saved = window.localStorage.getItem(`pyconlyse.treatment.activeTab.${treatmentSessionId}`);
      return !saved || (treeFirst && saved === 'info') ? 'files' : saved;
    } catch (_error) {
      return 'files';
    }
  });
  const [treatment, setTreatment] = useState(null);
  const filesLayoutRef = useRef(null);
  const treeResizeRef = useRef(null);
  const queueWasRunningRef = useRef(false);
  const folderQueueActiveRef = useRef(false);
  const stitchAutoPreviewAttemptKeyRef = useRef('');
  const skipNextStitchCoefficientRefreshRef = useRef(false);
  const [filesLayout, setFilesLayout] = useState(readFilesLayout);
  const [folderTreeCache, setFolderTreeCache] = useState({});
  const [fileSummaryCache, setFileSummaryCache] = useState({});
  const [expandedFolders, setExpandedFolders] = useState(() => new Set());
  const [fileContextMenu, setFileContextMenu] = useState(null);
  const [folderContextMenu, setFolderContextMenu] = useState(null);
  const [detailFile, setDetailFile] = useState(null);
  const [selectedFolders, setSelectedFolders] = useState([]);
  const folderSelectionAnchor = useRef(null);
  const [isFolderTreeOpen, setIsFolderTreeOpen] = useState(() => {
    try {
      return window.localStorage.getItem(`${FOLDER_TREE_OPEN_STORAGE_PREFIX}${treatmentSessionId}`)
        === 'true' || treeFirst;
    } catch (_error) {
      return treeFirst;
    }
  });
  const [isSelectingFolderRoot, setIsSelectingFolderRoot] = useState(false);
  const [treeRoot, setTreeRoot] = useState('');
  const [draftSaveFolder, setDraftSaveFolder] = useState('');
  const [draftSaveFileName, setDraftSaveFileName] = useState('');
  const [draftAllowedRoot, setDraftAllowedRoot] = useState('');
  const [draftKineticsRanges, setDraftKineticsRanges] = useState('');
  const [draftSpectraRanges, setDraftSpectraRanges] = useState('');
  const [cleaningAngleThreshold, setCleaningAngleThreshold] = useState(
    () => readCleaningDraft(treatmentSessionId, 'angle')
  );
  const [cleaningSurfaceThreshold, setCleaningSurfaceThreshold] = useState(
    () => readCleaningDraft(treatmentSessionId, 'surface')
  );
  const [error, setError] = useState('');
  const [operationMessage, setOperationMessage] = useState('');
  const [selectionMessage, setSelectionMessage] = useState('');
  const [cleaningSummary, setCleaningSummary] = useState(null);
  const [cleaningView, setCleaningView] = useState(null);
  const [pendingCleaningPreview, setPendingCleaningPreview] = useState(null);
  const [savedResultPath, setSavedResultPath] = useState('');
  const [treatmentQueue, setTreatmentQueue] = useState(null);
  const [queueLabel, setQueueLabel] = useState('');
  const [queueApplyCleaning, setQueueApplyCleaning] = useState(true);
  const [isQueueLoading, setIsQueueLoading] = useState(false);
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

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `pyconlyse.treatment.activeTab.${treatmentSessionId}`,
        activeTab
      );
    } catch (_error) {
      // Treatment remains usable when localStorage is unavailable.
    }
  }, [activeTab, treatmentSessionId]);

  const session = treatment ? treatment.session : null;
  const sourceFolder = treeRoot || session?.folder_path || treatment?.allowed_root || '';
  const cleaningFolders = selectedFolders.length > 0
    ? selectedFolders
    : sourceFolder && sourceFolder !== treatment?.allowed_root ? [sourceFolder] : [];

  useEffect(() => {
    saveSessionBackup(treatmentSessionId, session);
  }, [session, treatmentSessionId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `${FOLDER_TREE_OPEN_STORAGE_PREFIX}${treatmentSessionId}`,
        String(isFolderTreeOpen)
      );
    } catch (_error) {
      // Server-side folder selection remains available without browser storage.
    }
  }, [isFolderTreeOpen, treatmentSessionId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `${CLEANING_DRAFT_STORAGE_PREFIX}${treatmentSessionId}.angle`,
        cleaningAngleThreshold
      );
      window.localStorage.setItem(
        `${CLEANING_DRAFT_STORAGE_PREFIX}${treatmentSessionId}.surface`,
        cleaningSurfaceThreshold
      );
    } catch (_error) {
      // The server-side treatment session remains usable.
    }
  }, [cleaningAngleThreshold, cleaningSurfaceThreshold, treatmentSessionId]);
  const persistedCleaningPreview = useMemo(() => backendCleaningPreview(session), [session]);
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
  const isOperationRunning = isBusy;
  const busyElapsedSeconds =
    isOperationRunning && busyStartedAt ? Math.max(0, Math.floor((busyNow - busyStartedAt) / 1000)) : 0;
  const filesGridTemplate = `${filesLayout.parameters}px 6px minmax(620px, 1fr) 6px ${filesLayout.selected}px`;
  const queueJobs = Array.isArray(treatmentQueue?.jobs) ? treatmentQueue.jobs : [];
  const queueHisDataTypes = assignedCleaningTypes.filter((dataType) =>
    String(session?.path_sources?.[dataType] || session?.paths?.[dataType] || '').toLowerCase().endsWith('.his')
  );
  const queueConvertibleHisDataTypes = queueHisDataTypes.filter((dataType) =>
    ['ABS', 'BASE', 'NOISE'].includes(dataType)
  );
  const queueOutputConfigured = Boolean(session?.save_folder && session?.save_file_name);
  const queueSupportsCurrentRecipeCleaning =
    assignedCleaningTypes.length > 0 &&
    assignedCleaningTypes.every((dataType) => ['ABS', 'BASE', 'NOISE'].includes(dataType));
  const canApplyCleaningPreview = Boolean(
    pendingCleaningPreview &&
    !pendingCleaningPreview.backend &&
    !pendingCleaningPreview.stale &&
    !pendingCleaningPreview.invalidated &&
    pendingCleaningPreview.dataType === cleaningActiveDataType &&
    pendingCleaningPreview.angleThreshold === cleaningAngleThreshold &&
    pendingCleaningPreview.surfaceThreshold === cleaningSurfaceThreshold
  );

  const requireAppliedCleaningPreview = useCallback(() => {
    if (!pendingCleaningPreview) {
      return false;
    }
    setActiveTab('cleaning');
    setError(
      `Cleaning preview for ${pendingCleaningPreview.dataType} is not applied. Apply mask to H5 or reset the preview before calculating OD.`
    );
    return true;
  }, [pendingCleaningPreview]);

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
        ...startLayout,
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

  const resizeTree = (separator, requestedWidth) => {
    const maxWidth = Math.min(MAX_TREE_WIDTH, Math.floor(separator.parentElement.clientWidth * 0.38));
    const tree = clampNumber(Math.round(requestedWidth), MIN_TREE_WIDTH, maxWidth);
    const layout = { ...filesLayout, tree };
    setFilesLayout(layout);
    return layout;
  };

  const handleTreePointerDown = (event) => {
    if (event.button !== 0 || !event.isPrimary) return;
    const separator = event.currentTarget;
    treeResizeRef.current = {
      x: event.clientX,
      width: separator.previousElementSibling.getBoundingClientRect().width,
    };
    separator.setPointerCapture(event.pointerId);
  };

  const handleTreePointerMove = (event) => {
    const drag = treeResizeRef.current;
    if (drag && event.currentTarget.hasPointerCapture(event.pointerId)) {
      drag.layout = resizeTree(event.currentTarget, drag.width + event.clientX - drag.x);
    }
  };

  const finishTreeResize = () => {
    const layout = treeResizeRef.current?.layout;
    treeResizeRef.current = null;
    if (layout) saveFilesLayout(layout);
  };

  const handleTreeResizeKey = (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const separator = event.currentTarget;
    const width = separator.previousElementSibling.getBoundingClientRect().width;
    saveFilesLayout(resizeTree(separator, width + (event.key === 'ArrowLeft' ? -16 : 16)));
  };

  useEffect(() => {
    if (!isOperationRunning) {
      return undefined;
    }
    if (!busyStartedAt) {
      setBusyStartedAt(Date.now());
    }
    const timerId = window.setInterval(() => setBusyNow(Date.now()), 1000);
    return () => window.clearInterval(timerId);
  }, [busyStartedAt, isOperationRunning]);

  useEffect(() => {
    if (!isOperationRunning) {
      setBusyStartedAt(null);
    }
  }, [isOperationRunning]);

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

  const refreshTreatmentQueue = useCallback(async (isCurrent = () => true) => {
    const payload = await fetchTreatmentQueue(treatmentSessionId);
    if (isCurrent()) {
      const queue = payload?.queue || { running: false, jobs: [] };
      const finished = queueWasRunningRef.current && !queue.running;
      // Fetch before publishing running=false. Publishing it first cleans up
      // the poll effect and cancels its own pending session read.
      if (finished) {
        const sessionPayload = await fetchTreatmentSession(treatmentSessionId);
        if (isCurrent()) {
          setTreatment(sessionPayload);
          requestSelectionRefresh?.();
        }
      }
      if (isCurrent()) {
        queueWasRunningRef.current = Boolean(queue.running);
        setTreatmentQueue(queue);
      }
    }
    return payload;
  }, [requestSelectionRefresh, treatmentSessionId]);

  const handleQueueEnqueue = async () => {
    if (requireAppliedCleaningPreview()) {
      return;
    }
    if (!queueOutputConfigured) {
      setError('Set Save Folder and Save File Name before adding a queue recipe.');
      return;
    }
    if (queueApplyCleaning && !queueSupportsCurrentRecipeCleaning) {
      setError('Use Set/Convert/Clean/Calc for automatic SAM cleaning of paired inputs.');
      return;
    }

    const dataTypes = assignedCleaningTypes.filter((dataType) => session?.paths?.[dataType]);
    const cleaning = queueApplyCleaning
      ? {
          state: 'pending',
          enabled: true,
          angle_threshold: Number.parseFloat(cleaningAngleThreshold),
          surface_threshold: Number.parseFloat(cleaningSurfaceThreshold),
          data_types: dataTypes,
        }
      : { state: 'not_requested', enabled: false, data_types: [] };

    setError('');
    setIsQueueLoading(true);
    try {
      const payload = await enqueueTreatmentRecipe(treatmentSessionId, {
        label: queueLabel.trim() || pathName(session?.folder_path) || 'Treatment recipe',
        profile: treatmentProfile,
        convert_to_h5: queueConvertibleHisDataTypes.length > 0 ? queueConvertibleHisDataTypes : false,
        cleaning,
      });
      setTreatmentQueue((current) => mergeTreatmentQueue(current, payload?.queue));
      setQueueLabel('');
      setOperationMessage(
        `Current recipe ${payload?.started ? 'started' : 'queued behind active work'}.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsQueueLoading(false);
    }
  };

  const handleQueueStandardFolder = async (
    folderPath,
    { label, convert, clean, calculate, returnToFiles = true }
  ) => {
    const folders = Array.isArray(folderPath) ? folderPath : [folderPath];
    if (!folders[0] || (treeFirst && folderQueueActiveRef.current)) {
      return;
    }
    if (treeFirst) {
      folderQueueActiveRef.current = true;
      setIsQueueLoading(true);
      if (returnToFiles) setActiveTab('files');
    }
    const target = folders.length === 1 ? pathName(folders[0]) : `${folders.length} folders`;
    setError('');
    setFolderContextMenu(null);
    setOperationMessage(`Starting ${label} for ${target}…`);
    try {
      const payload = await enqueueStandardFolderTreatment(treatmentSessionId, {
        ...(treeFirst ? { folder_paths: folders, output_naming: 'sample',
          exp_type: shouldApplyAutoPreset(session, profilePreset) ? profilePreset.exp_type : session.exp_type }
          : { folder_path: folders[0] }),
        label: folders.length === 1 ? pathName(folders[0]) || label : undefined,
        profile: treatmentProfile,
        convert,
        clean,
        calculate,
        angle_threshold: Number(cleaningAngleThreshold),
        surface_threshold: Number(cleaningSurfaceThreshold),
      });
      const saveTarget = payload?.queue_job?.recipe?.save_target;
      if (saveTarget) {
        setDraftSaveFolder(saveTarget.save_folder || '');
        setDraftSaveFileName(saveTarget.save_file_name || '');
        setTreatment((current) => current ? {
          ...current,
          session: {
            ...current.session,
            save_folder: saveTarget.save_folder || '',
            save_file_name: saveTarget.save_file_name || '',
          },
        } : current);
      }
      queueWasRunningRef.current = true;
      setTreatmentQueue((current) => mergeTreatmentQueue(current, payload?.queue));
      // A short Set can finish before its enqueue response reaches the browser.
      if (!payload?.queue?.running) await refreshTreatmentQueue();
      setOperationMessage(
        `${label} ${payload?.started ? 'started' : 'queued'} for ${target}.`
      );
    } catch (err) {
      setOperationMessage('');
      setError(err.message);
    } finally {
      if (treeFirst) {
        folderQueueActiveRef.current = false;
        setIsQueueLoading(false);
      }
    }
  };

  const handleLoadFolderInputs = async () => {
    if (!sourceFolder || isSelectingFolderRoot || folderQueueActiveRef.current) return;
    folderQueueActiveRef.current = true;
    setIsQueueLoading(true);
    try {
      await handleQueueStandardFolder(sourceFolder, {
        label: 'Load folder inputs', convert: true, clean: false, calculate: false,
      });
    } finally {
      folderQueueActiveRef.current = false;
      setIsQueueLoading(false);
    }
  };

  const handleQueueRemove = async (jobId) => {
    if (!jobId) {
      return;
    }
    setError('');
    setIsQueueLoading(true);
    try {
      const payload = await removeTreatmentQueueJob(treatmentSessionId, jobId);
      setTreatmentQueue(payload?.queue || { running: false, jobs: [] });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsQueueLoading(false);
    }
  };

  const loadFileSummary = useCallback(
    async (file) => {
      if (!file?.path || !['.his', '.h5', '.dat'].includes(String(file.suffix || '').toLowerCase())) {
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
      let presetError = null;
      let restoreError = null;
      try {
        let payload = await fetchTreatmentSession(treatmentSessionId);
        if (cancelled) return;
        if (payload.session_persistence === 'sqlite' && isEmptyTreatmentSession(payload.session)) {
          const backup = readSessionBackup(treatmentSessionId);
          if (hasRecoverableTreatmentWork(backup)) {
            try {
              payload = await postTreatment(treatmentSessionId, '/api/treatment/session/restore', {
                session: backup,
              });
            } catch (err) {
              restoreError = err;
              if (!cancelled) setError(`Saved treatment session could not be restored: ${err.message}`);
            }
          }
        }
        if (treatmentContext?.initialFolder && payload.session.folder_path !== treatmentContext.initialFolder) {
          try {
            payload = await postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
              folder_path: treatmentContext.initialFolder,
            });
            if (!cancelled) {
              setTreeRoot(treatmentContext.initialFolder);
              setIsFolderTreeOpen(true);
            }
          } catch (err) {
            // Keep Data Root controls available when a linked folder cannot be selected.
            if (!cancelled) setError(`Cannot open selected folder: ${err.message}. Check Data Root.`);
          }
        }
        if (shouldApplyAutoPreset(payload.session, profilePreset)) {
          try {
            payload = await postTreatment(
              treatmentSessionId,
              '/api/treatment/session/config',
              profilePreset
            );
          } catch (err) {
            // Keep the readable session available when applying the preset fails.
            presetError = err;
            if (!cancelled) setError(err.message);
          }
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
          // A subsequent folder error must not hide authentication recovery.
          setError(restoreError?.message || presetError?.message || err.message);
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
    treatmentContext?.initialFolder,
  ]);

  useEffect(() => {
    if (!isStudioLayout) {
      return undefined;
    }
    let cancelled = false;
    const isCurrent = () => !cancelled;
    refreshTreatmentQueue(isCurrent).catch((err) => {
      if (!cancelled) {
        setError(err.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [isStudioLayout, refreshTreatmentQueue, treatmentSessionId]);

  useEffect(() => {
    if (!isStudioLayout || !treatmentQueue?.running) {
      return undefined;
    }
    let cancelled = false;
    let timeoutId;
    const poll = async () => {
      try {
        await refreshTreatmentQueue(() => !cancelled);
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
      if (!cancelled) {
        timeoutId = window.setTimeout(poll, 1500);
      }
    };
    timeoutId = window.setTimeout(poll, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [isStudioLayout, refreshTreatmentQueue, treatmentQueue?.running]);

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
    setDraftAllowedRoot(manifestProjectFolder?(session.folder_path||manifestProjectFolder):(treatment?.allowed_root || ''));
  }, [session, treatment?.allowed_root,manifestProjectFolder]);

  useEffect(() => {
    if (!persistedCleaningPreview) {
      return;
    }
    setPendingCleaningPreview((current) => {
      if (
        current &&
        !current.backend &&
        current.dataType === persistedCleaningPreview.dataType &&
        current.sourcePath === persistedCleaningPreview.sourcePath
      ) {
        return current;
      }
      return persistedCleaningPreview;
    });
  }, [persistedCleaningPreview]);

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
    if (treeFirst) return;
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
  }, [expandedFolders, fileSummaryCache, folderTreeCache, loadFileSummary, treeRoot, treeFirst]);

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
      return payload;
    } catch (err) {
      setError(err.message);
      return null;
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

  const handleReset = async () => {
    const payload = await applyPayload(
      postTreatment(treatmentSessionId, '/api/treatment/session/reset'), true
    );
    if (payload) {
      try {
        window.localStorage.removeItem(sessionBackupKey(treatmentSessionId));
      } catch (_error) {
        // The server-side reset already succeeded.
      }
    }
  };

  const handleQueueRun = async () => {
    setError('');
    setIsQueueLoading(true);
    try {
      const payload = await runTreatmentQueue(treatmentSessionId);
      setTreatmentQueue(payload?.queue || { running: false, jobs: [] });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsQueueLoading(false);
    }
  };

  const handleAllowedRootChange = async () => {
    const nextAllowedRoot = draftAllowedRoot.trim();
    if(manifestProjectFolder){
      if(!nextAllowedRoot||nextAllowedRoot===session.folder_path)return;
      const payload=await applyPayload(postTreatment(treatmentSessionId,'/api/treatment/session/folder',{folder_path:nextAllowedRoot}),true);
      if(payload){setTreeRoot(payload.session.folder_path);setDraftAllowedRoot(payload.session.folder_path);setIsFolderTreeOpen(true);}
      return;
    }
    if (!nextAllowedRoot || nextAllowedRoot === treatment.allowed_root) {
      return;
    }

    setError('');
    setIsBusy(true);
    try {
      let payload = await postTreatment(treatmentSessionId, '/api/treatment/session/root', {
        allowed_root: nextAllowedRoot,
      });
      if (treatmentContext?.initialFolder) {
        try {
          payload = await postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
            folder_path: treatmentContext.initialFolder,
          });
        } catch (err) {
          setError(`Cannot open selected folder: ${err.message}. Check Data Root.`);
        }
      }
      if (shouldApplyAutoPreset(payload.session, profilePreset)) {
        payload = await postTreatment(treatmentSessionId, '/api/treatment/session/config', profilePreset);
      }
      setTreatment(payload);
      setDraftAllowedRoot(payload.allowed_root || '');
      setCleaningSummary(null);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(payload.session.folder_path || payload.allowed_root);
      const rootPayload = await fetchFolderListing(treatmentSessionId, payload.allowed_root);
      cacheFolderListing(payload.allowed_root, rootPayload);
      setTreeRoot(payload.session.folder_path || payload.allowed_root || '');
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

  const handlePreviewDat = async filePath => {
    if (isBusy) return;
    setIsBusy(true); setError(''); setFileContextMenu(null);
    try {
      await postTreatment(treatmentSessionId, '/api/treatment/preview/dat', { file_path: filePath });
      requestSelectionRefresh?.();
      setOperationMessage(`Preview: ${pathName(filePath)}`);
    } catch (cause) { setError(cause.message); }
    finally { setIsBusy(false); }
  };
  const handleManifestFolder = async folder => {
    setFolderContextMenu(null); setIsBusy(true); setError('');
    try {
      const listing = await fetchFolderListing(treatmentSessionId, folder);
      const manifest = listing.files.find(isProjectManifest);
      if (!manifest) throw new Error('No vd2-manifest.json in this project folder.');
      treatmentContext?.onOpenManifest?.(manifest.path);
    } catch (cause) { setError(cause.message); }
    finally { setIsBusy(false); }
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
    setSelectedFolders([]);
    folderSelectionAnchor.current = null;
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
    const root=manifestProjectFolder?(session?.folder_path||manifestProjectFolder):treatment.allowed_root;
    setTreeRoot(root);
    setExpandedFolders((current) => {
      const next = new Set(current);
      next.add(root);
      return next;
    });
    try {
      await loadFolderTreeNode(root);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFileContextMenu = (event, file) => {
    event.preventDefault();
    event.stopPropagation();
    if ((!treeFirst && !file.supported && !isProjectManifest(file)) || isBusy) {
      return;
    }
    setFolderContextMenu(null);
    const bounds = event.currentTarget.getBoundingClientRect();
    setFileContextMenu({
      file,
      x: event.clientX ?? bounds.left,
      y: event.clientY ?? bounds.bottom,
    });
  };

  const handleFolderContextMenu = (event, folder) => {
    event.preventDefault();
    event.stopPropagation();
    if (!folder?.path || isBusy) {
      return;
    }
    setFileContextMenu(null);
    const paths = selectedFolders.includes(folder.path) ? selectedFolders : [folder.path];
    if (treeFirst) setSelectedFolders(paths);
    setFolderContextMenu({
      folder,
      paths,
      x: event.clientX,
      y: event.clientY,
    });
  };

  const handleTreeFolderClick = (event, folderPath, siblings) => {
    if (!treeFirst || isSelectingFolderRoot) {
      handleExplorerFolderSelect(folderPath);
      return;
    }
    const anchor = siblings.indexOf(folderSelectionAnchor.current);
    const clicked = siblings.indexOf(folderPath);
    if (event.shiftKey && anchor >= 0) {
      setSelectedFolders(siblings.slice(Math.min(anchor, clicked), Math.max(anchor, clicked) + 1));
      return;
    }
    folderSelectionAnchor.current = folderPath;
    setSelectedFolders(current => event.ctrlKey || event.metaKey
      ? current.includes(folderPath) ? current.filter(path => path !== folderPath) : [...current, folderPath]
      : [folderPath]);
  };

  const toggleBatchFolder = (folderPath) => {
    setIsSelectingFolderRoot(false);
    folderSelectionAnchor.current = folderPath;
    setSelectedFolders(current => current.includes(folderPath)
      ? current.filter(path => path !== folderPath)
      : [...current, folderPath]);
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
    if (requireAppliedCleaningPreview()) {
      return;
    }
    setError('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/calc-abs');
      setTreatment(payload);
      setSavedResultPath('');
      if (treeFirst) setActiveTab('files');
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
      const output = {};
      if (draftSaveFolder !== session.save_folder) output.save_folder = draftSaveFolder;
      if (draftSaveFileName !== session.save_file_name) output.save_file_name = draftSaveFileName;
      if (Object.keys(output).length) {
        await postTreatment(treatmentSessionId, '/api/treatment/session/config', output);
      }
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/save');
      setTreatment(payload);
      const savePath = String(payload?.saved?.save_path || '');
      setSavedResultPath(savePath);
      setOperationMessage(savePath ? `Result saved to ${savePath}` : 'Result saved on the backend.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleCopySavedResultPath = async () => {
    if (!savedResultPath) {
      return;
    }
    try {
      await navigator.clipboard.writeText(savedResultPath);
      setError('');
      setOperationMessage('Result path copied.');
    } catch (_error) {
      setError('Could not copy the result path. Select and copy it manually.');
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
    if (pendingCleaningPreview && pendingCleaningPreview.dataType !== dataType) {
      setError(
        `Apply or reset the ${pendingCleaningPreview.dataType} cleaning preview before selecting another role.`
      );
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

  const handleCleaningThresholdChange = (field, value) => {
    if (field === 'angle') {
      setCleaningAngleThreshold(value);
    } else {
      setCleaningSurfaceThreshold(value);
    }
    if (pendingCleaningPreview) {
      setPendingCleaningPreview((current) => current && {
        ...current,
        invalidated: true,
      });
      setOperationMessage('Cleaning preview invalidated after threshold change. Preview cleaning again before applying a mask to H5.');
    }
  };

  const handleCleaningAction = async (mode) => {
    if (
      mode === 'analyze' &&
      pendingCleaningPreview &&
      pendingCleaningPreview.dataType !== cleaningActiveDataType
    ) {
      setError(
        `Apply or reset the ${pendingCleaningPreview.dataType} cleaning preview before previewing another role.`
      );
      return;
    }
    if (
      mode === 'save' &&
      !canApplyCleaningPreview
    ) {
      setError('Preview cleaning again with the current thresholds before applying a map selection to H5.');
      return;
    }
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
        setPendingCleaningPreview(null);
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
        setPendingCleaningPreview(null);
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
            ? `Re-included ${payload.cleaning.restored_measurements} maps for processing.`
            : 'All raw maps are already included.'
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
          setPendingCleaningPreview(null);
          setOperationMessage(
            `Cleaned H5 saved to ${payload.cleaning.output_path} and assigned as ${payload.cleaning.assigned_data_type || session?.active_data_type || 'active file'}.`
          );
          if (requestSelectionRefresh) {
            requestSelectionRefresh();
          }
          refreshCleaningView();
        } else if (payload.cleaning.state_updated === false) {
          setPendingCleaningPreview(null);
          setOperationMessage(payload.cleaning.warning || 'No measurements passed the thresholds.');
        } else if (payload.cleaning.source_measurements !== payload.cleaning.original_measurements) {
          setPendingCleaningPreview({
            dataType: cleaningActiveDataType,
            sourcePath: cleaningSourcePath,
            angleThreshold: cleaningAngleThreshold,
            surfaceThreshold: cleaningSurfaceThreshold,
          });
          setOperationMessage(
            `Cleaning preview prepared from ${payload.cleaning.source_measurements} currently included maps. Apply mask to H5 before calculating OD.`
          );
        } else {
          setPendingCleaningPreview({
            dataType: cleaningActiveDataType,
            sourcePath: cleaningSourcePath,
            angleThreshold: cleaningAngleThreshold,
            surfaceThreshold: cleaningSurfaceThreshold,
          });
          setOperationMessage('Cleaning preview prepared from original file maps. Apply mask to H5 before calculating OD.');
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
          className={`explorer-tree-file-row ${file.supported || isProjectManifest(file) ? '' : 'is-disabled'}`}
          style={{ paddingLeft: `${treeFirst ? level * 10 + 13 : level * 14 + 28}px` }}
          onContextMenu={isV0Profile ? undefined : (event) => handleFileContextMenu(event, file)}
          title={treeFirst ? file.name : file.path}
        >
          <button
            className="explorer-tree-file-name"
            onDoubleClick={() => {
              if (String(file.suffix).toLowerCase() === '.dat') handlePreviewDat(file.path);
              else if (isProjectManifest(file)) treatmentContext?.onOpenManifest?.(file.path);
            }}
            onKeyDown={treeFirst ? event => {
              if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) handleFileContextMenu(event, file);
            } : undefined}
            disabled={(!treeFirst && !file.supported && !isProjectManifest(file)) || isBusy}
          >
            {file.name}
          </button>
          {!treeFirst && <><span className="explorer-file-meta explorer-file-size" title={`Size: ${formatFileSize(file.size_bytes)}`}>
            S:{formatFileSize(file.size_bytes)}
          </span>
          <span className="explorer-file-meta explorer-file-frames" title={`Frames: ${frames}`}>
            F:{frames}
          </span>
          <span className="explorer-file-meta explorer-file-time" title={`Time: ${timeRange}`}>
            T:{timeRange}
          </span>
          <span className="explorer-file-meta explorer-file-wavelength" title={`Wavelength: ${wavelengths}`}>
            W:{wavelengths}
          </span>
          </>}
        </div>
      );
    });

  const renderFolderTreeRows = (folders, level = 1) =>
    (folders || []).map((folder) => {
      const isExpanded = expandedFolders.has(folder.path);
      const cachedListing = folderTreeCache[folder.path];
      const isSelected = treeFirst ? selectedFolders.includes(folder.path) : session.folder_path === folder.path;
      const folderName = folder.name || pathName(folder.path);

      return (
        <React.Fragment key={folder.path}>
          <div
            className={`explorer-tree-row ${treeFirst ? 'with-folder-selection ' : ''}${isSelected ? 'is-selected' : ''}`}
            style={{ paddingLeft: `${level * (treeFirst ? 10 : 14)}px` }}
            onContextMenu={isV0Profile ? undefined : (event) => handleFolderContextMenu(event, folder)}
          >
            <button
              className="explorer-tree-toggle"
              onClick={() => handleFolderTreeToggle(folder.path)}
              aria-label={isExpanded ? 'Collapse folder' : 'Expand folder'}
            >
              {isExpanded ? 'v' : '>'}
            </button>
            {treeFirst && <input type="checkbox" className="explorer-folder-checkbox"
              aria-label={`Select ${folderName} for batch`} checked={isSelected}
              disabled={isBusy || isQueueLoading || treatmentQueue?.running}
              onChange={() => toggleBatchFolder(folder.path)} />}
            <button
              className="explorer-tree-name"
              onClick={(event) => handleTreeFolderClick(event, folder.path, folders.map(item => item.path))}
              aria-pressed={treeFirst ? isSelected : undefined}
              title={folder.path}
            >
              {folderName}
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

  const explorerRoot = sourceFolder;
  const explorerRootListing = folderTreeCache[explorerRoot] || { folders: [], files: [] };
  const refreshVisibleFolders = useCallback(async (isCurrent = () => true) => {
    const paths = [explorerRoot, ...Array.from(expandedFolders).filter(path =>
      path !== explorerRoot && folderPathChain(path, explorerRoot).length > 0)];
    await Promise.all(paths.filter(Boolean).map(async path => {
      const listing = await fetchFolderListing(treatmentSessionId, path);
      if (isCurrent()) cacheFolderListing(path, listing);
    }));
  }, [cacheFolderListing, expandedFolders, explorerRoot, treatmentSessionId]);

  useEffect(() => {
    if (!treeFirst || !explorerRoot) return undefined;
    let active = true;
    let timer;
    const poll = async () => {
      try { await refreshVisibleFolders(() => active); }
      catch (_error) { /* Keep the current listing during a transient read failure. */ }
      if (active) timer = window.setTimeout(poll, 5000);
    };
    timer = window.setTimeout(poll, 5000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [explorerRoot, refreshVisibleFolders, treeFirst]);
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
        {error ? <TreatmentError message={error} /> : <p>Loading treatment session...</p>}
        <button onClick={refreshSession}>Retry</button>
      </div>
    );
  }

  const dataLocation = (
      <details className="treatment-source-settings">
        <summary>Data location</summary>
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
      </details>
  );
  const sourceBrowser = (
    <div className="zone files-folder">
      {!treeFirst && <>
        {isStudioLayout ? <div className="zone-heading"><h3>1 Source</h3></div> : <h3>Files</h3>}
        <code className="treatment-selected-folder" title={explorerRoot}>{explorerRoot || 'No folder selected'}</code>
        {dataLocation}
      </>}
      <div className="folder-selection-header">
        <button onClick={handleFolderTreeOpen} disabled={!explorerRoot || (treeFirst && (isQueueLoading || treatmentQueue?.running))}>
          Select Folder
        </button>
        {treeFirst && <button type="button" aria-label="Refresh tree" title="Refresh tree"
          onClick={() => refreshVisibleFolders().catch(cause => setError(cause.message))}>↻</button>}
        {treeFirst && selectedFolders.length > 0 && (
          <button type="button" aria-label={`Run selected folders (${selectedFolders.length})`}
            title="Calculate and save the selected measurement folders"
            disabled={isBusy || isQueueLoading || treatmentQueue?.running}
            onClick={() => handleQueueStandardFolder(selectedFolders, {
              label: 'Calculate & save', convert: false, clean: false, calculate: true,
            })}>
            Run ({selectedFolders.length})
          </button>
        )}
        {!treeFirst && !isV0Profile && <button type="button" disabled={!explorerRoot || isSelectingFolderRoot || isBusy || isQueueLoading || treatmentQueue?.running}
          onClick={handleLoadFolderInputs}>
          Load folder inputs
        </button>}
        {!treeFirst && !isV0Profile && <button type="button" onClick={() => treatmentContext?.onOpenManifest?.('')}
          disabled={isBusy || !treatmentContext?.onOpenManifest}>Open manifest…</button>}
      </div>
      {treeFirst && isSelectingFolderRoot && <small role="status">Open a folder by name, or tick folders to run together.</small>}
      {isFolderTreeOpen && (
      <div className="explorer-panel">
        <div className="explorer-tree" role="tree" aria-label="Files" onKeyDown={treeFirst ? event => {
          if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
            event.preventDefault();
            setSelectedFolders(explorerRootListing.folders.map(folder => folder.path));
          }
        } : undefined}>
          <div
            className={`explorer-tree-row ${
                  (treeFirst ? selectedFolders.includes(explorerRoot) : session.folder_path === explorerRoot) ? 'is-selected' : ''
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
              onClick={event => handleTreeFolderClick(event, explorerRoot, [explorerRoot])}
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
          {treeFirst && <button type="button" onClick={() => {
            const file = fileContextMenu.file;
            setDetailFile(file);
            setFileContextMenu(null);
            loadFileSummary(file);
          }}>Details</button>}
          {isProjectManifest(fileContextMenu.file) ? <button type="button" onClick={() => {
            treatmentContext?.onOpenManifest?.(fileContextMenu.file.path); setFileContextMenu(null);
          }}>Calculate according to manifest…</button> : fileContextMenu.file.supported && <>
          {String(fileContextMenu.file.suffix).toLowerCase() === '.dat' && <button type="button"
            onClick={() => handlePreviewDat(fileContextMenu.file.path)}>Open in Preview</button>}
          {(treeFirst ? assignableDataTypes : ['ABS', 'BASE', 'NOISE']).map((dataType) => (
            <button
              key={dataType}
              onClick={() => handleAssignFile(fileContextMenu.file.path, dataType)}
                disabled={isBusy || (treeFirst && treatmentQueue?.running)}
            >
              Set {dataType}
            </button>
          ))}
          <div className="file-context-menu-separator" />
          <button
            onClick={() => handleCompressFile(fileContextMenu.file.path)}
              disabled={isBusy || (treeFirst && treatmentQueue?.running)}
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
          </>}
        </div>
      )}
      {!isV0Profile && folderContextMenu && (
        <div
          className="file-context-menu"
          style={{ left: folderContextMenu.x, top: folderContextMenu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          {folderContextMenu.paths.length > 1 && <p className="treatment-menu-count">{folderContextMenu.paths.length} folders</p>}
          <button type="button" disabled={isBusy || folderContextMenu.paths.length !== 1} onClick={() => handleManifestFolder(folderContextMenu.folder.path)}>
            Calculate according to manifest…
          </button>
          {treeFirst ? [
            ['Set', false, false, false],
            ['Convert', true, false, false],
            ['Clean', true, true, false],
            ['Calculate & save', false, false, true],
            ['Clean, calculate & save', true, true, true],
          ].map(([label, convert, clean, calculate]) => (
            <button key={label} type="button" disabled={isBusy || isQueueLoading || treatmentQueue?.running}
              onClick={() => handleQueueStandardFolder(folderContextMenu.paths, { label, convert, clean, calculate })}>
              {label}
            </button>
          )) : <>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert',
              convert: true,
              clean: false,
              calculate: false,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert/Clean',
              convert: true,
              clean: true,
              calculate: false,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert/Clean
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert/Calc (all maps)',
              convert: true,
              clean: false,
              calculate: true,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert/Calc (all maps)
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set/Convert/Clean/Calc',
              convert: true,
              clean: true,
              calculate: true,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set/Convert/Clean/Calc
          </button>
          <button
            onClick={() => handleQueueStandardFolder(folderContextMenu.folder.path, {
              label: 'Set',
              convert: false,
              clean: false,
              calculate: false,
            })}
            disabled={isBusy || isQueueLoading}
          >
            Set
          </button>
          </>}
        </div>
      )}
    </div>
  );
  const detailSummary = detailFile && fileSummaryCache[detailFile.path];
  const QueuePanel = treeFirst ? 'details' : 'section';
  const activeQueueJob = queueJobs.find(job => job.status === 'running');
  const lastFolderJob = [...queueJobs].reverse().find(job => job.recipe?.kind === 'standard_folder_set');

  return (
    <div className={`tabs-control${treeFirst ? ' treatment-tree-first' : ''}`}>
      {treeFirst && <div className="treatment-tree-and-preview" style={{ '--tree-width': `${filesLayout.tree}px` }}>
        {sourceBrowser}
        <div className="treatment-tree-separator" role="separator" tabIndex={0} aria-label="Resize folders"
          aria-orientation="vertical" aria-valuemin={MIN_TREE_WIDTH} aria-valuemax={MAX_TREE_WIDTH} aria-valuenow={filesLayout.tree}
          onPointerDown={handleTreePointerDown} onPointerMove={handleTreePointerMove}
          onLostPointerCapture={finishTreeResize} onKeyDown={handleTreeResizeKey} />
        {preview}
      </div>}
      {detailFile && <div className="treatment-dialog-backdrop">
        <section role="dialog" aria-modal="true" aria-label="File details" className="treatment-manifest-dialog"
          onKeyDown={event => { if (event.key === 'Escape') setDetailFile(null); }}>
          <header><h2>{detailFile.name}</h2><button type="button" autoFocus aria-label="Close file details" onClick={() => setDetailFile(null)}>×</button></header>
          <dl className="treatment-file-details">
            <dt>Path</dt><dd>{detailFile.path}</dd>
            <dt>Size</dt><dd>{formatFileSize(detailFile.size_bytes)}</dd>
            {detailSummary && !detailSummary.loading && !detailSummary.error && <>
              <dt>Frames</dt><dd>{formatFrameCount(detailSummary)}</dd>
              <dt>Time</dt><dd>{formatTimeRange(detailSummary)}</dd>
              <dt>Wavelength</dt><dd>{formatWavelengthRange(detailSummary)}</dd>
            </>}
          </dl>
          {detailSummary?.loading && <p role="status">Reading file details…</p>}
          {detailSummary?.error && <TreatmentError message={detailSummary.error} />}
        </section>
      </div>}
      {!isV0Profile && (
        <div className="tabs">
          {treeFirst ? <label className="treatment-experiment-type">Experiment type
            <select aria-label="Experiment type" disabled={isBusy || treatmentQueue?.running}
              value={session.exp_type} onChange={event => handleConfigChange({ exp_type: event.target.value })}>
              {(treatment.exp_types || []).map(type => <option key={type} value={type}>{type}</option>)}
            </select>
          </label> : <button
            className={activeTab === 'files' ? 'is-active' : ''}
            onClick={() => setActiveTab('files')}
            aria-pressed={activeTab === 'files'}
          >
            {isStudioLayout ? 'Treatment' : 'Files'}
          </button>}
          {treeFirst && <button type="button" onClick={handleCalcAbs}
            disabled={isBusy || isQueueLoading || treatmentQueue?.running || !session.ready_for_calc || Boolean(pendingCleaningPreview)}>
            Calculate OD
          </button>}
          <button
            className={activeTab === 'cleaning' ? 'is-active' : ''}
            onClick={() => setActiveTab(treeFirst && activeTab === 'cleaning' ? 'files' : 'cleaning')}
            aria-pressed={activeTab === 'cleaning'}
            disabled={isBusy || (treeFirst && treatmentQueue?.running)}
          >
            {treeFirst && activeTab === 'cleaning' ? 'Close Cleaning' : 'Cleaning'}
          </button>
          {treeFirst && <button type="button" className={activeTab === 'skana' ? 'is-active' : ''}
            onClick={() => setActiveTab(activeTab === 'skana' ? 'files' : 'skana')}
            aria-pressed={activeTab === 'skana'} disabled={isBusy}>
            SK-Ana
          </button>}
          <details className="treatment-more-tools"
            open={(treeFirst ? activeTab === 'stitch' : ['stitch', 'info', 'skana'].includes(activeTab)) || undefined}>
          <summary>{treeFirst ? 'Tools' : 'More tools'}</summary>
          <div>
          <button
            className={`secondary-tab ${activeTab === 'stitch' ? 'is-active' : ''}`}
            onClick={() => setActiveTab(treeFirst && activeTab === 'stitch' ? 'files' : 'stitch')}
            aria-pressed={activeTab === 'stitch'}
            disabled={isBusy}
          >
            Stitch
          </button>
          {!treeFirst && <><button
            className={activeTab === 'info' ? 'is-active' : ''}
            onClick={() => setActiveTab(treeFirst && activeTab === 'info' ? 'files' : 'info')}
            aria-pressed={activeTab === 'info'}
          >
            Info
          </button>
          <button type="button" className={activeTab === 'skana' ? 'is-active' : ''}
            onClick={() => setActiveTab('skana')} aria-pressed={activeTab === 'skana'} disabled={isBusy}>
            SK-Ana
          </button></>}
          </div>
          </details>
        </div>
      )}
      {treeFirst && !isV0Profile && <details className="treatment-manual-inputs">
        <summary>Manual inputs · {assignedCleaningTypes.length}/{assignableDataTypes.length}</summary>
        <p>For older projects, right-click each input file and choose its role
          {assignableDataTypes.length > 0 && ` (${assignableDataTypes.map(type => `Set ${type}`).join(', ')})`}.
          Then click Calculate OD.
          {assignableDataTypes.includes('ABS') && ' ABS is the absorption file.'}</p>
        <AssignedPaths session={session} />
      </details>}
      <TreatmentError message={error} />
      {treeFirst && treatmentQueue?.running && <p className="treatment-tree-status" role="status">
        {activeQueueJob?.label || 'Processing folders'} · {activeQueueJob?.phase || 'running'}
      </p>}
      {treeFirst && lastFolderJob?.status === 'failed' && (
        <TreatmentError message={`${lastFolderJob.label}: ${lastFolderJob.error || lastFolderJob.message}`} />
      )}
      {treeFirst && !treatmentQueue?.running && lastFolderJob?.status === 'completed' && (
        <p className="treatment-tree-status" role="status">{lastFolderJob.label} · completed</p>
      )}
                  {operationMessage && (
                  <p className={`treatment-operation-message ${isOperationRunning ? 'is-active' : ''}`}>
                    {isOperationRunning && (
                        <span className="treatment-operation-live">
                          <span className="treatment-operation-spinner" aria-hidden="true"></span>
                          <span>{busyElapsedSeconds}s</span>
                        </span>
                      )}
                      {operationMessage}
                    </p>
                  )}
      <div className="tab-content">
        {activeTab === 'skana' && <SkanaPanel />}
        {activeTab === 'files' && (
          <div
            className={`files-tab horizontal-layout ${isV0Profile ? 'is-v0-profile' : ''}`}
            ref={filesLayoutRef}
            style={isV0Profile || isStudioLayout ? undefined : { gridTemplateColumns: filesGridTemplate }}
          >
            {!treeFirst && sourceBrowser}
            {!isV0Profile && (
              <>
                {!treeFirst && <div
                  className="column-resizer roles-resizer"
                  role="separator"
                  aria-label="Resize processing controls"
                  onMouseDown={(event) => handleFilesColumnResizeStart('selected', event)}
                />}
                {(!treeFirst || queueJobs.length > 0) && <div className="zone raw-data-kinetics">
                  {!treeFirst && <>
                  <details className="treatment-assigned-inputs">
                    <summary>Input files · {Object.keys(session.paths || {}).length} assigned</summary>
                    <AssignedPaths session={session} />
                  </details>
                  <section className="treatment-step">
                    <h3>2 Cleaning</h3>
                    <button type="button" onClick={() => setActiveTab('cleaning')} disabled={isBusy || !assignedCleaningTypes.length}>Review cleaning</button>
                    <span>{pendingCleaningPreview ? 'Preview needs review' : 'Inspect and apply map selection'}</span>
                  </section>
                  <section className="treatment-step">
                    <h3>3 Calculate</h3>
                    <button onClick={handleCalcAbs} disabled={isBusy || !session.ready_for_calc || Boolean(pendingCleaningPreview)}>
                      Calculate OD
                    </button>
                    <span>{session.result_ready ? 'Result ready to save' : session.ready_for_calc ? session.calc_mode : 'Assign the required input files'}</span>
                  </section>
                  {pendingCleaningPreview && (
                    <div className="treatment-cleaning-pending" role="status">
                      <strong>Cleaning preview not applied</strong>
                      <span>
                        {pendingCleaningPreview.stale
                          ? `${pendingCleaningPreview.dataType} has a backend cleaning preview. Preview again with the current thresholds before applying it.`
                          : `${pendingCleaningPreview.dataType} still uses its previous H5 map selection for processing.`}
                      </span>
                    </div>
                  )}
                  {savedResultPath && (
                    <div className="treatment-save-receipt" role="status">
                      <strong>Result saved</strong>
                      <code title={savedResultPath}>{savedResultPath}</code>
                      <button type="button" onClick={handleCopySavedResultPath}>
                        Copy path
                      </button>
                    </div>
                  )}
                  </>}
                  {isStudioLayout && (
                    <QueuePanel className="treatment-queue" aria-labelledby="treatment-queue-heading">
                      {treeFirst ? <summary id="treatment-queue-heading">Queue · {queueJobs.length} jobs</summary> : <div className="treatment-queue-heading">
                        <h4 id="treatment-queue-heading">Queue</h4>
                        <span className={`treatment-queue-status ${treatmentQueue?.running ? 'is-running' : ''}`}>
                          {treatmentQueue?.running ? 'Running' : 'Idle'}
                        </span>
                      </div>}
                      {!treeFirst && <details className="treatment-batch-options">
                        <summary>Batch options</summary>
                      <input
                        className="treatment-queue-label-input"
                        type="text"
                        aria-label="Queue label"
                        value={queueLabel}
                        onChange={(event) => setQueueLabel(event.target.value)}
                        placeholder={pathName(session.folder_path) || 'Sample name'}
                        disabled={isQueueLoading || isBusy}
                      />
                      <label
                        className="treatment-queue-option"
                        title={
                          queueSupportsCurrentRecipeCleaning
                            ? `Use current SAM thresholds for ${assignedCleaningTypes.join(', ')}.`
                            : 'Used for automatic cleaning when queuing a folder.'
                        }
                      >
                        <input
                          type="checkbox"
                          checked={queueApplyCleaning}
                          onChange={(event) => setQueueApplyCleaning(event.target.checked)}
                          disabled={isQueueLoading || isBusy}
                        />
                        SAM cleaning
                      </label>
                      <div className="treatment-queue-actions">
                        <button
                          type="button"
                          onClick={handleQueueEnqueue}
                          disabled={
                            isQueueLoading ||
                            isBusy ||
                            !session.ready_for_calc ||
                            !queueOutputConfigured ||
                            Boolean(pendingCleaningPreview)
                          }
                        >
                          Add recipe
                        </button>
                      </div>
                      </details>}
                      {!treatmentQueue?.running && Number(treatmentQueue?.pending_count || 0) > 0 && (
                        <button type="button" onClick={handleQueueRun} disabled={isQueueLoading || isBusy}>Resume queue</button>
                      )}
                      {queueJobs.length > 0 ? (
                        <ol className="treatment-queue-jobs" aria-live="polite">
                          {queueJobs.map((job) => (
                            <li key={job.job_id || `${job.label}-${job.created_at || ''}`} className={`is-${job.status || 'queued'}`}>
                              <div>
                                <strong>{job.label || job.recipe?.label || 'Treatment recipe'}</strong>
                                <span>{job.status || 'queued'} · {job.phase || 'queued'}</span>
                              </div>
                              {job.status === 'queued' && job.job_id && (
                                <button
                                  type="button"
                                  className="treatment-queue-remove"
                                  onClick={() => handleQueueRemove(job.job_id)}
                                  disabled={isQueueLoading}
                                >
                                  Remove
                                </button>
                              )}
                              {job.error && <p role="alert">{job.error}</p>}
                              {(job.message || job.preparation) && <details className="treatment-job-details">
                              <summary>Processing details</summary>
                              {job.message && <p>{job.message}</p>}
                              {Object.entries(
                                job.preparation?.folder_set?.cleaned || job.preparation?.cleaned || {}
                              ).map(([role, summary]) => {
                                const total = Number(summary?.original_measurements);
                                const kept = Number(summary?.cleaned_measurements);
                                const removed = Number(summary?.removed_measurements);
                                if (!Number.isFinite(total) || !Number.isFinite(kept) || !Number.isFinite(removed)) {
                                  return null;
                                }
                                return (
                                  <p key={`cleaned-${role}`}>
                                    {role}: {kept}/{total} maps retained · {removed} removed
                                    {total > 0 ? ` (${(removed / total * 100).toFixed(1)}%)` : ''}
                                  </p>
                                );
                              })}
                              {job.preparation?.folder_set?.map_policy === 'all_raw_maps' && (
                                <>
                                  <p>Uncleaned calculation · all raw maps used; saved H5 masks unchanged.</p>
                                  {Object.entries(job.preparation.folder_set.map_counts || {}).map(([role, counts]) => (
                                    <p key={`raw-${role}`}>
                                      {role}: {counts.used_count}/{counts.total_count} raw maps used
                                      {counts.stored_mask_included_count < counts.total_count
                                        ? ` · prior mask ${counts.stored_mask_included_count}/${counts.total_count} ignored`
                                        : ''}
                                    </p>
                                  ))}
                                </>
                              )}
                              </details>}
                              {(job.saved?.save_path || job.result?.save_path) && (
                                <code>{job.saved?.save_path || job.result?.save_path}</code>
                              )}
                            </li>
                          ))}
                        </ol>
                      ) : null}
                    </QueuePanel>
                  )}
                </div>}
              </>
            )}
            {!isV0Profile && (!treeFirst || session.result_ready) && (
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
                    layoutMode={treatmentLayoutMode}
                    onSave={handleSave}
                    onAverageNoise={handleAverageNoise}
                    canAverageNoise={canAverageNoise}
                    compact={treeFirst}
                    busy={isBusy || (treeFirst && treatmentQueue?.running)}
                  />
                </div>
                {!treeFirst && <div
                  className="column-resizer source-resizer"
                  role="separator"
                  aria-label="Resize source files"
                  onMouseDown={(event) => handleFilesColumnResizeStart('parameters', event)}
                />}
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
                <div role="group" aria-label="Cleaning input files" className="cleaning-role-switch">
                  {assignableDataTypes.map(dataType => {
                    const source = session.path_sources?.[dataType] || session.paths?.[dataType];
                    const label = { ABS: 'Absorption', BASE: 'Base', NOISE: 'Bruit / Noise' }[dataType] || dataType;
                    return <button key={dataType} type="button" aria-pressed={cleaningActiveDataType === dataType}
                      disabled={isBusy || !source} title={source || `${label}: no file assigned. Set the sample folder in Treatment.`}
                      onClick={() => handleCleaningTargetChange(dataType)}>
                      {label}<small>{source ? pathName(source) : 'Not assigned'}</small>
                    </button>;
                  })}
                </div>
                <details className="treatment-advanced-settings">
                <summary>Cleaning settings</summary>
                <div className="treatment-settings-fields">
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
                    onChange={(event) => handleCleaningThresholdChange('angle', event.target.value)}
                  />
                </label>
                <label>
                  Surface Threshold (%)
                  <input
                    type="number"
                    min="0.01"
                    step="0.1"
                    value={cleaningSurfaceThreshold}
                    onChange={(event) => handleCleaningThresholdChange('surface', event.target.value)}
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
                </div>
                </details>
                {treeFirst && assignedCleaningTypes.length === 0 && !cleaningFolders.length && (
                  <p>Select a sample folder in the file tree to start cleaning.</p>
                )}
                <div className="cleaning-actions">
                  {treeFirst && assignedCleaningTypes.length === 0 && (
                    <button type="button"
                      disabled={isBusy || isQueueLoading || treatmentQueue?.running || !cleaningFolders.length}
                      onClick={() => handleQueueStandardFolder(cleaningFolders, {
                        label: 'Clean', convert: true, clean: true, calculate: false, returnToFiles: false,
                      })}>
                      Clean session
                    </button>
                  )}
                  <button onClick={() => handleCleaningAction('analyze')} disabled={isBusy || !cleaningActiveDataType}>
                    Preview cleaning
                  </button>
                  <button onClick={() => handleCleaningAction('reset')} disabled={isBusy}>
                    Reset preview
                  </button>
                  <details className="treatment-advanced-settings">
                    <summary>Recovery options</summary>
                    <button onClick={() => handleCleaningAction('restore')} disabled={isBusy || !String(cleaningSourcePath || '').toLowerCase().endsWith('.h5')}>
                      Restore raw-map selection
                    </button>
                  </details>
                  <button
                    onClick={() => handleCleaningAction('save')}
                    disabled={
                      isBusy ||
                      !canApplyCleaningPreview
                    }
                  >
                    Apply mask to H5
                  </button>
                </div>
                {pendingCleaningPreview && (
                  <p className="cleaning-preview-notice" role="status">
                    {pendingCleaningPreview.stale || pendingCleaningPreview.invalidated
                      ? `Preview for ${pendingCleaningPreview.dataType} must be refreshed with the current thresholds before it can be applied. Calculate OD remains blocked until you apply or reset it.`
                      : `Preview for ${pendingCleaningPreview.dataType} is not applied. Calculate OD is blocked until you apply its mask to H5 or reset the preview.`}
                  </p>
                )}
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
                    <strong>Removed:</strong> {cleaningSummary.removed_measurements}
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
        {!treeFirst && activeTab === 'info' && (
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
