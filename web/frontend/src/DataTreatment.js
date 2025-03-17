// web/frontend/src/tabs/DataTreatment.js
import React, { useState, useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist';
import './css/datatreatment.css';

const DataTreatment = () => {
  const [statusLabel, setStatusLabel] = useState("button is clicked");
  const [visualizationVisible, setVisualizationVisible] = useState(false);
  const plotRef = useRef(null);

  const buttonClicked = (buttonId) => {
    if (buttonId === 'V0') {
      setStatusLabel(`button ${buttonId} is clicked`);
      setVisualizationVisible(false);
    } else if (buttonId === 'VD2') {
      setStatusLabel('');
      setVisualizationVisible(true);
    }
  };

  // When visualization becomes visible, draw the 2D map.
  useEffect(() => {
    if (visualizationVisible && plotRef.current) {
      const data = [{
        z: [
          [1, 20, 30],
          [20, 1, 60],
          [30, 60, 1]
        ],
        type: 'heatmap'
      }];
      Plotly.newPlot(plotRef.current, data);
    }
  }, [visualizationVisible]);

  return (
    <div>
      <h1>You can treat the data here</h1>
      <div className="horizontal-container">
        <div className="block-1">
          <div className="column">
            <button id="button-v0" onClick={() => buttonClicked('V0')}>V0</button>
          </div>
          <div className="column">
            <button id="button-vd2" onClick={() => buttonClicked('VD2')}>VD2</button>
          </div>
        </div>
        <div className="block-2" id="block-2">
          <label id="status-label">{statusLabel}</label>
          <div id="visualization-container" style={{ display: visualizationVisible ? 'block' : 'none' }}>
            <div id="selectors">
              <label htmlFor="kinetics">Kinetics:</label>
              <select id="kinetics">
                <option value="option1">Option 1</option>
                <option value="option2">Option 2</option>
              </select>
              <label htmlFor="spectrum">Spectrum:</label>
              <select id="spectrum">
                <option value="option1">Option 1</option>
                <option value="option2">Option 2</option>
              </select>
            </div>
            <div id="map-2d" ref={plotRef}></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataTreatment;
