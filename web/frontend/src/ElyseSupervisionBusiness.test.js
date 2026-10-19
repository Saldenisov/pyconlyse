import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ElyseSupervisionBusiness from './ElyseSupervisionBusiness';

beforeAll(() => {
  // Older CRA/jsdom omits Web Crypto; browsers expose getRandomValues on HTTP too.
  Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto });
});

test('restores lifecycle state and phase without replaying initialization', async () => {
  const { client } = fixture({ acq: { mode: 'SIMULATION', quality: 'SIMULATED', revision: '30',
    lifecycle: { state: 'RUNNING', phase: 'completion', error: '' } } });
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByText('Cycle ACQ simulé : RUNNING')).toBeInTheDocument();
  expect(client.submitIntent).not.toHaveBeenCalled();
  expect(client.stageIntent).not.toHaveBeenCalled();
});

test('general stop requires explicit confirmation and cancellation sends nothing', async () => {
  const command = { page: 'Cycle ACQ', control: 'Arrêt général ACQ', kind: 'PROCEDURE',
    procedure: 'acq.stop', lifecycle: true, blocked_reason: '' };
  const intent = { intent_id: 'stop', request: { page: command.page, control: command.control },
    plan: command, state: 'DRAFT', error: '' };
  const { client } = fixture({ catalog: [command], intents: [intent], submission_allowed: true,
    acq: { mode: 'SIMULATION', quality: 'SIMULATED', revision: '31',
      lifecycle: { state: 'RUNNING', phase: 'completion', error: '' } } });
  render(<ElyseSupervisionBusiness client={client} />);
  const button = await screen.findByRole('button', { name: 'Soumettre à ACQ simulée' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(screen.getByRole('dialog', { name: 'Confirmer l’arrêt général ACQ simulé ?' })).toBeInTheDocument();
  expect(client.submitIntent).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(client.submitIntent).not.toHaveBeenCalled();
  fireEvent.click(button);
  expect(screen.getByRole('button', { name: 'Confirmer l’arrêt simulé' })).toHaveFocus();
  fireEvent.submit(screen.getByRole('button', { name: 'Confirmer l’arrêt simulé' }).closest('form'));
  await waitFor(() => expect(client.submitIntent).toHaveBeenCalledTimes(1));
  expect(client.submitIntent).toHaveBeenCalledWith('stop', '31', expect.any(AbortSignal));
});

test('restored unknown lifecycle is excluded and retains its failure message', async () => {
  const { client } = fixture({ busy: true, submission_allowed: false,
    acq: { mode: 'SIMULATION', quality: 'SIMULATED', revision: '32',
      lifecycle: { state: 'UNKNOWN', phase: 'Arrêt', error: 'ACQ restarted during lifecycle' } } });
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByText('Cycle ACQ simulé : UNKNOWN')).toBeInTheDocument();
  expect(screen.getByText('ACQ restarted during lifecycle')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Soumettre à ACQ simulée' })).toBeDisabled();
  expect(client.submitIntent).not.toHaveBeenCalled();
});

function fixture(extra = {}) {
  const command = { page: 'Page Fluides', control: 'Marche régulation', kind: 'PROCEDURE',
    procedure: 'cooling_start', blocked_reason: '' };
  const intent = { intent_id: 'saved-1', request: { page: command.page, control: command.control },
    plan: command, state: 'DRAFT', error: '', updated_at: '2026-10-07T12:00:00+00:00' };
  const data = { schema_version: 1, execution_allowed: false, catalog: [command], intents: [intent],
    events: [{ seq: 1, intent_id: 'saved-1', state: 'DRAFT', message: 'Saved without submission', recorded_at: intent.updated_at }],
    acq: { host: '10.20.30.10', mode: 'UNCONFIGURED', quality: 'UNAVAILABLE', revision: null, error: 'ACQ transport not configured' },
    busy: false, submission_allowed: false, ...extra };
  return { data, intent, client: {
    business: jest.fn().mockImplementation(async () => data),
    stageIntent: jest.fn().mockImplementation(async (request) => {
      const item = { ...intent, intent_id: request.intent_id, request };
      data.intents = [item, ...data.intents];
      return { intent: item };
    }),
    submitIntent: jest.fn().mockImplementation(async () => {
      data.intents = [{ ...intent, state: 'RUNNING' }];
      data.busy = true; data.submission_allowed = false;
      return { intent: data.intents[0] };
    }),
  } };
}

test('restores saved intents, distinguishes offline ACQ, never submits on mount', async () => {
  const { client } = fixture();
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByText('Marche régulation · DRAFT', { selector: 'strong' })).toBeInTheDocument();
  expect(screen.getByText('ACQ transport not configured')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Soumettre à ACQ simulée' })).toBeDisabled();
  expect(client.submitIntent).not.toHaveBeenCalled();
  expect(client.stageIntent).not.toHaveBeenCalled();
});

test('shows configured remote backend endpoint without exposing authentication key', async () => {
  const { client } = fixture({ acq: { host: '10.20.30.10', mode: 'SIMULATION', quality: 'SIMULATED',
    endpoint: 'tcp://10.20.30.10:8765', revision: '1', error: '' } });
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByText('Transport backend : tcp://10.20.30.10:8765')).toBeInTheDocument();
  expect(client.submitIntent).not.toHaveBeenCalled();
  expect(screen.queryByText(/SHARED_KEY/)).not.toBeInTheDocument();
});

test('restores ACQ simulated phase trace from the backend without issuing a command', async () => {
  const { client } = fixture({ acq: { host: '10.20.30.10', mode: 'SIMULATION', quality: 'SIMULATED',
    endpoint: 'tcp://127.0.0.1:8765', trace_intent_id: 'saved-1', trace_error: '',
    phases: [{ step_index: 0, operation: 'write_digital', outcome: 'SUCCEEDED',
      detail: { label: 'Emulated heating relay' }, recorded_at: '2026-10-07T12:00:00Z' }] } });
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByText(/Emulated heating relay/)).toBeInTheDocument();
  expect(screen.getByText('Journal ACQ · phases simulées')).toBeInTheDocument();
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test('staging sends only one named intent, not browser DPS telemetry or raw procedure', async () => {
  const { client } = fixture();
  render(<ElyseSupervisionBusiness client={client} />);
  await screen.findByText('Marche régulation · DRAFT', { selector: 'strong' });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer intention' }));
  await waitFor(() => expect(client.stageIntent).toHaveBeenCalledTimes(1));
  const request = client.stageIntent.mock.calls[0][0];
  expect(request).toEqual({ intent_id: expect.stringMatching(/^web-[0-9a-f]{32}$/),
    page: 'Page Fluides', control: 'Marche régulation' });
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test('explicit simulation submission is single flight with revision and survives reload', async () => {
  const { client } = fixture({ submission_allowed: true,
    acq: { host: '10.20.30.10', mode: 'SIMULATION', quality: 'SIMULATED', revision: 'guard-42', error: '' } });
  const view = render(<ElyseSupervisionBusiness client={client} />);
  const submit = await screen.findByRole('button', { name: 'Soumettre à ACQ simulée' });
  await waitFor(() => expect(submit).toBeEnabled());
  fireEvent.click(submit); fireEvent.click(submit);
  await screen.findByText('Marche régulation · RUNNING', { selector: 'strong' });
  expect(client.submitIntent).toHaveBeenCalledTimes(1);
  expect(client.submitIntent).toHaveBeenCalledWith('saved-1', 'guard-42', expect.any(AbortSignal));
  view.unmount();
  render(<ElyseSupervisionBusiness client={client} />);
  await screen.findByText('Marche régulation · RUNNING', { selector: 'strong' });
  expect(screen.getByRole('button', { name: 'Soumettre à ACQ simulée' })).toBeDisabled();
  expect(client.submitIntent).toHaveBeenCalledTimes(1);
});

test('lost receipt is surfaced without retrying the submission', async () => {
  const { client, data } = fixture({ submission_allowed: true,
    acq: { host: '10.20.30.10', mode: 'SIMULATION', quality: 'SIMULATED', revision: '1', error: '' } });
  client.submitIntent.mockImplementation(async () => {
    data.intents[0].state = 'UNKNOWN'; data.busy = true; data.submission_allowed = false;
    throw new Error('Receipt lost');
  });
  render(<ElyseSupervisionBusiness client={client} />);
  const submit = await screen.findByRole('button', { name: 'Soumettre à ACQ simulée' });
  await waitFor(() => expect(submit).toBeEnabled());
  fireEvent.click(submit);
  expect(await screen.findByRole('alert')).toHaveTextContent('Receipt lost');
  await screen.findByText('Marche régulation · UNKNOWN', { selector: 'strong' });
  expect(submit).toBeDisabled();
  expect(client.submitIntent).toHaveBeenCalledTimes(1);
});

test('disconnect removes a previously fresh submission permission', async () => {
  jest.useFakeTimers();
  try {
    const { client } = fixture({ submission_allowed: true });
    const view = render(<ElyseSupervisionBusiness client={client} />);
    await act(async () => {});
    client.business.mockRejectedValue(new Error('Disconnected'));
    await act(async () => { jest.advanceTimersByTime(2000); });
    expect(screen.getByRole('alert')).toHaveTextContent('Disconnected');
    expect(screen.queryByRole('button', { name: 'Soumettre à ACQ simulée' })).not.toBeInTheDocument();
    expect(client.submitIntent).not.toHaveBeenCalled();
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test('unmount aborts pending read and cancels polling', async () => {
  jest.useFakeTimers();
  try {
    const { client } = fixture();
    client.business.mockImplementation(() => new Promise(() => {}));
    const view = render(<ElyseSupervisionBusiness client={client} />);
    const signal = client.business.mock.calls[0][0];
    view.unmount();
    expect(signal.aborted).toBe(true);
    act(() => jest.advanceTimersByTime(10000));
    expect(client.business).toHaveBeenCalledTimes(1);
  } finally { jest.useRealTimers(); }
});

function setpointFixture(extra = {}) {
  const arrow = { page: 'Page Fluides', control: '> Canon', kind: 'SETPOINT',
    numeric_field: 'T° CANON:', delta: 0.1, native_limits: null, target: 'C8NI6703.01',
    procedure: 'setpoint.fluides.2', blocked_reason: '' };
  const result = fixture({ catalog: [arrow], intents: [], setpoint_submission_allowed: true,
    acq: { mode: 'SIMULATION', quality: 'SIMULATED', revision: 'arrow-1', error: '',
      setpoints: { 'C8NI6703.01': null } }, ...extra });
  result.client.stageIntent.mockImplementation(async (request) => {
    const item = { intent_id: request.intent_id, request, plan: { ...arrow, requested_value: 20.1 },
      state: 'DRAFT', error: '', updated_at: '2026-10-07T12:00:00Z' };
    result.data.intents = [item];
    return { intent: item };
  });
  return result;
}

test('uninitialized setpoint requires explicit base and never invents zero', async () => {
  const { client } = setpointFixture();
  render(<ElyseSupervisionBusiness client={client} />);
  const input = await screen.findByRole('spinbutton', { name: 'Valeur initiale simulée' });
  const stage = screen.getByRole('button', { name: 'Enregistrer intention' });
  expect(input.value).toBe('');
  expect(stage).toBeDisabled();
  fireEvent.change(input, { target: { value: '20' } });
  expect(stage).toBeEnabled();
  fireEvent.click(stage);
  await waitFor(() => expect(client.stageIntent).toHaveBeenCalledTimes(1));
  expect(client.stageIntent.mock.calls[0][0]).toEqual({ intent_id: expect.stringMatching(/^web-/),
    page: 'Page Fluides', control: '> Canon', base_value: 20 });
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test.each([[25.3, 25.3], [20.200000000000003, 20.2]])('restored server setpoint %s is displayed as %s without changing comparison base', async (raw, displayed) => {
  const { client } = setpointFixture({ acq: { revision: 'r2', setpoints: { 'C8NI6703.01': raw } } });
  render(<ElyseSupervisionBusiness client={client} />);
  const input = await screen.findByRole('spinbutton', { name: 'Valeur simulée ACQ' });
  expect(input).toHaveValue(displayed);
  expect(input).toHaveAttribute('readonly');
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer intention' }));
  await waitFor(() => expect(client.stageIntent).toHaveBeenCalledTimes(1));
  expect(client.stageIntent.mock.calls[0][0].base_value).toBe(raw);
});

test('setpoint submission uses its own permission while a procedure is busy', async () => {
  const { client, data } = setpointFixture({ busy: true, submission_allowed: false });
  render(<ElyseSupervisionBusiness client={client} />);
  fireEvent.change(await screen.findByRole('spinbutton', { name: 'Valeur initiale simulée' }), { target: { value: '20' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer intention' }));
  await screen.findByText('> Canon · DRAFT', { selector: 'strong' });
  const submit = screen.getByRole('button', { name: 'Soumettre à ACQ simulée' });
  expect(submit).toBeEnabled();
  client.submitIntent.mockImplementation(async () => {
    data.intents[0] = { ...data.intents[0], state: 'SUCCEEDED' };
    return { intent: data.intents[0] };
  });
  fireEvent.click(submit); fireEvent.click(submit);
  await screen.findByText('> Canon · SUCCEEDED', { selector: 'strong' });
  expect(client.submitIntent).toHaveBeenCalledTimes(1);
  expect(submit).toBeDisabled();
});

test('unknown outcome disables the separate setpoint lane', async () => {
  const { client } = setpointFixture({ busy: true, setpoint_submission_allowed: false });
  render(<ElyseSupervisionBusiness client={client} />);
  fireEvent.change(await screen.findByRole('spinbutton', { name: 'Valeur initiale simulée' }), { target: { value: '20' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer intention' }));
  await screen.findByText('> Canon · DRAFT', { selector: 'strong' });
  expect(screen.getByRole('button', { name: 'Soumettre à ACQ simulée' })).toBeDisabled();
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test('selected historical intent restores its own trace without resubmitting', async () => {
  const { client, data } = fixture();
  data.intents[0].state = 'SUCCEEDED';
  client.intentTrace = jest.fn().mockResolvedValue({ intent_id: 'saved-1', phases: [
    { step_index: 0, operation: 'setpoint', outcome: 'SUCCEEDED', detail: { control: '> Canon', base_value: 20, value: 20.1 }, recorded_at: '2026-10-07T12:00:00Z' },
  ], error: '' });
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByText(/20 → 20.1/)).toBeInTheDocument();
  expect(client.intentTrace).toHaveBeenCalledWith('saved-1', expect.any(AbortSignal));
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test('reload restores saved page, arrow and explicit draft base without submitting', async () => {
  const arrow = { page: 'Page HF', control: '> Att HF', kind: 'SETPOINT', numeric_field: 'Cons Atténuateur HF',
    target: 'C8NI6703.04', blocked_reason: '', procedure: 'setpoint.hf.4' };
  const { client } = fixture({ catalog: [{ page: 'Page Fluides', control: 'Marche régulation', kind: 'PROCEDURE' }, arrow],
    intents: [{ intent_id: 'last-arrow', request: { page: arrow.page, control: arrow.control, base_value: 15 },
      plan: arrow, state: 'DRAFT', error: '', updated_at: '2026-10-07T12:00:00Z' }],
    acq: { setpoints: { 'C8NI6703.04': null } } });
  render(<ElyseSupervisionBusiness client={client} />);
  expect(await screen.findByRole('spinbutton', { name: 'Valeur initiale simulée' })).toHaveValue(15);
  expect(screen.getByRole('combobox', { name: 'Page métier' })).toHaveValue('Page HF');
  expect(screen.getByRole('combobox', { name: 'Commande métier' })).toHaveValue('> Att HF');
  expect(client.stageIntent).not.toHaveBeenCalled();
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test('recovered polling clears connection error without submitting or losing saved intentions', async () => {
  jest.useFakeTimers();
  const { client } = fixture();
  client.business.mockRejectedValueOnce(new Error('Temporary disconnect'));
  const view = render(<ElyseSupervisionBusiness client={client} />);
  try {
    await screen.findByText('Temporary disconnect');
    await act(async () => { jest.advanceTimersByTime(2000); });
    await screen.findByText('Marche régulation · DRAFT', { selector: 'strong' });
    expect(screen.queryByText('Temporary disconnect')).not.toBeInTheDocument();
    expect(client.submitIntent).not.toHaveBeenCalled();
  } finally { view.unmount(); jest.useRealTimers(); }
});

test('draft never displays another intents ACQ trace as its own', async () => {
  const { client } = fixture({ acq: { trace_intent_id: 'other',
    phases: [{ step_index: 0, operation: 'write_digital', outcome: 'SUCCEEDED', detail: { label: 'Foreign history' } }] } });
  client.intentTrace = jest.fn();
  render(<ElyseSupervisionBusiness client={client} />);
  await screen.findByText('Marche régulation · DRAFT', { selector: 'strong' });
  expect(screen.queryByText(/Foreign history/)).not.toBeInTheDocument();
  expect(client.intentTrace).not.toHaveBeenCalled();
});
