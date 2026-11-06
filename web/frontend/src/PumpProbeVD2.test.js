import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import PumpProbeVD2, { EditableField, fetchVd2, refreshVd2Passive, TIME_RANGES, Vd2PhaseProtocol } from './PumpProbeVD2';

jest.mock('./useVd2ServerWorkspace',()=>({...jest.requireActual('./useVd2ServerWorkspace'),__esModule:true,
  default:()=>({ready:true,message:'Session saved on server.',error:'',history:async()=>[],restore:async()=>{}})}));

const originalFetch = global.fetch;
beforeEach(()=>window.localStorage.clear());

test('project manifest and earlier measurements open separately and preserve acquisition context',()=>{
  const onChange=jest.fn(),manifest='E:\\DATA_VD2\\20261103\\vd2-manifest.json';
  render(<Vd2PhaseProtocol settings={{framesPerHis:'10',outputRoot:'E:\\DATA_VD2\\20261103',runName:'next'}}
    protocol={{status:'completed',his_path:'E:\\DATA_VD2\\20261103\\water\\ABS.his',manifest_path:manifest}}
    project={{manifest_path:manifest,samples:[{name:'water',ready:true,measurements:[{id:'old',phase:'ABSORPTION',status:'completed',frames:20,selected:true}]}]}}
    onChange={onChange} onPhaseClick={jest.fn()} onPhaseDoubleClick={jest.fn()}/>);
  fireEvent.click(screen.getByText('Previous measurements · 1 samples'));
  for(const name of ['Project manifest ↗','Run folder ↗','View in Data Treatment ↗']){
    const link=screen.getByRole('link',{name});expect(link).toHaveAttribute('target','_blank');expect(link).toHaveAttribute('rel','noopener noreferrer');
  }
  expect(screen.getByText('Previous measurements · 1 samples')).toBeInTheDocument();
  expect(screen.getByText(/completed · 20 frames/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'water',exact:true}));
  expect(onChange).toHaveBeenCalledWith('runName','water');
});

test('processing queue leaves next phase and settings usable and preserves older conversion errors',()=>{
  const jobs=[{job_id:'old',sample_name:'older',phase:'BRUIT',status:'failed',error:'Conversion disk error'},
    {job_id:'new',sample_name:'dark',phase:'BASE',status:'processing'}];
  render(<Vd2PhaseProtocol settings={{framesPerHis:'10',outputRoot:'C:\\test',runName:'dark'}}
    onChange={jest.fn()} onPhaseClick={jest.fn()} onPhaseDoubleClick={jest.fn()}
    protocol={{status:'processing',acquisition_active:false,acquisition_phase:'idle',processing_jobs:jobs}} />);
  expect(screen.getByRole('button',{name:'Absorption',exact:true})).toBeEnabled();
  expect(screen.getByRole('textbox',{name:'Sample name'})).toBeEnabled();
  expect(screen.getByRole('alert')).toHaveTextContent('older · BRUIT: Conversion disk error');
  expect(screen.getByLabelText('H5 conversion queue')).toHaveTextContent('dark · BASE converting');
});

test('per-sample Bruit already saved to the queue allows Base before its H5 is ready',()=>{
  render(<Vd2PhaseProtocol settings={{framesPerHis:'10',outputRoot:'C:\\test',runName:'dark',reuseBruit:'none'}}
    onChange={jest.fn()} onPhaseClick={jest.fn()} onPhaseDoubleClick={jest.fn()}
    protocol={{status:'processing',acquisition_active:false,acquisition_phase:'idle'}}
    project={{samples:[{name:'dark',bruit_reference:'saved-noise'}],bruit_options:[{id:'saved-noise',sample:'dark',status:'processing'}]}} />);
  expect(screen.getByRole('button',{name:'Base',exact:true})).toBeEnabled();
  expect(screen.getByRole('button',{name:'Absorption',exact:true})).toBeEnabled();
});

test('a full conversion queue blocks only new phase submissions',()=>{
  render(<Vd2PhaseProtocol settings={{framesPerHis:'10',outputRoot:'C:\\test',runName:'dark'}}
    onChange={jest.fn()} onPhaseClick={jest.fn()} onPhaseDoubleClick={jest.fn()}
    protocol={{status:'processing',acquisition_active:false,acquisition_phase:'idle',queue_full:true}} />);
  expect(screen.getByRole('button',{name:'Absorption',exact:true})).toBeDisabled();
  expect(screen.getByRole('textbox',{name:'Sample name'})).toBeEnabled();
  expect(screen.getByRole('status')).toHaveTextContent('queue is full');
});

function repeatFixture() {
  global.fetch=jest.fn(async(url,options)=>{
    let payload={success:true,status:'idle',devices:[]};
    if(url==='/api/pump-probe-vd2/state')payload={success:true,state:'ON',connected:true,application_running:true,acquisition_status:'idle',remoteex_status:'idle',values:{}};
    if(url.endsWith('/preview'))payload={success:true,frame_available:false,stream_state:'no_valid_image'};
    if(url.endsWith('/protocol/plan'))payload={success:true,conflict:true,choices:{replace:{token:'replace-quote',run_name:'water'},new_folder:{token:'new-folder-quote',run_name:'water_2'}}};
    if(url.endsWith('/protocol/start'))payload={success:true,status:'acquiring',phase:'ABSORPTION',sample_name:JSON.parse(options.body).destination_token==='new-folder-quote'?'water_2':'water'};
    return {ok:true,json:async()=>payload};
  });
}
async function openRepeat() {
  await waitFor(()=>expect(screen.getByRole('button',{name:'Absorption',exact:true})).toBeEnabled());
  fireEvent.change(screen.getByRole('textbox',{name:'Sample name',exact:true}),{target:{value:'water'}});
  fireEvent.change(screen.getByRole('spinbutton',{name:'Frames / HIS',exact:true}),{target:{value:'20'}});
  fireEvent.doubleClick(screen.getByRole('button',{name:'Absorption',exact:true}));
  return screen.findByRole('dialog',{name:'Repeat Absorption'});
}

