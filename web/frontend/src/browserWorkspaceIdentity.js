import { useEffect, useState } from 'react';

const BROWSER_KEY='pyconlyse_treatment_namespace';
const COOKIE='pyconlyse_treatment_browser_namespace';
const WINDOW_KEY='pyconlyse.workspace.window.v1';
export const namespaceToken=()=>typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
const valid=value=>typeof value==='string'&&/^[A-Za-z0-9-]{10,100}$/.test(value);

export function getBrowserNamespace() {
  let cookie='';
  try {const part=document.cookie.split('; ').find(item=>item.startsWith(`${COOKIE}=`));cookie=part?decodeURIComponent(part.slice(COOKIE.length+1)):'';} catch (_error) { /* Storage may be blocked. */ }
  let value=valid(cookie)?cookie:'';
  try {const stored=window.localStorage.getItem(BROWSER_KEY);value=valid(stored)?stored:value||namespaceToken();window.localStorage.setItem(BROWSER_KEY,value);} catch (_error) { /* Preserve existing cookie fallback. */ }
  if(value)try {document.cookie=`${COOKIE}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax`;} catch (_error) { /* In-memory UI still works. */ }
  return value;
}

export function windowNamespace(storage) {
  try {const target=storage||window.sessionStorage;const previous=target.getItem(WINDOW_KEY);if(valid(previous))return previous;
    const created=namespaceToken();target.setItem(WINDOW_KEY,created);return created;
  } catch (_error) {return namespaceToken();}
}

// A duplicated tab can inherit sessionStorage. Ask existing windows before
// mounting an editable session so both tabs cannot silently share its writes.
export function claimWindowNamespace(storage, Channel=window.BroadcastChannel) {
  let id=windowNamespace(storage);
  if(!Channel)return Promise.resolve(id);
  return new Promise(resolve=>{
    let channel;
    try {channel=new Channel('pyconlyse.workspace.presence.v1');} catch (_error) {resolve(id);return;}
    const claim=namespaceToken();let ready=false;
    channel.onmessage=event=>{
      const message=event.data;
      if(message?.window!==id||message.claim===claim)return;
      if(message.type==='probe'&&(ready||claim<message.claim))channel.postMessage({type:'occupied',window:id,claim});
      if(message.type==='occupied'&&!ready){id=namespaceToken();try{(storage||window.sessionStorage).setItem(WINDOW_KEY,id);}catch(_error){/* Keep unique in-memory identity. */}}
    };
    channel.postMessage({type:'probe',window:id,claim});
    window.setTimeout(()=>{ready=true;resolve(id);},80);
    // Keep the claim alive for this document, including navigation inside React.
    window.addEventListener('pagehide',()=>channel.close(),{once:true});
  });
}

let claimPromise;
export function useWindowNamespace() {
  const [identity,setIdentity]=useState(null);
  useEffect(()=>{let alive=true;
    if(!claimPromise)claimPromise=claimWindowNamespace();
    claimPromise.then(value=>{if(alive)setIdentity(value);});
    return()=>{alive=false;};
  },[]);
  return identity;
}

export function workspaceHeaders(windowId) {
  const browser=getBrowserNamespace();
  if(!browser||!windowId)throw new Error('Browser storage is unavailable. Server session recovery is unavailable in this window.');
  return {'X-Workspace-Browser':browser,'X-Workspace-Window':windowId};
}
