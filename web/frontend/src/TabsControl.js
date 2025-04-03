import React, { useState, useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist';
import './css/DataWindowVD2.css';

// ---------------------
// ParametersZone: Controls including the Save Folder text input.
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

// ---------------------
// RawDataKineticsPlot: XY graph using Plotly.
const RawDataKineticsPlot = () => {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) {
      Plotly.newPlot(
        ref.current,
        [
          {
            x: [0, 1, 2, 3],
            y: [3, 8, 5, 7],
            type: 'scatter',
          },
        ],
        { margin: { t: 20 }, width: 300, height: 300 }
      );
    }
  }, []);
  return <div className="raw-data-kinetics-plot" ref={ref}></div>;
};

// ---------------------
// TreeNode: Recursively renders a folder tree node (for folder contents).
const TreeNode = ({ node }) => {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;
  return (
    <div style={{ marginLeft: '20px' }}>
      <div
        onClick={() => hasChildren && setExpanded(!expanded)}
        style={{ cursor: hasChildren ? 'pointer' : 'default' }}
      >
        {node.isFile ? '📄 ' : '📁 '} {node.name}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child, index) => (
            <TreeNode key={index} node={child} />
          ))}
        </div>
      )}
    </div>
  );
};

// ---------------------
// ServerFolderTreeView: Fetches and displays the selected folder's content.
const ServerFolderTreeView = ({ folderPath }) => {
  const [tree, setTree] = useState(null);

  const fetchFolderContents = () => {
    fetch(`/api/folder-contents?folder=${encodeURIComponent(folderPath)}`)
      .then((response) => response.json())
      .then((data) => setTree(data))
      .catch((error) => console.error('Error fetching folder contents:', error));
  };

  useEffect(() => {
    if (folderPath) {
      fetchFolderContents();
    }
  }, [folderPath]);

  return (
    <div>
      <button onClick={fetchFolderContents}>Refresh Folder</button>
      {tree ? (
        <div className="folder-tree-view">
          <TreeNode node={tree} />
        </div>
      ) : (
        <p>No folder content available.</p>
      )}
    </div>
  );
};

// ---------------------
// ModalTreeNode: Renders a node in the allowed folder selector modal.
const ModalTreeNode = ({ node, selectedFolder, onFolderClick }) => {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;
  const handleClick = () => {
    if (hasChildren) setExpanded(!expanded);
    if (!node.isFile) onFolderClick(node);
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

// ---------------------
// AllowedFolderSelector: Modal for selecting an allowed folder from the server.
const AllowedFolderSelector = ({ onFolderSelect, onClose }) => {
  const [folderTree, setFolderTree] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState(null);

  useEffect(() => {
    fetch('/api/folder-structure')
      .then((response) => response.json())
      .then((data) => setFolderTree(data))
      .catch((error) =>
        console.error('Error fetching allowed folder structure:', error)
      );
  }, []);

  const handleFolderClick = (node) => {
    if (!node.isFile) {
      setSelectedFolder(node.path);
    }
  };

  const handleSelect = () => {
    onFolderSelect(selectedFolder);
  };

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
    zIndex: 1000,
  };

  const modalContentStyle = {
    backgroundColor: '#fff',
    padding: '20px',
    borderRadius: '4px',
    maxHeight: '80%',
    overflowY: 'auto',
  };

  return (
    <div style={modalOverlayStyle}>
      <div style={modalContentStyle}>
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
        <div style={{ marginTop: '10px' }}>
          <button onClick={handleSelect} disabled={!selectedFolder}>
            Select
          </button>
          <button onClick={onClose} style={{ marginLeft: '10px' }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------------------
// TabsControl: Main component with tabs, folder selection, and the XY graph.
const TabsControl = () => {
  const [activeTab, setActiveTab] = useState('files');
  const [folderPath, setFolderPath] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [saveFolder, setSaveFolder] = useState('');

  const openFolderModal = () => setIsModalOpen(true);

  // When a folder is selected from the modal, update folderPath and the Save Folder control.
  const handleFolderSelect = (selectedFolder) => {
    setFolderPath(selectedFolder);
    setSaveFolder(selectedFolder);
    setIsModalOpen(false);
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
            {/* Controls Zone */}
            <div className="zone parameters">
              <ParametersZone
                saveFolder={saveFolder}
                onSaveFolderChange={(e) => setSaveFolder(e.target.value)}
              />
            </div>
            {/* Folder Structure Zone */}
            <div className="zone files-folder">
              <div className="folder-selection-header">
                <button onClick={openFolderModal}>Select Folder</button>
                {folderPath && (
                  <span style={{ marginLeft: '10px' }}>
                    Selected Folder: {folderPath}
                  </span>
                )}
              </div>
              {folderPath && (
                <div style={{ marginTop: '20px' }}>
                  <ServerFolderTreeView folderPath={folderPath} />
                </div>
              )}
            </div>
            {/* XY Graph Zone */}
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
