import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import AcqRuntime, { runtimeBank, RUNTIME_BANKS } from './AcqRuntime';

function payload(session = 'a', value = 7.75) {
  return { schema_version: 1, source: 'xp_python_acquisition_runtime', execution_allowed: false, hardware_writes: false,
    quality: 'FRESH', session_id: session.repeat(32), build_id: 'b'.repeat(64), runtime_state: 'RUNNING', state_revision: 0,
    bridge_stale: false, bridge_age_seconds: 0.1, source_stale: false, source_age_seconds: 0.2,
    source_stale_after_seconds: 2, bridge_stale_after_seconds: 3,
    snapshot: { runtime: { runtime_protocol_version: 2, session_id: session.repeat(32), build_id: 'b'.repeat(64),
      state_revision: 0, state: 'RUNNING', recovery: { required: false, reason: '', protection_active: true },
      current_operation: null, error: '', latest: { source: 'python_daqmx_acquisition', simulated: false,
        banks: { ...Object.fromEntries(RUNTIME_BANKS.map(([name, count, kind]) => [name, {
          kind, values: Array(count).fill(kind === 'digital_input' ? false : 0),
        }])), C1_NI6071E_AI: { kind: 'analog_input', values: [value, ...Array(63).fill(0)],
          legacy_scaled_values: [15.5, ...Array(63).fill(0)] },
        C3_DIO96_DI: { kind: 'digital_input', values: [true, ...Array(55).fill(false)] } } } } } };
}
beforeEach(() => { jest.useFakeTimers(); jest.spyOn(global, 'clearInterval'); });
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });
async function mount(client) {
  const view = render(<AcqRuntime client={client} />);
  await screen.findByText('Lecture NI récente');
  return view;
}
async function advance(ms) { await act(async () => { jest.advanceTimersByTime(ms); }); }

test('shows six source-specific typed input banks, identity and separate transport/NI freshness', async () => {
  const client = { status: jest.fn().mockResolvedValue(payload()) };
  const view = await mount(client);
  expect(within(screen.getByRole('navigation', { name: 'Banques Python Acquisition' })).getAllByRole('button')).toHaveLength(6);
  expect(screen.getByText('7.75')).toBeInTheDocument();
  expect(screen.getByText('15.5')).toBeInTheDocument();
  expect(screen.getByText('Transport Everest')).toBeInTheDocument();
  expect(screen.getByText('Lecture NI')).toBeInTheDocument();
  expect(screen.getByText('a'.repeat(32))).toBeInTheDocument();
  expect(screen.getByText('b'.repeat(64))).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Marche|Arrêt|Initialize|Start|Stop/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /C3_DIO96_DI/ }));
  expect(screen.getByText('TRUE')).toBeInTheDocument();
  expect(screen.getAllByText('FALSE')).toHaveLength(55);
  fireEvent.click(screen.getByRole('button', { name: /C4_DIO96_DI/ }));
  expect(screen.getAllByText('FALSE')).toHaveLength(64);
  expect(screen.getAllByRole('row')).toHaveLength(65);
  view.unmount();
});

test('discards measurements immediately on failed poll and restores only a valid fresh response', async () => {
  const client = { status: jest.fn().mockResolvedValueOnce(payload()).mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValue(payload('a', 9.25)) };
  const view = await mount(client);
  await advance(1000);
  expect(screen.getByRole('alert')).toHaveTextContent('offline');
  expect(screen.queryByText('7.75')).not.toBeInTheDocument();
  expect(screen.getByText('Serveur indisponible')).toBeInTheDocument();
  await advance(2000);
  expect(screen.getByText('9.25')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(client.status).toHaveBeenCalledTimes(3);
  view.unmount();
});

test('stale NI values are removed while transport read hangs; no overlapping requests', async () => {
  const client = { status: jest.fn().mockResolvedValueOnce(payload()).mockImplementation(() => new Promise(() => {})) };
  const view = await mount(client);
  await advance(1000);
  expect(client.status).toHaveBeenCalledTimes(2);
  await advance(1500);
  expect(screen.queryByText('7.75')).not.toBeInTheDocument();
  expect(screen.getByText('Mesures périmées · masquées')).toBeInTheDocument();
  await advance(10000);
  expect(client.status).toHaveBeenCalledTimes(2);
  const signal = client.status.mock.calls[1][0];
  view.unmount();
  expect(signal.aborted).toBe(true);
  expect(global.clearInterval).toHaveBeenCalled();
});

test('new session replaces complete image without copying values from former process', async () => {
  const restarted = payload('c', 8.25);
  restarted.snapshot.runtime.latest.banks.C3_DIO96_DI.values[0] = false;
  const client = { status: jest.fn().mockResolvedValueOnce(payload()).mockResolvedValue(restarted) };
  const view = await mount(client);
  await advance(1000);
  expect(screen.getByText('Nouvelle session du serveur : anciennes mesures supprimées.')).toBeInTheDocument();
  expect(screen.getByText('8.25')).toBeInTheDocument();
  expect(screen.queryByText('7.75')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /C3_DIO96_DI/ }));
  expect(screen.queryByText('TRUE')).not.toBeInTheDocument();
  view.unmount();
});

