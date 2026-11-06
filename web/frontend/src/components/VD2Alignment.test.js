import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ITestPSUClient from './ITestPSUClient';
import { AlignmentKinetics, AlignmentOptics } from './VD2Alignment';
import { AlignmentSignalBuffer } from '../vd2AlignmentSearch';
import io from 'socket.io-client';

jest.mock('socket.io-client', () => jest.fn());
const originalFetch = global.fetch;
beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
afterEach(() => { global.fetch = originalFetch; });

const region = { wavelengthMin: 500, wavelengthMax: 700, topPercent: 0, bottomPercent: 20 };
const geometry = { timeUnit: 'us', timeMin: 0, timeMax: 0.79 };
const auto = { baseline: [0.25, 0.34], signal: [0.35, 0.39] };

function serverReply(url) {
  const params = new URL(url, 'http://localhost').searchParams;
  const id = params.get('frame');
  const { windows = null } = JSON.parse(params.get('selection'));
  const percent = id === 'two' ? 30.86 : 15.43;
  const bad = windows?.baseline[1] < 0.1;
  return { ok: true, json: async () => ({
    success: true, version: 1, fresh: true, frame_age_ms: 10, summary_age_ms: 200,
    profile: { frameId: id, timeUnit: 'us', wavelengthMin: 500, wavelengthMax: 700,
      points: Array.from({ length: 80 }, (_, i) => ({ x: i * 0.01, y: 100 + i * 0.8 - (i >= 35 ? (id === 'two' ? 80 : 20) : 0) })) },
    windows: windows || auto, signal_key: 'server signal',
    comparison: bad ? { found: false, error: 'Each window needs at least 3 points.' } : {
      found: true, percent: 99, x: 0.37, y: 80, base: 130, windowStart: 0.35, windowEnd: 0.39,
      ...(id === 'two' ? { optical_density: 0.30103 } : id === 'zero' ? { optical_density: null, y: 0 } : {}),
      baseline: [{x: 0.25, y: 120}, {x: 0.39, y: 131.2}] },
    summary: bad ? null : { kind: 'mean', mean: percent, sd: 2.5, n: 4 },
  }) };
}

function TestKinetics({ id = 'one', ...props }) {
  return <AlignmentKinetics region={region} geometry={geometry} context="test ROI" frameId={id} {...props} />;
}

beforeEach(() => { global.fetch = jest.fn(async url => serverReply(url)); });

test('renders server mean and SD; a stale image keeps its number but cannot feed search', async () => {
  const buffer = new AlignmentSignalBuffer();
  const view = render(<TestKinetics measurements={buffer} />);
  await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('15.43% ± 2.50%'));
  expect(screen.getByLabelText('Optical density')).toHaveTextContent('Absorption · OD 0.211');
  expect(screen.getByLabelText('Alignment calculation status')).toHaveTextContent('1 s mean ± SD · n = 4');
  expect(buffer.samples[0].percent).toBe(99);
  view.rerender(<TestKinetics measurements={buffer} fresh={false} freshnessMessage="Network read failed" />);
  expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('15.43%');
  expect(screen.getByRole('status')).toHaveTextContent('Network read failed');
  expect(buffer.samples).toHaveLength(0);
});

test('shows OD from the server and leaves it unavailable for a zero signal', async () => {
  const view = render(<TestKinetics id="two" />);
  await waitFor(() => expect(screen.getByLabelText('Optical density')).toHaveTextContent('Absorption · OD 0.301'));
  view.rerender(<TestKinetics id="zero" />);
  await waitFor(() => expect(screen.getByLabelText('Optical density')).toHaveTextContent('Absorption · OD —'));
});

