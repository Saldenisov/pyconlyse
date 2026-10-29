import React from 'react';
import { act, render, screen } from '@testing-library/react';
import AcquisitionVideo from './AcquisitionVideo';

function payload(sequence = 1, capture = 'c'.repeat(32)) {
  const frame = { source: 'python_supervision_ni1409', simulated: false, sequence,
    sequence_interpretation: 'software grab observation, not hardware frame counter',
    capture_session_id: capture, observed_utc: '2026-10-26T12:00:00+00:00',
    sample_elapsed_seconds: 0.01, source_age_seconds: 0.1, width: 2, height: 1,
    pixel_type: 'U8', encoding: 'base64_raw_row_major', data: 'AP8=', channel: 2,
    processing: 'raw_grab_before_legacy_interlace_bcg_profiles', hardware_acknowledged: false };
  const { data, sample_elapsed_seconds, source_age_seconds, sequence_interpretation, simulated, ...metadata } = frame;
  return { schema_version: 1, owner: 'supervision', available: true, stale: false,
    session_id: 'a'.repeat(32), age_seconds: 0.2, source_mode: 'PYTHON_NATIVE', ...metadata, frame };
}

let context;
beforeEach(() => {
  jest.useFakeTimers();
  context = { createImageData: jest.fn((width, height) => ({ data: new Uint8ClampedArray(width * height * 4) })),
    putImageData: jest.fn() };
  jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
});
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });
const flush = async () => { await act(async () => { await Promise.resolve(); }); };
const advance = async (ms) => { await act(async () => { jest.advanceTimersByTime(ms); }); };

