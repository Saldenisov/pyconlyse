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

export {
  PROFILE_PRESETS, REQUIRED_DATA_TYPES, FILES_LAYOUT_STORAGE_KEY,
  SESSION_BACKUP_STORAGE_PREFIX, CLEANING_DRAFT_STORAGE_PREFIX,
  FOLDER_TREE_OPEN_STORAGE_PREFIX, DEFAULT_FILES_LAYOUT, MIN_TREE_WIDTH, MAX_TREE_WIDTH,
  isProjectManifest, clampNumber, readFilesLayout, saveFilesLayout, sessionBackupKey,
  isEmptyTreatmentSession, hasRecoverableTreatmentWork, readSessionBackup,
  saveSessionBackup, readCleaningDraft, requiredDataTypesForExpType,
  shouldApplyAutoPreset, ParametersZone, getParentFolder, getPathParent, joinPath,
  pathName, pathStem, h5NameForPath, stitchedNameForPaths, stitchRegionsToShapes,
  shapesToStitchRegions, cropHeatmapMap, sortStitchDatFiles, formatFileSize,
  formatSignedFileSize, formatWavelengthRange, formatAxisValue, formatTimeRange,
  formatFrameCount, mergeTreatmentQueue, summarizeFileCompression,
  summarizeCompressionProgress, wait, folderPathChain,
};
