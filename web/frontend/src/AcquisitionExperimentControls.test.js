import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AcquisitionCommands from './AcquisitionCommands';
import AcquisitionExperimentControls from './AcquisitionExperimentControls';

const stages = ['modulator.general', 'chauffage', 'prema', 'focales', 'relays_ht', 'alimentation_ht', 'modulator_impulse'];
const pulses = ['faraday_1.en_pulse', 'faraday_3.en_pulse', 'laser_mirror.en_pulse', 'laser_mirror.hors_pulse'];
const state = (beamline = false) => ({ session_id: 'a'.repeat(32), revision: 7, source_selected: true,
  state: 'RUNNING', commands: [], capabilities: Object.fromEntries([
    ...stages.flatMap((name) => [`${name}.start`, `${name}.stop`]), 'ht_voltage.set', ...(beamline ? pulses : []),
  ].map((name) => [name, { enabled: true, reason: '' }])) });

beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true,
    value: { getRandomValues: (buffer) => { buffer.fill(37); return buffer; } } });
});
beforeEach(() => { window.sessionStorage.clear(); });

function mount(value = state()) {
  const client = { controlState: jest.fn().mockResolvedValue(value),
    command: jest.fn().mockResolvedValue({ receipt: { outcome: 'QUEUED' } }) };
  render(<AcquisitionCommands client={client}><AcquisitionExperimentControls /></AcquisitionCommands>);
  return client;
}

test('all seven stages require individually confirmed commands; no automatic next stage', async () => {
  const client = mount();
  for (const label of ['General', 'Chauffage', 'PREMA', 'Focales', 'Relais HT', 'Alimentation HT', 'Impulsions modulateur']) {
    await waitFor(() => expect(screen.getByRole('button', { name: `Marche ${label}` })).toBeEnabled());
    expect(screen.getByRole('button', { name: `Arrêt ${label}` })).toBeEnabled();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Marche General' }));
  expect(client.command).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0].operation).toBe('modulator.general.start');
  expect(client.command.mock.calls.some(([command]) => command.operation === 'chauffage.start')).toBe(false);
});

test('HT starts empty, requires finite explicit input and shows exact frozen numeric value', async () => {
  const client = mount();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  const prepare = screen.getByRole('button', { name: 'Appliquer consigne HT' });
  expect(prepare).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Valeur demandée HT (kV)'), { target: { value: '8.625' } });
  expect(prepare).toBeEnabled();
  fireEvent.click(prepare);
  expect(screen.getByRole('dialog')).toHaveTextContent('8.625 kV');
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0]).toEqual(expect.objectContaining({ operation: 'ht_voltage.set', value: 8.625 }));
});

test('editing HT while confirmation is open requires a new explicit confirmation', async () => {
  const client = mount();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  const input = screen.getByLabelText('Valeur demandée HT (kV)');
  fireEvent.change(input, { target: { value: '8' } });
  fireEvent.click(screen.getByRole('button', { name: 'Appliquer consigne HT' }));
  fireEvent.change(input, { target: { value: '9' } });
  expect(screen.getByRole('dialog')).toHaveTextContent('8 kV');
  expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
});

test('unqualified or absent beamline capabilities stay disabled with honest source-pulse labels', async () => {
  const client = mount();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  for (const label of ['Faraday 1 — impulsion source EN', 'Faraday 3 — impulsion source EN',
    'Miroir laser — impulsion source EN', 'Miroir laser — impulsion source HORS']) {
    expect(screen.getByRole('button', { name: label })).toBeDisabled();
  }
  expect(screen.getByText(/ambiguïté EN\/HORS de Faraday 3/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Faraday.*HORS|ouvrir|fermer/i })).not.toBeInTheDocument();
  expect(client.command).not.toHaveBeenCalled();
});

test.each([
  ['Faraday 1 — impulsion source EN', 'faraday_1.en_pulse'],
  ['Faraday 3 — impulsion source EN', 'faraday_3.en_pulse'],
  ['Miroir laser — impulsion source EN', 'laser_mirror.en_pulse'],
  ['Miroir laser — impulsion source HORS', 'laser_mirror.hors_pulse'],
])('qualified pulse %s sends only its exact source operation, never a position alias', async (label, operation) => {
  const client = mount(state(true));
  await waitFor(() => expect(screen.getByRole('button', { name: label })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: label }));
  expect(client.command).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0]).toEqual(expect.objectContaining({ operation, value: null }));
});
