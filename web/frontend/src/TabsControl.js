import React, {
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import {
  fetchCleaningView,
  fetchFileSummary,
  fetchFolderListing,
  fetchTreatmentSession,
  postTreatment,
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
  onApplyProfilePreset,
  isBusy,
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
      <div className="parameter-field">
        <label>Save Folder:</label>
        <input
          type="text"
          value={draftSaveFolder}
          onChange={(event) => onDraftSaveFolderChange(event.target.value)}
          onBlur={onCommitSaveFolder}
          placeholder="Select a folder inside the treatment root"
        />
      </div>
      <div className="parameter-field">
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
        <button onClick={onApplyProfilePreset} disabled={isBusy}>
          Apply {profileName} Preset
        </button>
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

function summarizeFolderSet(payload, label, folderPath) {
  const folderSet = payload.folder_set || {};
  const assignedTypes = Object.keys(folderSet.assigned || {});
  const conversions = Object.values(folderSet.conversions || {});
  const cleanedTypes = Object.keys(folderSet.cleaned || {});
  const converted = conversions.filter((item) => item.converted);
  const reused = conversions.filter((item) => item.converted === false);
  const deletedHisCount = conversions.filter((item) => item.deleted_source).length;
  const sourceBytes = converted.reduce(
    (total, item) => total + Number(item.source_size_bytes || 0),
    0
  );
  const outputBytes = converted.reduce(
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
      `Converted: ${converted.length}; reused H5: ${reused.length}; removed HIS: ${deletedHisCount}.`
    );
  }
  if (converted.length) {
    const percent = sourceBytes
      ? `${((spaceChange / sourceBytes) * 100).toFixed(1)}%`
      : '0.0%';
    lines.push(
      `Disk: ${formatFileSize(sourceBytes)} HIS -> ${formatFileSize(outputBytes)} H5 (${formatSignedFileSize(spaceChange)}, ${percent}).`
    );
    lines.push('H5 raw_data compression: gzip level 9; file can still grow if source is already compact.');
  }
  if (cleanedTypes.length) {
    lines.push(`Cleaned: ${cleanedTypes.join(', ')}.`);
  }
  return lines.join('\n');
}

function summarizeFileCompression(payload, dataType) {
  const conversion = payload.conversion || {};
  const lines = [`Set to ${dataType} + Compress completed.`];
  if (conversion.converted) {
    lines.push(`${pathName(conversion.source_path)} -> ${pathName(conversion.output_path)}.`);
  } else {
    lines.push(`Reused existing H5: ${pathName(conversion.output_path)}.`);
  }
  lines.push(`Removed HIS: ${conversion.deleted_source ? 'yes' : 'no'}.`);
  lines.push(
    `Disk: ${formatFileSize(conversion.source_size_bytes)} -> ${formatFileSize(conversion.output_size_bytes)} (${formatSignedFileSize(conversion.space_change_bytes)}, ${Number(conversion.space_change_percent || 0).toFixed(1)}%).`
  );
  lines.push('H5 raw_data compression: gzip level 9.');
  lines.push(`Assigned source: ${payload.session?.path_sources?.[dataType] || conversion.output_path || ''}.`);
  return lines.join('\n');
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

const TabsControl = () => {
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const treatmentProfile = String(treatmentContext?.treatmentProfile || 'VD2').toUpperCase();
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;
  const [activeTab, setActiveTab] = useState('files');
  const [treatment, setTreatment] = useState(null);
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
  const [isBusy, setIsBusy] = useState(false);
  const profilePreset = PROFILE_PRESETS[treatmentProfile] || PROFILE_PRESETS.VD2;

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

    if (nextExpType === 'ABS+BASE+NOISE') {
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

  const handleAssignAndCompressFile = async (filePath, dataType = session?.selected_data_type) => {
    if (!session || !dataType) {
      return;
    }

    setError('');
    setOperationMessage('');
    setSelectionMessage('');
    setCleaningSummary(null);
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/compress-path', {
        data_type: dataType,
        file_path: filePath,
      });
      setTreatment(payload);
      setOperationMessage(summarizeFileCompression(payload, dataType));
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      refreshCleaningView();
      await refreshFolderListing(getParentFolder(filePath, treatment?.allowed_root));
    } catch (err) {
      setError(err.message);
    } finally {
      setFileContextMenu(null);
      setIsBusy(false);
    }
  };

  const handleAssignAndCleanFile = async (filePath, dataType = session?.selected_data_type) => {
    if (!session || !dataType) {
      return;
    }

    setError('');
    setOperationMessage('');
    setSelectionMessage('');
    setCleaningSummary(null);
    setIsBusy(true);
    try {
      await postTreatment(treatmentSessionId, '/api/treatment/session/cache-path', {
        data_type: dataType,
        file_path: filePath,
      });
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/cleaning/save', {
        angle_threshold: Number.parseFloat(cleaningAngleThreshold),
        surface_threshold: Number.parseFloat(cleaningSurfaceThreshold),
        output_file_name: '',
      });
      setTreatment(payload);
      setCleaningSummary(payload.cleaning);
      setOperationMessage(
        `Set to ${dataType}, cleaned, saved to ${payload.cleaning.output_path}.`
      );
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      refreshCleaningView();
    } catch (err) {
      setError(err.message);
    } finally {
      setFileContextMenu(null);
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
    setOperationMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/folder-set', {
        folder_path: folderPath,
        convert,
        clean,
        angle_threshold: Number(cleaningAngleThreshold),
        surface_threshold: Number(cleaningSurfaceThreshold),
      });
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
      const label = clean ? 'Set/Convert/Clean' : convert ? 'Set/Convert' : 'Set';
      setOperationMessage(summarizeFolderSet(payload, label, folderPath));
    } catch (err) {
      setError(err.message);
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

  const handleApplyProfilePreset = async () => {
    setError('');
    setIsBusy(true);
    setOperationMessage('');
    try {
      const payload = await postTreatment(
        treatmentSessionId,
        '/api/treatment/session/config',
        profilePreset
      );
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      setOperationMessage(`${treatmentProfile} preset applied.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
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

  const renderFolderTreeFiles = (files, level = 1) =>
    (files || []).map((file) => {
      const summary = fileSummaryCache[file.path] || {};
      const frames = summary.number_maps ? String(summary.number_maps) : '...';
      const timeScale = summary.time_scale || '...';
      const wavelengths = formatWavelengthRange(summary);
      return (
        <div
          key={file.path}
          className={`explorer-tree-file-row ${file.supported ? '' : 'is-disabled'}`}
          style={{ paddingLeft: `${level * 14 + 28}px` }}
          onContextMenu={(event) => handleFileContextMenu(event, file)}
          title={file.path}
        >
          <button
            className="explorer-tree-file-name"
            onContextMenu={(event) => handleFileContextMenu(event, file)}
            disabled={!file.supported || isBusy}
          >
            {file.name}
          </button>
          <span className="explorer-file-meta">S:{formatFileSize(file.size_bytes)}</span>
          <span className="explorer-file-meta">F:{frames}</span>
          <span className="explorer-file-meta">T:{timeScale}</span>
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
            onContextMenu={(event) => handleFolderContextMenu(event, folder)}
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
      <div className="tabs">
        <button onClick={() => setActiveTab('files')}>Files</button>
        <button onClick={() => setActiveTab('cleaning')}>Cleaning</button>
        <button onClick={() => setActiveTab('info')}>Info</button>
        <button onClick={() => setActiveTab('selection')}>Selection</button>
      </div>
      <div className="tab-content">
        {activeTab === 'files' && (
          <div className="files-tab horizontal-layout">
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
                onApplyProfilePreset={handleApplyProfilePreset}
                isBusy={isBusy}
              />
            </div>
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
                    onContextMenu={(event) =>
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
              {fileContextMenu && (
                <div
                  className="file-context-menu"
                  style={{ left: fileContextMenu.x, top: fileContextMenu.y }}
                  onClick={(event) => event.stopPropagation()}
                >
                  {assignableDataTypes.map((dataType) => (
                    <button
                      key={dataType}
                      onClick={() => handleAssignFile(fileContextMenu.file.path, dataType)}
                      disabled={isBusy}
                    >
                      Set to {dataType}
                    </button>
                  ))}
                  <div className="file-context-menu-separator" />
                  {assignableDataTypes.map((dataType) => (
                    <button
                      key={`${dataType}-clean`}
                      onClick={() => handleAssignAndCleanFile(fileContextMenu.file.path, dataType)}
                      disabled={isBusy}
                    >
                      Set to {dataType} + Clean
                    </button>
                  ))}
                  <div className="file-context-menu-separator" />
                  {assignableDataTypes.map((dataType) => (
                    <button
                      key={`${dataType}-compress`}
                      onClick={() => handleAssignAndCompressFile(fileContextMenu.file.path, dataType)}
                      disabled={isBusy}
                    >
                      Set to {dataType} + Compress
                    </button>
                  ))}
                </div>
              )}
              {folderContextMenu && (
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
              {operationMessage && <p className="treatment-operation-message">{operationMessage}</p>}
            </div>
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
