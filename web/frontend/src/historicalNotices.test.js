import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AcquisitionWatchdog, acquisitionProblems } from './SupervisionHeader';
import { CoolingAlarmDisplay } from './CoolingAlarm';
import AcquisitionCommands, { AcquisitionCommand, COMMAND_INTENTS_KEY } from './AcquisitionCommands';
import { HISTORY_SEEN_KEY, historicalCommandKey, journalNotice } from './historicalNotices';

const warning = 'Prior alarm journal writer did not close cleanly; unacknowledged events may be missing';
const safety = (change = {}) => ({ schema_version: 1, quality: 'FRESH', active: false, machine_active: false,
  circuits: [], stop_state: 'NONE', journal_error: warning, journal_storage_error: '',
  journal_history_warning: warning, journal_revision: 1, experiment_session_id: 'a'.repeat(32), ...change });
const telemetry = (alarm = safety()) => ({ failure: '', elapsed: 0, payload: {
  server_state: 'ON', quality: 'FRESH', cooling_safety: alarm, snapshot: {
    receiver_session: 'receiver-1', received_this_process: 12, publications: {
      x: { stale: false, age_seconds: .1, error: { status: false, code: 0 }, data: [1] },
    },
  },
} });
const command = (change = {}) => ({ command_id: 'e'.repeat(32), session_id: 'b'.repeat(32),
  operation: 'modulator.general.stop', outcome: 'FAILED', error: 'Focales OFF: Chroma timeout',
  hardware_acknowledged: false, automatic_retry: false, ...change });
const control = (commands) => ({ session_id: 'a'.repeat(32), revision: 0, state: 'IDLE',
  source_selected: false, source_mode: 'LABVIEW_BRIDGE', capabilities: {}, commands });

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });
afterEach(() => { jest.restoreAllMocks(); });

test('journal OK hides the same historic notice in header and alarm panel without changing source data', () => {
  const payload = telemetry();
  const before = JSON.stringify(payload);
  const view = render(<><AcquisitionWatchdog telemetry={payload} /><CoolingAlarmDisplay telemetry={payload} /></>);
  expect(screen.getByLabelText('Watchdog Acquisition')).toHaveClass('elyse-watchdog--warning');
  expect(screen.getAllByRole('button', { name: /Marquer l’ancien avertissement/ })).toHaveLength(2);
  fireEvent.click(screen.getAllByRole('button', { name: /Marquer l’ancien avertissement/ })[0]);
  expect(screen.getByLabelText('Watchdog Acquisition')).toHaveTextContent('Watchdog Acquisition : connecté');
  expect(screen.getByLabelText('Watchdog Acquisition')).not.toHaveClass('elyse-watchdog--warning');
  expect(screen.queryByText(/Prior alarm journal/)).not.toBeInTheDocument();
  expect(JSON.stringify(payload)).toBe(before);
  expect(JSON.parse(localStorage.getItem(HISTORY_SEEN_KEY)).keys).toHaveLength(1);
  view.unmount();
  render(<AcquisitionWatchdog telemetry={payload} />);
  expect(screen.queryByRole('button', { name: /Marquer l’ancien avertissement/ })).not.toBeInTheDocument();
});

test.each([
  { experiment_session_id: 'c'.repeat(32) },
  { journal_history_warning: 'A different prior writer gap', journal_error: 'A different prior writer gap' },
])('new journal source epoch/warning reappears after an earlier acknowledgment: %s', (change) => {
  const view = render(<AcquisitionWatchdog telemetry={telemetry()} />);
  fireEvent.click(screen.getByRole('button', { name: /Marquer l’ancien avertissement/ }));
  view.rerender(<AcquisitionWatchdog telemetry={telemetry(safety(change))} />);
  expect(screen.getByRole('button', { name: /Marquer l’ancien avertissement/ })).toBeInTheDocument();
});

