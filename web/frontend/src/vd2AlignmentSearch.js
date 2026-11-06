// Pure measurement/search logic. Importing this module performs no I/O.
export const ALIGNMENT_CHANNELS = ['T1-1', 'T1-2', 'H1', 'V1', 'Dip1', 'Dip2', 'Bcd1', 'Bcd2'];
const canonical = name => String(name).toLowerCase().replace(/[^a-z0-9]/g, '');
const quantize = value => Math.round(value * 1000) / 1000;

export function signalStatistics(values) {
  if (!values.length || values.some(value => !Number.isFinite(value))) return null;
  const mean = values.reduce((sum,value) => sum+value,0)/values.length;
  return { mean, sd:values.length > 1 ? Math.sqrt(values.reduce((sum,value) => sum+(value-mean)**2,0)/(values.length-1)) : null, n:values.length };
}

export class AlignmentSignalBuffer {
  constructor() { this.key=null;this.samples=[];this.lastId=null;this.order=0; }
  record(id,percent,key,at) {
    if (!id || !Number.isFinite(percent) || !Number.isFinite(at)) return;
    if (this.key!==key) {this.key=key;this.samples=[];this.lastId=null;}
    if (id===this.lastId) return;
    this.lastId=id;this.samples.push({id,percent,at,order:++this.order});
    this.samples=this.samples.filter(sample=>sample.at>=at-60000).slice(-1000);
  }
  invalidate() {this.key=null;this.samples=[];this.lastId=null;}
  summarize(start,end,key=this.key,afterOrder=-Infinity) {
    if (!key || key!==this.key) return null;
    const samples=this.samples.filter(sample=>sample.at>=start&&sample.at<=end&&sample.order>afterOrder);
    const stats=signalStatistics(samples.map(sample=>sample.percent));
    return stats ? {...stats,key,start,end,frameIds:samples.map(sample=>sample.id),lastOrder:samples[samples.length-1].order} : null;
  }
  assertFresh(key,now) {
    const last=this.samples[this.samples.length-1];
    if (!key || this.key!==key) throw new Error('ROI, averaging, calibration or image settings changed. Search stopped.');
    if (!last || now-last.at>1500) throw new Error('No fresh Alignment frames. Search stopped.');
  }
}

export function searchChannels(data) {
  if (data.success!==true) throw new Error(data.error||'iTest readback unavailable');
  const channels=ALIGNMENT_CHANNELS.map(name=>{
    const matches=(data.names||[]).map((value,index)=>canonical(value)===canonical(name)?index:-1).filter(index=>index>=0);
    if(matches.length!==1) throw new Error(`Cannot uniquely identify ${name}`);
    const index=matches[0],id=data.ids?.[index],value=data.currents_setpoint?.[index],measured=data.currents_meas?.[index];
    const min=data.current_limits?.[index*2],max=data.current_limits?.[index*2+1];
    if(!Number.isInteger(id)||![value,measured,min,max].every(Number.isFinite)||min>=max||value<min||value>max) throw new Error(`Invalid ${name} current/limits`);
    if(data.states?.[index]!==1) throw new Error(`${name} output is not ON. Search does not enable outputs.`);
    return {id,name,value,measured,min,max};
  });
  if(new Set(channels.map(channel=>channel.id)).size!==8)throw new Error('iTest channel IDs are not unique');
  return channels;
}

export function makeSearchPlan(channels,{probe=0.05,radius=0.05,seconds=3,iterations=3}={}) {
  if(channels.length!==8 || ![probe,radius,seconds].every(Number.isFinite)||probe<0.005||probe>0.05||radius<probe||radius>0.5
    ||seconds<2||seconds>10||!Number.isInteger(iterations)||iterations<1||iterations>5) throw new Error('Choose a 0.005–0.05 A probe, probe ≤ offset ≤ 0.5 A, 2–10 s and 1–5 iterations.');
  const start=channels.map(channel=>channel.value);
  const bounds=channels.map(channel=>[Math.ceil((Math.max(channel.min,channel.value-radius)-1e-9)*1000)/1000,
    Math.floor((Math.min(channel.max,channel.value+radius)+1e-9)*1000)/1000]);
  if(bounds.some((pair,index)=>pair[0]>=pair[1]||start[index]<pair[0]||start[index]>pair[1]))throw new Error('Current bounds do not permit the selected search');
  return {channels,start,bounds,probe,radius,seconds,iterations};
}

