import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import VD2PDUControl from './VD2PDUControl';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

jest.mock('../api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const originalFetch = global.fetch;
const response = (payload) => ({ ok: true, status: 200, json: async () => payload });
let sd2;
let vd2;

beforeEach(() => {
  sd2 = [
    { id: 1, name: 'StreakCamSpec', state: 1 },
    { id: 2, name: 'DG645', state: 1 },
    { id: 3, name: 'Power_control', state: 1 },
    { id: 4, name: 'Power_current', state: 0 },
  ];
  vd2 = [
    { id: 1, name: 'Flash Lamp', state: 1 },
    { id: 2, name: 'Xe-lamp-CW', state: 1 },
    { id: 3, name: 'Zaber', state: 1 },
    { id: 4, name: 'NO plug', state: 1 },
  ];
  global.fetch = jest.fn((url) => Promise.resolve(response({
    success: true, state: 'ON', outputs: url.includes('SD2') ? sd2 : vd2,
  })));
  fetchWithHardwareApproval.mockReset();
  fetchWithHardwareApproval.mockImplementation(async (url, options) => {
    if (url.includes('set_channels_states')) {
      const states = JSON.parse(options.body).args;
      const outputs = url.includes('SD2') ? sd2 : vd2;
      outputs.forEach((output, index) => { output.state = states[index]; });
      return response({ success: true });
    }
    return response({ success: true, running: true, server_name: JSON.parse(options.body).server_name });
  });
});

afterEach(() => {
  global.fetch = originalFetch;
  jest.restoreAllMocks();
});

test('shows both VD2 PDUs without switching outputs', async () => {
  render(<VD2PDUControl />);
  expect(await screen.findByLabelText('PDU VD2 output 3 Zaber')).toBeChecked();
  expect(screen.getByLabelText('PDU SD2 output 3 Power_control')).toBeChecked();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('switches one outlet and verifies all other states by readback', async () => {
  render(<VD2PDUControl />);
  const outlet = await screen.findByLabelText('PDU VD2 output 4 NO plug');
  fireEvent.click(outlet);
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  const [url, options] = fetchWithHardwareApproval.mock.calls[0];
  expect(url).toBe('/api/device/manip/VD2/PDU_VD2/command/set_channels_states');
  expect(JSON.parse(options.body)).toEqual({ args: [1, 1, 1, 0] });
  await waitFor(() => expect(outlet).not.toBeChecked());
});

test('right-click requests exact PDU server restart only after confirmation', async () => {
  const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true);
  render(<VD2PDUControl />);
  const card = await screen.findByRole('region', { name: 'PDU SD2' });
  expect(await within(card).findByLabelText('PDU SD2 output 1 StreakCamSpec')).toBeChecked();
  fireEvent.contextMenu(card);
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  fireEvent.click(within(card).getByRole('menuitem', { name: 'Restart DS_Netio_pdu/4_SD2' }));
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  expect(confirm).toHaveBeenCalled();
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({
    action: 'restart', server_name: 'DS_Netio_pdu/4_SD2',
  });
});
