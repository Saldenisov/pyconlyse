import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Elyse from './Elyse';
import { COMMAND_INTENTS_KEY } from './AcquisitionCommands';
import { clearHardwareApprovalNonce, getHardwareApprovalNonce } from './api/csrfRequest';

const BANKS = ['C1NI6071E', 'C2NI6071E', 'C3_IN_DIO96', 'C3_OUT_DIO96', 'C4_IN_DIO96', 'C4_OUT_DIO96',
  'C5_IN_DIO96', 'C5_OUT_DIO96', 'C6NI6703', 'C7NI6703', 'C8NI6703', 'C9NI6703', 'C1011NI6602',
  'DPS', 'DPC', 'EPS', 'EPC', 'C12NI1409', 'VDM-A', 'VDM-S', 'VDD', 'VAM-A', 'VAM-S', 'VAD', 'VTA', 'VTS', 'VTL'];
const commandView = (selected = true) => ({ schema_version: 1, mode: selected ? 'XP_CONTROL' : 'LABVIEW_READ_ONLY',
  source_mode: selected ? 'PYTHON_NATIVE' : 'LABVIEW_BRIDGE',
  source_selected: selected, session_id: 'a'.repeat(32), revision: 7, state: 'RUNNING', commands: [],
  capabilities: selected ? { 'modulator.general.start': { enabled: true, reason: '' },
    'modulator.general.stop': { enabled: true, reason: '' },
    'ht_voltage.set': { enabled: true, reason: '' }, 'counter_timing.set': { enabled: true, reason: '' } } : {},
  synchronization: { running_counters: [0, 1, 2, 5, 6, 7], commanded_ticks: {}, uncertain_counters: [] } });

function telemetry(selected = false) {
  return { schema_version: 1, server_state: 'ON', quality: 'FRESH', expected_banks: BANKS,
    stale_after_seconds: 2, error_banks: [], snapshot: { source: selected ? 'python_daqmx_acquisition' : 'copied_labview_telemetry',
      receiver_session: 'offline-test', received_this_process: 27, publications: Object.fromEntries(BANKS.map((bank) => [bank,
        { data: [1.25], age_seconds: .1, stale: false, sequence: 7,
          error: { status: false, code: 0, source: '' }, lv_type: { type: 'Array', element_type: { type: 'DBL' } } }])) } };
}

function authorizationRefusal(command, code, error) {
  return { schema_version: 1, code, error, automatic_retry: false,
    receipt: { command_id: command.command_id, session_id: command.session_id, operation: command.operation,
      outcome: 'REJECTED', hardware_acknowledged: false, automatic_retry: false, dispatch_attempted: false, error } };
}

beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true,
    value: { getRandomValues: (buffer) => { buffer.fill(37); return buffer; } } });
});
beforeEach(() => { window.sessionStorage.clear(); clearHardwareApprovalNonce(); });
afterEach(() => { delete global.fetch; jest.useRealTimers(); });

function mount(selected = true) {
  global.fetch = jest.fn(async (url, options) => {
    if (url === '/api/elyse/acquisition/control') return { ok: true, json: async () => commandView(selected) };
    if (url === '/api/elyse/acquisition/telemetry') return { ok: true, json: async () => telemetry(selected) };
    if (url === '/api/elyse/acquisition/control/commands') {
      const command = JSON.parse(options.body);
      return { ok: true, json: async () => ({ schema_version: 1, receipt: {
        command_id: command.command_id, session_id: command.session_id, operation: command.operation,
        outcome: 'QUEUED', hardware_acknowledged: false, automatic_retry: false } }) };
    }
    throw new Error(`Unexpected external request: ${url}`);
  });
  return render(<Elyse />);
}

