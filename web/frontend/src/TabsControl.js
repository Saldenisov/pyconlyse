import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import {
  fetchFolderListing,
  fetchTreatmentPreview,
  fetchTreatmentSession,
  postTreatment,
} from './api/treatmentClient';
import './css/DataWindowVD2.css';

const SAM_CLEANABLE_SUFFIXES = new Set(['.h5', '.his', '.img']);
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

function isSamCleanableFile(file) {
  const suffix = String(file?.suffix || '').toLowerCase();
  return SAM_CLEANABLE_SUFFIXES.has(suffix);
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
      <h3>Treatment Session</h3>
      <div style={{ marginBottom: '8px', color: '#475467', fontSize: '0.9rem' }}>
        Profile: <strong>{profileName}</strong>
      </div>
      <div>
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
      <div>
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
      <div>
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
      <div>
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
      <div>
        <label>Save Folder:</label>
        <input
          type="text"
          value={draftSaveFolder}
          onChange={(event) => onDraftSaveFolderChange(event.target.value)}
          onBlur={onCommitSaveFolder}
          placeholder="Select a folder inside the treatment root"
        />
      </div>
      <div>
        <label>Save File Name:</label>
        <input
          type="text"
          value={draftSaveFileName}
          onChange={(event) => onDraftSaveFileNameChange(event.target.value)}
          onBlur={onCommitSaveFileName}
          placeholder="result.dat"
        />
      </div>
      <div>
        <button onClick={onApplyProfilePreset} disabled={isBusy}>
          Apply {profileName} Preset
        </button>
      </div>
      <div>
        <button onClick={onReset}>Reset Session</button>
      </div>
    </div>
  );
};

const RawDataKineticsPlot = ({ preview }) => {
  const ref = useRef(null);

  useEffect(() => {
    const plotNode = ref.current;
    if (!plotNode) {
      return undefined;
    }

    const sample = preview && Array.isArray(preview.sample) ? preview.sample : null;
    const isHeatmap =
      sample &&
      sample.length > 0 &&
      Array.isArray(sample[0]) &&
      sample[0].length > 0;

    Plotly.newPlot(
      plotNode,
      isHeatmap
        ? [
            {
              z: sample,
              type: 'heatmap',
              colorscale: 'Viridis',
            },
          ]
        : [
            {
              x: [0, 1, 2, 3],
              y: [3, 8, 5, 7],
              type: 'scatter',
            },
          ],
      { margin: { t: 20 }, width: 300, height: 300 }
    );

    return () => {
      Plotly.purge(plotNode);
    };
  }, [preview]);

  return <div className="raw-data-kinetics-plot" ref={ref}></div>;
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

const AllowedFolderSelector = ({
  sessionId,
  initialFolder,
  allowedRoot,
  onFolderSelect,
  onClose,
}) => {
  const startFolder = initialFolder || allowedRoot || '';
  const [currentFolder, setCurrentFolder] = useState(startFolder);
  const [folders, setFolders] = useState([]);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!currentFolder) {
      setFolders([]);
      return undefined;
    }

    let cancelled = false;
    setIsLoading(true);
    setError('');

    fetchFolderListing(sessionId, currentFolder)
      .then((data) => {
        if (!cancelled) {
          setFolders(data.folders || []);
        }
      })
      .catch((err) => {
        if (!cancelled) {
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
  }, [currentFolder, sessionId]);

  const parentFolder = getParentFolder(currentFolder, allowedRoot);

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          backgroundColor: '#fff',
          padding: '20px',
          borderRadius: '4px',
          width: 'min(800px, 90vw)',
          maxHeight: '80vh',
          overflowY: 'auto',
        }}
      >
        <h3>Select Treatment Folder</h3>
        <p>
          <strong>Allowed Root:</strong> {allowedRoot}
        </p>
        <p>
          <strong>Current Folder:</strong> {currentFolder || 'Not available'}
        </p>
        {error && <p>{error}</p>}
        {isLoading && <p>Loading folders...</p>}
        {!isLoading && !error && folders.length === 0 && (
          <p>No subfolders in this directory.</p>
        )}
        {!isLoading && !error && folders.length > 0 && (
          <div className="folder-tree-view">
            {folders.map((folder) => (
              <div
                key={folder.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                  marginBottom: '8px',
                }}
              >
                <button onClick={() => setCurrentFolder(folder.path)}>{folder.name}</button>
                <button onClick={() => onFolderSelect(folder.path)}>Use</button>
              </div>
            ))}
          </div>
        )}
        <div style={{ marginTop: '10px' }}>
          <button onClick={() => onFolderSelect(currentFolder)} disabled={!currentFolder}>
            Use Current Folder
          </button>
          <button
            onClick={() => setCurrentFolder(parentFolder)}
            disabled={!parentFolder}
            style={{ marginLeft: '10px' }}
          >
            Up One Level
          </button>
          <button onClick={onClose} style={{ marginLeft: '10px' }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

const AssignedPaths = ({ session, onPreview }) => {
  const entries = Object.entries(session.paths || {});
  if (entries.length === 0) {
    return <p>No input files assigned yet.</p>;
  }

  return (
    <div>
      {entries.map(([dataType, filePath]) => (
        <div
          key={dataType}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '8px',
          }}
        >
          <div>
            <strong>{dataType}:</strong> {filePath}
          </div>
          <button onClick={() => onPreview(dataType)}>Preview</button>
        </div>
      ))}
    </div>
  );
};

