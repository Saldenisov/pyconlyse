// DataTreatment.js
import React, { useCallback, useEffect, useState } from 'react';
import DataWindowVD2, { buildTreatmentSessionId } from './DataWindowVD2';
import { namespaceToken, useWindowNamespace, workspaceHeaders } from './browserWorkspaceIdentity';
import { workspaceRequest } from './useVd2ServerWorkspace';
import ServerSessionPicker from './components/ServerSessionPicker';
import VD2ManifestTreatment from './components/VD2ManifestTreatment';
import { closeWorkspace, folderWorkspaceId, readWorkspaces, saveWorkspaces } from './treatmentWorkspaces';
import { cleanServerPath, serverPathParent } from './serverPaths';
import './css/datatreatment.css';

const DataTreatmentWindow = ({windowId}) => {
  const [incoming] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return { profile: params.get('profile') === 'V0' ? 'V0' : 'VD2', folder: cleanServerPath(params.get('folder')), manifest: cleanServerPath(params.get('manifest')), sample:params.get('sample')||'' };
  });
  const [activeProfile, setActiveProfile] = useState(() => {
    if (new URLSearchParams(window.location.search).has('folder') || new URLSearchParams(window.location.search).has('manifest')) return new URLSearchParams(window.location.search).get('profile') === 'V0' ? 'V0' : 'VD2';
    try {
      return window.localStorage.getItem(`pyconlyse.treatment.activeProfile.${windowId}`) === 'V0'
        ? 'V0' : 'VD2';
    } catch (_error) {
      return 'VD2';
    }
  });
  const [workspaces, setWorkspaces] = useState(() => {
    const state = { VD2: readWorkspaces('VD2',windowId), V0: readWorkspaces('V0',windowId) };
    if (incoming.folder) {
      const entry = state[incoming.profile];
      const id = folderWorkspaceId(incoming.folder);
      if (!entry.items.some(w => w.id === id)) entry.items.push({ id, label: incoming.folder.split(/[\\/]/).filter(Boolean).pop(), folder: incoming.folder });
      entry.active = id;
    }
    return state;
  });
  const workspace = workspaces[activeProfile];
  const activeWorkspace = workspace.items.find(w => w.id === workspace.active);
  const [manifestRequest, setManifestRequest] = useState(() => incoming.manifest ? { path: incoming.manifest } : null);
  const openManifest = useCallback(path => setManifestRequest({ path }), []);
  const removeWorkspace = () => {
    if (workspace.items.length <= 1) return;
    const url = new URL(window.location.href);
    ['folder', 'manifest', 'sample'].forEach(key => url.searchParams.delete(key));
    window.history.replaceState({}, '', url.pathname + url.search + url.hash);
    setManifestRequest(null);
    setWorkspaces(current => ({ ...current,
      [activeProfile]: closeWorkspace(current[activeProfile], current[activeProfile].active) }));
  };
  useEffect(() => {
    try {
      window.localStorage.setItem(`pyconlyse.treatment.activeProfile.${windowId}`, activeProfile);
    } catch (_error) {
      // The profile remains usable when localStorage is unavailable.
    }
  }, [activeProfile,windowId]);
  useEffect(() => {
    try {
      window.localStorage.setItem('pyconlyse.treatment.layoutMode', 'studio');
    } catch (_error) {
      // The layout is still usable when localStorage is unavailable.
    }
    saveWorkspaces('VD2', workspaces.VD2,windowId);
    saveWorkspaces('V0', workspaces.V0,windowId);
  }, [workspaces,windowId]);
  const selectWorkspace = id => setWorkspaces(current => ({ ...current,
    [activeProfile]: { ...current[activeProfile], active: id } }));
  const addWorkspace = () => {
    const id = `ws-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    setWorkspaces(current => ({ ...current, [activeProfile]: { active: id,
      items: [...current[activeProfile].items, { id, label: `Workspace ${current[activeProfile].items.length + 1}` }] } }));
  };
  const savedSessions=async()=>{
    const headers={...workspaceHeaders(windowId),'X-Treatment-Session-Id':buildTreatmentSessionId(activeProfile,workspace.active,windowId)};
    const payload=await workspaceRequest('/api/treatment/session/saved',{headers});
    return payload.sessions.map(item=>({...item,id:item.session_id}));
  };
  const restoreSession=async item=>{
    const id=`restored-${namespaceToken()}`;
    await workspaceRequest('/api/treatment/session/copy',{method:'POST',
      headers:{...workspaceHeaders(windowId),'X-Treatment-Session-Id':buildTreatmentSessionId(activeProfile,id,windowId),'Content-Type':'application/json'},
      body:JSON.stringify({source_session_id:item.session_id})});
    setWorkspaces(current=>({...current,[activeProfile]:{active:id,
      items:[...current[activeProfile].items,{id,label:`Restored ${item.name.split(/[\\/]/).pop()}`}]
    }}));
  };
  const manifestLoaded=useCallback(plan=>{
    const manifest=cleanServerPath(plan.manifest_path),folder=plan.project_folder||serverPathParent(manifest);
    if(!folder)return;
    const id=`manifest-${folderWorkspaceId(folder)}`;
    setWorkspaces(current=>{
      const state=current.VD2,previous=state.items.find(item=>item.id===id);
      if(state.active===id&&previous?.manifest===manifest&&previous.folder===folder)return current;
      const item={id,label:folder.split(/[\\/]/).filter(Boolean).pop(),folder,manifest};
      return {...current,VD2:{active:id,items:previous?state.items.map(entry=>entry.id===id?item:entry):[...state.items,item]}};
    });
  },[]);

  return (
    <div className="data-treatment-container layout-mode-studio">
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
        <div className="treatment-workspace-switch">
          <label>Workspace <select value={workspace.active} onChange={e => selectWorkspace(e.target.value)}>
            {workspace.items.map(w => <option key={w.id} value={w.id}>{w.label}</option>)}
          </select></label>
          <button type="button" onClick={addWorkspace} aria-label="New workspace">+</button>
          <button type="button" onClick={removeWorkspace} aria-label="Close workspace"
            title="Close this workspace; saved files and server sessions remain available in Restore."
            disabled={workspace.items.length <= 1}>×</button>
          <ServerSessionPicker load={savedSessions} onRestore={restoreSession} />
        </div>
      </header>
      {activeProfile === 'VD2' && manifestRequest && <VD2ManifestTreatment initialManifest={manifestRequest.path} initialSample={incoming.sample} onLoaded={manifestLoaded}
        dialog onClose={() => setManifestRequest(null)}
        sessionId={buildTreatmentSessionId('VD2','manifest-queue',windowId)} />}
      <DataWindowVD2 profile={activeProfile} layoutMode="studio" workspace={workspace.active}
        onOpenManifest={openManifest}
        manifestProjectFolder={activeWorkspace?.manifest?activeWorkspace.folder:''}
        windowId={windowId} initialFolder={activeWorkspace?.folder || ''} key={`${activeProfile}:${workspace.active}`} />
    </div>
  );
};

const DataTreatment=()=>{
  const windowId=useWindowNamespace();
  return windowId?<DataTreatmentWindow windowId={windowId} />:<p role="status">Opening this window’s workspace…</p>;
};

export default DataTreatment;
