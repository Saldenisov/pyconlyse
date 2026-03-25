// DataTreatment.js
import React, { useState } from 'react';
import DataWindowVD2 from './DataWindowVD2'; // Adjust the path if necessary
import './css/datatreatment.css';

const DataTreatment = () => {
  const [activeProfile, setActiveProfile] = useState('VD2');
  const statusLabel =
    activeProfile === 'V0'
      ? 'V0 web treatment is active.'
      : 'VD2 web treatment is active.';

  return (
    <div className="data-treatment-container">
      <h1>Data Treatment</h1>
      <div className="button-container">
        <button id="button-v0" onClick={() => setActiveProfile('V0')}>V0</button>
        <button id="button-vd2" onClick={() => setActiveProfile('VD2')}>VD2</button>
      </div>
      <div className="status-label">
        <label>{statusLabel}</label>
      </div>
      <DataWindowVD2 profile={activeProfile} key={activeProfile} />
    </div>
  );
};

export default DataTreatment;
