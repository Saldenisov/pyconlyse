// DataTreatment.js
import React, { useState } from 'react';
import DataWindowVD2 from './DataWindowVD2'; // Adjust the path if necessary
import './css/datatreatment.css';

const DataTreatment = () => {
  const [showVD2Window, setShowVD2Window] = useState(true);
  const [statusLabel, setStatusLabel] = useState("VD2 web treatment is active.");

  const buttonClicked = (buttonId) => {
    if (buttonId === 'V0') {
      setStatusLabel('Basic treatment placeholder is selected.');
      setShowVD2Window(false);
    } else if (buttonId === 'VD2') {
      setStatusLabel("VD2 web treatment is active.");
      setShowVD2Window(true);
    }
  };

  return (
    <div className="data-treatment-container">
      <h1>Data Treatment</h1>
      <div className="button-container">
        <button id="button-v0" onClick={() => buttonClicked('V0')}>V0</button>
        <button id="button-vd2" onClick={() => buttonClicked('VD2')}>VD2</button>
      </div>
      <div className="status-label">
        <label>{statusLabel}</label>
      </div>
      {showVD2Window ? (
        <DataWindowVD2 />
      ) : (
        <div>
          <p>Basic data treatment placeholder. Use VD2 for the active workflow.</p>
        </div>
      )}
    </div>
  );
};

export default DataTreatment;
