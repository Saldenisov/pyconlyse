import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DAQmxClients, { formatDAQmxValue, groupDAQmxChannels } from './DAQmxClients';
import { fetchWithHardwareApproval } from './api/csrfRequest';

jest.mock('./api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const response = (status, payload) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
});

const channels = [
  {
    name: 'Laser_SC Shutter', kind: 'DigitalOut', value: -1, value_known: false,
    physical_channel: 'TRANCON-DAQ/port0/line0', unit: '', alarm: false,
  },
  {
    name: 'Faraday Cup Status', kind: 'DigitalIn', value: 1, value_known: true,
    physical_channel: 'TRANCON-DAQ/port0/line4', unit: '', alarm: false,
  },
  {
    name: 'Power Status', kind: 'AIcurrent', value: 120, value_known: true,
    physical_channel: 'TRANCON-DAQ/ai0', unit: 'uA', alarm: false,
    limit_alarm_min: 100, limit_alarm_max: 1000,
  },
  {
    name: 'ELYSE Pulse Counter', kind: 'DigitalCounter', value: 42, value_known: true,
    physical_channel: '/TRANCON-DAQ/PFI0', counter: 'TRANCON-DAQ/ctr0', unit: 'pulses',
  },
];

const latest = {
  success: true,
  state: 'ON',
  latest: { timestamp: 10.5, source: 'direct', device: 'TRANCON-DAQ' },
  device_info: { name: 'TRANCON-DAQ', product_type: 'PCIe-6320', serial_num: 29471170 },
  channels,
};

const physicalDevice = [{
  name: 'control/DAQ/TRANCON-DAQ', class: 'DS_DAQmx', state: 'ON', available: true,
}];

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue(response(200, latest));
  fetchWithHardwareApproval.mockReset();
  fetchWithHardwareApproval.mockResolvedValue(response(200, { success: true, value: 1 }));
});

afterEach(() => { delete global.fetch; });

test('groups the physical channel types and formats engineering units', () => {
  const grouped = groupDAQmxChannels(channels);
  expect(grouped.outputs.map((channel) => channel.name)).toEqual(['Laser_SC Shutter']);
  expect(grouped.inputs).toHaveLength(1);
  expect(grouped.analog).toHaveLength(1);
  expect(grouped.counters).toHaveLength(1);
  expect(formatDAQmxValue(channels[2])).toBe('120 uA');
  expect(formatDAQmxValue(channels[0])).toBe('Unknown');
});

test('renders direct card controls and sends an explicit digital-output command', async () => {
  render(<DAQmxClients deviceOverride={physicalDevice} />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Open card' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Open card' }));

  expect(await screen.findByText('PCIe-6320')).toBeInTheDocument();
  expect(screen.getByText('Faraday Cup Status')).toBeInTheDocument();
  expect(screen.getByText('120 uA')).toBeInTheDocument();
  expect(screen.getByText('42 pulses')).toBeInTheDocument();
  expect(screen.getByText('UNKNOWN')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Set Laser_SC Shutter ON' }));
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  const [url, options] = fetchWithHardwareApproval.mock.calls[0];
  expect(url).toContain('/api/daqmx/device/control%2FDAQ%2FTRANCON-DAQ/write');
  expect(JSON.parse(options.body)).toEqual({
    channel: 'Laser_SC Shutter', value: 1, command_variant: 'write_digital_output',
  });
});

test('uses the guarded counter-reset endpoint', async () => {
  render(<DAQmxClients deviceOverride={physicalDevice} />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Open card' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Open card' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Reset counter' }));

  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  const [url, options] = fetchWithHardwareApproval.mock.calls[0];
  expect(url).toContain('/counter/reset');
  expect(JSON.parse(options.body)).toEqual({
    channel: 'ELYSE Pulse Counter', command_variant: 'reset_counter',
  });
});
