import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AcquisitionCommands, { AcquisitionCommand, COMMAND_INTENTS_KEY } from './AcquisitionCommands';

beforeEach(() => { window.sessionStorage.clear(); });

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
    await waitFor(() => expect(screen.getByRole('button', { name: 'Marche GENERAL' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Marche GENERAL' }));
    client.controlState.mockResolvedValue(state({ revision: 8 }));
    await act(async () => { jest.advanceTimersByTime(1000); });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
    expect(client.command).not.toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent('modifié ou périmé');
  } finally { jest.useRealTimers(); }
});

test('read-only LabVIEW source never enables commands even if an erroneous capability says enabled', async () => {
  const { client } = setup(state({ source_selected: false, source_mode: 'LABVIEW_BRIDGE' }));
  expect(await screen.findByText(/Serveur XP : relais VI/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Marche GENERAL/ })).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
});

test.each([
  { session_id: 'b'.repeat(32) }, { source_selected: false },
  { capabilities: { 'modulator.general.start': { enabled: false, reason: 'COOLING_LOST' } } },
  { capabilities: { 'modulator.general.start': { enabled: true, reason: 'QUALIFICATION_CHANGED' } } },
])('session/source/capability changes invalidate open confirmation: %p', async (change) => {
  jest.useFakeTimers();
  try {
    const { client } = setup();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Marche GENERAL' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Marche GENERAL' }));
    client.controlState.mockResolvedValue(state(change));
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('modifié ou périmé');
    client.controlState.mockResolvedValue(state());
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
    expect(client.command).not.toHaveBeenCalled();
  } finally { jest.useRealTimers(); }
});

test('a hanging status read expires confirmation instead of keeping command authority', async () => {
  jest.useFakeTimers();
  try {
    const { client } = setup();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Marche GENERAL' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Marche GENERAL' }));
    client.controlState.mockImplementation(() => new Promise(() => {}));
    await act(async () => { jest.advanceTimersByTime(3000); });
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
    expect(client.command).not.toHaveBeenCalled();
  } finally { jest.useRealTimers(); }
});

test('a frozen numeric HT value is sent once, including explicit zero', async () => {
  const client = { controlState: jest.fn().mockResolvedValue(state({ capabilities: { 'ht_voltage.set': { enabled: true } } })),
    command: jest.fn().mockResolvedValue({ receipt: { outcome: 'QUEUED' } }) };
  render(<AcquisitionCommands client={client}><AcquisitionCommand operation="ht_voltage.set" name="HT demandée" value={0}>Set</AcquisitionCommand></AcquisitionCommands>);
  await waitFor(() => expect(screen.getByRole('button', { name: 'HT demandée' })).toBeEnabled());
  fireEvent.click(await screen.findByRole('button', { name: 'HT demandée' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('0 kV');
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0]).toEqual(expect.objectContaining({ operation: 'ht_voltage.set', value: 0 }));
});

test('changing numeric draft invalidates confirmation and never silently substitutes the new value', async () => {
  const client = { controlState: jest.fn().mockResolvedValue(state({ capabilities: { 'ht_voltage.set': { enabled: true } } })),
    command: jest.fn().mockResolvedValue({ receipt: { outcome: 'QUEUED' } }) };
  const children = (value) => <AcquisitionCommands client={client}><AcquisitionCommand operation="ht_voltage.set" name="HT demandée" value={value}>Set</AcquisitionCommand></AcquisitionCommands>;
  const view = render(children(8.25));
  await waitFor(() => expect(screen.getByRole('button', { name: 'HT demandée' })).toBeEnabled());
  fireEvent.click(await screen.findByRole('button', { name: 'HT demandée' }));
  view.rerender(children(9.75));
  expect(screen.getByRole('dialog')).toHaveTextContent('8.25 kV');
  expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('Consigne modifiée');
  expect(client.command).not.toHaveBeenCalled();
});

test('unresolved numeric intent persists across remount and empty history cannot authorize a new start', async () => {
  const intent = { command_id: 'c'.repeat(32), session_id: 'a'.repeat(32), expected_revision: 7,
    operation: 'ht_voltage.set', operator_confirmed: true, value: 8.125 };
  window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify({ schema_version: 1, intents: [intent], error: '' }));
  const native = state({ capabilities: { 'modulator.general.start': { enabled: true }, 'modulator.general.stop': { enabled: true } } });
  const client = { controlState: jest.fn().mockResolvedValue(native), command: jest.fn() };
  const panel = <AcquisitionCommands client={client}>
    <AcquisitionCommand operation="modulator.general.start" name="Start">M</AcquisitionCommand>
    <AcquisitionCommand operation="modulator.general.stop" name="Stop">A</AcquisitionCommand>
  </AcquisitionCommands>;
  const view = render(panel);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Stop' })).toBeEnabled());
  expect(screen.getByRole('button', { name: 'Start' })).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('8.125 kV');
  view.unmount();
  render(panel);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Stop' })).toBeEnabled());
  expect(screen.getByRole('button', { name: 'Start' })).toBeDisabled();
  expect(client.command).not.toHaveBeenCalled();
});

