import { act, fireEvent, render, screen } from '@testing-library/react';
import VD2LiveAverage from './VD2LiveAverage';

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

test('reports a brief read failure and verified recovery to history without replaying writes', async () => {
  jest.useFakeTimers();
  const onReadError = jest.fn();
  let failed = true;
  global.fetch = jest.fn(async () => ({ ok: !failed, json: async () => failed
    ? { success: false, error: 'Acquisition in progress' }
    : { success: true, enabled: true, frames: 2 } }));
  const view = render(<VD2LiveAverage onReadError={onReadError} />);
  try {
    await screen.findByText('Acquisition in progress');
    expect(onReadError).toHaveBeenLastCalledWith('Acquisition in progress');
    failed = false;
    await act(async () => { jest.advanceTimersByTime(5000); });
    expect(onReadError).toHaveBeenLastCalledWith('');
    expect(screen.queryByText('Acquisition in progress')).not.toBeInTheDocument();
    expect(global.fetch.mock.calls.every(([, options]) => !options.method)).toBe(true);
  } finally { view.unmount(); jest.useRealTimers(); }
});

test('active Live reads current averaging settings and permits explicit changes', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ success: true, enabled: false, frames: 2 }) }));
  render(<VD2LiveAverage liveActive />);
  await screen.findByText('Current: Off · 2 frames');
  expect(screen.getByRole('checkbox', { name: 'Rolling average' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();
  expect(global.fetch.mock.calls.every(([, options]) => !options.method)).toBe(true);
});

test('checkbox applies immediately and frame edits apply without blur or Apply', async () => {
  global.fetch = jest.fn(async (_url, options) => ({ ok: true, json: async () => options.method === 'POST'
    ? { success: true, ...JSON.parse(options.body) } : { success: true, enabled: false, frames: 2 } }));
  render(<VD2LiveAverage />);
  await screen.findByText('Current: Off · 2 frames');
  expect(global.fetch.mock.calls.every(([, options]) => !options.method)).toBe(true);
  fireEvent.click(screen.getByRole('checkbox', { name: 'Rolling average' }));
  await screen.findByText('Current: On · 2 frames');
  fireEvent.change(screen.getByLabelText('Rolling average frames'), { target: { value: '10' } });
  await screen.findByText('Current: On · 10 frames');
  const writes = global.fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(JSON.parse(writes[1][1].body)).toEqual({ enabled: true, frames: 10 });
});

test('Enter during a pending setting change never sends concurrent writes', async () => {
  let finish;
  global.fetch = jest.fn(async (_url, options) => options.method === 'POST'
    ? new Promise(resolve => { finish=()=>resolve({ok:true,json:async()=>({success:true,enabled:true,frames:10})}); })
    : {ok:true,json:async()=>({success:true,enabled:true,frames:2})});
  render(<VD2LiveAverage />);
  await screen.findByText('Current: On · 2 frames');
  fireEvent.change(screen.getByLabelText('Rolling average frames'),{target:{value:'10'}});
  fireEvent.submit(screen.getByRole('form',{name:'Live rolling average'}));
  fireEvent.submit(screen.getByRole('form',{name:'Live rolling average'}));
  expect(global.fetch.mock.calls.filter(([,options])=>options.method==='POST')).toHaveLength(1);
  await act(async()=>{finish();});
  expect(screen.getByText('Current: On · 10 frames')).toBeInTheDocument();
});

test('a nominal success with mismatched readback is still reported as a failure', async () => {
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({success:true,enabled:true,frames:2})}));
  render(<VD2LiveAverage />);
  await screen.findByText('Current: On · 2 frames');
  fireEvent.change(screen.getByLabelText('Rolling average frames'),{target:{value:'10'}});
  fireEvent.blur(screen.getByLabelText('Rolling average frames'));
  expect(await screen.findByRole('alert')).toHaveTextContent('readback differs');
  expect(screen.queryByText('Current: On · 10 frames')).not.toBeInTheDocument();
});

test('failed setting change stays visible without claiming successful readback', async () => {
  global.fetch = jest.fn(async (_url, options) => options.method === 'POST'
    ? { ok: false, json: async () => ({ success: false, error: 'Cannot verify Live RecurNumber2' }) }
    : { ok: true, json: async () => ({ success: true, enabled: false, frames: 2 }) });
  render(<VD2LiveAverage />);
  await screen.findByText('Current: Off · 2 frames');
  fireEvent.click(screen.getByRole('checkbox', { name: 'Rolling average' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot verify Live RecurNumber2');
  expect(screen.getByText('Unavailable')).toBeInTheDocument();
});

test('typing then toggling applies the latest count once and cancels the delayed edit', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(async (_url, options) => ({ ok: true, json: async () => options.method === 'POST'
    ? { success: true, ...JSON.parse(options.body) } : { success: true, enabled: false, frames: 2 } }));
  const view = render(<VD2LiveAverage />);
  try {
    await screen.findByText('Current: Off · 2 frames');
    fireEvent.change(screen.getByLabelText('Rolling average frames'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('Rolling average frames'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Rolling average' }));
    await screen.findByText('Current: On · 10 frames');
    await act(async () => { jest.advanceTimersByTime(500); });
    const writes = global.fetch.mock.calls.filter(([, options]) => options.method === 'POST');
    expect(writes).toHaveLength(1);
    expect(JSON.parse(writes[0][1].body)).toEqual({ enabled: true, frames: 10 });
  } finally { view.unmount(); jest.useRealTimers(); }
});

test('leaving or disabling the control cancels a delayed frame edit', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ success: true, enabled: false, frames: 2 }) }));
  const view = render(<VD2LiveAverage />);
  try {
    await screen.findByText('Current: Off · 2 frames');
    fireEvent.change(screen.getByLabelText('Rolling average frames'), { target: { value: '10' } });
    view.rerender(<VD2LiveAverage disabled />);
    await act(async () => { jest.advanceTimersByTime(500); });
    view.unmount();
    expect(global.fetch.mock.calls.every(([, options]) => !options.method)).toBe(true);
  } finally { view.unmount(); jest.useRealTimers(); }
});

test('a Live status transition does not cancel a pending frame-count edit',async()=>{
  jest.useFakeTimers();
  global.fetch=jest.fn(async(_url,options)=>({ok:true,json:async()=>options.method==='POST'
    ?{success:true,...JSON.parse(options.body)}:{success:true,enabled:true,frames:2}}));
  const view=render(<VD2LiveAverage liveActive={false}/>);
  try{
    await screen.findByText('Current: On · 2 frames');
    fireEvent.change(screen.getByLabelText('Rolling average frames'),{target:{value:'5'}});
    view.rerender(<VD2LiveAverage liveActive/>);
    await act(async()=>jest.advanceTimersByTime(400));
    expect(screen.getByText('Current: On · 5 frames')).toBeInTheDocument();
    expect(global.fetch.mock.calls.filter(([,options])=>options.method==='POST')).toHaveLength(1);
  }finally{view.unmount();jest.useRealTimers();}
});
