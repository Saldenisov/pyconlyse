import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import DataTreatment from './DataTreatment';

jest.mock('./browserWorkspaceIdentity',()=>({...jest.requireActual('./browserWorkspaceIdentity'),useWindowNamespace:()=> 'window-for-tests'}));
jest.mock('./api/treatmentClient',()=>({...jest.requireActual('./api/treatmentClient'),fetchTreatmentQueue:jest.fn()}));
jest.mock('./DataWindowVD2', () => {
  const React = require('react');
  return {__esModule:true,buildTreatmentSessionId:(profile,workspace,windowId)=>`browser:test-browser:window:${windowId}:profile:${profile.toLowerCase()}:workspace:${workspace}`,
    default:function MockWindow({ profile, layoutMode, workspace, initialFolder }) {
      return React.createElement('div', { 'data-testid': 'treatment-window', 'data-profile': profile,
        'data-layout-mode': layoutMode, 'data-workspace': workspace, 'data-folder': initialFolder });
    }};
});

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, '', '/datatreatment');
});

test('Studio is the only layout, including an old Classic preference', () => {
  window.localStorage.setItem('pyconlyse.treatment.layoutMode', 'classic');
  render(<DataTreatment />);
  expect(screen.queryByRole('button', { name: 'Classic' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Studio' })).not.toBeInTheDocument();
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'studio');
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-workspace', 'main');
  fireEvent.click(screen.getByRole('button', { name: 'V0 legacy' }));
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-profile', 'V0');
});

test('workspaces switch independently and persist across reload', () => {
  const { unmount } = render(<DataTreatment />);
  fireEvent.click(screen.getByRole('button', { name: 'New workspace' }));
  const second = screen.getByTestId('treatment-window').getAttribute('data-workspace');
  expect(second).not.toBe('main');
  fireEvent.change(screen.getByLabelText('Workspace'), { target: { value: 'main' } });
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-workspace', 'main');
  fireEvent.change(screen.getByLabelText('Workspace'), { target: { value: second } });
  unmount();
  render(<DataTreatment />);
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-workspace', second);
  fireEvent.click(screen.getByRole('button', { name: 'V0 legacy' }));
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-workspace', 'main');
});

test('measurement folder opens a separate VD2 workspace and preserves main', () => {
  window.localStorage.setItem('pyconlyse.treatment.activeProfile', 'V0');
  const folder = 'E:\\DATA_VD2\\2026\\test & space';
  window.history.replaceState({}, '', `/datatreatment?${new URLSearchParams({ profile: 'VD2', folder })}`);
  const { unmount } = render(<DataTreatment />);
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-profile', 'VD2');
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-folder', folder);
  expect(screen.getByTestId('treatment-window').getAttribute('data-workspace')).toMatch(/^folder-/);
  expect(screen.getAllByRole('option')).toHaveLength(2);
  unmount();
  render(<DataTreatment />);
  expect(screen.getAllByRole('option')).toHaveLength(2);
  fireEvent.change(screen.getByLabelText('Workspace'), { target: { value: 'main' } });
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-folder', '');
});

test('restoring server treatment creates a new independent workspace and never starts a queue',async()=>{
  const previousFetch=global.fetch;
  global.fetch=jest.fn(async(url)=>({ok:true,json:async()=>url.endsWith('/saved')
    ?{success:true,sessions:[{session_id:'old-owned-session',name:'water.dat',folder:'E:\\DATA_VD2\\water',updated_at:'2026-11-03T16:00:00Z'}]}
    :{success:true,restored:true}}));
  try{
    render(<DataTreatment/>);
    expect(global.fetch.mock.calls.some(([,options])=>options.method==='POST')).toBe(false);
    fireEvent.click(screen.getByRole('button',{name:'Restore session',exact:true}));
    const dialog=await screen.findByRole('dialog');
    fireEvent.click(await within(dialog).findByRole('button',{name:/water.dat/}));
    await waitFor(()=>expect(screen.getByTestId('treatment-window').getAttribute('data-workspace')).toMatch(/^restored-/));
    const [url,options]=global.fetch.mock.calls.find(([path])=>path.endsWith('/session/copy'));
    expect(url).toBe('/api/treatment/session/copy');
    expect(options.headers['X-Treatment-Session-Id']).toContain(':workspace:restored-');
    expect(JSON.parse(options.body)).toEqual({source_session_id:'old-owned-session'});
    expect(global.fetch.mock.calls.some(([path,request])=>path.includes('/queue')&&request.method==='POST')).toBe(false);
    fireEvent.change(screen.getByLabelText('Workspace'),{target:{value:'main'}});
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-workspace','main');
  }finally{global.fetch=previousFetch;}
});

test('opening a manifest selects its project folder in this window and persists it across reload',async()=>{
  const previousFetch=global.fetch;
  const folder='E:\\DATA_VD2\\20261103',manifest=`${folder}\\vd2-manifest.json`;
  global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('/manifest/vd2')
    ?{success:true,manifest:{manifest_path:manifest,project_folder:folder,samples:[]}}
    :{success:true,queue:{running:false,pending_count:0,jobs:[]}}}));
  window.history.replaceState({},'',`/datatreatment?${new URLSearchParams({manifest:`"${manifest}"`})}`);
  try{
    const first=render(<DataTreatment/>);
    await waitFor(()=>expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-folder',folder));
    expect(screen.getByTestId('treatment-window').getAttribute('data-workspace')).toMatch(/^manifest-/);
    first.unmount();window.history.replaceState({},'','/datatreatment');
    render(<DataTreatment/>);
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-folder',folder);
    expect(screen.queryByRole('textbox',{name:'Manifest JSON path'})).not.toBeInTheDocument();
    expect(screen.queryByText('VD2 project manifest')).not.toBeInTheDocument();
    expect(global.fetch.mock.calls.some(([path])=>path==='/api/treatment/session/root')).toBe(false);
  }finally{global.fetch=previousFetch;}
});

test('closing a workspace selects its neighbour, persists, and keeps the final workspace', () => {
  const view = render(<DataTreatment />);
  expect(screen.getByRole('button', { name: 'Close workspace' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'New workspace' }));
  expect(screen.getAllByRole('option')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Close workspace' }));
  expect(screen.getAllByRole('option')).toHaveLength(1);
  expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-workspace', 'main');
  view.unmount(); render(<DataTreatment />);
  expect(screen.getAllByRole('option')).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Close workspace' })).toBeDisabled();
});
