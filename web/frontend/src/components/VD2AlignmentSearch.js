import React,{useEffect,useRef,useState} from 'react';
import {fetchWithHardwareApproval} from '../api/csrfRequest';
import {captureAlignmentSnapshot,getAlignmentSnapshots} from '../api/vd2AlignmentPresets';
import {makeRestorePlan,makeSearchPlan,restoreAlignmentSettings,runAlignmentSearch,searchChannels} from '../vd2AlignmentSearch';

async function responseJson(response) {
  const data=await response.json();
  if(!response.ok||data.success!==true)throw new Error(data.error||`Search request failed (HTTP ${response.status})`);
  return data;
}
const changed=(a,b)=>a.length!==b.length||a.some((value,index)=>Math.abs(value-b[index])>0.0005);
const sourceName=snapshot=>({manual_best:'Operator-saved best',search_best:'Completed search best',before_search:'Before previous search (not a verified best)',
  before_restore:'Before previous restore'}[snapshot?.kind]||'No saved settings');
const stamp=snapshot=>snapshot?new Date(snapshot.created_at).toLocaleString():'';

function RestoreTable({plan}) {
  return <table><thead><tr><th>Channel</th><th>Now, A</th><th>Saved, A</th></tr></thead><tbody>
    {plan.channels.map((channel,index)=><tr key={channel.id}><td>{channel.name}</td><td>{channel.value.toFixed(3)}</td><td>{plan.targets[index].toFixed(3)}</td></tr>)}
  </tbody></table>;
}