function solve(matrix,vector) {
  const n=vector.length,a=matrix.map((row,index)=>[...row,vector[index]]);
  for(let col=0;col<n;col+=1) {
    let pivot=col;for(let row=col+1;row<n;row+=1) if(Math.abs(a[row][col])>Math.abs(a[pivot][col])) pivot=row;
    [a[col],a[pivot]]=[a[pivot],a[col]];
    if(Math.abs(a[col][col])<1e-12) return Array(n).fill(0);
    const divisor=a[col][col];for(let j=col;j<=n;j+=1)a[col][j]/=divisor;
    for(let row=0;row<n;row+=1) if(row!==col) {const factor=a[row][col];for(let j=col;j<=n;j+=1)a[row][j]-=factor*a[col][j];}
  }
  return a.map(row=>row[n]);
}
const dot=(a,b)=>a.reduce((sum,value,index)=>sum+value*b[index],0);
const difference=(a,b)=>a.map((value,index)=>value-b[index]);
const same=(a,b)=>a.every((value,index)=>Math.abs(value-b[index])<0.0005);

export class AlignmentSearchStopped extends Error {}

export function makeRestorePlan(snapshot,channels) {
  if(!snapshot?.id||!Array.isArray(snapshot.channels)||snapshot.channels.length!==8||channels.length!==8)throw new Error('A complete saved state is required');
  const targets=snapshot.channels.map((saved,index)=>{
    const current=channels[index];
    if(saved.name!==ALIGNMENT_CHANNELS[index]||current.name!==saved.name||current.id!==saved.id)throw new Error('Saved channel IDs/names no longer match iTest');
    if(!Number.isFinite(saved.value)||saved.value<current.min||saved.value>current.max)throw new Error(`${saved.name} saved current exceeds current native limits`);
    if(Math.abs(quantize(saved.value)-saved.value)>1e-6)throw new Error(`${saved.name} saved current exceeds iTest resolution`);
    return saved.value;
  });
  return {channels,start:channels.map(channel=>channel.value),targets,snapshot};
}

export async function restoreAlignmentSettings({plan,read,write,sleep,now,signal,onProgress=()=>{}}) {
  let known=[...plan.start];
  const checkpoint=()=>{if(signal?.aborted)throw new AlignmentSearchStopped('Restore stopped; currents kept at the last confirmed position.');};
  const verify=async()=>{
    checkpoint();const current=await read();checkpoint();
    makeRestorePlan(plan.snapshot,current); // Validate every target before each write.
    if(current.some((channel,index)=>channel.id!==plan.channels[index].id||Math.abs(channel.value-known[index])>0.0005))throw new Error('Currents changed outside this restore. No further writes.');
    return current;
  };
  const settle=async()=>{
    const start=now();
    while(true) {
      const current=await verify();
      if(current.every((channel,index)=>Math.abs(channel.measured-known[index])<=0.01))return;
      if(now()-start>=10000)throw new Error('Restored current readback did not settle within 10 s');
      await sleep(200);
    }
  };
  try {
    await settle();
    for(let index=0;index<8;index+=1) {
      while(Math.abs(plan.targets[index]-known[index])>0.0005) {
        await verify();
        const next=quantize(known[index]+Math.sign(plan.targets[index]-known[index])*Math.min(0.05,Math.abs(plan.targets[index]-known[index])));
        onProgress({phase:`Restoring ${plan.channels[index].name}`,target:next});
        try {await write(plan.channels[index].id,next);} catch(error) {error.uncertain=true;throw error;}
        known[index]=next;await settle();
      }
    }
    return {status:'restored',position:known,snapshot_id:plan.snapshot.id};
  } catch(error) {
    error.result={status:error instanceof AlignmentSearchStopped?'stopped':'failed',position:known,uncertain:Boolean(error.uncertain)};
    throw error;
  }
}