test('Acquisition shows averaging then 100 Frames / HIS; timing controls stay in Hardware setup', async () => {
  repeatFixture();
  const view = render(<PumpProbeVD2 />);
  try {
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'Frames / HIS' })).toBeEnabled());
    const frames = screen.getByRole('spinbutton', { name: 'Frames / HIS' });
    expect(frames).toHaveValue(100);
    expect(screen.getByRole('checkbox', { name: 'Rolling average' }).compareDocumentPosition(frames) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    for (const name of ['Live exposure', 'Acquire exposure', 'Integrations', 'Sequence loops']) {
      expect(screen.queryByLabelText(name)).not.toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole('tab', { name: 'Hardware setup' }));
    for (const name of ['Live exposure', 'Acquire exposure', 'Integrations', 'Sequence loops']) {
      expect(screen.getByLabelText(name)).toBeInTheDocument();
    }
    expect(screen.getByLabelText('Live exposure')).toHaveAttribute('min', '1');
    expect(global.fetch.mock.calls.some(([url]) => url.includes('/parameter') || url.includes('/command'))).toBe(false);
  } finally { view.unmount(); global.fetch = originalFetch; }
});

test('repeat dialog and Cancel never start acquisition or alter the folder',async()=>{
  repeatFixture();const view=render(<PumpProbeVD2 />);
  try {
    const dialog=await openRepeat();
    expect(dialog).toHaveTextContent('water · 20 frames');
    expect(screen.getByRole('button',{name:'Overwrite Absorption'})).toHaveFocus();
    expect(screen.getByRole('spinbutton',{name:'Frames / HIS'})).toBeDisabled();
    expect(global.fetch.mock.calls.some(([url])=>url.endsWith('/protocol/start'))).toBe(false);
    fireEvent.keyDown(document,{key:'Escape'});
    expect(screen.queryByRole('dialog',{name:'Repeat Absorption'})).not.toBeInTheDocument();
    expect(screen.getByRole('textbox',{name:'Sample name'})).toHaveValue('water');
    expect(global.fetch.mock.calls.some(([url])=>url.endsWith('/protocol/start'))).toBe(false);
  } finally {view.unmount();global.fetch=originalFetch;}
});

test.each([['Overwrite Absorption','replace-quote','water'],['New folder: water_2','new-folder-quote','water_2']])('%s sends the reviewed choice once with the corrected frame count',async(label,token,name)=>{
  repeatFixture();const view=render(<PumpProbeVD2 />);
  try {
    await openRepeat();
    const button=screen.getByRole('button',{name:label});
    fireEvent.click(button);fireEvent.click(button);
    await waitFor(()=>expect(screen.queryByRole('dialog',{name:'Repeat Absorption'})).not.toBeInTheDocument());
    const calls=global.fetch.mock.calls.filter(([url])=>url.endsWith('/protocol/start'));
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0][1].body)).toMatchObject({phase:'ABSORPTION',frames_per_his:'20',run_name:'water',destination_token:token});
    expect(screen.getByRole('textbox',{name:'Sample name'})).toHaveValue(name);
  } finally {view.unmount();global.fetch=originalFetch;}
});

test('missing destination review on an old Web process fails before any acquisition request',async()=>{
  repeatFixture();const normal=global.fetch.getMockImplementation();
  global.fetch.mockImplementation(async(url,options)=>url.endsWith('/protocol/plan')?{ok:false,status:404}:normal(url,options));
  const view=render(<PumpProbeVD2 />);
  try {
    await waitFor(()=>expect(screen.getByRole('button',{name:'Absorption',exact:true})).toBeEnabled());
    fireEvent.doubleClick(screen.getByRole('button',{name:'Absorption',exact:true}));
    await screen.findByText('Measurement overwrite options need Web reload. No acquisition was started.');
    expect(global.fetch.mock.calls.filter(([url])=>url.endsWith('/protocol/start'))).toHaveLength(0);
  } finally {view.unmount();global.fetch=originalFetch;}
});

test('leaving the page during the passive folder review cannot start a late acquisition',async()=>{
  repeatFixture();const normal=global.fetch.getMockImplementation();let finish;
  global.fetch.mockImplementation(async(url,options)=>url.endsWith('/protocol/plan')?new Promise(resolve=>{finish=resolve;}):normal(url,options));
  const view=render(<PumpProbeVD2 />);
  try {
    await waitFor(()=>expect(screen.getByRole('button',{name:'Absorption',exact:true})).toBeEnabled());
    fireEvent.doubleClick(screen.getByRole('button',{name:'Absorption',exact:true}));
    await waitFor(()=>expect(finish).toBeDefined());view.unmount();
    await act(async()=>finish({ok:true,json:async()=>({success:true,conflict:false,choices:{record:{token:'record',run_name:'water'}}})}));
    expect(global.fetch.mock.calls.some(([url])=>url.endsWith('/protocol/start'))).toBe(false);
  } finally {view.unmount();global.fetch=originalFetch;}
});

test('Acquisition ROI movement and Clear persist after page remount',async()=>{
  const key='pyconlyse.vd2.acquisition.rois.v1:12x12';
  window.localStorage.setItem(key,JSON.stringify({version:1,value:[{id:'roi-1',type:'rectangle',x0:3,x1:6,y0:2,y1:8}]}));
  const canvas=jest.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({createImageData:()=>({data:new Uint8ClampedArray(576)}),putImageData:jest.fn()});
  global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('/preview')
    ?{success:true,frame_available:true,width:12,height:12,pixels_b64:window.btoa('\0'.repeat(144)),received_at:'frame'}
    :url==='/api/pump-probe-vd2/state'?{success:true,state:'ON',connected:true,application_running:true,acquisition_status:'idle',values:{}}
      :{success:true,status:'idle',devices:[]}}));
  const view=render(<PumpProbeVD2 />);
  try {
    fireEvent.keyDown(await screen.findByRole('button',{name:'Move Both ROI 1'}),{key:'ArrowRight'});
    expect(JSON.parse(window.localStorage.getItem(key)).value[0]).toMatchObject({x0:4,x1:7});
    view.unmount();
    const utils=render(<PumpProbeVD2 />);
    const region=await screen.findByRole('button',{name:'Move Both ROI 1'});
    expect(region).toHaveAttribute('x','4');expect(region).toHaveAttribute('width','4');
    fireEvent.click(screen.getByRole('button',{name:'Clear',exact:true}));
    expect(JSON.parse(window.localStorage.getItem(key)).value).toEqual([]);
    expect(global.fetch.mock.calls.every(([,options])=>!options?.method||options.method==='GET')).toBe(true);
    utils.unmount();
  } finally {view.unmount();canvas.mockRestore();global.fetch=originalFetch;}
});

