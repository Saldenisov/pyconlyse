import React, { useCallback, useEffect, useRef, useState } from 'react';
import { workspaceRequest } from '../useVd2ServerWorkspace';
import { cleanServerPath, serverPathParent } from '../serverPaths';
import './ServerSessionPicker.css';

export default function VD2FolderPicker({value,onChange,disabled=false,kind='folder',onChoose=onChange}) {
  const manifest=kind==='manifest';
  const inputLabel=manifest?'Manifest JSON path':'Everest folder';
  const [open,setOpen]=useState(false),[draft,setDraft]=useState(value),[listing,setListing]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const alive=useRef(true),sequence=useRef(0),dialog=useRef(null),button=useRef(null);
  const invalidate=useCallback(()=>{sequence.current++;},[]);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;invalidate();};},[invalidate]);
  useEffect(()=>{if(open)dialog.current?.focus();},[open]);
  const load=async path=>{
    const epoch=++sequence.current;setBusy(true);setError('');setListing(null);
    try{const result=await workspaceRequest(`/api/pump-probe-vd2/protocol/folders?${new URLSearchParams({folder:cleanServerPath(path),...(manifest?{kind:'manifest'}:{})})}`);
      if(alive.current&&epoch===sequence.current){setListing(result);setDraft(result.folder);}}
    catch(cause){if(alive.current&&epoch===sequence.current)setError(cause.message);}
    finally{if(alive.current&&epoch===sequence.current)setBusy(false);}
  };
  const close=()=>{sequence.current++;setOpen(false);setBusy(false);button.current?.focus();};
  const keys=event=>{
    if(event.key==='Escape'){event.preventDefault();close();}
    if(event.key==='Tab'){
      const controls=[...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled)')],first=controls[0],last=controls[controls.length-1];
      if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===dialog.current)){event.preventDefault();first?.focus();}
    }
  };
  return <>
    <span className="vd2-folder-input"><input aria-label={inputLabel} value={value} disabled={disabled} onChange={event=>onChange(event.target.value)} />
      <button type="button" ref={button} aria-label={manifest?'Browse manifest JSON':'Browse Everest folder'} title={manifest?'Choose manifest on server':'Choose folder on Everest'} disabled={disabled} onClick={()=>{const initial=manifest?serverPathParent(value):cleanServerPath(value);setOpen(true);setDraft(initial);load(initial);}}>…</button></span>
    {open&&<div className="server-session-backdrop" onClick={close}>
      <section role="dialog" aria-modal="true" aria-label={manifest?'Choose manifest JSON':'Choose Everest folder'} tabIndex="-1" ref={dialog} onKeyDown={keys} onClick={event=>event.stopPropagation()}>
        <header><strong>{manifest?'Manifest JSON':'Everest folder'}</strong><button type="button" onClick={close}>Cancel</button></header>
        <form onSubmit={event=>{event.preventDefault();load(draft);}} className="vd2-folder-path">
          <input aria-label="Folder path on Everest" value={draft} onChange={event=>setDraft(event.target.value)} />
          <button type="submit" disabled={busy}>Open</button>
          <button type="button" disabled={busy||!listing?.parent} onClick={()=>load(listing.parent)}>Up</button>
          <button type="button" disabled={busy} onClick={()=>load('')}>Data root</button>
        </form>
        {busy&&<p role="status">Loading folders…</p>}{error&&<p role="alert">{error}</p>}
        {listing&&<><p>{listing.folder}</p><div className="server-session-list">{listing.folders.map(folder=><button type="button" key={folder.path} onClick={()=>load(folder.path)}>▸ {folder.name}</button>)}
          {manifest&&(listing.files||[]).map(file=><button type="button" key={file.path} disabled={disabled} onClick={()=>{onChoose(cleanServerPath(file.path));close();}}>▤ {file.name}</button>)}</div>
          {!listing.folders.length&&(!manifest||!listing.files?.length)&&<p>{manifest?'No JSON files or subfolders.':'No subfolders.'}</p>}{listing.truncated&&<p>First 1000 entries shown. Enter a path to open another folder.</p>}
          {!manifest&&<footer><button type="button" disabled={disabled||busy} onClick={()=>{onChoose(listing.folder);close();}}>Use this folder</button></footer>}</>}
      </section>
    </div>}
  </>;
}
