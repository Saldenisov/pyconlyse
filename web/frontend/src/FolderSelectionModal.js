// FolderSelectionModal.js
import React, { useState, useEffect } from 'react';
import './css/FolderSelectionModal.css';

// A recursive component for each tree item.
const FolderTreeItem = ({ node, onSelect }) => {
  const [expanded, setExpanded] = useState(false);
  const toggleExpand = () => setExpanded(!expanded);

  return (
    <li>
      {(node.type === 'folder' || node.type === 'parent') ? (
        <div className="folder-item">
          <span onClick={toggleExpand} className="expand-toggle" style={{cursor: 'pointer'}}>
            {expanded ? '▼' : '▶'}
          </span>
          <span onClick={() => onSelect(node)} className="folder-name" style={{cursor: 'pointer', marginLeft: '5px'}}>
            {node.name}
          </span>
        </div>
      ) : (
        <div className="file-item">
          <span>📄</span>
          <span style={{marginLeft: '5px'}}>{node.name}</span>
        </div>
      )}
      {expanded && node.children && node.children.length > 0 && (
        <ul className="folder-children">
          {node.children.map((child, index) => (
            <FolderTreeItem key={index} node={child} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
};

const FolderTree = ({ data, onSelect }) => {
  return (
    <ul className="folder-tree">
      {data.map((node, index) => (
        <FolderTreeItem key={index} node={node} onSelect={onSelect} />
      ))}
    </ul>
  );
};

const FolderSelectionModal = ({ isOpen, onClose, onFolderSelect, initialFolderData }) => {
  // In this simple example, we assume the initialFolderData is already in a tree structure.
  // In a real app you might need to call the backend to get children for each folder on demand.
  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Select Folder</h2>
        <FolderTree data={initialFolderData} onSelect={onFolderSelect} />
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
};

export default FolderSelectionModal;
