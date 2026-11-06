import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import VD2AlignmentSearch from './VD2AlignmentSearch';
import {ALIGNMENT_CHANNELS,AlignmentSignalBuffer,runAlignmentSearch} from '../vd2AlignmentSearch';
import {fetchWithHardwareApproval} from '../api/csrfRequest';
import {captureAlignmentSnapshot,getAlignmentSnapshots} from '../api/vd2AlignmentPresets';

jest.mock('../vd2AlignmentSearch',()=>({...jest.requireActual('../vd2AlignmentSearch'),runAlignmentSearch:jest.fn()}));
jest.mock('../api/csrfRequest',()=>({fetchWithHardwareApproval:jest.fn()}));
jest.mock('../api/vd2AlignmentPresets',()=>({captureAlignmentSnapshot:jest.fn(),getAlignmentSnapshots:jest.fn()}));
const originalFetch=global.fetch;
const response=data=>({ok:true,json:async()=>data});
const native=()=>({success:true,ids:ALIGNMENT_CHANNELS.map((_,i)=>i+11),names:ALIGNMENT_CHANNELS,states:Array(8).fill(1),
  currents_setpoint:Array(8).fill(0),currents_meas:Array(8).fill(0),current_limits:Array(16).fill(0).map((_,i)=>i%2?15:-15)});
const props=()=>{
  const measurements=new AlignmentSignalBuffer();measurements.record('frame',20,'fixed-roi',Date.now());
  return {device:'ELYSE/pdu/iTest',measurements,live:true,onRunning:jest.fn()};
};
const snapshot=(kind='manual_best',value=0)=>({id:`${kind}-saved`,device:'ELYSE/pdu/iTest',kind,created_at:'2026-11-03T15:00:00Z',
  channels:ALIGNMENT_CHANNELS.map((name,index)=>({name,id:index+11,value,measured:value,min:-15,max:15}))});
beforeEach(()=>{
  global.fetch=jest.fn(async()=>response(native()));runAlignmentSearch.mockReset();fetchWithHardwareApproval.mockReset();
  getAlignmentSnapshots.mockReset();getAlignmentSnapshots.mockResolvedValue({best:null,previous:null,recommended:null});
  captureAlignmentSnapshot.mockReset();captureAlignmentSnapshot.mockImplementation(async args=>({...snapshot(args.kind),channels:args.channels,parent_id:args.parent_id}));
});
afterEach(()=>{global.fetch=originalFetch;});

test('render and reviewing all eight bounds never starts a search or writes hardware',async()=>{
  render(<VD2AlignmentSearch {...props()} />);
  expect(global.fetch).not.toHaveBeenCalled();
  expect(getAlignmentSnapshots).toHaveBeenCalledWith('ELYSE/pdu/iTest');
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Start search & apply best'})).toBeEnabled());
  expect(screen.getByText('T1-1')).toBeInTheDocument();expect(screen.getByText('Bcd2')).toBeInTheDocument();
  expect(runAlignmentSearch).not.toHaveBeenCalled();expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  expect(captureAlignmentSnapshot).not.toHaveBeenCalled();
});

test('a double submit starts one job; leaving the tab cancels that owner',async()=>{
  let resolve;
  runAlignmentSearch.mockImplementation(()=>new Promise(done=>{resolve=done;}));
  const view=render(<VD2AlignmentSearch {...props()} />);
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Start search & apply best'})).toBeEnabled());
  fireEvent.submit(screen.getByRole('form',{name:'Alignment search settings'}));
  fireEvent.submit(screen.getByRole('form',{name:'Alignment search settings'}));
  await waitFor(()=>expect(runAlignmentSearch).toHaveBeenCalledTimes(1));
  const call=runAlignmentSearch.mock.calls[0][0];view.unmount();expect(call.signal.aborted).toBe(true);
  await act(async()=>resolve({status:'stopped'}));
});

test('search writes the real slot ID through the existing authorized current route only',async()=>{
  fetchWithHardwareApproval.mockResolvedValue(response({success:true,slot_id:13,current_setpoint:0.05}));
  runAlignmentSearch.mockImplementation(async callbacks=>{
    await callbacks.write(13,0.05);
    return {status:'completed',measurements:1,history:[],best:{position:Array(8).fill(0),mean:20,sd:0.2,n:15}};
  });
  render(<VD2AlignmentSearch {...props()} />);
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Start search & apply best'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  await screen.findByText(/completed.*1 points/);
  expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1);
  expect(fetchWithHardwareApproval.mock.calls[0][0]).toBe('/api/device/ds_itest_psu/ELYSE/pdu/iTest/slot/13/current');
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({current:0.05});
});