test('Alignment ROI survives page remount without camera or magnet writes',async()=>{
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({success:true,status:'idle',devices:[]})}));
  const view=render(<PumpProbeVD2 />);
  try {
    fireEvent.click(screen.getByRole('tab',{name:'Alignment',exact:true}));
    fireEvent.change(screen.getByLabelText('From, nm'),{target:{value:'550'}});
    fireEvent.change(screen.getByLabelText('To, nm'),{target:{value:'680'}});
    fireEvent.change(screen.getByLabelText('Top, %'),{target:{value:'7'}});
    fireEvent.change(screen.getByLabelText('Bottom, %'),{target:{value:'29'}});
    view.unmount();
    const utils=render(<PumpProbeVD2 />);
    fireEvent.click(screen.getByRole('tab',{name:'Alignment',exact:true}));
    await screen.findByText('No VD2 iTest channels configured.');
    expect(screen.getByLabelText('From, nm')).toHaveValue(550);
    expect(screen.getByLabelText('To, nm')).toHaveValue(680);
    expect(screen.getByLabelText('Top, %')).toHaveValue(7);
    expect(screen.getByLabelText('Bottom, %')).toHaveValue(29);
    expect(global.fetch.mock.calls.every(([,options])=>!options?.method||options.method==='GET')).toBe(true);
    utils.unmount();
  } finally {view.unmount();global.fetch=originalFetch;}
});

test('closing a notification does not mark a failed read as recovered in history', async () => {
  jest.useFakeTimers();
  let failed = true;
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url === '/api/pump-probe-vd2/state'
    ? failed ? { success: false, error: 'State unavailable' }
      : { success: true, state: 'ON', connected: true, application_running: false, values: {} }
    : { success: true, status: 'idle' } }));
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('State unavailable');
    fireEvent.click(screen.getByRole('button', { name: 'Close this error' }));
    expect(screen.getByText(/Read history \(1\).*1 active/)).toBeInTheDocument();
    failed = false;
    await act(async () => { jest.advanceTimersByTime(2500); });
    expect(screen.getByText(/Read history \(1\).*resolved/)).toBeInTheDocument();
  } finally { view.unmount(); global.fetch = originalFetch; jest.useRealTimers(); }
});

