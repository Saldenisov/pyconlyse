// DataWindowVD2.js (Main Component)
import React, { useState, createContext } from 'react';
import TopSection from './TopSection';
import TabsControl from './TabsControl';
import './css/DataWindowVD2.css';

// Create context for sharing state between components
export const TreatmentContext = createContext();

const DataWindowVD2 = () => {
  // State for file paths
  const [absPath, setAbsPath] = useState(null);
  const [basePath, setBasePath] = useState(null);
  const [noisePath, setNoisePath] = useState(null);
  const [absBasePath, setAbsBasePath] = useState(null);
  
  // State for current data
  const [currentData, setCurrentData] = useState(null);
  const [wavelengths, setWavelengths] = useState([]);
  const [timedelays, setTimedelays] = useState([]);
  const [mapIndex, setMapIndex] = useState(0);
  const [numberMaps, setNumberMaps] = useState(0);
  
  // State for calculated OD
  const [odData, setOdData] = useState(null);
  
  // State for cursor positions
  const [cursorX, setCursorX] = useState(null);
  const [cursorY, setCursorY] = useState(null);
  
  // State for experiment type
  const [expType, setExpType] = useState('ABS+BASE+BRUIT');
  
  const contextValue = {
    absPath, setAbsPath,
    basePath, setBasePath,
    noisePath, setNoisePath,
    absBasePath, setAbsBasePath,
    currentData, setCurrentData,
    wavelengths, setWavelengths,
    timedelays, setTimedelays,
    mapIndex, setMapIndex,
    numberMaps, setNumberMaps,
    odData, setOdData,
    cursorX, setCursorX,
    cursorY, setCursorY,
    expType, setExpType
  };
  
  return (
    <TreatmentContext.Provider value={contextValue}>
      <div className="graph-window">
        <TopSection />
        <div className="bottom-section">
          <TabsControl />
        </div>
      </div>
    </TreatmentContext.Provider>
  );
};

export default DataWindowVD2;
