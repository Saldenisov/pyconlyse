import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchWithCsrfToken } from './api/csrfRequest';
import { useWindowNamespace, workspaceHeaders } from './browserWorkspaceIdentity';

export async function workspaceRequest(url,options={}) {
  const controller=new AbortController();const timer=window.setTimeout(()=>controller.abort(),10000);
  try {
    const response=await fetchWithCsrfToken(url,{...options,signal:controller.signal});
    let payload;
    try{payload=await response.json();}catch(_error){throw new Error('Server session API unavailable. Web reload may be required.');}
    if(!response.ok||payload.success!==true)throw new Error(payload.error||`Server session unavailable (HTTP ${response.status}).`);
    return payload;
  } catch(error) {if(error.name==='AbortError')throw new Error('Server session request timed out.');throw error;}
  finally{window.clearTimeout(timer);}
}

export default function useVd2ServerWorkspace(settings,setSettings) {
  const windowId=useWindowNamespace();
  const [ready,setReady]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const revision=useRef(0),lastSaved=useRef(''),latest=useRef(settings),alive=useRef(true),saving=useRef(false),blocked=useRef(false),hydrated=useRef(false),flush=useRef(null);
  latest.current=settings;
  useEffect(()=>{
    alive.current=true;
    const saveOnExit=()=>flush.current?.();
    window.addEventListener('pagehide',saveOnExit);
    return()=>{alive.current=false;window.removeEventListener('pagehide',saveOnExit);saveOnExit();};
  },[]);
  useEffect(()=>{
    if(!windowId)return undefined;
    let active=true;
    (async()=>{
      try{
        const payload=await workspaceRequest('/api/pump-probe-vd2/workspace',{headers:workspaceHeaders(windowId)});
        if(!active)return;
        const saved=payload.workspace;
        revision.current=saved?.revision||0;
        const initial=saved?.settings||latest.current;
        lastSaved.current=JSON.stringify(initial);
        if(saved){setSettings(initial);setMessage('Session restored from server.');}
        blocked.current=false;setError('');
      }catch(cause){if(active){blocked.current=true;setError(`Session recovery: ${cause.message}`);}}
      finally{if(active){hydrated.current=true;setReady(true);}}
    })();
    return()=>{active=false;};
  },[windowId,setSettings]);

  const save=useCallback(async()=>{
    if(!hydrated.current||!windowId||saving.current||blocked.current)return;
    saving.current=true;
    try{
      while(lastSaved.current!==JSON.stringify(latest.current)){
        const snapshot=latest.current,encoded=JSON.stringify(snapshot);
        const payload=await workspaceRequest('/api/pump-probe-vd2/workspace',{method:'POST',keepalive:true,headers:{...workspaceHeaders(windowId),'Content-Type':'application/json'},
          body:JSON.stringify({settings:snapshot,revision:revision.current})});
        revision.current=payload.workspace.revision;lastSaved.current=encoded;
        if(alive.current){setMessage('Session saved on server.');setError('');}
      }
    }catch(cause){blocked.current=true;if(alive.current)setError(`Session was not saved: ${cause.message}`);}
    finally{saving.current=false;}
  },[windowId]);
  flush.current=save;
  useEffect(()=>{
    if(!ready||lastSaved.current===JSON.stringify(settings))return undefined;
    const timer=window.setTimeout(save,500);
    return()=>window.clearTimeout(timer);
  },[ready,settings,save]);

  const history=useCallback(async()=>{
    const payload=await workspaceRequest('/api/pump-probe-vd2/workspace/history',{headers:workspaceHeaders(windowId)});
    return payload.workspaces.map(item=>({id:item.window_id,name:item.settings.runName||'Untitled sample',folder:item.settings.outputRoot,updated_at:item.updated_at,settings:item.settings}));
  },[windowId]);
  const restore=useCallback(async item=>{
    if(saving.current)throw new Error('Wait until this window finishes saving.');
    // Re-read this window to obtain its current revision after a conflict.
    const payload=await workspaceRequest('/api/pump-probe-vd2/workspace',{headers:workspaceHeaders(windowId)});
    revision.current=payload.workspace?.revision||0;blocked.current=false;
    setSettings({...item.settings});setMessage('Restored form settings; camera settings unchanged.');setError('');
  },[windowId,setSettings]);
  return {ready,message,error,history,restore,windowId};
}
