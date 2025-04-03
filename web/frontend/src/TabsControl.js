import React, { useState, useEffect } from 'react';
import Plotly from 'plotly.js-dist';
import './css/DataWindowVD2.css';

// --- Modal tree view components for selecting allowed folders from the server ---

const ModalTreeNode = ({ node, selectedFolder, onFolderClick }) => {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;

  const handleClick = () => {
    if (hasChildren) setExpanded(!expanded);
    // Only allow folder selection (node.isFile should be false)
    if (!node.isFile) onFolderClick(node);
  };

  return (
    <div style={{ marginLeft: '20px' }}>
      <div
        onClick={handleClick}
        style={{
          cursor: 'pointer',
          fontWeight: selectedFolder === node.path ? 'bold' : 'normal'
        }}
      >
        {'📁 '} {node.name}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child, index) => (
            <ModalTreeNode
              key={index}
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

function AllowedFolderSelector({ onFolderSelect, onClose }) {
  const [folderTree, setFolderTree] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState(null);

  useEffect(() => {
    // Fetch the allowed folder structure from the server.
    fetch('/api/folder-structure')
      .then((response) => response.json())
      .then((data) => {
        setFolderTree(data);
      })
      .catch((error) => console.error('Error fetching folder structure:', error));
  }, []);

  const handleFolderClick = (node) => {
    if (!node.isFile) {
      setSelectedFolder(node.path);
    }
  };

  const handleSelect = () => {
    onFolderSelect(selectedFolder);
  };

  // Inline styles for modal overlay
  const modalOverlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  };

  const modalContentStyle = {
    backgroundColor: '#fff',
    padding: '20px',
    borderRadius: '4px',
    maxHeight: '80%',
    overflowY: 'auto'
  };

  return (
    <div className="folder-selector-modal" style={modalOverlayStyle}>
      <div className="modal-content" style={modalContentStyle}>
        <h3>Select a Folder</h3>
        {folderTree ? (
          <div className="folder-tree-view">
            <ModalTreeNode
              node={folderTree}
              selectedFolder={selectedFolder}
              onFolderClick={handleFolderClick}
            />
          </div>
        ) : (
          <p>Loading folders...</p>
        )}
        <div className="modal-actions">
          <button onClick={handleSelect} disabled={!selectedFolder}>
            Select
          </button>
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// --- Other UI components ---

const ParametersZone = ({ saveFolder, onSaveFolderChange }) => {
  return (
    <div className="parameters-zone">
      <h3>Parameters</h3>
      <div>
        <label>Exp Type:</label>
        <select>
          <option value="ABS">ABS</option>
          <option value="BASE">BASE</option>
          <option value="NOISE">NOISE</option>
          <option value="ABS_BASE">ABS+BASE</option>
          <option value="ABS_BASE_NOISE">ABS+BASE+NOISE</option>
        </select>
      </div>
      <div>
        <label>Data:</label>
        <input type="text" placeholder="Data" />
      </div>
      <div>
        <label>Noise:</label>
        <input type="text" placeholder="Noise" />
      </div>
      <div>
        <label>Save Folder:</label>
        <input
          type="text"
          value={saveFolder}
          onChange={onSaveFolderChange}
          placeholder="/path/to/data"
        />
      </div>
      <div>
        <label>Save File Name:</label>
        <input type="text" placeholder="filename" />
      </div>
    </div>
  );
};

const FilesFolderStructureZone = ({ saveFolder, onOpenFolderSelector }) => {
  return (
    <div className="files-folder-zone">
      <h3>Files Folder Structure</h3>
      <button onClick={onOpenFolderSelector}>Select Folder</button>
      {saveFolder ? <p>Selected Folder: {saveFolder}</p> : <p>No folder selected.</p>}
    </div>
  );
};

const RawDataKineticsPlot = () => {
  const ref = React.useRef(null);
  useEffect(() => {
    if (ref.current) {
      Plotly.newPlot(
        ref.current,
        [
          {
            x: [0, 1, 2, 3],
            y: [3, 8, 5, 7],
            type: 'scatter'
          }
        ],
        { margin: { t: 20 }, width: 300, height: 300 }
      );
    }
  }, []);
  return <div className="raw-data-kinetics-plot" ref={ref}></div>;
};

const TabsControl = () => {
  const [activeTab, setActiveTab] = useState('files');
  const [saveFolder, setSaveFolder] = useState('');
  const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false);

  const handleOpenFolderSelector = () => {
    setIsFolderSelectorOpen(true);
  };

  const handleFolderSelect = (folderPath) => {
    setSaveFolder(folderPath);
    setIsFolderSelectorOpen(false);
  };

  return (
    <div className="tabs-control">
      <div className="tabs">
        <button onClick={() => setActiveTab('files')}>Files</button>
        <button onClick={() => setActiveTab('cleaning')}>Cleaning</button>
        <button onClick={() => setActiveTab('info')}>Info</button>
        <button onClick={() => setActiveTab('selection')}>Selection Tab</button>
      </div>
      <div className="tab-content">
        {activeTab === 'files' && (
          <div className="files-tab horizontal-layout">
            <div className="zone parameters">
              <ParametersZone
                saveFolder={saveFolder}
                onSaveFolderChange={(e) => setSaveFolder(e.target.value)}
              />
            </div>
            <div className="zone files-folder">
              <FilesFolderStructureZone
                saveFolder={saveFolder}
                onOpenFolderSelector={handleOpenFolderSelector}
              />
            </div>
            <div className="zone raw-data-kinetics">
              <h3>Raw Data Kinetics</h3>
              <RawDataKineticsPlot />
            </div>
          </div>
        )}
        {activeTab === 'cleaning' && (
          <div className="tab-panel">Cleaning content here</div>
        )}
        {activeTab === 'info' && (
          <div className="tab-panel">Info content here</div>
        )}
        {activeTab === 'selection' && (
          <div className="tab-panel">Selection content here</div>
        )}
      </div>
      {isFolderSelectorOpen && (
        <AllowedFolderSelector
          onFolderSelect={handleFolderSelect}
          onClose={() => setIsFolderSelectorOpen(false)}
        />
      )}
    </div>
  );
};

export default TabsControl;
