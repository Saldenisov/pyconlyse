import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AcquisitionCommands, { COMMAND_INTENTS_KEY } from './AcquisitionCommands';
import AcquisitionSynchronizationControls from './AcquisitionSynchronizationControls';
import { syncTicks, validSyncValue } from './acquisitionCommandValue';

const state = () => ({ source_selected: true, source_mode: 'PYTHON_NATIVE', session_id: 'a'.repeat(32),
  revision: 7, state: 'RUNNING', commands: [], synchronization: { running_counters: [0, 1, 2, 5, 6, 7],
    commanded_ticks: {}, uncertain_counters: [] }, capabilities: { 'counter_timing.set': { enabled: true, reason: '' } } });

beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true,
    value: { getRandomValues: (buffer) => { buffer.fill(43); return buffer; } } });
});
beforeEach(() => window.sessionStorage.clear());
afterEach(() => jest.useRealTimers());
function mount(value = state()) {
  const client = { controlState: jest.fn().mockResolvedValue(value),
    command: jest.fn().mockResolvedValue({ receipt: { outcome: 'QUEUED' } }) };
  render(<AcquisitionCommands client={client}><AcquisitionSynchronizationControls /></AcquisitionCommands>);
  return client;
}
const apply = () => screen.getByRole('button', { name: 'Appliquer synchronisation C10' });
const fill = () => {
  fireEvent.change(screen.getByLabelText('Délai (µs)'), { target: { value: '1.25' } });
  fireEvent.change(screen.getByLabelText('Largeur (µs)'), { target: { value: '3.5' } });
};

test('eight named C10 outputs, blank draft and no fictional current bank or editable C11', async () => {
  const client = mount();
  await screen.findByText(/Compteur en marche selon/);
  expect(screen.getAllByRole('option')).toHaveLength(8);
  expect(screen.getByLabelText('Délai (µs)')).toHaveValue(null);
  expect(apply()).toBeDisabled();
  expect(screen.getByLabelText('Dernières propriétés commandées')).toHaveTextContent('indisponibles');
  expect(client.command).not.toHaveBeenCalled();
});

test('confirmation freezes exact pair and submits one named intent without another stage', async () => {
  const client = mount(); fill();
  await waitFor(() => expect(apply()).toBeEnabled());
  fireEvent.click(apply());
  const modal = screen.getByRole('dialog');
  expect(modal).toHaveTextContent('C10/ctr0 : délai 1.25 µs ; largeur 3.5 µs');
  expect(client.command).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0]).toEqual(expect.objectContaining({ operation: 'counter_timing.set',
    session_id: 'a'.repeat(32), expected_revision: 7, operator_confirmed: true,
    value: { counter: 0, delay_us: 1.25, width_us: 3.5 } }));
});

test('editing pair invalidates frozen confirmation without sending', async () => {
  const client = mount(); fill();
  await waitFor(() => expect(apply()).toBeEnabled()); fireEvent.click(apply());
  fireEvent.change(screen.getByLabelText('Largeur (µs)'), { target: { value: '4' } });
  expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
  expect(screen.getByRole('dialog')).toHaveTextContent('largeur 3.5 µs');
  expect(client.command).not.toHaveBeenCalled();
});

test('equal structured value on metadata refresh does not spuriously invalidate confirmation', async () => {
  jest.useFakeTimers(); mount(); fill();
  await waitFor(() => expect(apply()).toBeEnabled()); fireEvent.click(apply());
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Confirmer' })).toBeEnabled();
});

test('stopped modulator counter keeps editable draft but never implicitly starts', async () => {
  const client = mount();
  fireEvent.change(screen.getByLabelText('Sortie C10'), { target: { value: '3' } }); fill();
  await screen.findByText(/Compteur arrêté ou état indisponible/);
  expect(apply()).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
});

test('VI mode cannot enable timing even with malicious capabilities and running flags', async () => {
  const client = mount({ ...state(), source_selected: false, source_mode: 'LABVIEW_BRIDGE' }); fill();
  await screen.findByText(/relais VI/);
  expect(apply()).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
});

test('lost response retains structured intent across remount and never replays it', async () => {
  const client = mount(); client.command.mockRejectedValue(new Error('lost response')); fill();
  await waitFor(() => expect(apply()).toBeEnabled()); fireEvent.click(apply());
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await screen.findByText(/Résultat UNKNOWN/);
  const ledger = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
  expect(ledger.intents[0].value).toEqual({ counter: 0, delay_us: 1.25, width_us: 3.5 });
  expect(client.command).toHaveBeenCalledTimes(1);
  cleanup();
  const replacement = mount(); fill();
  await screen.findByText(/Intention non résolue/);
  expect(apply()).toBeDisabled();
  expect(replacement.command).not.toHaveBeenCalled();
});

test('source ties-to-even conversion and remote numeric refusals match Python policy', () => {
  expect(syncTicks(.075)).toBe(2); expect(syncTicks(.125)).toBe(2);
  const valid = { counter: 0, delay_us: 1.25, width_us: 3.5 };
  expect(validSyncValue(valid)).toBe(true);
  for (const value of [{ ...valid, counter: true }, { ...valid, counter: 8 }, { ...valid, delay_us: .025 },
    { ...valid, delay_us: 0 }, { ...valid, width_us: Infinity }, { ...valid, bank: 'C11' }]) {
    expect(validSyncValue(value)).toBe(false);
  }
});