test('only matching authoritative terminal receipt reconciles uncertain intent; queued or unrelated results do not', async () => {
  jest.useFakeTimers();
  try {
    const intent = { command_id: 'c'.repeat(32), session_id: 'a'.repeat(32), expected_revision: 7,
      operation: 'ht_voltage.set', operator_confirmed: true, value: 8.125 };
    window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify({ schema_version: 1, intents: [intent], error: '' }));
    const { client } = setup();
    expect(await screen.findByText('Acquisition Python : RUNNING')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Intention non résolue');
    const receipt = { command_id: intent.command_id, session_id: intent.session_id, operation: intent.operation,
      outcome: 'QUEUED', hardware_acknowledged: false, automatic_retry: false };
    for (const change of [state({ commands: [receipt] }), state({ session_id: 'b'.repeat(32), commands: [] }),
      state({ commands: [{ ...receipt, command_id: 'd'.repeat(32), outcome: 'COMPLETED' }] })]) {
      client.controlState.mockResolvedValue(change);
      await act(async () => { jest.advanceTimersByTime(1000); });
      expect(screen.getByRole('button', { name: /Marche GENERAL/ })).toBeDisabled();
    }
    client.controlState.mockResolvedValue(state({ commands: [{ ...receipt, outcome: 'COMPLETED' }] }));
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: 'Marche GENERAL' })).toBeEnabled();
    expect(JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY)).intents).toEqual([]);
    expect(client.command).not.toHaveBeenCalled();
  } finally { jest.useRealTimers(); }
});

test('lost protective stop uses a single reserved slot without dropping a full normal ledger or retrying', async () => {
  jest.useFakeTimers();
  try {
    const intents = Array.from({ length: 16 }, (_, index) => ({ command_id: (index + 1).toString(16).padStart(32, '0'),
      session_id: 'a'.repeat(32), expected_revision: 7, operation: 'ht_voltage.set', operator_confirmed: true, value: index }));
    window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify({ schema_version: 1, intents, error: '' }));
    const client = { controlState: jest.fn().mockResolvedValue(state({ capabilities: { 'modulator.general.stop': { enabled: true } } })),
      command: jest.fn().mockRejectedValue(new Error('Offline lost stop reply')) };
    const panel = <AcquisitionCommands client={client}><AcquisitionCommand operation="modulator.general.stop" name="Stop">A</AcquisitionCommand></AcquisitionCommands>;
    const view = render(panel);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Stop' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
    expect(await screen.findByRole('status')).toHaveTextContent('UNKNOWN');
    const saved = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
    expect(saved.intents).toEqual(intents);
    expect(saved.stop_intent).toEqual(client.command.mock.calls[0][0]);
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Aucun second envoi');
    view.unmount();
    render(panel);
    expect(await screen.findByText('Acquisition Python : RUNNING')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();
    await act(async () => { jest.advanceTimersByTime(5000); });
    expect(client.command).toHaveBeenCalledTimes(1);
    expect(JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY)).intents).toEqual(intents);
  } finally { jest.useRealTimers(); }
});

test('a reloaded unresolved stop never resubmits even if a same-ID authorization refusal could be returned', async () => {
  const stop = { command_id: '25'.repeat(16), session_id: 'a'.repeat(32), expected_revision: 7,
    operation: 'modulator.general.stop', operator_confirmed: true, value: null };
  window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify({ schema_version: 1, intents: [], stop_intent: stop, error: '' }));
  const client = { controlState: jest.fn().mockResolvedValue(state({ capabilities: { 'modulator.general.stop': { enabled: true } } })),
    command: jest.fn().mockResolvedValue({ schema_version: 1, code: 'hardware_approval_required',
      receipt: { ...stop, outcome: 'REJECTED', dispatch_attempted: false, hardware_acknowledged: false, automatic_retry: false } }) };
  render(<AcquisitionCommands client={client}><AcquisitionCommand operation="modulator.general.stop" name="Stop">A</AcquisitionCommand></AcquisitionCommands>);
  expect(await screen.findByText('Acquisition Python : RUNNING')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(client.command).not.toHaveBeenCalled();
  expect(JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY)).stop_intent).toEqual(stop);
});