test('production Elyse route mounts provider and reachable controls, sends only explicitly confirmed fixed facade request', async () => {
  mount();
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  const start = screen.getByRole('button', { name: 'Marche General' });
  await waitFor(() => expect(start).toBeEnabled());
  expect(screen.getByRole('region', { name: 'Commandes Acquisition Python' })).toBeInTheDocument();
  expect(screen.getByRole('form', { name: 'Hardware approval' })).toBeInTheDocument();
  expect(screen.getByText(/Coller uniquement un nonce accordé séparément/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Hardware approval nonce'), { target: { value: 'c'.repeat(64) } });
  fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));
  expect(getHardwareApprovalNonce()).toBe('c'.repeat(64));
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
  fireEvent.click(start);
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(true));
  const commands = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(commands).toHaveLength(1);
  expect(commands[0][0]).toBe('/api/elyse/acquisition/control/commands');
  expect(commands[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe('c'.repeat(64));
  expect(getHardwareApprovalNonce()).toBeNull();
  expect(JSON.parse(commands[0][1].body)).toEqual(expect.objectContaining({ operation: 'modulator.general.start',
    expected_revision: 7, session_id: 'a'.repeat(32), value: null, operator_confirmed: true }));
  expect(await screen.findByText(/General : QUEUED/)).toBeInTheDocument();
});

test('one persistent telemetry poller feeds connection status and raw banks across tabs', async () => {
  jest.useFakeTimers();
  mount();
  const connection = screen.getByRole('region', { name: 'Connexion unique Acquisition' });
  await waitFor(() => expect(connection).toHaveTextContent('27 / 27 banques'));
  expect(connection).toHaveTextContent('10.20.30.10');
  expect(connection).toHaveTextContent('elyse/acquisition/telemetry');
  expect(connection).toHaveTextContent('NI → acquisition native dans le même serveur XP');
  const reads = () => fetch.mock.calls.filter(([url]) => url === '/api/elyse/acquisition/telemetry').length;
  expect(reads()).toBe(1);
  fireEvent.click(screen.getByRole('tab', { name: 'Acquisition Telemetry' }));
  await act(async () => { jest.advanceTimersByTime(0); });
  expect(reads()).toBe(1); // No extra raw-view reader.
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(reads()).toBe(2);
  expect(fetch.mock.calls.every(([url]) => url.startsWith('/api/elyse/acquisition/'))).toBe(true);
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
});

test('Synchronization tab reaches same confirmed and approved command path', async () => {
  mount();
  fireEvent.click(screen.getByRole('tab', { name: 'Synchronization' }));
  fireEvent.change(screen.getByLabelText('Délai (µs)'), { target: { value: '1.25' } });
  fireEvent.change(screen.getByLabelText('Largeur (µs)'), { target: { value: '3.5' } });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer synchronisation C10' })).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Hardware approval nonce'), { target: { value: 'c'.repeat(64) } });
  fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));
  fireEvent.click(screen.getByRole('button', { name: 'Appliquer synchronisation C10' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(true));
  const posts = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(posts).toHaveLength(1);
  expect(posts[0][0]).toBe('/api/elyse/acquisition/control/commands');
  expect(posts[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe('c'.repeat(64));
  expect(JSON.parse(posts[0][1].body)).toEqual(expect.objectContaining({ operation: 'counter_timing.set',
    value: { counter: 0, delay_us: 1.25, width_us: 3.5 } }));
});

test('the same server changing to VI mode invalidates confirmation without issuing a command', async () => {
  jest.useFakeTimers();
  mount();
  const original = fetch.getMockImplementation();
  let native = true;
  fetch.mockImplementation((url, options) => url === '/api/elyse/acquisition/control'
    ? Promise.resolve({ ok: true, json: async () => commandView(native) }) : original(url, options));
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Marche General' }));
  native = false;
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
  expect(screen.getByRole('region', { name: 'Connexion unique Acquisition' })).toHaveTextContent('VI LabVIEW → relais dans le serveur XP');
  expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(false);
});

test('metadata failure and read recovery never restart XP or replay an operation', async () => {
  jest.useFakeTimers();
  mount();
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  const original = fetch.getMockImplementation();
  let online = false;
  fetch.mockImplementation((url, options) => url === '/api/elyse/acquisition/control' && !online
    ? Promise.resolve({ ok: false, json: async () => ({ error: 'fake DS unavailable' }) }) : original(url, options));
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Marche General' })).toBeDisabled();
  expect(screen.getByRole('region', { name: 'Connexion unique Acquisition' })).toHaveTextContent('UNAVAILABLE');
  online = true;
  await act(async () => { jest.advanceTimersByTime(1000); });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
});

test('legacy Modulator controls remain non-actuating even when native commands are permitted', async () => {
  mount();
  fireEvent.click(screen.getByRole('tab', { name: 'Modulator' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/elyse/acquisition/control', expect.anything()));
  fireEvent.click(screen.getAllByRole('button', { name: 'M' })[0]);
  expect(screen.getByText(/Sending is unavailable in test mode \(Modulator\)/)).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([, options]) => options.method !== 'GET')).toBe(false);
});

test('legacy LabVIEW source keeps Experiment disabled while all 27 bank displays and refresh still work', async () => {
  jest.useFakeTimers();
  mount(false);
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  expect(screen.getByRole('button', { name: 'Marche General' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Faraday 3 — impulsion source EN' })).toBeDisabled();
  fireEvent.click(screen.getByRole('tab', { name: 'Acquisition Telemetry' }));
  expect(await screen.findByText('Flux récent')).toBeInTheDocument();
  const banks = screen.getByRole('navigation', { name: 'Banques de télémétrie' });
  expect(within(banks).getAllByRole('button')).toHaveLength(27);
  expect(screen.getByText('27 / 27')).toBeInTheDocument();
  const before = fetch.mock.calls.filter(([url]) => url === '/api/elyse/acquisition/telemetry').length;
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
  await act(async () => { jest.advanceTimersByTime(0); });
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url === '/api/elyse/acquisition/telemetry').length).toBeGreaterThan(before));
  expect(fetch.mock.calls.some(([, options]) => options.method !== 'GET')).toBe(false);
});

test('real page timeout keeps UNKNOWN numeric intent latched while fresh empty history permits only General stop', async () => {
  jest.useFakeTimers();
  mount();
  const normalFetch = fetch.getMockImplementation();
  fetch.mockImplementation((url, options) => url.endsWith('/commands') ? new Promise(() => {}) : normalFetch(url, options));
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Valeur demandée HT (kV)'), { target: { value: '8.125' } });
  fireEvent.click(screen.getByRole('button', { name: 'Appliquer consigne HT' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  for (let second = 0; second < 11; second += 1) {
    await act(async () => { jest.advanceTimersByTime(1000); });
  }
  expect(within(screen.getByLabelText('État commandes Acquisition')).getByRole('status')).toHaveTextContent('UNKNOWN');
  expect(screen.getByRole('alert')).toHaveTextContent('ht_voltage.set = 8.125 kV');
  expect(screen.getByRole('button', { name: 'Marche General' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Appliquer consigne HT' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Arrêt General' })).toBeEnabled();
  const posts = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(posts).toHaveLength(1);
  expect(posts[0][1].signal.aborted).toBe(true);
  const saved = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
  expect(saved.intents).toHaveLength(1);
  expect(saved.intents[0]).toEqual(JSON.parse(posts[0][1].body));
  expect(saved.intents[0].value).toBe(8.125);
});

test('full unresolved ledger preserves all entries and still records a nonce-approved protective General stop separately', async () => {
  const intents = Array.from({ length: 16 }, (_, index) => ({ command_id: (index + 1).toString(16).padStart(32, '0'),
    session_id: 'a'.repeat(32), expected_revision: 7, operation: 'ht_voltage.set', operator_confirmed: true, value: index }));
  window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify({ schema_version: 1, intents, error: '' }));
  mount();
  const normalFetch = fetch.getMockImplementation();
  let reservedDuringSend;
  fetch.mockImplementation((url, options) => {
    if (options.method === 'POST') reservedDuringSend = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
    return normalFetch(url, options);
  });
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Arrêt General' })).toBeEnabled());
  expect(screen.getByRole('button', { name: 'Marche General' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Hardware approval nonce'), { target: { value: 'd'.repeat(64) } });
  fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));
  fireEvent.click(screen.getByRole('button', { name: 'Arrêt General' }));
  expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  expect(await screen.findByText(/Arrêt General : QUEUED/)).toBeInTheDocument();
  const posts = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(posts).toHaveLength(1);
  expect(posts[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe('d'.repeat(64));
  expect(JSON.parse(posts[0][1].body)).toEqual(expect.objectContaining({ operation: 'modulator.general.stop', value: null }));
  expect(reservedDuringSend.intents).toEqual(intents);
  expect(reservedDuringSend.stop_intent).toEqual(JSON.parse(posts[0][1].body));
  const saved = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
  expect(saved.intents).toEqual(intents);
  expect(saved.stop_intent).toBeNull();
  expect(getHardwareApprovalNonce()).toBeNull();
});

test.each([
  [428, 'hardware_approval_required', 'Hardware approval is required', false],
  [409, 'hardware_approval_invalid', 'Hardware approval is expired or has an invalid lifetime', true],
  [403, 'hardware_not_authorized', 'Hardware action is not authorized', false],
])('exact nondispatched approval refusal HTTP%s clears only this attempt; fresh manual arm and confirmation are required',
  async (status, code, error, expired) => {
    jest.useFakeTimers();
    mount();
    const normalFetch = fetch.getMockImplementation();
    let posts = 0;
    fetch.mockImplementation((url, options) => {
      if (options.method === 'POST' && ++posts === 1) {
        const command = JSON.parse(options.body);
        return Promise.resolve({ ok: false, status, json: async () => authorizationRefusal(command, code, error) });
      }
      return normalFetch(url, options);
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
    if (expired) {
      fireEvent.change(screen.getByLabelText('Hardware approval nonce'), { target: { value: 'e'.repeat(64) } });
      fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));
    }
    fireEvent.click(screen.getByRole('button', { name: 'Marche General' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
    expect(await screen.findByText(`Marche General : REJECTED · ${error} · vérifier le retour Acquisition.`)).toBeInTheDocument();
    const rejected = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
    expect(rejected.intents).toEqual([]);
    expect(rejected.stop_intent).toBeNull();
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(posts).toBe(1);
    expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Hardware approval nonce'), { target: { value: 'f'.repeat(64) } });
    fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));
    fireEvent.click(screen.getByRole('button', { name: 'Marche General' }));
    expect(posts).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
    expect(await screen.findByText(/Marche General : QUEUED/)).toBeInTheDocument();
    expect(posts).toBe(2);
    const sent = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
    expect(sent[0][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe(expired ? 'e'.repeat(64) : undefined);
    expect(sent[1][1].headers['X-PYCONLYSE-HARDWARE-APPROVAL']).toBe('f'.repeat(64));
    expect(JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY)).intents).toEqual([]);
  });

test.each(['missing dispatch proof', 'wrong command ID', 'server500'])('unproven rejection remains UNKNOWN in actual page: %s', async (variant) => {
  jest.useFakeTimers();
  mount();
  const normalFetch = fetch.getMockImplementation();
  fetch.mockImplementation((url, options) => {
    if (options.method === 'POST') {
      const proof = authorizationRefusal(JSON.parse(options.body), 'hardware_approval_required', 'Hardware approval is required');
      if (variant === 'missing dispatch proof') delete proof.receipt.dispatch_attempted;
      if (variant === 'wrong command ID') proof.receipt.command_id = 'd'.repeat(32);
      return Promise.resolve({ ok: false, status: variant === 'server500' ? 500 : 428, json: async () => proof });
    }
    return normalFetch(url, options);
  });
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Marche General' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Marche General' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  expect(await screen.findByText(/Résultat UNKNOWN.*Aucun renvoi automatique/)).toBeInTheDocument();
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Marche General' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Arrêt General' })).toBeEnabled();
  const sent = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(sent).toHaveLength(1);
  expect(JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY)).intents).toEqual([JSON.parse(sent[0][1].body)]);
});

test('same-ID nondispatched General stop refusal never clears an older unresolved ordinary intent', async () => {
  jest.useFakeTimers();
  const prior = { command_id: '25'.repeat(16), session_id: 'a'.repeat(32), expected_revision: 7,
    operation: 'ht_voltage.set', operator_confirmed: true, value: 8.125 };
  window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify({ schema_version: 1, intents: [prior], error: '' }));
  mount();
  const normalFetch = fetch.getMockImplementation();
  fetch.mockImplementation((url, options) => options.method === 'POST'
    ? Promise.resolve({ ok: false, status: 428,
      json: async () => authorizationRefusal(JSON.parse(options.body), 'hardware_approval_required', 'Hardware approval is required') })
    : normalFetch(url, options));
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Arrêt General' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Arrêt General' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
  expect(await screen.findByText(/Arrêt General : REJECTED/)).toBeInTheDocument();
  const sent = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(sent).toHaveLength(1);
  expect(JSON.parse(sent[0][1].body).command_id).toBe(prior.command_id);
  const saved = JSON.parse(window.sessionStorage.getItem(COMMAND_INTENTS_KEY));
  expect(saved.intents).toEqual([prior]);
  expect(saved.stop_intent).toBeNull();
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Marche General' })).toBeDisabled();
  expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1);
});
