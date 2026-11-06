import { alignmentDropWindows, editAlignmentWindow, measureAlignmentWindows, alignmentProfile, detectAlignmentDrop, exposureMilliseconds, previewRefreshRate, previewShouldPoll, treatmentFolderUrl } from './vd2AlignmentMath';
import { alignmentRegionFromBounds, editRoiBounds } from './vd2RoiMath';

test('Live preview continues during conversion only after explicit camera ownership release',()=>{
  const state={connected:true,application_running:true,remoteex_status:'busy'};
  expect(previewShouldPoll('alignment',state,{status:'processing',acquisition_active:false,acquisition_phase:'idle'},true)).toBe(true);
  expect(previewShouldPoll('alignment',state,{status:'processing'},true)).toBe(false);
  expect(previewShouldPoll('alignment',state,{status:'saving',acquisition_active:true,acquisition_phase:'saving'},true)).toBe(false);
});

test.each([['10 ms', '10'], ['0.02 s', '20'], ['500 us', '0.5'], ['', '']])('exposure %s displays %s ms', (raw, display) => {
  expect(exposureMilliseconds(raw)).toBe(display);
});

const preview = { width: 4, height: 5, pixels_b64: window.btoa(String.fromCharCode(...Array.from({ length: 20 }, (_, i) => i + 1))) };
const calibration = { width: 4, height: 5, wavelengths: [500, 600, 700, 800], timedelays: [0.1, 0.2, 0.4, 0.8, 1.5], time_unit: 'us' };
const region = { wavelengthMin: 500, wavelengthMax: 700, topPercent: 0, bottomPercent: 20 };

const fallingTrace = (drop = 20, xAt = i => i * 0.01) => ({ timeUnit: 'us',
  points: Array.from({ length: 80 }, (_, i) => ({ x: xAt(i), y: 100 + 80 * xAt(i) - (i >= 35 ? drop : 0) })) });

test('manual windows measure a broad drop that the sharp-edge detector deliberately rejects', () => {
  const profile = fallingTrace(0);
  profile.points = profile.points.map((p,i) => ({ ...p,y:p.y-Math.max(0,Math.min(10,i-30))*3 }));
  expect(detectAlignmentDrop(profile).found).toBe(false);
  const windows = { baseline: [0.1,0.25], signal:[0.45,0.55] };
  const measured = measureAlignmentWindows(profile,windows);
  expect(measured.found).toBe(true);
  expect(measured.drop).toBeCloseTo(30,8);
  expect(measured.base).toBeCloseTo(140,8);
  expect(measured.percent).toBeCloseTo(100*30/140,8);
  expect(measureAlignmentWindows({...profile,points:[...profile.points].reverse()},windows).percent).toBeCloseTo(measured.percent,8);
});

test('fixed windows keep measuring new frames and give zero on the same unbroken rising trend', () => {
  const windows = alignmentDropWindows(fallingTrace());
  expect(measureAlignmentWindows(fallingTrace(),windows).percent).toBeCloseTo(100*20/129.6,8);
  expect(measureAlignmentWindows(fallingTrace(40),windows).percent).toBeCloseTo(100*40/129.6,8);
  expect(measureAlignmentWindows(fallingTrace(0),windows).percent).toBeCloseTo(0,8);
  expect(measureAlignmentWindows(fallingTrace(-20),windows).percent).toBeLessThan(0);
});

test('invalid or overlapping measurement windows never invent an intensity percentage', () => {
  expect(measureAlignmentWindows(fallingTrace(), {baseline:[0.1,0.4],signal:[0.3,0.5]}).found).toBe(false);
  expect(measureAlignmentWindows(fallingTrace(), {baseline:[0.1,0.101],signal:[0.3,0.5]}).error).toMatch(/at least 3/);
  const zero={points:Array.from({length:20},(_,x)=>({x,y:0}))};
  expect(measureAlignmentWindows(zero,alignmentDropWindows(zero)).error).toMatch(/positive/);
});

test('moving and resizing windows cannot cross one another or leave the calibrated time axis', () => {
  const windows={baseline:[0.1,0.25],signal:[0.4,0.5]};
  expect(editAlignmentWindow(windows,'baseline','move',-2,[0,1],0.01).baseline[0]).toBe(0);
  expect(editAlignmentWindow(windows,'baseline','end',2,[0,1],0.01).baseline[1]).toBeLessThan(windows.signal[0]);
  expect(editAlignmentWindow(windows,'signal','start',-2,[0,1],0.01).signal[0]).toBeGreaterThan(windows.baseline[1]);
  expect(editAlignmentWindow(windows,'signal','move',2,[0,1],0.01).signal[1]).toBe(1);
  expect(windows).toEqual({baseline:[0.1,0.25],signal:[0.4,0.5]});
});

