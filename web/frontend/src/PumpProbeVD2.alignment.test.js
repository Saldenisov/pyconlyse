import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

import PumpProbeVD2, { EditableField, fetchVd2, refreshVd2Passive, TIME_RANGES, Vd2PhaseProtocol } from './PumpProbeVD2';

jest.mock('./useVd2ServerWorkspace',()=>({...jest.requireActual('./useVd2ServerWorkspace'),__esModule:true,
  default:()=>({ready:true,message:'Session saved on server.',error:'',history:async()=>[],restore:async()=>{}})}));

const originalFetch = global.fetch;

beforeEach(()=>window.localStorage.clear());

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
