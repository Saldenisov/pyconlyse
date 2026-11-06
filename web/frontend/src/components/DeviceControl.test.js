import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import io from 'socket.io-client';
import DeviceControl from './DeviceControl';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

jest.mock('socket.io-client', () => jest.fn());
jest.mock('../api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const originalFetch = global.fetch;
const device = 'test/device/one';
const response = (payload) => ({ ok: true, status: 200, json: async () => payload });

beforeEach(() => {
  io.mockReturnValue({ on: jest.fn(), disconnect: jest.fn(), emit: jest.fn() });
  global.fetch = jest.fn((url) => Promise.resolve(response(
    url.endsWith('/attributes')
      ? { success: true, attributes: {} }
      : { success: true, device_info: { name: device, state: 'ON', class: 'FakeDevice' } }
  )));
});

afterEach(() => { global.fetch = originalFetch; });

test('refreshes loaded attributes on a command receipt without reconnecting or replaying a command', async () => {
  const view = render(<DeviceControl deviceName={device} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Load Attributes' }));
  await screen.findByRole('button', { name: 'Refresh Attributes' });
  const socket = io.mock.results[0].value;
  const commandResult = socket.on.mock.calls.find(([event]) => event === 'command_result')[1];
  await act(async () => { commandResult({ device }); });
  await waitFor(() => expect(global.fetch.mock.calls.filter(([url]) => url.endsWith('/attributes'))).toHaveLength(2));
  expect(io).toHaveBeenCalledTimes(1);
  expect(socket.disconnect).not.toHaveBeenCalled();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  view.unmount();
  const reads = global.fetch.mock.calls.length;
  act(() => { commandResult({ device }); });
  expect(global.fetch).toHaveBeenCalledTimes(reads);
  expect(socket.disconnect).toHaveBeenCalledTimes(1);
});
