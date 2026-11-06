import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import AcquisitionCommands from './AcquisitionCommands';

const first = '1'.repeat(32), second = '2'.repeat(32), future = '3'.repeat(32);
const candidates = () => [
  { incident_id: first, circuit: 'CANON', deadline_utc: '2026-10-26T14:02:00Z' },
  { incident_id: second, circuit: 'SECTION', deadline_utc: '2026-10-26T14:02:15Z' },
];
const state = (change = {}) => ({ source_selected: true, source_mode: 'PYTHON_NATIVE',
  session_id: 'a'.repeat(32), revision: 7, state: 'RUNNING', commands: [],
  capabilities: { 'cooling.confirm_circulation': { enabled: true, reason: '' } },
  cooling_safety: { confirmation_required: true, countdown_required: true, confirmation_candidates: candidates() }, ...change });
const setup = (value = state()) => {
  const client = { controlState: jest.fn().mockResolvedValue(value),
    command: jest.fn().mockResolvedValue({ receipt: { outcome: 'COMPLETED',
      operator_confirmation_only: true, hardware_writes: false } }) };
  render(<AcquisitionCommands client={client}><span>Supervision existante</span></AcquisitionCommands>);
  return client;
};
const open = async () => {
  const button = await screen.findByRole('button', { name: 'Confirmer la circulation physique de l’eau' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  return screen.getByRole('dialog');
};

beforeEach(() => { window.sessionStorage.clear(); });
beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true,
    value: { getRandomValues: (buffer) => { buffer.fill(37); return buffer; } } });
});

test('server incident prompts require an explicit physical observation and send only displayed incident IDs', async () => {
  const client = setup();
  const dialog = await open();
  expect(within(dialog).getByRole('button', { name: 'Annuler' })).toHaveFocus();
  expect(dialog).toHaveTextContent('CANON'); expect(dialog).toHaveTextContent('SECTION');
  expect(dialog).toHaveTextContent('Le signal rouge reste affiché');
  expect(client.command).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Oui, l’eau circule physiquement maintenant' }));
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(1));
  expect(client.command.mock.calls[0][0]).toEqual(expect.objectContaining({
    operation: 'cooling.confirm_circulation', operator_confirmed: true,
    session_id: 'a'.repeat(32), expected_revision: 7, value: { incident_ids: [first, second] },
  }));
});

test('startup red and already confirmed episodes do not create a confirmation action', async () => {
  const client = setup(state({ cooling_safety: { confirmation_required: false, countdown_required: false,
    confirmation_candidates: [], circuits: [{ circuit: 'CANON', water_confirmation_received: true }] } }));
  await screen.findByText('Acquisition Python : RUNNING');
  expect(screen.queryByRole('button', { name: 'Confirmer la circulation physique de l’eau' })).not.toBeInTheDocument();
  expect(client.command).not.toHaveBeenCalled();
});

test('cancel never confirms water or cancels the server deadline', async () => {
  const client = setup();
  const dialog = await open();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Annuler' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('120 s');
  expect(client.command).not.toHaveBeenCalled();
});

test.each(['incident', 'deadline', 'revision', 'session'])('changed %s invalidates the displayed confirmation rather than acknowledging future episodes', async (change) => {
  jest.useFakeTimers();
  try {
    const client = setup();
    const dialog = await open();
    const next = state();
    if (change === 'incident') next.cooling_safety.confirmation_candidates[1].incident_id = future;
    if (change === 'deadline') next.cooling_safety.confirmation_candidates[1].deadline_utc = '2026-10-26T14:03:00Z';
    if (change === 'revision') next.revision = 8;
    if (change === 'session') next.session_id = 'b'.repeat(32);
    client.controlState.mockResolvedValue(next);
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(within(dialog).getByRole('button', { name: 'Oui, l’eau circule physiquement maintenant' })).toBeDisabled();
    expect(client.command).not.toHaveBeenCalled();
  } finally { jest.useRealTimers(); }
});

test('lost confirmation reply never triggers an automatic retry', async () => {
  jest.useFakeTimers();
  try {
    const client = setup(); client.command.mockRejectedValue(new Error('reply lost'));
    const dialog = await open();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Oui, l’eau circule physiquement maintenant' }));
    await act(async () => {});
    await act(async () => { jest.advanceTimersByTime(5000); });
    expect(client.command).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status')).toHaveTextContent('Aucun renvoi automatique');
  } finally { jest.useRealTimers(); }
});

test('invalid incident candidates never provide an enabled acknowledgement', async () => {
  const client = setup(state({ cooling_safety: { confirmation_required: true,
    confirmation_candidates: [{ incident_id: 'not-an-incident', circuit: 'CANON', deadline_utc: '2026-10-26T14:02:00Z' }] } }));
  await screen.findByText('Acquisition Python : RUNNING');
  expect(screen.queryByRole('button', { name: 'Confirmer la circulation physique de l’eau' })).not.toBeInTheDocument();
  expect(client.command).not.toHaveBeenCalled();
});
