import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import io from 'socket.io-client';
import '@testing-library/jest-dom';
import DSNetioPDUClient from './DSNetioPDUClient';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

jest.mock('socket.io-client', () => jest.fn());
jest.mock('../api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const deviceName = 'manip/SD2/PDU_SD2';
const originalFetch = global.fetch;
const response = (status, payload) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
});
const readings = (state = 0) => ({
  success: true, state: 'ON', outputs: [
    { id: 1, name: 'StreakCamSpec', state: 0 },
    { id: 2, name: 'DG645', state },
    { id: 3, name: 'Power_control', state: 0 },
    { id: 4, name: 'Power_current', state: 0 },
  ],
});

beforeEach(() => {
  fetchWithHardwareApproval.mockReset();
  io.mockReset();
  io.mockReturnValue({
    on: jest.fn(), disconnect: jest.fn(), emit: jest.fn(), connect: jest.fn(),
  });
  global.fetch = jest.fn().mockResolvedValue(response(200, readings()));
});
afterEach(() => { global.fetch = originalFetch; });

async function switchOutput() {
  render(<DSNetioPDUClient deviceNames={[deviceName]} />);
  const output = (await screen.findByText('2. DG645')).closest('.output-control');
  const toggle = within(output).getByRole('checkbox');
  fireEvent.click(toggle);
  return toggle;
}

test('shows server rejection without a login action and does not replay the command', async () => {
  fetchWithHardwareApproval.mockResolvedValue(response(401, {
    msg: 'Missing or invalid authentication credentials',
  }));
  const toggle = await switchOutput();
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Missing or invalid authentication credentials'
  );
  expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  expect(toggle).not.toBeChecked();
  expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test.each([
  [403, { msg: 'Operator role required' }, 'Operator role required'],
  [409, { success: false, error: 'PDU readback does not match' }, 'PDU readback does not match'],
])('preserves the actual HTTP %s rejection', async (status, payload, message) => {
  fetchWithHardwareApproval.mockResolvedValue(response(status, payload));
  const toggle = await switchOutput();
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
  expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  expect(toggle).not.toBeChecked();
  expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1);
});

test('includes HTTP status when an upstream error is not JSON', async () => {
  fetchWithHardwareApproval.mockResolvedValue({
    ok: false, status: 502, json: async () => { throw new SyntaxError('Not JSON'); },
  });
  await switchOutput();
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 502');
});

test('updates the switch only after successful command and matching readback', async () => {
  fetchWithHardwareApproval.mockResolvedValue(response(200, { success: true }));
  global.fetch.mockResolvedValueOnce(response(200, readings()))
    .mockResolvedValueOnce(response(200, readings()))
    .mockResolvedValueOnce(response(200, readings(1)));
  await switchOutput();
  await waitFor(() => expect(within(screen.getByText('2. DG645').closest('.output-control')).getByRole('checkbox')).toBeChecked());
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1);
});

async function realtimeClient() {
  render(<DSNetioPDUClient deviceNames={[deviceName]} />);
  await screen.findByText('2. DG645');
  const socket = io.mock.results[0].value;
  return {
    socket,
    handler: (name) => socket.on.mock.calls.find(([event]) => event === name)[1],
  };
}

