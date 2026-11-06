import { act, render, screen } from '@testing-library/react';
import CameraClient from './CameraClient';

test('camera preview displays actual draw frequency and zero after grabbing stops, without hardware commands', async () => {
  jest.useFakeTimers();
  const originalFetch = global.fetch;
  let grabbing = true;
  const context = { createImageData: () => ({ data: new Uint8ClampedArray(4) }), putImageData: jest.fn() };
  const canvas = jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
  global.fetch = jest.fn(async url => ({ json: async () => url.endsWith('/cameras')
    ? { success: true, cameras: [{ name: 'test/camera/one', state: 'ON' }] }
    : url.endsWith('/info') ? { success: true, camera_info: { state: 'ON', isgrabbing: grabbing, width: 1, height: 1 } }
      : { success: true, image: [[10], [20], [30]] } }));
  const view = render(<CameraClient />);
  try {
    await screen.findByText('Live Preview');
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 0.0 Hz');
    await act(async () => { jest.advanceTimersByTime(1000); });
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 1.0 Hz');
    expect(context.putImageData).toHaveBeenCalledTimes(2);
    grabbing = false;
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByLabelText('Frame display rate')).toHaveTextContent('Display 0.0 Hz');
    expect(global.fetch.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  } finally {
    view.unmount(); canvas.mockRestore(); global.fetch = originalFetch; jest.useRealTimers();
  }
});
