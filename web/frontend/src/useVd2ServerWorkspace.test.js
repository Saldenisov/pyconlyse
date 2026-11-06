import React, { useState } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import useVd2ServerWorkspace from './useVd2ServerWorkspace';
import VD2FolderPicker from './components/VD2FolderPicker';
import ServerSessionPicker from './components/ServerSessionPicker';

jest.mock('./browserWorkspaceIdentity',()=>({...jest.requireActual('./browserWorkspaceIdentity'),useWindowNamespace:()=> 'window-test-12345'}));
const originalFetch=global.fetch;
const defaults={outputRoot:'E:\\DATA_VD2',runName:'new',framesPerHis:'10',sampleDescription:'',reuseBruit:'latest'};
const saved={...defaults,outputRoot:'E:\\DATA_VD2\\2026\\water',runName:'water',framesPerHis:'40',sampleDescription:'notes'};
const ok=value=>({ok:true,json:async()=>({success:true,...value})});
function Harness(){const [settings,setSettings]=useState(defaults);const workspace=useVd2ServerWorkspace(settings,setSettings);
  return <><input aria-label="Sample" disabled={!workspace.ready} value={settings.runName} onChange={event=>setSettings({...settings,runName:event.target.value})}/>
    <output>{settings.outputRoot} · {settings.framesPerHis}</output><p role="alert">{workspace.error}</p>
    <ServerSessionPicker load={workspace.history} onRestore={workspace.restore}/></>;
}
beforeEach(()=>{window.localStorage.setItem('pyconlyse_treatment_namespace','browser-test-12345');global.fetch=jest.fn();});
afterEach(()=>{global.fetch=originalFetch;jest.useRealTimers();});

test('reload hydrates this window from server before enabling edits or writing defaults',async()=>{
  let finish;
  global.fetch.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<Harness/>);
  expect(screen.getByLabelText('Sample')).toBeDisabled();
  await act(async()=>finish(ok({workspace:{revision:3,settings:saved}})));
  expect(screen.getByLabelText('Sample')).toHaveValue('water');
  expect(screen.getByLabelText('Sample')).toBeEnabled();
  expect(screen.getByRole('status')).toHaveTextContent('40');
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.fetch.mock.calls[0][1].headers).toMatchObject({'X-Workspace-Browser':'browser-test-12345','X-Workspace-Window':'window-test-12345'});
  view.unmount();
});

test('autosave coalesces rapid edits and serializes updates behind a slow request',async()=>{
  jest.useFakeTimers();let release;
  global.fetch.mockResolvedValueOnce(ok({workspace:{revision:5,settings:saved}}))
    .mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}))
    .mockResolvedValueOnce(ok({workspace:{revision:7}}));
  const view=render(<Harness/>);
  await act(async()=>{});
  fireEvent.change(screen.getByLabelText('Sample'),{target:{value:'first'}});
  await act(async()=>{jest.advanceTimersByTime(500);});
  fireEvent.change(screen.getByLabelText('Sample'),{target:{value:'latest'}});
  await act(async()=>{jest.advanceTimersByTime(500);});
  expect(global.fetch).toHaveBeenCalledTimes(2);
  await act(async()=>release(ok({workspace:{revision:6}})));
  expect(global.fetch).toHaveBeenCalledTimes(3);
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toMatchObject({revision:5,settings:{runName:'first'}});
  expect(JSON.parse(global.fetch.mock.calls[2][1].body)).toMatchObject({revision:6,settings:{runName:'latest'}});
  expect(global.fetch.mock.calls.every(([url])=>url.includes('/workspace'))).toBe(true);
  view.unmount();
});