test('cursor edits suppress the old result, report invalid zones, and persist valid positions after remount', async () => {
  const view = render(<TestKinetics />);
  await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('15.43%'));
  fireEvent.change(screen.getByLabelText('Baseline end time'), {target: {value: '0.08'}});
  expect(screen.getByLabelText('Relative signal drop')).not.toHaveTextContent('15.43%');
  expect(await screen.findByText(/Each window needs at least 3 points/,{selector:'p'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Auto zones'}));
  await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('15.43%'));
  fireEvent.change(screen.getByLabelText('Signal end time'), {target:{value:'0.5'}});
  view.unmount();
  render(<TestKinetics id="two" />);
  expect(await screen.findByLabelText('Signal end time')).toHaveValue(0.5);
  await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('30.86%'));
  expect(window.localStorage.length).toBe(0);
});

test('window dragging keeps the chosen interval fixed across live frames and supports edge resizing', async () => {
  const previousPointerEvent=window.PointerEvent;
  window.PointerEvent=MouseEvent;
  const view=render(<TestKinetics />);
  await screen.findByLabelText('Signal start time');
  try {
    const svg=screen.getByRole('img',{name:'Kinetics versus time (us)'});
    svg.getBoundingClientRect=()=>({left:0,top:0,width:560,height:450});
    const start=Number(screen.getByLabelText('Signal start time').value);
    const end=Number(screen.getByLabelText('Signal end time').value);
    fireEvent.pointerDown(screen.getByRole('slider',{name:'Signal window'}),{clientX:290,clientY:180,button:0});
    fireEvent.pointerMove(svg,{clientX:310,clientY:180});
    fireEvent.pointerUp(svg);
    const movedStart=Number(screen.getByLabelText('Signal start time').value);
    const movedEnd=Number(screen.getByLabelText('Signal end time').value);
    expect(movedStart).toBeGreaterThan(start);
    expect(movedEnd-movedStart).toBeCloseTo(end-start,6);
    view.rerender(<TestKinetics id="two" />);
    await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('30.86%'));
    expect(Number(screen.getByLabelText('Signal start time').value)).toBe(movedStart);
    fireEvent.keyDown(screen.getByRole('slider',{name:'Signal end'}),{key:'ArrowRight'});
    expect(Number(screen.getByLabelText('Signal end time').value)).toBeGreaterThan(movedEnd);
  } finally {view.unmount();window.PointerEvent=previousPointerEvent;}
});

test('star alone controls Y autorange, wheel zoom remains independent, and live drop keeps updating', async () => {
  const view = render(<TestKinetics />);
  await screen.findByLabelText('Signal start time');
  const star = screen.getByRole('button', { name: 'Auto Y' });
  expect(star).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(star);
  const fixedTicks = screen.getByLabelText('Y axis divisions').textContent;
  view.rerender(<TestKinetics id="two" />);
    await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('30.86%'));
  expect(screen.getByLabelText('Y axis divisions').textContent).toBe(fixedTicks);
  expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('30.86%');
  const svg = screen.getByRole('img', { name: 'Kinetics versus time (us)' });
  fireEvent.wheel(svg, { deltaY: -120, clientX: 299, clientY: 213 });
  expect(star).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getByLabelText('Y axis divisions').textContent).not.toBe(fixedTicks);
  fireEvent.click(screen.getByRole('button', { name: 'Reset zoom' }));
  expect(star).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(star);
  expect(star).toHaveAttribute('aria-pressed', 'true');
  fireEvent.wheel(svg, { deltaY: -120, clientX: 299, clientY: 213 });
  expect(star).toHaveAttribute('aria-pressed', 'true');
});

