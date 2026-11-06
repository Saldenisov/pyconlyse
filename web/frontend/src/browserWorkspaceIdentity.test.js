import { claimWindowNamespace, windowNamespace } from './browserWorkspaceIdentity';
import { readWorkspaces, saveWorkspaces } from './treatmentWorkspaces';

const memory=()=>{const entries=new Map();return {getItem:key=>entries.get(key)||null,setItem:(key,value)=>entries.set(key,value)};};

test('window identity persists on reload and differs between independent windows',async()=>{
  const first=memory(),second=memory();
  expect(await claimWindowNamespace(first,null)).toBe(windowNamespace(first));
  expect(windowNamespace(first)).not.toBe(windowNamespace(second));
});

test('duplicate-tab detection forks inherited identity before restoring or saving',async()=>{
  jest.useFakeTimers();
  const channels=[];
  class Channel {
    constructor(){channels.push(this);}
    postMessage(data){channels.filter(item=>item!==this).forEach(item=>item.onmessage?.({data}));}
    close(){}
  }
  try{
    const storage=memory();const first=claimWindowNamespace(storage,Channel);
    jest.advanceTimersByTime(80);const original=await first;
    const duplicate=memory();duplicate.setItem('pyconlyse.workspace.window.v1',original);
    const second=claimWindowNamespace(duplicate,Channel);
    jest.advanceTimersByTime(80);
    expect(await second).not.toBe(original);
    expect(windowNamespace(storage)).toBe(original);
  }finally{jest.useRealTimers();}
});

test('workspace menus stay separate per window and survive reload',()=>{
  window.localStorage.clear();
  saveWorkspaces('VD2',{active:'one',items:[{id:'one',label:'Water'}]},'window-one');
  saveWorkspaces('VD2',{active:'two',items:[{id:'two',label:'Another sample'}]},'window-two');
  expect(readWorkspaces('VD2','window-one').active).toBe('one');
  expect(readWorkspaces('VD2','window-two').active).toBe('two');
  expect(readWorkspaces('VD2','window-new').active).toBe('main');
});
