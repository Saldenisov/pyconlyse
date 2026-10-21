import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AcquisitionCommands, { AcquisitionCommand } from './AcquisitionCommands';

beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true,
    value: { getRandomValues: (buffer) => { buffer.fill(37); return buffer; } } });
});

const state = (change = {}) => ({ session_id: 'a'.repeat(32), revision: 7, source_selected: true,
  state: 'RUNNING', capabilities: { 'modulator.general.start': { enabled: true } }, commands: [], ...change });
function setup(value = state()) {
  const client = { controlState: jest.fn().mockResolvedValue(value), command: jest.fn().mockResolvedValue({ receipt: { outcome: 'QUEUED' } }) };
  const view = render(<AcquisitionCommands client={client}>
    <AcquisitionCommand operation="modulator.general.start" name="Marche GENERAL · commande désactivée">M</AcquisitionCommand>
    <AcquisitionCommand name="Unsupported">X</AcquisitionCommand>
  </AcquisitionCommands>);
  return { client, ...view };
}

test('only server-permitted commands enable; explicit confirmation, no optimistic equipment state', async () => {
  const { client } = setup();
  const button = await screen.findByRole('button', { name: 'Marche GENERAL' });
  expect(button).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Unsupported' })).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
  fireEvent.click(button);
  expect(screen.getByRole('dialog')).toHaveTextContent('CANON et SECTION confirmée pendant 2 s');
  expect(screen.getByRole('button', { name: 'Annuler' })).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0]).toEqual(expect.objectContaining({
    operation: 'modulator.general.start', session_id: 'a'.repeat(32), expected_revision: 7, operator_confirmed: true, value: null,
  }));
  expect(client.command.mock.calls[0][0].command_id).toMatch(/^[a-f0-9]{32}$/);
  expect(await screen.findByRole('status')).toHaveTextContent('QUEUED');
});

test('cancel and escape never submit', async () => {
  const { client } = setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Marche GENERAL' }));
  fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
  fireEvent.click(screen.getByRole('button', { name: 'Marche GENERAL' }));
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(client.command).not.toHaveBeenCalled();
});

test('lost response is never retried automatically', async () => {
  const { client } = setup();
  client.command.mockRejectedValue(new Error('reply lost'));
  fireEvent.click(await screen.findByRole('button', { name: 'Marche GENERAL' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Aucun renvoi automatique');
  expect(client.command).toHaveBeenCalledTimes(1);
});

test('persisted unknown command is displayed, never submitted on mount', async () => {
  const { client } = setup(state({ capabilities: {}, commands: [{ operation: 'chauffage.start', outcome: 'INDETERMINATE' }] }));
  expect(await screen.findByText(/Ne pas renvoyer la commande/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Marche GENERAL/ })).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
});

test('runtime revision changing while dialog is open requires fresh confirmation', async () => {
  jest.useFakeTimers();
  try {
    const { client } = setup();
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: 'Marche GENERAL' }));
    client.controlState.mockResolvedValue(state({ revision: 8 }));
    await act(async () => { jest.advanceTimersByTime(1000); });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
    expect(client.command).not.toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent('modifié ou périmé');
  } finally { jest.useRealTimers(); }
});
