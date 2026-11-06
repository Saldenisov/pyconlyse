import React, { useEffect, useRef, useState } from 'react';
import './ServerSessionPicker.css';

export default function ServerSessionPicker({load,onRestore,disabled=false}) {
  const [open,setOpen]=useState(false),[items,setItems]=useState([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const button=useRef(null),dialog=useRef(null),alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(()=>{if(open)dialog.current?.focus();},[open]);
  const close=()=>{if(!busy){setOpen(false);button.current?.focus();}};
  const show=async()=>{
    setOpen(true);setBusy(true);setError('');setItems([]);
    try{const data=await load();if(alive.current)setItems(data);}
    catch(cause){if(alive.current)setError(cause.message);}
    finally{if(alive.current)setBusy(false);}
  };
  const restore=async item=>{
    if(disabled)return;
    setBusy(true);setError('');
    try{await onRestore(item);if(alive.current){setOpen(false);button.current?.focus();}}
    catch(cause){if(alive.current)setError(cause.message);}
    finally{if(alive.current)setBusy(false);}
  };
  const keys=event=>{
    if(event.key==='Escape'){event.preventDefault();close();}
    if(event.key==='Tab'){
      const controls=[...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled)')];
      const first=controls[0],last=controls[controls.length-1];
      if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===dialog.current)){event.preventDefault();first?.focus();}
    }
  };
  return <>
    <button type="button" ref={button} onClick={show} disabled={disabled}>Restore session</button>
    {open&&<div className="server-session-backdrop" onClick={close}>
      <section ref={dialog} tabIndex="-1" role="dialog" aria-modal="true" aria-label="Restore session from server" onKeyDown={keys} onClick={event=>event.stopPropagation()}>
        <header><strong>Restore session from server</strong><button type="button" onClick={close} disabled={busy}>Cancel</button></header>
        <p>Saved work from this browser. Restore a copy; other windows keep their own state.</p>
        {busy&&<p role="status">Loading…</p>}{error&&<p role="alert">{error}</p>}
        {!busy&&!error&&!items.length&&<p>No saved sessions in this browser yet.</p>}
        <div className="server-session-list">{items.map(item=><button type="button" key={item.id} disabled={busy||disabled} onClick={()=>restore(item)}>
          <strong>{item.name}</strong><span>{item.folder}</span><small>{item.updated_at?new Date(item.updated_at).toLocaleString():'Saved session'}</small>
        </button>)}</div>
      </section>
    </div>}
  </>;
}