test('one-frame drop integrates at the foot against the extrapolated rising baseline', () => {
  const profile = fallingTrace();
  const result = detectAlignmentDrop(profile, 5);
  expect(result).toMatchObject({ found: true, integrationPoints: 5 });
  expect(result.edgeX).toBeCloseTo(0.35, 8);
  expect(result.windowStart).toBeCloseTo(0.35, 8);
  expect(result.windowEnd).toBeCloseTo(0.39, 8);
  expect(result.base).toBeCloseTo(129.6, 8);
  expect(result.drop).toBeCloseTo(20, 8);
  expect(result.percent).toBeCloseTo(100 * 20 / 129.6, 8);
  expect(detectAlignmentDrop(fallingTrace(40), 5).percent).toBeCloseTo(100 * 40 / 129.6, 8);
});

test('calibrated nonlinear time and reversed row order retain the physical baseline', () => {
  const profile = fallingTrace(20, i => (i / 80) ** 2);
  const result = detectAlignmentDrop(profile, 5);
  const expected = profile.points.slice(35, 40).reduce((sum, p) => sum + 100 + 80 * p.x, 0) / 5;
  expect(result.found).toBe(true);
  expect(result.base).toBeCloseTo(expected, 7);
  expect(result.drop).toBeCloseTo(20, 7);
  const reversed = { ...profile, points: [...profile.points].reverse() };
  expect(detectAlignmentDrop(reversed, 5).percent).toBeCloseTo(result.percent, 8);
  expect(reversed.points[0]).toBe(profile.points[79]);
});

test('a short sloping fall is followed to its foot before integrating', () => {
  const profile = fallingTrace(0);
  profile.points = profile.points.map((p, i) => ({ ...p, y: p.y - (i < 35 ? 0 : Math.min(3, i - 34) * 10) }));
  const result = detectAlignmentDrop(profile, 5);
  expect(result.found).toBe(true);
  expect(result.windowStart).toBeCloseTo(0.37, 8);
  expect(result.drop).toBeCloseTo(30, 7);
});

test.each(['rising', 'falling', 'flat noise', 'down spike', 'up spike', 'slow rolloff'])('%s alone is not reported as a sharp persistent drop', type => {
  const profile = fallingTrace(0);
  profile.points = profile.points.map((p, i) => ({ ...p, y: type === 'falling' ? 180 - 0.5 * i
    : type === 'flat noise' ? 100 + [0.1, -0.2, 0.15, -0.1, 0.05][i % 5]
    : p.y + (type === 'down spike' && i === 35 ? -30 : type === 'up spike' && i === 35 ? 30
      : type === 'slow rolloff' ? -Math.max(0, Math.min(10, i - 30)) * 3 : 0) }));
  expect(detectAlignmentDrop(profile, 5).found).toBe(false);
});

test('noise and isolated pre-edge outliers do not replace a real step; N changes the averaging interval', () => {
  const profile = fallingTrace();
  profile.points = profile.points.map((p, i) => ({ ...p, y: p.y + [0.1, -0.2, 0.15, -0.1, 0.05][i % 5] + (i === 29 ? 8 : 0) }));
  expect(detectAlignmentDrop(profile, 5)).toMatchObject({ found: true, integrationPoints: 5 });
  expect(detectAlignmentDrop(profile, 5).drop).toBeCloseTo(20, 0);
  const result = detectAlignmentDrop(fallingTrace(), 8);
  expect(result.found).toBe(true);
  expect(result.windowEnd - result.windowStart).toBeCloseTo(0.07, 8);
});

test('the larger of two genuine steps is selected, without using another image', () => {
  const profile = fallingTrace(0);
  profile.points = profile.points.map((p, i) => ({ ...p, y: p.y - (i >= 25 ? 10 : 0) - (i >= 50 ? 25 : 0) }));
  const result = detectAlignmentDrop(profile, 5);
  expect(result.edgeX).toBeCloseTo(0.5, 8);
  expect(result.drop).toBeCloseTo(25, 8);
});

test('invalid, undersized or zero-baseline traces cannot yield a percentage', () => {
  expect(detectAlignmentDrop({ error: 'No image' })).toMatchObject({ found: false, error: 'No image' });
  expect(detectAlignmentDrop(fallingTrace(), 0).error).toMatch(/3.50/);
  expect(detectAlignmentDrop({ points: fallingTrace().points.slice(0, 10) }, 5).error).toMatch(/at least 15/);
  expect(detectAlignmentDrop({ points: Array.from({ length: 20 }, () => ({ x: 0, y: 1 })) }).error).toMatch(/Invalid/);
  expect(detectAlignmentDrop({ points: Array.from({ length: 30 }, (_, x) => ({ x, y: 0 })) }).found).toBe(false);
});