async function reviewed() {
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Start search & apply best'})).toBeEnabled());
}

test('DB failure before baseline capture blocks the engine and all hardware writes',async()=>{
  captureAlignmentSnapshot.mockRejectedValue(new Error('Database full'));
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Database full');
  expect(runAlignmentSearch).not.toHaveBeenCalled();expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('durable before-search snapshot precedes engine; only completed best is saved with statistics',async()=>{
  const order=[];
  captureAlignmentSnapshot.mockImplementation(async args=>{order.push(args.kind);return {...snapshot(args.kind),channels:args.channels};});
  runAlignmentSearch.mockImplementation(async()=>{order.push('engine');return {status:'completed',best:{position:Array(8).fill(0),mean:25,sd:0.4,n:15}};});
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  await screen.findByText(/Completed best saved/);
  expect(order).toEqual(['before_search','engine','search_best']);
  expect(captureAlignmentSnapshot.mock.calls[1][0]).toMatchObject({parent_id:'before_search-saved',quality:{mean:25,sd:0.4,n:15}});
});

test.each(['failed','stopped'])('%s search keeps previous best and exposes its durable return point',async status=>{
  const best=snapshot();getAlignmentSnapshots.mockResolvedValue({best,recommended:best});
  runAlignmentSearch.mockRejectedValue(Object.assign(new Error('Stopped on failure'),{result:{status}}));
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  await screen.findByRole('alert');
  expect(captureAlignmentSnapshot.mock.calls.map(call=>call[0].kind)).toEqual(['before_search']);
  expect(screen.getByText(/Operator-saved best/)).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Before last search'})).toBeEnabled();
});

test('a saved baseline fallback is labeled honestly and requires a restore/current decision before writes',async()=>{
  const previous=snapshot('before_search',0.05);getAlignmentSnapshots.mockResolvedValue({previous,recommended:previous});
  runAlignmentSearch.mockResolvedValue({status:'stopped'});
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  const choice=await screen.findByRole('group',{name:'Restore before search'});
  expect(choice).toHaveTextContent('not a verified best');
  expect(runAlignmentSearch).not.toHaveBeenCalled();expect(captureAlignmentSnapshot).not.toHaveBeenCalled();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Search from current settings'}));
  await waitFor(()=>expect(runAlignmentSearch).toHaveBeenCalledTimes(1));
  expect(captureAlignmentSnapshot.mock.calls.map(call=>call[0].kind)).toEqual(['before_search']);
});

test('Save as best is explicit, persists all eight currents and does not write hardware',async()=>{
  render(<VD2AlignmentSearch {...props()} />);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Save as best'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Save as best'}));
  await screen.findByText(/Saved best ·/);
  expect(captureAlignmentSnapshot).toHaveBeenCalledWith(expect.objectContaining({kind:'manual_best',device:'ELYSE/pdu/iTest',channels:expect.any(Array)}));
  expect(captureAlignmentSnapshot.mock.calls[0][0].channels).toHaveLength(8);
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('an older running Web process cannot enable search or saving until the DB route is loaded',async()=>{
  getAlignmentSnapshots.mockResolvedValue({available:false,best:null,recommended:null,history:[]});
  render(<VD2AlignmentSearch {...props()} />);
  await screen.findByText('Saved-current presets need Web reload.');
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Review currents'})).toBeEnabled());
  expect(screen.getByRole('button',{name:'Start search & apply best'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Save as best'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Restore saved…'})).toBeDisabled();
  expect(runAlignmentSearch).not.toHaveBeenCalled();expect(captureAlignmentSnapshot).not.toHaveBeenCalled();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('restoration needs review and durable before-restore snapshot; DB failure prevents all writes',async()=>{
  const best=snapshot('manual_best',0.05);getAlignmentSnapshots.mockResolvedValue({best,recommended:best});
  render(<VD2AlignmentSearch {...props()} />);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Restore saved…'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Restore saved…'}));
  const button=await screen.findByRole('button',{name:'Restore these 8 currents'});
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();expect(captureAlignmentSnapshot).not.toHaveBeenCalled();
  captureAlignmentSnapshot.mockRejectedValue(new Error('Database read only'));
  fireEvent.click(button);
  expect(await screen.findByRole('alert')).toHaveTextContent('Database read only');
  expect(captureAlignmentSnapshot.mock.calls[0][0]).toMatchObject({kind:'before_restore',parent_id:best.id});
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('restored target uses actual slot IDs and verified native readback',async()=>{
  const best=snapshot('manual_best',0.05),data=native();getAlignmentSnapshots.mockResolvedValue({best,recommended:best});
  const order=[];
  global.fetch.mockImplementation(async()=>response(data));
  captureAlignmentSnapshot.mockImplementation(async args=>{order.push(args.kind);return {...snapshot(args.kind),channels:args.channels};});
  fetchWithHardwareApproval.mockImplementation(async(url,options)=>{
    const id=Number(url.match(/slot\/(\d+)/)[1]),value=JSON.parse(options.body).current;
    order.push(id);const index=data.ids.indexOf(id);data.currents_setpoint[index]=value;data.currents_meas[index]=value;
    return response({success:true,slot_id:id,current_setpoint:value});
  });
  render(<VD2AlignmentSearch {...props()} />);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Restore saved…'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Restore saved…'}));
  fireEvent.click(await screen.findByRole('button',{name:'Restore these 8 currents'}));
  await screen.findByText(/Restored · Operator-saved best/);
  expect(order).toEqual(['before_restore',11,12,13,14,15,16,17,18]);
  expect(runAlignmentSearch).not.toHaveBeenCalled();
});

