// DataWindowVD2.js (Main Component)
import React, { useCallback, useMemo, useState, createContext } from 'react';
import TopSection from './TopSection';
import TabsControl from './TabsControl';
import './css/DataWindowVD2.css';

// Create context for sharing state between components
export const TreatmentContext = createContext();

const TREATMENT_NAMESPACE_KEY = 'pyconlyse_treatment_namespace';
let inMemoryNamespace = '';

function createNamespaceToken() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function getBrowserNamespace() {
  try {
    const stored = window.localStorage.getItem(TREATMENT_NAMESPACE_KEY);
    if (stored) {
      return stored;
    }

    const created = createNamespaceToken();
    window.localStorage.setItem(TREATMENT_NAMESPACE_KEY, created);
    return created;
  } catch (_error) {
    if (!inMemoryNamespace) {
      inMemoryNamespace = createNamespaceToken();
    }
    return inMemoryNamespace;
  }
}

function buildTreatmentSessionId(profile) {
  const normalizedProfile = String(profile || 'VD2').trim().toLowerCase();
  return `browser:${getBrowserNamespace()}:profile:${normalizedProfile}`;
}

const DataWindowVD2 = ({ profile = 'VD2' }) => {
  const treatmentProfile = String(profile || 'VD2').trim().toUpperCase();
  const treatmentSessionId = useMemo(
    () => buildTreatmentSessionId(treatmentProfile),
    [treatmentProfile]
  );

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
  const [selectionRefreshToken, setSelectionRefreshToken] = useState(0);

  const requestSelectionRefresh = useCallback(() => {
    setSelectionRefreshToken((current) => current + 1);
  }, []);
  
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
    expType, setExpType,
    selectionRefreshToken,
    requestSelectionRefresh,
    treatmentProfile,
    treatmentSessionId,
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
