import React from 'react';
import { act, render, screen, within } from '@testing-library/react';
import SupervisionMonitor from './SupervisionMonitor';

const telemetry = { payload: null, elapsed: 0, failure: true };
function payload(channel, sequence = 1) {
  const frame = { source: 'labview_supervision_ni1409', simulated: false, sequence,
    sequence_interpretation: 'software grab observation, not hardware frame counter',
    capture_session_id: 'c'.repeat(32), source_session_id: 'b'.repeat(32),
    observed_utc: '2026-11-03T11:00:00+00:00', sample_elapsed_seconds: 0.01,
    source_age_seconds: 0.1, width: 2, height: 1, pixel_type: 'U8',
    encoding: 'base64_raw_row_major', data: 'AP8=', channel,
    processing: 'raw_grab_before_legacy_interlace_bcg_profiles', hardware_acknowledged: false };
  const { data, sample_elapsed_seconds, source_age_seconds, sequence_interpretation, simulated, ...metadata } = frame;
  return { schema_version: 1, owner: 'supervision', available: true, stale: false,
    session_id: 'a'.repeat(32), age_seconds: 0.1, source_mode: 'LABVIEW_BRIDGE', ...metadata, frame };
}

let context;
beforeEach(() => {
  jest.useFakeTimers();
  context = { createImageData: jest.fn((w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })),
    putImageData: jest.fn() };
  jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
});
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });

test('permanent image uses independent live SuperVision stream even when Acquisition is unavailable', async () => {
  let callbacks;
  const close = jest.fn();
  const client = { subscribe: jest.fn((options) => { callbacks = options; return close; }) };
  const view = render(<SupervisionMonitor telemetry={telemetry} videoClient={client} />);
  expect(callbacks.channel).toBeUndefined();  // Follow source, never pin the old channel2.
  await act(async () => callbacks.onFrame(payload(1)));
  const monitor = screen.getByRole('region', { name: 'Image laser permanente' });
  expect(within(monitor).getByRole('img', { name: 'Dernière image Image laser' })).toBeInTheDocument();
  expect(within(monitor).getByRole('status')).toHaveTextContent('Image récente');
  expect(within(monitor).getByText(/U8 brut · canal 1/)).toBeInTheDocument();
  expect([...context.putImageData.mock.calls[0][0].data]).toEqual([0, 0, 0, 255, 255, 255, 255, 255]);
  await act(async () => callbacks.onError(new Error('Stream interrupted')));
  expect(within(monitor).getByRole('img')).toBeInTheDocument();
  expect(within(monitor).getByRole('status')).toHaveTextContent('dernière image conservée');
  view.unmount();
  expect(close).toHaveBeenCalledTimes(1);
});

test('source-selected camera change displays new channel without choosing or commanding hardware', async () => {
  let callbacks;
  const client = { subscribe: jest.fn((options) => { callbacks = options; }) };
  const view = render(<SupervisionMonitor telemetry={telemetry} videoClient={client} />);
  await act(async () => callbacks.onFrame(payload(2)));
  await act(async () => callbacks.onFrame(payload(1)));
  expect(screen.getByText(/U8 brut · canal 1/)).toBeInTheDocument();
  expect(context.putImageData).toHaveBeenCalledTimes(2);
  expect(client.subscribe).toHaveBeenCalledTimes(1);
  expect(Object.keys(client)).toEqual(['subscribe']);
  view.unmount();
});
