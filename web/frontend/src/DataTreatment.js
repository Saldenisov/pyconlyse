// DataTreatment.js
import React, { useState } from 'react';
import DataWindowVD2 from './DataWindowVD2'; // Adjust the path if necessary
import './css/datatreatment.css';

const DataTreatment = () => {
  // State to toggle between basic view and full VD2 treatment view.
  const [showVD2Window, setShowVD2Window] = useState(false);
  const [statusLabel, setStatusLabel] = useState("");

  const buttonClicked = (buttonId) => {
    if (buttonId === 'V0') {
      setStatusLabel(`Button ${buttonId} is clicked.`);
      setShowVD2Window(false);
    } else if (buttonId === 'VD2') {
      setStatusLabel("Switching to full VD2 treatment view...");
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
          {/* Basic view or placeholder content */}
          <p>Basic data treatment view. Click VD2 to load full VD2 treatment.</p>
        </div>
      )}
    </div>
  );
};

export default DataTreatment;