test('preserves its connection and readings when equivalent device names are rendered again', async () => {
  const view = render(<DSNetioPDUClient deviceNames={[deviceName]} />);
  await screen.findByText('2. DG645');
  const socket = io.mock.results[0].value;
  view.rerender(<DSNetioPDUClient deviceNames={[deviceName]} />);
  expect(io).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(socket.disconnect).not.toHaveBeenCalled();
  view.unmount();
  expect(socket.disconnect).toHaveBeenCalledTimes(1);
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('keeps a device fault visible after initial readings have loaded', async () => {
  const { handler } = await realtimeClient();
  act(() => { handler('device_error')({ device: deviceName, error: 'readback unavailable' }); });
  expect(screen.getByRole('alert')).toHaveTextContent('readback unavailable');
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('shows connection rejection without probing login or sending a hardware command', async () => {
  const { handler } = await realtimeClient();
  global.fetch.mockResolvedValue(response(401, { msg: 'Token has expired' }));
  await act(async () => { await handler('connect_error')(new Error('Connection rejected by server')); });
  expect(screen.getByRole('alert')).toHaveTextContent('Connection rejected by server');
  expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Stop Monitoring' })).toBeDisabled();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('shows transport errors and supports reconnecting', async () => {
  const { socket, handler } = await realtimeClient();
  global.fetch.mockResolvedValue(response(200, { authenticated: true }));
  await act(async () => { await handler('connect_error')(new Error('websocket error')); });
  expect(screen.getByRole('alert')).toHaveTextContent('websocket error');
  expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Reconnect' }));
  expect(screen.getByRole('button', { name: 'Reconnect' }).closest('.connection-status')).not.toBeNull();
  expect(socket.connect).toHaveBeenCalledTimes(1);
  act(() => { handler('connect')(); });
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Stop Monitoring' })).toBeEnabled();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('clears a disconnect error when the socket reconnects without checking a session', async () => {
  const { handler } = await realtimeClient();
  act(() => { handler('disconnect')(); });
  expect(screen.getByRole('alert')).toHaveTextContent('connection lost');
  act(() => { handler('connect')(); });
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Stop Monitoring' })).toBeEnabled();
});

test('restores PDU monitoring and refreshes readings after a connection loss', async () => {
  const { socket, handler } = await realtimeClient();
  act(() => { handler('connect')(); });
  expect(socket.emit).toHaveBeenCalledWith('subscribe_device', { device: deviceName });

  act(() => { handler('disconnect')(); });
  expect(screen.getByRole('button', { name: 'Stop Monitoring' })).toBeDisabled();

  await act(async () => { handler('connect')(); });
  expect(socket.emit.mock.calls.filter(([event]) => event === 'subscribe_device')).toHaveLength(2);
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Stop Monitoring' })).toBeEnabled();
});

test('keeps selected PDU subscriptions in sync while monitoring', async () => {
  const { socket, handler } = await realtimeClient();
  socket.connected = true;
  act(() => { handler('connect')(); });

  fireEvent.click(screen.getByRole('button', { name: 'Hide All' }));
  expect(socket.emit).toHaveBeenCalledWith('unsubscribe_device', { device: deviceName });
  fireEvent.click(screen.getByRole('button', { name: 'Show All' }));
  expect(socket.emit.mock.calls.filter(([event]) => event === 'subscribe_device')).toHaveLength(2);

  act(() => { handler('disconnect')(); });
  await act(async () => { handler('connect')(); });
  expect(socket.emit.mock.calls.filter(([event]) => event === 'subscribe_device')).toHaveLength(3);
});

test('updates an already open PDU client when another page changes an outlet', async () => {
  const { socket, handler } = await realtimeClient();
  act(() => { handler('connect')(); });
  expect(socket.emit).toHaveBeenCalledWith('subscribe_device', { device: deviceName });
  const output = screen.getByText('3. Power_control').closest('.output-control');
  expect(within(output).getByRole('checkbox')).not.toBeChecked();
  act(() => {
    handler('device_update')({ device: deviceName, state: 'ON', outputs: readings().outputs.map(
      item => item.id === 3 ? { ...item, state: 1 } : item
    ) });
  });
  expect(within(output).getByRole('checkbox')).toBeChecked();
});

test('reads current outlets before a toggle and preserves changes from another page', async () => {
  fetchWithHardwareApproval.mockResolvedValue(response(200, { success: true }));
  const latest = {
    ...readings(),
    outputs: readings().outputs.map(item => item.id === 3 ? { ...item, state: 1 } : item),
  };
  global.fetch.mockResolvedValueOnce(response(200, readings()))
    .mockResolvedValueOnce(response(200, latest))
    .mockResolvedValueOnce(response(200, {
      ...latest,
      outputs: latest.outputs.map(item => item.id === 2 ? { ...item, state: 1 } : item),
    }));
  await switchOutput();
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(within(screen.getByText('2. DG645').closest('.output-control')).getByRole('checkbox')).toBeChecked());
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body).args).toEqual([0, 1, 1, 0]);
});

test('refreshes an outdated OFF switch without sending a redundant command', async () => {
  const latest = {
    ...readings(),
    outputs: readings().outputs.map(item => item.id === 3 ? { ...item, state: 1 } : item),
  };
  global.fetch.mockResolvedValueOnce(response(200, readings()))
    .mockResolvedValueOnce(response(200, latest));
  render(<DSNetioPDUClient deviceNames={[deviceName]} />);
  const output = (await screen.findByText('3. Power_control')).closest('.output-control');
  fireEvent.click(within(output).getByRole('checkbox'));
  expect(await within(output).findByText('ON')).toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});
