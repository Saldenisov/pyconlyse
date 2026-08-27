// DataTreatment.js
import React, { useEffect, useState } from 'react';
import DataWindowVD2 from './DataWindowVD2'; // Adjust the path if necessary
import './css/datatreatment.css';

const DataTreatment = () => {
  const [activeProfile, setActiveProfile] = useState('VD2');
  const [layoutMode, setLayoutMode] = useState(() => {
    try {
      return window.localStorage.getItem('pyconlyse.treatment.layoutMode') === 'studio'
        ? 'studio'
        : 'classic';
    } catch (_error) {
      return 'classic';
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem('pyconlyse.treatment.layoutMode', layoutMode);
    } catch (_error) {
      // The layout is still usable when localStorage is unavailable.
    }
  }, [layoutMode]);

  return (
    <div className={`data-treatment-container layout-mode-${layoutMode}`}>
      <header className="data-treatment-header">
        <div>
          <h1>Data Treatment</h1>
        </div>
        <div className="treatment-profile-switch" role="group" aria-label="Treatment profile">
          <button
            id="button-vd2"
            className={activeProfile === 'VD2' ? 'is-active' : ''}
            aria-pressed={activeProfile === 'VD2'}
            onClick={() => setActiveProfile('VD2')}
          >
            VD2
          </button>
          <button
            id="button-v0"
            className={activeProfile === 'V0' ? 'is-active' : ''}
            aria-pressed={activeProfile === 'V0'}
            onClick={() => setActiveProfile('V0')}
          >
            V0 legacy
          </button>
        </div>
        <div className="treatment-layout-switch" role="group" aria-label="Treatment layout">
          <span>Layout</span>
          <button
            className={layoutMode === 'classic' ? 'is-active' : ''}
            aria-pressed={layoutMode === 'classic'}
            onClick={() => setLayoutMode('classic')}
          >
            Classic
          </button>
          <button
            className={layoutMode === 'studio' ? 'is-active' : ''}
            aria-pressed={layoutMode === 'studio'}
            onClick={() => setLayoutMode('studio')}
          >
            Studio
          </button>
        </div>
      </header>
      <DataWindowVD2 profile={activeProfile} layoutMode={layoutMode} key={activeProfile} />
    </div>
  );
};

export default DataTreatment;