export async function runAlignmentSearch({plan,read,write,measure,checkSignal,sleep,now,signal,onProgress=()=>{}}) {
  let known=[...plan.start],best=null,measurements=0;
  const history=[];
  const checkpoint=()=>{if(signal?.aborted)throw new AlignmentSearchStopped('Stopped; currents kept at the last tested position.');checkSignal();};
  const verify=async()=>{
    checkpoint();const actual=await read();checkpoint();
    if(actual.length!==8)throw new Error('Eight current readbacks are required');
    actual.forEach((channel,index)=>{
      const original=plan.channels[index];
      if(channel.id!==original.id||channel.name!==original.name||Math.abs(channel.value-known[index])>0.0005)throw new Error('iTest currents changed outside this search. No further writes.');
      if(known[index]<channel.min||known[index]>channel.max)throw new Error(`${channel.name} current limits changed`);
    });
    return actual;
  };
  const move=async target=>{
    for(let index=0;index<8;index+=1) {
      if(!Number.isFinite(target[index])||target[index]<plan.bounds[index][0]-1e-9||target[index]>plan.bounds[index][1]+1e-9)throw new Error('Search target exceeds the selected bounds');
      while(Math.abs(target[index]-known[index])>0.0005) {
        await verify();
        const next=quantize(known[index]+Math.sign(target[index]-known[index])*Math.min(plan.probe,Math.abs(target[index]-known[index])));
        if(next===known[index])throw new Error('Search step is below iTest resolution');
        onProgress({phase:'setting',channel:plan.channels[index].name,target:next,best,measurements});
        try {await write(plan.channels[index].id,next);} catch(error) {error.uncertain=true;throw error;}
        known[index]=next;
        // A cancelled request is never replayed. At most this one awaited write
        // can finish after Stop; no subsequent command passes checkpoint().
        await verify();
      }
    }
  };
  const evaluate=async(position,phase)=>{
    await move(position);
    const settling=now();
    while(true) {
      const actual=await verify();
      if(actual.every((channel,index)=>Math.abs(channel.measured-position[index])<=0.01))break;
      if(now()-settling>10000)throw new Error('iTest measured currents did not settle within 10 s');
      onProgress({phase:'settling',measurements,best});await sleep(200);
    }
    const start=now();onProgress({phase,position:[...position],measurements,best});
    while(now()-start<plan.seconds*1000) {checkpoint();await sleep(Math.min(100,plan.seconds*1000-(now()-start)));}
    await verify();const stats=await measure(start,now());checkpoint();
    if(!stats||stats.n<3||!Number.isFinite(stats.mean)||!Number.isFinite(stats.sd))throw new Error('Not enough fresh frames for mean ± SD. Search stopped.');
    const result={position:[...position],...stats,measuredAt:(start+now())/2};measurements+=1;history.push({...result,phase,at:now()});
    onProgress({phase:'measured',last:result,measurements,best});return result;
  };
  let reason='iteration limit';
  try {
    best=await evaluate(plan.start,'baseline');
    let centre=[...plan.start],h=plan.probe,damping=0.01,model=null,previousGradient=null,previousCentre=null;
    for(let iteration=0;iteration<plan.iterations;iteration+=1) {
      checkpoint();let reference=best;
      if(!same(centre,best.position))reference=await evaluate(centre,'reference');
      const gradient=[],curvature=[],probes=[];
      for(let axis=0;axis<8;axis+=1) {
        const lower=quantize(Math.max(plan.bounds[axis][0],centre[axis]-h));
        const upper=quantize(Math.min(plan.bounds[axis][1],centre[axis]+h));
        const hm=centre[axis]-lower,hp=upper-centre[axis];
        let minus=reference,plus=reference;
        if(hm>=0.0005){const point=[...centre];point[axis]=lower;minus=await evaluate(point,`gradient ${axis+1}/8 −`);probes.push(minus);}
        if(hp>=0.0005){const point=[...centre];point[axis]=upper;plus=await evaluate(point,`gradient ${axis+1}/8 +`);probes.push(plus);}
        gradient[axis]=hm>=0.0005&&hp>=0.0005
          ?(hm*hm*(plus.mean-reference.mean)+hp*hp*(reference.mean-minus.mean))/(hp*hm*(hp+hm))
          :hp>=0.0005?(plus.mean-reference.mean)/hp:hm>=0.0005?(reference.mean-minus.mean)/hm:0;
        curvature[axis]=hm>=0.0005&&hp>=0.0005?-2*(hm*plus.mean-(hm+hp)*reference.mean+hp*minus.mean)/(hp*hm*(hp+hm)):1;
      }
      if(!model)model=curvature.map((value,row)=>curvature.map((_,col)=>row===col?Math.max(1,Math.abs(value)):0));
      if(previousGradient&&previousCentre) {
        // BFGS curvature update for loss = -signal; positive curvature preserves
        // a bounded ascent direction rather than inverting a noisy Hessian.
        const s=difference(centre,previousCentre),y=difference(previousGradient,gradient),ys=dot(y,s),bs=model.map(row=>dot(row,s)),sbs=dot(s,bs);
        if(ys>1e-8&&sbs>1e-8)model=model.map((row,i)=>row.map((value,j)=>value+y[i]*y[j]/ys-bs[i]*bs[j]/sbs));
      }
      const scale=Math.max(1,...model.map((row,index)=>Math.abs(row[index])));
      const regularization=damping*scale,maxStep=h;
      let step=solve(model.map((row,i)=>row.map((value,j)=>value+(i===j?regularization:0))),gradient);
      const largest=Math.max(...step.map(Math.abs));if(largest>maxStep)step=step.map(value=>value*maxStep/largest);
      const trial=centre.map((value,index)=>quantize(Math.max(plan.bounds[index][0],Math.min(plan.bounds[index][1],value+step[index]))));
      if(!same(trial,centre))probes.push(await evaluate(trial,'damped Newton trial'));
      const candidate=probes.reduce((retained,item)=>item.mean>retained.mean?item:retained,reference);
      const threshold=Math.max(0.05,Math.hypot(candidate.sd,reference.sd));
      let accepted=false;
      if(!same(candidate.position,centre)&&candidate.mean-reference.mean>threshold) {
        const freshReference=await evaluate(centre,'confirm reference');
        const freshCandidate=await evaluate(candidate.position,'confirm candidate');
        const referenceAfter=await evaluate(centre,'confirm reference after');
        const fraction=Math.max(0,Math.min(1,(freshCandidate.measuredAt-freshReference.measuredAt)/(referenceAfter.measuredAt-freshReference.measuredAt)));
        const predictedReference=freshReference.mean+fraction*(referenceAfter.mean-freshReference.mean);
        const confirmationThreshold=Math.max(0.05,Math.hypot(freshCandidate.sd,(1-fraction)*freshReference.sd,fraction*referenceAfter.sd));
        if(freshCandidate.mean-predictedReference>confirmationThreshold) {
          previousCentre=[...centre];previousGradient=[...gradient];centre=[...candidate.position];best=freshCandidate;
          best.confirmedGain={reference:predictedReference,improvement:freshCandidate.mean-predictedReference,threshold:confirmationThreshold};
          damping=Math.max(0.001,damping*0.3);accepted=true;
        } else best=referenceAfter;
      }
      if(!accepted){h=quantize(h/2);damping*=10;previousCentre=null;previousGradient=null;}
      onProgress({phase:accepted?'improvement confirmed':'step reduced',iteration:iteration+1,best,measurements});
      if(h<0.005){reason='no confirmed improvement above noise';break;}
    }
    const final=await evaluate(best.position,'final verification');best=final;
    return {status:'completed',reason,best,position:[...known],history,measurements};
  } catch(error) {
    error.result={status:error instanceof AlignmentSearchStopped?'stopped':'failed',error:error.message,best,position:[...known],history,measurements,uncertain:Boolean(error.uncertain)};
    throw error;
  }
}