const TabsControl = () => {
  const treatmentContext = useContext(TreatmentContext);
  const treatmentSessionId = treatmentContext?.treatmentSessionId || '';
  const treatmentProfile = String(treatmentContext?.treatmentProfile || 'VD2').toUpperCase();
  const requestSelectionRefresh = treatmentContext?.requestSelectionRefresh;
  const [activeTab, setActiveTab] = useState('files');
  const [treatment, setTreatment] = useState(null);
  const [folderListing, setFolderListing] = useState({ folders: [], files: [] });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [draftSaveFolder, setDraftSaveFolder] = useState('');
  const [draftSaveFileName, setDraftSaveFileName] = useState('');
  const [draftAllowedRoot, setDraftAllowedRoot] = useState('');
  const [draftKineticsRanges, setDraftKineticsRanges] = useState('');
  const [draftSpectraRanges, setDraftSpectraRanges] = useState('');
  const [cleaningAngleThreshold, setCleaningAngleThreshold] = useState('1.0');
  const [cleaningSurfaceThreshold, setCleaningSurfaceThreshold] = useState('1.0');
  const [cleaningOutputName, setCleaningOutputName] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);
  const [operationMessage, setOperationMessage] = useState('');
  const [selectionMessage, setSelectionMessage] = useState('');
  const [cleaningSummary, setCleaningSummary] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const profilePreset = PROFILE_PRESETS[treatmentProfile] || PROFILE_PRESETS.VD2;

  const session = treatment ? treatment.session : null;
  const requiredDataTypes =
    session?.required_data_types || requiredDataTypesForExpType(session?.exp_type);
  const assignableDataTypes =
    requiredDataTypes && requiredDataTypes.length > 0 ? requiredDataTypes : treatment?.data_types || [];

  const refreshSession = async () => {
    const payload = await fetchTreatmentSession(treatmentSessionId);
    setTreatment(payload);
    if (requestSelectionRefresh) {
      requestSelectionRefresh();
    }
    return payload;
  };

  const refreshFolderListing = useCallback(
    async (folderPath) => {
      if (!folderPath) {
        setFolderListing({ folders: [], files: [] });
        return;
      }

      const payload = await fetchFolderListing(treatmentSessionId, folderPath);
      setFolderListing({
        folders: payload.folders || [],
        files: payload.files || [],
      });
    },
    [treatmentSessionId]
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
  }, [profilePreset, refreshFolderListing, requestSelectionRefresh, treatmentSessionId]);

  useEffect(() => {
    if (!session) {
      return;
    }
    setDraftSaveFolder(session.save_folder || '');
    setDraftSaveFileName(session.save_file_name || '');
    setDraftAllowedRoot(treatment?.allowed_root || '');
    setCleaningOutputName((current) => (
      current || (session.active_data_type ? `${session.active_data_type.toLowerCase()}_cleaned.h5` : '')
    ));
  }, [session, treatment?.allowed_root]);

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

  const handleFolderSelect = (selectedFolder) => {
    if (!selectedFolder) {
      return;
    }
    setIsModalOpen(false);
    applyPayload(
      postTreatment(treatmentSessionId, '/api/treatment/session/folder', {
        folder_path: selectedFolder,
      }),
      true
    );
  };

  const handleAllowedRootChange = async () => {
    if (!draftAllowedRoot || draftAllowedRoot === treatment.allowed_root) {
      return;
    }

    setError('');
    setOperationMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/root', {
        allowed_root: draftAllowedRoot,
      });
      setTreatment(payload);
      setDraftAllowedRoot(payload.allowed_root || '');
      setPreview(null);
      setCleaningSummary(null);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      await refreshFolderListing(payload.session.folder_path || payload.allowed_root);
      setOperationMessage(`Data root set to ${payload.allowed_root}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleAssignFile = (filePath) => {
    if (!session) {
      return;
    }
    applyPayload(
      postTreatment(treatmentSessionId, '/api/treatment/session/path', {
        data_type: session.selected_data_type,
        file_path: filePath,
      })
    );
  };

  const handleCacheAssignFile = async (filePath) => {
    if (!session) {
      return;
    }

    setError('');
    setOperationMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/cache-path', {
        data_type: session.selected_data_type,
        file_path: filePath,
      });
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      const cachedPath = payload.cached_file?.cached_path || filePath;
      setOperationMessage(`Cached and assigned ${session.selected_data_type}: ${cachedPath}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleAutoAssignFiles = async () => {
    if (!session?.folder_path) {
      return;
    }

    setError('');
    setOperationMessage('');
    setIsBusy(true);
    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/session/auto-assign', {
        folder_path: session.folder_path,
      });
      setTreatment(payload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      const assignedTypes = Object.keys(payload.auto_assigned || {});
      const missingTypes = payload.auto_assign_missing || [];
      if (assignedTypes.length > 0) {
        setOperationMessage(
          `Auto assigned ${assignedTypes.join(', ')}${
            missingTypes.length > 0 ? `; missing ${missingTypes.join(', ')}` : ''
          }.`
        );
      } else {
        setOperationMessage('No matching ABS/BASE/NOISE files found in this folder.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handlePreview = async (dataType) => {
    setError('');
    setIsBusy(true);
    try {
      const sessionPayload = await postTreatment(treatmentSessionId, '/api/treatment/session/selection', {
        active_data_type: dataType,
        map_index: 0,
      });
      setTreatment(sessionPayload);
      if (requestSelectionRefresh) {
        requestSelectionRefresh();
      }
      const payload = await fetchTreatmentPreview(treatmentSessionId, dataType);
      setPreview(payload.preview);
      setOperationMessage(`Preview loaded for ${dataType}.`);
    } catch (err) {
      setError(err.message);
    } finally {
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
      setPreview(payload.noise);
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
      setPreview({
        ...payload.result,
        sample: payload.result.sample,
      });
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
            output_file_name: cleaningOutputName,
          }
        );
      }

      if (mode === 'reset') {
        setCleaningSummary(null);
        setOperationMessage(
          payload.cleaning.discarded_measurements
            ? `Cleaning state reset for ${payload.cleaning.file_path}.`
            : 'Cleaning state was already empty.'
        );
      } else {
        setCleaningSummary(payload.cleaning);
        if (mode === 'save') {
          setOperationMessage(`Cleaned H5 saved to ${payload.cleaning.output_path}`);
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

  const handleCleaningFileSave = async (filePath) => {
    setError('');
    setSelectionMessage('');
    setIsBusy(true);

    try {
      const payload = await postTreatment(treatmentSessionId, '/api/treatment/cleaning/file/save', {
        file_path: filePath,
        angle_threshold: Number.parseFloat(cleaningAngleThreshold),
        surface_threshold: Number.parseFloat(cleaningSurfaceThreshold),
        output_file_name: cleaningOutputName,
      });
      setCleaningSummary(payload.cleaning);
      setOperationMessage(`Cleaned H5 saved to ${payload.cleaning.output_path}`);
      setActiveTab('cleaning');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

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
              <div style={{ marginBottom: '12px' }}>
                <label>
                  Data Root
                  <input
                    type="text"
                    value={draftAllowedRoot}
                    onChange={(event) => setDraftAllowedRoot(event.target.value)}
                    placeholder={treatment.allowed_root || 'E:/Data/DATA_VD2'}
                    style={{ width: '100%', marginTop: '4px' }}
                  />
                </label>
                <div style={{ marginTop: '8px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <button onClick={handleAllowedRootChange} disabled={isBusy || !draftAllowedRoot}>
                    Apply Data Root
                  </button>
                  <span>
                    <strong>Allowed Base:</strong> {treatment.treatment_root_base}
                  </span>
                </div>
                <div style={{ marginTop: '6px', color: '#475467', fontSize: '0.9rem' }}>
                  <strong>Cache:</strong> {treatment.cache_root} (
                  {Math.round((treatment.cache_limit_bytes || 0) / 1024 / 1024)} MB limit)
                </div>
              </div>
              <div className="folder-selection-header">
                <button onClick={() => setIsModalOpen(true)}>Select Folder</button>
                <button
                  onClick={() => refreshFolderListing(session.folder_path)}
                  style={{ marginLeft: '10px' }}
                >
                  Refresh
                </button>
                <button
                  onClick={handleAutoAssignFiles}
                  disabled={isBusy || !session.folder_path}
                  style={{ marginLeft: '10px' }}
                >
                  Auto Assign
                </button>
              </div>
              <p style={{ marginTop: '10px' }}>
                <strong>Current Folder:</strong>{' '}
                {session.folder_path || treatment.allowed_root}
              </p>
              {!treatment.allowed_root_exists && (
                <p>
                  <strong>Data Root:</strong> not found on this server.
                </p>
              )}
              <p>
                <strong>Status:</strong> {session.status_label}
              </p>
              <p>
                <strong>Required Inputs:</strong>{' '}
                {requiredDataTypes.length > 0 ? requiredDataTypes.join(', ') : 'n/a'}
              </p>
              {session.missing_data_types && session.missing_data_types.length > 0 && (
                <p>
                  <strong>Missing:</strong> {session.missing_data_types.join(', ')}
                </p>
              )}
              <p>
                <strong>Backend State:</strong>{' '}
                {isBusy
                  ? 'Working...'
                  : session.result_ready
                    ? 'Result ready'
                    : session.ready_for_calc
                      ? 'Ready to calculate'
                    : session.noise_ready
                      ? 'Noise ready'
                      : 'Idle'}
              </p>
              {operationMessage && <p>{operationMessage}</p>}
              {error && <p>{error}</p>}
              <div style={{ marginTop: '15px' }}>
                <h4>Subfolders</h4>
                {folderListing.folders.length === 0 && <p>No subfolders.</p>}
                {folderListing.folders.map((folder) => (
                  <div key={folder.path} style={{ marginBottom: '8px' }}>
                    <button onClick={() => handleFolderSelect(folder.path)}>
                      {folder.name}
                    </button>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: '15px' }}>
                <h4>Files</h4>
                {folderListing.files.length === 0 && <p>No files in this folder.</p>}
                {folderListing.files.map((file) => (
                  <div
                    key={file.path}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px',
                      marginBottom: '8px',
                    }}
                  >
                    <div>
                      <strong>{file.name}</strong> ({file.suffix || 'no suffix'})
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <button
                        onClick={() => handleAssignFile(file.path)}
                        disabled={!file.supported || isBusy}
                      >
                        Assign as {session.selected_data_type}
                      </button>
                      <button
                        onClick={() => handleCacheAssignFile(file.path)}
                        disabled={!file.supported || isBusy}
                      >
                        Cache & Assign
                      </button>
                      <button
                        onClick={() => handleCleaningFileSave(file.path)}
                        disabled={!isSamCleanableFile(file) || isBusy}
                      >
                        Clean File (SAM)
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="zone raw-data-kinetics">
              <h3>Assigned Inputs</h3>
              <AssignedPaths session={session} onPreview={handlePreview} />
              <div style={{ marginTop: '15px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button onClick={handleAverageNoise} disabled={isBusy}>
                  Average Noise
                </button>
                <button onClick={handleCalcAbs} disabled={isBusy}>
                  Calculate OD
                </button>
                <button onClick={handleSave} disabled={isBusy || !session.result_ready}>
                  Save Result
                </button>
              </div>
              <div style={{ marginTop: '20px' }}>
                <h3>Preview</h3>
                {preview && (
                  <div style={{ marginBottom: '12px' }}>
                    {preview.file_info && (
                      <p>
                        <strong>File:</strong> {preview.file_info.file_path}
                      </p>
                    )}
                    {(preview.data_shape || preview.shape) && (
                      <p>
                        <strong>Shape:</strong>{' '}
                        {(preview.data_shape || preview.shape).join(' x ')}
                      </p>
                    )}
                    {'mean' in preview && (
                      <p>
                        <strong>Mean:</strong> {preview.mean.toFixed(4)}
                      </p>
                    )}
                  </div>
                )}
                <RawDataKineticsPlot preview={preview} />
              </div>
            </div>
          </div>
        )}
        {activeTab === 'cleaning' && (
          <div className="tab-panel">
            <p>
              Run desktop-style SAM filtering on the active file. Each Analyze pass
              filters the current cleaned working set, and Reset returns you to the
              original file maps before the next pass.
            </p>
            <div style={{ display: 'grid', gap: '12px', maxWidth: '720px' }}>
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
                  onChange={(event) => setCleaningOutputName(event.target.value)}
                  placeholder="active_cleaned.h5"
                />
              </label>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button onClick={() => handleCleaningAction('analyze')} disabled={isBusy}>
                  Analyze SAM
                </button>
                <button onClick={() => handleCleaningAction('reset')} disabled={isBusy}>
                  Reset Cleaning
                </button>
                <button onClick={() => handleCleaningAction('save')} disabled={isBusy}>
                  Save Cleaned H5
                </button>
              </div>
              {cleaningSummary && (
                <div>
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
      {isModalOpen && (
        <AllowedFolderSelector
          sessionId={treatmentSessionId}
          initialFolder={session.folder_path || treatment.allowed_root}
          allowedRoot={treatment.allowed_root}
          onFolderSelect={handleFolderSelect}
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </div>
  );
};

export default TabsControl;
