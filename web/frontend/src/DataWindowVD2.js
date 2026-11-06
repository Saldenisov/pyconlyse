// DataWindowVD2.js (Main Component)
import React, { useCallback, useMemo, useState, createContext } from 'react';
import TopSection from './TopSection';
import TabsControl from './TabsControl';
import { getBrowserNamespace, namespaceToken } from './browserWorkspaceIdentity';
import './css/DataWindowVD2.css';
export { getBrowserNamespace } from './browserWorkspaceIdentity';

// Create context for sharing state between components
export const TreatmentContext = createContext();

const workspaceMemoryNamespace = namespaceToken();

export function buildTreatmentSessionId(profile, workspace = 'main', windowId = '') {
  const normalizedProfile = String(profile || 'VD2').trim().toLowerCase();
  const namespace = getBrowserNamespace();
  if (!namespace && workspace === 'main' && !windowId) return '';
  const base = `browser:${namespace || workspaceMemoryNamespace}${windowId?`:window:${windowId}`:''}:profile:${normalizedProfile}`;
  return workspace === 'main' ? base : `${base}:workspace:${workspace}`;
}

const DataWindowVD2 = ({ profile = 'VD2', layoutMode = 'studio', workspace = 'main', initialFolder = '', windowId = '', manifestProjectFolder='', onOpenManifest }) => {
  const treatmentProfile = String(profile || 'VD2').trim().toUpperCase();
  const treatmentSessionId = useMemo(
    () => buildTreatmentSessionId(treatmentProfile, workspace, windowId),
    [treatmentProfile, workspace, windowId]
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
    treatmentLayoutMode: layoutMode,
    initialFolder,
    manifestProjectFolder,
    onOpenManifest,
  };
  const treeFirst = layoutMode === 'studio' && treatmentProfile === 'VD2';
  const preview = (
    <section className="treatment-preview-workspace" aria-labelledby="treatment-preview-title">
      <div className="workspace-section-heading"><h2 id="treatment-preview-title">Preview</h2></div>
      <TopSection fillPanel={treeFirst} />
    </section>
  );

  return (
    <TreatmentContext.Provider value={contextValue}>
      <main className={`graph-window treatment-layout-${layoutMode}${treeFirst ? ' treatment-tree-workspace' : ''}`}>
        <section className="bottom-section" aria-label="Treatment inputs and processing">
          <TabsControl preview={treeFirst ? preview : null} />
        </section>
        {!treeFirst && preview}
      </main>
    </TreatmentContext.Provider>
  );
};

export default DataWindowVD2;