test('ordinary journal progress does not revive the same acknowledged writer notice', () => {
  const view = render(<AcquisitionWatchdog telemetry={telemetry()} />);
  fireEvent.click(screen.getByRole('button', { name: /Marquer l’ancien avertissement/ }));
  view.rerender(<AcquisitionWatchdog telemetry={telemetry(safety({ journal_revision: 20 }))} />);
  expect(screen.queryByRole('button', { name: /Marquer l’ancien avertissement/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Watchdog Acquisition')).not.toHaveClass('elyse-watchdog--warning');
});

test('acknowledging history cannot hide current disk failure or active cooling/countdown', () => {
  const alarm = safety({ journal_storage_error: 'CURRENT DISK FAILURE', active: true,
    machine_active: true, automatic_stop_available: false, countdown_required: true,
    remaining_seconds: 90, circuits: [{ incident_id: 'incident-1', circuit: 'CANON',
      started_utc: '2026-11-03T11:00:00+00:00', deadline_utc: '2026-11-03T11:02:00+00:00' }] });
  render(<><AcquisitionWatchdog telemetry={telemetry(alarm)} />
    <CoolingAlarmDisplay telemetry={telemetry(alarm)} /></>);
  fireEvent.click(screen.getAllByRole('button', { name: /Marquer l’ancien avertissement/ })[0]);
  expect(screen.getByLabelText('Watchdog Acquisition')).toHaveClass('elyse-watchdog--fault');
  expect(screen.getAllByText(/CURRENT DISK FAILURE/).length).toBeGreaterThan(0);
  expect(screen.getByRole('heading', { name: /SIGNAL REFROIDISSEMENT ROUGE/ })).toBeInTheDocument();
  expect(screen.getByText(/COUNTDOWN — 90 s/)).toBeInTheDocument();
});

test('a journal error without explicit history metadata never gains a dismiss button', () => {
  const alarm = safety({ journal_history_warning: '', journal_error: 'Disk unavailable' });
  render(<AcquisitionWatchdog telemetry={telemetry(alarm)} />);
  expect(screen.getByLabelText('Watchdog Acquisition')).toHaveClass('elyse-watchdog--fault');
  expect(screen.queryByRole('button', { name: /Marquer l’ancien avertissement/ })).not.toBeInTheDocument();
  expect(journalNotice(alarm).currentError).toBe('Disk unavailable');
});

test('failed browser persistence leaves the notice visible', () => {
  render(<AcquisitionWatchdog telemetry={telemetry()} />);
  jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage full'); });
  fireEvent.click(screen.getByRole('button', { name: /Marquer l’ancien avertissement/ }));
  expect(screen.getByLabelText('Watchdog Acquisition')).toHaveTextContent(warning);
  expect(screen.getByRole('alert')).toHaveTextContent('Confirmation non enregistrée');
});

test('one click hides prior terminal command messages, keeps original receipts and sends no command', async () => {
  const receipts = [command(), command({ command_id: 'f'.repeat(32), operation: 'cooling.start' })];
  const before = JSON.stringify(receipts);
  const client = { controlState: jest.fn().mockResolvedValue(control(receipts)), command: jest.fn() };
  const view = render(<AcquisitionCommands client={client}><AcquisitionCommand
    operation="modulator.general.start" name="General">M</AcquisitionCommand></AcquisitionCommands>);
  fireEvent.click(await screen.findByRole('button', { name: 'Marquer les anciennes commandes comme vues' }));
  expect(screen.queryByText(/Chroma timeout/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'General' })).toBeDisabled();
  expect(JSON.stringify(receipts)).toBe(before);
  expect(client.command).not.toHaveBeenCalled();
  expect(sessionStorage.getItem(COMMAND_INTENTS_KEY)).toBeNull();
  view.unmount();
  render(<AcquisitionCommands client={client} />);
  await waitFor(() => expect(client.controlState).toHaveBeenCalledTimes(2));
  expect(screen.queryByText(/Chroma timeout/)).not.toBeInTheDocument();
});

test('current failures and unresolved prior commands remain visible and cannot be dismissed as history', async () => {
  const current = command({ session_id: 'a'.repeat(32) });
  const unresolved = command({ outcome: 'INDETERMINATE', command_id: 'f'.repeat(32) });
  expect(historicalCommandKey(current, 'a'.repeat(32))).toBeNull();
  expect(historicalCommandKey(unresolved, 'a'.repeat(32))).toBeNull();
  const client = { controlState: jest.fn().mockResolvedValue(control([current, unresolved])), command: jest.fn() };
  const view = render(<AcquisitionCommands client={client} />);
  expect(await screen.findByText(/Chroma timeout/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Marquer les anciennes commandes comme vues' })).not.toBeInTheDocument();
  view.unmount();
  client.controlState.mockResolvedValue(control([unresolved]));
  render(<AcquisitionCommands client={client} />);
  expect(await screen.findByText(/Ne pas renvoyer la commande/)).toBeInTheDocument();
  expect(client.command).not.toHaveBeenCalled();
});

test('acknowledging an old message preserves an unrelated unresolved hardware intent', async () => {
  const intent = { command_id: 'c'.repeat(32), session_id: 'a'.repeat(32), expected_revision: 0,
    operation: 'modulator.general.start', value: null };
  const ledger = { schema_version: 1, intents: [intent], stop_intent: null, error: '' };
  sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify(ledger));
  const client = { controlState: jest.fn().mockResolvedValue(control([command()])), command: jest.fn() };
  render(<AcquisitionCommands client={client} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Marquer les anciennes commandes comme vues' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Intention non résolue');
  expect(JSON.parse(sessionStorage.getItem(COMMAND_INTENTS_KEY))).toEqual(ledger);
  expect(client.command).not.toHaveBeenCalled();
});