test('normal recovery reason is neutral; inactive ownership barrier is an explicit warning', async () => {
  const next = payload();
  next.snapshot.runtime.recovery.reason = 'NO_UNRELEASED_OWNERSHIP_MARKER';
  const client = { status: jest.fn().mockResolvedValueOnce(next).mockResolvedValue({ ...next,
    snapshot: { runtime: { ...next.snapshot.runtime, recovery: { ...next.snapshot.runtime.recovery, protection_active: false } } } }) };
  const view = await mount(client);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByText(/Diagnostic de récupération : NO_UNRELEASED_OWNERSHIP_MARKER/)).toBeInTheDocument();
  await advance(1000);
  expect(screen.getByRole('alert')).toHaveTextContent('Barrière de propriété persistante inactive');
  view.unmount();
});

test('missing FRESH bank invalidates complete response instead of retaining another current-looking bank', async () => {
  const next = payload(); delete next.snapshot.runtime.latest.banks.C5_DIO96_DI;
  const client = { status: jest.fn().mockResolvedValueOnce(payload()).mockResolvedValue(next) };
  const view = await mount(client);
  await advance(1000);
  expect(screen.getByRole('alert')).toHaveTextContent('Contrat Python Acquisition incompatible');
  expect(screen.queryByText('7.75')).not.toBeInTheDocument();
  expect(screen.getByText('Aucune mesure actuelle validée pour cette banque.')).toBeInTheDocument();
  view.unmount();
});

test.each(['RECOVERY_REQUIRED', 'IDLE', 'EXECUTING', 'FAULT', 'STALE'])('masks measurements for %s without claiming physical OFF', async (quality) => {
  const next = payload(); next.quality = quality;
  if (quality === 'RECOVERY_REQUIRED') { next.snapshot.runtime.recovery.required = true; next.snapshot.runtime.recovery.reason = 'unclean restart'; }
  const client = { status: jest.fn().mockResolvedValueOnce(payload()).mockResolvedValue(next) };
  const view = await mount(client);
  await advance(1000);
  expect(screen.queryByText('7.75')).not.toBeInTheDocument();
  expect(screen.getByText(/Connexion perdue ou récupération requise ≠ équipement arrêté/)).toBeInTheDocument();
  view.unmount();
});

test('rejects incompatible contracts from injected clients and uses bounded failure backoff', async () => {
  const incompatible = payload(); incompatible.execution_allowed = true;
  const client = { status: jest.fn().mockResolvedValue(incompatible) };
  const view = render(<AcqRuntime client={client} />);
  await screen.findByRole('alert');
  expect(screen.queryByText('7.75')).not.toBeInTheDocument();
  for (const seconds of [2, 4, 8, 16, 30, 30]) await advance(seconds * 1000);
  expect(client.status).toHaveBeenCalledTimes(7);
  expect(screen.getByRole('alert')).toHaveTextContent('Nouvelle tentative dans 30 s');
  view.unmount();
  await advance(60000);
  expect(client.status).toHaveBeenCalledTimes(7);
});

test('unmount cancels pending client and late results cannot schedule another poll', async () => {
  let resolve;
  const client = { status: jest.fn().mockImplementation(() => new Promise((done) => { resolve = done; })) };
  const view = render(<AcqRuntime client={client} />);
  const signal = client.status.mock.calls[0][0];
  view.unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => { resolve(payload()); });
  await advance(60000);
  expect(client.status).toHaveBeenCalledTimes(1);
  expect(global.clearInterval).toHaveBeenCalled();
});

test('invalid bank count, mixed types or nonfinite values do not become invented zeroes', () => {
  const data = payload();
  data.snapshot.runtime.latest.banks.C1_NI6071E_AI.values[2] = NaN;
  expect(runtimeBank(data, 'C1_NI6071E_AI')).toBeNull();
  data.snapshot.runtime.latest.banks.C3_DIO96_DI.values[0] = 1;
  expect(runtimeBank(data, 'C3_DIO96_DI')).toBeNull();
  data.snapshot.runtime.latest.banks.C3_DIO96_DI.values.pop();
  expect(runtimeBank(data, 'C3_DIO96_DI')).toBeNull();
});