test('the hand pans both axes without dragging the measurement windows or changing Auto Y', async () => {
  const previousPointerEvent = window.PointerEvent;
  window.PointerEvent = MouseEvent;
  const view = render(<TestKinetics />);
  try {
    const signal = await screen.findByRole('slider', { name: 'Signal window' });
    const svg = screen.getByRole('img', { name: 'Kinetics versus time (us)' });
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 560, height: 450 });
    const start = screen.getByLabelText('Signal start time').value;
    const end = screen.getByLabelText('Signal end time').value;
    const xAxis = screen.getByLabelText('X axis divisions');
    const yAxis = screen.getByLabelText('Y axis divisions');
    const initialX = xAxis.textContent, initialY = yAxis.textContent;
    const hand = screen.getByRole('button', { name: 'Pan kinetics' });
    fireEvent.click(hand);
    expect(hand).toHaveAttribute('aria-pressed', 'true');
    fireEvent.pointerDown(signal, { button: 0, clientX: 290, clientY: 180 });
    fireEvent.pointerMove(svg, { clientX: 340, clientY: 230 });
    fireEvent.pointerUp(svg);
    expect(xAxis.textContent).not.toBe(initialX);
    expect(yAxis.textContent).not.toBe(initialY);
    expect(screen.getByLabelText('Signal start time').value).toBe(start);
    expect(screen.getByLabelText('Signal end time').value).toBe(end);
    expect(screen.getByRole('button', { name: 'Auto Y' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Reset zoom' }));
    expect(xAxis.textContent).toBe(initialX);
    expect(yAxis.textContent).toBe(initialY);
  } finally { view.unmount(); window.PointerEvent = previousPointerEvent; }
});

test.each(['X', 'Y', 'XY'])('%s wheel zoom changes only the selected axes and preserves autorange mode', async direction => {
  render(<TestKinetics />);
  await screen.findByLabelText('Signal start time');
  const star = screen.getByRole('button', { name: 'Auto Y' });
  fireEvent.click(star);
  fireEvent.click(screen.getByRole('button', { name: `Zoom ${direction}` }));
  const xBefore = screen.getByLabelText('X axis divisions').textContent;
  const yBefore = screen.getByLabelText('Y axis divisions').textContent;
  fireEvent.wheel(screen.getByRole('img', { name: 'Kinetics versus time (us)' }),
    { deltaY: -120, clientX: 299, clientY: 213 });
  const xAfter = screen.getByLabelText('X axis divisions').textContent;
  const yAfter = screen.getByLabelText('Y axis divisions').textContent;
  expect(xAfter === xBefore).toBe(direction === 'Y');
  expect(yAfter === yBefore).toBe(direction === 'X');
  expect(star).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getByRole('button', { name: `Zoom ${direction}` })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'Reset zoom' }));
  expect(screen.getByLabelText('X axis divisions').textContent).toBe(xBefore);
  expect(screen.getByLabelText('Y axis divisions').textContent).toBe(yBefore);
  expect(star).toHaveAttribute('aria-pressed', 'false');
});

test('X-only zoom leaves automatic Y scaling active for new live frames', async () => {
  const view = render(<TestKinetics />);
  await screen.findByLabelText('Signal start time');
  fireEvent.click(screen.getByRole('button', { name: 'Zoom X' }));
  const yBefore = screen.getByLabelText('Y axis divisions').textContent;
  fireEvent.wheel(screen.getByRole('img', { name: 'Kinetics versus time (us)' }),
    { deltaY: -120, clientX: 299, clientY: 213 });
  const xZoomed = screen.getByLabelText('X axis divisions').textContent;
  expect(screen.getByLabelText('Y axis divisions').textContent).toBe(yBefore);
  view.rerender(<TestKinetics id="two" />);
    await waitFor(() => expect(screen.getByLabelText('Relative signal drop')).toHaveTextContent('30.86%'));
  expect(screen.getByLabelText('X axis divisions').textContent).toBe(xZoomed);
  expect(screen.getByLabelText('Y axis divisions').textContent).not.toBe(yBefore);
  expect(screen.getByRole('button', { name: 'Auto Y' })).toHaveAttribute('aria-pressed', 'true');
});