test('restore before search saves the pre-restore state, restores all eight, then records the new search origin',async()=>{
  const best=snapshot('manual_best',0.05),data=native(),order=[];
  getAlignmentSnapshots.mockResolvedValue({best,recommended:best});
  global.fetch.mockImplementation(async()=>response(data));
  captureAlignmentSnapshot.mockImplementation(async args=>{order.push([args.kind,args.channels[0].value]);return {...snapshot(args.kind),channels:args.channels};});
  fetchWithHardwareApproval.mockImplementation(async(url,options)=>{
    const id=Number(url.match(/slot\/(\d+)/)[1]),value=JSON.parse(options.body).current,index=data.ids.indexOf(id);
    order.push(['write',id]);data.currents_setpoint[index]=value;data.currents_meas[index]=value;
    return response({success:true,slot_id:id,current_setpoint:value});
  });
  runAlignmentSearch.mockImplementation(async callbacks=>{order.push(['engine',callbacks.plan.start[0]]);return {status:'stopped'};});
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  fireEvent.click(await screen.findByRole('button',{name:'Restore then search'}));
  await waitFor(()=>expect(runAlignmentSearch).toHaveBeenCalledTimes(1));
  expect(order[0]).toEqual(['before_restore',0]);
  expect(order.slice(1,9)).toEqual(data.ids.map(id=>['write',id]));
  expect(order.slice(9)).toEqual([['before_search',0.05],['engine',0.05]]);
  expect(runAlignmentSearch.mock.calls[0][0].plan.bounds[0][0]).toBeCloseTo(0,9);
  expect(runAlignmentSearch.mock.calls[0][0].plan.bounds[0][1]).toBeCloseTo(0.1,9);
});

test('an incompatible historical target can be skipped explicitly without being written',async()=>{
  const best=snapshot('manual_best',20);getAlignmentSnapshots.mockResolvedValue({best,recommended:best});
  runAlignmentSearch.mockResolvedValue({status:'stopped'});
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  const button=await screen.findByRole('button',{name:'Restore then search'});
  expect(button).toBeDisabled();expect(screen.getByRole('alert')).toHaveTextContent('native limits');
  fireEvent.click(screen.getByRole('button',{name:'Search from current settings'}));
  await waitFor(()=>expect(runAlignmentSearch).toHaveBeenCalledTimes(1));
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  expect(captureAlignmentSnapshot.mock.calls.map(call=>call[0].kind)).toEqual(['before_search']);
});

test('failure to persist completed best retains completed result and reports the persistence error',async()=>{
  captureAlignmentSnapshot.mockImplementation(async args=>{
    if(args.kind==='search_best')throw new Error('disk full');
    return {...snapshot(args.kind),channels:args.channels};
  });
  runAlignmentSearch.mockResolvedValue({status:'completed',best:{position:Array(8).fill(0),mean:25,sd:0.2,n:15}});
  render(<VD2AlignmentSearch {...props()} />);await reviewed();
  fireEvent.click(screen.getByRole('button',{name:'Start search & apply best'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Previous saved best is preserved');
  expect(screen.getByText('completed')).toBeInTheDocument();
});

test('an output that is OFF prevents approval of the plan and is never turned on',async()=>{
  const data=native();data.states[3]=0;global.fetch.mockResolvedValue(response(data));
  render(<VD2AlignmentSearch {...props()} />);
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}));
  expect(await screen.findByRole('alert')).toHaveTextContent('V1 output is not ON');
  expect(screen.getByRole('button',{name:'Start search & apply best'})).toBeDisabled();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});
