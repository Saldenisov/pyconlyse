import { act, renderHook } from '@testing-library/react';
import useElyseUiState from './useElyseUiState';

const CHOICES = ['synchro', 'fluides'];
beforeEach(() => localStorage.clear());
afterEach(() => jest.restoreAllMocks());

test('stores only a validated selection and restores it on remount', () => {
  const first = renderHook(() => useElyseUiState('test.tab', 'synchro', CHOICES));
  act(() => {
    first.result.current[1]('fluides');
    expect(localStorage.getItem('test.tab')).toBe('fluides');
  });
  first.unmount();
  const second = renderHook(() => useElyseUiState('test.tab', 'synchro', CHOICES));
  expect(second.result.current[0]).toBe('fluides');
  act(() => second.result.current[1]('retired-command'));
  expect(second.result.current[0]).toBe('synchro');
  expect(localStorage.getItem('test.tab')).toBe('synchro');
});

test('ignores stale, invalid or non-navigation cached content', () => {
  localStorage.setItem('test.tab', '{"command":"start","authorized":true}');
  const hook = renderHook(() => useElyseUiState('test.tab', 'synchro', CHOICES));
  expect(hook.result.current[0]).toBe('synchro');
  expect(localStorage.getItem('test.tab')).toBe('synchro');
});

test('disabled persistence neither reads nor overwrites existing preference', () => {
  localStorage.setItem('test.tab', 'fluides');
  const hook = renderHook(() => useElyseUiState('test.tab', 'synchro', CHOICES, false));
  expect(hook.result.current[0]).toBe('synchro');
  act(() => hook.result.current[1]('fluides'));
  act(() => hook.result.current[1]('synchro'));
  expect(localStorage.getItem('test.tab')).toBe('fluides');
});

test('blocked storage keeps navigation usable without claiming persistence', () => {
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
  jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); });
  const hook = renderHook(() => useElyseUiState('test.tab', 'synchro', CHOICES));
  expect(hook.result.current[0]).toBe('synchro');
  act(() => hook.result.current[1]('fluides'));
  expect(hook.result.current[0]).toBe('fluides');
});
