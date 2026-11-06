import {ALIGNMENT_CHANNELS,AlignmentSignalBuffer,AlignmentSearchStopped,makeRestorePlan,makeSearchPlan,restoreAlignmentSettings,runAlignmentSearch,searchChannels,signalStatistics} from './vd2AlignmentSearch';

const payload=()=>({success:true,ids:ALIGNMENT_CHANNELS.map((_,i)=>i+11),names:ALIGNMENT_CHANNELS,
  states:Array(8).fill(1),currents_setpoint:Array(8).fill(0),currents_meas:Array(8).fill(0),current_limits:Array(8).fill([-15,15]).flat()});

function restoreRig(value=0.11) {
  const native=payload();native.ids=[1,3,5,6,7,9,11,12];
  let time=0;
  const channels=searchChannels(native),snapshot={id:'saved',channels:channels.map(channel=>({...channel,value}))};
  const read=jest.fn(async()=>searchChannels(native)),controller=new AbortController();
  const write=jest.fn(async(id,current)=>{
    const index=native.ids.indexOf(id);native.currents_setpoint[index]=current;native.currents_meas[index]=current;
  });
  const callbacks={plan:makeRestorePlan(snapshot,channels),read,write,signal:controller.signal,now:()=>time,sleep:async ms=>{time+=ms;}};
  return {native,controller,callbacks};
}

test('restore validates every channel, saved identity and current native limits before any write',async()=>{
  const test=restoreRig();
  test.native.current_limits[15]=0.1;
  await expect(restoreAlignmentSettings(test.callbacks)).rejects.toThrow(/native limits/);
  expect(test.callbacks.write).not.toHaveBeenCalled();
  const channels=searchChannels(payload());
  const snapshot={id:'old',channels:channels.map(channel=>({...channel}))};
  snapshot.channels[7].id=100;
  expect(()=>makeRestorePlan(snapshot,channels)).toThrow(/IDs\/names/);
});

test('restore uses nonsequential native IDs, limits each change to 0.05 A and verifies all readbacks',async()=>{
  const test=restoreRig();
  const result=await restoreAlignmentSettings(test.callbacks);
  expect(result.status).toBe('restored');expect(result.position).toEqual(Array(8).fill(0.11));
  expect(test.callbacks.write.mock.calls.slice(0,3)).toEqual([[1,0.05],[1,0.1],[1,0.11]]);
  expect(test.callbacks.write.mock.calls.slice(-3)).toEqual([[12,0.05],[12,0.1],[12,0.11]]);
  expect(test.callbacks.read.mock.calls.length).toBeGreaterThan(test.callbacks.write.mock.calls.length);
});

test('restore stops after an uncertain write without retry or automatic rollback',async()=>{
  const test=restoreRig();test.callbacks.write.mockRejectedValue(new Error('RPC timeout'));
  await expect(restoreAlignmentSettings(test.callbacks)).rejects.toMatchObject({uncertain:true,result:{status:'failed',uncertain:true}});
  expect(test.callbacks.write).toHaveBeenCalledTimes(1);
});

test('Stop during a restore lets at most one pending write finish and never advances another channel',async()=>{
  const test=restoreRig();
  test.callbacks.write.mockImplementation(async()=>{test.controller.abort();});
  await expect(restoreAlignmentSettings(test.callbacks)).rejects.toBeInstanceOf(AlignmentSearchStopped);
  expect(test.callbacks.write).toHaveBeenCalledTimes(1);
});

test('restore refuses external current changes and nonsettling readbacks',async()=>{
  const test=restoreRig();test.native.currents_setpoint[0]=0.02;
  await expect(restoreAlignmentSettings(test.callbacks)).rejects.toThrow(/outside this restore/);
  expect(test.callbacks.write).not.toHaveBeenCalled();
  const unsettled=restoreRig();unsettled.native.currents_meas[0]=0.1;
  await expect(restoreAlignmentSettings(unsettled.callbacks)).rejects.toThrow(/did not settle/);
  expect(unsettled.callbacks.write).not.toHaveBeenCalled();
});

