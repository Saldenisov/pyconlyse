import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import ITestBeamLinePanel from './ITestBeamLinePanel';

jest.mock('socket.io-client', () => () => ({ on: jest.fn(), emit: jest.fn(), disconnect: jest.fn() }));
jest.mock('../api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const device = 'elyse/pdu/itest';
const v0Order = `pyconlyse.itest.beamline-order.${device}.V0`;
const vd2Order = `pyconlyse.itest.beamline-order.${device}.VD2`;
const tabConfig = { V0: { slots: [1, 3, 5] }, VD2: { slots: [3, 7] } };
const slots = {
  hardware_available: true, ids: [1, 3, 5, 7], names: ['Q1', 'Q3', 'Q5', 'Q7'], states: [0, 1, 0, 0],
  currents_setpoint: [0, 1, 0, 0], currents_meas: [0, 1.01, 0, 0],
  current_limits: [-15, 15, -15, 15, -15, 15, -15, 15],
};
const response = (body) => ({ ok: true, json: async () => body });
const originalFetch = global.fetch;
const displayedSlots = () => screen.getAllByRole('region').map((region) => Number(region.dataset.slotId));

beforeEach(() => {
  window.localStorage.removeItem(v0Order);
  window.localStorage.removeItem(vd2Order);
  fetchWithHardwareApproval.mockReset();
  global.fetch = jest.fn(async (url) => response(url.endsWith('/tab_config') ? { tab_configs: tabConfig } : slots));
});

afterEach(() => { global.fetch = originalFetch; });

test('uses Tango groups and remembers placement by slot across remounts and renames', async () => {
  const view = render(<ITestBeamLinePanel tab="V0" readOnly />);
  await screen.findByRole('region', { name: 'Q1' });
  expect(displayedSlots()).toEqual([1, 3, 5]);
  const transfer = { setData: jest.fn() };
  fireEvent.dragStart(screen.getByRole('button', { name: 'Déplacer Q5' }), { dataTransfer: transfer });
  fireEvent.dragOver(screen.getByRole('region', { name: 'Q1' }), { dataTransfer: transfer });
  expect(screen.getByRole('region', { name: 'Q1' })).toHaveClass('is-drop-target');
  fireEvent.drop(screen.getByRole('region', { name: 'Q1' }), { dataTransfer: transfer });
  expect(displayedSlots()).toEqual([5, 1, 3]);
  expect(JSON.parse(window.localStorage.getItem(v0Order))).toEqual([5, 1, 3]);
  expect(window.localStorage.getItem(vd2Order)).toBeNull();

  view.rerender(<ITestBeamLinePanel tab="VD2" readOnly />);
  await screen.findByRole('region', { name: 'Q7' });
  expect(displayedSlots()).toEqual([3, 7]);
  fireEvent.keyDown(screen.getByRole('button', { name: 'Déplacer Q7' }), { key: 'ArrowLeft' });
  expect(displayedSlots()).toEqual([7, 3]);

  global.fetch.mockImplementation(async (url) => response(url.endsWith('/tab_config')
    ? { tab_configs: tabConfig } : { ...slots, names: ['Q1', 'Q3', 'Nouveau Q5', 'Q7'] }));
  view.rerender(<ITestBeamLinePanel tab="V0" deviceName={device.toUpperCase()} readOnly />);
  await screen.findByRole('region', { name: 'Nouveau Q5' });
  expect(displayedSlots()).toEqual([5, 1, 3]);
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('shows measured and target current and delegates writes to the existing iTest client', async () => {
  const view = render(<ITestBeamLinePanel tab="VD2" readOnly />);
  const card = within(await screen.findByRole('region', { name: 'Q3' }));
  expect(card.getByLabelText('Q3 · Consigne')).toHaveTextContent('1.000');
  expect(card.getByLabelText('Q3 · Lecture')).toHaveTextContent('1.010');
  expect(card.getByRole('button', { name: 'Q3 · marche / arrêt' })).toBeDisabled();
  expect(card.getByRole('button', { name: 'Augmenter la consigne · Q3' })).toBeDisabled();
  expect(card.getByRole('spinbutton')).toHaveAttribute('readonly');
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();

  view.rerender(<ITestBeamLinePanel tab="VD2" />);
  fetchWithHardwareApproval.mockResolvedValueOnce(response({ success: true, slot_id: 3, current_setpoint: 1.1 }));
  fireEvent.click(card.getByRole('button', { name: 'Augmenter la consigne · Q3' }));
  await waitFor(() => expect(card.getByLabelText('Q3 · Consigne')).toHaveTextContent('1.100'));
  expect(fetchWithHardwareApproval).toHaveBeenCalledWith(`/api/device/itest/${device}/slot/3/current`,
    expect.objectContaining({ body: JSON.stringify({ value: 1.1 }) }));

  fetchWithHardwareApproval.mockResolvedValueOnce(response({ success: true }));
  fireEvent.click(card.getByRole('button', { name: 'Q3 · marche / arrêt' }));
  await screen.findByRole('region', { name: 'Q3' });
  expect(fetchWithHardwareApproval).toHaveBeenLastCalledWith(`/api/device/itest/${device}/slot/3/output`,
    expect.objectContaining({ body: JSON.stringify({ state: 0 }) }));
});

test('shows the configured physical slots without values or controls while the device is in fault', async () => {
  global.fetch.mockImplementation(async (url) => response(url.endsWith('/tab_config')
    ? { tab_configs: tabConfig, slot_names: { 3: 'T1-2', 7: 'Dip1' } }
    : { ...slots, hardware_available: false, hardware_state: 'FAULT' }));
  render(<ITestBeamLinePanel tab="VD2" />);
  expect(await screen.findByText('Télémétrie iTest indisponible')).toHaveTextContent('Télémétrie iTest indisponible');
  const card = within(await screen.findByRole('region', { name: 'Dip1' }));
  expect(card.getByLabelText('Dip1 · Lecture')).toHaveTextContent('—');
  expect(card.getByRole('button', { name: 'Dip1 · marche / arrêt' })).toBeDisabled();
  expect(card.getByRole('spinbutton')).toHaveValue(null);
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});
