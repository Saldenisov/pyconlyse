import { act, renderHook } from '@testing-library/react';
import useFrameDisplayRate, { createFrameDisplayMeter } from './useFrameDisplayRate';

test('display rate measures new completed frames, not duplicate redraws', () => {
  const meter = createFrameDisplayMeter();
  for (let i = 0; i <= 5; i += 1) meter.record(`frame-${i}`, i * 200);
  expect(meter.rate(1000)).toBe(5);
  meter.record('frame-5', 1100); // LUT / overlay / cached frame redraw.
  expect(meter.rate(1100)).toBe(5);
  expect(meter.rate(1400)).toBeLessThan(5); // An overdue frame still lowers Hz.
  expect(meter.rate(2500)).toBe(0);
  meter.record('frame-6', 4500);
  expect(meter.rate(4500)).toBe(0); // A new burst needs two observations.
});

test('a steady 5 Hz stream does not become 4.7 Hz between frame arrivals', () => {
  const meter = createFrameDisplayMeter();
  for (let i = 0; i < 15; i += 1) meter.record(i, i * 200);
  for (const now of [2800, 2850, 2900, 2950, 2999]) expect(meter.rate(now)).toBe(5);
  expect(meter.rate(3200)).toBeLessThan(5);
  expect(meter.rate(4300)).toBe(0);
});

test.each([4, 4.7, 5])('a genuine %s Hz stream is reported without rounding it up to the target', hz => {
  const meter = createFrameDisplayMeter();
  for (let i = 0; i < 12; i += 1) meter.record(i, i * 1000 / hz);
  expect(meter.rate(11 * 1000 / hz + 50)).toBeCloseTo(hz, 6);
});

test('same-looking pixels in different frames still count; resets discard old sessions', () => {
  const meter = createFrameDisplayMeter();
  meter.record({ pixels: 'same' }, 0);
  meter.record({ pixels: 'same' }, 1000);
  expect(meter.rate(1000)).toBe(1);
  meter.reset();
  meter.record('sequence-1', 1100);
  expect(meter.rate(1100)).toBe(0);
});

test('counter falls to zero without another frame or request and clears its timer', () => {
  jest.useFakeTimers();
  try {
    const view = renderHook(() => useFrameDisplayRate('camera'));
    act(() => view.result.current.frameDisplayed(1));
    act(() => jest.advanceTimersByTime(200));
    act(() => view.result.current.frameDisplayed(2));
    expect(view.result.current.hz).toBe(5);
    act(() => jest.advanceTimersByTime(1600));
    expect(view.result.current.hz).toBe(0);
    view.unmount();
    expect(jest.getTimerCount()).toBe(0);
  } finally { jest.useRealTimers(); }
});

test('source changes and disabled views cannot inherit old or late frame rates', () => {
  jest.useFakeTimers();
  try {
    const view = renderHook(({ source, enabled }) => useFrameDisplayRate(source, enabled),
      { initialProps: { source: 'A', enabled: true } });
    act(() => view.result.current.frameDisplayed(1, 'A'));
    act(() => jest.advanceTimersByTime(200));
    act(() => view.result.current.frameDisplayed(2, 'A'));
    expect(view.result.current.hz).toBe(5);
    view.rerender({ source: 'B', enabled: true });
    act(() => view.result.current.frameDisplayed(3, 'A'));
    expect(view.result.current.hz).toBe(0);
    act(() => view.result.current.frameDisplayed(1, 'B'));
    act(() => jest.advanceTimersByTime(200));
    act(() => view.result.current.frameDisplayed(2, 'B'));
    expect(view.result.current.hz).toBe(5);
    view.rerender({ source: 'B', enabled: false });
    expect(view.result.current.hz).toBe(0);
    expect(jest.getTimerCount()).toBe(0);
    view.unmount();
  } finally { jest.useRealTimers(); }
});