test('embedded magnet client shows only configured VD2 channels without changing currents', async () => {
  io.mockReturnValue({ on: jest.fn(), disconnect: jest.fn(), emit: jest.fn() });
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url.includes('tab_config')
    ? { tab_configs: { V0: { slots: [1] }, VD2: { slots: [4] } } }
    : { ids: [1, 4], names: ['V0 magnet', 'VD2 magnet'], states: [1, 1], currents_setpoint: [0.1, 0.2], currents_meas: [0.1, 0.2], current_limits: [-1, 1, -1, 1] } }));
  render(<ITestPSUClient deviceName="test/psu/one" fixedTab="VD2" compact />);
  expect(await screen.findByRole('heading', { name: 'VD2 magnet' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'V0 magnet' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Load Defaults' })).not.toBeInTheDocument();
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(global.fetch.mock.calls.every(([, options]) => !options.method || options.method === 'GET')).toBe(true);
});

const readyOptics = { success: true, ready: true,
  shutters: { streak_shutter: { value: 'Open' }, spectrograph_shutter: { value: 'Open' } },
  zaber_mirror: { state: 'ON', position_mm: 0.01, at_flash_lamp: true } };
const opticalResponse = payload => ({ ok: true, json: async () => payload });

test('optics mount only reads actual shutter and mirror state', async () => {
  global.fetch = jest.fn(async () => opticalResponse(readyOptics));
  render(<AlignmentOptics />);
  expect(await screen.findByText('Ready · Flash lamp + both shutters open')).toHaveClass('is-confirmed');
  expect(screen.getByText('Flash lamp · Out · 0.0100 mm')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Flash lamp · Out · 0 mm' })).toBeDisabled();
  expect(global.fetch.mock.calls.every(([, options]) => !options.method || options.method === 'GET')).toBe(true);
});

test('mirror command acknowledgement is shown as moving, never as confirmed Flash lamp', async () => {
  const initial = { ...readyOptics, ready: false,
    zaber_mirror: { state: 'ON', position_mm: 50, at_flash_lamp: false } };
  let current = initial;
  global.fetch = jest.fn(async (url, options) => {
    if (options.method === 'POST') {
      current = { ...initial, zaber_mirror: { state: 'MOVING', at_flash_lamp: false } };
      return opticalResponse({ success: true });
    }
    return opticalResponse(current);
  });
  render(<AlignmentOptics />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Flash lamp · Out · 0 mm' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Flash lamp · Out · 0 mm' }));
  expect(await screen.findByText('Moving…')).toBeInTheDocument();
  expect(screen.queryByText('Ready · Flash lamp + both shutters open')).not.toBeInTheDocument();
  expect(global.fetch.mock.calls.filter(([, options]) => options.method === 'POST').map(([url]) => url))
    .toEqual(['/api/pump-probe-vd2/alignment/flash-lamp']);
});

test('partial shutter failure remains visible and cannot produce a Ready badge', async () => {
  let current = readyOptics;
  global.fetch = jest.fn(async (_url, options) => {
    if (options.method === 'POST') {
      current = { ...readyOptics, ready: false, shutters: { ...readyOptics.shutters, spectrograph_shutter: { value: 'Closed' } } };
      return { ok: false, json: async () => ({ success: false, error: 'Spectrograph did not open' }) };
    }
    return opticalResponse(current);
  });
  render(<AlignmentOptics />);
  await screen.findByText('Ready · Flash lamp + both shutters open');
  fireEvent.click(screen.getByRole('button', { name: 'Open both shutters' }));
  expect(await screen.findByText('Spectrograph did not open')).toBeInTheDocument();
  expect(await screen.findByText('Closed')).toBeInTheDocument();
  expect(screen.queryByText('Ready · Flash lamp + both shutters open')).not.toBeInTheDocument();
});

test('old successful readings lose confirmation when polling stops responding', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn().mockResolvedValueOnce(opticalResponse(readyOptics)).mockImplementation(() => new Promise(() => {}));
  const view = render(<AlignmentOptics />);
  try {
    await screen.findByText('Ready · Flash lamp + both shutters open');
    await act(async () => { jest.advanceTimersByTime(7000); });
    expect(screen.queryByText('Ready · Flash lamp + both shutters open')).not.toBeInTheDocument();
    expect(screen.getByText('Flash lamp · Out · 0.0100 mm · unverified')).toBeInTheDocument();
  } finally {
    view.unmount();
    jest.useRealTimers();
  }
});