test('one-second percentages report sample SD, not standard error or an invented uncertainty',()=>{
  expect(signalStatistics([10,12,14])).toEqual({mean:12,sd:2,n:3});
  expect(signalStatistics([10])).toEqual({mean:10,sd:null,n:1});
  const buffer=new AlignmentSignalBuffer();
  buffer.record('first',10,'roi',0);buffer.record('first',10,'roi',20);buffer.record('second',14,'roi',500);
  expect(buffer.summarize(0,1000)).toMatchObject({mean:12,n:2,sd:Math.sqrt(8)});
  buffer.record('third',20,'new-gain',600);
  expect(buffer.summarize(0,1000,'roi')).toBeNull();
  expect(buffer.summarize(0,1000,'new-gain').n).toBe(1);
  expect(()=>buffer.assertFresh('new-gain',2200)).toThrow(/fresh/);
  buffer.invalidate();expect(()=>buffer.assertFresh('new-gain',600)).toThrow(/settings changed/);
});

test('a frame on a timer boundary is included once, even when recorded after that tick',()=>{
  const buffer=new AlignmentSignalBuffer();
  buffer.record('before',10,'roi',900);
  const first=buffer.summarize(0,1000,'roi');
  buffer.record('at-boundary',20,'roi',1000);
  buffer.record('after',30,'roi',1300);
  const second=buffer.summarize(1000,2000,'roi',first.lastOrder);
  expect(first.frameIds).toEqual(['before']);
  expect(second.frameIds).toEqual(['at-boundary','after']);
  expect(second.mean).toBe(25);
  expect(buffer.summarize(1000,2000,'roi',second.lastOrder)).toBeNull();
  buffer.invalidate();buffer.record('fresh',40,'roi',2000);
  expect(buffer.summarize(1000,2000,'roi',second.lastOrder)).toMatchObject({mean:40,n:1});
});

test('named slots are resolved by verified IDs and missing, off or duplicated channels are rejected',()=>{
  const data=payload();
  expect(searchChannels(data).map(channel=>channel.id)).toEqual([11,12,13,14,15,16,17,18]);
  expect(makeSearchPlan(searchChannels(data)).bounds[0]).toEqual([-0.05,0.05]);
  data.states[0]=0;expect(()=>searchChannels(data)).toThrow(/not ON/);
  data.states[0]=1;data.ids[0]=12;expect(()=>searchChannels(data)).toThrow(/not unique/);
  data.ids[0]=11;data.current_limits[1]=NaN;expect(()=>searchChannels(data)).toThrow(/Invalid/);
});

function rig(objective=position=>100-position.reduce((sum,value)=>sum+2000*(value-0.02)**2,0),options={}) {
  let time=0,position=Array(8).fill(0);
  const writes=[],controller=new AbortController(),plan=makeSearchPlan(searchChannels(payload()),options);
  const read=jest.fn(async()=>plan.channels.map((channel,index)=>({...channel,value:position[index],measured:position[index]})));
  const write=jest.fn(async(id,value)=>{const index=plan.channels.findIndex(channel=>channel.id===id);writes.push({index,value,previous:position[index]});position[index]=value;});
  const measure=jest.fn(()=>({mean:objective(position),sd:0.01,n:15}));
  const checkSignal=jest.fn();
  const callbacks={plan,read,write,measure,checkSignal,signal:controller.signal,now:()=>time,sleep:async ms=>{time+=ms;}};
  return {callbacks,controller,writes,get position(){return position;}};
}

