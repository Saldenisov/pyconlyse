import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import io from 'socket.io-client';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import ITestPSUClient from './ITestPSUClient';

jest.mock('socket.io-client', () => jest.fn());
jest.mock('../api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const device = 'elyse/pdu/itest';
const originalFetch = global.fetch;
const response = (body) => ({ ok: true, status: 200, json: async () => body });
const slots = {
  ids: [1], names: ['T1-1'], states: [0], currents_setpoint: [0],
  currents_meas: [0], current_limits: [-15, 15],
};

function handler(socket, event) {
  return socket.on.mock.calls.find(([name]) => name === event)[1];
}

beforeEach(() => {
  io.mockReset();
  io.mockImplementation(() => ({ on: jest.fn(), emit: jest.fn(), disconnect: jest.fn() }));
  fetchWithHardwareApproval.mockReset();
  global.fetch = jest.fn((url) => Promise.resolve(response(
    url.endsWith('/tab_config')
      ? { tab_configs: { V0: { slots: [1], defaults: {}, enabled: true } } }
      : slots
  )));
});

afterEach(() => { global.fetch = originalFetch; });

test('subscribes on connection without a manual monitor control or hardware command', async () => {
  render(<ITestPSUClient deviceName={device} />);
  await screen.findByText(`iTest PSU: ${device}`);
  const socket = io.mock.results[0].value;
  act(() => { handler(socket, 'connect')(); });
  expect(socket.emit).toHaveBeenCalledWith('subscribe_device', { device });
  act(() => { handler(socket, 'subscribed')({ device }); });
  expect(screen.getByRole('status')).toHaveTextContent('Monitoring automatically');
  expect(screen.queryByRole('button', { name: /Monitoring/ })).not.toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  expect(global.fetch.mock.calls.every(([, options]) => !options.method || options.method === 'GET')).toBe(true);
});

test('restores monitoring after reconnect and accepts fresh measured values', async () => {
  render(<ITestPSUClient deviceName={device} />);
  await screen.findByText(`iTest PSU: ${device}`);
  const socket = io.mock.results[0].value;
  act(() => {
    handler(socket, 'connect')();
    handler(socket, 'subscribed')({ device });
    handler(socket, 'disconnect')();
  });
  expect(screen.getByRole('status')).toHaveTextContent('Waiting for monitoring');
  act(() => { handler(socket, 'connect')(); });
  expect(socket.emit.mock.calls.filter(([event]) => event === 'subscribe_device')).toHaveLength(2);
  act(() => { handler(socket, 'device_error')({ device, error: 'Temporary read failure' }); });
  expect(screen.getByText('Temporary read failure')).toBeInTheDocument();
  act(() => { handler(socket, 'device_update')({ device, slots: [
    { id: 1, name: 'T1-1', state: false, current_setpoint: 0, current_measured: 1.234 },
  ] }); });
  expect(screen.getByRole('status')).toHaveTextContent('Monitoring automatically');
  expect(screen.getByText('1.234 A')).toBeInTheDocument();
  expect(screen.queryByText('Temporary read failure')).not.toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('ignores a disposed connection after changing device or unmounting', async () => {
  const view = render(<ITestPSUClient deviceName={device} />);
  await screen.findByText(`iTest PSU: ${device}`);
  const old = io.mock.results[0].value;
  view.rerender(<ITestPSUClient deviceName="test/pdu/second" />);
  await waitFor(() => expect(io).toHaveBeenCalledTimes(2));
  const current = io.mock.results[1].value;
  act(() => { handler(old, 'connect')(); });
  expect(old.emit).not.toHaveBeenCalled();
  act(() => { handler(current, 'connect')(); });
  expect(current.emit).toHaveBeenCalledWith('subscribe_device', { device: 'test/pdu/second' });
  view.unmount();
  const count = current.emit.mock.calls.length;
  act(() => { handler(current, 'connect')(); });
  expect(current.emit).toHaveBeenCalledTimes(count);
  expect(current.disconnect).toHaveBeenCalledTimes(1);
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('shows connection errors and waits for Socket.IO to reconnect', async () => {
  render(<ITestPSUClient deviceName={device} />);
  await screen.findByText(`iTest PSU: ${device}`);
  const socket = io.mock.results[0].value;
  act(() => { handler(socket, 'connect_error')(new Error('Connection unavailable')); });
  expect(screen.getByText('Connection unavailable')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Waiting for monitoring');
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('right-click saves a channel step shared by Alignment and Equipment; each arrow sends a bounded setpoint', async () => {
  const storageKey = `pyconlyse.itest.current-step.${device}.1`;
  window.localStorage.removeItem(storageKey);
  let setpoint = 1;
  global.fetch.mockImplementation(async (url) => response(url.endsWith('/tab_config')
    ? { tab_configs: { V0: { slots: [1, 2] }, VD2: { slots: [1, 2] } } }
    : { ids: [1, 2], names: ['T1-1', 'T1-2'], states: [0, 1], currents_setpoint: [setpoint, 2],
      currents_meas: [0, 2], current_limits: [0, 2, 0, 15] }));
  fetchWithHardwareApproval.mockImplementation(async (_url, request) => {
    setpoint = JSON.parse(request.body).value;
    return response({ success: true, slot_id: 1, current_setpoint: setpoint });
  });

  const { unmount: unmountAlignment } = render(<ITestPSUClient deviceName={device.toUpperCase()} fixedTab="VD2" compact />);
  const increase = await screen.findByRole('button', { name: 'Increase T1-1 current' });
  expect(fireEvent.contextMenu(increase)).toBe(false);
  expect(screen.getByRole('group', { name: 'T1-1 current step options' })).toBeVisible();
  expect(screen.getByRole('button', { name: '0.1 A', exact: true })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: '1 A', exact: true }));
  expect(screen.getByRole('button', { name: 'T1-2 current step: 0.1 A' })).toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();

  fireEvent.click(increase);
  const input = screen.getByRole('spinbutton', { name: 'T1-1 current (A)' });
  await waitFor(() => expect(input).toHaveValue(2));
  expect(increase).toBeDisabled();
  expect(fetchWithHardwareApproval).toHaveBeenCalledWith(
    `/api/device/itest/${device.toUpperCase()}/slot/1/current`,
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ value: 2 }) }),
  );
  expect(screen.getAllByRole('checkbox')[0]).not.toBeChecked();
  unmountAlignment();

  const { unmount: unmountEquipment } = render(<ITestPSUClient deviceName={device} />);
  try {
    const decrease = await screen.findByRole('button', { name: 'Decrease T1-1 current' });
    expect(screen.getByRole('button', { name: 'T1-1 current step: 1 A' })).toBeInTheDocument();
    fireEvent.click(decrease);
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'T1-1 current (A)' })).toHaveValue(1));
    expect(fetchWithHardwareApproval).toHaveBeenLastCalledWith(
      `/api/device/itest/${device}/slot/1/current`,
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ value: 1 }) }),
    );
    expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(2);
  } finally {
    unmountEquipment();
    window.localStorage.removeItem(storageKey);
  }
});