test('navigation flushes the last draft behind an in-flight save without sending stale revisions',async()=>{
  jest.useFakeTimers();let release;
  global.fetch.mockResolvedValueOnce(ok({workspace:{revision:1,settings:saved}}))
    .mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}))
    .mockResolvedValueOnce(ok({workspace:{revision:3}}));
  const view=render(<Harness/>);await act(async()=>{});
  fireEvent.change(screen.getByLabelText('Sample'),{target:{value:'first'}});
  await act(async()=>{jest.advanceTimersByTime(500);});
  fireEvent.change(screen.getByLabelText('Sample'),{target:{value:'last draft'}});
  view.unmount();
  await act(async()=>release(ok({workspace:{revision:2}})));
  expect(JSON.parse(global.fetch.mock.calls[2][1].body)).toMatchObject({revision:2,settings:{runName:'last draft'}});
  expect(global.fetch.mock.calls[2][1].keepalive).toBe(true);
});

test('server failure leaves a visible warning and never overwrites an unknown revision',async()=>{
  global.fetch.mockRejectedValue(new Error('Network unavailable'));
  const view=render(<Harness/>);
  await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Network unavailable'));
  expect(screen.getByLabelText('Sample')).toBeEnabled();
  fireEvent.change(screen.getByLabelText('Sample'),{target:{value:'offline draft'}});
  await act(async()=>new Promise(resolve=>setTimeout(resolve,550)));
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('Sample')).toHaveValue('offline draft');
  view.unmount();
});

test('explicit server restore replaces only the form, never sends camera commands',async()=>{
  global.fetch.mockImplementation(async url=>url.endsWith('/history')?ok({workspaces:[{window_id:'older-window',settings:saved,updated_at:'2026-11-03T16:00:00Z'}]}):ok({workspace:null}));
  const view=render(<Harness/>);
  await waitFor(()=>expect(screen.getByLabelText('Sample')).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Restore session',exact:true}));
  const dialog=await screen.findByRole('dialog');
  fireEvent.click(await within(dialog).findByRole('button',{name:/water.*2026/}));
  await waitFor(()=>expect(screen.getByLabelText('Sample')).toHaveValue('water'));
  expect(global.fetch.mock.calls.every(([url])=>url.includes('/workspace'))).toBe(true);
  view.unmount();
});

test('folder button is inside the path control and selects a server directory without acquisition',async()=>{
  const change=jest.fn();
  global.fetch.mockImplementation(async url=>ok({folder:url.includes('folder=child')?'child':'E:\\DATA_VD2',parent:null,folders:[{name:'2026',path:'child'}]}));
  const view=render(<VD2FolderPicker value="E:\\DATA_VD2" onChange={change}/>);
  expect(screen.getByLabelText('Browse Everest folder').parentElement).toBe(screen.getByRole('textbox',{name:'Everest folder'}).parentElement);
  fireEvent.click(screen.getByLabelText('Browse Everest folder'));
  const dialog=await screen.findByRole('dialog',{name:'Choose Everest folder'});
  fireEvent.click(await within(dialog).findByRole('button',{name:/2026/}));
  await waitFor(()=>expect(within(dialog).getByRole('textbox')).toHaveValue('child'));
  fireEvent.click(within(dialog).getByRole('button',{name:'Use this folder'}));
  expect(change).toHaveBeenCalledWith('child');
  expect(global.fetch.mock.calls.every(([url,options])=>url.includes('/protocol/folders?')&&!options.method)).toBe(true);
  view.unmount();
});

test('manifest chooser lists server JSON files and returns a clean absolute path',async()=>{
  const selected=jest.fn(),path='E:\\DATA_VD2\\20261103\\vd2-manifest.json';
  global.fetch.mockResolvedValue(ok({folder:'E:\\DATA_VD2\\20261103',folders:[],files:[{name:'vd2-manifest.json',path}],parent:'E:\\DATA_VD2'}));
  render(<VD2FolderPicker kind="manifest" value={`"${path}"`} onChange={jest.fn()} onChoose={selected}/>);
  fireEvent.click(screen.getByRole('button',{name:'Browse manifest JSON'}));
  const dialog=await screen.findByRole('dialog',{name:'Choose manifest JSON'});
  fireEvent.click(await within(dialog).findByRole('button',{name:/vd2-manifest.json/}));
  expect(selected).toHaveBeenCalledWith(path);
  expect(global.fetch.mock.calls[0][0]).toContain('kind=manifest');
  expect(global.fetch.mock.calls[0][0]).not.toContain('%22');
});