test.each([
  ['VD2 operation in progress; acquisition status not queried', false],
  ['RemoteEx is not connected', true],
])('a transient acquisition read is retained without treating a deferred check as a failure: %s', async (message, isFailure) => {
  jest.useFakeTimers();
  let recovered = false;
  global.fetch = jest.fn(async url => {
    const payload = url === '/api/pump-probe-vd2/state'
      ? { success: true, state: 'ON', connected: true, application_running: false,
        acquisition_status: recovered ? 'idle' : 'unknown', values: {},
        attribute_errors: recovered ? {} : { acquisition_status: message } }
      : { success: true, status: 'idle' };
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText(/Read history \(1\)/);
    expect(Boolean(screen.queryByText(`Acquisition status unavailable: ${message}`))).toBe(isFailure);
    expect(Boolean(screen.queryByText('Acquisition status check deferred: another VD2 operation is in progress.'))).toBe(!isFailure);
    expect(screen.getByRole('button', { name: 'Live', exact: true })).toBeDisabled();
    recovered = true;
    await act(async () => { jest.advanceTimersByTime(2500); });
    expect(screen.queryByText(`Acquisition status unavailable: ${message}`)).not.toBeInTheDocument();
    expect(screen.getByText(/Read history \(1\).*resolved/)).toBeInTheDocument();
    const history = screen.getByLabelText('Recent read warnings');
    history.open = true;
    fireEvent(history, new Event('toggle'));
    expect(within(history).getByText(message)).toBeInTheDocument();
    expect(global.fetch.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  } finally {
    view.unmount(); global.fetch = originalFetch; jest.useRealTimers();
  }
});

test.each(['state', 'protocol'])('a recovered %s read automatically removes its old error without sending commands', async scope => {
  jest.useFakeTimers();
  let failed = true;
  global.fetch = jest.fn(async url => {
    const target = scope === 'state' ? url === '/api/pump-probe-vd2/state' : url.endsWith('/protocol/state');
    const payload = failed && target ? { success: false, error: `${scope} read unavailable` }
      : url === '/api/pump-probe-vd2/state'
        ? { success: true, state: 'ON', connected: true, application_running: false, values: {} }
        : { success: true, status: 'idle' };
    return { ok: payload.success, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText(`${scope} read unavailable`);
    failed = false;
    await act(async () => { jest.advanceTimersByTime(2500); });
    await waitFor(() => expect(screen.queryByText(`${scope} read unavailable`)).not.toBeInTheDocument());
    expect(global.fetch.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  } finally {
    view.unmount(); global.fetch = originalFetch; jest.useRealTimers();
  }
});

test.each([false, true])('Refresh clears resolved connection errors, retains uncertain writes and verifies the preview (still failed: %s)', async previewStillFailed => {
  let recovered = false;
  const healthy = { success: true, state: 'ON', connected: true, application_running: true,
    acquisition_status: 'idle', remoteex_status: 'idle', values: {} };
  global.fetch = jest.fn(async url => {
    let payload = { success: true, status: 'idle' };
    if (url === '/api/pump-probe-vd2/state') payload = healthy;
    else if (url.endsWith('/command/Acquire')) payload = { success: false, error: 'Acquisition write outcome unknown' };
    else if (url.endsWith('/refresh')) payload = recovered ? healthy : { success: false, error: 'Refresh link lost' };
    else if (url.endsWith('/preview')) payload = !recovered || previewStillFailed
      ? { success: false, error: 'Preview link lost' }
      : { success: true, frame_available: false, stream_state: 'no_valid_image' };
    return { ok: payload.success, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Preview link lost');
    fireEvent.click(screen.getByRole('button', { name: 'Acquire', exact: true }));
    await screen.findByText('Acquisition write outcome unknown');
    const refresh = within(screen.getByLabelText('VD2 header')).getByRole('button', { name: 'Refresh', exact: true });
    fireEvent.click(refresh);
    await screen.findByText('Refresh link lost');
    recovered = true;
    fireEvent.click(refresh);
    await waitFor(() => expect(screen.queryByText('Refresh link lost')).not.toBeInTheDocument());
    expect(screen.getByText('Acquisition write outcome unknown')).toBeInTheDocument();
    await waitFor(() => expect(refresh).toBeEnabled());
    expect(Boolean(screen.queryByText('Preview link lost'))).toBe(previewStillFailed);
    expect(Boolean(screen.queryByText('Waiting for first frame'))).toBe(!previewStillFailed);
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/command/Acquire'))).toHaveLength(1);
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/refresh'))).toHaveLength(2);
  } finally {
    view.unmount(); global.fetch = originalFetch;
  }
});

test('verified state clears an acknowledged command readback failure without replaying the command', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(async url => {
    const payload = url.endsWith('/command/StartLive')
      ? { success: false, code: 'READBACK_UNAVAILABLE', command_acknowledged: true, error: 'Live accepted; state read failed' }
      : url === '/api/pump-probe-vd2/state'
        ? { success: true, state: 'ON', connected: true, application_running: true,
          acquisition_status: 'idle', remoteex_status: 'idle', values: {} }
        : url.endsWith('/preview') ? { success: true, frame_available: false, stream_state: 'no_valid_image' }
          : { success: true, status: 'idle' };
    return { ok: payload.success, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    fireEvent.click(screen.getByRole('button', { name: 'Live', exact: true }));
    await screen.findByText('Live accepted; state read failed');
    await act(async () => { jest.advanceTimersByTime(2500); });
    expect(screen.queryByText('Live accepted; state read failed')).not.toBeInTheDocument();
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/command/StartLive'))).toHaveLength(1);
  } finally {
    view.unmount(); global.fetch = originalFetch; jest.useRealTimers();
  }
});

test('a stale state failure cannot undo a successful Refresh', async () => {
  let rejectState;
  const healthy = { success: true, state: 'ON', connected: true, application_running: false,
    acquisition_status: 'idle', remoteex_status: 'idle', values: {} };
  global.fetch = jest.fn(async url => {
    if (url === '/api/pump-probe-vd2/state') return new Promise((_resolve, reject) => { rejectState = reject; });
    return { ok: true, json: async () => url.endsWith('/refresh') ? healthy : { success: true, status: 'idle' } };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await waitFor(() => expect(rejectState).toBeDefined());
    fireEvent.click(within(screen.getByLabelText('VD2 header')).getByRole('button', { name: 'Refresh' }));
    await screen.findByText('Tango ON');
    await act(async () => { rejectState(new Error('Old connection failed')); });
    expect(screen.queryByText('Old connection failed')).not.toBeInTheDocument();
    expect(screen.getByText('RemoteEx connected')).toBeInTheDocument();
  } finally {
    view.unmount(); global.fetch = originalFetch;
  }
});

test('Refresh waits for an older preview request and verifies a new frame read afterwards', async () => {
  let finishOldPreview;
  let previewReads = 0;
  const healthy = { success: true, state: 'ON', connected: true, application_running: true,
    acquisition_status: 'idle', remoteex_status: 'idle', values: {} };
  global.fetch = jest.fn(async url => {
    if (url.endsWith('/preview') && ++previewReads === 1) {
      return new Promise(resolve => { finishOldPreview = resolve; });
    }
    const payload = url === '/api/pump-probe-vd2/state' || url.endsWith('/refresh') ? healthy
      : url.endsWith('/preview') ? { success: true, frame_available: false, stream_state: 'no_valid_image' }
        : { success: true, status: 'idle' };
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await waitFor(() => expect(finishOldPreview).toBeDefined());
    const refresh = within(screen.getByLabelText('VD2 header')).getByRole('button', { name: 'Refresh' });
    fireEvent.click(refresh);
    await waitFor(() => expect(global.fetch.mock.calls.some(([url]) => url.endsWith('/refresh'))).toBe(true));
    await act(async () => { finishOldPreview({ ok: false, json: async () => ({ success: false, error: 'Old preview failed' }) }); });
    await screen.findByText('Waiting for first frame');
    expect(screen.queryByText('Old preview failed')).not.toBeInTheDocument();
    expect(previewReads).toBe(2);
  } finally {
    view.unmount(); global.fetch = originalFetch;
  }
});

test('Refresh retries a failed Alignment calibration and clears it only after successful verification', async () => {
  let recovered = false;
  let calibrated = false;
  const healthy = { success: true, state: 'ON', connected: true, application_running: true,
    acquisition_status: 'idle', remoteex_status: 'idle', values: {} };
  const axes = { width: 3, height: 3, time_unit: 'us', wavelengths: [500, 600, 700], timedelays: [0, 0.5, 1] };
  const canvas = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    createImageData: () => ({ data: new Uint8ClampedArray(36) }), putImageData: jest.fn(),
  });
  global.fetch = jest.fn(async url => {
    let payload = { success: true, status: 'idle' };
    if (url === '/api/pump-probe-vd2/state' || url.endsWith('/refresh')) payload = healthy;
    else if (url.endsWith('/alignment/calibration')) {
      calibrated = recovered;
      payload = recovered ? { success: true, calibration: axes } : { success: false, error: 'Calibration link lost' };
    } else if (url.endsWith('/preview')) payload = { success: true, frame_available: true,
      width: 3, height: 3, pixels_b64: 'AAAAAAAAAAAA', calibration_key: 'optics',
      calibration: calibrated ? axes : null, received_at: new Date().toISOString() };
    return { ok: payload.success, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    fireEvent.click(screen.getByRole('tab', { name: 'Alignment', exact: true }));
    await screen.findByText('Calibration link lost');
    recovered = true;
    fireEvent.click(within(screen.getByLabelText('VD2 header')).getByRole('button', { name: 'Refresh' }));
    await screen.findByText('Calibration · automatic');
    expect(screen.queryByText('Calibration link lost')).not.toBeInTheDocument();
    expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST')
      .every(([url]) => url.endsWith('/refresh') || url.endsWith('/alignment/calibration'))).toBe(true);
  } finally {
    view.unmount(); canvas.mockRestore(); global.fetch = originalFetch;
  }
});

test('no current image clears an old error, stays passive and resumes when a frame arrives', async () => {
  let mode = 'error';
  const context = { createImageData: () => ({ data: new Uint8ClampedArray(16) }), putImageData: jest.fn() };
  const canvas = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
  global.fetch = jest.fn(async url => {
    let payload = { success: true, status: 'idle' };
    if (url.endsWith('/state') && !url.endsWith('/protocol/state') && !url.endsWith('/runtime/state')) {
      payload = { success: true, state: 'ON', connected: true, application_running: true,
        remoteex_status: 'idle', acquisition_status: 'idle', values: {} };
    } else if (url.endsWith('/preview')) {
      payload = mode === 'error' ? { success: false, error: 'Camera link lost' }
        : mode === 'empty' ? { success: true, frame_available: false, stream_state: 'no_valid_image' }
          : { success: true, frame_available: true, stream_state: 'last_frame', width: 2, height: 2,
            pixels_b64: 'AAAAAA==', received_at: new Date().toISOString() };
    }
    return { ok: payload.success, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Camera link lost');
    mode = 'empty';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame', exact: true }));
    await screen.findByText('No image available yet. Start Live or acquire a frame.');
    expect(screen.queryByText('Camera link lost')).not.toBeInTheDocument();
    expect(screen.getByText('Waiting for first frame')).toBeInTheDocument();
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 0.0 Hz');
    mode = 'frame';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame', exact: true }));
    await screen.findByText('2 x 2');
    expect(screen.queryByText('No image available yet. Start Live or acquire a frame.')).not.toBeInTheDocument();
    expect(context.putImageData).toHaveBeenCalledTimes(1);
    mode = 'empty';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame', exact: true }));
    await screen.findByText('No current image · Previous frame');
    expect(context.putImageData).toHaveBeenCalledTimes(1);
    mode = 'error';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame', exact: true }));
    await screen.findByText('Camera link lost');
    expect(global.fetch.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  } finally {
    view.unmount(); canvas.mockRestore(); global.fetch = originalFetch;
  }
});

test('both VD2 image screens show drawn-frame Hz; LUT redraws and cached frames cannot inflate it', async () => {
  jest.useFakeTimers();
  let frozenAt = null;
  let frameAvailable = true;
  const context = { createImageData: () => ({ data: new Uint8ClampedArray(4) }), putImageData: jest.fn() };
  const canvas = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url.endsWith('/preview')
    ? { success: true, frame_available: frameAvailable, width: 1, height: 1, pixels_b64: 'AA==', stream_state: 'acquiring',
      received_at: new Date(frozenAt ?? Date.now()).toISOString() }
    : url.endsWith('/state') && !url.endsWith('/protocol/state') && !url.endsWith('/runtime/state')
      ? { success: true, state: 'ON', connected: true, application_running: true, remoteex_status: 'busy', acquisition_status: 'busy', values: {} }
      : { success: true, status: 'idle' } }));
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    for (let i = 0; i < 5; i += 1) await act(async () => { jest.advanceTimersByTime(200); });
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 5.0 Hz');
    const draws = context.putImageData.mock.calls.length;
    fireEvent.change(screen.getByRole('combobox', { name: 'LUT palette' }), { target: { value: 'grayscale' } });
    expect(context.putImageData.mock.calls.length).toBeGreaterThan(draws);
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 5.0 Hz');
    fireEvent.click(screen.getByRole('tab', { name: 'Alignment', exact: true }));
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 5.0 Hz');
    frameAvailable = false;
    await act(async () => { jest.advanceTimersByTime(200); });
    expect(screen.getByLabelText('Frame display rate')).not.toHaveTextContent('Display 0.0 Hz');
    frameAvailable = true;
    await act(async () => { jest.advanceTimersByTime(200); });
    frozenAt = Date.now();
    for (let i = 0; i < 10; i += 1) await act(async () => { jest.advanceTimersByTime(200); });
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 0.0 Hz');
    expect(global.fetch.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  } finally {
    view.unmount(); canvas.mockRestore(); global.fetch = originalFetch; jest.useRealTimers();
  }
});

test('confirmed two-frame averaging paces the Alignment canvas to 2.5 Hz with a 5 Hz input', async () => {
  jest.useFakeTimers();
  let previewReads = 0;
  const context = { createImageData: () => ({ data: new Uint8ClampedArray(4) }), putImageData: jest.fn() };
  const canvas = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
  global.fetch = jest.fn(async url => {
    let payload = { success: true, status: 'idle' };
    if (url.endsWith('/preview')) {
      previewReads += 1;
      payload = { success: true, frame_available: true, width: 1, height: 1, pixels_b64: 'AA==',
        stream_state: 'acquiring', received_at: new Date().toISOString() };
    } else if (url.endsWith('/live/rolling-average')) {
      payload = { success: true, enabled: true, frames: 2 };
    } else if (url.endsWith('/state') && !url.endsWith('/protocol/state') && !url.endsWith('/runtime/state')) {
      payload = { success: true, state: 'ON', connected: true, application_running: true,
        remoteex_status: 'busy', acquisition_status: 'busy', acquisition_mode: 'Live', values: {} };
    }
    return { ok: true, headers: { get: () => new Date().toUTCString() }, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    fireEvent.click(screen.getByRole('tab', { name: 'Alignment', exact: true }));
    await screen.findByText('Current: On · 2 frames');
    for (let i = 0; i < 4; i += 1) await act(async () => jest.advanceTimersByTime(200));
    const draws = context.putImageData.mock.calls.length;
    const reads = previewReads;
    for (let i = 0; i < 10; i += 1) await act(async () => jest.advanceTimersByTime(200));
    expect(previewReads - reads).toBe(10);
    expect(context.putImageData.mock.calls.length - draws).toBe(5);
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 2.5 Hz');
    fireEvent.click(screen.getByRole('tab', { name: 'Acquisition', exact: true }));
    for (let i = 0; i < 5; i += 1) await act(async () => jest.advanceTimersByTime(200));
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 5.0 Hz');
  } finally {
    view.unmount(); canvas.mockRestore(); global.fetch = originalFetch; jest.useRealTimers();
  }
});

test('Alignment calibrates and refreshes kinetics during Live without stopping it', async () => {
  const canvasContext = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    createImageData: (width, height) => ({ data: new Uint8ClampedArray(width * height * 4) }),
    putImageData: jest.fn(),
  });
  let key = 'first-image-settings';
  let calibratedKey = null;
  let samples = [2, 4, 6, 2, 4, 6, 2, 4, 6];
  const axes = () => ({ width: 3, height: 3, time_unit: 'us',
    wavelengths: key === 'first-image-settings' ? [500, 600, 700] : [550, 650, 750],
    timedelays: [0, 0.5, 1] });
  global.fetch = jest.fn(async (url, options) => {
    let payload = { success: true };
    if (url.endsWith('/protocol/state')) payload = { success: true, status: 'idle' };
    else if (url.endsWith('/state')) payload = { success: true, state: 'ON', connected: true, application_running: true,
      acquisition_status: 'busy', acquisition_mode: 'Live', remoteex_status: 'busy', values: {} };
    else if (url.endsWith('/alignment/calibration')) { calibratedKey = key; payload = { success: true, calibration: axes() }; }
    else if (url.endsWith('/live/rolling-average')) payload = { success: true, enabled: false, frames: 2 };
    else if (url.endsWith('/preview')) payload = { success: true, frame_available: true, stream_state: 'acquiring',
      width: 3, height: 3, pixels_b64: window.btoa(String.fromCharCode(...samples)), calibration_key: key,
      calibration: calibratedKey === key ? axes() : null, received_at: new Date().toISOString() };
    else if (url.includes('/alignment/readout?')) {
      const params = new URL(url, 'http://localhost').searchParams;
      const {region} = JSON.parse(params.get('selection'));
      const y = key !== 'first-image-settings' ? 20 : samples[0] === 10 ? 25 : region.wavelengthMin === 600 ? 5 : 4;
      payload = { success: true, version: 1, profile: { frameId: params.get('frame'), timeUnit: 'us',
        wavelengthMin: 500, wavelengthMax: 700, points: [{x: 0, y}, {x: 0.5, y}, {x: 1, y}] },
        comparison: {found: false, error: 'Test frame has too few points.'} };
    }
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    fireEvent.click(screen.getByRole('tab', { name: 'Alignment' }));
    await screen.findByText('Calibration · automatic');
    expect(screen.queryByRole('button', { name: 'Refresh calibration' })).not.toBeInTheDocument();
    expect((await screen.findAllByText('4.0')).length).toBeGreaterThan(0);
    const liveImage = screen.getByRole('region', { name: 'Live streak-camera preview' });
    const plot = screen.getByRole('region', { name: 'Alignment kinetics' });
    expect(liveImage.compareDocumentPosition(plot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.change(screen.getByLabelText('From, nm'), { target: { value: '600' } });
    expect((await screen.findAllByText('5.0')).length).toBeGreaterThan(0);
    expect(screen.getByRole('region', { name: 'Live streak-camera preview' })).toBe(liveImage);
    samples = [10, 20, 30, 10, 20, 30, 10, 20, 30];
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame' }));
    await waitFor(() => expect(screen.getAllByText('25.0').length).toBeGreaterThan(0));
    key = 'new-image-settings';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame' }));
    await waitFor(() => expect(screen.getAllByText('20.0').length).toBeGreaterThan(0));
    expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST').map(([url]) => url)).toEqual([
      '/api/pump-probe-vd2/alignment/calibration', '/api/pump-probe-vd2/alignment/calibration',
    ]);
  } finally {
    view.unmount();
    canvasContext.mockRestore();
    global.fetch = originalFetch;
  }
});

test('Alignment waits for an image and stops calibration retries when the current image disappears', async () => {
  jest.useFakeTimers();
  let haveImage = false;
  let calibrationRequests = 0;
  let calibrated = false;
  const axes = { width: 3, height: 3, time_unit: 'us', wavelengths: [500, 600, 700], timedelays: [0, 0.5, 1] };
  const context = { createImageData: () => ({ data: new Uint8ClampedArray(36) }), putImageData: jest.fn() };
  const canvas = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
  global.fetch = jest.fn(async url => {
    let payload = { success: true, status: 'idle' };
    if (url.endsWith('/state') && !url.endsWith('/protocol/state') && !url.endsWith('/runtime/state')) {
      payload = { success: true, state: 'ON', connected: true, application_running: true,
        acquisition_status: 'idle', remoteex_status: 'idle', values: {} };
    } else if (url.endsWith('/preview')) {
      payload = haveImage ? { success: true, frame_available: true, stream_state: 'last_frame',
        width: 3, height: 3, pixels_b64: 'AAAAAAAAAAAA', calibration_key: 'optics', calibration: calibrated ? axes : null,
        received_at: new Date().toISOString() }
        : { success: true, frame_available: false, stream_state: 'no_valid_image' };
    } else if (url.endsWith('/alignment/calibration')) {
      calibrationRequests += 1;
      if (calibrationRequests === 1) {
        // Preview may still cache the previous frame: the calibration result
        // itself must invalidate it without another GET promoting it as fresh.
        payload = { success: true, calibration: null, frame_available: false, stream_state: 'no_valid_image' };
      } else {
        calibrated = true;
        payload = { success: true, calibration: axes };
      }
    }
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    fireEvent.click(screen.getByRole('tab', { name: 'Alignment', exact: true }));
    await screen.findByText('No VD2 iTest channels configured.');
    await screen.findByText('Waiting for first frame');
    await act(async () => { jest.advanceTimersByTime(6000); });
    expect(calibrationRequests).toBe(0);
    haveImage = true;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame', exact: true }));
    await screen.findByText('No current image · Previous frame');
    expect(calibrationRequests).toBe(1);
    await act(async () => { jest.advanceTimersByTime(6000); });
    expect(calibrationRequests).toBe(1);
    expect(screen.queryByText('Updating calibration…')).not.toBeInTheDocument();
    haveImage = true;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh frame', exact: true }));
    await screen.findByText('Calibration · automatic');
    expect(calibrationRequests).toBe(2);
    expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST')
      .every(([url]) => url.endsWith('/alignment/calibration'))).toBe(true);
  } finally {
    view.unmount(); canvas.mockRestore(); global.fetch = originalFetch; jest.useRealTimers();
  }
});

test.each(['acquiring', 'saving', 'processing'])('Alignment controls cannot interrupt a HIS %s phase', async status => {
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url.endsWith('/protocol/state')
    ? { success: true, status }
    : { success: true, state: 'ON', connected: true, application_running: true,
      acquisition_status: 'busy', acquisition_mode: 'Live', remoteex_status: 'busy', values: {} } }));
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    fireEvent.click(screen.getByRole('tab', { name: 'Alignment' }));
    const average = within(screen.getByRole('form', { name: 'Live rolling average' }));
    expect(average.getByRole('button', { name: 'Live', exact: true })).toBeDisabled();
    expect(average.getByRole('button', { name: 'Stop', exact: true })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Refresh calibration' })).not.toBeInTheDocument();
    expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  } finally {
    view.unmount();
    global.fetch = originalFetch;
  }
});

test.each([false, true])('HPD-TA stopped is reported only with a connected control link (%s)', async (connected) => {
  global.fetch = jest.fn(async url => {
    let payload = { success: true };
    if (url.endsWith('/refresh') || (url.endsWith('/state') && !url.endsWith('/runtime/state') && !url.endsWith('/protocol/state'))) {
      payload = { success: true, state: 'ON', connected, application_running: false, remoteex_status: connected ? 'idle' : 'disconnected', values: {} };
    }
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Tango ON');
    expect(screen.getByText(connected ? 'HPD-TA stopped' : 'HPD-TA status unknown')).toBeInTheDocument();
    expect(Boolean(screen.queryByText(/HPD-TA may still be running; its acquisition state is unknown/))).toBe(!connected);
    const header = within(screen.getByLabelText('VD2 header'));
    expect(header.getAllByRole('button').map(button => button.textContent)).toEqual(['Refresh']);
    expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
    fireEvent.click(header.getByRole('button', { name: 'Refresh' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-vd2/refresh', expect.objectContaining({ method: 'POST' })));
    expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST').map(([url]) => url)).toEqual(['/api/pump-probe-vd2/refresh']);
  } finally {
    view.unmount();
    global.fetch = originalFetch;
  }
});

const protocolProps = {
  settings: { framesPerHis: '10', outputRoot: 'C:\\test', runName: 'dark' },
  onChange: jest.fn(), onPhaseClick: jest.fn(), onPhaseDoubleClick: jest.fn(),
};

test('replacement links use the current project manifest rather than the older canonical H5',()=>{
  render(<Vd2PhaseProtocol {...protocolProps} protocol={{status:'completed',sample_folder:'C:\\test\\dark',
    his_path:'C:\\test\\dark\\.versions\\ABSORPTION\\2\\ABS.his',manifest_path:'C:\\test\\vd2-manifest.json',is_replacement:true}} />);
  const link=screen.getByRole('link',{name:'Run folder ↗'});
  expect(new URL(link.href).searchParams.get('manifest')).toBe('C:\\test\\vd2-manifest.json');
  fireEvent.contextMenu(link,{clientX:100,clientY:100});
  expect(new URL(screen.getByRole('menuitem',{name:'Open in Data Treatment'}).href).searchParams.get('manifest')).toBe('C:\\test\\vd2-manifest.json');
});

test('noise source offers only latest or per-sample Bruit and keeps provenance out of the control row', () => {
  const onChange = jest.fn();
  render(<Vd2PhaseProtocol {...protocolProps} onChange={onChange} protocol={{ status: 'idle' }}
    project={{ samples: [{ name: 'dark', bruit_reference: 'noise-identity' }],
      bruit_options: [{ id: 'noise-identity', sample: 'metadata_validation', completed_at: '2026-11-03' }] }} />);
  const source = screen.getByRole('combobox', { name: 'Noise Source' });
  expect(source).toHaveValue('latest');
  expect(within(source).getAllByRole('option').map(option => option.textContent)).toEqual([
    'Latest completed Bruit in project', 'Bruit for each sample',
  ]);
  expect(screen.queryByText(/Bruit: metadata_validation/)).not.toBeInTheDocument();
  fireEvent.change(source, { target: { value: 'none' } });
  expect(onChange).toHaveBeenCalledWith('reuseBruit', 'none');
});

test('per-sample noise cannot silently reuse a different samples Bruit', () => {
  const settings = { ...protocolProps.settings, reuseBruit: 'none' };
  const project = { samples: [{ name: 'dark', bruit_reference: 'noise-identity' }],
    bruit_options: [{ id: 'noise-identity', sample: 'another sample' }] };
  const view = render(<Vd2PhaseProtocol {...protocolProps} settings={settings} project={project} protocol={{ status: 'idle' }} />);
  expect(screen.getByRole('button', { name: 'Bruit', exact: true })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Base', exact: true })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Absorption', exact: true })).toBeDisabled();
  project.bruit_options = [{ id: 'noise-identity', sample: 'dark' }];
  view.rerender(<Vd2PhaseProtocol {...protocolProps} settings={settings} project={project} protocol={{ status: 'idle' }} />);
  expect(screen.getByRole('button', { name: 'Base', exact: true })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Absorption', exact: true })).toBeEnabled();
});

test.each(['acquiring', 'saving', 'processing'])('%s blocks a second phase', (status) => {
  render(<Vd2PhaseProtocol {...protocolProps} protocol={{ status, phase: 'BRUIT' }} />);
  expect(screen.getByRole('button', { name: 'Bruit' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Absorption' })).toBeDisabled();
  expect(screen.getByLabelText('Sample name')).toBeDisabled();
  expect(screen.getByText(`BRUIT ${status}`)).toBeInTheDocument();
});

test('completed phase displays verified H5 and retained raw source', () => {
  render(<Vd2PhaseProtocol {...protocolProps} protocol={{ status: 'completed',
    his_path: 'C:\\test\\BRUIT.his', h5_path: 'C:\\test\\BRUIT.h5', frame_count: 10, source_his_retained: true }} />);
  expect(screen.getByText(/10 frames · Lossless H5 verified · HIS retained/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Base' })).toBeEnabled();
});

test('completed conversion shows only H5 after HIS retirement', () => {
  render(<Vd2PhaseProtocol {...protocolProps} protocol={{ status: 'completed',
    his_path: 'C:\\test\\BRUIT.his', h5_path: 'C:\\test\\BRUIT.h5', frame_count: 10, source_his_retained: false }} />);
  expect(screen.getByText(/10 frames · Lossless H5 verified · HIS removed/)).toBeInTheDocument();
  expect(screen.queryByText('C:\\test\\BRUIT.his')).not.toBeInTheDocument();
  expect(screen.getByText('C:\\test\\BRUIT.h5')).toBeInTheDocument();
});

test('exposure displays actual milliseconds and writes explicit units only after edit', () => {
  const apply = jest.fn();
  render(<EditableField field={{ key: 'live_exposure_time', label: 'Live exposure', type: 'number', duration: true, unit: 'ms' }} value="10 ms" onApply={apply} />);
  const input = screen.getByLabelText('Live exposure');
  expect(input).toHaveValue(10);
  fireEvent.blur(input);
  expect(apply).not.toHaveBeenCalled();
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: '20' } });
  fireEvent.blur(input);
  expect(apply).toHaveBeenCalledWith('live_exposure_time', '20 ms');
});

test('folder context menu carries selected run into Data Treatment', () => {
  render(<Vd2PhaseProtocol {...protocolProps} protocol={{ status: 'idle' }} />);
  fireEvent.contextMenu(screen.getByLabelText('Everest folder'), { clientX: 200, clientY: 200 });
  const link = screen.getByRole('menuitem', { name: 'Open in Data Treatment' });
  const url = new URL(link.getAttribute('href'), 'http://localhost');
  expect(url.searchParams.get('folder')).toBe('C:\\test\\dark');
  expect(url.searchParams.get('profile')).toBe('VD2');
});

test('time-range selector includes the operator-supplied 2 ms endpoint', () => {
  expect(TIME_RANGES).toContain('2 ms');
});

test('starting a HIS phase keeps fetching preview frames while native state is idle', async () => {
  jest.useFakeTimers();
  let acquiring = false;
  global.fetch = jest.fn(async url => {
    let payload = { success: true };
    if (url.endsWith('/protocol/start')) acquiring = true;
    if (url.endsWith('/protocol/start') || url.endsWith('/protocol/state')) {
      payload = { success: true, status: acquiring ? 'acquiring' : 'idle', phase: 'BRUIT' };
    } else if (url.endsWith('/protocol/plan')) {
      payload={success:true,conflict:false,choices:{record:{token:'reviewed',run_name:'test'}}};
    } else if (url.endsWith('/state') && !url.endsWith('/runtime/state')) {
      payload = { success: true, connected: true, application_running: true, remoteex_status: 'idle', values: {} };
    } else if (url.endsWith('/preview')) {
      payload = { success: true, frame_available: false, stream_state: acquiring ? 'acquiring' : 'last_frame' };
    }
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await waitFor(() => expect(screen.getByRole('button', { name: 'Live', exact: true })).toBeEnabled());
    fireEvent.doubleClick(screen.getByRole('button', { name: 'Bruit' }));
    await screen.findByText('Acquiring', { exact: true });
    const before = global.fetch.mock.calls.filter(([url]) => url.endsWith('/preview')).length;
    await act(async () => { jest.advanceTimersByTime(600); });
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/preview')).length).toBeGreaterThan(before);
    expect(screen.getByText('Acquiring', { exact: true })).toBeInTheDocument();
  } finally {
    view.unmount();
    global.fetch = originalFetch;
    jest.useRealTimers();
  }
});

test('native busy Live keeps preview polling when Tango cache says idle', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(async url => {
    let payload = { success: true };
    if (url.endsWith('/state') && !url.endsWith('/runtime/state') && !url.endsWith('/protocol/state')) {
      payload = { success: true, state: 'ON', connected: true, application_running: true,
        cached_remoteex_status: 'idle', remoteex_status: 'busy', acquisition_status: 'busy',
        acquisition_mode: 'Live', values: {} };
    } else if (url.endsWith('/preview')) {
      payload = { success: true, frame_available: false, stream_state: 'last_frame' };
    }
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Acquiring', { exact: true });
    const before = global.fetch.mock.calls.filter(([url]) => url.endsWith('/preview')).length;
    await act(async () => { jest.advanceTimersByTime(1100); });
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/preview')).length).toBeGreaterThan(before);
    expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/live/rolling-average')).every(([, options]) => !options.method)).toBe(true);
  } finally {
    view.unmount();
    global.fetch = originalFetch;
    jest.useRealTimers();
  }
});

test('Live preview targets 5 Hz and never overlaps a slow frame transfer', async () => {
  jest.useFakeTimers();
  let delay = 0;
  let active = 0;
  let maximumActive = 0;
  let previews = 0;
  global.fetch = jest.fn(async url => {
    let payload = { success: true };
    if (url.endsWith('/state') && !url.endsWith('/protocol/state') && !url.endsWith('/runtime/state')) {
      payload = { success: true, state: 'ON', connected: true, application_running: true,
        acquisition_status: 'busy', remoteex_status: 'busy', acquisition_mode: 'Live', values: {} };
    } else if (url.endsWith('/preview')) {
      previews += 1;
      active += 1;
      maximumActive = Math.max(maximumActive, active);
      if (delay) await new Promise(resolve => window.setTimeout(resolve, delay));
      active -= 1;
      payload = { success: true, frame_available: false, stream_state: 'acquiring' };
    }
    return { ok: true, json: async () => payload };
  });
  const view = render(<PumpProbeVD2 />);
  try {
    await screen.findByText('Acquiring', { exact: true });
    const before = previews;
    for (let i = 0; i < 10; i += 1) await act(async () => { jest.advanceTimersByTime(100); });
    expect(previews - before).toBe(5);
    delay = 350;
    for (let i = 0; i < 15; i += 1) await act(async () => { jest.advanceTimersByTime(100); });
    expect(maximumActive).toBe(1);
  } finally {
    view.unmount();
    jest.useRealTimers();
    global.fetch = originalFetch;
  }
});

describe('fetchVd2', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true });
    document.cookie = 'csrf_access_token=vd2%20token; path=/';
  });

  afterEach(() => {
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });

  test('adds CSRF to same-origin mutations and preserves request fields', () => {
    const body = JSON.stringify({ phase: 'BASE' });

    fetchVd2('/api/pump-probe-vd2/protocol/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'vd2-1' },
      credentials: 'include',
      body,
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-vd2/protocol/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-Id': 'vd2-1',
        'X-CSRF-TOKEN': 'vd2 token',
      },
      credentials: 'include',
      body,
    });
  });

  test('leaves GET request headers unchanged', () => {
    const options = { method: 'GET', headers: { 'X-Request-Id': 'vd2-2' } };

    fetchVd2('/api/pump-probe-vd2/state', options);

    expect(global.fetch).toHaveBeenCalledWith('/api/pump-probe-vd2/state', options);
  });

  test('uses only passive state and readiness loaders for automatic refresh', async () => {
    const loadState = jest.fn().mockResolvedValue();
    const loadStartupReadiness = jest.fn().mockResolvedValue();

    await refreshVd2Passive(loadState, loadStartupReadiness);

    expect(loadState).toHaveBeenCalledTimes(1);
    expect(loadStartupReadiness).toHaveBeenCalledTimes(1);
  });
});