export default function VD2AlignmentSearch({device,measurements,live,onRunning}) {
  const [open,setOpen]=useState(false),[plan,setPlan]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [running,setRunning]=useState(false),[action,setAction]=useState(''),[stopping,setStopping]=useState(false),[progress,setProgress]=useState(null),[result,setResult]=useState(null);
  const [saved,setSaved]=useState(null),[restoreReview,setRestoreReview]=useState(null),[searchChoice,setSearchChoice]=useState(null);
  const [options,setOptions]=useState({probe:0.05,radius:0.05,seconds:3,iterations:3});
  const controller=useRef(null),active=useRef(false),uncertain=useRef(false),liveRef=useRef(live),alive=useRef(true);
  liveRef.current=live;
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;controller.current?.abort();};},[]);
  useEffect(()=>{
    let cancelled=false;setSaved(null);
    getAlignmentSnapshots(device).then(data=>{if(!cancelled)setSaved(data);}).catch(cause=>{if(!cancelled)setError(cause.message);});
    return()=>{cancelled=true;};
  },[device]);
  const refreshSaved=async()=>{const data=await getAlignmentSnapshots(device);if(alive.current)setSaved(data);return data;};
  const read=async()=>{
    const abort=new AbortController(),timer=window.setTimeout(()=>abort.abort(),7000);
    try{return searchChannels(await responseJson(await fetch(`/api/device/itest/${device}/all_slots`,{credentials:'include',signal:abort.signal})));}
    finally{window.clearTimeout(timer);}
  };
  const write=async(id,current)=>{
    const data=await responseJson(await fetchWithHardwareApproval(`/api/device/ds_itest_psu/${device}/slot/${id}/current`,{
      method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({current})}));
    if(data.slot_id!==id||!Number.isFinite(data.current_setpoint)||Math.abs(data.current_setpoint-current)>0.0005)throw new Error('iTest did not confirm the requested current.');
  };
  const checkpoint=abort=>{if(abort.signal.aborted)throw new Error('Stopped before the next action.');};
  const perform=async(label,task)=>{
    if(active.current)return;
    if(uncertain.current&&['Searching','Restoring'].includes(label)){setError('Prior current write outcome is unknown. Resolve it before further writes.');return;}
    const abort=new AbortController();controller.current=abort;active.current=true;setRunning(true);setAction(label);onRunning?.(true);
    setError('');setNotice('');setStopping(false);
    try{await task(abort);}
    catch(cause){if(cause.uncertain||cause.result?.uncertain)uncertain.current=true;if(alive.current){setError(cause.message);if(cause.result)setResult({...cause.result,plan});}}
    finally{active.current=false;controller.current=null;if(alive.current){setRunning(false);setStopping(false);onRunning?.(false);}}
  };
  const capture=async(kind,channels,extra={})=>{
    const snapshot=await captureAlignmentSnapshot({device,kind,channels,context:{signal_key:measurements.key,search_options:options},...extra});
    if(alive.current)setSaved(current=>{
      const next={...current};
      if(['manual_best','search_best'].includes(kind))next.best=snapshot;
      if(kind==='before_search')next.previous=snapshot;
      if(kind==='before_restore')next.before_restore=snapshot;
      next.recommended=next.best||next.previous||null;
      return next;
    });
    return snapshot;
  };
  const review=()=>perform('Reviewing',async()=>{
    setOpen(true);setPlan(null);setSearchChoice(null);setRestoreReview(null);
    const [next]=await Promise.all([read(),refreshSaved()]);
    if(alive.current)setPlan(makeSearchPlan(next,options));
  });
  const saveBest=()=>perform('Saving',async abort=>{
    const channels=await read();checkpoint(abort);
    const snapshot=await capture('manual_best',channels);
    if(alive.current)setNotice(`Saved best · ${stamp(snapshot)}`);
    await refreshSaved();
  });
  const reviewRestore=snapshot=>perform('Reviewing',async()=>{
    const channels=await read();
    const next=makeRestorePlan(snapshot,channels);
    if(alive.current){setRestoreReview(next);setSearchChoice(null);}
  });
  const restore=async(reviewed,abort)=>{
    const channels=await read();checkpoint(abort);
    const next=makeRestorePlan(reviewed.snapshot,channels);
    if(changed(next.start,reviewed.start))throw new Error('Currents changed after review. Review saved settings again.');
    await capture('before_restore',channels,{parent_id:reviewed.snapshot.id});checkpoint(abort);
    const outcome=await restoreAlignmentSettings({plan:next,read,write,signal:abort.signal,now:()=>Date.now(),
      sleep:ms=>new Promise(resolve=>window.setTimeout(resolve,ms)),onProgress:value=>{if(alive.current)setProgress(value);}});
    if(alive.current){setRestoreReview(null);setNotice(`Restored · ${sourceName(reviewed.snapshot)} · ${stamp(reviewed.snapshot)}`);}
    return outcome;
  };
  const confirmRestore=()=>perform('Restoring',async abort=>{
    setResult(null);setProgress(null);
    const outcome=await restore(restoreReview,abort);
    if(alive.current){setResult(outcome);setPlan(null);}
    await refreshSaved();
  });
  const start=(mode='prompt')=>perform('Searching',async abort=>{
    setResult(null);setProgress(null);setRestoreReview(null);
    let freshPlan=makeSearchPlan(await read(),options);checkpoint(abort);
    const reviewed=searchChoice?.plan||plan;
    if(!reviewed||changed(freshPlan.start,reviewed.start)||freshPlan.channels.some((channel,index)=>channel.id!==reviewed.channels[index].id))throw new Error('Currents changed after review. Review the new starting currents.');
    const history=await refreshSaved();checkpoint(abort);
    const context=measurements.key;
    measurements.assertFresh(context,Date.now());
    if(!liveRef.current)throw new Error('Start Live before Search.');
    if(mode==='prompt'&&history.recommended) {
      let previous;
      try {previous=makeRestorePlan(history.recommended,freshPlan.channels);}
      catch(cause) {setSearchChoice({plan:freshPlan,snapshot:history.recommended,restore:null,error:cause.message});return;}
      if(changed(previous.start,previous.targets)) {
        setSearchChoice({plan:freshPlan,restore:previous});return;
      }
    }
    if(mode==='restore') {
      if(!searchChoice)throw new Error('Review the saved settings before restoring');
      await restore(searchChoice.restore,abort);checkpoint(abort);
      freshPlan=makeSearchPlan(await read(),options);
      if(changed(freshPlan.start,searchChoice.restore.targets))throw new Error('Restored settings changed before search');
    }
    setSearchChoice(null);setPlan(freshPlan);
    // A durable return point is mandatory before the engine gets any write callback.
    const searchContext={signal_key:context,search_options:options};
    const baseline=await capture('before_search',freshPlan.channels,{context:searchContext});checkpoint(abort);
    measurements.assertFresh(context,Date.now());
    const outcome=await runAlignmentSearch({plan:freshPlan,read,write,
      checkSignal:()=>{if(!liveRef.current)throw new Error('Live stopped. Search stopped.');measurements.assertFresh(context,Date.now());},
      measure:(from,to)=>measurements.summarize(from,to,context),now:()=>Date.now(),
      sleep:ms=>new Promise(resolve=>window.setTimeout(resolve,ms)),signal:abort.signal,
      onProgress:value=>{if(alive.current)setProgress(value);},
    });
    if(alive.current)setResult({...outcome,plan:freshPlan,return_point:baseline.id});
    if(outcome.status==='completed') {
      checkpoint(abort);
      try {
        const channels=await read();checkpoint(abort);
        if(!outcome.best||changed(channels.map(channel=>channel.value),outcome.best.position)
          ||channels.some((channel,index)=>channel.id!==freshPlan.channels[index].id))throw new Error('Final currents changed after verification');
        const best=await capture('search_best',channels,{context:searchContext,parent_id:baseline.id,quality:{mean:outcome.best.mean,sd:outcome.best.sd,n:outcome.best.n}});
        if(alive.current)setNotice(`Completed best saved · ${stamp(best)}`);
      } catch(cause) {throw new Error(`Search completed, but best was not saved: ${cause.message}. Previous saved best is preserved.`);}
    }
    await refreshSaved();
  });
  const save=()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download=`VD2-alignment-search-${Date.now()}.json`;link.click();URL.revokeObjectURL(url);
  };
  const best=result?.best||progress?.best;
  const recommended=saved?.recommended;
  return <section className="vd2-alignment-search" aria-label="Alignment search">
    <div className="vd2-search-actions">
      <button type="button" onClick={review} disabled={running}>Search</button>
      <button type="button" onClick={saveBest} disabled={running||!saved||saved.available===false}>Save as best</button>
      <button type="button" onClick={()=>reviewRestore(recommended)} disabled={running||!recommended}>Restore saved…</button>
      {running&&<button type="button" className="vd2-stop" onClick={()=>{setStopping(true);controller.current?.abort();}} disabled={stopping}>{stopping?'Stopping…':'Stop'}</button>}
      {(running||result)&&<output>{running?progress?.phase||action:result?.status||'Ready'}{(result?.measurements??progress?.measurements)!==undefined?` · ${result?.measurements??progress?.measurements} points`:''}</output>}
    </div>
    <small>{saved?(saved.available===false?'Saved-current presets need Web reload.':recommended?`${sourceName(recommended)} · ${stamp(recommended)}`:'No saved settings yet. The first search records its starting state.'):'Loading saved settings…'}</small>
    {(saved?.previous||saved?.before_restore)&&<details className="vd2-saved-return-points"><summary>Return points</summary>
      {saved.previous&&<button type="button" disabled={running} onClick={()=>reviewRestore(saved.previous)}>Before last search</button>}
      {saved.before_restore&&<button type="button" disabled={running} onClick={()=>reviewRestore(saved.before_restore)}>Before last restore</button>}
    </details>}
    {restoreReview&&<div className="vd2-restore-review" aria-label="Review saved settings">
      <strong>{sourceName(restoreReview.snapshot)}</strong><small>{stamp(restoreReview.snapshot)}</small><RestoreTable plan={restoreReview} />
      <div className="vd2-search-actions"><button type="button" disabled={running||Boolean(result?.uncertain)} onClick={confirmRestore}>Restore these 8 currents</button>
        <button type="button" disabled={running} onClick={()=>setRestoreReview(null)}>Cancel</button></div>
    </div>}
    {open&&<form onSubmit={event=>{event.preventDefault();if(plan&&!searchChoice)start();}} aria-label="Alignment search settings">
      <strong>Damped Newton · BFGS · 8 currents</strong>
      <div className="vd2-search-settings">{[['probe','Probe, A','0.005','0.05','0.005'],['radius','Max offset ± A','0.005','0.5','0.005'],
        ['seconds','Seconds / point','2','10','1'],['iterations','Iterations','1','5','1']].map(([key,label,min,max,step])=>
        <label key={key}>{label}<input type="number" min={min} max={max} step={step} value={options[key]} disabled={running}
          onChange={event=>{setOptions(current=>({...current,[key]:Number(event.target.value)}));setPlan(null);setSearchChoice(null);}} /></label>)}</div>
      <p>Mean ± SD; wait for current readback, then measure. Improvements are remeasured before acceptance.</p>
      {plan&&<details><summary>Current values are zero offsets · bounds</summary><table><thead><tr><th>Channel</th><th>Start, A</th><th>Bounds, A</th></tr></thead><tbody>
        {plan.channels.map((channel,index)=><tr key={channel.id}><td>{channel.name}</td><td>{channel.value.toFixed(3)}</td><td>{plan.bounds[index].map(value=>value.toFixed(3)).join(' … ')}</td></tr>)}
      </tbody></table></details>}
      {searchChoice?<div className="vd2-restore-review" role="group" aria-label="Restore before search">
        <strong>Restore to the previous state?</strong><small>{sourceName(searchChoice.restore?.snapshot||searchChoice.snapshot)} · {stamp(searchChoice.restore?.snapshot||searchChoice.snapshot)}</small>
        {searchChoice.restore?<RestoreTable plan={searchChoice.restore} />:<p role="alert">Saved settings cannot be restored: {searchChoice.error}</p>}
        <div className="vd2-search-actions"><button type="button" disabled={running||!searchChoice.restore} onClick={()=>start('restore')}>Restore then search</button>
          <button type="button" disabled={running} onClick={()=>start('current')}>Search from current settings</button>
          <button type="button" disabled={running} onClick={()=>setSearchChoice(null)}>Cancel</button></div>
      </div>:<div className="vd2-search-actions"><button type="button" disabled={running} onClick={review}>Review currents</button>
        <button type="submit" disabled={running||!plan||!live||saved?.available===false||Boolean(result?.uncertain)}>Start search &amp; apply best</button></div>}
      <small>Starting currents are saved in the database before every search. Stop keeps the current tested settings.</small>
    </form>}
    {best&&<p>Best ΔI/I₀: {best.mean.toFixed(2)}% ± {best.sd.toFixed(2)}% · n={best.n}</p>}
    {result?.reason&&<p>{result.reason}</p>}
    {notice&&<p role="status">{notice}</p>}
    {error&&<p role="alert">{error}</p>}
    {result&&<button type="button" onClick={save}>Save search JSON</button>}
  </section>;
}