test('Web refresh rate counts recent delivery intervals and decays on stream stall', () => {
  expect(previewRefreshRate([0, 200, 400, 600, 800, 1000], 1000)).toBe(5);
  expect(previewRefreshRate([0, 200, 400, 600, 800, 1000], 1150)).toBe(5);
  expect(previewRefreshRate([0, 200, 400, 600, 800, 1000], 1400)).toBeLessThan(5);
  expect(previewRefreshRate([0, 200, 400, 600, 800, 1000], 2600)).toBe(0);
});

test('current-frame profile does not depend on any historical reference or LUT identity', () => {
  const first = alignmentProfile({ ...preview, intensity_key: 'lut-1' }, calibration, region);
  const next = alignmentProfile({ ...preview, intensity_key: 'lut-2', display_rescaled: true }, calibration, region);
  expect(next.points).toEqual(first.points);
  expect(next.referenceError).toBeUndefined();
});

test('kinetics averages wavelength columns and keeps calibrated nonlinear time', () => {
  const profile = alignmentProfile(preview, calibration, { ...region, bottomPercent: 100 });
  expect(profile.points).toEqual([{ x: 0.1, y: 2 }, { x: 0.2, y: 6 }, { x: 0.4, y: 10 }, { x: 0.8, y: 14 }, { x: 1.5, y: 18 }]);
  expect(profile.timeUnit).toBe('us');
  expect(alignmentProfile(preview, calibration, region).points).toEqual([{ x: 0.1, y: 2 }]);
});

test('out-of-view wavelengths are clipped explicitly, never extrapolated', () => {
  const profile = alignmentProfile(preview, calibration, { ...region, wavelengthMax: 900 });
  expect(profile.clipped).toBe(true);
  expect(profile.wavelengthMax).toBe(800);
  expect(alignmentProfile(preview, calibration, { ...region, wavelengthMin: 900, wavelengthMax: 1000 }).error).toMatch(/outside/);
  expect(alignmentProfile(preview, { ...calibration, width: 10 }, region).error).toMatch(/differs/);
});

test('HIS preview stays active during acquisition and pauses during file save', () => {
  const state = { connected: true, application_running: true, remoteex_status: 'idle' };
  expect(previewShouldPoll('acquisition', state, { status: 'acquiring' }, true)).toBe(true);
  expect(previewShouldPoll('alignment', { ...state, remoteex_status: 'busy' }, {}, true)).toBe(true);
  expect(previewShouldPoll('alignment', { ...state, remoteex_status: 'busy' }, { status: 'saving' }, true)).toBe(false);
  expect(previewShouldPoll('hardware', { ...state, remoteex_status: 'busy' }, {}, true)).toBe(false);
});

test('folder link preserves spaces and URL delimiters as folder text', () => {
  const folder = 'E:\\DATA_VD2\\test & x#1';
  expect(new URL(treatmentFolderUrl(folder), 'http://localhost').searchParams.get('folder')).toBe(folder);
});

test('ROI move stops at image edges while preserving dimensions', () => {
  const bounds = { x0: 20, x1: 39, y0: 10, y1: 29 };
  expect(editRoiBounds(bounds, 100, -100, 'move', 100, 80)).toEqual({ x0: 80, x1: 99, y0: 0, y1: 19 });
  expect(editRoiBounds(bounds, -100, 100, 'move', 100, 80)).toEqual({ x0: 0, x1: 19, y0: 60, y1: 79 });
});

test('ROI handles cannot cross opposite edges or leave the image', () => {
  const bounds = { x0: 20, x1: 39, y0: 10, y1: 29 };
  expect(editRoiBounds(bounds, 100, 100, 'nw', 100, 80)).toEqual({ x0: 38, x1: 39, y0: 28, y1: 29 });
  expect(editRoiBounds(bounds, 100, 100, 'se', 100, 80)).toEqual({ x0: 20, x1: 99, y0: 10, y1: 79 });
});

test.each([false, true])('dragged ROI retains exact pixel rows with descending wavelength axis: %s', descending => {
  const wavelengths = Array.from({ length: 640 }, (_, i) => 330 + i * 0.5 + i * i * 0.0001);
  if (descending) wavelengths.reverse();
  const axes = { width: 640, height: 508, wavelengths, timedelays: Array.from({ length: 508 }, (_, i) => i * i / 1000), time_unit: 'us' };
  const frame = { width: 640, height: 508, pixels_b64: window.btoa('a'.repeat(640 * 508)) };
  const bounds = { x0: 100, x1: 200, y0: 153, y1: 253 };
  const selected = alignmentProfile(frame, axes, alignmentRegionFromBounds(bounds, axes));
  expect(selected.bounds).toEqual(bounds);
  expect(selected.points).toHaveLength(101);
  expect(selected.points[0].x).toBe(axes.timedelays[153]);
  expect(selected.points[100].x).toBe(axes.timedelays[253]);
});
