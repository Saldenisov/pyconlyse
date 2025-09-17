// TopSection.js
import React, { useEffect, useRef } from 'react';
import SplitPane from 'react-split-pane';
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

// TopSection component using SplitPane for resizable columns
const TopSection = () => {
  return (
    <div className="top-section-container">
      <SplitPane
        split="vertical"
        defaultSize="60%"
        minSize={200} /* minimum pane size in pixels */
        resizerStyle={{ cursor: 'col-resize', background: '#ccc', width: '5px' }}
        style={{ height: '100%' }} /* ensure SplitPane fills the container */
      >
        <div className="left-column">
          {/* The imshow graph is wrapped so that its size is constrained */}
          <div className="imshow-wrapper">
            <ImshowGraph />
          </div>
        </div>
        <div className="right-column">
          <div className="vertical-layout">
            <KineticsPlot />
            <SpectrumPlot />
          </div>
        </div>
      </SplitPane>
    </div>
  );
};

export default TopSection;