test('damped Newton/BFGS approaches a coupled eight-current maximum and verifies it again',async()=>{
  const target=[0.025,-0.015,0.02,-0.025,0.01,-0.015,0.02,-0.01];
  const objective=p=>100-p.reduce((sum,value,i)=>sum+2000*(value-target[i])**2,0)-800*((p[0]-target[0])+(p[1]-target[1]))**2;
  const test=rig(objective,{iterations:3});
  const result=await runAlignmentSearch(test.callbacks);
  expect(result.status).toBe('completed');expect(result.best.mean).toBeGreaterThan(99.8);
  expect(result.history.at(-1).phase).toBe('final verification');
  expect(result.history.some(point=>point.phase==='confirm candidate')).toBe(true);
  expect(result.position).toEqual(result.best.position);
  expect(test.writes.every(point=>Math.abs(point.value)<=0.05&&Math.abs(point.value-point.previous)<=0.050001)).toBe(true);
});

test('pure pulse noise is not retained as an improvement',async()=>{
  let point=0;
  const test=rig(()=>50+Math.sin(point++)*0.01,{iterations:3});
  test.callbacks.measure=async()=>({mean:50+Math.sin(point++)*0.01,sd:0.2,n:15});
  const result=await runAlignmentSearch(test.callbacks);
  expect(result.best.position).toEqual(Array(8).fill(0));
  expect(result.position).toEqual(Array(8).fill(0));
});

test('a monotonically drifting beam is rejected by reference-candidate-reference confirmation',async()=>{
  const test=rig(()=>50,{iterations:2});
  test.callbacks.measure=async(start,end)=>({mean:50+(start+end)/2*0.0002,sd:0.18,n:15});
  const result=await runAlignmentSearch(test.callbacks);
  expect(result.history.some(point=>point.phase==='confirm reference after')).toBe(true);
  expect(result.best.position).toEqual(Array(8).fill(0));
  expect(result.position).toEqual(Array(8).fill(0));
});

test('Stop during an in-flight setting allows no subsequent write and does not replay or restore',async()=>{
  const test=rig();
  const write=test.callbacks.write;
  test.callbacks.write=async(...args)=>{await write(...args);test.controller.abort();};
  let error;try{await runAlignmentSearch(test.callbacks);}catch(cause){error=cause;}
  expect(error).toBeInstanceOf(AlignmentSearchStopped);expect(error.result.status).toBe('stopped');
  expect(test.writes).toHaveLength(1);
});

test('a failed current command stops with unknown outcome and is never retried',async()=>{
  const test=rig();test.callbacks.write=jest.fn(async()=>{throw new Error('SCPI timeout');});
  let error;try{await runAlignmentSearch(test.callbacks);}catch(cause){error=cause;}
  expect(error.result.uncertain).toBe(true);expect(error.result.status).toBe('failed');
  expect(test.callbacks.write).toHaveBeenCalledTimes(1);
});

test('external current changes, unsettled readbacks and missing fresh frames block further writes',async()=>{
  const external=rig();external.callbacks.read=async()=>external.callbacks.plan.channels.map((channel,index)=>({...channel,value:index===4?0.1:0}));
  await expect(runAlignmentSearch(external.callbacks)).rejects.toThrow(/outside this search/);
  expect(external.writes).toHaveLength(0);
  const unsettled=rig();unsettled.callbacks.read=async()=>unsettled.callbacks.plan.channels.map(channel=>({...channel,measured:0.02}));
  await expect(runAlignmentSearch(unsettled.callbacks)).rejects.toThrow(/did not settle/);
  expect(unsettled.writes).toHaveLength(0);
  const stale=rig();stale.callbacks.checkSignal=()=>{throw new Error('No fresh Alignment frames');};
  await expect(runAlignmentSearch(stale.callbacks)).rejects.toThrow(/fresh/);expect(stale.writes).toHaveLength(0);
});

test('too few frames do not supply a score to the optimizer',async()=>{
  const test=rig();test.callbacks.measure=()=>({mean:50,sd:0,n:1});
  await expect(runAlignmentSearch(test.callbacks)).rejects.toThrow(/Not enough fresh/);
  expect(test.writes).toHaveLength(0);
});
