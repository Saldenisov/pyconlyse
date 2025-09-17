// DataWindowVD2.js (Main Component)
import React from 'react';
import TopSection from './TopSection'; // if you split it out; or inline if you prefer
import TabsControl from './TabsControl'; // assuming TabsControl is defined as before
import './css/DataWindowVD2.css';

const DataWindowVD2 = () => {
  return (
    <div className="graph-window">
      <TopSection />
      <div className="bottom-section">
        <TabsControl />
      </div>
    </div>
  );
};

export default DataWindowVD2;
