// TopSection.js
import React, { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist';
import './css/TopSection.css';

// Imshow-like 2D heatmap component
const ImshowGraph = () => {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) {
      Plotly.newPlot(
        ref.current,
        [
          {
            z: [
              [1, 2, 3, 4],
              [5, 6, 7, 8],
              [9, 10, 11, 12],
              [13, 14, 15, 16]
            ],
            type: 'heatmap',
            colorscale: 'Viridis'
          }
        ],
        { margin: { t: 20 } }
      );
    }
  }, []);
  return <div className="imshow-graph" ref={ref}></div>;
};

// Kinetics XY plot component
const KineticsPlot = () => {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) {
      Plotly.newPlot(
        ref.current,
        [
          {
            x: [0, 1, 2, 3],
            y: [10, 15, 13, 17],
            type: 'scatter'
          }
        ],
        { margin: { t: 20 } }
      );
    }
  }, []);
  return <div className="xy-plot kinetics-plot" ref={ref}></div>;
};

// Spectrum XY plot component
const SpectrumPlot = () => {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) {
      Plotly.newPlot(
        ref.current,
        [
          {
            x: [0, 1, 2, 3],
            y: [5, 10, 8, 12],
            type: 'scatter'
          }
        ],
        { margin: { t: 20 } }
      );
    }
  }, []);
  return <div className="xy-plot spectrum-plot" ref={ref}></div>;
};

const TopSection = () => {
  return (
    <div className="top-section-container">
      <div
        style={{
          display: 'flex',
          gap: '12px',
          height: '100%',
          width: '100%',
        }}
      >
        <div className="left-column" style={{ flex: 3 }}>
          <div className="imshow-wrapper">
            <ImshowGraph />
          </div>
        </div>
        <div className="right-column" style={{ flex: 2 }}>
          <div className="vertical-layout">
            <KineticsPlot />
            <SpectrumPlot />
          </div>
        </div>
      </div>
    </div>
  );
};

export default TopSection;