test('renders actual grayscale pixels and read-only metadata after a current validated frame', async () => {
  const client = { video: jest.fn().mockResolvedValue(payload()) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  await flush();
  expect(screen.getByRole('status')).toHaveTextContent('Image récente');
  expect(screen.getByRole('img')).toHaveAttribute('width', '2');
  expect([...context.putImageData.mock.calls[0][0].data]).toEqual([0, 0, 0, 255, 255, 255, 255, 255]);
  expect(screen.getByText(/U8 brut · canal 2/)).toHaveTextContent('observation 1');
  expect(client.video).toHaveBeenCalledTimes(1);
  unmount();
});

test('repeated sequence cannot refresh a frozen image, while a new capture may restart at sequence1', async () => {
  const client = { video: jest.fn().mockResolvedValue(payload()) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  await flush();
  await advance(1000);
  expect(client.video).toHaveBeenCalledTimes(2);
  expect(screen.getByRole('status')).toHaveTextContent('Image récente');
  await advance(1000);
  expect(screen.getByRole('status')).toHaveTextContent('Image périmée');
  expect(screen.getByRole('img')).toBeInTheDocument();
  expect(screen.getByRole('img')).toHaveAccessibleName('Dernière image caméra SuperVision');
  expect(context.putImageData).toHaveBeenCalledTimes(1);
  client.video.mockResolvedValue(payload(1, 'd'.repeat(32)));
  await advance(1000);
  expect(screen.getByRole('status')).toHaveTextContent('Image récente');
  expect(screen.getByRole('img')).toBeInTheDocument();
  unmount();
});

test('lost read and unavailable response retain last pixels with explicit source status', async () => {
  const client = { video: jest.fn().mockResolvedValueOnce(payload()).mockRejectedValueOnce(new Error('receiver absent'))
    .mockResolvedValue({ schema_version: 1, owner: 'supervision', available: false, frame: null }) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  await flush();
  const canvas = screen.getByRole('img');
  await advance(1000);
  expect(screen.getByRole('status')).toHaveTextContent('Vidéo indisponible');
  expect(screen.getByRole('img')).toBe(canvas);
  expect(screen.getByRole('status')).toHaveTextContent('dernière image conservée');
  expect(screen.getByRole('alert')).toHaveTextContent('receiver absent');
  await advance(1000);
  expect(screen.getByRole('status')).toHaveTextContent('Vidéo indisponible');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('img')).toBe(canvas);
  expect(context.putImageData).toHaveBeenCalledTimes(1);
  unmount();
});

test('one slow in-flight request cannot cause overlapping reads; HTTP delay consumes image age', async () => {
  let finish;
  const client = { video: jest.fn().mockImplementation(() => new Promise((resolve) => { finish = resolve; })) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  await advance(4000);
  expect(client.video).toHaveBeenCalledTimes(1);
  await act(async () => { finish(payload()); });
  expect(screen.getByRole('status')).toHaveTextContent('Image périmée');
  expect(screen.getByRole('img')).toBeInTheDocument();
  unmount();
});

test('unmount aborts only the read, clears poll/age timers and discards a late response', async () => {
  let finish;
  const client = { video: jest.fn().mockImplementation(() => new Promise((resolve) => { finish = resolve; })) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  const signal = client.video.mock.calls[0][0];
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => { finish(payload()); });
  await advance(10000);
  expect(client.video).toHaveBeenCalledTimes(1);
  expect(context.putImageData).not.toHaveBeenCalled();
});

test('same capture sequence regression and malformed frames never display as current', async () => {
  const client = { video: jest.fn().mockResolvedValueOnce(payload(2)).mockResolvedValueOnce(payload(1))
    .mockResolvedValue({ ...payload(3), width: 99 }) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  await flush();
  await advance(1000);
  expect(screen.getByRole('alert')).toHaveTextContent('Séquence vidéo antérieure');
  expect(screen.getByRole('img')).toBeInTheDocument();
  expect(screen.getByText(/U8 brut/)).toHaveTextContent('observation 2');
  await advance(1000);
  expect(screen.getByRole('status')).toHaveTextContent('Vidéo indisponible');
  expect(screen.getByRole('img')).toBeInTheDocument();
  expect(screen.getByText(/U8 brut/)).toHaveTextContent('observation 2');
  unmount();
});

test('disabled viewer does not request pixels', async () => {
  const client = { video: jest.fn() };
  const { unmount } = render(<AcquisitionVideo client={client} enabled={false} />);
  await flush();
  expect(client.video).not.toHaveBeenCalled();
  expect(screen.getByRole('status')).toHaveTextContent('Vidéo indisponible');
  unmount();
});

test('expired source keeps canvas mounted until next valid image replaces pixels', async () => {
  const client = { video: jest.fn().mockResolvedValueOnce(payload(1))
    .mockResolvedValueOnce({ schema_version: 1, owner: 'supervision', available: false,
      stale: true, sequence: 1, age_seconds: 3, frame: null })
    .mockResolvedValue(payload(2)) };
  const { unmount } = render(<AcquisitionVideo client={client} />);
  await flush();
  const canvas = screen.getByRole('img');
  await advance(1000);
  expect(screen.getByRole('status')).toHaveTextContent('Image périmée');
  expect(screen.getByRole('img')).toBe(canvas);
  expect(screen.getByText(/U8 brut/)).toHaveTextContent('observation 1');
  await advance(1000);
  expect(screen.getByRole('img')).toBe(canvas);
  expect(screen.getByText(/U8 brut/)).toHaveTextContent('observation 2');
  expect(context.putImageData).toHaveBeenCalledTimes(2);
  unmount();
});

test('successful fallback polling requests the next image after40ms at25Hz and80ms at12.5Hz', async () => {
  const client = { video: jest.fn().mockResolvedValue(payload()) };
  const { unmount, rerender } = render(<AcquisitionVideo client={client} targetFps={25} />);
  await flush();
  await advance(39);
  expect(client.video).toHaveBeenCalledTimes(1);
  await advance(1);
  expect(client.video).toHaveBeenCalledTimes(2);
  rerender(<AcquisitionVideo client={client} targetFps={12.5} />);
  await flush();
  const before = client.video.mock.calls.length;
  await advance(79);
  expect(client.video).toHaveBeenCalledTimes(before);
  await advance(1);
  expect(client.video).toHaveBeenCalledTimes(before + 1);
  unmount();
});

test('subscribed stream does not create polling reads and retains canvas through source status events', async () => {
  let callbacks;
  const unsubscribe = jest.fn();
  const client = { video: jest.fn(), subscribe: jest.fn((options) => { callbacks = options; return unsubscribe; }) };
  const { unmount } = render(<AcquisitionVideo client={client} channel={2} targetFps={25} />);
  expect(client.subscribe).toHaveBeenCalledWith(expect.objectContaining({ channel: 2, targetFps: 25 }));
  await act(async () => { callbacks.onFrame(payload(1)); });
  const canvas = screen.getByRole('img');
  await act(async () => { callbacks.onFrame(payload(2)); });
  await act(async () => { callbacks.onError(new Error('stream disconnected')); });
  expect(screen.getByRole('img')).toBe(canvas);
  expect(screen.getByRole('status')).toHaveTextContent('dernière image conservée');
  expect(client.video).not.toHaveBeenCalled();
  unmount();
  expect(unsubscribe).toHaveBeenCalledTimes(1);
  expect(callbacks.signal.aborted).toBe(true);
  await act(async () => { callbacks.onFrame(payload(3)); });
  expect(context.putImageData).toHaveBeenCalledTimes(2);
});

test('raw-channel mismatch cannot relabel an existing image and subscription absence uses serial fallback', async () => {
  const client = { video: jest.fn().mockResolvedValue(payload()),
    subscribe: jest.fn(() => { throw new Error('EventSource unavailable'); }) };
  const { unmount } = render(<AcquisitionVideo client={client} channel={1} />);
  await flush();
  expect(screen.getByRole('alert')).toHaveTextContent('canal caméra demandé');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(client.video).toHaveBeenCalledTimes(1);
  expect(client.video).toHaveBeenCalledWith(expect.any(AbortSignal), { channel: 1 });
  unmount();
});
