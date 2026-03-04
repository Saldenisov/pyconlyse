import React, { useEffect, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import './css/DataWindowVD2.css';

async function parseResponse(response) {
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || 'Treatment request failed.');
  }
  return payload;
}

async function fetchTreatmentSession() {
  const response = await fetch('/api/treatment/session');
  return parseResponse(response);
}

async function postTreatment(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  return parseResponse(response);
}

async function fetchFolderListing(folderPath) {
  const response = await fetch(
    `/api/treatment/files?folder=${encodeURIComponent(folderPath)}`
  );
  return parseResponse(response);
}

async function fetchTreatmentPreview(dataType) {
  const response = await fetch(
    `/api/treatment/preview?data_type=${encodeURIComponent(dataType)}&map_index=0`
  );
  return parseResponse(response);
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
}) => {
  return (
    <div className="parameters-zone">
      <h3>Treatment Session</h3>
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
          onChange={(event) => onConfigChange({ calc_mode: event.target.value })}
        >
          {calcModes.map((item) => (
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

const ModalTreeNode = ({ node, selectedFolder, onFolderClick }) => {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;

  const handleClick = () => {
    if (hasChildren) {
      setExpanded((current) => !current);
    }
    if (!node.isFile) {
      onFolderClick(node.path);
    }
  };

  return (
    <div style={{ marginLeft: '20px' }}>
      <div
        onClick={handleClick}
        style={{
          cursor: 'pointer',
          fontWeight: selectedFolder === node.path ? 'bold' : 'normal',
        }}
      >
        {node.name}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child, index) => (
            <ModalTreeNode
              key={`${child.path}-${index}`}
              node={child}
              selectedFolder={selectedFolder}
              onFolderClick={onFolderClick}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const AllowedFolderSelector = ({ onFolderSelect, onClose }) => {
  const [folderTree, setFolderTree] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    fetch('/api/folder-structure')
      .then(parseResponse)
      .then((data) => {
        if (!cancelled) {
          setFolderTree(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

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
        {error && <p>{error}</p>}
        {!error && !folderTree && <p>Loading folders...</p>}
        {folderTree && (
          <div className="folder-tree-view">
            <ModalTreeNode
              node={folderTree}
              selectedFolder={selectedFolder}
              onFolderClick={setSelectedFolder}
            />
          </div>
        )}
        <div style={{ marginTop: '10px' }}>
          <button
            onClick={() => onFolderSelect(selectedFolder)}
            disabled={!selectedFolder}
          >
            Use Folder
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
  const [activeTab, setActiveTab] = useState('files');
  const [treatment, setTreatment] = useState(null);
  const [folderListing, setFolderListing] = useState({ folders: [], files: [] });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [draftSaveFolder, setDraftSaveFolder] = useState('');
  const [draftSaveFileName, setDraftSaveFileName] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);
  const [operationMessage, setOperationMessage] = useState('');
  const [isBusy, setIsBusy] = useState(false);

  const session = treatment ? treatment.session : null;

  const refreshSession = async () => {
    const payload = await fetchTreatmentSession();
    setTreatment(payload);
    return payload;
  };

  const refreshFolderListing = async (folderPath) => {
    if (!folderPath) {
      setFolderListing({ folders: [], files: [] });
      return;
    }

    const payload = await fetchFolderListing(folderPath);
    setFolderListing({
      folders: payload.folders || [],
      files: payload.files || [],
    });
  };

  useEffect(() => {
    let cancelled = false;

    refreshSession()
      .then((payload) => {
        if (!cancelled && payload.session.folder_path) {
          return refreshFolderListing(payload.session.folder_path);
        }
        return undefined;
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }
    setDraftSaveFolder(session.save_folder || '');
    setDraftSaveFileName(session.save_file_name || '');
  }, [session]);

  const applyPayload = async (requestPromise, refreshListing = false) => {
    setError('');
    setIsBusy(true);
    try {
      const payload = await requestPromise;
      setTreatment(payload);
      if (refreshListing && payload.session.folder_path) {
        await refreshFolderListing(payload.session.folder_path);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const handleConfigChange = (patch) =>
    applyPayload(postTreatment('/api/treatment/session/config', patch));

  const handleReset = () =>
    applyPayload(postTreatment('/api/treatment/session/reset'), true);

  const handleFolderSelect = (selectedFolder) => {
    if (!selectedFolder) {
      return;
    }
    setIsModalOpen(false);
    applyPayload(
      postTreatment('/api/treatment/session/folder', {
        folder_path: selectedFolder,
      }),
      true
    );
  };

  const handleAssignFile = (filePath) => {
    if (!session) {
      return;
    }
    applyPayload(
      postTreatment('/api/treatment/session/path', {
        data_type: session.selected_data_type,
        file_path: filePath,
      })
    );
  };

  const handlePreview = async (dataType) => {
    setError('');
    setIsBusy(true);
    try {
      const payload = await fetchTreatmentPreview(dataType);
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
      const payload = await postTreatment('/api/treatment/average-noise');
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
      const payload = await postTreatment('/api/treatment/calc-abs');
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
      const payload = await postTreatment('/api/treatment/save');
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

  if (!session) {
    return <div className="tabs-control">Loading treatment session...</div>;
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
                dataTypes={treatment.data_types}
                calcModes={treatment.calc_modes}
                draftSaveFolder={draftSaveFolder}
                draftSaveFileName={draftSaveFileName}
                onConfigChange={handleConfigChange}
                onDraftSaveFolderChange={setDraftSaveFolder}
                onDraftSaveFileNameChange={setDraftSaveFileName}
                onCommitSaveFolder={handleCommitSaveFolder}
                onCommitSaveFileName={handleCommitSaveFileName}
                onReset={handleReset}
              />
            </div>
            <div className="zone files-folder">
              <div className="folder-selection-header">
                <button onClick={() => setIsModalOpen(true)}>Select Folder</button>
                <button
                  onClick={() => refreshFolderListing(session.folder_path)}
                  style={{ marginLeft: '10px' }}
                >
                  Refresh
                </button>
              </div>
              <p style={{ marginTop: '10px' }}>
                <strong>Current Folder:</strong>{' '}
                {session.folder_path || treatment.allowed_root}
              </p>
              <p>
                <strong>Status:</strong> {session.status_label}
              </p>
              <p>
                <strong>Backend State:</strong>{' '}
                {isBusy
                  ? 'Working...'
                  : session.result_ready
                    ? 'Result ready'
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
                    <button
                      onClick={() => handleAssignFile(file.path)}
                      disabled={!file.supported}
                    >
                      Assign as {session.selected_data_type}
                    </button>
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
            Cleaning workflow is next. The session state is now persisted on the
            backend, so this tab can call real treatment operations next.
          </div>
        )}
        {activeTab === 'info' && (
          <div className="tab-panel">
            <p>
              <strong>Allowed Root:</strong> {treatment.allowed_root}
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
            Selection tools from the desktop Treatment client are not ported yet,
            but file-role assignment and session persistence now run through the
            web backend.
          </div>
        )}
      </div>
      {isModalOpen && (
        <AllowedFolderSelector
          onFolderSelect={handleFolderSelect}
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </div>
  );
};

export default TabsControl;
